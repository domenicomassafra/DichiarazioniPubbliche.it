#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.source_intelligence import (  # noqa: E402
    SourceIntelligenceStore,
    load_source_intelligence_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync versioned Source Intelligence and evidence requirement profiles"
    )
    parser.add_argument("--database-url")
    args = parser.parse_args()
    contract = load_source_intelligence_contract()
    counts = SourceIntelligenceStore(database_url=args.database_url).sync_contract(contract)
    print(
        json.dumps(
            {
                "source_version": contract.source_version,
                "requirement_version": contract.requirement_version,
                **counts,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
