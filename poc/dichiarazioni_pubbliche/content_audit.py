from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


MATERIAL_ASSESSMENTS = {
    "SUPPORTED",
    "SUPPORTED_WITH_CONTEXT",
    "APPROXIMATELY_SUPPORTED",
    "MISSING_CONTEXT",
    "PARTIALLY_SUPPORTED",
    "CONTRADICTED",
    "MISATTRIBUTED",
    "MISATTRIBUTED_CONTEXT",
    "REASONING_OVERREACH",
}


def load_audit(path: Path) -> dict:
    return json.loads(path.read_text())


def validate_audit(audit: dict) -> list[str]:
    errors: list[str] = []
    claims = audit.get("claims", [])
    evidence = audit.get("evidence", [])
    segments = audit.get("segment_coverage", [])

    claim_ids = [row.get("id") for row in claims]
    evidence_ids = [row.get("id") for row in evidence]
    if len(claim_ids) != len(set(claim_ids)):
        errors.append("duplicate claim id")
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("duplicate evidence id")

    claim_id_set = set(claim_ids)
    evidence_id_set = set(evidence_ids)

    for claim in claims:
        cid = claim.get("id", "<missing>")
        assessment = claim.get("assessment")
        refs = claim.get("evidence_ids", [])
        unknown = sorted(set(refs) - evidence_id_set)
        if unknown:
            errors.append(f"{cid}: unknown evidence ids {unknown}")
        if assessment in MATERIAL_ASSESSMENTS and not refs:
            errors.append(f"{cid}: material assessment without evidence")
        if claim.get("type") == "ELECTION_PREDICTION" and assessment not in {
            "PREDICTION_PENDING",
            "PREDICTION_NOT_FACT_CHECKABLE",
        }:
            errors.append(
                f"{cid}: election prediction given current-fact assessment {assessment}"
            )
        if claim.get("type") == "MOTIVE_ATTRIBUTION" and assessment == "SUPPORTED":
            errors.append(
                f"{cid}: motive attribution cannot be supported without a stronger intent contract"
            )
        if claim.get("numeric_sensitive"):
            asr = claim.get("asr_verification")
            if not isinstance(asr, dict) or asr.get("status") != "CONFIRMED":
                errors.append(
                    f"{cid}: numeric-sensitive claim lacks confirmed secondary ASR"
                )

    if segments:
        indices = [row.get("index") for row in segments]
        if indices != list(range(len(segments))):
            errors.append("segment indices are not contiguous from zero")
        inserted_clip_rows = []
        for row in segments:
            unknown = sorted(set(row.get("claim_ids", [])) - claim_id_set)
            if unknown:
                errors.append(
                    f"segment {row.get('index')}: unknown claim ids {unknown}"
                )
            try:
                minutes, seconds = map(int, str(row.get("timestamp", "")).split(":"))
                start_seconds = minutes * 60 + seconds
            except (TypeError, ValueError):
                errors.append(f"segment {row.get('index')}: invalid timestamp")
                continue
            if 414 <= start_seconds <= 434:
                inserted_clip_rows.append(row)
        if not inserted_clip_rows:
            errors.append("inserted Meloni clip interval has no segment coverage")
        elif any(
            row.get("speaker") != "Giorgia Meloni (inserted clip)"
            for row in inserted_clip_rows
        ):
            errors.append("inserted Meloni clip is attributed to the wrong speaker")

    forbidden = {
        "accuracy_score",
        "truth_score",
        "person_score",
        "creator_score",
        "overall_verdict",
    }
    present = sorted(forbidden.intersection(audit))
    if present:
        errors.append(f"forbidden aggregate score fields present: {present}")

    provenance = audit.get("transcript_provenance", {})
    if provenance.get("full_transcript_committed") is not False:
        errors.append("full transcript must remain local and uncommitted")
    if not provenance.get("content_sha256"):
        errors.append("missing transcript/source content hash")

    return errors


def summarize_audit(audit: dict) -> dict:
    claims = audit.get("claims", [])
    segments = audit.get("segment_coverage", [])
    evidence = audit.get("evidence", [])
    assessments = Counter(row.get("assessment", "<missing>") for row in claims)
    types = Counter(row.get("type", "<missing>") for row in claims)
    return {
        "audit_id": audit.get("audit_id") or audit.get("content_id"),
        "claim_count": len(claims),
        "segment_count": len(segments),
        "evidence_count": len(evidence),
        "assessment_counts": dict(sorted(assessments.items())),
        "type_counts": dict(sorted(types.items())),
        "validation_errors": validate_audit(audit),
    }


# Aliases for the first POC naming.
load_content_audit = load_audit
validate_content_audit = validate_audit
summarize_content_audit = summarize_audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    audit = load_audit(args.audit)
    summary = summarize_audit(audit)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    print(
        f"{summary['audit_id']}: {summary['claim_count']} claims, "
        f"{summary['segment_count']} transcript segments, "
        f"{summary['evidence_count']} evidence records"
    )
    for key, value in summary["assessment_counts"].items():
        print(f"  {key}: {value}")
    if summary["validation_errors"]:
        for error in summary["validation_errors"]:
            print(f"ERROR: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
