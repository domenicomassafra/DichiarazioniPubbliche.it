#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.candidate_matching import (  # noqa: E402
    CandidateMatchingStore,
    match_claim_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Match one Claim Candidate against the private corpus")
    parser.add_argument("claim_candidate_id")
    parser.add_argument("--database-url")
    parser.add_argument("--target-limit", type=int, default=200)
    args = parser.parse_args()
    receipt = match_claim_candidate(
        claim_candidate_id=args.claim_candidate_id,
        store=CandidateMatchingStore(database_url=args.database_url),
        target_limit=args.target_limit,
    )
    print(
        json.dumps(
            {
                "run_id": receipt.run_id,
                "claim_candidate_id": receipt.claim_candidate_id,
                "input_fingerprint": receipt.input_fingerprint,
                "result_count": receipt.result_count,
                "replayed": receipt.replayed,
                "results": [
                    {
                        "rank": result.rank,
                        "target_type": result.target.proposition.member_type,
                        "target_id": result.target.proposition.member_id,
                        "match_class": result.match.match_class,
                        "method": result.match.method,
                        "lexical_score": result.match.lexical_score,
                        "disposition": result.disposition,
                        "cluster_id": result.cluster_id,
                        "supporting_features": list(result.supporting_features),
                        "contradicting_features": list(result.contradicting_features),
                    }
                    for result in receipt.results
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
