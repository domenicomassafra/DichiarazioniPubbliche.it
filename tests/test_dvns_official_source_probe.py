"""Official-data DP-234 technical canary: read-only HTTPS, held rights, replay."""

import io
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.dvns_official_source_probe import (  # noqa: E402
    DvnsOfficialProbeError,
    _DenyRedirect,
    _fetch_official_archive,
    acquire_senato_official_candidate,
    read_back_senato_official_candidate,
    verify_senato_official_readback,
)
from dichiarazioni_pubbliche.senato_open_data_sedute import DATASET_URL  # noqa: E402
from tests.test_senato_open_data_sedute import SOURCE_ROWS, archive  # noqa: E402


class Response(io.BytesIO):
    status = 200

    def __init__(self, raw, *, location=DATASET_URL, headers=None):
        super().__init__(raw)
        self.location = location
        self.headers = headers or {
            "Content-Length": str(len(raw)), "Content-Type": "application/zip"
        }

    def geturl(self):
        return self.location


class Transport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request.full_url, timeout, request.get_method()))
        return self.response


class DvnsOfficialSourceProbeTests(unittest.TestCase):
    def test_real_rdf_shape_enters_dp215_held_rights_and_replays_from_source(self):
        raw = archive()
        transport = Transport(Response(raw))
        with mock.patch(
            "dichiarazioni_pubbliche.dvns_official_source_probe._live_utc",
            return_value="2026-10-10T15:30:00Z",
        ):
            first = acquire_senato_official_candidate(opener=transport)
        second = verify_senato_official_readback(raw, expected=first)
        self.assertEqual(first, second)
        self.assertEqual(first.imported_records, 2)
        self.assertEqual(first.candidate_state, "HELD")
        self.assertIn("DVNS_RIGHTS_BLOCKED", first.blocking_reasons)
        self.assertEqual(first.rights_gate, "BLOCKED_PENDING_PROJECT_SOURCE_PROFILE_REVIEW")
        self.assertEqual(first.dataset_url, DATASET_URL)
        self.assertEqual(first.source_version, "sha256:" + first.source_sha256)
        self.assertEqual(transport.calls, [(DATASET_URL, 15, "GET")])
        self.assertNotIn("raw", asdict(first))
        self.assertNotIn("PUBLISH", str(asdict(first)))

    def test_fetched_source_must_match_exact_pinned_url_type_length_and_size(self):
        raw = archive()
        cases = (
            (Response(raw, location="https://untrusted.example/archive.zip"), "RESPONSE_UNEXPECTED"),
            (Response(raw, headers={"Content-Length": "900000", "Content-Type": "application/zip"}), "LENGTH_INVALID"),
            (Response(raw, headers={"Content-Length": str(len(raw) + 1), "Content-Type": "application/zip"}), "LENGTH_MISMATCH"),
            (Response(raw, headers={"Content-Length": "banana", "Content-Type": "application/zip"}), "LENGTH_INVALID"),
            (Response(raw, headers={"Content-Type": "text/html"}), "CONTENT_TYPE_INVALID"),
            (Response(b"a" * 512_001, headers={"Content-Type": "application/zip"}), "SIZE_INVALID"),
        )
        for response, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(
                DvnsOfficialProbeError, "DVNS_OFFICIAL_" + code,
            ):
                _fetch_official_archive(opener=Transport(response))

    def test_redirect_refused_and_network_errors_do_not_become_empty_success(self):
        with self.assertRaisesRegex(DvnsOfficialProbeError, "REDIRECT_REFUSED"):
            _DenyRedirect().redirect_request(None, None, 302, "redirect", {}, "https://example.test")
        transport = mock.Mock()
        transport.open.side_effect = TimeoutError("private upstream text")
        with self.assertRaisesRegex(
            DvnsOfficialProbeError, "^DVNS_OFFICIAL_UNAVAILABLE$"
        ) as caught:
            acquire_senato_official_candidate(opener=transport)
        self.assertNotIn("private upstream", str(caught.exception))

    def test_mutated_source_bytes_fail_independent_cross_host_receipt(self):
        raw = archive()
        original = read_back_senato_official_candidate(
            raw, observed_at_utc="2026-10-10T15:30:00Z",
        )
        other = archive(SOURCE_ROWS.replace(
            ">2</osr:numeroSeduta>", ">3</osr:numeroSeduta>"
        ))
        changed = read_back_senato_official_candidate(
            other, observed_at_utc=original.observed_at_utc,
        )
        self.assertNotEqual(original.source_sha256, changed.source_sha256)
        self.assertNotEqual(original.dvns_replay_id, changed.dvns_replay_id)
        self.assertEqual(changed.candidate_state, "HELD")
        with self.assertRaisesRegex(DvnsOfficialProbeError, "RECEIPT_MISMATCH"):
            verify_senato_official_readback(other, expected=original)


if __name__ == "__main__":
    unittest.main()
