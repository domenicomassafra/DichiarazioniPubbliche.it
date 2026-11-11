"""#704/#468: a challenged v3 Statement fenced until a new release replaces it."""

import http.client
import json
import sys
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.live_correction_http import build_live_correction_server  # noqa: E402
from dichiarazioni_pubbliche.public_statement_authority import PublicStatementChallengeStore  # noqa: E402
from dp468_authority_support import MemoryPostgres  # noqa: E402
from tests.test_dp437_public_opinion_api import ReviewedSyntheticOpinions  # noqa: E402
from tests.test_dp466_live_correction import FakeLedger, LiveCorrectionHttpTests  # noqa: E402


class StatementV3CorrectionIntakeTests(unittest.TestCase):
    """Reuse the v2 correction fixture, then opt into the v3 release authority."""

    setUp = LiveCorrectionHttpTests.setUp
    tearDown = LiveCorrectionHttpTests.tearDown
    request = LiveCorrectionHttpTests.request
    auth_headers = LiveCorrectionHttpTests.auth_headers

    def test_statement_v3_intake_holds_exact_version_and_allows_only_a_new_pinned_version(self):
        root = Path(self.temp.name)
        source = ReviewedSyntheticOpinions()
        v3 = source.build()
        candidate = root / "statement-correction-v3.json"
        current = root / "statement-correction-v3-sha256"
        candidate.write_text(json.dumps(v3), encoding="utf-8")
        current.write_text(v3["dataset_sha256"] + "\n", encoding="ascii")
        statement_db = MemoryPostgres()
        statement_store = PublicStatementChallengeStore(store=statement_db)
        purges = []
        jobs = []
        service = self.server.RequestHandlerClass.account_service

        def purge_with_origin_readback(target):
            connection = http.client.HTTPConnection("127.0.0.1", private.server_port, timeout=0.5)
            try:
                connection.request("GET", "/api/v3/statements", headers={
                    "Host": "dichiarazionipubbliche.it",
                })
                response = connection.getresponse()
                status, cache = response.status, response.getheader("Cache-Control", "")
                response.read()
            finally:
                connection.close()
            if status != 503 or "no-store" not in cache:
                return False
            purges.append(target)
            return True

        private = build_live_correction_server(
            str(root / "projection.json"), host="127.0.0.1", port=0,
            static_dir=str(root / "static"), account_service=service,
            correction_ledger=FakeLedger(),
            correction_enqueue=lambda *args: jobs.append(args) or True,
            correction_purge=purge_with_origin_readback,
            correction_reserve=lambda *_: True,
            statement_projection_path=candidate,
            statement_current_fingerprint_path=current,
            statement_challenge_store=statement_store,
        )
        thread = threading.Thread(target=private.serve_forever, daemon=True)
        thread.start()
        original_port = self.port
        self.port = private.server_port
        payload = {
            "statement_id": "statement:1",
            "version_id": "statement-version:1",
            "reason": "La citazione non corrisponde alla fonte",
        }
        try:
            self.assertEqual(self.request("GET", "/api/v3/statements")[0], 200)
            self.assertEqual(self.request("GET", "/")[0], 200)
            status, _, receipt = self.request(
                "POST", "/intake/corrections", payload, self.auth_headers(),
            )
            self.assertEqual(status, 202)
            request_id = receipt["request_id"]
            self.assertTrue(request_id.startswith("public-statement-challenge-request:"))
            self.assertEqual(receipt["state"], "HOLD")
            self.assertEqual(purges, ["statement-v3:statement:1"])
            self.assertTrue(statement_store.current_hold("statement:1", "statement-version:1"))
            self.assertEqual(self.request("GET", "/api/v3/statements")[0], 503)
            self.assertEqual(self.request("GET", "/api/v3/statements/statement:1")[0], 503)
            self.assertEqual(self.request("GET", "/")[0], 503)
            self.assertEqual(self.request("GET", "/segnalazioni/")[0], 200)

            status, _, state = self.request(
                "GET", "/intake/corrections/" + request_id, headers=self.auth_headers(),
            )
            self.assertEqual(status, 200)
            self.assertEqual(state["state"], "HOLD")
            other = self.auth_headers() | {"Cookie": "__Host-dp-session=other-session"}
            self.assertEqual(self.request(
                "GET", "/intake/corrections/" + request_id, headers=other,
            )[0], 404)

            status, _, replay = self.request(
                "POST", "/intake/corrections", payload, self.auth_headers(),
            )
            self.assertEqual(status, 202)
            self.assertEqual(replay["request_id"], request_id)
            self.assertEqual(len(statement_db.challenge_requests), 1)
            self.assertEqual(len(statement_db.challenge_events), 1)
            self.assertEqual(len(purges), 2)
            self.assertEqual(jobs, [])
            self.assertEqual(self.request(
                "POST", "/intake/corrections", payload, other,
            )[0], 409)
            self.assertEqual(len(purges), 2)
            self.assertEqual(self.request(
                "POST", "/intake/corrections",
                payload | {"version_id": "statement-version:stale"},
                self.auth_headers(),
            )[0], 404)

            reviewed_at = datetime.now(timezone.utc).replace(microsecond=0)
            statement_store.append_event(
                request_id=request_id, status="TRIAGED", reason_code="REVIEW_STARTED",
                actor_ref="reviewer:one",
                occurred_at=(reviewed_at + timedelta(minutes=1)).isoformat(),
            )
            statement_store.append_event(
                request_id=request_id, status="CORRECTED", reason_code="NEW_VERSION_REQUIRED",
                actor_ref="reviewer:two",
                occurred_at=(reviewed_at + timedelta(minutes=2)).isoformat(),
            )
            self.assertEqual(self.request("GET", "/")[0], 503)

            source.subjects[0].row["version_id"] = "statement-version:1-corrected"
            for proof in source.subjects[0].gates.values():
                proof["version_id"] = "statement-version:1-corrected"
            corrected = source.build()
            candidate.write_text(json.dumps(corrected), encoding="utf-8")
            current.write_text(corrected["dataset_sha256"] + "\n", encoding="ascii")
            self.assertEqual(self.request("GET", "/")[0], 200)
            status, _, detail = self.request("GET", "/api/v3/statements/statement:1")
            self.assertEqual(status, 200)
            self.assertEqual(detail["data"]["version_id"], "statement-version:1-corrected")
            status, _, old_state = self.request(
                "GET", "/intake/corrections/" + request_id, headers=self.auth_headers(),
            )
            self.assertEqual(status, 200)
            self.assertEqual(old_state["state"], "HOLD")
            inventory = statement_store.public_release_clear
            statement_store.public_release_clear = lambda *args, **kwargs: None
            self.assertEqual(self.request("GET", "/")[0], 503)
            statement_store.public_release_clear = inventory
            self.assertEqual(self.request("GET", "/")[0], 200)
        finally:
            self.port = original_port
            private.shutdown()
            private.server_close()
            thread.join(timeout=5)

    def test_v3_release_cannot_be_opted_in_without_statement_challenge_store(self):
        root = Path(self.temp.name)
        v3 = ReviewedSyntheticOpinions().build()
        candidate = root / "unbacked-v3.json"
        current = root / "unbacked-v3-sha256"
        candidate.write_text(json.dumps(v3), encoding="utf-8")
        current.write_text(v3["dataset_sha256"] + "\n", encoding="ascii")
        with self.assertRaisesRegex(ValueError, "STATEMENT_CORRECTION_RELEASE_AND_LEDGER_REQUIRED"):
            build_live_correction_server(
                str(root / "projection.json"), host="127.0.0.1", port=0,
                static_dir=str(root / "static"),
                account_service=self.server.RequestHandlerClass.account_service,
                correction_ledger=FakeLedger(), correction_enqueue=lambda *_: True,
                correction_purge=lambda *_: True, correction_reserve=lambda *_: True,
                statement_projection_path=candidate,
                statement_current_fingerprint_path=current,
            )


if __name__ == "__main__":
    unittest.main()
