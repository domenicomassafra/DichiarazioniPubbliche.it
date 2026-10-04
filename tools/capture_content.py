#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import (  # noqa: E402
    CaptureBodyStore,
    CapturePipelineStore,
    capture_content,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely capture and parse one existing Content URL")
    parser.add_argument("--content-id", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=Path(os.environ.get("DICHIARAZIONI_PUBBLICHE_CAPTURE_STORAGE_ROOT", "~/.local/share/dichiarazioni-pubbliche-captures")).expanduser(),
    )
    parser.add_argument(
        "--retention-class",
        choices=("POLICY_PENDING", "EPHEMERAL", "DURABLE_PRIVATE", "DURABLE_PROVENANCE"),
        default="EPHEMERAL",
    )
    parser.add_argument("--rights-status", default="UNKNOWN")
    parser.add_argument("--language", default="it")
    args = parser.parse_args(argv)

    receipt = capture_content(
        content_id=args.content_id,
        url=args.url,
        store=CapturePipelineStore(database_url=args.database_url),
        body_store=CaptureBodyStore(args.storage_root),
        retention_class=args.retention_class,
        rights_status=args.rights_status,
        language=args.language,
    )
    print(json.dumps(receipt.__dict__, ensure_ascii=False, sort_keys=True))
    return 0 if receipt.parse_status == "SUCCEEDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
