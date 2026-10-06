from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Iterable, Mapping

from dichiarazioni_pubbliche.publication_safety import PUBLICATION_SAFETY_VERSION


PROVENANCE_QUARANTINE_VERSION = "provenance-quarantine-v1"
MAX_GRAPH_NODES = 10_000
MAX_GRAPH_EDGES = 20_000
MAX_PUBLIC_RECORDS = 5_000
MAX_TRAVERSAL_DEPTH = 16
MAX_RECEIPT_PUBLIC_IDS = 50
MAX_LOAD_BEARING_REFS = 64


class ProvenanceQuarantineError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "PROVENANCE_QUARANTINE_ERROR").strip().upper()[:240]
        super().__init__(self.code)


class ScopeKind(StrEnum):
    SOURCE_PROVIDER_VERSION = "SOURCE_PROVIDER_VERSION"
    CAPTURE = "CAPTURE"
    TRANSCRIPT = "TRANSCRIPT"
    SPEAKER_METHOD_VERSION = "SPEAKER_METHOD_VERSION"
    PERSON_MAPPING = "PERSON_MAPPING"
    EVIDENCE_REQUIREMENT_PROFILE = "EVIDENCE_REQUIREMENT_PROFILE"
    POLICY_VERSION = "POLICY_VERSION"
    FINDING = "FINDING"


class HoldEventType(StrEnum):
    ACTIVATE = "ACTIVATE"
    REVIEWED_UNHOLD = "REVIEWED_UNHOLD"
    REVALIDATED = "REVALIDATED"


class HoldState(StrEnum):
    ACTIVE = "ACTIVE"
    PENDING_REVALIDATION = "PENDING_REVALIDATION"
    RELEASED = "RELEASED"


class HoldPermission(StrEnum):
    ACTIVATE = "ACTIVATE"
    REVIEW_UNHOLD = "REVIEW_UNHOLD"
    REVALIDATE = "REVALIDATE"


_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,119}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _text(value: object, name: str, *, maximum: int = 256) -> str:
    if isinstance(value, bool):
        raise ProvenanceQuarantineError(f"HOLD_{name}_INVALID")
    text = str(value or "").strip()
    if not text:
        raise ProvenanceQuarantineError(f"HOLD_{name}_REQUIRED")
    if len(text) > maximum:
        raise ProvenanceQuarantineError(f"HOLD_{name}_TOO_LONG")
    return text


def _optional_text(value: object, name: str, *, maximum: int = 256) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > maximum:
        raise ProvenanceQuarantineError(f"HOLD_{name}_TOO_LONG")
    return text


def _code(value: object, name: str) -> str:
    text = _text(value, name, maximum=120).upper()
    if not _CODE.fullmatch(text):
        raise ProvenanceQuarantineError(f"HOLD_{name}_INVALID")
    return text


