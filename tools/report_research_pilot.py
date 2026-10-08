#!/usr/bin/env python3
"""Read-only operator inventory for a real Research Collection (DP-214/215)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.research_pilot_readiness import (  # noqa: E402
    ResearchPilotReadinessStore, ReadinessReportError, summarize_readiness,
    load_unreviewed_public_leads,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only real-corpus stage/blocker report")
    parser.add_argument("--collection-id", required=True)
    parser.add_argument("--include-ids", action="store_true", help="Add private Content IDs without titles, URLs or bodies")
    parser.add_argument("--leads-file", type=Path, help="Optional unreviewed public URL candidate file; counted separately, never as real Content")
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    args = parser.parse_args(argv)
    try:
        summary, members = ResearchPilotReadinessStore(database_url=args.database_url).read_collection(args.collection_id)
        report = summarize_readiness(summary, members, include_ids=args.include_ids)
        if args.leads_file is not None:
            if args.collection_id != "research:garlasco":
                raise ReadinessReportError("PILOT_LEADS_FILE_COLLECTION_UNSUPPORTED")
            report["external_candidate_hints"] = load_unreviewed_public_leads(args.leads_file)
    except (ReadinessReportError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED_READ_ONLY", "reason_code": str(exc),
                          "publication_authorized": False}, sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
