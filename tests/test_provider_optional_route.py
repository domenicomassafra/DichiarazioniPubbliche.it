import hashlib
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.provider_optional_route import (  # noqa: E402
    plan_optional_private_candidate, read_sanitized_catalog,
    validate_optional_omniroute_dispatch,
)


SHA = hashlib.sha256(b"private test fixture").hexdigest()


def row(model, family, tier, **patch):
    return {
        "model_id": model, "family": family, "billing_tier": tier,
        "catalog_model_verified": True, "schema_canary_passed": True,
        "operator_enabled": True, "terms_accepted": True,
        "confidentiality_approved": True,
        "separate_api_entitlement_verified": True,
        "quota_remaining_requests": 20, "quota_remaining_tokens": 200000,
        "usd_per_1k_total_tokens": "0", "paid_owner_authorized": False,
    } | patch


def catalog(*rows, paid=()):
    return {
        "schema_version": 1,
        "catalog_origin": "OWNER_VERIFIED_SANITIZED_OMNIROUTE_CATALOG",
        "models": list(rows), "approved_paid_model_ids": list(paid),
    }


def plan(data, **patch):
    return plan_optional_private_candidate(
        data, input_bytes_sha256=SHA, max_total_tokens=12000,
        requests_needed=2, max_batch_cost_usd=Decimal("0.05"),
        source_approved_for_external_api=False,
        **patch,
    )


