"""DP-437 opt-in Person/Content opinion reader; synthetic approved sources only.

The current public HTTP site and public-v2 writer are NEVER exercised here.
"""
from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.public_api import (  # noqa: E402
    PublicApiError, get_public_statement_v3,
    list_public_opinions_by_person_content_v3,
)
from dichiarazioni_pubbliche.public_projection import build_public_projection  # noqa: E402
from test_dp435_public_statement_seam import (  # noqa: E402
    IsolatedStatementSource, QUOTE, SHA, SOURCE, STAMP,
)
from test_dp436_public_statement_consumers import v2_bundle  # noqa: E402


class ReviewedSyntheticOpinions:
    """Each record has its own candidate, immutable text and five review lanes."""

    def __init__(self):
        self.subjects: list[IsolatedStatementSource] = []
        for number, person_id, content_id in (
            (1, "person:A", "content:A"),
            (2, "person:A", "content:B"),
            (3, "person:B", "content:B"),
        ):
            owner = IsolatedStatementSource()
            row = owner.row
            row.update({
                "statement_id": f"statement:{number}",
                "version_id": f"statement-version:{number}",
                "person_id": person_id,
                "speaker_name": f"Persona sintetica {person_id}",
                "content_id": content_id,
                "source_version": f"source-version:{number}",
                "source_url": f"https://example.org/source-{number}",
                "statement_date": f"2026-10-{number:02d}",
            })
            for lane, proof in owner.gates.items():
                proof.update({
                    "statement_id": row["statement_id"],
                    "version_id": row["version_id"],
                    "person_id": row["person_id"],
                    "content_id": row["content_id"],
                    "source_version": row["source_version"],
                    "source_url": row["source_url"],
                    "statement_date": row["statement_date"],
                    "decision_id": f"decision:{lane}:{number}",
                    "review_event_id": f"review:{lane}:{number}",
                })
                if lane == "attribution":
                    proof["speaker_name"] = row["speaker_name"]
            self.subjects.append(owner)
        self.reversed = False

    def projectable_findings(self):
        return []

    def projectable_public_statements(self):
        items = [owner.row for owner in self.subjects]
        return list(reversed(items)) if self.reversed else items

    def get_statement_source_text(self, content_id, version):
        match = next((owner for owner in self.subjects if (
            owner.row["content_id"], owner.row["source_version"]
        ) == (content_id, version)), None)
        return match.source_text if match else None

    def statement_publication_attestations(self, statement_id, version):
        match = next((owner for owner in self.subjects if (
            owner.row["statement_id"], owner.row["version_id"]
        ) == (statement_id, version)), None)
        return match.gates if match else None

    def autonomous_publication_evidence(self, statement_id, version):
        match = next((owner for owner in self.subjects if (
            owner.row["statement_id"], owner.row["version_id"]
        ) == (statement_id, version)), None)
        return match.autonomous_publication_evidence(statement_id, version) if match else None

    def current_statement_challenge_hold(self, statement_id, version):
        match = next((owner for owner in self.subjects if (
            owner.row["statement_id"], owner.row["version_id"]
        ) == (statement_id, version)), None)
        return match.current_statement_challenge_hold(statement_id, version) if match else None

    def build(self):
        # Used as a direct synthetic source by Python tests and Node fixtures.
        # The override is limited to the build call, never the live policy.
        with patch(
            "dichiarazioni_pubbliche.autonomous_publication.APPROVED_REVIEW_MODELS",
            frozenset({"model:1", "model:2"}),
        ):
            return build_public_projection(
                self, generated_at=STAMP, include_public_statements=True,
            )


