from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping

from dichiarazioni_pubbliche.provenance_quarantine import (
    ActorAuthorization,
    BoundedDependencyGraph,
    DependencyLink,
    HoldEvent,
    HoldEventType,
    HoldReceipt,
    HoldScopeTarget,
    HoldState,
    ImpactReceipt,
    InMemoryProvenanceHoldRegistry,
    PROVENANCE_QUARANTINE_VERSION,
    ProvenanceQuarantineError,
    PublicDependencyRecord,
    ScopeKind,
    verify_hold_event_chain,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


DEPENDENCY_GRAPH_SNAPSHOT_VERSION = "provenance-dependency-graph-v1"


@dataclass(frozen=True)
class DurableDependencyGraphReplay:
    snapshot_id: str | None
    graph: BoundedDependencyGraph | None
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class DurableHoldReplay:
    events: tuple[HoldEvent, ...]
    blockers: tuple[str, ...]


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _required(value: object, code: str, *, maximum: int = 512) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum:
        raise ProvenanceQuarantineError(code)
    return text


def _hex64(value: object, code: str) -> str:
    text = _required(value, code, maximum=64).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ProvenanceQuarantineError(code)
    return text


def _scope_from_json(raw: object) -> HoldScopeTarget:
    if not isinstance(raw, dict):
        raise ProvenanceQuarantineError("HOLD_DURABLE_SCOPE_INVALID")
    allowed = {"kind", "identifier", "version", "provider_id"}
    if set(raw) != allowed:
        raise ProvenanceQuarantineError("HOLD_DURABLE_SCOPE_INVALID")
    try:
        kind = ScopeKind(str(raw.get("kind") or ""))
    except ValueError as exc:
        raise ProvenanceQuarantineError("HOLD_DURABLE_SCOPE_INVALID") from exc
    return HoldScopeTarget(
        kind=kind,
        identifier=str(raw.get("identifier") or ""),
        version=raw.get("version"),
        provider_id=raw.get("provider_id"),
    )


def _graph_payload(graph: BoundedDependencyGraph) -> dict[str, object]:
    return {
        "version": DEPENDENCY_GRAPH_SNAPSHOT_VERSION,
        "records": [
            {
                "public_id": record.public_id,
                "dependencies": [scope.canonical() for scope in record.dependencies],
                "load_bearing_refs": dict(sorted(record.load_bearing_refs.items())),
            }
            for record in graph.records
        ],
        "links": [
            {
                "upstream": link.upstream.canonical(),
                "downstream": link.downstream.canonical(),
            }
            for link in graph.links
        ],
    }


def _graph_from_json(raw: object) -> BoundedDependencyGraph:
    if not isinstance(raw, dict) or set(raw) != {"version", "records", "links"}:
        raise ProvenanceQuarantineError("HOLD_DEPENDENCY_GRAPH_ROW_INVALID")
    if raw.get("version") != DEPENDENCY_GRAPH_SNAPSHOT_VERSION:
        raise ProvenanceQuarantineError("HOLD_DEPENDENCY_GRAPH_VERSION_INVALID")
    record_rows = raw.get("records")
    link_rows = raw.get("links")
    if not isinstance(record_rows, list) or not isinstance(link_rows, list):
        raise ProvenanceQuarantineError("HOLD_DEPENDENCY_GRAPH_ROW_INVALID")
    records: list[PublicDependencyRecord] = []
    for row in record_rows:
        if not isinstance(row, dict) or set(row) != {
            "public_id",
            "dependencies",
            "load_bearing_refs",
        }:
            raise ProvenanceQuarantineError("HOLD_DEPENDENCY_GRAPH_ROW_INVALID")
        dependencies = row.get("dependencies")
        refs = row.get("load_bearing_refs")
        if not isinstance(dependencies, list) or not isinstance(refs, dict):
            raise ProvenanceQuarantineError("HOLD_DEPENDENCY_GRAPH_ROW_INVALID")
        records.append(
            PublicDependencyRecord(
                public_id=str(row.get("public_id") or ""),
                dependencies=tuple(_scope_from_json(value) for value in dependencies),
                load_bearing_refs={str(key): str(value) for key, value in refs.items()},
            )
        )
    links: list[DependencyLink] = []
    for row in link_rows:
        if not isinstance(row, dict) or set(row) != {"upstream", "downstream"}:
            raise ProvenanceQuarantineError("HOLD_DEPENDENCY_GRAPH_ROW_INVALID")
        links.append(
            DependencyLink(
                upstream=_scope_from_json(row.get("upstream")),
                downstream=_scope_from_json(row.get("downstream")),
            )
        )
    return BoundedDependencyGraph(records=tuple(records), links=tuple(links))


def _snapshot_integrity_material(
    *,
    snapshot_id: str,
    sequence: int,
    previous_snapshot_id: str | None,
    previous_integrity_sha256: str | None,
    graph_sha256: str,
) -> dict[str, object]:
    return {
        "snapshot_id": snapshot_id,
        "snapshot_version": DEPENDENCY_GRAPH_SNAPSHOT_VERSION,
        "snapshot_sequence": sequence,
        "previous_snapshot_id": previous_snapshot_id,
        "previous_integrity_sha256": previous_integrity_sha256,
        "graph_sha256": graph_sha256,
    }


def _hold_event_from_row(row: Mapping[str, object]) -> HoldEvent:
    try:
        event_type = HoldEventType(str(row.get("event_type") or ""))
    except ValueError as exc:
        raise ProvenanceQuarantineError("HOLD_DURABLE_EVENT_TYPE_INVALID") from exc
    return HoldEvent(
        sequence=int(row.get("event_sequence") or 0),
        event_id=_required(row.get("event_id"), "HOLD_DURABLE_EVENT_ID_INVALID"),
        request_id=_required(row.get("request_id"), "HOLD_DURABLE_REQUEST_ID_INVALID"),
        hold_id=_required(row.get("hold_id"), "HOLD_DURABLE_ID_INVALID"),
        event_type=event_type,
        actor_id=_required(row.get("actor_id"), "HOLD_DURABLE_ACTOR_INVALID"),
        reason_code=_required(row.get("reason_code"), "HOLD_DURABLE_REASON_INVALID"),
        incident_id=(
            str(row.get("incident_id")).strip() if row.get("incident_id") is not None else None
        ),
        scope=_scope_from_json(row.get("scope_json")),
        impact_binding_sha256=_hex64(
            row.get("impact_binding_sha256"), "HOLD_DURABLE_IMPACT_BINDING_INVALID"
        ),
        revalidation_binding_sha256=(
            _hex64(
                row.get("revalidation_binding_sha256"),
                "HOLD_DURABLE_REVALIDATION_BINDING_INVALID",
            )
            if row.get("revalidation_binding_sha256") is not None
            else None
        ),
        private_note_sha256=(
            _hex64(row.get("private_note_sha256"), "HOLD_DURABLE_PRIVATE_NOTE_INVALID")
            if row.get("private_note_sha256") is not None
            else None
        ),
        previous_event_hash=_hex64(
            row.get("previous_event_hash"), "HOLD_DURABLE_PREVIOUS_HASH_INVALID"
        ),
        event_hash=_hex64(row.get("event_hash"), "HOLD_DURABLE_EVENT_HASH_INVALID"),
        event_version=_required(row.get("event_version"), "HOLD_DURABLE_VERSION_INVALID"),
    )


def _request_fingerprint(event: HoldEvent) -> str:
    if event.event_type is HoldEventType.ACTIVATE:
        payload = {
            "event_type": event.event_type.value,
            "hold_id": event.hold_id,
            "actor_id": event.actor_id,
            "reason_code": event.reason_code,
            "incident_id": event.incident_id,
            "scope": event.scope.canonical(),
            "private_note_sha256": event.private_note_sha256,
        }
    elif event.event_type is HoldEventType.REVIEWED_UNHOLD:
        payload = {
            "event_type": event.event_type.value,
            "hold_id": event.hold_id,
            "actor_id": event.actor_id,
            "review_code": event.reason_code,
            "scope": event.scope.canonical(),
            "private_note_sha256": event.private_note_sha256,
        }
    else:
        payload = {
            "event_type": event.event_type.value,
            "hold_id": event.hold_id,
            "actor_id": event.actor_id,
            "revalidation_code": event.reason_code,
            "scope": event.scope.canonical(),
            "revalidation_binding_sha256": event.revalidation_binding_sha256,
            "private_note_sha256": event.private_note_sha256,
        }
    return _sha(payload)


def _state_for_event(event: HoldEvent) -> HoldState:
    if event.event_type is HoldEventType.ACTIVATE:
        return HoldState.ACTIVE
    if event.event_type is HoldEventType.REVIEWED_UNHOLD:
        return HoldState.PENDING_REVALIDATION
    return HoldState.RELEASED


class ProvenanceHoldPersistenceStore(PsqlRuntime):
    """Private append-only DP-510 dependency/hold ledger used by public projection."""

    def _graph_rows(self) -> list[dict[str, object]]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'snapshot_id', snapshot_id,
                'snapshot_version', snapshot_version,
                'snapshot_sequence', snapshot_sequence,
                'previous_snapshot_id', previous_snapshot_id,
                'previous_integrity_sha256', previous_integrity_sha256,
                'graph_json', graph_json,
                'graph_sha256', graph_sha256,
                'integrity_sha256', integrity_sha256
            ) ORDER BY snapshot_sequence)::text, '[]')
            FROM provenance_dependency_graph_snapshot;
            """
        )
        rows = json.loads(raw or "[]")
        if not isinstance(rows, list):
            raise ProvenanceQuarantineError("HOLD_DEPENDENCY_GRAPH_ROWS_INVALID")
        return rows

    def _replay_graph_chain(
        self,
    ) -> tuple[list[tuple[dict[str, object], BoundedDependencyGraph]], tuple[str, ...]]:
        try:
            rows = self._graph_rows()
        except (RuntimeError, TypeError, ValueError, json.JSONDecodeError, ProvenanceQuarantineError):
            return [], ("HOLD_DEPENDENCY_GRAPH_READ_FAILED",)
        parsed: list[tuple[dict[str, object], BoundedDependencyGraph]] = []
        blockers: list[str] = []
        previous_id: str | None = None
        previous_integrity: str | None = None
        for expected_sequence, row in enumerate(rows, start=1):
            try:
                sequence = int(row.get("snapshot_sequence") or 0)
                snapshot_id = _required(
                    row.get("snapshot_id"), "HOLD_DEPENDENCY_SNAPSHOT_ID_INVALID"
                )
                graph = _graph_from_json(row.get("graph_json"))
                graph_sha = _hex64(
                    row.get("graph_sha256"), "HOLD_DEPENDENCY_GRAPH_HASH_INVALID"
                )
                integrity = _hex64(
                    row.get("integrity_sha256"), "HOLD_DEPENDENCY_INTEGRITY_INVALID"
                )
                row_previous_id = row.get("previous_snapshot_id")
                row_previous_integrity = row.get("previous_integrity_sha256")
                if sequence != expected_sequence:
                    raise ProvenanceQuarantineError("HOLD_DEPENDENCY_SEQUENCE_INVALID")
                if row.get("snapshot_version") != DEPENDENCY_GRAPH_SNAPSHOT_VERSION:
                    raise ProvenanceQuarantineError("HOLD_DEPENDENCY_GRAPH_VERSION_INVALID")
                if row_previous_id != previous_id or row_previous_integrity != previous_integrity:
                    raise ProvenanceQuarantineError("HOLD_DEPENDENCY_CHAIN_INVALID")
                if _sha(_graph_payload(graph)) != graph_sha:
                    raise ProvenanceQuarantineError("HOLD_DEPENDENCY_GRAPH_TAMPERED")
                material = _snapshot_integrity_material(
                    snapshot_id=snapshot_id,
                    sequence=sequence,
                    previous_snapshot_id=previous_id,
                    previous_integrity_sha256=previous_integrity,
                    graph_sha256=graph_sha,
                )
                if _sha(material) != integrity:
                    raise ProvenanceQuarantineError("HOLD_DEPENDENCY_INTEGRITY_MISMATCH")
            except (TypeError, ValueError, ProvenanceQuarantineError):
                blockers.append("HOLD_DEPENDENCY_GRAPH_TAMPERED")
                continue
            parsed.append((row, graph))
            previous_id = snapshot_id
            previous_integrity = integrity
        if blockers:
            return [], tuple(dict.fromkeys(blockers))
        return parsed, ()

    def current_dependency_graph(self) -> DurableDependencyGraphReplay:
        parsed, blockers = self._replay_graph_chain()
        if blockers:
            return DurableDependencyGraphReplay(None, None, blockers)
        if not parsed:
            return DurableDependencyGraphReplay(
                None, None, ("HOLD_DEPENDENCY_GRAPH_MISSING",)
            )
        row, graph = parsed[-1]
        return DurableDependencyGraphReplay(str(row["snapshot_id"]), graph, ())

    def append_dependency_graph(self, graph: BoundedDependencyGraph) -> str:
        if not isinstance(graph, BoundedDependencyGraph):
            raise ProvenanceQuarantineError("HOLD_DEPENDENCY_GRAPH_INVALID")
        parsed, blockers = self._replay_graph_chain()
        if blockers:
            raise ProvenanceQuarantineError(blockers[0])
        payload = _graph_payload(graph)
        graph_sha = _sha(payload)
        if parsed:
            latest_row, latest_graph = parsed[-1]
            if _sha(_graph_payload(latest_graph)) == graph_sha:
                return str(latest_row["snapshot_id"])
            sequence = int(latest_row["snapshot_sequence"]) + 1
            previous_id = str(latest_row["snapshot_id"])
            previous_integrity = str(latest_row["integrity_sha256"])
        else:
            sequence = 1
            previous_id = None
            previous_integrity = None
        snapshot_id = "dependency-graph:" + _sha(
            {
                "sequence": sequence,
                "previous_snapshot_id": previous_id,
                "graph_sha256": graph_sha,
            }
        )
        material = _snapshot_integrity_material(
            snapshot_id=snapshot_id,
            sequence=sequence,
            previous_snapshot_id=previous_id,
            previous_integrity_sha256=previous_integrity,
            graph_sha256=graph_sha,
        )
        integrity = _sha(material)
        self.run(
            """
            INSERT INTO provenance_dependency_graph_snapshot (
                snapshot_id, snapshot_version, snapshot_sequence,
                previous_snapshot_id, previous_integrity_sha256,
                graph_json, graph_sha256, integrity_sha256
            ) VALUES (
                :'snapshot_id', :'snapshot_version', :'snapshot_sequence'::bigint,
                NULLIF(:'previous_snapshot_id',''), NULLIF(:'previous_integrity_sha256',''),
                :'graph_json'::jsonb, :'graph_sha256', :'integrity_sha256'
            );
            """,
            snapshot_id=snapshot_id,
            snapshot_version=DEPENDENCY_GRAPH_SNAPSHOT_VERSION,
            snapshot_sequence=sequence,
            previous_snapshot_id=previous_id or "",
            previous_integrity_sha256=previous_integrity or "",
            graph_json=_canonical_json(payload),
            graph_sha256=graph_sha,
            integrity_sha256=integrity,
        )
        return snapshot_id

    def _hold_rows(self) -> list[dict[str, object]]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'event_id', event_id,
                'event_sequence', event_sequence,
                'request_id', request_id,
                'hold_id', hold_id,
                'event_type', event_type,
                'actor_id', actor_id,
                'reason_code', reason_code,
                'incident_id', incident_id,
                'scope_json', scope_json,
                'impact_binding_sha256', impact_binding_sha256,
                'revalidation_binding_sha256', revalidation_binding_sha256,
                'private_note_sha256', private_note_sha256,
                'previous_event_hash', previous_event_hash,
                'event_hash', event_hash,
                'event_version', event_version,
                'dependency_snapshot_id', dependency_snapshot_id
            ) ORDER BY event_sequence)::text, '[]')
            FROM provenance_hold_event_durable;
            """
        )
        rows = json.loads(raw or "[]")
        if not isinstance(rows, list):
            raise ProvenanceQuarantineError("HOLD_DURABLE_ROWS_INVALID")
        return rows

    def _replay_hold_rows(
        self,
    ) -> tuple[list[tuple[dict[str, object], HoldEvent, BoundedDependencyGraph]], tuple[str, ...]]:
        graph_rows, graph_blockers = self._replay_graph_chain()
        if graph_blockers:
            return [], graph_blockers
        graph_by_id = {str(row["snapshot_id"]): graph for row, graph in graph_rows}
        try:
            rows = self._hold_rows()
        except (RuntimeError, TypeError, ValueError, json.JSONDecodeError, ProvenanceQuarantineError):
            return [], ("HOLD_DURABLE_READ_FAILED",)
        parsed: list[tuple[dict[str, object], HoldEvent, BoundedDependencyGraph]] = []
        events: list[HoldEvent] = []
        blockers: list[str] = []
        for row in rows:
            try:
                event = _hold_event_from_row(row)
                snapshot_id = _required(
                    row.get("dependency_snapshot_id"),
                    "HOLD_DURABLE_DEPENDENCY_SNAPSHOT_INVALID",
                )
                graph = graph_by_id.get(snapshot_id)
                if graph is None:
                    raise ProvenanceQuarantineError(
                        "HOLD_DURABLE_DEPENDENCY_SNAPSHOT_INVALID"
                    )
                impact = graph.dry_run(event.scope)
                if impact.impact_binding_sha256 != event.impact_binding_sha256:
                    raise ProvenanceQuarantineError("HOLD_DURABLE_IMPACT_TAMPERED")
            except (TypeError, ValueError, ProvenanceQuarantineError):
                blockers.append("HOLD_DURABLE_EVENT_TAMPERED")
                continue
            events.append(event)
            parsed.append((row, event, graph))
        if blockers or not verify_hold_event_chain(events):
            return [], ("HOLD_DURABLE_EVENT_TAMPERED",)
        by_hold: dict[str, list[HoldEventType]] = {}
        for event in events:
            by_hold.setdefault(event.hold_id, []).append(event.event_type)
        valid_sequences = {
            (HoldEventType.ACTIVATE,),
            (HoldEventType.ACTIVATE, HoldEventType.REVIEWED_UNHOLD),
            (
                HoldEventType.ACTIVATE,
                HoldEventType.REVIEWED_UNHOLD,
                HoldEventType.REVALIDATED,
            ),
        }
        if any(tuple(sequence) not in valid_sequences for sequence in by_hold.values()):
            return [], ("HOLD_DURABLE_STATE_SEQUENCE_INVALID",)
        return parsed, ()

    def replay_hold_events(self) -> DurableHoldReplay:
        parsed, blockers = self._replay_hold_rows()
        if blockers:
            return DurableHoldReplay((), blockers)
        return DurableHoldReplay(tuple(event for _, event, _ in parsed), ())

    def persist_registry(
        self,
        *,
        registry: InMemoryProvenanceHoldRegistry,
        graph: BoundedDependencyGraph,
    ) -> int:
        if not verify_hold_event_chain(registry.events):
            raise ProvenanceQuarantineError("HOLD_EVENT_CHAIN_TAMPERED")
        snapshot_id = self.append_dependency_graph(graph)
        durable_rows, blockers = self._replay_hold_rows()
        if blockers:
            raise ProvenanceQuarantineError(blockers[0])
        durable_events = tuple(event for _, event, _ in durable_rows)
        candidate_events = registry.events
        if len(candidate_events) < len(durable_events):
            raise ProvenanceQuarantineError("HOLD_DURABLE_HISTORY_TRUNCATION_REFUSED")
        if candidate_events[: len(durable_events)] != durable_events:
            raise ProvenanceQuarantineError("HOLD_DURABLE_HISTORY_FORK_REFUSED")
        inserted = 0
        for event in candidate_events[len(durable_events) :]:
            impact = graph.dry_run(event.scope)
            if impact.impact_binding_sha256 != event.impact_binding_sha256:
                raise ProvenanceQuarantineError("HOLD_DURABLE_IMPACT_MISMATCH")
            self.run(
                """
                INSERT INTO provenance_hold_event_durable (
                    event_id, event_sequence, request_id, hold_id, event_type,
                    actor_id, reason_code, incident_id, scope_json,
                    impact_binding_sha256, revalidation_binding_sha256,
                    private_note_sha256, previous_event_hash, event_hash,
                    event_version, dependency_snapshot_id
                ) VALUES (
                    :'event_id', :'event_sequence'::integer, :'request_id', :'hold_id', :'event_type',
                    :'actor_id', :'reason_code', NULLIF(:'incident_id',''), :'scope_json'::jsonb,
                    :'impact_binding_sha256', NULLIF(:'revalidation_binding_sha256',''),
                    NULLIF(:'private_note_sha256',''), :'previous_event_hash', :'event_hash',
                    :'event_version', :'dependency_snapshot_id'
                );
                """,
                event_id=event.event_id,
                event_sequence=event.sequence,
                request_id=event.request_id,
                hold_id=event.hold_id,
                event_type=event.event_type.value,
                actor_id=event.actor_id,
                reason_code=event.reason_code,
                incident_id=event.incident_id or "",
                scope_json=_canonical_json(event.scope.canonical()),
                impact_binding_sha256=event.impact_binding_sha256,
                revalidation_binding_sha256=event.revalidation_binding_sha256 or "",
                private_note_sha256=event.private_note_sha256 or "",
                previous_event_hash=event.previous_event_hash,
                event_hash=event.event_hash,
                event_version=event.event_version,
                dependency_snapshot_id=snapshot_id,
            )
            inserted += 1
        return inserted

    def restore_registry(
        self,
        *,
        actors: Iterable[ActorAuthorization],
    ) -> InMemoryProvenanceHoldRegistry:
        parsed, blockers = self._replay_hold_rows()
        if blockers:
            raise ProvenanceQuarantineError(blockers[0])
        registry = InMemoryProvenanceHoldRegistry(actors=actors)
        registry._events.extend(event for _, event, _ in parsed)
        for _, event, graph in parsed:
            impact: ImpactReceipt = graph.dry_run(event.scope)
            receipt = HoldReceipt(
                hold_id=event.hold_id,
                event_id=event.event_id,
                event_type=event.event_type,
                state=_state_for_event(event),
                scope=event.scope,
                actor_ref=(
                    "actor:"
                    + hashlib.sha256(event.actor_id.encode("utf-8")).hexdigest()[:16]
                ),
                reason_code=event.reason_code,
                incident_id=event.incident_id,
                impact=impact,
                event_hash=event.event_hash,
                revalidation_binding_sha256=event.revalidation_binding_sha256,
            )
            registry._requests[event.request_id] = (_request_fingerprint(event), receipt)
        return registry

    def allows_publication(
        self,
        *,
        public_id: str,
        current_publication_binding_sha256: str,
    ) -> bool:
        finding = str(public_id or "").strip()
        try:
            binding = _hex64(
                current_publication_binding_sha256,
                "HOLD_CURRENT_PUBLICATION_BINDING_INVALID",
            )
        except ProvenanceQuarantineError:
            return False
        if not finding:
            return False
        graph_replay = self.current_dependency_graph()
        if graph_replay.blockers or graph_replay.graph is None:
            return False
        graph = graph_replay.graph
        records = tuple(record for record in graph.records if record.public_id == finding)
        if len(records) != 1 or records[0].binding_sha256 != binding:
            return False
        parsed, blockers = self._replay_hold_rows()
        if blockers:
            return False
        by_hold: dict[str, list[HoldEvent]] = {}
        for _, event, _ in parsed:
            by_hold.setdefault(event.hold_id, []).append(event)
        try:
            for events in by_hold.values():
                activation = events[0]
                if finding not in graph.affected_public_ids(activation.scope):
                    continue
                latest = events[-1]
                if latest.event_type is not HoldEventType.REVALIDATED:
                    return False
                if latest.revalidation_binding_sha256 != binding:
                    return False
        except (TypeError, ValueError, ProvenanceQuarantineError):
            return False
        return True


__all__ = [
    "DEPENDENCY_GRAPH_SNAPSHOT_VERSION",
    "DurableDependencyGraphReplay",
    "DurableHoldReplay",
    "ProvenanceHoldPersistenceStore",
]
