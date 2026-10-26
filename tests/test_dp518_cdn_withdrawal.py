"""DP-518C: source-event-bound CDN withdrawal and readback at the operator seam."""

import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.ops.cdn_withdrawal import (
    Probe,
    ProbeResult,
    PurgeReceipt,
    WithdrawalEvent,
    WithdrawalRunner,
    cloudflare_purge,
    http_probe,
    withdrawal_digest,
)


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


class CDNWithdrawalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = Path(self.temp.name) / "withdrawals.sqlite3"
        self.event = WithdrawalEvent(
            event_id="revocation:123", source_id="source:abc", reason_class="RIGHTS_REVOKED",
            committed_at=(datetime.now(UTC) - timedelta(seconds=3)).isoformat(),
            previous_manifest_sha256="1" * 64, safe_manifest_sha256="2" * 64,
            generation_sha256="3" * 64,
            probes=(Probe("/", sha(b"safe")), Probe("/api/v1/findings", sha(b"[]")),
                    Probe("/old-quote", None)),
        )
        self.responses = {"/": ProbeResult(200, b"safe", "MISS"),
                          "/api/v1/findings": ProbeResult(200, b"[]", "MISS"),
                          "/old-quote": ProbeResult(404, b"", "MISS")}
        self.purge_count = 0
        self.safe_fence = True

    def runner(self, *, ack="a" * 32, edge=None, origin=None):
        def purge():
            self.purge_count += 1
            if isinstance(ack, Exception):
                raise ack
            if isinstance(ack, PurgeReceipt):
                return ack
            return PurgeReceipt(200, sha(b'{"success":true}'), ack)

        return WithdrawalRunner(
            self.ledger,
            verify_current_release=lambda event: self.safe_fence,
            read_origin=origin or (lambda probe: self.responses[probe.path]),
            read_edge=edge or (lambda probe: self.responses[probe.path]),
            purge_cloudflare=purge,
        )

    def test_safely_purges_and_records_real_ack_and_readback(self):
        runner = self.runner()
        result = runner.run(self.event)
        self.assertEqual(result.status, "SAFE_READBACK")
        self.assertEqual(result.provider_ack, "a" * 32)
        self.assertEqual(result.safe_count, 3)
        self.assertIsNotNone(result.commit_to_safe_ms)
        self.assertEqual(self.purge_count, 1)
        self.assertEqual(runner.run(self.event), result)
        self.assertEqual(self.purge_count, 1)
        digest = withdrawal_digest(self.ledger)
        self.assertEqual(digest["event_count"], 1)
        self.assertEqual(digest["affected_surface_count"], 3)
        self.assertEqual(digest["ack_count"], 1)
        self.assertEqual(digest["safe_count"], 1)

    def test_successful_retry_cannot_reuse_ack_if_origin_rolled_back(self):
        self.assertEqual(self.runner().run(self.event).status, "SAFE_READBACK")
        cached_edge = dict(self.responses)
        self.responses["/api/v1/findings"] = ProbeResult(200, b"old withdrawn data", "MISS")
        attempted = self.runner(edge=lambda probe: cached_edge[probe.path]).run(self.event)
        self.assertEqual(attempted.status, "HOLD")
        self.assertEqual(attempted.reason, "ORIGIN_UNSAFE_OR_UNAVAILABLE")
        self.assertEqual(self.purge_count, 1)

    def test_immutable_attempt_receipt_records_origin_edge_http_status_and_hashes(self):
        self.runner().run(self.event)
        with sqlite3.connect(self.ledger) as db:
            receipt = db.execute("SELECT observations_json FROM attempt").fetchone()[0]
        observations = json.loads(receipt)
        self.assertEqual(len(observations), 7)
        self.assertEqual(observations[0], {
            "location": "origin", "path": "/", "status": 200, "body_sha256": sha(b"safe"),
        })
        self.assertEqual(observations[-1], {
            "location": "edge", "path": "/old-quote", "status": 404,
            "body_sha256": sha(b""),
        })
        self.assertEqual(observations[3], {
            "location": "cloudflare", "path": "purge_cache", "status": 200,
            "body_sha256": sha(b'{"success":true}'),
        })
        self.assertEqual(withdrawal_digest(self.ledger)["observed_http_status_counts"],
                         {"200": 5, "404": 2})

    def test_timeout_and_missing_ack_keep_hold_and_retry_without_false_success(self):
        runner = self.runner(ack=TimeoutError("private URL/token must not leak"))
        result = runner.run(self.event)
        self.assertEqual(result.status, "HOLD")
        self.assertEqual(result.reason, "PURGE_FAILED_OR_TIMED_OUT")
        self.assertNotIn("private", str(result))
        self.assertEqual(self.purge_count, 1)
        self.assertEqual(self.runner(ack="").run(self.event).reason, "PURGE_ACK_MISSING")
        success = self.runner().run(self.event)
        self.assertEqual(success.status, "SAFE_READBACK")
        self.assertEqual(self.purge_count, 3)
        self.assertEqual(withdrawal_digest(self.ledger)["attempt_count"], 3)

    def test_provider_503_is_journaled_without_accepting_an_ack(self):
        result = self.runner(ack=PurgeReceipt(503, sha(b"provider unavailable"), None)).run(
            self.event)
        self.assertEqual((result.status, result.reason, result.provider_ack),
                         ("HOLD", "PURGE_FAILED_OR_TIMED_OUT", None))
        with sqlite3.connect(self.ledger) as db:
            observations = json.loads(db.execute(
                "SELECT observations_json FROM attempt").fetchone()[0])
        self.assertEqual(observations[-1], {
            "location": "cloudflare", "path": "purge_cache", "status": 503,
            "body_sha256": sha(b"provider unavailable"),
        })

    def test_unsafe_origin_never_purges_and_stale_edge_cannot_be_safe(self):
        old = ProbeResult(200, b"revoked content", "HIT")
        result = self.runner(origin=lambda probe: old).run(self.event)
        self.assertEqual(result.reason, "ORIGIN_UNSAFE_OR_UNAVAILABLE")
        self.assertEqual(self.purge_count, 0)
        result = self.runner(edge=lambda probe: old).run(self.event)
        self.assertEqual(result.reason, "EDGE_UNSAFE_OR_UNAVAILABLE")
        self.assertEqual(result.status, "HOLD")
        self.assertEqual(self.purge_count, 1)

    def test_untrusted_fence_and_rollback_fail_closed(self):
        self.safe_fence = False
        held = self.runner().run(self.event)
        self.assertEqual(held.reason, "RELEASE_FENCE_UNVERIFIED")
        self.assertEqual(self.purge_count, 0)
        self.safe_fence = True
        self.assertEqual(self.runner().run(self.event).status, "SAFE_READBACK")
        from dataclasses import replace
        rollback = replace(self.event, generation_sha256="4" * 64)
        with self.assertRaisesRegex(ValueError, "EVENT_REPLAY_CONFLICT"):
            self.runner().run(rollback)

    def test_fence_changes_during_edge_readback_and_ack_does_not_clear_hold(self):
        def delayed(probe):
            self.safe_fence = False
            return self.responses[probe.path]
        result = self.runner(edge=delayed).run(self.event)
        self.assertEqual(result.reason, "RELEASE_FENCE_CHANGED")
        self.assertEqual(result.status, "HOLD")
        self.assertEqual(self.purge_count, 1)

    def test_live_http_probe_observes_status_and_actual_bytes(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/waf-safe":
                    if self.headers.get("User-Agent") != "DichiarazioniPubbliche-Readback/1.0":
                        self.send_response(403)
                        self.end_headers()
                        return
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"safe")
                    return
                if self.path == "/cache-key":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"normal edge request" if not self.headers.get("Cache-Control")
                                     else b"forced revalidation")
                    return
                if self.path == "/gone":
                    self.send_response(410)
                    self.end_headers()
                    return
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/safe")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("CF-Cache-Status", "HIT")
                self.end_headers()
                self.wfile.write(b"safe")

            def log_message(self, *_args):
                return

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                self.assertEqual(http_probe(base, Probe("/safe", sha(b"safe"))),
                                 ProbeResult(200, b"safe", "HIT"))
                self.assertEqual(http_probe(base, Probe("/gone", None)).status, 410)
                self.assertEqual(http_probe(base, Probe("/redirect", None)).status, 302)
                self.assertEqual(http_probe(base, Probe("/cache-key", sha(b"normal edge request"))).body,
                                 b"normal edge request")
                self.assertEqual(http_probe(base, Probe("/waf-safe", sha(b"safe"))).status, 200)
            finally:
                server.shutdown()
                thread.join(timeout=5)

    def test_cloudflare_api_ack_is_parsed_from_real_response_contract(self):
        class CloudflareResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                return json.dumps({"success": True, "result": {"id": "a" * 32}}).encode()

        class Adapter:
            def open(self, req, **_kwargs):
                self.req = req
                return CloudflareResponse()

        adapter = Adapter()
        with patch("dichiarazioni_pubbliche.ops.cdn_withdrawal.request.build_opener",
                   return_value=adapter):
            receipt = cloudflare_purge("c" * 32, "token-private")
        self.assertEqual(receipt.ack_id, "a" * 32)
        self.assertEqual(receipt.status, 200)
        self.assertEqual(receipt.body_sha256, sha(json.dumps(
            {"success": True, "result": {"id": "a" * 32}}
        ).encode()))
        self.assertEqual(adapter.req.get_method(), "POST")
        self.assertEqual(adapter.req.data, b'{"purge_everything":true}')
        self.assertEqual(adapter.req.get_header("Authorization"), "Bearer token-private")

    def test_invalid_cache_key_and_untrusted_url_cannot_start_work(self):
        from dataclasses import replace
        with self.assertRaisesRegex(ValueError, "EVENT_PROBES_INVALID"):
            self.runner().run(replace(self.event, probes=(Probe("//external/", None),)))
        with self.assertRaisesRegex(ValueError, "HTTP_PROBE_BASE_INVALID"):
            http_probe("http://127.0.0.1:18090/other", Probe("/", sha(b"safe")))

    def test_persisted_events_and_ack_history_reject_edits_and_deletes(self):
        self.runner().run(self.event)
        with sqlite3.connect(self.ledger) as db:
            for table in ("event", "attempt"):
                for action in ("UPDATE", "DELETE"):
                    with self.subTest(table=table, action=action):
                        if action == "UPDATE":
                            command = f"UPDATE {table} SET event_id='tampered'"
                        else:
                            command = f"DELETE FROM {table}"
                        with self.assertRaisesRegex(sqlite3.IntegrityError, "APPEND_ONLY"):
                            db.execute(command)
            self.assertEqual(db.execute("SELECT count(*) FROM attempt").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
