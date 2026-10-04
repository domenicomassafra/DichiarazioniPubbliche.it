from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence


class ReadinessState(StrEnum):
    READY = "READY"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    DEFERRED = "DEFERRED"
    UNCONFIGURED = "UNCONFIGURED"


class PipelineStage(StrEnum):
    SOURCE_DISCOVERY = "SOURCE_DISCOVERY"
    TRANSCRIPT_ACQUISITION = "TRANSCRIPT_ACQUISITION"
    REMOTE_ASR = "REMOTE_ASR"
    CLAIM_EXTRACTION = "CLAIM_EXTRACTION"
    EVIDENCE_RETRIEVAL = "EVIDENCE_RETRIEVAL"
    DETERMINISTIC_VERIFICATION = "DETERMINISTIC_VERIFICATION"
    RELATION_ANALYSIS = "RELATION_ANALYSIS"
    PUBLIC_PROJECTION = "PUBLIC_PROJECTION"


# Known capabilities that the collection-readiness checker evaluates.
KNOWN_CAPABILITIES = frozenset(
    {
        "claim_extraction_available",
        "remote_asr_credential_configured",
        "deterministic_verification_available",
        "public_projection_writable",
        "evidence_retrieval_available",
        "relation_analysis_available",
    }
)


@dataclass(frozen=True)
class StageReadiness:
    stage: PipelineStage
    state: ReadinessState
    detail: str
    next_action: str
    downstream_child_jobs_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "state": self.state.value,
            "detail": self.detail,
            "next_action": self.next_action,
            "downstream_child_jobs_allowed": self.downstream_child_jobs_allowed,
        }


@dataclass(frozen=True)
class CollectionReadinessReport:
    overall_state: ReadinessState
    stages: tuple[StageReadiness, ...]
    unrecognized_capabilities: tuple[str, ...]
    queue_counts: dict[str, int]

    @property
    def is_ready(self) -> bool:
        return self.overall_state == ReadinessState.READY

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_state": self.overall_state.value,
            "is_ready": self.is_ready,
            "unrecognized_capabilities": list(self.unrecognized_capabilities),
            "stages": [s.to_dict() for s in self.stages],
            "queue_counts": dict(sorted(self.queue_counts.items())),
        }


