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
from dichiarazioni_pubbliche.capture_authorization import (  # noqa: E402
    private_capture_rights_guard,
)
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore  # noqa: E402


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
    parser.add_argument("--rights-record-id", required=True, help="Current, reviewed private rights record ID")
    parser.add_argument("--source-family", required=True, help="Exact source family bound to the rights record")
    parser.add_argument("--language", default="it")
    args = parser.parse_args(argv)

    rights_store = PrivateRightsRegistryStore(database_url=args.database_url)
    capture_store = CapturePipelineStore(database_url=args.database_url)
    guard = private_capture_rights_guard(
        read_current=rights_store.read_current,
        rights_record_id=args.rights_record_id,
        content_id=args.content_id,
        canonical_url=args.url,
        source_family=args.source_family,
        read_content_state=capture_store.read_operator_capture_content_state,
    )
    guard()  # Refuse before network, filesystem writes or ingestion permit issuance.
    receipt = capture_content(
        content_id=args.content_id,
        url=args.url,
        store=capture_store,
        body_store=CaptureBodyStore(args.storage_root),
        retention_class=args.retention_class,
        rights_status="CLEARED",
        language=args.language,
        rights_guard=guard,
    )
    print(json.dumps(receipt.__dict__, ensure_ascii=False, sort_keys=True))
    return 0 if receipt.parse_status == "SUCCEEDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
