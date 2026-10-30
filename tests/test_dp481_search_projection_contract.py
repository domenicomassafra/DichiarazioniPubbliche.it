"""Canonical nonempty public-projection records must survive immutable release gates."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.correction_propagation import _expected_search_records, _projection_state
from tools import dp481_minipc_release as release_tool


ROOT = Path(__file__).resolve().parents[1]


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
        self.public = json.loads((ROOT / "web/src/data/demo-projection.json").read_text())
        (self.projection / "index.json").write_text(json.dumps(self.public))
        self.root = base / "host-release"
        self.approved = sorted(_expected_search_records(_projection_state(self.public)).values(),
                               key=lambda record: (record["kind"], record["id"]))
        self.assertEqual(len(self.approved), 12)
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
            sealed = self.stage()
        with self.assertRaisesRegex(ValueError, "STATIC_FORMAT_INVALID"):
            release_tool.validated(self.root, sealed["release_id"])

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
