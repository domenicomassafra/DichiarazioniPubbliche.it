from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping


class HandlerFamily(str, Enum):
    TRANSCRIPT_ASR = "TRANSCRIPT_ASR"
    CLAIM_EVIDENCE = "CLAIM_EVIDENCE"
    VERIFICATION_RELATION_REANALYSIS = "VERIFICATION_RELATION_REANALYSIS"


class HandlerCapability(str, Enum):
    PLATFORM_TRANSCRIPT = "PLATFORM_TRANSCRIPT"
    LOCAL_TRANSCRIPT = "LOCAL_TRANSCRIPT"
    REMOTE_ASR = "REMOTE_ASR"
    CLAIM_EXTRACTION = "CLAIM_EXTRACTION"
    EVIDENCE_RETRIEVAL = "EVIDENCE_RETRIEVAL"
    EVIDENCE_OBSERVATION = "EVIDENCE_OBSERVATION"
    DETERMINISTIC_VERIFICATION = "DETERMINISTIC_VERIFICATION"
    RELATION_CLASSIFICATION = "RELATION_CLASSIFICATION"
    REANALYSIS = "REANALYSIS"


class UnregisteredWorkerJobType(RuntimeError):
    pass


WorkerHandler = Callable[[Any, Any, Any], None]


@dataclass(frozen=True)
class HandlerSpec:
    job_type: str
    family: HandlerFamily
    capability: HandlerCapability
    handler: WorkerHandler


_HANDLER_METADATA = (
    (
        "TRANSCRIPT_RESOLVE_PLATFORM",
        HandlerFamily.TRANSCRIPT_ASR,
        HandlerCapability.PLATFORM_TRANSCRIPT,
        "resolve_platform",
    ),
    (
        "TRANSCRIPT_ACQUIRE_CAPTION",
        HandlerFamily.TRANSCRIPT_ASR,
        HandlerCapability.PLATFORM_TRANSCRIPT,
        "acquire_caption",
    ),
    (
        "TRANSCRIPT_CANONICALIZE",
        HandlerFamily.TRANSCRIPT_ASR,
        HandlerCapability.LOCAL_TRANSCRIPT,
        "canonicalize",
    ),
    (
        "TRANSCRIPT_ACQUIRE_ASR",
        HandlerFamily.TRANSCRIPT_ASR,
        HandlerCapability.REMOTE_ASR,
        "acquire_asr",
    ),
    (
        "CLAIM_PREPARE",
        HandlerFamily.CLAIM_EVIDENCE,
        HandlerCapability.CLAIM_EXTRACTION,
        "prepare_claim_windows",
    ),
    (
        "CLAIM_EXTRACT",
        HandlerFamily.CLAIM_EVIDENCE,
        HandlerCapability.CLAIM_EXTRACTION,
        "prepare_claim_windows",
    ),
    (
        "CLAIM_EXTRACT_WINDOW",
        HandlerFamily.CLAIM_EVIDENCE,
        HandlerCapability.CLAIM_EXTRACTION,
        "extract_claim_window",
    ),
    (
        "EVIDENCE_FETCH_URL",
        HandlerFamily.CLAIM_EVIDENCE,
        HandlerCapability.EVIDENCE_RETRIEVAL,
        "fetch_evidence_url",
    ),
    (
        "EVIDENCE_QUERY_OFFICIAL",
        HandlerFamily.CLAIM_EVIDENCE,
        HandlerCapability.EVIDENCE_RETRIEVAL,
        "query_official_evidence",
    ),
    (
        "EVIDENCE_OBSERVE",
        HandlerFamily.CLAIM_EVIDENCE,
        HandlerCapability.EVIDENCE_OBSERVATION,
        "persist_evidence_observation",
    ),
    (
        "VERIFY_CLAIM",
        HandlerFamily.VERIFICATION_RELATION_REANALYSIS,
        HandlerCapability.DETERMINISTIC_VERIFICATION,
        "verify_claim",
    ),
    (
        "CLASSIFY_CLAIM_RELATION",
        HandlerFamily.VERIFICATION_RELATION_REANALYSIS,
        HandlerCapability.RELATION_CLASSIFICATION,
        "classify_claim_relation_job",
    ),
    (
        "REGISTER_REANALYSIS",
        HandlerFamily.VERIFICATION_RELATION_REANALYSIS,
        HandlerCapability.REANALYSIS,
        "register_reanalysis",
    ),
    (
        "REANALYZE_CLAIM",
        HandlerFamily.VERIFICATION_RELATION_REANALYSIS,
        HandlerCapability.REANALYSIS,
        "reanalyze_claim",
    ),
)


def processing_worker_handler_catalog() -> Mapping[str, HandlerSpec]:
    # Lazy import keeps this boundary usable as the future target of worker_daemon's
    # dispatch without creating an import cycle during the preparatory DP-108 tranche.
    from dichiarazioni_pubbliche.worker_daemon import ProcessingWorker

    catalog: dict[str, HandlerSpec] = {}
    for job_type, family, capability, handler_name in _HANDLER_METADATA:
        handler = getattr(ProcessingWorker, handler_name)
        catalog[job_type] = HandlerSpec(
            job_type=job_type,
            family=family,
            capability=capability,
            handler=handler,
        )
    return MappingProxyType(catalog)


def resolve_processing_worker_handler(job_type: str) -> HandlerSpec:
    normalized = str(job_type or "").strip()
    spec = processing_worker_handler_catalog().get(normalized)
    if spec is None:
        raise UnregisteredWorkerJobType(f"NO_HANDLER:{normalized}")
    return spec


def dispatch_processing_worker_job(worker: Any, job: Any, content: Any) -> None:
    spec = resolve_processing_worker_handler(str(getattr(job, "job_type", "")))
    spec.handler(worker, job, content)
