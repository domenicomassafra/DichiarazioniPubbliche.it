#!/usr/bin/env python3
"""DP-214: verified private Passage -> Candidate operator batch.

Default preflight is read-only. --execute requires a positive global cost cap,
model/provider configuration and all persisted provenance/rights decisions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_authorization import PrivateCaptureAuthorizationBlocked  # noqa: E402
from dichiarazioni_pubbliche.capture_pipeline import CapturePipelineStore  # noqa: E402
from dichiarazioni_pubbliche.candidate_extraction import (  # noqa: E402
    CandidateExtractionStore,
    OmniRouteCandidateExtractionClient,
    extract_passage_candidates,
)
from dichiarazioni_pubbliche.private_candidate_batch import (  # noqa: E402
    load_candidate_batch,
    preflight_candidate_batch,
)
from dichiarazioni_pubbliche.private_candidate_commit_fence import PrivateCandidateCommitFence  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore  # noqa: E402


def _output(status: str, **values: object) -> None:
    print(json.dumps({"status": status, "publication_authorized": False, **values}, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rights-reviewed private Passage extraction (no publication)")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--execute", action="store_true", help="Explicitly permit model calls and private candidate writes")
    parser.add_argument("--max-cost-usd", default="0", help="Positive TOTAL batch cap required for execution")
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--omniroute-base-url", default=os.environ.get("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128"))
    parser.add_argument("--api-key", default=os.environ.get("OMNIROUTE_API_KEY", ""))
    parser.add_argument("--model", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_CANDIDATE_EXTRACTION_MODEL", ""))
    args = parser.parse_args(argv)
    batch = load_candidate_batch(args.manifest)
    try:
        cap = Decimal(args.max_cost_usd)
        if not cap.is_finite() or cap < 0 or cap > Decimal("25"):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        parser.error("--max-cost-usd must be a nonnegative finite amount <= 25")
    if args.execute and cap <= 0:
        parser.error("--execute requires an explicit positive --max-cost-usd")

    capture_store = CapturePipelineStore(database_url=args.database_url)
    candidate_store = CandidateExtractionStore(database_url=args.database_url)
    rights_store = PrivateRightsRegistryStore(database_url=args.database_url)
    try:
        guards = preflight_candidate_batch(
            batch, capture_store=capture_store, candidate_store=candidate_store, rights_store=rights_store
        )
    except PrivateCaptureAuthorizationBlocked as exc:
        _output("BLOCKED_NO_MODEL_CALL", reason_code=str(exc), manifest_sha256=batch.sha256)
        return 2
    if not args.execute:
        _output("PREFLIGHT_PASS_NO_WRITES", ready_passages=len(guards), manifest_sha256=batch.sha256)
        return 0

    client = OmniRouteCandidateExtractionClient(
        api_key=args.api_key,
        model_id=args.model or None,
        base_url=args.omniroute_base_url,
    )
    # A missing configured provider is not a zero-cost success or a fake canary.
    if not client.api_key or not client.model_id or client.cost_rate is None:
        _output("BLOCKED_PROVIDER_NOT_CONFIGURED", manifest_sha256=batch.sha256)
        return 2

    before = capture_store.read_private_capture_safety_counts()
    spent = Decimal("0")
    completed = 0
    for item, guard in zip(batch.items, guards):
        try:
            guard()
        except PrivateCaptureAuthorizationBlocked as exc:
            _output("BLOCKED_AUTHORITY_CHANGED", reason_code=str(exc), completed=completed,
                    manifest_sha256=batch.sha256)
            return 2
        receipt = extract_passage_candidates(
            passage_id=item.passage_id,
            store=candidate_store,
            provider=client,
            max_cost_usd=cap - spent,
            authorization_guard=guard,
            commit_fence=PrivateCandidateCommitFence(
                collection_id=batch.collection_id,
                content_id=item.content_id,
                capture_id=item.capture_id,
                passage_id=item.passage_id,
                passage_sha256=item.passage_sha256,
                canonical_url=item.canonical_url,
                source_family=item.source_family,
                rights_record_id=item.rights_record_id,
            ),
        )
        # Cost-bearing failed attempts also consume the remaining batch budget.
        spent += receipt.cost_usd
        if spent > cap:
            _output("HALTED_BATCH_COST_EXCEEDED", completed=completed,
                    manifest_sha256=batch.sha256)
            return 3
        after = capture_store.read_private_capture_safety_counts()
        if (after["atomic_claim"] != before["atomic_claim"] or
                after["publish_finding"] != before["publish_finding"]):
            _output("HALTED_PROTECTED_COUNTS_CHANGED", completed=completed,
                    manifest_sha256=batch.sha256)
            return 3
        if receipt.status != "COMPLETED":
            _output("HALTED_EXTRACTION", reason_code=receipt.reason_code, completed=completed,
                    provider_calls=receipt.call_count, manifest_sha256=batch.sha256)
            return 2
        completed += 1
    _output("PRIVATE_CANDIDATES_EXTRACTED", completed=completed,
            actual_cost_usd=str(spent), manifest_sha256=batch.sha256,
            claim_promotion=False, publication=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