def _sha(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _private_note_sha256(private_note: str | None) -> str | None:
    if private_note is None:
        return None
    note = _text(private_note, "PRIVATE_NOTE", maximum=2_000)
    return hashlib.sha256(note.encode("utf-8")).hexdigest()


@dataclass(frozen=True, order=True)
class HoldScopeTarget:
    kind: ScopeKind
    identifier: str
    version: str | None = None
    provider_id: str | None = None

    def __post_init__(self) -> None:
        try:
            normalized_kind = (
                self.kind
                if isinstance(self.kind, ScopeKind)
                else ScopeKind(str(self.kind))
            )
        except ValueError as exc:
            raise ProvenanceQuarantineError("HOLD_SCOPE_KIND_INVALID") from exc
        object.__setattr__(self, "kind", normalized_kind)
        object.__setattr__(self, "identifier", _text(self.identifier, "SCOPE_IDENTIFIER"))
        object.__setattr__(
            self,
            "version",
            _optional_text(self.version, "SCOPE_VERSION"),
        )
        object.__setattr__(
            self,
            "provider_id",
            _optional_text(self.provider_id, "SCOPE_PROVIDER_ID"),
        )
        if self.kind is ScopeKind.SOURCE_PROVIDER_VERSION:
            if self.provider_id is None or self.version is None:
                raise ProvenanceQuarantineError("HOLD_SOURCE_SCOPE_PROVIDER_VERSION_REQUIRED")
        elif self.kind in {
            ScopeKind.TRANSCRIPT,
            ScopeKind.SPEAKER_METHOD_VERSION,
            ScopeKind.PERSON_MAPPING,
            ScopeKind.POLICY_VERSION,
            ScopeKind.EVIDENCE_REQUIREMENT_PROFILE,
            ScopeKind.CAPTURE,
        }:
            if self.version is None:
                raise ProvenanceQuarantineError("HOLD_SCOPE_VERSION_REQUIRED")
            if self.provider_id is not None:
                raise ProvenanceQuarantineError("HOLD_SCOPE_PROVIDER_FORBIDDEN")
        elif self.provider_id is not None or self.version is not None:
            raise ProvenanceQuarantineError("HOLD_SCOPE_EXTRA_QUALIFIER")

    @classmethod
    def source(
        cls,
        *,
        provider_id: str,
        source_id: str,
        source_version: str,
    ) -> "HoldScopeTarget":
        return cls(
            ScopeKind.SOURCE_PROVIDER_VERSION,
            source_id,
            version=source_version,
            provider_id=provider_id,
        )

    @classmethod
    def transcript(cls, transcript_id: str, version: str) -> "HoldScopeTarget":
        return cls(ScopeKind.TRANSCRIPT, transcript_id, version=version)

    @classmethod
    def speaker_method(cls, method: str, version: str) -> "HoldScopeTarget":
        return cls(ScopeKind.SPEAKER_METHOD_VERSION, method, version=version)

    @classmethod
    def person_mapping(cls, mapping_id: str, version: str) -> "HoldScopeTarget":
        return cls(ScopeKind.PERSON_MAPPING, mapping_id, version=version)

    @classmethod
    def finding(cls, finding_id: str) -> "HoldScopeTarget":
        return cls(ScopeKind.FINDING, finding_id)

    def canonical(self) -> dict[str, str | None]:
        return {
            "kind": self.kind.value,
            "identifier": self.identifier,
            "version": self.version,
            "provider_id": self.provider_id,
        }


@dataclass(frozen=True)
class DependencyLink:
    upstream: HoldScopeTarget
    downstream: HoldScopeTarget

    def __post_init__(self) -> None:
        if self.upstream == self.downstream:
            raise ProvenanceQuarantineError("HOLD_DEPENDENCY_SELF_LINK")


def _clean_load_bearing_refs(refs: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(refs, Mapping) or not refs:
        raise ProvenanceQuarantineError("HOLD_LOAD_BEARING_REFS_REQUIRED")
    if len(refs) > MAX_LOAD_BEARING_REFS:
        raise ProvenanceQuarantineError("HOLD_LOAD_BEARING_REFS_TOO_MANY")
    cleaned: dict[str, str] = {}
    for raw_name, raw_value in refs.items():
        name = _text(raw_name, "LOAD_BEARING_REF_NAME", maximum=120)
        value = _text(raw_value, "LOAD_BEARING_REF_VALUE", maximum=256)
        if name in cleaned:
            raise ProvenanceQuarantineError("HOLD_LOAD_BEARING_REF_DUPLICATE")
        cleaned[name] = value
    return cleaned


def publication_binding_sha256(refs: Mapping[str, str]) -> str:
    """Use the same binding shape as DP-308 publication-safety-v1."""

    cleaned = _clean_load_bearing_refs(refs)
    return _sha(
        {
            "profile_version": PUBLICATION_SAFETY_VERSION,
            "refs": cleaned,
        }
    )


@dataclass(frozen=True)
class PublicDependencyRecord:
    public_id: str
    dependencies: tuple[HoldScopeTarget, ...]
    load_bearing_refs: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "public_id",
            _text(self.public_id, "PUBLIC_ID"),
        )
        dependencies = tuple(sorted(set(self.dependencies)))
        if not dependencies:
            raise ProvenanceQuarantineError("HOLD_PUBLIC_DEPENDENCIES_REQUIRED")
        if len(dependencies) > 64:
            raise ProvenanceQuarantineError("HOLD_PUBLIC_DEPENDENCIES_TOO_MANY")
        object.__setattr__(self, "dependencies", dependencies)
        object.__setattr__(
            self,
            "load_bearing_refs",
            MappingProxyType(_clean_load_bearing_refs(self.load_bearing_refs)),
        )

    @property
    def binding_sha256(self) -> str:
        return publication_binding_sha256(self.load_bearing_refs)


@dataclass(frozen=True)
class ImpactReceipt:
    scope: HoldScopeTarget
    affected_count: int
    affected_public_ids: tuple[str, ...]
    ids_truncated: bool
    dependency_nodes_visited: int
    max_depth_seen: int
    impact_binding_sha256: str
    receipt_version: str = PROVENANCE_QUARANTINE_VERSION


class BoundedDependencyGraph:
    def __init__(
        self,
        *,
        records: Iterable[PublicDependencyRecord],
        links: Iterable[DependencyLink] = (),
    ) -> None:
        record_rows = tuple(records)
        link_rows = tuple(links)
        if len(record_rows) > MAX_PUBLIC_RECORDS:
            raise ProvenanceQuarantineError("HOLD_GRAPH_PUBLIC_RECORD_LIMIT")
        if len(link_rows) > MAX_GRAPH_EDGES:
            raise ProvenanceQuarantineError("HOLD_GRAPH_EDGE_LIMIT")
        by_public_id: dict[str, PublicDependencyRecord] = {}
        nodes: set[HoldScopeTarget] = set()
        for record in record_rows:
            if record.public_id in by_public_id:
                raise ProvenanceQuarantineError("HOLD_GRAPH_PUBLIC_ID_DUPLICATE")
            by_public_id[record.public_id] = record
            nodes.update(record.dependencies)
        adjacency: dict[HoldScopeTarget, set[HoldScopeTarget]] = {}
        for link in link_rows:
            adjacency.setdefault(link.upstream, set()).add(link.downstream)
            nodes.add(link.upstream)
            nodes.add(link.downstream)
        if len(nodes) > MAX_GRAPH_NODES:
            raise ProvenanceQuarantineError("HOLD_GRAPH_NODE_LIMIT")
        self._records = tuple(sorted(record_rows, key=lambda row: row.public_id))
        self._links = tuple(
            sorted(
                link_rows,
                key=lambda link: (
                    json.dumps(link.upstream.canonical(), sort_keys=True),
                    json.dumps(link.downstream.canonical(), sort_keys=True),
                ),
            )
        )
        self._adjacency = {
            key: tuple(sorted(values)) for key, values in adjacency.items()
        }

    @property
    def records(self) -> tuple[PublicDependencyRecord, ...]:
        return self._records

    @property
    def links(self) -> tuple[DependencyLink, ...]:
        return self._links

    def _reachable(
        self,
        scope: HoldScopeTarget,
        *,
        max_depth: int,
    ) -> tuple[set[HoldScopeTarget], int]:
        reachable: set[HoldScopeTarget] = {scope}
        frontier = deque([(scope, 0)])
        max_depth_seen = 0
        while frontier:
            node, depth = frontier.popleft()
            max_depth_seen = max(max_depth_seen, depth)
            children = self._adjacency.get(node, ())
            if children and depth >= int(max_depth):
                raise ProvenanceQuarantineError("HOLD_GRAPH_TRAVERSAL_BOUND_EXCEEDED")
            for child in children:
                if child in reachable:
                    continue
                reachable.add(child)
                if len(reachable) > MAX_GRAPH_NODES:
                    raise ProvenanceQuarantineError("HOLD_GRAPH_NODE_LIMIT")
                frontier.append((child, depth + 1))
        return reachable, max_depth_seen

    def affected_public_ids(
        self,
        scope: HoldScopeTarget,
        *,
        max_depth: int = MAX_TRAVERSAL_DEPTH,
    ) -> tuple[str, ...]:
        if not 0 <= int(max_depth) <= MAX_TRAVERSAL_DEPTH:
            raise ProvenanceQuarantineError("HOLD_GRAPH_DEPTH_INVALID")
        reachable, _ = self._reachable(scope, max_depth=int(max_depth))
        return tuple(
            record.public_id
            for record in self._records
            if any(dependency in reachable for dependency in record.dependencies)
        )

    def dry_run(
        self,
        scope: HoldScopeTarget,
        *,
        max_depth: int = MAX_TRAVERSAL_DEPTH,
        receipt_id_limit: int = MAX_RECEIPT_PUBLIC_IDS,
    ) -> ImpactReceipt:
        if not 0 <= int(max_depth) <= MAX_TRAVERSAL_DEPTH:
            raise ProvenanceQuarantineError("HOLD_GRAPH_DEPTH_INVALID")
        if not 1 <= int(receipt_id_limit) <= MAX_RECEIPT_PUBLIC_IDS:
            raise ProvenanceQuarantineError("HOLD_RECEIPT_ID_LIMIT_INVALID")

        reachable, max_depth_seen = self._reachable(scope, max_depth=int(max_depth))

        affected = tuple(
            record
            for record in self._records
            if any(dependency in reachable for dependency in record.dependencies)
        )
        affected_ids = tuple(record.public_id for record in affected)
        receipt_ids = affected_ids[: int(receipt_id_limit)]
        binding = _sha(
            {
                "scope": scope.canonical(),
                "affected": [
                    {
                        "public_id": record.public_id,
                        "publication_binding_sha256": record.binding_sha256,
                    }
                    for record in affected
                ],
                "version": PROVENANCE_QUARANTINE_VERSION,
            }
        )
        return ImpactReceipt(
            scope=scope,
            affected_count=len(affected_ids),
            affected_public_ids=receipt_ids,
            ids_truncated=len(receipt_ids) != len(affected_ids),
            dependency_nodes_visited=len(reachable),
            max_depth_seen=max_depth_seen,
            impact_binding_sha256=binding,
        )


@dataclass(frozen=True)
class ActorAuthorization:
    actor_id: str
    permissions: frozenset[HoldPermission]

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor_id", _text(self.actor_id, "ACTOR_ID"))
        normalized: set[HoldPermission] = set()
        for value in self.permissions:
            try:
                normalized.add(
                    value if isinstance(value, HoldPermission) else HoldPermission(str(value))
                )
            except ValueError as exc:
                raise ProvenanceQuarantineError("HOLD_PERMISSION_INVALID") from exc
        if not normalized:
            raise ProvenanceQuarantineError("HOLD_PERMISSIONS_REQUIRED")
        object.__setattr__(self, "permissions", frozenset(normalized))


@dataclass(frozen=True)
class RevalidationProof:
    load_bearing_refs: Mapping[str, str]
    binding_sha256: str = ""
    profile_version: str = PUBLICATION_SAFETY_VERSION

    def __post_init__(self) -> None:
        if self.profile_version != PUBLICATION_SAFETY_VERSION:
            raise ProvenanceQuarantineError("HOLD_REVALIDATION_PROFILE_VERSION_INVALID")
        refs = _clean_load_bearing_refs(self.load_bearing_refs)
        required = {
            "source_version",
            "provenance_version",
            "policy_version",
            "review_version",
        }
        if not required.issubset(refs):
            raise ProvenanceQuarantineError("HOLD_REVALIDATION_REQUIRED_REFS_MISSING")
        computed = publication_binding_sha256(refs)
        supplied = str(self.binding_sha256 or "").strip().lower()
        if supplied and (not _HEX64.fullmatch(supplied) or supplied != computed):
            raise ProvenanceQuarantineError("HOLD_REVALIDATION_BINDING_MISMATCH")
        object.__setattr__(self, "load_bearing_refs", MappingProxyType(refs))
        object.__setattr__(self, "binding_sha256", computed)


@dataclass(frozen=True)
class HoldEvent:
    sequence: int
    event_id: str
    request_id: str
    hold_id: str
    event_type: HoldEventType
    actor_id: str
    reason_code: str
    incident_id: str | None
    scope: HoldScopeTarget
    impact_binding_sha256: str
    revalidation_binding_sha256: str | None
    private_note_sha256: str | None
    previous_event_hash: str
    event_hash: str
    event_version: str = PROVENANCE_QUARANTINE_VERSION


@dataclass(frozen=True)
class HoldReceipt:
    hold_id: str
    event_id: str
    event_type: HoldEventType
    state: HoldState
    scope: HoldScopeTarget
    actor_ref: str
    reason_code: str
    incident_id: str | None
    impact: ImpactReceipt
    event_hash: str
    revalidation_binding_sha256: str | None
    private_note_redacted: bool = True
    receipt_version: str = PROVENANCE_QUARANTINE_VERSION


def _event_payload(event: HoldEvent) -> dict[str, object]:
    return {
        "sequence": event.sequence,
        "event_id": event.event_id,
        "request_id": event.request_id,
        "hold_id": event.hold_id,
        "event_type": event.event_type.value,
        "actor_id": event.actor_id,
        "reason_code": event.reason_code,
        "incident_id": event.incident_id,
        "scope": event.scope.canonical(),
        "impact_binding_sha256": event.impact_binding_sha256,
        "revalidation_binding_sha256": event.revalidation_binding_sha256,
        "private_note_sha256": event.private_note_sha256,
        "previous_event_hash": event.previous_event_hash,
        "event_version": event.event_version,
    }


def verify_hold_event_chain(events: Iterable[HoldEvent]) -> bool:
    previous = "0" * 64
    for expected_sequence, event in enumerate(events, start=1):
        if event.sequence != expected_sequence:
            return False
        if event.previous_event_hash != previous:
            return False
        if event.event_version != PROVENANCE_QUARANTINE_VERSION:
            return False
        if _sha(_event_payload(event)) != event.event_hash:
            return False
        previous = event.event_hash
    return True


class InMemoryProvenanceHoldRegistry:
    __slots__ = ("_actors", "_events", "_requests")

    def __init__(self, *, actors: Iterable[ActorAuthorization]) -> None:
        authorizations = tuple(actors)
        self._actors: dict[str, frozenset[HoldPermission]] = {}
        for actor in authorizations:
            if actor.actor_id in self._actors:
                raise ProvenanceQuarantineError("HOLD_ACTOR_DUPLICATE")
            self._actors[actor.actor_id] = actor.permissions
        self._events: list[HoldEvent] = []
        self._requests: dict[str, tuple[str, HoldReceipt]] = {}

    @property
    def events(self) -> tuple[HoldEvent, ...]:
        return tuple(self._events)

    def _authorize(self, actor_id: str, permission: HoldPermission) -> str:
        actor = _text(actor_id, "ACTOR_ID")
        if permission not in self._actors.get(actor, frozenset()):
            raise ProvenanceQuarantineError("HOLD_ACTOR_UNAUTHORIZED")
        return actor

    def _assert_chain(self) -> None:
        if not verify_hold_event_chain(self._events):
            raise ProvenanceQuarantineError("HOLD_EVENT_CHAIN_TAMPERED")

    def _events_for_hold(self, hold_id: str) -> tuple[HoldEvent, ...]:
        return tuple(event for event in self._events if event.hold_id == hold_id)

    def state(self, hold_id: str) -> HoldState:
        self._assert_chain()
        hold = _text(hold_id, "ID")
        events = self._events_for_hold(hold)
        if not events:
            raise ProvenanceQuarantineError("HOLD_NOT_FOUND")
        event_type = events[-1].event_type
        if event_type is HoldEventType.ACTIVATE:
            return HoldState.ACTIVE
        if event_type is HoldEventType.REVIEWED_UNHOLD:
            return HoldState.PENDING_REVALIDATION
        return HoldState.RELEASED

    def active_hold_ids(self) -> tuple[str, ...]:
        hold_ids = sorted({event.hold_id for event in self._events})
        return tuple(
            hold_id
            for hold_id in hold_ids
            if self.state(hold_id) is not HoldState.RELEASED
        )

    def held_public_ids(self, graph: BoundedDependencyGraph) -> tuple[str, ...]:
        affected: set[str] = set()
        for hold_id in self.active_hold_ids():
            activation = self._events_for_hold(hold_id)[0]
            affected.update(graph.affected_public_ids(activation.scope))
        return tuple(sorted(affected))

    def _replay_or_conflict(
        self,
        *,
        request_id: str,
        fingerprint: str,
    ) -> HoldReceipt | None:
        prior = self._requests.get(request_id)
        if prior is None:
            return None
        prior_fingerprint, receipt = prior
        if prior_fingerprint != fingerprint:
            raise ProvenanceQuarantineError("HOLD_REPLAY_CONFLICT")
        return receipt

    def _append(
        self,
        *,
        request_id: str,
        request_fingerprint: str,
        hold_id: str,
        event_type: HoldEventType,
        actor_id: str,
        reason_code: str,
        incident_id: str | None,
        scope: HoldScopeTarget,
        impact: ImpactReceipt,
        private_note: str | None,
        revalidation_binding_sha256: str | None,
        resulting_state: HoldState,
    ) -> HoldReceipt:
        private_note_sha256 = _private_note_sha256(private_note)
        sequence = len(self._events) + 1
        previous_event_hash = self._events[-1].event_hash if self._events else "0" * 64
        event_id = "hold-event:" + _sha(
            {
                "request_id": request_id,
                "request_fingerprint": request_fingerprint,
                "sequence": sequence,
            }
        )
        draft = HoldEvent(
            sequence=sequence,
            event_id=event_id,
            request_id=request_id,
            hold_id=hold_id,
            event_type=event_type,
            actor_id=actor_id,
            reason_code=reason_code,
            incident_id=incident_id,
            scope=scope,
            impact_binding_sha256=impact.impact_binding_sha256,
            revalidation_binding_sha256=revalidation_binding_sha256,
            private_note_sha256=private_note_sha256,
            previous_event_hash=previous_event_hash,
            event_hash="",
        )
        event_hash = _sha(_event_payload(draft))
        event = HoldEvent(**{**draft.__dict__, "event_hash": event_hash})
        self._events.append(event)
        receipt = HoldReceipt(
            hold_id=hold_id,
            event_id=event_id,
            event_type=event_type,
            state=resulting_state,
            scope=scope,
            actor_ref=(
                "actor:"
                + hashlib.sha256(actor_id.encode("utf-8")).hexdigest()[:16]
            ),
            reason_code=reason_code,
            incident_id=incident_id,
            impact=impact,
            event_hash=event_hash,
            revalidation_binding_sha256=revalidation_binding_sha256,
        )
        self._requests[request_id] = (request_fingerprint, receipt)
        return receipt

    def activate(
        self,
        *,
        request_id: str,
        hold_id: str,
        actor_id: str,
        reason_code: str,
        scope: HoldScopeTarget,
        graph: BoundedDependencyGraph,
        incident_id: str | None = None,
        private_note: str | None = None,
    ) -> HoldReceipt:
        self._assert_chain()
        request = _text(request_id, "REQUEST_ID")
        hold = _text(hold_id, "ID")
        actor = self._authorize(actor_id, HoldPermission.ACTIVATE)
        reason = _code(reason_code, "REASON_CODE")
        incident = _optional_text(incident_id, "INCIDENT_ID")
        note_sha256 = _private_note_sha256(private_note)
        fingerprint = _sha(
            {
                "event_type": HoldEventType.ACTIVATE.value,
                "hold_id": hold,
                "actor_id": actor,
                "reason_code": reason,
                "incident_id": incident,
                "scope": scope.canonical(),
                "private_note_sha256": note_sha256,
            }
        )
        replay = self._replay_or_conflict(request_id=request, fingerprint=fingerprint)
        if replay is not None:
            return replay
        if self._events_for_hold(hold):
            raise ProvenanceQuarantineError("HOLD_ID_ALREADY_EXISTS")
        impact = graph.dry_run(scope)
        return self._append(
            request_id=request,
            request_fingerprint=fingerprint,
            hold_id=hold,
            event_type=HoldEventType.ACTIVATE,
            actor_id=actor,
            reason_code=reason,
            incident_id=incident,
            scope=scope,
            impact=impact,
            private_note=private_note,
            revalidation_binding_sha256=None,
            resulting_state=HoldState.ACTIVE,
        )

    def reviewed_unhold(
        self,
        *,
        request_id: str,
        hold_id: str,
        actor_id: str,
        review_code: str,
        graph: BoundedDependencyGraph,
        private_note: str | None = None,
    ) -> HoldReceipt:
        self._assert_chain()
        request = _text(request_id, "REQUEST_ID")
        hold = _text(hold_id, "ID")
        actor = self._authorize(actor_id, HoldPermission.REVIEW_UNHOLD)
        reason = _code(review_code, "REVIEW_CODE")
        events = self._events_for_hold(hold)
        if not events:
            raise ProvenanceQuarantineError("HOLD_NOT_FOUND")
        scope = events[0].scope
        note_sha256 = _private_note_sha256(private_note)
        fingerprint = _sha(
            {
                "event_type": HoldEventType.REVIEWED_UNHOLD.value,
                "hold_id": hold,
                "actor_id": actor,
                "review_code": reason,
                "scope": scope.canonical(),
                "private_note_sha256": note_sha256,
            }
        )
        replay = self._replay_or_conflict(request_id=request, fingerprint=fingerprint)
        if replay is not None:
            return replay
        if self.state(hold) is not HoldState.ACTIVE:
            raise ProvenanceQuarantineError("HOLD_REVIEWED_UNHOLD_SEQUENCE_INVALID")
        impact = graph.dry_run(scope)
        return self._append(
            request_id=request,
            request_fingerprint=fingerprint,
            hold_id=hold,
            event_type=HoldEventType.REVIEWED_UNHOLD,
            actor_id=actor,
            reason_code=reason,
            incident_id=events[0].incident_id,
            scope=scope,
            impact=impact,
            private_note=private_note,
            revalidation_binding_sha256=None,
            resulting_state=HoldState.PENDING_REVALIDATION,
        )

    def revalidate(
        self,
        *,
        request_id: str,
        hold_id: str,
        actor_id: str,
        proof: RevalidationProof,
        graph: BoundedDependencyGraph,
        revalidation_code: str = "REVALIDATED_CURRENT_BINDINGS",
        private_note: str | None = None,
    ) -> HoldReceipt:
        self._assert_chain()
        request = _text(request_id, "REQUEST_ID")
        hold = _text(hold_id, "ID")
        actor = self._authorize(actor_id, HoldPermission.REVALIDATE)
        reason = _code(revalidation_code, "REVALIDATION_CODE")
        events = self._events_for_hold(hold)
        if not events:
            raise ProvenanceQuarantineError("HOLD_NOT_FOUND")
        scope = events[0].scope
        note_sha256 = _private_note_sha256(private_note)
        fingerprint = _sha(
            {
                "event_type": HoldEventType.REVALIDATED.value,
                "hold_id": hold,
                "actor_id": actor,
                "revalidation_code": reason,
                "scope": scope.canonical(),
                "revalidation_binding_sha256": proof.binding_sha256,
                "private_note_sha256": note_sha256,
            }
        )
        replay = self._replay_or_conflict(request_id=request, fingerprint=fingerprint)
        if replay is not None:
            return replay
        if self.state(hold) is not HoldState.PENDING_REVALIDATION:
            raise ProvenanceQuarantineError("HOLD_REVALIDATION_SEQUENCE_INVALID")
        impact = graph.dry_run(scope)
        return self._append(
            request_id=request,
            request_fingerprint=fingerprint,
            hold_id=hold,
            event_type=HoldEventType.REVALIDATED,
            actor_id=actor,
            reason_code=reason,
            incident_id=events[0].incident_id,
            scope=scope,
            impact=impact,
            private_note=private_note,
            revalidation_binding_sha256=proof.binding_sha256,
            resulting_state=HoldState.RELEASED,
        )


__all__ = [
    "ActorAuthorization",
    "BoundedDependencyGraph",
    "DependencyLink",
    "HoldEvent",
    "HoldEventType",
    "HoldPermission",
    "HoldReceipt",
    "HoldScopeTarget",
    "HoldState",
    "ImpactReceipt",
    "InMemoryProvenanceHoldRegistry",
    "MAX_RECEIPT_PUBLIC_IDS",
    "PROVENANCE_QUARANTINE_VERSION",
    "ProvenanceQuarantineError",
    "PublicDependencyRecord",
    "RevalidationProof",
    "ScopeKind",
    "publication_binding_sha256",
    "verify_hold_event_chain",
]
