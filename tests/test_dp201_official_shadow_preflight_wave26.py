"""Offline, adversarial readiness checks for the official OmniRoute DP-201 shadow."""

import base64
import contextlib
import hashlib
import io
import json
import sys
import socket
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tools"))

import dp201_official_shadow_preflight_wave26 as gate  # noqa: E402


CHECKS = (
    "npm-stable-artifact",
    "github-stable-release",
    "stable-channel-convergence",
    "minimum-version",
    "stable-docker-artifact",
    "artifact-anchor",
    "required-fix-ancestry",
)


class OfficialShadowPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tarball = self.root / "omniroute-official.tgz"
        with tarfile.open(self.tarball, "w:gz") as tf:
            blob = json.dumps({"name": "omniroute", "version": "3.8.51"}).encode()
            item = tarfile.TarInfo("package/package.json")
            item.size = len(blob)
            tf.addfile(item, io.BytesIO(blob))
        digest = hashlib.sha512(self.tarball.read_bytes()).digest()
        integrity = "sha512-" + base64.b64encode(digest).decode()
        self.receipt = {
            "schema_version": 1,
            "decision": "ELIGIBLE",
            "eligible": True,
            "stable_version": "3.8.51",
            "blockers": [],
            "checks": [{"name": name, "passed": True} for name in CHECKS],
            "artifacts": {
                "npm": {"version": "3.8.51", "integrity": integrity,
                        "tarball": "https://registry.npmjs.org/omniroute/-/omniroute-3.8.51.tgz"},
                "github_release": {"tag": "v3.8.51", "draft": False, "prerelease": False},
                "docker": {"tag": "3.8.51", "digest": "sha256:" + "b" * 64},
            },
            "required_commits": sorted(gate.REQUIRED_OFFICIAL_FIX_COMMITS),
            "commit_proof": [{"contained": True, "required_commit": sha}
                             for sha in sorted(gate.REQUIRED_OFFICIAL_FIX_COMMITS)],
            "artifact_anchor": {"anchored_to_stable": True},
        }
        self.receipt_path = self.root / "official-gate.json"
        self.fixture_path = self.root / "offline-response.json"
        self.fixture = {
            "fixture_only": True,
            "response": {
                "choices": [{"message": {"content": json.dumps({"claims": [{
                    "source_timestamp": "0:00", "source_segment_indices": [0],
                    "speaker": "", "claim_type": "PRICE_STATISTIC",
                    "claim_text": "Il prezzo è 10 euro.",
                    "check_worthy": True, "numeric_sensitive": True,
                }]})}}],
            },
        }
        self.write_inputs()

    def write_inputs(self):
        self.receipt_path.write_text(json.dumps(self.receipt))
        self.fixture_path.write_text(json.dumps(self.fixture))

    def check(self, **overrides):
        options = {
            "artifact_tarball": self.tarball,
            "official_gate_receipt": self.receipt_path,
            "trusted_gate_sha256": hashlib.sha256(self.receipt_path.read_bytes()).hexdigest(),
            "offline_fixture": self.fixture_path,
            "max_usd_per_1k_total_tokens": "0.01",
            "approved_max_cost_usd": "0.10",
        }
        options.update(overrides)
        return gate.verify_offline_shadow_readiness(**options)

    def assertBlocked(self, code, **overrides):
        with self.assertRaises(gate.PreflightBlocked) as caught:
            self.check(**overrides)
        self.assertEqual(caught.exception.code, code)

    def test_pinned_3851_with_meaningful_offline_contract_is_ready_only_for_review(self):
        report = self.check()
        self.assertEqual(report["status"], "OFFLINE_READY_FOR_OPERATOR_REVIEW")
        self.assertEqual(report["artifact_version"], "3.8.51")
        self.assertEqual(report["planned_model_calls_preflighted"], 2)
        self.assertEqual(report["probe_max_output_tokens"], 256)
        self.assertEqual(report["extraction_max_output_tokens"], 2048)
        self.assertEqual(report["claim_count_in_fixture"], 1)
        self.assertGreater(float(report["estimated_max_cost_usd"]), 0)
        self.assertFalse(report["live_canary_executed"])
        self.assertFalse(report["paid_call_authorized"])
        self.assertNotIn("claims", json.dumps(report))
        self.assertNotIn("Il prezzo", json.dumps(report))

    def test_mutated_tarball_cannot_pass_release_integrity(self):
        with self.tarball.open("ab") as out:
            out.write(b"tampered")
        self.assertBlocked("ARTIFACT_INTEGRITY_MISMATCH")

    def test_untrusted_modified_release_receipt_fails_independent_pin(self):
        pinned = hashlib.sha256(self.receipt_path.read_bytes()).hexdigest()
        self.receipt["stable_version"] = "3.8.52"
        self.write_inputs()
        self.assertBlocked("RELEASE_RECEIPT_HASH_MISMATCH", trusted_gate_sha256=pinned)

    def test_rejects_local_fork_and_unapproved_new_official_version(self):
        self.receipt["stable_version"] = "3.8.50"
        self.write_inputs()
        self.assertBlocked("OFFICIAL_VERSION_NOT_ALLOWED")
        self.receipt["stable_version"] = "3.8.52"
        self.write_inputs()
        self.assertBlocked("OFFICIAL_VERSION_NOT_ALLOWED")
        self.receipt["stable_version"] = "3.8.51"
        self.receipt["eligible"] = False
        self.write_inputs()
        self.assertBlocked("OFFICIAL_RELEASE_GATE_NOT_ELIGIBLE")

    def test_rejects_missing_stable_channel_or_fix_ancestry(self):
        self.receipt["checks"][6]["passed"] = False
        self.write_inputs()
        self.assertBlocked("OFFICIAL_RELEASE_GATE_NOT_ELIGIBLE")
        self.receipt["checks"][6]["passed"] = True
        self.receipt["artifacts"]["docker"]["digest"] = None
        self.write_inputs()
        self.assertBlocked("OFFICIAL_RELEASE_PROVENANCE_INCOMPLETE")

    def test_no_zero_missing_or_negative_paid_call_budget(self):
        for rate, cap in (("0", "0.05"), ("0.01", "0"), ("-1", "0.05"),
                          ("NaN", "0.05"), ("0.01", "-0.05"), ("", "0.05")):
            with self.subTest(rate=rate, cap=cap):
                self.assertBlocked("EXPLICIT_POSITIVE_COST_REQUIRED",
                                   max_usd_per_1k_total_tokens=rate,
                                   approved_max_cost_usd=cap)

    def test_budget_must_cover_full_conservative_request_estimate(self):
        self.assertBlocked("ESTIMATED_COST_EXCEEDS_APPROVED_CAP",
                           max_usd_per_1k_total_tokens="10", approved_max_cost_usd="0.05")
        self.assertBlocked("APPROVED_CAP_EXCEEDS_WORKER_JOB_LIMIT",
                           approved_max_cost_usd="0.30")

    def test_fixture_fails_closed_for_made_up_claim_or_invalid_schema(self):
        self.fixture["response"]["choices"][0]["message"]["content"] = json.dumps({
            "claims": [{"source_segment_indices": [7], "claim_type": "PRICE_STATISTIC",
                        "claim_text": "Il prezzo è 99 euro.", "check_worthy": True,
                        "numeric_sensitive": True}]})
        self.write_inputs()
        self.assertBlocked("OFFLINE_RESPONSE_SCHEMA_INVALID")

    def test_fixture_is_not_a_fake_live_provider_receipt(self):
        self.fixture["fixture_only"] = False
        self.write_inputs()
        self.assertBlocked("OFFLINE_FIXTURE_REQUIRED")

    def test_rejects_runtime_request_tools_and_model_substitution(self):
        request = gate.build_intended_request()
        gate.validate_intended_request(request)
        request["tools"] = [{"type": "function"}]
        with self.assertRaises(gate.PreflightBlocked) as caught:
            gate.validate_intended_request(request)
        self.assertEqual(caught.exception.code, "INTENDED_REQUEST_SCHEMA_INVALID")
        request = gate.build_intended_request()
        request["model"] = "antigravity/gemini-3.8-flash"
        with self.assertRaises(gate.PreflightBlocked):
            gate.validate_intended_request(request)

    def test_offline_requests_match_actual_probe_and_extract_without_network(self):
        from dichiarazioni_pubbliche.claim_runtime import OmniRouteClaimClient

        expected_probe = gate.build_intended_request()
        expected_extraction = gate.build_intended_request(extraction=True)
        called = []

        def local_reply(_self, prompt, *, max_tokens):
            called.append((prompt, max_tokens))
            return self.fixture["response"], 0.0

        client = OmniRouteClaimClient(api_key="")
        with patch.object(OmniRouteClaimClient, "_post", local_reply):
            self.assertTrue(client.probe().healthy)
            self.assertEqual(len(client.extract(window_text=gate.SAMPLE,
                                               allowed_segment_indices=(0,)).claims), 1)
        self.assertEqual(called, [
            (expected_probe["messages"][0]["content"], expected_probe["max_tokens"]),
            (expected_extraction["messages"][0]["content"], expected_extraction["max_tokens"]),
        ])

    def test_bundled_offline_fixture_stays_usable(self):
        self.assertEqual(
            gate._validate_offline_fixture(ROOT / "tests/fixtures/dp201-shadow-response-wave26.json"), 1
        )

    def test_cli_never_opens_network_or_prints_fixture_or_request(self):
        stdout = io.StringIO()
        args = [
            "--artifact-tgz", str(self.tarball),
            "--official-gate-receipt", str(self.receipt_path),
            "--trusted-gate-sha256", hashlib.sha256(self.receipt_path.read_bytes()).hexdigest(),
            "--offline-fixture", str(self.fixture_path),
            "--max-usd-per-1k-total-tokens", "0.01",
            "--approved-max-cost-usd", "0.10",
        ]
        with patch.object(socket, "socket", side_effect=AssertionError("NETWORK_FORBIDDEN")):
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(gate.main(args), 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "OFFLINE_READY_FOR_OPERATOR_REVIEW")
        self.assertFalse(result["paid_call_authorized"])
        self.assertNotIn("10 euro", stdout.getvalue())
        self.assertNotIn("TRANSCRIPT WINDOW", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
