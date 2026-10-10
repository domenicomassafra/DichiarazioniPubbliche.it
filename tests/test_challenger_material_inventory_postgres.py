"""DP-229: read-only challenger inventory against a disposable PostgreSQL ledger."""

from __future__ import annotations

import shutil
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


def _bin(name: str) -> str:
    executable = shutil.which(name)
    if executable:
        return executable
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
             CREATE TABLE evidence (
                 id text PRIMARY KEY, canonical_url text,
                 content_sha256 text, rights_status text, record_status text,
                 independence_group text
             );
             CREATE TABLE review_event (
                 id text PRIMARY KEY, entity_type text, entity_id text,
                 action text, actor_ref text, reason text,
                 metadata jsonb, created_at timestamptz DEFAULT now()
             );
             INSERT INTO atomic_claim (id) VALUES ('claim:collision'), ('claim:hash');
             INSERT INTO evidence (id, content_sha256, rights_status, record_status)
             VALUES ('ev|part', repeat('a', 64), 'CLEARED', 'ACTIVE'),
                    ('ev', repeat('b', 64), 'CLEARED', 'ACTIVE'),
                    ('ev:hash-missing', NULL, 'CLEARED', 'ACTIVE');
             """)
        _run([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database,
              "-f", str(ROOT / "db/migrations/20260922-add-claim-evidence-ledger.sql")])
        cls.store = QueueRuntimeStore(cls.database)

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
        self.assertEqual(inventory.pending_or_unverified, 1)
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


if __name__ == "__main__":
    unittest.main()
