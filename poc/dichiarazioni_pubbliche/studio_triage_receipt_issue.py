"""Explicit LOCAL pre-issue of an operator identity-bound private triage intent.

Run separately from the browser and PostgreSQL writer. An issued receipt is
NOT a persisted annotation and NEVER licenses a review/capture/publish action.
This CLI refuses an unsafe authority root via the existing credential guard.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dichiarazioni_pubbliche.reviewer_identity_authority import LocalFileReviewerIdentityAuthority
from dichiarazioni_pubbliche.studio_discovery_triage_authority import issue_triage_attestation
from dichiarazioni_pubbliche.studio_discovery_triage_contract import make_triage_request


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create signed DP417 private annotation receipt; no DB write")
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--credential-id", required=True)
    parser.add_argument("--collection-id", required=True)
    parser.add_argument("--hit-id", required=True)
    parser.add_argument("--request-key", required=True)
    parser.add_argument("--decision", required=True, choices=("NEEDS_REVIEW", "DEFERRED", "REJECTED"))
    parser.add_argument("--expected-revision", type=int, required=True)
    parser.add_argument("--actor-ref", required=True)
    parser.add_argument("--confirm-private-annotation-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_private_annotation_only:
        parser.error("explicit --confirm-private-annotation-only required")
    try:
        authority = LocalFileReviewerIdentityAuthority(args.authority_root)
        request = make_triage_request(
            collection_id=args.collection_id, hit_id=args.hit_id,
            request_key=args.request_key, decision=args.decision,
            expected_revision=args.expected_revision, actor_ref=args.actor_ref,
        )
        proof = issue_triage_attestation(authority, request, args.credential_id)
        print(json.dumps({
            "contract_version": "studio-private-annotation-receipt-cli-v1",
            "receipt_id": proof["receipt_id"],
            "payload_sha256": proof["payload_sha256"],
            "database_written": False,
            "publication_authority": False,
        }, separators=(",", ":"), sort_keys=True))
        return 0
    except (ValueError, OSError, UnicodeError):
        # Never echo private path, credential data, filenames or supplied IDs.
        print("STUDIO_TRIAGE_RECEIPT_ISSUE_REFUSED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
