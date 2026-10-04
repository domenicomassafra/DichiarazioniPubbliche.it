#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.candidate_extraction import (  # noqa: E402
    CandidateExtractionStore,
    OmniRouteCandidateExtractionClient,
    extract_passage_candidates,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract private research candidates from one Passage")
    parser.add_argument("--passage-id", required=True)
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--omniroute-base-url", default=os.environ.get("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128"))
    parser.add_argument("--api-key", default=os.environ.get("OMNIROUTE_API_KEY", ""))
    parser.add_argument("--model", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_CANDIDATE_EXTRACTION_MODEL", ""))
    parser.add_argument("--max-cost-usd", default="0")
    args = parser.parse_args(argv)

    client = OmniRouteCandidateExtractionClient(
        api_key=args.api_key,
        model_id=args.model or None,
        base_url=args.omniroute_base_url,
    )
    receipt = extract_passage_candidates(
        passage_id=args.passage_id,
        store=CandidateExtractionStore(database_url=args.database_url),
        provider=client,
        max_cost_usd=Decimal(args.max_cost_usd),
    )
    print(
        json.dumps(
            {
                **receipt.__dict__,
                "cost_upper_bound_usd": str(receipt.cost_upper_bound_usd),
                "cost_usd": str(receipt.cost_usd),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if receipt.status == "COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
