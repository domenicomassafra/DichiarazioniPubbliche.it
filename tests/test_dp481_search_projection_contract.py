"""Canonical nonempty public-projection records must survive immutable release gates."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.correction_propagation import _expected_search_records, _projection_state
from dichiarazioni_pubbliche.public_projection import build_public_projection
from dichiarazioni_pubbliche.public_schema import validate_public_bundle
from tests.test_public_projection import FakeContentSource, valid_content_row, valid_row
from tools import dp481_minipc_release as release_tool
from tools.dp481_static_contract import write_build_stamp


class PublicSearchReleaseParityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dp481-search-parity-")
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.source = base / "source"
        (self.source / "poc/dichiarazioni_pubbliche").mkdir(parents=True)
        (self.source / "poc/dichiarazioni_pubbliche/__init__.py").write_text("# fixture\n")
        (self.source / "db").mkdir()
        (self.source / "db/schema.v1.sql").write_text("-- fixture\n")
        self.static = base / "static"
        self.static.mkdir()
        home = (b'<html><head><link rel="icon" href="/favicon.svg"></head>'
                b'<body><main><h1>Approved public preview</h1></main></body></html>')
        (self.static / "index.html").write_bytes(home)
        for route in ("esplora", "metodo", "correzioni", "dati", "progetto",
                      "accedi", "account", "privacy", "segnalazioni"):
            (self.static / route).mkdir()
            (self.static / route / "index.html").write_bytes(home)
        (self.static / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        (self.static / "robots.txt").write_text("User-agent: *\nDisallow: /account/\n")
        (self.static / "sitemap.xml").write_text("<urlset/>")
        self.projection = base / "projection"
        self.projection.mkdir()
        self.public = validate_public_bundle(build_public_projection(
            FakeContentSource([valid_row()], [valid_content_row()]),
            generated_at="2026-09-22T12:00:00+00:00",
        ))
        (self.projection / "index.json").write_text(json.dumps(self.public))
        self.root = base / "host-release"
        self.approved = sorted(_expected_search_records(_projection_state(self.public)).values(),
                               key=lambda record: (record["kind"], record["id"]))
        self.assertEqual(self.public["dossier_count"], 1)
        self.assertEqual(len(self.public["contents"]), 1)
        self.assertEqual(len(self.approved), 3)
        self.write_index(self.approved)

    def write_index(self, records):
        material = {
            "schema_version": "dichiarazioni-pubbliche-search-index-v1",
            "projection_schema_version": self.public["schema_version"],
            "projection_sha256": self.public["dataset_sha256"],
            "generated_at": self.public["generated_at"],
            "records": records,
        }
        material["index_sha256"] = hashlib.sha256(json.dumps(
            material, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()).hexdigest()
        (self.static / "search-index.v1.json").write_text(json.dumps(material))
        write_build_stamp(self.static, git_sha="1" * 40,
                          projection_index=self.projection / "index.json")

    def stage(self):
        return release_tool.stage(
            self.root, self.source, self.static, self.projection,
            git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO",
        )

    def test_authorized_nonempty_public_index_stages_and_validates(self):
        sealed = self.stage()
        self.assertEqual(release_tool.validated(self.root, sealed["release_id"])["release_id"],
                         sealed["release_id"])

    def test_claimed_projection_fingerprint_cannot_override_source_validation(self):
        self.public["dataset_sha256"] = "f" * 64
        (self.projection / "index.json").write_text(json.dumps(self.public))
        self.write_index(self.approved)
        with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
            self.stage()
        with patch.object(release_tool, "check_static_contract", return_value=None):
            with self.assertRaisesRegex(ValueError, "DP481_PROJECTION_INVALID"):
                self.stage()

    def test_retracted_finding_keeps_status_and_uses_retracted_search_label(self):
        row = valid_row()
        row["publication_status"] = "RETRACTED"
        self.public = validate_public_bundle(build_public_projection(
            FakeContentSource([row], [valid_content_row()]),
            generated_at="2026-09-22T12:00:00+00:00",
        ))
        (self.projection / "index.json").write_text(json.dumps(self.public))
        self.approved = sorted(_expected_search_records(_projection_state(self.public)).values(),
                               key=lambda record: (record["kind"], record["id"]))
        self.write_index(self.approved)

        sealed = self.stage()
        finding = next(record for record in self.approved if record["kind"] == "finding")
        self.assertEqual(finding["publication_status"], "RETRACTED")
        self.assertIsNone(finding["assessment"])
        self.assertTrue(finding["subtitle"].startswith("Valutazione ritirata · "))
        self.assertIn("Valutazione ritirata", finding["secondary_terms"])
        self.assertEqual(release_tool.validated(self.root, sealed["release_id"])["release_id"],
                         sealed["release_id"])

    def test_nonempty_index_cannot_omit_or_invent_rebind_or_duplicate_records(self):
        person = next(record for record in self.approved if record["kind"] == "person")
        finding = next(record for record in self.approved if record["kind"] == "finding")
        variants = {
            "missing_all_approved": [],
            "invented_person": [*copy.deepcopy(self.approved), {
                **person, "id": "private-marker", "title": "Unapproved synthetic person",
                "route": "/persone/private-marker/",
            }],
            "duplicate_kind_id_and_route": [*copy.deepcopy(self.approved), copy.deepcopy(person)],
            "rebound_person_route": [
                {**record, "route": "/persone/someone-else/"} if record == person else record
                for record in copy.deepcopy(self.approved)
            ],
            "wrong_approved_person_facet": [
                {**record, "person_id": "private-marker"} if record == finding else record
                for record in copy.deepcopy(self.approved)
            ],
            "missing_finding_publication_status": [
                {key: value for key, value in record.items() if key != "publication_status"}
                if record["kind"] == "finding" else record
                for record in copy.deepcopy(self.approved)
            ],
            "unapproved_finding_publication_status": [
                {**record, "publication_status": "POLICY_HOLD"}
                if record["kind"] == "finding" else record
                for record in copy.deepcopy(self.approved)
            ],
            "non_string_finding_publication_status": [
                {**record, "publication_status": ["PUBLISH"]}
                if record["kind"] == "finding" else record
                for record in copy.deepcopy(self.approved)
            ],
            "non_string_finding_subtitle": [
                {**record, "subtitle": None}
                if record["kind"] == "finding" else record
                for record in copy.deepcopy(self.approved)
            ],
        }
        for label, records in variants.items():
            with self.subTest(variant=label):
                self.write_index(records)
                with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
                    self.stage()
                with patch.object(release_tool, "check_static_contract", return_value=None):
                    sealed = self.stage()
                with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
                    release_tool.validated(self.root, sealed["release_id"])
