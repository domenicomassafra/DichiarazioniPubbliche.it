"""DP-232 bounded runtime bridge over DP-228 -> DP-209 -> mirror persistence.

This module deliberately has no network client.  A caller supplies an already-configured
lookup callable; the bridge gives it only the persisted DP-209 query text/result limit and
remaining cost state, then lets the canonical DP-209 runner persist the manifest, attempt,
hit and provider receipt before any normalized mirror is appended.

The bridge grants no rights, evidence approval, verification or publication authority.
Every persisted mirror created here starts with ``rights_status=UNKNOWN``; later public
excerpt eligibility remains owned by DP-305.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Mapping

from dichiarazioni_pubbliche.existing_factcheck import ExistingFactCheckRecord
from dichiarazioni_pubbliche.existing_factcheck_persistence import (
    ExistingFactCheckMirrorStore,
    PersistedFactCheckMirror,
)
from dichiarazioni_pubbliche.policy.excerpt_policy import RightsStatus
from dichiarazioni_pubbliche.research_discovery import (
    DiscoveryAdapterError,
    DiscoveryAdapterRequest,
    DiscoveryAdapterResult,
    DiscoveryHitCandidate,
    DiscoveryRunReceipt,
    ResearchDiscoveryStore,
    run_discovery_manifest,
)
from dichiarazioni_pubbliche.research_plan import (
    ResearchAssignment,
    discovery_manifest_from_assignments,
)


EXISTING_FACTCHECK_RUNTIME_VERSION = "existing-factcheck-runtime-v1"


class ExistingFactCheckRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class ExistingFactCheckMirrorCandidate:
    record: ExistingFactCheckRecord
    upstream_record_id: str
    source_external_id: str
    source_version: str
    source_content_sha256: str
    supersedes_source_version: str | None = None


@dataclass(frozen=True)
class ExistingFactCheckLookupRequest:
    query_text: str
    page_size: int
    date_from: str | None
    date_to: str | None
    remaining_cost_usd: Decimal
    research_assignment_id: str


@dataclass(frozen=True)
class ExistingFactCheckLookupResult:
    candidates: tuple[ExistingFactCheckMirrorCandidate, ...]
    provider_receipt: Mapping[str, object]
    cost_usd: Decimal = Decimal("0")
    omitted_results: int = 0


@dataclass(frozen=True)
class ExistingFactCheckRuntimeReceipt:
    run: DiscoveryRunReceipt
    mirrors: tuple[PersistedFactCheckMirror, ...]
    manifest_id: str
    assignment_id: str
    publication_authority: bool = False
    runtime_version: str = EXISTING_FACTCHECK_RUNTIME_VERSION


def _required(value: object, code: str, *, limit: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or "\x00" in text:
        raise ExistingFactCheckRuntimeError(code)
    return text


class ExistingFactCheckDiscoveryAdapter:
    """DP-209 adapter facade around an injected existing-fact-check lookup.

    The lookup receives the exact saved query and query result cap.  Returned normalized
    records are represented to DP-209 only by URL/external-ID and bounded metadata; claim
    text/rating/body stay out of discovery metadata and are appended to the private mirror
    ledger only after DP-209 has accepted the corresponding hit.
    """

    def __init__(
        self,
        *,
        provider_id: str,
        adapter_version: str,
        source_family: str,
        cost_upper_bound_usd: Decimal | str | float,
        lookup: Callable[[ExistingFactCheckLookupRequest], ExistingFactCheckLookupResult],
    ) -> None:
        self.adapter_id = _required(provider_id, "FACTCHECK_RUNTIME_PROVIDER_ID_REQUIRED", limit=256)
        self.adapter_version = _required(
            adapter_version, "FACTCHECK_RUNTIME_ADAPTER_VERSION_REQUIRED", limit=256
        )
        self.source_family = _required(
            source_family, "FACTCHECK_RUNTIME_SOURCE_FAMILY_REQUIRED", limit=128
        )
        self.supported_families = frozenset({self.source_family})
        self._upper = Decimal(str(cost_upper_bound_usd))
        if not self._upper.is_finite() or self._upper < 0:
            raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_COST_BOUND_INVALID")
        self._lookup = lookup
        self._candidates: dict[str, ExistingFactCheckMirrorCandidate] = {}

    @property
    def candidates(self) -> Mapping[str, ExistingFactCheckMirrorCandidate]:
        return dict(self._candidates)

    def cost_upper_bound_usd(self, request: DiscoveryAdapterRequest) -> Decimal:
        return self._upper

    def discover(self, request: DiscoveryAdapterRequest) -> DiscoveryAdapterResult:
        assignment_id = _required(
            request.query.metadata.get("research_assignment_id"),
            "FACTCHECK_RUNTIME_ASSIGNMENT_BINDING_REQUIRED",
        )
        if request.query.id != assignment_id:
            raise DiscoveryAdapterError("FACTCHECK_ASSIGNMENT_QUERY_ID_MISMATCH")
        if request.query.metadata.get("lane") != "EXISTING_FACT_CHECK":
            raise DiscoveryAdapterError("FACTCHECK_RESEARCH_LANE_MISMATCH")
        if request.query.max_results < 1:
            raise DiscoveryAdapterError("FACTCHECK_RESULT_LIMIT_INVALID")
        result = self._lookup(
            ExistingFactCheckLookupRequest(
                query_text=request.query.query_text,
                page_size=request.query.max_results,
                date_from=request.date_from,
                date_to=request.date_to,
                remaining_cost_usd=request.remaining_cost_usd,
                research_assignment_id=assignment_id,
            )
        )
        if not isinstance(result, ExistingFactCheckLookupResult):
            raise DiscoveryAdapterError("FACTCHECK_LOOKUP_RESULT_INVALID")
        if len(result.candidates) > request.query.max_results:
            raise DiscoveryAdapterError("FACTCHECK_RESULT_BOUND_EXCEEDED")
        cost = Decimal(str(result.cost_usd))
        if not cost.is_finite() or cost < 0:
            raise DiscoveryAdapterError("FACTCHECK_COST_INVALID")

        hits: list[DiscoveryHitCandidate] = []
        seen_external: set[str] = set()
        self._candidates = {}
        for candidate in result.candidates:
            if not isinstance(candidate, ExistingFactCheckMirrorCandidate):
                raise DiscoveryAdapterError("FACTCHECK_MIRROR_CANDIDATE_INVALID")
            if candidate.record.provider_id != self.adapter_id:
                raise DiscoveryAdapterError("FACTCHECK_PROVIDER_ID_MISMATCH")
            external_id = _required(
                candidate.source_external_id,
                "FACTCHECK_RUNTIME_SOURCE_EXTERNAL_ID_REQUIRED",
                limit=512,
            )
            if external_id in seen_external:
                raise DiscoveryAdapterError("FACTCHECK_DUPLICATE_EXTERNAL_ID")
            seen_external.add(external_id)
            _required(candidate.upstream_record_id, "FACTCHECK_RUNTIME_UPSTREAM_ID_REQUIRED")
            _required(candidate.source_version, "FACTCHECK_RUNTIME_SOURCE_VERSION_REQUIRED")
            source_sha = str(candidate.source_content_sha256 or "").strip().lower()
            if len(source_sha) != 64 or any(ch not in "0123456789abcdef" for ch in source_sha):
                raise DiscoveryAdapterError("FACTCHECK_SOURCE_HASH_INVALID")
            self._candidates[external_id] = candidate
            hits.append(
                DiscoveryHitCandidate(
                    canonical_url=candidate.record.review_url,
                    title=candidate.record.review_title or candidate.record.review_publisher_name or "",
                    published_at=candidate.record.review_date,
                    source_family=self.source_family,
                    external_id=external_id,
                    metadata={
                        "existing_factcheck_record_id": candidate.record.record_id,
                        "source_version": candidate.source_version,
                        "source_content_sha256": source_sha,
                        "upstream_record_id_sha256": hashlib.sha256(
                            candidate.upstream_record_id.encode("utf-8")
                        ).hexdigest(),
                    },
                )
            )
        return DiscoveryAdapterResult(
            hits=tuple(hits),
            status="OK",
            cost_usd=cost,
            provider_receipt=dict(result.provider_receipt),
            omitted_hits=max(int(result.omitted_results), 0),
        )


def run_existing_factcheck_assignment(
    assignment: ResearchAssignment,
    *,
    collection_id: str,
    database_url: str,
    adapters: Mapping[str, ExistingFactCheckDiscoveryAdapter],
    source_family: str = "existing_factcheck",
    run_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> ExistingFactCheckRuntimeReceipt:
    """Execute exactly one saved DP-228 EXISTING_FACT_CHECK assignment via DP-209.

    No provider is selected or widened here.  The assignment's query/result/cost bounds
    become the DP-209 manifest unchanged; adapter calls outside the permitted adapter IDs
    are impossible because only those IDs are passed to the canonical runner.
    """

    if assignment.lane != "EXISTING_FACT_CHECK":
        raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_LANE_REQUIRED")
    if assignment.status != "READY" or not assignment.adapter_ids:
        raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_READY_ASSIGNMENT_REQUIRED")
    if assignment.max_queries < 1:
        raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_QUERY_LIMIT_EXHAUSTED")

    supplied = set(adapters)
    permitted = set(assignment.adapter_ids)
    if supplied - permitted:
        raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_ADAPTER_PERMISSION_EXPANSION")
    missing = permitted - supplied
    if missing:
        raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_ADAPTER_MISSING")
    for adapter_id in assignment.adapter_ids:
        adapter = adapters[adapter_id]
        if adapter.adapter_id != adapter_id:
            raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_ADAPTER_ID_MISMATCH")
        if adapter.source_family != source_family:
            raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_SOURCE_FAMILY_MISMATCH")

    manifest = discovery_manifest_from_assignments(
        (assignment,),
        collection_id=collection_id,
        lane_source_families={"EXISTING_FACT_CHECK": (source_family,)},
        date_from=date_from,
        date_to=date_to,
    )
    query = manifest.queries[0]
    if query.id != assignment.assignment_id or query.query_text != assignment.question:
        raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_QUERY_BINDING_MISMATCH")
    if query.max_results != assignment.max_results:
        raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_RESULT_LIMIT_MISMATCH")
    if manifest.cost_cap_usd != assignment.cost_cap_usd:
        raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_COST_LIMIT_MISMATCH")
    if query.metadata.get("remaining_attempts") != assignment.max_queries:
        raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_QUERY_LIMIT_MISMATCH")

    discovery_store = ResearchDiscoveryStore(database_url)
    receipt = run_discovery_manifest(
        manifest,
        discovery_store,
        adapters,
        run_id=run_id,
    )
    mirror_store = ExistingFactCheckMirrorStore(database_url)
    persisted: list[PersistedFactCheckMirror] = []
    for adapter_id in assignment.adapter_ids:
        adapter = adapters[adapter_id]
        rows = mirror_store.accepted_discovery_hits(
            run_id=receipt.run_id,
            query_id=query.id,
            adapter_id=adapter_id,
        )
        candidates = adapter.candidates
        for row in rows:
            external_id = str(row["external_id"])
            candidate = candidates.get(external_id)
            if candidate is None:
                existing = mirror_store.mirror_for_discovery_hit(str(row["hit_id"]))
                if existing is not None:
                    persisted.append(existing)
                    continue
                raise ExistingFactCheckRuntimeError("FACTCHECK_RUNTIME_ACCEPTED_HIT_UNBOUND")
            persisted.append(
                mirror_store.persist_mirror(
                    candidate.record,
                    upstream_record_id=candidate.upstream_record_id,
                    source_external_id=candidate.source_external_id,
                    source_version=candidate.source_version,
                    source_content_sha256=candidate.source_content_sha256,
                    research_assignment_id=assignment.assignment_id,
                    discovery_attempt_id=str(row["attempt_id"]),
                    discovery_hit_id=str(row["hit_id"]),
                    rights_status=RightsStatus.UNKNOWN,
                    supersedes_source_version=candidate.supersedes_source_version,
                )
            )
    return ExistingFactCheckRuntimeReceipt(
        run=receipt,
        mirrors=tuple(persisted),
        manifest_id=manifest.id,
        assignment_id=assignment.assignment_id,
    )


__all__ = [
    "EXISTING_FACTCHECK_RUNTIME_VERSION",
    "ExistingFactCheckDiscoveryAdapter",
    "ExistingFactCheckLookupRequest",
    "ExistingFactCheckLookupResult",
    "ExistingFactCheckMirrorCandidate",
    "ExistingFactCheckRuntimeError",
    "ExistingFactCheckRuntimeReceipt",
    "run_existing_factcheck_assignment",
]