class PublicOpinionApiTests(unittest.TestCase):
    def setUp(self):
        self.source = ReviewedSyntheticOpinions()
        self.bundle = self.source.build()
        self.assertEqual(len(self.bundle["statements"]), 3)

    def read(self, *, bundle=None, current=None, **kwargs):
        snapshot = self.bundle if bundle is None else bundle
        return list_public_opinions_by_person_content_v3(
            snapshot, allow_statement_v3=True,
            current_public_dataset_sha256=(
                snapshot["dataset_sha256"] if current is None else current
            ), **kwargs,
        )

    def test_original_opinions_without_findings_group_by_person_and_content(self):
        result = self.read()
        self.assertEqual(result["meta"]["count"], 3)
        self.assertEqual(result["meta"]["person_count"], 2)
        self.assertEqual(result["meta"]["public_schema_version"], self.bundle["schema_version"])
        self.assertEqual(result["meta"]["dataset_sha256"], self.bundle["dataset_sha256"])
        self.assertEqual([row["person_id"] for row in result["data"]], ["person:A", "person:B"])
        self.assertEqual(
            [(row["content_id"], len(row["statements"])) for row in result["data"][0]["contents"]],
            [("content:A", 1), ("content:B", 1)],
        )
        for person in result["data"]:
            for content in person["contents"]:
                for row in content["statements"]:
                    self.assertEqual(row["person"]["id"], person["person_id"])
                    self.assertEqual(row["source"]["content_id"], content["content_id"])
                    self.assertEqual(row["original"]["text"], QUOTE)
                    self.assertEqual(row["original"]["quote_sha256"], SHA(QUOTE))
                    self.assertEqual(row["source"]["sha256"], SHA(SOURCE))
                    self.assertTrue(row["endorsed"])
                    self.assertEqual(row["speech_act"], "OPINION")
                    self.assertIsNone(row["finding_id"])
                    self.assertEqual(row["original"]["wording_type"], "VERBATIM_ORIGINAL")
                    self.assertEqual(
                        row, get_public_statement_v3(
                            self.bundle, row["statement_id"], allow_statement_v3=True,
                            current_public_dataset_sha256=self.bundle["dataset_sha256"],
                        )["data"],
                    )
        body = json.dumps(result)
        for denied in ("verdict", "assessment", "truth_score", "review_provenance",
                       "raw_transcript", "private_candidate_count", SOURCE):
            self.assertNotIn(denied, body)

    def test_person_content_filters_are_intersected_not_inferred(self):
        result = self.read(person_id="person:A", content_id="content:B")
        self.assertEqual(result["meta"]["count"], 1)
        self.assertEqual(result["data"][0]["contents"][0]["statements"][0]["statement_id"], "statement:2")
        for filter_value in ("person:private", "person:unknown"):
            absent = self.read(person_id=filter_value)
            self.assertEqual(absent["data"], [])
            self.assertEqual(absent["meta"]["count"], 0)
            self.assertNotIn(filter_value, json.dumps(absent))
        self.assertEqual(self.read(person_id="person:B", content_id="content:A")["data"], [])
        self.assertEqual(self.read(content_id="content:B")["meta"]["count"], 2)
        for invalid in ("", "  ", "../secret", "person:A\nprivate", "x" * 129):
            with self.subTest(invalid=invalid):
                with self.assertRaises(PublicApiError) as exc:
                    self.read(person_id=invalid)
                self.assertEqual(exc.exception.status, 400)

    def test_two_original_opinions_on_same_content_form_dated_chronology(self):
        second = self.source.subjects[1]
        second.row["content_id"] = "content:A"
        for gate in second.gates.values():
            gate["content_id"] = "content:A"
        bundled = self.source.build()
        result = self.read(bundle=bundled, person_id="person:A", content_id="content:A")
        self.assertEqual(result["meta"]["count"], 2)
        self.assertEqual(result["meta"]["content_group_count"], 1)
        self.assertEqual(
            [entry["statement_id"] for entry in result["data"][0]["contents"][0]["statements"]],
            ["statement:2", "statement:1"],
        )
        self.assertEqual(
            [entry["statement_date"] for entry in result["data"][0]["contents"][0]["statements"]],
            ["2026-10-02", "2026-10-01"],
        )
        self.assertTrue(all(entry["original"]["wording_type"] == "VERBATIM_ORIGINAL"
                            for entry in result["data"][0]["contents"][0]["statements"]))

    def test_reported_critical_or_unendorsed_statements_not_promoted_to_opinion(self):
        self.source.subjects[1].gates["context"].update({
            "speech_act": "REPORTED_QUOTE", "endorsed": False,
        })
        self.source.subjects[2].gates["context"].update({
            "speech_act": "OPINION", "endorsed": False,
        })
        rebuilt = self.source.build()
        self.assertEqual(len(rebuilt["statements"]), 3, "record stays public but has no endorsement")
        result = self.read(bundle=rebuilt)
        self.assertEqual(result["meta"]["count"], 1)
        self.assertEqual(result["data"][0]["contents"][0]["statements"][0]["statement_id"], "statement:1")
        self.assertNotIn("statement:2", json.dumps(result))
        self.assertNotIn("statement:3", json.dumps(result))
        self.source.subjects[1].gates["context"]["speech_act"] = "CRITICISM"
        self.assertEqual(self.read(bundle=self.source.build())["meta"]["count"], 1)

    def test_rights_revocation_private_hold_and_unavailable_unknown_stay_absent(self):
        previous = self.bundle
        self.source.subjects[0].gates["rights"]["status"] = "REVOKED"
        self.source.subjects[1].gates["publication"]["status"] = "HELD"
        after = self.source.build()
        self.assertEqual(len(after["statements"]), 1)
        now = self.read(bundle=after)
        self.assertEqual(now["meta"]["count"], 1)
        self.assertEqual(now["data"][0]["person_id"], "person:B")
        self.assertNotIn("statement:1", json.dumps(now))
        self.assertNotIn("statement:2", json.dumps(now))
        with self.assertRaises(PublicApiError) as exc:
            self.read(bundle=previous, current=after["dataset_sha256"])
        self.assertEqual(exc.exception.status, 503)
        self.assertEqual(exc.exception.code, "PUBLIC_PROJECTION_UNAVAILABLE")

    def test_explicit_optin_v2_and_external_current_fingerprint_required(self):
        for params in (
            {"allow_statement_v3": False, "current_public_dataset_sha256": self.bundle["dataset_sha256"]},
            {"allow_statement_v3": True},
            {"allow_statement_v3": True, "current_public_dataset_sha256": "f" * 64},
        ):
            with self.subTest(params=params), self.assertRaises(PublicApiError) as exc:
                list_public_opinions_by_person_content_v3(self.bundle, **params)
            self.assertEqual(exc.exception.status, 503)
        with self.assertRaises(PublicApiError):
            self.read(bundle=v2_bundle())

    def test_stable_replay_source_version_correction_and_no_mutable_original_alias(self):
        before = self.read()
        self.assertEqual(before, self.read())
        self.source.reversed = True
        same = self.source.build()
        self.assertEqual(same, self.bundle)
        self.assertEqual(self.read(bundle=same), before)
        # A source version change without independently updated approval
        # cannot be presented to the reader, even with matching quote text.
        owner = self.source.subjects[0]
        owner.row["source_version"] = "source-version:corrected"
        self.assertEqual(len(self.source.build()["statements"]), 2)
        for gate in owner.gates.values():
            gate["source_version"] = "source-version:corrected"
        changed = self.source.build()
        self.assertEqual(len(changed["statements"]), 3)
        corrected = self.read(bundle=changed)
        self.assertNotEqual(corrected["meta"]["dataset_sha256"], before["meta"]["dataset_sha256"])
        self.assertEqual(corrected["data"][0]["contents"][0]["statements"][0]["source"]["version_id"],
                         "source-version:corrected")
        self.bundle["statements"][0]["original_text"] = "TAMPERED LATER"
        self.assertEqual(before["data"][0]["contents"][0]["statements"][0]["original"]["text"], QUOTE)


if __name__ == "__main__":
    unittest.main()
