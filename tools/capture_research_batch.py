#!/usr/bin/env python3
"""Private, dry-run-first bounded Capture/Passage batch; no public side effects."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import (  # noqa: E402
    CaptureBodyStore, CapturePipelineStore, capture_content,
)
from dichiarazioni_pubbliche.capture_authorization import (  # noqa: E402
    PrivateCaptureAuthorizationBlocked,
)
from dichiarazioni_pubbliche.private_capture_batch import (  # noqa: E402
    load_private_capture_batch, preflight_capture_batch,
)
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight or run a reviewed private capture batch")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Explicitly perform network and private database writes")
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument(
        "--storage-root", type=Path,
        default=Path(os.environ.get(
            "DICHIARAZIONI_PUBBLICHE_CAPTURE_STORAGE_ROOT",
            "~/.local/share/dichiarazioni-pubbliche-captures",
        )).expanduser(),
    )
    args = parser.parse_args(argv)
    batch = load_private_capture_batch(args.manifest)
    capture_store = CapturePipelineStore(database_url=args.database_url)
    rights_store = PrivateRightsRegistryStore(database_url=args.database_url)
    try:
        guards = preflight_capture_batch(batch, capture_store=capture_store, rights_store=rights_store)
    except PrivateCaptureAuthorizationBlocked as exc:
        print(json.dumps({
            "status": "BLOCKED_NO_FETCH",
            "reason_code": str(exc),
            "manifest_sha256": batch.manifest_sha256,
            "publication_authorized": False,
        }, sort_keys=True))
        return 2
    if not args.execute:
        print(json.dumps({
            "status": "PREFLIGHT_PASS_NO_WRITES",
            "collection_id": batch.collection_id,
            "manifest_sha256": batch.manifest_sha256,
            "ready_items": len(guards),
            "publication_authorized": False,
        }, sort_keys=True))
        return 0

    before = capture_store.read_private_capture_safety_counts()
    body_store = CaptureBodyStore(args.storage_root)
    successful = 0
    for item, guard in zip(batch.items, guards):
        # Check against the current DB again even if another item was processed.
        guard()
        receipt = capture_content(
            content_id=item.content_id,
            url=item.canonical_url,
            store=capture_store,
            body_store=body_store,
            rights_status="CLEARED",
            rights_guard=guard,
        )
        if receipt.parse_status != "SUCCEEDED":
            print(json.dumps({
                "status": "HALTED_PARSE_NOT_SUCCEEDED",
                "completed": successful,
                "manifest_sha256": batch.manifest_sha256,
                "reason_code": receipt.reason_code,
                "publication_authorized": False,
            }, sort_keys=True))
            return 2
        if capture_store.read_private_capture_safety_counts() != before:
            print(json.dumps({
                "status": "HALTED_DOWNSTREAM_COUNTS_CHANGED",
                "completed": successful + 1,
                "manifest_sha256": batch.manifest_sha256,
                "publication_authorized": False,
            }, sort_keys=True))
            return 3
        successful += 1
    print(json.dumps({
        "status": "PRIVATE_CAPTURES_PARSED",
        "completed": successful,
        "manifest_sha256": batch.manifest_sha256,
        "publication_authorized": False,
        "candidate_count": 0,
        "candidate_extraction_status": "NOT_RUN_PROVIDER_REVIEW_REQUIRED",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
