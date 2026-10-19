"""Observed source recovery: bounded real-source adapter and private Studio readback."""

from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.original_source_observation_v1 import (  # noqa: E402
    LocalObservedRecoveryJournal,
)
from dichiarazioni_pubbliche.studio_local_api import (  # noqa: E402
    StudioLocalReaders, StudioLoopbackServer,
)
from tools.dp241_nasa_observed_pilot import (  # noqa: E402
    CASE_ID, LONG_URI, MEDIA_RIGHTS_URI, RAW_RIGHTS_URI, SHORT_URI, observe,
)

_SHORT = (b"Neil: I'm going to step off the LM now. That's one small step for a man, "
          b"one giant leap for mankind.")
_LONG = (b"<html><body>04 13 24 48 CDR THAT'S ONE SMALL STEP FOR (A) MAN, "
         b"ONE GIANT LEAP FOR MANKIND. 04 13 24 48 CDR And the - the surface is "
         b"fine and powdery. I can pick it up loosely with my toe.</body></html>")


def responses(short=_SHORT, long=_LONG):
    return {
        SHORT_URI: (short, SHORT_URI), LONG_URI: (long, LONG_URI),
        MEDIA_RIGHTS_URI: (b"NASA video clips in the public domain", MEDIA_RIGHTS_URI),
        RAW_RIGHTS_URI: (b"NASA raw original transcript: no copyright is asserted", RAW_RIGHTS_URI),
    }


class ObservedSourceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dp241-observed-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private"

    def run_pilot(self, fixture=None, *, recheck=False):
        expected = fixture or responses()
        with patch("tools.dp241_nasa_observed_pilot.fetch", side_effect=lambda u: expected[u]) as get, \
             patch("tools.dp241_nasa_observed_pilot.probe_media", return_value=3543382):
            receipt = observe(self.root, recheck=recheck)
        return receipt, get.call_count

    def test_two_distinct_observed_methods_and_same_lineage_stay_held(self):
        receipt, count = self.run_pilot()
        self.assertEqual(count, 4)  # two sources + two independent rights-page reads
        record = receipt["record"]
        self.assertEqual(receipt["history_count"], 1)
        self.assertEqual(record["status"], "HELD_FOR_REVIEW")
        self.assertEqual(record["spent_usd"], "0")
        self.assertEqual(record["attempt_cap"], 2)
        self.assertEqual(record["root_lineage"], "NASA_APOLLO_11_SINGLE_ROOT")
        self.assertEqual({row["method_family"] for row in record["attempts"]},
                         {"ORIGINAL_PUBLISHER", "OFFICIAL_RECORD"})
        self.assertEqual(record["attempts"][1]["result"], "CONTEXT_LOCATED_HELD")
        self.assertTrue(record["reanalysis_required"])
        for key in ("rights_clearance", "review_authority", "publication_authority",
                    "external_receipts_independently_verified"):
            self.assertIs(record[key], False)
        self.assertTrue(record["timeline_snapshot_id"].startswith("original-source-timeline:"))
        self.assertNotIn("fine and powdery", json.dumps(record))
        self.assertNotIn("one giant leap", json.dumps(record))

    def test_identical_replay_never_refetches_and_changed_version_holds_history(self):
        original, _ = self.run_pilot()
        with patch("tools.dp241_nasa_observed_pilot.fetch", side_effect=AssertionError("refetched")):
            replay = observe(self.root)
        self.assertEqual(replay["snapshot_id"], original["snapshot_id"])
        same, count = self.run_pilot(recheck=True)
        self.assertEqual(count, 4)
        self.assertEqual(same["snapshot_id"], original["snapshot_id"])
        changed, _ = self.run_pilot(responses(short=b"Official clip revised: " + _SHORT), recheck=True)
        self.assertEqual(changed["history_count"], 2)
        self.assertEqual(changed["record"]["status"], "SOURCE_STALE")
        self.assertEqual(changed["record"]["next_action"], "DP511_SOURCE_REVALIDATION")
        self.assertEqual({row["record"]["status"] for row in
                          LocalObservedRecoveryJournal(self.root).history(CASE_ID)},
                         {"SOURCE_STALE", "HELD_FOR_REVIEW"})

    def test_journal_refuses_tampering_unsafe_permissions_and_invalid_source_ids(self):
        receipt, _ = self.run_pilot()
        journal = LocalObservedRecoveryJournal(self.root)
        altered = deepcopy(receipt["record"])
        altered["attempts"][1]["attempt_id"] = altered["attempts"][0]["attempt_id"]
        with self.assertRaisesRegex(ValueError, "METHOD"):
            journal.append(altered)
        altered = deepcopy(receipt["record"])
        altered["publication_authority"] = True
        with self.assertRaisesRegex(ValueError, "AUTHORITY"):
            journal.append(altered)
        with self.assertRaisesRegex(ValueError, "CASE_INVALID"):
            journal.read("../secret")
        case_dir = self.root / CASE_ID
        file = next(case_dir.glob("*.json"))
        data = file.read_bytes().replace(b"HELD_FOR_REVIEW", b"SOURCE_STALE")
        file.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "TAMPERED"):
            journal.read(CASE_ID)
        os.chmod(self.root, 0o755)
        with self.assertRaisesRegex(ValueError, "ROOT_UNSAFE"):
            LocalObservedRecoveryJournal(self.root)

    def test_studio_loopback_requires_auth_and_displays_exact_private_attempts(self):
        receipt, _ = self.run_pilot()
        token = "a" * 64
        readers = StudioLocalReaders(None, None, None,
                                     recovery_observations=LocalObservedRecoveryJournal(self.root))
        with StudioLoopbackServer(0, readers, token) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(lambda: (server.shutdown(), thread.join(timeout=3)))
            page_client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            page_client.request("GET", "/")
            page = page_client.getresponse()
            html = page.read().decode("utf-8")
            self.assertEqual(page.status, 200)
            self.assertIn('data-panel="recovery"', html)
            self.assertIn('data-endpoint="/v1/recovery/observed"', html)
            page_client.close()
            def request(body, *, authorized):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                headers = {"Content-Type": "application/json"}
                if authorized:
                    headers["Authorization"] = "Bearer " + token
                connection.request("POST", "/v1/recovery/observed", json.dumps(body), headers)
                response = connection.getresponse()
                result = response.status, json.loads(response.read())
                connection.close()
                return result
            self.assertEqual(request({"case_id": CASE_ID}, authorized=False)[0], 401)
            status, result = request({"case_id": CASE_ID}, authorized=True)
            self.assertEqual(status, 200, result)
            self.assertEqual(result["data"]["snapshot_id"], receipt["snapshot_id"])
            self.assertEqual(result["data"]["record"]["attempt_cap"], 2)
            self.assertEqual(result["data"]["record"]["exception_question"],
                             receipt["record"]["exception_question"])
            self.assertFalse(result["data"]["publication_authority"])
            self.assertEqual(request({"case_id": "../../x"}, authorized=True)[0], 422)
            self.assertEqual(request({"case_id": CASE_ID, "publish": True}, authorized=True)[0], 422)


if __name__ == "__main__":
    unittest.main()
