from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from dichiarazioni_pubbliche.provenance_quarantine import (
    BoundedDependencyGraph,
    InMemoryProvenanceHoldRegistry,
)
from dichiarazioni_pubbliche.provenance_quarantine_persistence import (
    ProvenanceHoldPersistenceStore,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.source_revalidation import (
    SOURCE_REVALIDATION_VERSION,
    ReobservationState,
    RevalidationDecision,
    RevalidationDisposition,
    SourceSnapshot,
    snapshot_ref,
)
from dichiarazioni_pubbliche.source_revalidation_hold import (
    SourceRevalidationHoldReceipt,
    activate_source_revalidation_hold,
)


@dataclass(frozen=True)
class PersistedSourceRevalidation:
    event_key: str
    previous_snapshot_ref: str
    current_snapshot_ref: str
    previous_capture_id: str | None
    current_capture_id: str | None
    hold_id: str | None


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _availability(snapshot: SourceSnapshot) -> str:
    value = snapshot.availability
    try:
        return (value if isinstance(value, ReobservationState) else ReobservationState(str(value))).value
    except ValueError as exc:
        raise ValueError("SOURCE_REVALIDATION_DURABLE_AVAILABILITY_INVALID") from exc


def _date_text(value: date | None) -> str:
    return value.isoformat() if value is not None else ""


def _snapshot_row(snapshot: SourceSnapshot) -> dict[str, object]:
    if snapshot.observed_at.tzinfo is None:
        raise ValueError("SOURCE_REVALIDATION_DURABLE_OBSERVED_AT_TZ_REQUIRED")
    content_hash = str(snapshot.content_sha256 or "").strip().lower() or None
    if content_hash is not None and (
        len(content_hash) != 64
        or any(ch not in "0123456789abcdef" for ch in content_hash)
    ):
        raise ValueError("SOURCE_REVALIDATION_DURABLE_CONTENT_HASH_INVALID")
    return {
        "snapshot_ref": snapshot_ref(snapshot),
        "source_id": str(snapshot.source_id or "").strip(),
        "observed_at": snapshot.observed_at.isoformat(),
        "availability": _availability(snapshot),
        "content_sha256": content_hash,
        "source_version": str(snapshot.source_version or "").strip() or None,
        "etag": str(snapshot.etag or "").strip() or None,
        "canonical_url": str(snapshot.canonical_url or "").strip(),
        "supersedes_version": str(snapshot.supersedes_version or "").strip() or None,
        "rights_status": str(snapshot.rights_status or "UNKNOWN").strip().upper(),
        "rights_expires_on": snapshot.rights_expires_on,
        "authority_valid_until": snapshot.authority_valid_until,
    }


def _expected_event_key(
    previous: SourceSnapshot,
    current: SourceSnapshot,
    decision: RevalidationDecision,
) -> str:
    codes = tuple(sorted(set(decision.material_change_codes + decision.benign_change_codes)))
    return _sha(
        {
            "version": SOURCE_REVALIDATION_VERSION,
            "source_id": previous.source_id,
            "previous_snapshot_ref": snapshot_ref(previous),
            "current_snapshot_ref": snapshot_ref(current),
            "change_codes": list(codes),
        }
    )


def _snapshot_from_row(row: dict[str, Any]) -> SourceSnapshot:
    observed_at = datetime.fromisoformat(str(row["observed_at"]))
    return SourceSnapshot(
        source_id=str(row["source_id"]),
        observed_at=observed_at,
        availability=str(row["availability"]),
        content_sha256=(str(row["content_sha256"]) if row.get("content_sha256") else None),
        source_version=(str(row["source_version"]) if row.get("source_version") else None),
        etag=(str(row["etag"]) if row.get("etag") else None),
        canonical_url=str(row["canonical_url"]),
        supersedes_version=(
            str(row["supersedes_version"]) if row.get("supersedes_version") else None
        ),
        rights_status=str(row["rights_status"]),
        rights_expires_on=(
            date.fromisoformat(str(row["rights_expires_on"]))
            if row.get("rights_expires_on")
            else None
        ),
        authority_valid_until=(
            date.fromisoformat(str(row["authority_valid_until"]))
            if row.get("authority_valid_until")
            else None
        ),
    )


class SourceRevalidationPersistenceStore(PsqlRuntime):
    """Append-only DP-511 source observations/decisions plus immutable Capture linkage."""

    def _validate_content_source(self, *, content_id: str, source_id: str) -> None:
        raw = self.run(
            """
            SELECT COALESCE(source_id, '')
            FROM content_item
            WHERE id = :'content_id';
            """,
            content_id=content_id,
        ).strip()
        if not raw:
            raise ValueError("SOURCE_REVALIDATION_CONTENT_NOT_FOUND")
        if raw != source_id:
            raise ValueError("SOURCE_REVALIDATION_CONTENT_SOURCE_MISMATCH")

    def _persist_capture(
        self,
        *,
        snapshot: SourceSnapshot,
        content_id: str | None,
    ) -> str | None:
        row = _snapshot_row(snapshot)
        if content_id is None or row["availability"] != ReobservationState.AVAILABLE.value:
            return None
        content_hash = row["content_sha256"]
        if not content_hash:
            return None
        clean_content_id = str(content_id or "").strip()
        if not clean_content_id:
            raise ValueError("SOURCE_REVALIDATION_CONTENT_ID_INVALID")
        self._validate_content_source(content_id=clean_content_id, source_id=str(row["source_id"]))
        proposed_id = "capture:source-revalidation:" + hashlib.sha256(
            f"{clean_content_id}\0{content_hash}".encode("utf-8")
        ).hexdigest()
        raw = self.run(
            """
            WITH inserted AS (
                INSERT INTO content_capture (
                    id, content_id, observed_at, final_url, content_sha256,
                    retrieval_method, retrieval_version, rights_status,
                    retention_class, status, metadata
                ) VALUES (
                    :'capture_id', :'content_id', :'observed_at'::timestamptz,
                    :'final_url', :'content_sha256', 'SOURCE_REVALIDATION',
                    :'retrieval_version', :'rights_status', 'DURABLE_PROVENANCE',
                    'CAPTURED', :'metadata'::jsonb
                )
                ON CONFLICT (content_id, content_sha256) DO NOTHING
                RETURNING id
            )
            SELECT id FROM inserted
            UNION ALL
            SELECT id FROM content_capture
            WHERE content_id = :'content_id'
              AND content_sha256 = :'content_sha256'
              AND NOT EXISTS (SELECT 1 FROM inserted)
            LIMIT 1;
            """,
            capture_id=proposed_id,
            content_id=clean_content_id,
            observed_at=row["observed_at"],
            final_url=row["canonical_url"],
            content_sha256=content_hash,
            retrieval_version=SOURCE_REVALIDATION_VERSION,
            rights_status=row["rights_status"],
            metadata=_canonical_json(
                {
                    "source_revalidation_snapshot_ref": row["snapshot_ref"],
                    "source_version": row["source_version"],
                }
            ),
        ).strip()
        if not raw:
            raise ValueError("SOURCE_REVALIDATION_CAPTURE_PERSIST_FAILED")
        return raw

    def _persist_snapshot(
        self,
        snapshot: SourceSnapshot,
        *,
        content_id: str | None,
    ) -> tuple[str, str | None]:
        row = _snapshot_row(snapshot)
        if not row["source_id"] or not row["canonical_url"]:
            raise ValueError("SOURCE_REVALIDATION_DURABLE_SNAPSHOT_INVALID")
        capture_id = self._persist_capture(snapshot=snapshot, content_id=content_id)
        self.run(
            """
            INSERT INTO source_revalidation_snapshot_durable (
                snapshot_ref, source_id, content_id, capture_id, observed_at,
                availability, content_sha256, source_version, etag, canonical_url,
                supersedes_version, rights_status, rights_expires_on,
                authority_valid_until, snapshot_version
            ) VALUES (
                :'snapshot_ref', :'source_id', NULLIF(:'content_id',''), NULLIF(:'capture_id',''),
                :'observed_at'::timestamptz, :'availability', NULLIF(:'content_sha256',''),
                NULLIF(:'source_version',''), NULLIF(:'etag',''), :'canonical_url',
                NULLIF(:'supersedes_version',''), :'rights_status',
                NULLIF(:'rights_expires_on','')::date,
                NULLIF(:'authority_valid_until','')::date, :'snapshot_version'
            )
            ON CONFLICT (snapshot_ref) DO NOTHING;
            """,
            snapshot_ref=row["snapshot_ref"],
            source_id=row["source_id"],
            content_id=content_id or "",
            capture_id=capture_id or "",
            observed_at=row["observed_at"],
            availability=row["availability"],
            content_sha256=row["content_sha256"] or "",
            source_version=row["source_version"] or "",
            etag=row["etag"] or "",
            canonical_url=row["canonical_url"],
            supersedes_version=row["supersedes_version"] or "",
            rights_status=row["rights_status"],
            rights_expires_on=_date_text(row["rights_expires_on"]),
            authority_valid_until=_date_text(row["authority_valid_until"]),
            snapshot_version=SOURCE_REVALIDATION_VERSION,
        )
        stored = self.run(
            """
            SELECT json_build_object(
                'source_id', source_id,
                'content_id', content_id,
                'capture_id', capture_id,
                'observed_at', observed_at::text,
                'availability', availability,
                'content_sha256', content_sha256,
                'source_version', source_version,
                'etag', etag,
                'canonical_url', canonical_url,
                'supersedes_version', supersedes_version,
                'rights_status', rights_status,
                'rights_expires_on', rights_expires_on::text,
                'authority_valid_until', authority_valid_until::text,
                'snapshot_version', snapshot_version
            )::text
            FROM source_revalidation_snapshot_durable
            WHERE snapshot_ref = :'snapshot_ref';
            """,
            snapshot_ref=row["snapshot_ref"],
        )
        parsed = json.loads(stored or "{}")
        if not isinstance(parsed, dict):
            raise ValueError("SOURCE_REVALIDATION_DURABLE_SNAPSHOT_INVALID")
        replay = _snapshot_from_row(parsed)
        if snapshot_ref(replay) != row["snapshot_ref"]:
            raise ValueError("SOURCE_REVALIDATION_DURABLE_SNAPSHOT_TAMPERED")
        if (parsed.get("content_id") or None) != (content_id or None):
            raise ValueError("SOURCE_REVALIDATION_DURABLE_CONTENT_BINDING_CONFLICT")
        if (parsed.get("capture_id") or None) != capture_id:
            raise ValueError("SOURCE_REVALIDATION_DURABLE_CAPTURE_BINDING_CONFLICT")
        if parsed.get("snapshot_version") != SOURCE_REVALIDATION_VERSION:
            raise ValueError("SOURCE_REVALIDATION_DURABLE_VERSION_INVALID")
        return str(row["snapshot_ref"]), capture_id

    def persist_reobservation(
        self,
        *,
        previous: SourceSnapshot,
        current: SourceSnapshot,
        decision: RevalidationDecision,
        content_id: str | None = None,
    ) -> PersistedSourceRevalidation:
        if decision.version != SOURCE_REVALIDATION_VERSION:
            raise ValueError("SOURCE_REVALIDATION_DURABLE_DECISION_VERSION_INVALID")
        previous_ref = snapshot_ref(previous)
        current_ref = snapshot_ref(current)
        if previous_ref == current_ref:
            raise ValueError("SOURCE_REVALIDATION_DURABLE_NEW_OBSERVATION_REQUIRED")
        if previous.source_id != current.source_id:
            raise ValueError("SOURCE_REVALIDATION_DURABLE_SOURCE_ID_MISMATCH")
        if decision.previous_snapshot_ref != previous_ref:
            raise ValueError("SOURCE_REVALIDATION_DURABLE_PREVIOUS_REF_MISMATCH")
        if decision.current_snapshot_ref != current_ref:
            raise ValueError("SOURCE_REVALIDATION_DURABLE_CURRENT_REF_MISMATCH")
        if decision.event_key != _expected_event_key(previous, current, decision):
            raise ValueError("SOURCE_REVALIDATION_DURABLE_EVENT_KEY_MISMATCH")
        if decision.needs_reanalysis != bool(decision.material_change_codes):
            raise ValueError("SOURCE_REVALIDATION_DURABLE_REANALYSIS_FLAG_INVALID")
        if decision.needs_targeted_hold != (
            decision.disposition is RevalidationDisposition.HOLD_REQUIRED
        ):
            raise ValueError("SOURCE_REVALIDATION_DURABLE_HOLD_FLAG_INVALID")

        previous_ref, previous_capture = self._persist_snapshot(
            previous, content_id=content_id
        )
        current_ref, current_capture = self._persist_snapshot(current, content_id=content_id)
        self.run(
            """
            INSERT INTO source_revalidation_event_durable (
                event_key, source_id, previous_snapshot_ref, current_snapshot_ref,
                disposition, material_change_codes, benign_change_codes,
                needs_reanalysis, needs_targeted_hold, event_version
            ) VALUES (
                :'event_key', :'source_id', :'previous_snapshot_ref', :'current_snapshot_ref',
                :'disposition', :'material_change_codes'::jsonb, :'benign_change_codes'::jsonb,
                :'needs_reanalysis'::boolean, :'needs_targeted_hold'::boolean, :'event_version'
            )
            ON CONFLICT (event_key) DO NOTHING;
            """,
            event_key=decision.event_key,
            source_id=previous.source_id,
            previous_snapshot_ref=previous_ref,
            current_snapshot_ref=current_ref,
            disposition=decision.disposition.value,
            material_change_codes=_canonical_json(list(decision.material_change_codes)),
            benign_change_codes=_canonical_json(list(decision.benign_change_codes)),
            needs_reanalysis="true" if decision.needs_reanalysis else "false",
            needs_targeted_hold="true" if decision.needs_targeted_hold else "false",
            event_version=decision.version,
        )
        raw = self.run(
            """
            SELECT json_build_object(
                'source_id', source_id,
                'previous_snapshot_ref', previous_snapshot_ref,
                'current_snapshot_ref', current_snapshot_ref,
                'disposition', disposition,
                'material_change_codes', material_change_codes,
                'benign_change_codes', benign_change_codes,
                'needs_reanalysis', needs_reanalysis,
                'needs_targeted_hold', needs_targeted_hold,
                'event_version', event_version
            )::text
            FROM source_revalidation_event_durable
            WHERE event_key = :'event_key';
            """,
            event_key=decision.event_key,
        )
        row = json.loads(raw or "{}")
        expected = {
            "source_id": previous.source_id,
            "previous_snapshot_ref": previous_ref,
            "current_snapshot_ref": current_ref,
            "disposition": decision.disposition.value,
            "material_change_codes": list(decision.material_change_codes),
            "benign_change_codes": list(decision.benign_change_codes),
            "needs_reanalysis": decision.needs_reanalysis,
            "needs_targeted_hold": decision.needs_targeted_hold,
            "event_version": decision.version,
        }
        if row != expected:
            raise ValueError("SOURCE_REVALIDATION_DURABLE_EVENT_CONFLICT")
        return PersistedSourceRevalidation(
            event_key=decision.event_key,
            previous_snapshot_ref=previous_ref,
            current_snapshot_ref=current_ref,
            previous_capture_id=previous_capture,
            current_capture_id=current_capture,
            hold_id=None,
        )

    def history_for_source(self, source_id: str) -> tuple[dict[str, Any], ...]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'event_key', event_key,
                'previous_snapshot_ref', previous_snapshot_ref,
                'current_snapshot_ref', current_snapshot_ref,
                'disposition', disposition,
                'material_change_codes', material_change_codes,
                'benign_change_codes', benign_change_codes,
                'needs_reanalysis', needs_reanalysis,
                'needs_targeted_hold', needs_targeted_hold,
                'event_version', event_version
            ) ORDER BY persisted_at, event_key)::text, '[]')
            FROM source_revalidation_event_durable
            WHERE source_id = :'source_id';
            """,
            source_id=source_id,
        )
        rows = json.loads(raw or "[]")
        if not isinstance(rows, list):
            raise ValueError("SOURCE_REVALIDATION_DURABLE_HISTORY_INVALID")
        return tuple(row for row in rows if isinstance(row, dict))


def persist_revalidation_with_hold(
    *,
    store: SourceRevalidationPersistenceStore,
    hold_store: ProvenanceHoldPersistenceStore,
    previous: SourceSnapshot,
    current: SourceSnapshot,
    decision: RevalidationDecision,
    content_id: str | None,
    provider_id: str,
    actor_id: str,
    graph: BoundedDependencyGraph,
    registry: InMemoryProvenanceHoldRegistry,
) -> PersistedSourceRevalidation:
    persisted = store.persist_reobservation(
        previous=previous,
        current=current,
        decision=decision,
        content_id=content_id,
    )
    hold_store.append_dependency_graph(graph)
    hold: SourceRevalidationHoldReceipt | None = activate_source_revalidation_hold(
        decision=decision,
        previous=previous,
        current=current,
        provider_id=provider_id,
        actor_id=actor_id,
        graph=graph,
        registry=registry,
    )
    hold_store.persist_registry(registry=registry, graph=graph)
    return PersistedSourceRevalidation(
        event_key=persisted.event_key,
        previous_snapshot_ref=persisted.previous_snapshot_ref,
        current_snapshot_ref=persisted.current_snapshot_ref,
        previous_capture_id=persisted.previous_capture_id,
        current_capture_id=persisted.current_capture_id,
        hold_id=hold.hold.hold_id if hold is not None else None,
    )


__all__ = [
    "PersistedSourceRevalidation",
    "SourceRevalidationPersistenceStore",
    "persist_revalidation_with_hold",
]
