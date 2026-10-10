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
from dichiarazioni_pubbliche.antigravity_cli_candidate import (  # noqa: E402
    AntigravityCliCandidateExtractionClient,
)
from dichiarazioni_pubbliche.private_candidate_batch import (  # noqa: E402
    load_candidate_batch,
    preflight_candidate_batch,
)
from dichiarazioni_pubbliche.private_candidate_commit_fence import PrivateCandidateCommitFence  # noqa: E402
from dichiarazioni_pubbliche.provider_optional_route import (  # noqa: E402
    plan_optional_private_candidate, read_sanitized_catalog,
    validate_optional_omniroute_dispatch,
)
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore  # noqa: E402


def _output(status: str, **values: object) -> None:
    print(json.dumps({"status": status, "publication_authorized": False, **values}, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rights-reviewed private Passage extraction (no publication)")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--execute", action="store_true", help="Explicitly permit model calls and private candidate writes")
    parser.add_argument("--max-cost-usd", default="0", help="Positive TOTAL batch cap required for execution")
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    configured_storage = os.environ.get("DICHIARAZIONI_PUBBLICHE_CAPTURE_STORAGE_ROOT", "").strip()
    parser.add_argument(
        "--storage-root", type=Path,
        default=Path(configured_storage).expanduser() if configured_storage else None,
        help="Existing, approved private Capture storage root; required even for preflight",
    )
    parser.add_argument("--omniroute-base-url", default=os.environ.get("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128"))
    parser.add_argument("--api-key", default=os.environ.get("OMNIROUTE_API_KEY", ""))
    parser.add_argument("--model", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_CANDIDATE_EXTRACTION_MODEL", ""))
    parser.add_argument(
        "--optional-model-catalog", type=Path,
        help="Operator-exported sanitized model/quota catalog; select one approved private candidate model",
    )
    parser.add_argument(
        "--optional-model-catalog-sha256", default="",
        help="Independent SHA-256 approval of the exact sanitized catalog bytes",
    )
    parser.add_argument(
        "--external-model-data-approved", action="store_true",
        help="Explicit permission to send rights-reviewed passages to an external API",
    )
    args = parser.parse_args(argv)
    batch = load_candidate_batch(args.manifest)
    try:
        cap = Decimal(args.max_cost_usd)
        if not cap.is_finite() or cap < 0 or cap > Decimal("25"):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        parser.error("--max-cost-usd must be a nonnegative finite amount <= 25")
    if args.execute and cap <= 0 and args.optional_model_catalog is None:
        parser.error("--execute requires an explicit positive --max-cost-usd")
    root = args.storage_root
    if (
        root is None or not root.is_absolute()
        or root.is_symlink() or not root.is_dir()
    ):
        _output("BLOCKED_NO_MODEL_CALL", reason_code="PRIVATE_ANALYSIS_STORAGE_ROOT_UNAVAILABLE")
        return 2

    capture_store = CapturePipelineStore(database_url=args.database_url)
    candidate_store = CandidateExtractionStore(database_url=args.database_url)
    rights_store = PrivateRightsRegistryStore(database_url=args.database_url)
    try:
        guards = preflight_candidate_batch(
            batch, capture_store=capture_store, candidate_store=candidate_store,
            rights_store=rights_store, storage_root=root,
        )
    except PrivateCaptureAuthorizationBlocked as exc:
        _output("BLOCKED_NO_MODEL_CALL", reason_code=str(exc), manifest_sha256=batch.sha256)
        return 2
    optional_plan = None
    catalog = None
    if args.optional_model_catalog is not None:
        if args.model:
            _output("BLOCKED_NO_MODEL_CALL", reason_code="OPTIONAL_MODEL_CONFLICTS_WITH_FIXED_MODEL")
            return 2
        try:
            catalog = read_sanitized_catalog(
                args.optional_model_catalog,
                expected_sha256=args.optional_model_catalog_sha256,
            )
            # Conservative UTF-8/input+prompt+output budget per bounded passage.
            # The candidate runtime independently estimates each *actual* call.
            total_token_bound = len(guards) * (6000 * 4 + 4096 + 12000)
            optional_plan = plan_optional_private_candidate(
                catalog, input_bytes_sha256=batch.sha256,
                max_total_tokens=total_token_bound,
                requests_needed=len(guards),
                max_batch_cost_usd=cap,
                source_approved_for_external_api=args.external_model_data_approved,
            )
        except ValueError as exc:
            _output("BLOCKED_NO_MODEL_CALL", reason_code=str(exc))
            return 2
        if optional_plan.selected is None:
            _output("BLOCKED_OPTIONAL_PROVIDER", reason_code="NO_ELIGIBLE_MODEL",
                    provider_calls=0, blocked=list(optional_plan.blocked),
                    plan_receipt_id=optional_plan.receipt_id)
            return 2
    if not args.execute:
        _output("PREFLIGHT_PASS_NO_WRITES", ready_passages=len(guards), manifest_sha256=batch.sha256,
                selected_optional_model=(optional_plan.selected.model_id if optional_plan else None),
                plan_receipt_id=(optional_plan.receipt_id if optional_plan else None))
        return 0

    if optional_plan is not None and optional_plan.selected.billing_tier != "ANTIGRAVITY_CLI_QUOTA":
        try:
            validate_optional_omniroute_dispatch(
                optional_plan.selected, args.omniroute_base_url,
            )
        except ValueError as exc:
            _output("BLOCKED_NO_MODEL_CALL", reason_code=str(exc),
                    plan_receipt_id=optional_plan.receipt_id, provider_calls=0)
            return 2

    if optional_plan is not None and optional_plan.selected.billing_tier == "ANTIGRAVITY_CLI_QUOTA":
        # `agy` uses the existing native CLI session quota. Never route this
        # tier through OmniRoute's auto fallback or Gemini Developer API.
        selected_row = next(
            row for row in catalog["models"]
            if row["model_id"] == optional_plan.selected.model_id
        )
        try:
            client = AntigravityCliCandidateExtractionClient(
                model_id=optional_plan.selected.model_id,
                account_scope_sha256=selected_row["single_account_scope"],
                quota_remaining_requests=selected_row["quota_remaining_requests"],
                quota_remaining_tokens=selected_row["quota_remaining_tokens"],
                quota_receipt_id=optional_plan.receipt_id,
                quota_observed_at=selected_row["quota_observed_at"],
            )
        except (RuntimeError, ValueError) as exc:
            _output("BLOCKED_NO_MODEL_CALL", reason_code=str(exc), provider_calls=0)
            return 2
    else:
        client = OmniRouteCandidateExtractionClient(
            api_key=args.api_key,
            model_id=optional_plan.selected.model_id if optional_plan else args.model or None,
            base_url=args.omniroute_base_url,
            cost_rate_usd_per_1k_total_tokens=(
                optional_plan.selected.rate_usd_per_1k_total_tokens
                if optional_plan else None
            ),
        )
    # A missing configured provider is not a zero-cost success or a fake canary.
    if (not isinstance(client, AntigravityCliCandidateExtractionClient)
            and (not client.api_key or not client.model_id or client.cost_rate is None)):
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
