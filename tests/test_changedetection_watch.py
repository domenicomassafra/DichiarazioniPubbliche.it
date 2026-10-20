"""#172: isolated changedetection.io -> DP-515 durable admission contract."""

import hashlib
import json
import sqlite3
import sys
import threading
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.changedetection_watch import (  # noqa: E402
    ChangedetectionBinding, ChangedetectionError, ChangedetectionSnapshot,
    poll_changedetection_watch, read_changedetection_snapshot,
)
from dichiarazioni_pubbliche.incremental_source_watch import (  # noqa: E402
    WatchPolicy, WatchReadiness, WatchState, policy_fingerprint,
)
from dichiarazioni_pubbliche.source_watch_store_v1 import LocalSourceWatchStore  # noqa: E402


T0 = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
UUID = "da4d01d4-e39f-4ed5-8d0c-a9b542843f9a"
URL = "https://example.org/official/no-feed.html"


def source():
    return ChangedetectionBinding(
        source_id="official:web:no-feed", locator_id="cdio:" + UUID,
        canonical_url=URL, watch_uuid=UUID,
    )


def policy():
    b = source()
    return WatchPolicy(
        source_id=b.source_id, locator_id=b.locator_id,
        source_family="WEB_NO_FEED", corpus_id="pilot:synthetic",
        corpus_cutoff="2026-10-19", policy_revision="operator-approved-r1",
        enabled=True, base_backoff_seconds=10, max_backoff_seconds=120,
    )


def gate(p, **changes):
    fields = dict(
        source_id=p.source_id, corpus_id=p.corpus_id,
        policy_fingerprint=policy_fingerprint(p),
        rights_status="READY", rights_receipt="rights:synthetic",
        capability_status="READY", capability_receipt="service:fixture",
        budget_status="READY", budget_receipt="budget:synthetic",
        remaining_children=1,
    )
    fields.update(changes)
    return WatchReadiness(**fields)


def provider(content=b"official page v1", *, seconds=0, history="1792490400", **changes):
    watch = dict(
        uuid=UUID, url=URL, link=URL,
        last_checked=(T0 + timedelta(seconds=seconds)).timestamp(),
        last_error=False,
    )
    watch.update(changes)
    return ChangedetectionSnapshot(watch, {history: "snapshot"}, content)


class ChangedetectionWatchTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.store = LocalSourceWatchStore(self.db)
        self.store.init_isolated_fixture_schema()
        self.policy = policy()
        self.binding = source()
        self.store.register_fixture_source(
            self.policy, WatchState(source_id=self.policy.source_id), gate(self.policy),
        )

    def poll(self, snapshot, n=0, attempt="tick-1"):
        return poll_changedetection_watch(
            self.store, self.policy, self.binding, attempt_id=attempt,
            attempted_at=T0 + timedelta(seconds=n),
            observed_at=T0 + timedelta(seconds=n + 2), snapshot=snapshot,
        )

    def test_change_no_change_new_change_and_durable_dedupe(self):
        first, first_receipt = self.poll(provider())
        self.assertTrue(first.allowed)
        self.assertEqual(first_receipt.disposition, "CHANGED")
        self.assertEqual(first_receipt.source_id, self.policy.source_id)
        self.assertEqual(first_receipt.watch_uuid, UUID)
        self.assertEqual(first_receipt.content_sha256, hashlib.sha256(b"official page v1").hexdigest())
        self.assertEqual(len(self.store.private_proposals(self.policy.source_id)), 1)

        _, duplicate = self.poll(provider(seconds=30, history="1792490430"), 30, "tick-2")
        self.assertEqual(duplicate.disposition, "UNCHANGED")
        self.assertEqual(len(self.store.private_proposals(self.policy.source_id)), 1)

        _, edited = self.poll(provider(b"official page v2", seconds=60,
                                       history="1792490460"), 60, "tick-3")
        self.assertEqual(edited.disposition, "CHANGED")
        self.assertEqual(len(self.store.private_proposals(self.policy.source_id)), 2)
        self.assertEqual(self.store.committed_attempt_count(self.policy.source_id), 3)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM dp515_watch_attempt").fetchone()[0], 3)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM dp515_watch_proposal").fetchone()[0], 2)
        self.assertEqual(self.store.read_state(self.policy.source_id).last_successful_observed_at,
                         T0 + timedelta(seconds=62))

    def test_source_mismatch_and_old_or_failed_check_fail_closed(self):
        for invalid in (
            provider(url="https://other.invalid/"),
            provider(last_error="fetch failed"),
            provider(seconds=-800),
            provider(content=b"", seconds=0),
        ):
            with self.subTest(invalid=invalid):
                self.setUp_for_case()
                _, receipt = self.poll(invalid)
                self.assertEqual(receipt.disposition, "UNAVAILABLE")
                self.assertEqual(receipt.reason, "HTTP_503")
                self.assertEqual(self.store.private_proposals(self.policy.source_id), ())
                self.assertGreater(self.store.read_state(self.policy.source_id).retry_not_before, T0)

    def test_cached_provider_result_does_not_invent_new_freshness(self):
        self.poll(provider())
        _, stale = self.poll(provider(seconds=0), 30, "tick-cached")
        self.assertEqual(stale.disposition, "UNAVAILABLE")
        self.assertEqual(stale.reason, "HTTP_503")
        self.assertEqual(self.store.read_state(self.policy.source_id).last_successful_observed_at,
                         T0 + timedelta(seconds=2))
        self.assertEqual(len(self.store.private_proposals(self.policy.source_id)), 1)

    def setUp_for_case(self):
        # Each bad observation gets a new isolated durable fixture.
        self.db.close()
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.store = LocalSourceWatchStore(self.db)
        self.store.init_isolated_fixture_schema()
        self.store.register_fixture_source(
            self.policy, WatchState(source_id=self.policy.source_id), gate(self.policy),
        )

    def test_rights_budget_and_disabled_profiles_prevent_provider_calls(self):
        for changes in (
            dict(rights_status="REVOKED"),
            dict(budget_status="CAPPED"),
            dict(capability_status="ABSENT"),
        ):
            with self.subTest(changes=changes):
                self.setUp_for_case()
                self.store.update_fixture_readiness(gate(self.policy, **changes), expected_gate_revision=0)
                with patch("dichiarazioni_pubbliche.changedetection_watch.read_changedetection_snapshot",
                           side_effect=AssertionError("Provider read forbidden")) as network:
                    plan, receipt = poll_changedetection_watch(
                        self.store, self.policy, self.binding, attempt_id="held",
                        attempted_at=T0, observed_at=T0 + timedelta(seconds=2),
                        api_key="fixture-only",
                    )
                self.assertFalse(plan.allowed)
                self.assertIsNone(receipt)
                network.assert_not_called()
                self.assertEqual(self.store.committed_attempt_count(self.policy.source_id), 0)
        with self.assertRaisesRegex(ChangedetectionError, "NO_FEED_PROFILE_NOT_AUTHORIZED"):
            poll_changedetection_watch(
                self.store, replace(self.policy, source_family="OFFICIAL_RSS"), self.binding,
                attempt_id="feed-misroute", attempted_at=T0,
                observed_at=T0 + timedelta(seconds=2), snapshot=provider(),
            )

        disabled = replace(self.policy, enabled=False)
        self.db.close()
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.store = LocalSourceWatchStore(self.db)
        self.store.init_isolated_fixture_schema()
        self.store.register_fixture_source(disabled, WatchState(source_id=disabled.source_id), gate(disabled))
        with patch("dichiarazioni_pubbliche.changedetection_watch.read_changedetection_snapshot",
                   side_effect=AssertionError("Provider read forbidden")):
            plan, receipt = poll_changedetection_watch(
                self.store, disabled, self.binding, attempt_id="disabled",
                attempted_at=T0, observed_at=T0 + timedelta(seconds=2), api_key="fixture-only",
            )
        self.assertEqual(plan.reason, "WATCH_DISABLED")
        self.assertIsNone(receipt)

    def test_provider_token_never_sent_to_remote_host(self):
        remote = replace(self.binding, api_base="https://evil.example:443")
        with patch("dichiarazioni_pubbliche.changedetection_watch.request.build_opener",
                   side_effect=AssertionError("Network not allowed")) as client:
            with self.assertRaisesRegex(ChangedetectionError, "API_MUST_BE_LOOPBACK"):
                read_changedetection_snapshot(remote, api_key="private-synthetic-key")
            client.assert_not_called()

    def test_smoke_synthetic_no_real_source_access(self):
        with patch("dichiarazioni_pubbliche.changedetection_watch.read_changedetection_snapshot",
                   side_effect=AssertionError("Synthetic test accessed provider")):
            _, receipt = self.poll(provider(b"synthetic v1"))
        self.assertEqual(receipt.disposition, "CHANGED")
        self.assertEqual(receipt.upstream_release_reference, "0.60.9")
        self.assertEqual(len(receipt.receipt_sha256), 64)
        self.assertIsNone(receipt.measured_cost_micro_eur)

    def test_smoke_authenticated_loopback_api_without_external_fetch(self):
        paths = []

        class FakeProvider(BaseHTTPRequestHandler):
            def do_GET(self):
                paths.append(self.path)
                if self.headers.get("x-api-key") != "synthetic-token":
                    self.send_error(403)
                    return
                base = "/api/v1/watch/" + UUID
                if self.path == base:
                    content = json.dumps(provider().watch).encode()
                elif self.path == base + "/history":
                    content = json.dumps(provider().history).encode()
                elif self.path == base + "/history/latest":
                    content = b"official page v1"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, format, *args):
                pass  # Test-only HTTP server; no credentials or content logged.

        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeProvider)
        self.addCleanup(server.server_close)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            binding = replace(self.binding, api_base=f"http://127.0.0.1:{server.server_port}")
            # A host-level HTTP proxy must not receive the loopback API token,
            # even when system NO_PROXY settings have been overridden.
            with patch("urllib.request.getproxies", return_value={"http": "http://127.0.0.1:9"}), \
                 patch("urllib.request.proxy_bypass", return_value=False):
                _, receipt = poll_changedetection_watch(
                    self.store, self.policy, binding,
                    attempt_id="loopback", attempted_at=T0,
                    observed_at=T0 + timedelta(seconds=2), api_key="synthetic-token",
                )
            self.assertEqual(receipt.disposition, "CHANGED")
            self.assertEqual(paths, [
                "/api/v1/watch/" + UUID,
                "/api/v1/watch/" + UUID + "/history",
                "/api/v1/watch/" + UUID + "/history/latest",
            ])
            self.assertEqual(len(self.store.private_proposals(self.policy.source_id)), 1)
        finally:
            server.shutdown()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
