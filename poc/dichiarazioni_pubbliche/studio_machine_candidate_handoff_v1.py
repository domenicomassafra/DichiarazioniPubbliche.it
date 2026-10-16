"""DP-242 private Studio-to-machine *preview*, not an authority or transition.

Two existing persisted read boundaries are reused. No candidate, annotation,
review_event, machine command or public projection is created by this module.
The eventual B authority must independently authenticate and re-read all inputs
in the same transactional fence; these digests are not signatures or write tokens.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from dichiarazioni_pubbliche.multi_person_batch_v1 import (
    IsolatedBatchPlan,
    PrivateBatchReceiptIndex,
    export_private_batch_receipt_index,
)
from dichiarazioni_pubbliche.studio_candidate_review import (
    inspect_candidate_review_readiness,
)
from dichiarazioni_pubbliche.studio_discovery_inbox_workflow import (
    DiscoveryInboxWorkflow,
    _SELECTED_SQL,
    _present,
)
from dichiarazioni_pubbliche.studio_discovery_triage_contract import (
    _validated_ref,
    _validated_revision,
)


STUDIO_MACHINE_PREVIEW_VERSION = "studio-machine-candidate-preflight-v1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_REQUEST = re.compile(r"[A-Za-z][A-Za-z0-9_:-]{0,127}\Z")


@dataclass(frozen=True)
class CurrentBatchStudioItem:
    """Caller-read current private corpus/rights/identity metadata for one Passage.

    A revision and a hash identify *what* was read; neither establishes an
    authenticated store, independent license review, or machine authority.
    Caller must obtain this independently of the DP-240 receipt.
    """

    passage_id: str
    content_id: str
    capture_id: str
    source_sha256: str
    passage_sha256: str
    selector_fingerprint: str
    speaker_candidate_id: str | None
    identity_review_status: str
    speech_role: str
    speech_act: str
    context_version: str
    context_review_id: str | None
    rights_status: str
    rights_evidence_sha256: str | None
    source_revision: int
    identity_revision: int
    rights_revision: int


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError(f"STUDIO_MACHINE_{name}_INVALID")
    return value


def _key(value: object) -> str:
    if not isinstance(value, str) or not _REQUEST.fullmatch(value):
        raise ValueError("STUDIO_MACHINE_REQUEST_KEY_INVALID")
    return value


def _canonical(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _receipt(payload: dict[str, object], *, request_key: str) -> dict[str, object]:
    # Digest binds the exact scoped intent but is not a durable replay record,
    # credential, approval, receipt from B, or a permission-bearing token.
    fingerprint = hashlib.sha256(
        _canonical(payload | {"request_key": request_key})
    ).hexdigest()
    return payload | {
        "contract_version": STUDIO_MACHINE_PREVIEW_VERSION,
        "intent_fingerprint": fingerprint,
        "private_only": True,
        "preview_only": True,
        "enqueued": False,
        "source_rights_verified": False,
        "human_review_approved": False,
        "machine_review_approved": False,
        "review_authority": False,
        "dispatch_authorized": False,
        "publication_authority": False,
    }


def _reload_hit(
    workflow: DiscoveryInboxWorkflow, *, collection_id: str, hit_id: str
) -> dict[str, object]:
    """Read one persisted scoped Hit, not a caller-supplied HTML/JSON snapshot."""
    try:
        raw = workflow.store.run(
            _SELECTED_SQL, collection_id=collection_id, selected_ids=hit_id, limit=1
        )
    except Exception:
        raise RuntimeError("STUDIO_MACHINE_DISCOVERY_STORE_UNAVAILABLE") from None
    if not isinstance(raw, str) or len(raw) > 48_000:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_RECORD_INVALID")
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_SCOPE_NOT_FOUND")
    try:
        data = json.loads(lines[0])
        if not isinstance(data, dict):
            raise ValueError("STUDIO_MACHINE_DISCOVERY_RECORD_INVALID")
        result = _present(data, collection_id=collection_id)
    except ValueError as exc:
        if str(exc) == "STUDIO_INBOX_COLLECTION_MISMATCH":
            raise ValueError("STUDIO_MACHINE_DISCOVERY_SCOPE_NOT_FOUND") from None
        raise
    except (TypeError, json.JSONDecodeError):
        raise ValueError("STUDIO_MACHINE_DISCOVERY_RECORD_INVALID") from None
    if result["hit_id"] != hit_id:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_SCOPE_NOT_FOUND")
    return result


def preview_discovery_machine_exception(
    workflow: DiscoveryInboxWorkflow,
    *,
    collection_id: str,
    hit_id: str,
    request_key: str,
    expected_revision: int,
    expected_snapshot_sha256: str,
) -> dict[str, object]:
    """Determine a specific private exception for one *real persisted* Hit.

    The retry re-reads the exact SQL selector. It detects an observed change,
    not a transaction lock; no caller may use this preview to enqueue/publish.
    """
    if not isinstance(workflow, DiscoveryInboxWorkflow):
        raise ValueError("STUDIO_MACHINE_DISCOVERY_WORKFLOW_INVALID")
    collection_id = _validated_ref(collection_id)
    hit_id = _validated_ref(hit_id)
    key = _key(request_key)
    revision = _validated_revision(expected_revision, expected=True)
    expected = _sha(expected_snapshot_sha256, "SNAPSHOT")
    first = _reload_hit(workflow, collection_id=collection_id, hit_id=hit_id)
    if first["annotation_revision"] != revision:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_REVISION_CONFLICT")
    if first["snapshot_sha256"] != expected:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_SNAPSHOT_CHANGED")
    if first["queue"] == "AMBIGUOUS_CONTENT_IDENTITY" or first["content_id"] is None:
        action = "INVESTIGATE_CONTENT_IDENTITY"
    elif first["current"] is not True:
        action = "REFRESH_DISCOVERY_PROVENANCE"
    elif first["latest_annotation"] == "REJECTED":
        action = "HOLD_REJECTED_ANNOTATION"
    elif "DISCOVERY_CONTENT_RIGHTS_UNCLEARED" in first["blockers"]:
        action = "REVALIDATE_SOURCE_RIGHTS"
    else:
        action = "REVALIDATE_RIGHTS_AND_AUTHORITY"
    second = _reload_hit(workflow, collection_id=collection_id, hit_id=hit_id)
    if first != second:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_CHANGED_DURING_PREFLIGHT")
    return _receipt(
        {
            "family": "DISCOVERY_HIT",
            "status": "HELD_EXCEPTION",
            "action": action,
            "collection_id": collection_id,
            "hit_id": hit_id,
            "content_id": first["content_id"],
            "queue": first["queue"],
            "annotation_revision": revision,
            "snapshot_sha256": expected,
            "provenance": first["provenance_path"],
            "blockers": tuple(first["blockers"]),
            "requires_fresh_transactional_cas": True,
            "machine_authority_status": "NOT_CONFIGURED_OR_NOT_ATTESTED",
        },
        request_key=key,
    )


def preview_candidate_machine_handoff(
    match_store: Any,
    promotion_store: Any,
    *,
    run_id: str,
    claim_candidate_id: str,
    result_id: str,
    request_key: str,
    expected_content_id: str,
    expected_capture_sha256: str,
    expected_input_fingerprint: str,
) -> dict[str, object]:
    """Recompute a persisted match and source reference, refusing stale input.

    Legacy reviewer state is deliberately NOT promoted to machine authority.
    A successful source preflight is HELD until an independent B API/signature,
    rights record and fenced downstream execution actually exist.
    """
    run_id, claim_candidate_id = (
        _validated_ref(run_id),
        _validated_ref(claim_candidate_id),
    )
    result_id = _validated_ref(result_id)
    content_id = _validated_ref(expected_content_id)
    key = _key(request_key)
    capture_sha = _sha(expected_capture_sha256, "CAPTURE_SHA256")
    fingerprint = _sha(expected_input_fingerprint, "INPUT_FINGERPRINT")

    def readback() -> tuple[dict[str, object], dict[str, object]]:
        checked = inspect_candidate_review_readiness(
            match_store,
            promotion_store,
            run_id=run_id,
            claim_candidate_id=claim_candidate_id,
        )
        if (
            checked["currentness"] != "CURRENT"
            or checked["input_fingerprint"] != fingerprint
        ):
            raise ValueError("STUDIO_MACHINE_CANDIDATE_STALE_MATCH")
        if not any(result["result_id"] == result_id for result in checked["results"]):
            raise ValueError("STUDIO_MACHINE_CANDIDATE_RESULT_MISSING")
        try:
            context = promotion_store.context(claim_candidate_id)
        except Exception:
            raise RuntimeError("STUDIO_MACHINE_CONTEXT_STORE_UNAVAILABLE") from None
        if (
            not isinstance(context, Mapping)
            or context.get("candidate_id") != claim_candidate_id
            or context.get("content_id") != content_id
        ):
            raise ValueError("STUDIO_MACHINE_CANDIDATE_CONTENT_SCOPE_MISMATCH")
        passages = context.get("passages")
        if not isinstance(passages, list) or len(passages) > 2:
            raise ValueError("STUDIO_MACHINE_CANDIDATE_PASSAGES_INVALID")
        return checked, dict(context)

    checked, context = readback()
    passages = context["passages"]
    refs = checked.get("source_references")
    if not isinstance(refs, list) or len(refs) != len(passages):
        raise ValueError("STUDIO_MACHINE_CANDIDATE_SOURCE_REFS_INVALID")
    if len(passages) == 1 and isinstance(passages[0], Mapping):
        passage = passages[0]
        first_ref = refs[0]
        if (
            not isinstance(first_ref, Mapping)
            or passage.get("capture_sha256") != capture_sha
            or first_ref.get("capture_sha256") != capture_sha
            or first_ref.get("passage_id") != passage.get("passage_id")
            or first_ref.get("capture_id") != passage.get("capture_id")
        ):
            raise ValueError("STUDIO_MACHINE_CANDIDATE_CAPTURE_BINDING_MISMATCH")
        source = {
            "passage_id": first_ref["passage_id"],
            "capture_id": first_ref["capture_id"],
            "capture_sha256": capture_sha,
        }
        provenance_usable = (
            context.get("candidate_status") in {"CANDIDATE", "DUPLICATE"}
            # A source preflight still needs a coherent, single written
            # occurrence bound to an eligible public Person. Neither the
            # legacy review flags nor match confidence grant B authority.
            and isinstance(context.get("statement_candidate_id"), str)
            and bool(context["statement_candidate_id"])
            and type(context.get("passage_count")) is int
            and context["passage_count"] == 1
            and type(context.get("written_count")) is int
            and context["written_count"] == 1
            and type(context.get("media_count")) is int
            and context["media_count"] == 0
            and passage.get("capture_status") == "CAPTURED"
            and passage.get("capture_hold_status") == "NONE"
            and passage.get("canonical_segment_id") is None
            # A written Passage has no media segment (None); an explicit
            # unblocked flag must be the boolean False. Integer/string
            # lookalikes cannot silently clear a publication hold.
            and "segment_publication_blocked" in passage
            and (
                passage.get("segment_publication_blocked") is None
                or passage.get("segment_publication_blocked") is False
            )
            and isinstance(context.get("speaker_person_id"), str)
            and bool(context["speaker_person_id"].strip())
            and context.get("speaker_is_public") is True
            and bool(first_ref.get("passage_id"))
            and bool(first_ref.get("capture_id"))
        )
    else:
        source = {"passage_id": None, "capture_id": None, "capture_sha256": None}
        provenance_usable = False
    checked_again, context_again = readback()
    if checked_again != checked or context_again != context:
        raise ValueError("STUDIO_MACHINE_CANDIDATE_CHANGED_DURING_PREFLIGHT")
    return _receipt(
        {
            "family": "CLAIM_CANDIDATE_MATCH",
            "status": (
                "HELD_MACHINE_AUTHORITY_UNAVAILABLE"
                if provenance_usable
                else "HELD_SOURCE_OR_ATTRIBUTION"
            ),
            "action": (
                "AWAIT_INDEPENDENT_MACHINE_AUTHORITY"
                if provenance_usable
                else "INVESTIGATE_SOURCE_OR_ATTRIBUTION"
            ),
            "candidate_id": claim_candidate_id,
            "run_id": run_id,
            "result_id": result_id,
            "content_id": content_id,
            "input_fingerprint": fingerprint,
            "review_context_sha256": checked["review_context_sha256"],
            "source": source,
            "requires_fresh_transactional_cas": True,
            "machine_authority_status": "NOT_CONFIGURED_OR_NOT_ATTESTED",
        },
        request_key=key,
    )


def _batch_snapshot_valid(snapshot: CurrentBatchStudioItem) -> bool:
    """Currentness metadata is mandatory, even for an operator-only preview."""
    if not isinstance(snapshot, CurrentBatchStudioItem):
        return False
    ids = (
        snapshot.passage_id,
        snapshot.content_id,
        snapshot.capture_id,
        snapshot.selector_fingerprint,
        snapshot.context_version,
    )
    if any(
        not isinstance(value, str) or not value or len(value) > 256 for value in ids
    ):
        return False
    if snapshot.speaker_candidate_id is not None and (
        not isinstance(snapshot.speaker_candidate_id, str)
        or not snapshot.speaker_candidate_id.strip()
        or len(snapshot.speaker_candidate_id) > 256
    ):
        return False
    if snapshot.context_review_id is not None and (
        not isinstance(snapshot.context_review_id, str)
        or not snapshot.context_review_id.strip()
        or len(snapshot.context_review_id) > 256
    ):
        return False
    if any(
        not isinstance(value, str) or not _HASH.fullmatch(value)
        for value in (
            snapshot.source_sha256,
            snapshot.passage_sha256,
        )
    ):
        return False
    if snapshot.rights_evidence_sha256 is not None and (
        not isinstance(snapshot.rights_evidence_sha256, str)
        or not _HASH.fullmatch(snapshot.rights_evidence_sha256)
    ):
        return False
    if any(
        type(value) is not int or value < 0
        for value in (
            snapshot.source_revision,
            snapshot.identity_revision,
            snapshot.rights_revision,
        )
    ):
        return False
    return (
        snapshot.rights_status in {"CLEARED", "UNKNOWN", "EXPIRED", "REVOKED", "DENIED"}
        and snapshot.identity_review_status
        in {"UNRESOLVED", "CANDIDATE_MATCH", "REVIEWED_SAME_PERSON"}
        and snapshot.speech_role
        in {"DIRECT_SPEAKER", "AUTHOR", "REPORTER", "QUOTED_SPEAKER", "UNRESOLVED"}
        and snapshot.speech_act
        in {
            "DIRECT_ASSERTION",
            "OPINION",
            "REPORTED_QUOTE",
            "CRITICISM",
            "IRONY",
            "UNKNOWN",
        }
    )


def _batch_exception_action(reason: str) -> str:
    """Operator actions depend on reviewed source holds, never model scoring."""
    return {
        "MULTIPERSON_QUOTATION_NOT_ENDORSEMENT": "INVESTIGATE_QUOTED_SPEAKER_NOT_ENDORSEMENT",
        "MULTIPERSON_SOURCE_RIGHTS_HELD": "REVALIDATE_SOURCE_RIGHTS",
        "MULTIPERSON_CONTEXT_UNREVIEWED": "REVIEW_SOURCE_CONTEXT_PROVENANCE",
        "MULTIPERSON_SPEAKER_AMBIGUOUS": "INVESTIGATE_SPEAKER_PERSON_IDENTITY",
        "MULTIPERSON_PROVIDER_CAPABILITY_UNAVAILABLE": "CHECK_PRIVATE_PROVIDER_CAPABILITY",
        "MULTIPERSON_BATCH_TOKEN_CAP": "REPLAN_PRIVATE_TOKEN_ALLOCATION",
        "MULTIPERSON_UNATTRIBUTED_CONTEXT": "INVESTIGATE_SOURCE_OR_ATTRIBUTION",
        "MULTIPERSON_OBSERVED_HELD": "INVESTIGATE_HELD_EXTRACTION",
    }.get(reason, "INVESTIGATE_SOURCE_OR_ATTRIBUTION")


def preview_private_batch_machine_handoff(
    plan: IsolatedBatchPlan,
    index: PrivateBatchReceiptIndex,
    *,
    current_items: Mapping[str, CurrentBatchStudioItem],
    expected_receipt_sha256: str | None = None,
    request_key: str,
) -> dict[str, object]:
    """Read-only DP-240 receipts → bounded, actionable private Studio queue.

    Requires a valid exact DP-240 receipt and **independently obtained** current
    Capture/Passage/person-candidate/context/rights snapshots by Passage ID.
    It is not a machine authority adapter, durable job, rights certificate, or
    transactional CAS. Not even a matching current readback enables dispatch.
    A future Studio adapter must re-read under its own authenticated fence.
    """
    key = _key(request_key)
    expected = _sha(expected_receipt_sha256, "BATCH_RECEIPT_SHA256")
    # DP-240 itself validates the original manifest, immutable per-item
    # provenance, digest, observation/status, counts and no-authority flags.
    persisted = export_private_batch_receipt_index(plan, index)
    if expected != persisted["receipt_sha256"]:
        raise ValueError("STUDIO_MACHINE_BATCH_RECEIPT_STALE")
    if not isinstance(current_items, Mapping) or set(current_items) - {
        row.passage_id for row in index.items
    }:
        raise ValueError("STUDIO_MACHINE_BATCH_CURRENT_SCOPE_INVALID")

    # Snapshot each separately retrieved row at the start, then verify none
    # drifted while constructing the preview. This is not a DB transaction.
    current_before = {
        row.passage_id: current_items.get(row.passage_id) for row in index.items
    }
    output: list[dict[str, object]] = []
    for receipt in index.items:
        current = current_before[receipt.passage_id]
        if current is None:
            status, action, reason = (
                "HELD_CURRENT_READBACK_MISSING",
                "RETRIEVE_CURRENT_SOURCE_RIGHTS_IDENTITY",
                "CURRENT_ITEM_READBACK_MISSING",
            )
        elif (
            not _batch_snapshot_valid(current)
            or current.passage_id != receipt.passage_id
        ):
            status, action, reason = (
                "HELD_CURRENT_READBACK_INVALID",
                "RETRIEVE_CURRENT_SOURCE_RIGHTS_IDENTITY",
                "CURRENT_ITEM_READBACK_INVALID",
            )
        elif (current.content_id, current.capture_id) != (
            receipt.content_id,
            receipt.capture_id,
        ):
            status, action, reason = (
                "HELD_SOURCE_SCOPE_MISMATCH",
                "INVESTIGATE_SOURCE_BINDING",
                "CURRENT_CONTENT_CAPTURE_SCOPE_MISMATCH",
            )
        elif (
            current.source_sha256 != receipt.source_sha256
            or current.passage_sha256 != receipt.passage_sha256
            or current.selector_fingerprint != receipt.selector_fingerprint
        ):
            status, action, reason = (
                "HELD_STALE_SOURCE",
                "REFRESH_CAPTURE_PASSAGE_AND_REPLAN",
                "CURRENT_ORIGINAL_VERSION_OR_SELECTOR_CHANGED",
            )
        elif current.rights_status != "CLEARED" or receipt.rights_status != "CLEARED":
            status, action, reason = (
                "HELD_SOURCE_RIGHTS",
                "REVALIDATE_SOURCE_RIGHTS",
                "CURRENT_OR_PLAN_RIGHTS_NOT_CLEARED",
            )
        elif current.rights_evidence_sha256 is None:
            status, action, reason = (
                "HELD_RIGHTS_EVIDENCE_MISSING",
                "RETRIEVE_SOURCE_RIGHTS_EVIDENCE",
                "CURRENT_RIGHTS_EVIDENCE_MISSING",
            )
        elif (
            current.speaker_candidate_id != receipt.speaker_candidate_id
            or current.identity_review_status != receipt.identity_review_status
            or current.speech_role != receipt.speech_role
            or current.speech_act != receipt.speech_act
            or current.context_version != receipt.context_version
            or current.context_review_id != receipt.context_review_id
        ):
            status, action, reason = (
                "HELD_IDENTITY_CHANGED",
                "RECHECK_SPEAKER_PERSON_AND_CONTEXT",
                "CURRENT_IDENTITY_CONTEXT_CHANGED",
            )
        elif receipt.status == "HELD":
            status, action, reason = (
                "HELD_SOURCE_OR_ATTRIBUTION",
                _batch_exception_action(receipt.reason_code),
                receipt.reason_code,
            )
        elif receipt.status == "FAILED":
            status, action, reason = (
                "HELD_EXTRACTION_FAILED",
                "INVESTIGATE_FAILED_EXTRACTION",
                "PRIVATE_EXTRACTION_FAILED",
            )
        elif receipt.status == "UNOBSERVED":
            status, action, reason = (
                "HELD_EXTRACTION_UNOBSERVED",
                "INSPECT_EXTRACTION_ATTEMPT_BEFORE_RETRY",
                "PRIVATE_EXTRACTION_RESULT_MISSING",
            )
        else:
            # PRIVATE_CANDIDATE_UNVERIFIED still does not prove the result
            # text, machine B permission, author Person or any public Finding.
            status, action, reason = (
                "HELD_MACHINE_AUTHORITY_UNAVAILABLE",
                "AWAIT_INDEPENDENT_B_MACHINE_AUTHORITY",
                "B_MACHINE_AUTHORITY_NOT_ATTESTED",
            )
        source = {
            "content_id": receipt.content_id,
            "capture_id": receipt.capture_id,
            "passage_id": receipt.passage_id,
            "source_family": receipt.source_family,
            "source_sha256": receipt.source_sha256,
            "passage_sha256": receipt.passage_sha256,
            "selector_fingerprint": receipt.selector_fingerprint,
            "partition_id": receipt.partition_id,
            "language_tag": receipt.language_tag,
            "speaker_candidate_id": receipt.speaker_candidate_id,
            "identity_review_status": receipt.identity_review_status,
            "speech_role": receipt.speech_role,
            "speech_act": receipt.speech_act,
            "context_version": receipt.context_version,
            "context_review_id": receipt.context_review_id,
            "planned_rights_status": receipt.rights_status,
            "current_rights_status": (
                current.rights_status if _batch_snapshot_valid(current) else None
            ),
            "source_revision": (
                current.source_revision if _batch_snapshot_valid(current) else None
            ),
            "identity_revision": (
                current.identity_revision if _batch_snapshot_valid(current) else None
            ),
            "rights_revision": (
                current.rights_revision if _batch_snapshot_valid(current) else None
            ),
            "rights_evidence_sha256": (
                current.rights_evidence_sha256
                if _batch_snapshot_valid(current)
                else None
            ),
        }
        output.append(
            _receipt(
                {
                    "family": "DP240_BATCH_ITEM",
                    "plan_sha256": plan.plan_sha256,
                    "status": status,
                    "action": action,
                    "reason_code": reason,
                    "source": source,
                    "observed_result": receipt.observation_result,
                    "extraction_version": receipt.extraction_version,
                    # Failure reasons can be arbitrary private provider payloads;
                    # acknowledge their presence, never render their content.
                    "failure_reason_recorded": receipt.failure_reason is not None,
                    "requires_fresh_transactional_cas": True,
                    "machine_authority_status": "NOT_CONFIGURED_OR_NOT_ATTESTED",
                },
                request_key=key,
            )
        )
    if any(
        current_items.get(row.passage_id) != current_before[row.passage_id]
        for row in index.items
    ):
        raise ValueError("STUDIO_MACHINE_BATCH_CHANGED_DURING_PREFLIGHT")
    summary = {
        "item_count": len(output),
        "authority_pending_count": sum(
            row["status"] == "HELD_MACHINE_AUTHORITY_UNAVAILABLE" for row in output
        ),
        "exception_count": sum(
            row["status"] != "HELD_MACHINE_AUTHORITY_UNAVAILABLE" for row in output
        ),
    }
    return _receipt(
        {
            "family": "DP240_PRIVATE_CANDIDATE_BATCH",
            "collection_id": plan.collection_id,
            "manifest_sha256": plan.manifest_sha256,
            "plan_sha256": plan.plan_sha256,
            "batch_receipt_sha256": persisted["receipt_sha256"],
            "status": "HELD_PRIVATE_OPERATOR_PREVIEW",
            "items": tuple(output),
            "summary": summary,
            "requires_fresh_transactional_cas": True,
            "machine_authority_status": "NOT_CONFIGURED_OR_NOT_ATTESTED",
        },
        request_key=key,
    )


class LocalPersistedBatchMachineHandoff:
    """Disposable SQLite DP-242 persistence seam, not the production PG schema.

    The operator seeds *separate persisted* Source/Capture/Passage/rights rows
    obtained from authorized storage. The same SQLite BEGIN IMMEDIATE fence
    protects their readback, a Passage revision CAS and an immutable held
    request receipt. This adapter does not seed evidence, issue authority, call
    B, or create a downstream work item. External PostgreSQL writers are NOT
    serialized by this isolated fixture.
    """

    def __init__(self, connection: sqlite3.Connection):
        if not isinstance(connection, sqlite3.Connection):
            raise ValueError("STUDIO_MACHINE_LOCAL_SQLITE_INVALID")
        self.connection = connection

    def init_isolated_fixture_schema(self) -> None:
        """Create only opt-in disposable tables; never a canonical migration."""
        if self.connection.in_transaction:
            raise ValueError("STUDIO_MACHINE_LOCAL_TRANSACTION_ACTIVE")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS dp242_source (
                id TEXT PRIMARY KEY, collection_id TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK (revision >= 0)
            );
            CREATE TABLE IF NOT EXISTS dp242_capture (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES dp242_source(id),
                content_id TEXT NOT NULL, capture_sha256 TEXT NOT NULL,
                capture_status TEXT NOT NULL, hold_status TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK (revision >= 0)
            );
            CREATE TABLE IF NOT EXISTS dp242_passage (
                id TEXT PRIMARY KEY,
                capture_id TEXT NOT NULL REFERENCES dp242_capture(id),
                content_id TEXT NOT NULL, passage_sha256 TEXT NOT NULL,
                selector_fingerprint TEXT NOT NULL, speaker_candidate_id TEXT,
                identity_review_status TEXT NOT NULL, speech_role TEXT NOT NULL,
                speech_act TEXT NOT NULL, context_version TEXT NOT NULL,
                context_review_id TEXT,
                identity_revision INTEGER NOT NULL CHECK (identity_revision >= 0),
                revision INTEGER NOT NULL CHECK (revision >= 0),
                handoff_revision INTEGER NOT NULL DEFAULT 0
                    CHECK (handoff_revision >= 0)
            );
            CREATE TABLE IF NOT EXISTS dp242_rights (
                capture_id TEXT PRIMARY KEY REFERENCES dp242_capture(id),
                status TEXT NOT NULL, evidence_sha256 TEXT,
                revision INTEGER NOT NULL CHECK (revision >= 0)
            );
            CREATE TABLE IF NOT EXISTS dp242_machine_handoff (
                request_key TEXT PRIMARY KEY,
                passage_id TEXT NOT NULL REFERENCES dp242_passage(id),
                request_fingerprint TEXT NOT NULL,
                source_snapshot_sha256 TEXT NOT NULL,
                receipt_json TEXT NOT NULL, receipt_sha256 TEXT NOT NULL
            );
            """
        )

    def _load_snapshot(
        self, passage_id: str
    ) -> tuple[CurrentBatchStudioItem, dict[str, object]]:
        cursor = self.connection.execute(
            """
            SELECT p.id AS passage_id, p.capture_id, p.content_id, p.passage_sha256,
                p.selector_fingerprint, p.speaker_candidate_id,
                p.identity_review_status, p.speech_role, p.speech_act,
                p.context_version, p.context_review_id, p.identity_revision,
                p.revision AS passage_revision, p.handoff_revision,
                c.content_id AS capture_content_id, c.source_id AS capture_source_id,
                c.capture_sha256,
                c.capture_status, c.hold_status, c.revision AS capture_revision,
                s.id AS source_id, s.collection_id AS source_collection_id,
                s.source_sha256, s.revision AS source_revision,
                r.status AS rights_status, r.evidence_sha256 AS rights_evidence_sha256,
                r.revision AS rights_revision
            FROM dp242_passage p
            JOIN dp242_capture c ON c.id = p.capture_id
            JOIN dp242_source s ON s.id = c.source_id
            JOIN dp242_rights r ON r.capture_id = c.id
            WHERE p.id = ?
            """,
            (passage_id,),
        )
        values = cursor.fetchone()
        if values is None:
            raise ValueError("STUDIO_MACHINE_SOURCE_OR_SNAPSHOT_STALE")
        row = dict(zip((part[0] for part in cursor.description), values))
        snapshot = CurrentBatchStudioItem(
            passage_id=row["passage_id"],
            content_id=row["content_id"],
            capture_id=row["capture_id"],
            source_sha256=row["source_sha256"],
            passage_sha256=row["passage_sha256"],
            selector_fingerprint=row["selector_fingerprint"],
            speaker_candidate_id=row["speaker_candidate_id"],
            identity_review_status=row["identity_review_status"],
            speech_role=row["speech_role"],
            speech_act=row["speech_act"],
            context_version=row["context_version"],
            context_review_id=row["context_review_id"],
            rights_status=row["rights_status"],
            rights_evidence_sha256=row["rights_evidence_sha256"],
            source_revision=row["source_revision"],
            identity_revision=row["identity_revision"],
            rights_revision=row["rights_revision"],
        )
        return snapshot, row

    @staticmethod
    def _snapshot_hash(row: dict[str, object]) -> str:
        # Includes every joined source/Capture/Passage/rights field, not just
        # the lossy public preview. handoff_revision is a separate CAS token.
        material = {
            key: value for key, value in row.items() if key != "handoff_revision"
        }
        return hashlib.sha256(_canonical(material)).hexdigest()

    def read_snapshot_binding_sha256(self, passage_id: str) -> str:
        """Private untrusted pin only; the transactional write rechecks it."""
        if not isinstance(passage_id, str) or not passage_id or len(passage_id) > 256:
            raise ValueError("STUDIO_MACHINE_PASSAGE_ID_INVALID")
        _, row = self._load_snapshot(passage_id)
        return self._snapshot_hash(row)

    def persist_held_batch_handoff(
        self,
        *,
        plan: IsolatedBatchPlan,
        index: PrivateBatchReceiptIndex,
        passage_id: str,
        expected_receipt_sha256: str,
        expected_capture_sha256: str,
        expected_snapshot_sha256: str,
        expected_handoff_revision: int,
        request_key: str,
    ) -> dict[str, object]:
        """CAS a single private HELD receipt, without any downstream dispatch.

        Same-key retries replay the exact committed bytes only if the joined
        persisted snapshot is still current and rights remain CLEARED.
        A rollback/error leaves both Passage revision and receipt unchanged.
        """
        key = _key(request_key)
        receipt_pin = _sha(expected_receipt_sha256, "BATCH_RECEIPT_SHA256")
        capture_pin = _sha(expected_capture_sha256, "CAPTURE_SHA256")
        snapshot_pin = _sha(expected_snapshot_sha256, "SNAPSHOT_SHA256")
        if not isinstance(passage_id, str) or not passage_id or len(passage_id) > 256:
            raise ValueError("STUDIO_MACHINE_PASSAGE_ID_INVALID")
        if type(expected_handoff_revision) is not int or expected_handoff_revision < 0:
            raise ValueError("STUDIO_MACHINE_HANDOFF_REVISION_INVALID")
        if self.connection.in_transaction:
            raise ValueError("STUDIO_MACHINE_LOCAL_TRANSACTION_ACTIVE")
        request_material = {
            "passage_id": passage_id,
            "plan_sha256": plan.plan_sha256,
            "manifest_sha256": plan.manifest_sha256,
            "receipt_pin": receipt_pin,
            "capture_pin": capture_pin,
            "snapshot_pin": snapshot_pin,
            "expected_revision": expected_handoff_revision,
        }
        request_fingerprint = hashlib.sha256(_canonical(request_material)).hexdigest()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            snapshot, row = self._load_snapshot(passage_id)
            # Check revocation before even reading an old replay receipt.
            if row["rights_status"] != "CLEARED" or not _HASH.fullmatch(
                row["rights_evidence_sha256"] or ""
            ):
                raise ValueError("STUDIO_MACHINE_RIGHTS_NOT_CURRENT")
            if (
                row["capture_status"] != "CAPTURED"
                or row["hold_status"] != "NONE"
                or row["source_collection_id"] != plan.collection_id
                or row["capture_source_id"] != row["source_id"]
                or row["capture_content_id"] != row["content_id"]
                or row["capture_sha256"] != capture_pin
                or not _batch_snapshot_valid(snapshot)
                or self._snapshot_hash(row) != snapshot_pin
            ):
                raise ValueError("STUDIO_MACHINE_SOURCE_OR_SNAPSHOT_STALE")
            preview = preview_private_batch_machine_handoff(
                plan,
                index,
                current_items={passage_id: snapshot},
                expected_receipt_sha256=receipt_pin,
                request_key=key,
            )
            selected = tuple(
                item
                for item in preview["items"]
                if item["source"]["passage_id"] == passage_id
            )
            if (
                len(selected) != 1
                or selected[0]["status"] != "HELD_MACHINE_AUTHORITY_UNAVAILABLE"
            ):
                raise ValueError("STUDIO_MACHINE_SOURCE_OR_SNAPSHOT_STALE")

            existing = self.connection.execute(
                "SELECT request_fingerprint, source_snapshot_sha256, receipt_json, "
                "receipt_sha256 FROM dp242_machine_handoff WHERE request_key=?",
                (key,),
            ).fetchone()
            if existing is not None:
                stored_request, stored_snapshot, body, digest = existing
                if stored_request != request_fingerprint:
                    raise ValueError("STUDIO_MACHINE_REQUEST_KEY_CONFLICT")
                if (
                    stored_snapshot != snapshot_pin
                    or hashlib.sha256(body.encode("utf-8")).hexdigest() != digest
                ):
                    raise ValueError("STUDIO_MACHINE_PERSISTED_RECEIPT_CORRUPT")
                result = json.loads(body)
                if any(
                    result.get(flag) is not False
                    for flag in (
                        "enqueued",
                        "dispatch_authorized",
                        "review_authority",
                        "publication_authority",
                        "human_review_approved",
                        "machine_review_approved",
                    )
                ):
                    raise ValueError("STUDIO_MACHINE_PERSISTED_RECEIPT_CORRUPT")
                self.connection.commit()
                return result
            if row["handoff_revision"] != expected_handoff_revision:
                raise ValueError("STUDIO_MACHINE_HANDOFF_REVISION_CONFLICT")
            changed = self.connection.execute(
                "UPDATE dp242_passage SET handoff_revision=handoff_revision+1 "
                "WHERE id=? AND handoff_revision=? AND revision=? AND identity_revision=?",
                (
                    passage_id,
                    expected_handoff_revision,
                    row["passage_revision"],
                    row["identity_revision"],
                ),
            )
            if changed.rowcount != 1:
                raise ValueError("STUDIO_MACHINE_HANDOFF_REVISION_CONFLICT")
            result = _receipt(
                {
                    "family": "DP240_PERSISTED_CANDIDATE_MACHINE_HANDOFF",
                    "status": "HELD_MACHINE_AUTHORITY_UNAVAILABLE",
                    "action": "AWAIT_INDEPENDENT_B_MACHINE_AUTHORITY",
                    "reason_code": "B_MACHINE_AUTHORITY_NOT_ATTESTED",
                    "source": selected[0]["source"]
                    | {
                        "source_id": row["source_id"],
                        "collection_id": row["source_collection_id"],
                        "capture_sha256": capture_pin,
                    },
                    "source_snapshot_sha256": snapshot_pin,
                    "batch_receipt_sha256": receipt_pin,
                    "plan_sha256": plan.plan_sha256,
                    "snapshot_revisions": {
                        "source": row["source_revision"],
                        "capture": row["capture_revision"],
                        "passage": row["passage_revision"],
                        "identity": row["identity_revision"],
                        "rights": row["rights_revision"],
                    },
                    "resulting_handoff_revision": expected_handoff_revision + 1,
                    "requires_fresh_transactional_cas": True,
                    "machine_authority_status": "NOT_CONFIGURED_OR_NOT_ATTESTED",
                },
                request_key=key,
            )
            body = _canonical(result).decode("ascii")
            self.connection.execute(
                "INSERT INTO dp242_machine_handoff "
                "(request_key, passage_id, request_fingerprint, "
                "source_snapshot_sha256, receipt_json, receipt_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    key,
                    passage_id,
                    request_fingerprint,
                    snapshot_pin,
                    body,
                    hashlib.sha256(body.encode("utf-8")).hexdigest(),
                ),
            )
            self.connection.commit()
            return json.loads(body)
        except BaseException:
            self.connection.rollback()
            raise


__all__ = [
    "STUDIO_MACHINE_PREVIEW_VERSION",
    "preview_discovery_machine_exception",
    "preview_candidate_machine_handoff",
    "CurrentBatchStudioItem",
    "preview_private_batch_machine_handoff",
    "LocalPersistedBatchMachineHandoff",
]