def evaluate_collection_readiness(
    *,
    configured_sources: Sequence[Mapping[str, Any]] | None = None,
    capabilities: Mapping[str, Any] | None = None,
    queue_counts: Mapping[str, int] | None = None,
) -> CollectionReadinessReport:
    """Pure, governed evaluation of pipeline collection readiness.

    Takes bounded in-memory inputs, performs no I/O, no network calls, no DB writes,
    and returns a deterministic CollectionReadinessReport.
    """
    caps = dict(capabilities or {})
    sources = list(configured_sources or [])
    q_counts = {str(k): int(v) for k, v in (queue_counts or {}).items()}

    # Check for unrecognized capabilities -> fail-closed
    unrecognized = tuple(sorted(set(caps.keys()) - KNOWN_CAPABILITIES))

    # Evaluate each pipeline stage deterministically in order
    stages_eval: list[StageReadiness] = []

    # 1. SOURCE_DISCOVERY
    if unrecognized:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.SOURCE_DISCOVERY,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail=f"Unrecognized capability flags detected: {', '.join(unrecognized)}",
                next_action="Remove or govern unknown capability flags before proceeding.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif not sources:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.SOURCE_DISCOVERY,
                state=ReadinessState.UNCONFIGURED,
                detail="No sources configured in registry.",
                next_action="Configure at least one approved source in source-registry.",
                downstream_child_jobs_allowed=False,
            )
        )
    else:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.SOURCE_DISCOVERY,
                state=ReadinessState.READY,
                detail=f"{len(sources)} source(s) configured.",
                next_action="Run source discovery on schedule.",
                downstream_child_jobs_allowed=True,
            )
        )

    # 2. TRANSCRIPT_ACQUISITION
    if unrecognized:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.TRANSCRIPT_ACQUISITION,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail=f"Unrecognized capability flags detected: {', '.join(unrecognized)}",
                next_action="Remove or govern unknown capability flags.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif not sources:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.TRANSCRIPT_ACQUISITION,
                state=ReadinessState.UNCONFIGURED,
                detail="No sources configured for transcript acquisition.",
                next_action="Configure source registry entries with valid content policy.",
                downstream_child_jobs_allowed=False,
            )
        )
    else:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.TRANSCRIPT_ACQUISITION,
                state=ReadinessState.READY,
                detail="Source transcript adapters and platform caption acquisition ready.",
                next_action="Acquire captions and canonicalize transcripts.",
                downstream_child_jobs_allowed=True,
            )
        )

    # 3. REMOTE_ASR
    asr_configured = bool(caps.get("remote_asr_credential_configured"))
    if unrecognized:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.REMOTE_ASR,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail=f"Unrecognized capability flags detected: {', '.join(unrecognized)}",
                next_action="Resolve unrecognized capability flags.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif not asr_configured:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.REMOTE_ASR,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail="Remote ASR credential is not configured or missing.",
                next_action="DP-204: Configure Groq API credential outside Git and verify live receipt canary.",
                downstream_child_jobs_allowed=False,
            )
        )
    else:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.REMOTE_ASR,
                state=ReadinessState.READY,
                detail="Remote ASR credential configured.",
                next_action="Process secondary ASR fallback when needed.",
                downstream_child_jobs_allowed=True,
            )
        )

    # 4. CLAIM_EXTRACTION
    claim_avail = bool(caps.get("claim_extraction_available"))
    if unrecognized:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.CLAIM_EXTRACTION,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail=f"Unrecognized capability flags detected: {', '.join(unrecognized)}",
                next_action="Resolve unrecognized capability flags.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif not claim_avail:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.CLAIM_EXTRACTION,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail="Claim extraction capability is unavailable (official OmniRoute route blocked).",
                next_action="DP-201: Complete official OmniRoute meaningful canary and cost gate before fan-out.",
                downstream_child_jobs_allowed=False,
            )
        )
    else:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.CLAIM_EXTRACTION,
                state=ReadinessState.READY,
                detail="Claim extraction capability available.",
                next_action="Run claim extraction on prepared transcript windows.",
                downstream_child_jobs_allowed=True,
            )
        )

    # 5. EVIDENCE_RETRIEVAL
    # Can run if configured, but downstream depends on claim extraction
    evidence_avail = caps.get("evidence_retrieval_available")
    if unrecognized:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.EVIDENCE_RETRIEVAL,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail=f"Unrecognized capability flags detected: {', '.join(unrecognized)}",
                next_action="Resolve unrecognized capability flags.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif evidence_avail is None:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.EVIDENCE_RETRIEVAL,
                state=ReadinessState.UNCONFIGURED,
                detail="Evidence retrieval capability flag not provided.",
                next_action="Configure evidence retrieval capability flag.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif not evidence_avail:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.EVIDENCE_RETRIEVAL,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail="Evidence retrieval capability is disabled or unavailable.",
                next_action="Enable safe evidence fetcher and official query endpoints.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif not claim_avail:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.EVIDENCE_RETRIEVAL,
                state=ReadinessState.DEFERRED,
                detail="Evidence retrieval ready but deferred until upstream claim extraction produces claims.",
                next_action="Await upstream claim extraction readiness (DP-201..DP-203).",
                downstream_child_jobs_allowed=False,
            )
        )
    else:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.EVIDENCE_RETRIEVAL,
                state=ReadinessState.READY,
                detail="Evidence retrieval ready.",
                next_action="Fetch evidence for extracted claims.",
                downstream_child_jobs_allowed=True,
            )
        )

    # 6. DETERMINISTIC_VERIFICATION
    verif_avail = caps.get("deterministic_verification_available")
    if unrecognized:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.DETERMINISTIC_VERIFICATION,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail=f"Unrecognized capability flags detected: {', '.join(unrecognized)}",
                next_action="Resolve unrecognized capability flags.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif verif_avail is None:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.DETERMINISTIC_VERIFICATION,
                state=ReadinessState.UNCONFIGURED,
                detail="Deterministic verification capability flag not provided.",
                next_action="Configure deterministic verification availability flag.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif not verif_avail:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.DETERMINISTIC_VERIFICATION,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail="Deterministic verification rules or runner unavailable.",
                next_action="Verify deterministic verification rule set and runtime setup.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif not claim_avail:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.DETERMINISTIC_VERIFICATION,
                state=ReadinessState.DEFERRED,
                detail="Deterministic verification ready but deferred until claims and evidence exist.",
                next_action="Await upstream claim extraction and evidence observation.",
                downstream_child_jobs_allowed=False,
            )
        )
    else:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.DETERMINISTIC_VERIFICATION,
                state=ReadinessState.READY,
                detail="Deterministic verification v2 ready.",
                next_action="Verify extracted claims against evidence observations.",
                downstream_child_jobs_allowed=True,
            )
        )

    # 7. RELATION_ANALYSIS
    relation_avail = caps.get("relation_analysis_available")
    if unrecognized:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.RELATION_ANALYSIS,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail=f"Unrecognized capability flags detected: {', '.join(unrecognized)}",
                next_action="Resolve unrecognized capability flags.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif relation_avail is None:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.RELATION_ANALYSIS,
                state=ReadinessState.UNCONFIGURED,
                detail="Relation analysis capability flag not provided.",
                next_action="Configure relation analysis capability flag.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif not relation_avail:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.RELATION_ANALYSIS,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail="Claim relation classifier unavailable.",
                next_action="Enable longitudinal claim relation classifier (DP-104).",
                downstream_child_jobs_allowed=False,
            )
        )
    elif not claim_avail:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.RELATION_ANALYSIS,
                state=ReadinessState.DEFERRED,
                detail="Relation analysis ready but deferred until claims exist.",
                next_action="Await upstream claim extraction readiness.",
                downstream_child_jobs_allowed=False,
            )
        )
    else:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.RELATION_ANALYSIS,
                state=ReadinessState.READY,
                detail="Claim relation classification ready.",
                next_action="Classify longitudinal claim relations.",
                downstream_child_jobs_allowed=True,
            )
        )

    # 8. PUBLIC_PROJECTION
    proj_writable = caps.get("public_projection_writable")
    if unrecognized:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.PUBLIC_PROJECTION,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail=f"Unrecognized capability flags detected: {', '.join(unrecognized)}",
                next_action="Resolve unrecognized capability flags.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif proj_writable is None:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.PUBLIC_PROJECTION,
                state=ReadinessState.UNCONFIGURED,
                detail="Public projection target writability flag not provided.",
                next_action="Check and configure public projection output path permissions.",
                downstream_child_jobs_allowed=False,
            )
        )
    elif not proj_writable:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.PUBLIC_PROJECTION,
                state=ReadinessState.BLOCKED_EXTERNAL,
                detail="Public projection output directory is not writable.",
                next_action="Ensure destination directory for public projection is writable.",
                downstream_child_jobs_allowed=False,
            )
        )
    else:
        stages_eval.append(
            StageReadiness(
                stage=PipelineStage.PUBLIC_PROJECTION,
                state=ReadinessState.READY,
                detail="Public projection output path writable.",
                next_action="Project approved findings according to fail-closed policy.",
                downstream_child_jobs_allowed=True,
            )
        )

    # Compute overall state
    all_states = [s.state for s in stages_eval]
    if all(st == ReadinessState.READY for st in all_states):
        overall = ReadinessState.READY
    elif any(st == ReadinessState.BLOCKED_EXTERNAL for st in all_states):
        overall = ReadinessState.BLOCKED_EXTERNAL
    elif any(st == ReadinessState.UNCONFIGURED for st in all_states):
        overall = ReadinessState.UNCONFIGURED
    else:
        overall = ReadinessState.DEFERRED

    return CollectionReadinessReport(
        overall_state=overall,
        stages=tuple(stages_eval),
        unrecognized_capabilities=unrecognized,
        queue_counts=q_counts,
    )


