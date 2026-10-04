#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.curated_written_intake import (  # noqa: E402
    apply_curated_written_batch,
    prepare_curated_written_batch,
)
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a curated written-source claim batch without storing quote bodies."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--database-url")
    parser.add_argument("--actor", default="local-operator")
    parser.add_argument("--approve-attribution", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("curated intake root must be a JSON object")
    batch = prepare_curated_written_batch(payload)
    store = QueueRuntimeStore(args.database_url)
    receipt = apply_curated_written_batch(
        store,
        batch,
        actor_ref=args.actor,
        approve_attribution=args.approve_attribution,
    )
    encoded = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)
    if args.receipt:
        args.receipt.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
