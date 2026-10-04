#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.research_discovery import (  # noqa: E402
    ConfiguredRegistryDiscoveryAdapter,
    ResearchDiscoveryStore,
    load_discovery_manifest,
    run_discovery_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one bounded private research discovery manifest")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--registry", type=Path, default=ROOT / "config" / "source-registry.v1.json")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)

    manifest = load_discovery_manifest(args.manifest)
    store = ResearchDiscoveryStore(database_url=args.database_url)
    adapters = {
        "configured_registry": ConfiguredRegistryDiscoveryAdapter(args.registry),
    }
    receipt = run_discovery_manifest(manifest, store, adapters, run_id=args.run_id)
    print(
        json.dumps(
            {
                **receipt.__dict__,
                "cost_usd": str(receipt.cost_usd),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if receipt.status == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