def format_readiness_report(report: CollectionReadinessReport) -> str:
    """Format report deterministically into a clean human-readable table."""
    lines: list[str] = [
        "DICHIARAZIONI PUBBLICHE — COLLECTION READINESS REPORT",
        f"Overall Status: {report.overall_state.value}",
        "",
        f"{'Stage':<30} {'State':<18} {'Next Action'}",
        "-" * 80,
    ]
    for s in report.stages:
        lines.append(f"{s.stage.value:<30} {s.state.value:<18} {s.next_action}")
        if s.detail:
            lines.append(f"  └─ Detail: {s.detail}")
    if report.unrecognized_capabilities:
        lines.append("")
        lines.append("Unrecognized Capabilities:")
        for cap in report.unrecognized_capabilities:
            lines.append(f"  - {cap}")
    if report.queue_counts:
        lines.append("")
        lines.append("Queue Counts:")
        for k, v in sorted(report.queue_counts.items()):
            lines.append(f"  {k}: {v}")
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Governed collection-readiness check for Dichiarazioni Pubbliche pipeline."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output",
    )
    parser.add_argument(
        "--sources-file",
        type=str,
        default=None,
        help="Path to source registry JSON file",
    )
    parser.add_argument(
        "--capabilities-json",
        type=str,
        default=None,
        help="JSON string with capability flags",
    )
    parser.add_argument(
        "--queue-counts-json",
        type=str,
        default=None,
        help="JSON string with queue status counts",
    )
    args = parser.parse_args(argv)

    sources = []
    if args.sources_file:
        try:
            with open(args.sources_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                sources = data.get("sources", [])
        except Exception as exc:
            print(f"Error reading sources file: {exc}", file=sys.stderr)
            return 2

    caps = {}
    if args.capabilities_json:
        try:
            caps = json.loads(args.capabilities_json)
        except Exception as exc:
            print(f"Error parsing capabilities JSON: {exc}", file=sys.stderr)
            return 2

    q_counts = {}
    if args.queue_counts_json:
        try:
            q_counts = json.loads(args.queue_counts_json)
        except Exception as exc:
            print(f"Error parsing queue counts JSON: {exc}", file=sys.stderr)
            return 2

    report = evaluate_collection_readiness(
        configured_sources=sources,
        capabilities=caps,
        queue_counts=q_counts,
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_readiness_report(report))

    return 0 if report.is_ready else 1


if __name__ == "__main__":
    sys.exit(main())
