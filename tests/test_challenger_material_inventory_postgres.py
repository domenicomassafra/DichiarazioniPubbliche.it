"""DP-229: read-only challenger inventory against a disposable PostgreSQL ledger."""

from __future__ import annotations

import shutil
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.challenger_material_inventory import (  # noqa: E402
    load_challenger_material_inventory,
)
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PrivateRightsRegistryStore, RightsSubject,
)


def _bin(name: str) -> str:
    executable = shutil.which(name)
    if executable:
        return executable
    # Ubuntu packages server binaries under versioned lib directories. GitHub
    # runners can have PostgreSQL installed while `initdb` is absent from PATH;
    # skipping this high-risk revocation regression would hide a real failure.
    for candidate in sorted(Path("/usr/lib/postgresql").glob(f"*/bin/{name}"), reverse=True):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise unittest.SkipTest(f"disposable PostgreSQL unavailable: {name}")


def _run(argv: list[str], *, stdin: str | None = None) -> str:
    result = subprocess.run(argv, input=stdin, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"disposable PostgreSQL failed: {result.stderr[:1200]}")
    return result.stdout.strip()


class ChallengerMaterialInventoryPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        for name in ("initdb", "pg_ctl", "psql"):
            _bin(name)
        cls.temporary = tempfile.TemporaryDirectory(prefix="dp229-inventory-")
        cls.root = Path(cls.temporary.name)
        cls.pgdata = cls.root / "db"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.pgctl = _bin("pg_ctl")
        _run([_bin("initdb"), "-D", str(cls.pgdata), "--username=postgres", "--auth=trust", "--no-locale"])
        _run([cls.pgctl, "-D", str(cls.pgdata), "-l", str(cls.root / "postgres.log"),
              "-o", f"-F -p {port} -h 127.0.0.1 -k {cls.root}", "-w", "start"])
        cls.database = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        _run([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database],
             stdin="""
             CREATE TABLE atomic_claim (id text PRIMARY KEY);
             CREATE TABLE content_item (id text PRIMARY KEY);
             CREATE TABLE transcript_variant (id text PRIMARY KEY, content_id text REFERENCES content_item(id));
             CREATE TABLE transcript_segment (id text PRIMARY KEY, variant_id text REFERENCES transcript_variant(id));
             CREATE TABLE canonical_transcript_segment (id text PRIMARY KEY, content_id text REFERENCES content_item(id));
             CREATE TABLE passage (id text PRIMARY KEY, content_id text REFERENCES content_item(id));
             CREATE TABLE evidence (
                 id text PRIMARY KEY, canonical_url text,
                 content_sha256 text, rights_status text, record_status text,
                 independence_group text, publication_date date,
                 valid_from date, valid_until date, reference_period text
             );
             CREATE TABLE review_event (
                 id text PRIMARY KEY, entity_type text, entity_id text,
                 action text, actor_ref text, reason text,
                 metadata jsonb, created_at timestamptz DEFAULT now()
             );
             INSERT INTO atomic_claim (id) VALUES
                 ('claim:collision'), ('claim:hash'), ('claim:temporal'), ('claim:senato-rights');
             INSERT INTO evidence (id, content_sha256, rights_status, record_status, canonical_url)
             VALUES ('ev|part', repeat('a', 64), 'CLEARED', 'ACTIVE', NULL),
                    ('ev', repeat('b', 64), 'CLEARED', 'ACTIVE', NULL),
                    ('ev:hash-missing', NULL, 'CLEARED', 'ACTIVE', NULL),
                    ('ev:temporal', repeat('c', 64), 'CLEARED', 'ACTIVE', 'https://example.org/temporal'),
                    ('ev:senato', '57fcd8ae860d3e4593686567612e251dc0f40a4d1842bddb6eeac68bdb7ad929', 'CLEARED', 'ACTIVE',
                     'https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml');
             """)
        _run([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database,
              "-f", str(ROOT / "db/migrations/20260922-add-claim-evidence-ledger.sql")])
        _run([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database,
              "-f", str(ROOT / "db/migrations/20261006-add-private-rights-registry.sql")])
        cls.store = QueueRuntimeStore(cls.database)
        cls.rights = PrivateRightsRegistryStore(cls.database)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            _run([cls.pgctl, "-D", str(cls.pgdata), "-m", "fast", "-w", "stop"])
        finally:
            cls.temporary.cleanup()

    def test_delimiter_colliding_entity_ids_do_not_count_as_independent_reviews(self):
        self.assertTrue(self.store.link_claim_evidence(
            claim_id="claim:collision", evidence_id="ev|part",
            retrieval_method="OFFICIAL_INDEX", retrieval_version="v1",
            relation_candidate="CONTRADICT",
        ))
        self.assertTrue(self.store.approve_claim_evidence_with_review(
            claim_id="claim:collision", evidence_id="ev|part", retrieval_version="v1",
            event_id="review:collision", actor_ref="reviewer:fixture", reason="checked",
        ))
        self.assertTrue(self.store.link_claim_evidence(
            claim_id="claim:collision", evidence_id="ev",
            retrieval_method="OFFICIAL_INDEX", retrieval_version="part|v1",
            relation_candidate="CONTRADICT",
        ))
        inventory = load_challenger_material_inventory(self.store, claim_id="claim:collision")
        self.assertEqual(inventory.candidates, 2)
        self.assertGreaterEqual(inventory.pending_or_unverified, 1)
        self.assertIn("CHALLENGER_REVIEW_BINDING_MISMATCH", inventory.blockers)
        self.assertFalse(inventory.publication_authority)

    def test_approved_candidate_with_null_capture_hash_stays_unverified(self):
        self.assertTrue(self.store.link_claim_evidence(
            claim_id="claim:hash", evidence_id="ev:hash-missing",
            retrieval_method="OFFICIAL_INDEX", retrieval_version="v1",
            relation_candidate="CONTRADICT",
        ))
        self.assertTrue(self.store.approve_claim_evidence_with_review(
            claim_id="claim:hash", evidence_id="ev:hash-missing", retrieval_version="v1",
            event_id="review:hash", actor_ref="reviewer:fixture", reason="checked",
        ))
        inventory = load_challenger_material_inventory(self.store, claim_id="claim:hash")
        self.assertEqual(inventory.pending_or_unverified, 1)
        self.assertIn("CHALLENGER_MATERIAL_PROVENANCE_INCOMPLETE", inventory.blockers)
        self.assertFalse(inventory.publication_authority)

    def test_reviewed_material_temporal_scope_change_invalidates_fingerprint(self):
        self.assertTrue(self.store.link_claim_evidence(
            claim_id="claim:temporal", evidence_id="ev:temporal",
            retrieval_method="OFFICIAL_INDEX", retrieval_version="v1",
            relation_candidate="CONTRADICT", statement_cutoff="2025-01-01",
        ))
        self.assertTrue(self.store.approve_claim_evidence_with_review(
            claim_id="claim:temporal", evidence_id="ev:temporal", retrieval_version="v1",
            event_id="review:temporal", actor_ref="reviewer:fixture", reason="checked",
        ))
        self.rights.record_rights(
            subject=RightsSubject(source_family="SYNTHETIC", locator_kind="URL",
                                  locator_value="https://example.org/temporal", evidence_id="ev:temporal"),
            policy_version="dp229-canary-v1", rights_status="CLEARED",
            rights_receipt_ref="fixture:temporal", permitted_uses=("CHALLENGER_PRIVATE_RESEARCH",),
            reviewed_at="2026-10-21T00:00:00+00:00", reviewer_ref="fixture:reviewer",
        )
        baseline = load_challenger_material_inventory(self.store, claim_id="claim:temporal")
        self.assertEqual(baseline.pending_or_unverified, 0)
        edits = [
            "UPDATE evidence SET publication_date='2025-02-01' WHERE id='ev:temporal'",
            "UPDATE evidence SET valid_from='2025-03-01' WHERE id='ev:temporal'",
            "UPDATE evidence SET valid_until='2025-09-01' WHERE id='ev:temporal'",
            "UPDATE evidence SET reference_period='2025-Q1' WHERE id='ev:temporal'",
            "UPDATE claim_evidence_candidate SET statement_cutoff='2024-01-01' "
            "WHERE claim_id='claim:temporal' AND evidence_id='ev:temporal'",
        ]
        for statement in edits:
            self.store.run(statement)
            changed = load_challenger_material_inventory(self.store, claim_id="claim:temporal")
            self.assertNotEqual(
                baseline.material_sha256, changed.material_sha256,
                "reviewed challenger material must stale when temporal scope changes",
            )
            baseline = changed
            self.assertFalse(changed.publication_authority)

    def test_real_source_rights_revocation_stales_inventory_and_blocks_high_risk(self):
        """Source-specific append-only rights supersession must stale the exact claim packet."""
        subject = RightsSubject(
            source_family="SENATO_AKOMANTOSO_CC_BY_4_0", locator_kind="URL",
            locator_value="https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml",
            evidence_id="ev:senato",
        )
        self.assertTrue(self.store.link_claim_evidence(
            claim_id="claim:senato-rights", evidence_id="ev:senato",
            retrieval_method="OFFICIAL_INDEX", retrieval_version="senato:2da7d887",
            relation_candidate="CONTEXT",
        ))
        self.assertTrue(self.store.approve_claim_evidence_with_review(
            claim_id="claim:senato-rights", evidence_id="ev:senato",
            retrieval_version="senato:2da7d887", event_id="review:senato-rights",
            actor_ref="fixture:generic-reviewer", reason="Source identity reviewed; no truth verdict",
        ))
        before = load_challenger_material_inventory(self.store, claim_id="claim:senato-rights")
        cleared = self.rights.record_rights(
            subject=subject, policy_version="dp229-cc-by4-documentary-v1",
            rights_status="CLEARED", rights_receipt_ref="senato:license:2da7d887:cc-by-4.0",
            permitted_uses=("CHALLENGER_PRIVATE_RESEARCH",),
            attribution_requirements=("CITE_SENATO_AND_CC_BY_4_0",),
            reviewed_at="2026-10-21T00:00:00+00:00", reviewer_ref="ai:source-license-review",
        )
        authorized = load_challenger_material_inventory(self.store, claim_id="claim:senato-rights")
        self.assertNotEqual(before.material_sha256, authorized.material_sha256)
        self.assertEqual(authorized.pending_or_unverified, 0)
        self.assertFalse(authorized.publication_authority)
        self.rights.record_rights(
            subject=subject, policy_version="dp229-cc-by4-documentary-v1",
            rights_status="REVOKED", rights_receipt_ref="canary:simulated-revocation",
            reviewed_at="2026-10-22T00:00:00+00:00", reviewer_ref="ai:source-license-review",
            supersedes_record_id=cleared.id,
        )
        revoked = load_challenger_material_inventory(self.store, claim_id="claim:senato-rights")
        self.assertNotEqual(authorized.material_sha256, revoked.material_sha256)
        self.assertEqual(revoked.pending_or_unverified, 1)
        self.assertIn("CHALLENGER_MATERIAL_PENDING_OR_UNVERIFIED", revoked.blockers)
        self.assertIn("CHALLENGER_SOURCE_RIGHTS_NOT_CURRENT", revoked.blockers)
        self.assertFalse(revoked.publication_authority)


if __name__ == "__main__":
    unittest.main()
