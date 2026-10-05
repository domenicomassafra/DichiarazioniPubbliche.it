"""Restore-drill verification logic (DP-502).

Pure comparison functions used by ``deploy/ops/restore_drill.sh``. The script
does the I/O (pg_dump, pg_restore, psql); this module decides whether what came
back is actually correct.

The rule this module exists to enforce: a restore must never fabricate data and
a failed restore must fail loudly. Concretely,

  * a table is RESTORED only if its row count matches the source exactly;
  * a projection bundle is RESTORED only if its ``dataset_sha256`` matches;
  * a missing measurement is ``UNKNOWN``/FAIL, never assumed-good;
  * nothing here ever "regenerates" a projection to make a comparison pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


# Result statuses, worst last.
RESULTS = ("RESTORED", "MISSING", "MISMATCH", "UNKNOWN")

# Tables whose contents constitute the public record and provider accounting.
# Empty restore of any of these is a failed drill, not an empty database.
LOAD_BEARING_TABLES = (
    "source",
    "content_item",
    "content_capture",
    "capture_lifecycle_event",
    "research_collection",
    "research_collection_content",
    "research_discovery_manifest",
    "research_discovery_query",
    "research_discovery_run",
    "research_discovery_attempt",
    "research_discovery_hit",
    "content_derivation_family",
    "content_derivation_candidate",
    "proposition_cluster",
    "proposition_cluster_member",
    "candidate_match_run",
    "candidate_match_result",
    "topic",
    "topic_alias",
    "event",
    "event_alias",
    "organization_alias",
    "entity_identifier",
    "entity_resolution_candidate",
    "claim_topic_membership",
    "passage",
    "statement_candidate",
    "statement_candidate_passage",
    "claim_candidate",
    "claim_candidate_promotion",
    "candidate_extraction_run",
    "entity_mention_candidate",
    "source_profile",
    "source_evidence_role",
    "source_authority_scope",
    "source_relation",
    "evidence_requirement_profile",
    "evidence_requirement_rule",
    "evidence_set_assessment",
    "transcript_variant",
    "transcript_segment",
    "canonical_transcript_segment",
    "atomic_claim",
    "claim_segment",
    "claim_text_provenance",
    "evidence",
    "claim_evidence_candidate",
    "evidence_observation",
    "coverage_need",
    "coverage_need_event",
    "verification_run",
    "inference_candidate",
    "review_event",
    "finding",
    "finding_evidence",
    "provider_receipt",
    "processing_job",
)


@dataclass(frozen=True)
class TableCheck:
    table: str
    source_rows: int | None
    restored_rows: int | None
    result: str
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.result == "RESTORED"


@dataclass(frozen=True)
class BundleCheck:
    label: str
    source_sha256: str | None
    restored_sha256: str | None
    result: str
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.result == "RESTORED"


@dataclass(frozen=True)
class DrillReport:
    checks: tuple[Any, ...]
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def check_table(table: str, source_rows: Any, restored_rows: Any) -> TableCheck:
    """Compare one table's row counts across backup and restore."""
    if source_rows is None or restored_rows is None:
        missing = []
        if source_rows is None:
            missing.append("source")
        if restored_rows is None:
            missing.append("restored")
        return TableCheck(
            table, source_rows, restored_rows, "UNKNOWN",
            f"unmeasured:{'+'.join(missing)}",
        )
    try:
        src = int(source_rows)
        dst = int(restored_rows)
    except (TypeError, ValueError):
        return TableCheck(
            table, source_rows, restored_rows, "UNKNOWN", "non_integer_count"
        )
    if src == dst:
        return TableCheck(table, src, dst, "RESTORED")
    if dst == 0 and src > 0:
        return TableCheck(
            table, src, dst, "MISSING", "restored table is empty while source has rows"
        )
    return TableCheck(
        table, src, dst, "MISMATCH", f"delta={dst - src}"
    )


def check_bundle(label: str, source_sha256: Any, restored_sha256: Any) -> BundleCheck:
    """Compare a projection bundle's dataset_sha256 across backup and restore."""
    src = str(source_sha256).strip() if source_sha256 is not None else ""
    dst = str(restored_sha256).strip() if restored_sha256 is not None else ""
    if not src or not dst:
        return BundleCheck(
            label, src or None, dst or None, "UNKNOWN", "dataset_sha256 unavailable"
        )
    if src == dst:
        return BundleCheck(label, src, dst, "RESTORED")
    return BundleCheck(label, src, dst, "MISMATCH", "dataset_sha256 differs")


def read_dataset_sha256(path: str) -> str | None:
    """Read dataset_sha256 from a public bundle index.json, or None."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    value = payload.get("dataset_sha256")
    return str(value).strip() if isinstance(value, str) and value.strip() else None


def build_report(
    table_counts: Mapping[str, Any],
    bundles: Sequence[BundleCheck] = (),
    *,
    required_tables: Sequence[str] = LOAD_BEARING_TABLES,
) -> DrillReport:
    """Assemble the drill verdict.

    ``table_counts`` maps table -> (source_rows, restored_rows). A required
    table absent from the mapping is an UNKNOWN failure, because a drill that
    silently skips a load-bearing table is exactly the silent-failure mode this
    module is meant to eliminate.
    """
    checks: list[Any] = []
    failures: list[str] = []

    for table in required_tables:
        pair = table_counts.get(table)
        if pair is None:
            check = TableCheck(table, None, None, "UNKNOWN", "table not measured")
        elif isinstance(pair, (list, tuple)) and len(pair) == 2:
            check = check_table(table, pair[0], pair[1])
        else:
            check = TableCheck(table, pair, None, "UNKNOWN", "malformed_count_pair")
        checks.append(check)
        if not check.ok:
            failures.append(f"table:{table}:{check.result}:{check.detail}")

    for bundle in bundles:
        checks.append(bundle)
        if not bundle.ok:
            failures.append(f"bundle:{bundle.label}:{bundle.result}:{bundle.detail}")

    return DrillReport(checks=tuple(checks), failures=tuple(failures))


def format_report(report: DrillReport) -> str:
    """Human-readable drill output, suitable for pasting into a ticket."""
    lines = ["RESTORE DRILL VERIFICATION", ""]
    for check in report.checks:
        if isinstance(check, TableCheck):
            lines.append(
                f"  [{check.result:8}] table {check.table}: "
                f"source={check.source_rows} restored={check.restored_rows} "
                f"{check.detail}".rstrip()
            )
        else:
            lines.append(
                f"  [{check.result:8}] bundle {check.label}: "
                f"source={check.source_sha256} restored={check.restored_sha256} "
                f"{check.detail}".rstrip()
            )
    lines.append("")
    if report.passed:
        lines.append("RESULT: PASS (restored state matches backup exactly)")
    else:
        lines.append("RESULT: FAIL (restore did not reproduce the backup; do not publish)")
        for failure in report.failures:
            lines.append(f"  - {failure}")
    return "\n".join(lines)


def validate_drill(
    report: DrillReport,
    *,
    forbidden_states: Sequence[str] = ("REGENERATED", "SUBSTITUTED", "SKIPPED"),
) -> tuple[str, ...]:
    """Assert the drill report contains no forbidden 'made it green' states."""
    defects: list[str] = []
    for state in forbidden_states:
        for check in report.checks:
            if getattr(check, "result", "") == state:
                defects.append(f"forbidden_state:{state}:{getattr(check, 'label', '')}")
    if report.passed and report.failures:
        defects.append("passed_with_failures")
    if not report.passed and not report.failures:
        defects.append("failed_without_failures")
    return tuple(defects)