class OptionalRouteTests(unittest.TestCase):
    def test_local_plan_cannot_transmit_through_omniroute_gateway(self):
        local = plan(catalog(row("local/qwen3-4b", "local", "LOCAL_ZERO_EXTERNAL"))).selected
        with self.assertRaisesRegex(ValueError, "LOCAL_CANDIDATE_ADAPTER_UNAVAILABLE"):
            validate_optional_omniroute_dispatch(local, "http://127.0.0.1:20128")
        remote = plan_optional_private_candidate(
            catalog(row("openrouter/free-model", "openrouter", "API_FREE_VERIFIED")),
            input_bytes_sha256=SHA, max_total_tokens=12000, requests_needed=2,
            max_batch_cost_usd=Decimal("0"), source_approved_for_external_api=True,
        ).selected
        with self.assertRaisesRegex(ValueError, "GATEWAY_NOT_PINNED_TO_LOOPBACK"):
            validate_optional_omniroute_dispatch(remote, "https://example.invalid")
        validate_optional_omniroute_dispatch(remote, "http://127.0.0.1:20128")
    def test_non_boolean_remote_approval_cannot_enable_api_path(self):
        remote = catalog(row("openrouter/free-model", "openrouter", "API_FREE_VERIFIED"))
        for deceptive in ("false", "0", 1, [], None):
            with self.subTest(deceptive=deceptive), self.assertRaisesRegex(
                ValueError, "OPTIONAL_REMOTE_APPROVAL_MUST_BE_BOOLEAN"
            ):
                plan_optional_private_candidate(
                    remote, input_bytes_sha256=SHA, max_total_tokens=12000,
                    requests_needed=2, max_batch_cost_usd=Decimal("0.05"),
                    source_approved_for_external_api=deceptive,
                )

    def test_micropayment_cost_bound_rounds_up_before_budget_gate(self):
        candidate = row("typesafe/micro-model", "openrouter", "API_PAID_APPROVED",
                        usd_per_1k_total_tokens="0.00000001", paid_owner_authorized=True)
        result = plan_optional_private_candidate(
            catalog(candidate, paid=[candidate["model_id"]]),
            input_bytes_sha256=SHA, max_total_tokens=12000,
            requests_needed=2, max_batch_cost_usd=Decimal("0.000000"),
            source_approved_for_external_api=True,
        )
        self.assertIsNone(result.selected)
        self.assertEqual(result.blocked[0]["reason"], "BATCH_COST_CAP_EXCEEDED")

    def test_local_first_even_when_approved_remote_free_present(self):
        data = catalog(
            row("openrouter/free-model", "openrouter", "API_FREE_VERIFIED"),
            row("local/qwen3-4b", "local", "LOCAL_ZERO_EXTERNAL"),
            row("groq/free-model", "groq", "API_FREE_VERIFIED"),
        )
        result = plan(data)
        self.assertEqual(result.selected.model_id, "local/qwen3-4b")
        self.assertEqual(result.selected.estimated_upper_usd, Decimal("0.000000"))
        self.assertEqual(result.provider_calls, 0)
        self.assertFalse(result.publication_authorized)
        self.assertEqual([x["reason"] for x in result.blocked], [
            "SOURCE_NOT_APPROVED_FOR_REMOTE_MODEL", "SOURCE_NOT_APPROVED_FOR_REMOTE_MODEL",
        ])
        self.assertEqual(result.receipt_id, plan(data).receipt_id)

    def test_openrouter_free_prioritized_over_other_verified_api_free(self):
        remote = catalog(
            row("nvidia/verified-free-model", "nvidia", "API_FREE_VERIFIED"),
            row("gemini/verified-api-model", "gemini-api", "API_FREE_VERIFIED"),
            row("openrouter/verified-free-model", "openrouter", "API_FREE_VERIFIED"),
        )
        selected = plan_optional_private_candidate(
            remote, input_bytes_sha256=SHA, max_total_tokens=12000,
            requests_needed=2, max_batch_cost_usd=Decimal("0"),
            source_approved_for_external_api=True,
        )
        self.assertEqual(selected.selected.model_id, "openrouter/verified-free-model")

    def test_missing_account_quota_terms_quality_and_source_approval_block_each_tier(self):
        data = catalog(
            row("openrouter/unknown-entitlement", "openrouter", "API_FREE_VERIFIED",
                separate_api_entitlement_verified=False),
            row("groq/insufficient", "groq", "API_FREE_VERIFIED", quota_remaining_requests=1),
            row("gemini/terms-missing", "gemini-api", "API_FREE_VERIFIED", terms_accepted=False),
            row("cerebras/privacy-missing", "cerebras", "API_FREE_VERIFIED", confidentiality_approved=False),
            row("local/quality-missing", "local", "LOCAL_ZERO_EXTERNAL", schema_canary_passed=False),
        )
        result = plan_optional_private_candidate(
            data, input_bytes_sha256=SHA, max_total_tokens=12000,
            requests_needed=2, max_batch_cost_usd=Decimal("0.05"),
            source_approved_for_external_api=True,
        )
        self.assertIsNone(result.selected)
        self.assertEqual({x["reason"] for x in result.blocked}, {
            "SEPARATE_API_ENTITLEMENT_UNVERIFIED", "VERIFIED_FREE_OR_PAID_QUOTA_INSUFFICIENT",
            "PROVIDER_TERMS_NOT_ACCEPTED", "REMOTE_CONFIDENTIALITY_NOT_APPROVED",
            "SCHEMA_QUALITY_CANARY_UNPROVEN",
        })

    def test_paid_requires_both_whitelist_and_explicit_owner_budget(self):
        candidate = row("typesafe/owner-curated-model", "openrouter", "API_PAID_APPROVED",
                        usd_per_1k_total_tokens="0.002", paid_owner_authorized=True)
        blocked = plan_optional_private_candidate(
            catalog(candidate), input_bytes_sha256=SHA, max_total_tokens=12000,
            requests_needed=2, max_batch_cost_usd=Decimal("0.05"),
            source_approved_for_external_api=True,
        )
        self.assertEqual(blocked.blocked[0]["reason"], "PAID_MODEL_NOT_OWNER_WHITELISTED")
        allowed = plan_optional_private_candidate(
            catalog(candidate, paid=[candidate["model_id"]]),
            input_bytes_sha256=SHA, max_total_tokens=12000,
            requests_needed=2, max_batch_cost_usd=Decimal("0.05"),
            source_approved_for_external_api=True,
        )
        self.assertEqual(allowed.selected.estimated_upper_usd, Decimal("0.024000"))
        over = plan_optional_private_candidate(
            catalog(candidate, paid=[candidate["model_id"]]),
            input_bytes_sha256=SHA, max_total_tokens=12000,
            requests_needed=2, max_batch_cost_usd=Decimal("0.01"),
            source_approved_for_external_api=True,
        )
        self.assertEqual(over.blocked[0]["reason"], "BATCH_COST_CAP_EXCEEDED")

    def test_missing_rate_never_represented_as_free_or_zero(self):
        data = catalog(row("openrouter/price-unknown", "openrouter", "API_FREE_VERIFIED",
                           usd_per_1k_total_tokens=None))
        result = plan_optional_private_candidate(
            data, input_bytes_sha256=SHA, max_total_tokens=12000,
            requests_needed=2, max_batch_cost_usd=Decimal("0.05"),
            source_approved_for_external_api=True,
        )
        self.assertIsNone(result.selected)
        self.assertEqual(result.blocked[0]["reason"], "MODEL_COST_RATE_UNVERIFIED")

    def test_unsafe_catalog_rejected_without_echoing_credentials(self):
        for modified, message in (
            (row("openrouter/free-model", "openrouter", "API_FREE_VERIFIED", api_key="sensitive"),
             "SENSITIVE_FIELD_FORBIDDEN"),
            (row("openrouter/free-model", "openrouter", "API_FREE_VERIFIED", token="sensitive"),
             "SENSITIVE_FIELD_FORBIDDEN"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "catalog.json"
                path.write_text(json.dumps(catalog(modified)))
                receipt_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, message) as caught:
                    read_sanitized_catalog(path, expected_sha256=receipt_hash)
                self.assertNotIn("sensitive", str(caught.exception))

    def test_catalog_load_then_plan_no_network(self):
        data = catalog(row("local/qwen3-4b", "local", "LOCAL_ZERO_EXTERNAL"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.json"
            path.write_text(json.dumps(data))
            receipt_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(plan(read_sanitized_catalog(path, expected_sha256=receipt_hash)).selected.family, "local")
            with self.assertRaisesRegex(ValueError, "OPTIONAL_CATALOG_RECEIPT_MISMATCH"):
                read_sanitized_catalog(path, expected_sha256="0" * 64)
            with self.assertRaisesRegex(ValueError, "OPTIONAL_CATALOG_RECEIPT_REQUIRED"):
                read_sanitized_catalog(path, expected_sha256="")

    def test_unknown_family_model_duplicates_and_invalid_budget_fail_closed(self):
        valid = row("local/qwen3-4b", "local", "LOCAL_ZERO_EXTERNAL")
        for obj in (catalog(valid, valid),
                    catalog(row("bad/model", "unapproved-service", "API_FREE_VERIFIED"))):
            with self.assertRaises(ValueError):
                plan(obj)
        with self.assertRaisesRegex(ValueError, "OPTIONAL_BUDGET_INVALID"):
            plan_optional_private_candidate(
                catalog(valid), input_bytes_sha256=SHA, max_total_tokens=12000,
                requests_needed=2, max_batch_cost_usd=Decimal("NaN"),
                source_approved_for_external_api=False,
            )


if __name__ == "__main__":
    unittest.main()
