"""DP-213: an event-ID collision must never mutate a Coverage Need without a receipt.

This test executes the actual narrow-store SQL against a disposable PostgreSQL
database with the exact canonical coverage_need and coverage_need_event DDL.
"""

from __future__ import annotations

import json
import socket
import tempfile
import unittest
from pathlib import Path

from tests.test_claim_evidence_retrieval_replay import ROOT, _bin, _cmd

import sys
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore  # noqa: E402


class CoverageNeedEventCollisionPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="dp213-coverage-event-")
        cls.root = Path(cls.temporary.name)
        cls.pgdata = cls.root / "data"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        _cmd([_bin("initdb"), "-D", str(cls.pgdata), "--username=postgres", "--auth=trust", "--no-locale"])
        cls.pgctl = _bin("pg_ctl")
        _cmd([cls.pgctl, "-D", str(cls.pgdata), "-l", str(cls.root / "postgres.log"),
              "-o", f"-F -p {port} -h 127.0.0.1 -k {cls.root}", "-w", "start"])
        cls.database = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        _cmd([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database],
             stdin="""
             CREATE TABLE research_collection (id text PRIMARY KEY);
             CREATE TABLE atomic_claim (id text PRIMARY KEY);
             CREATE TABLE claim_candidate (id text PRIMARY KEY);
             CREATE TABLE evidence_set_assessment (id text PRIMARY KEY, metadata jsonb NOT NULL DEFAULT '{}');
             CREATE TABLE content_item (id text PRIMARY KEY);
             CREATE TABLE evidence (id text PRIMARY KEY);
             CREATE TABLE source_profile (id text PRIMARY KEY);
             INSERT INTO atomic_claim(id) VALUES ('claim:fixture');
             INSERT INTO evidence(id) VALUES ('evidence:fixture');
             """)
        source = (ROOT / "db/schema.v1.sql").read_text(encoding="utf-8")
        need_ddl = "CREATE TABLE IF NOT EXISTS coverage_need (\n" + source.split(
            "CREATE TABLE IF NOT EXISTS coverage_need (\n", 1
        )[1].split("\nCREATE UNIQUE INDEX IF NOT EXISTS coverage_need_identity_idx", 1)[0]
        event_ddl = "CREATE TABLE IF NOT EXISTS coverage_need_event (\n" + source.split(
            "CREATE TABLE IF NOT EXISTS coverage_need_event (\n", 1
        )[1].split("\nCREATE INDEX IF NOT EXISTS coverage_need_event_need_idx", 1)[0]
        _cmd([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database],
             stdin=need_ddl + "\n" + event_ddl + """
             INSERT INTO coverage_need
                 (id, atomic_claim_id, need_type, requirement_kind, requirement_fingerprint, question)
             VALUES
                 ('need:attempt','claim:fixture','OTHER','OTHER',repeat('a',64),'attempt'),
                 ('need:satisfy','claim:fixture','OTHER','OTHER',repeat('b',64),'satisfy'),
                 ('need:block','claim:fixture','OTHER','OTHER',repeat('c',64),'block'),
                 ('need:replay','claim:fixture','OTHER','OTHER',repeat('d',64),'replay'),
                 ('need:owner','claim:fixture','OTHER','OTHER',repeat('e',64),'existing owner'),
                 ('need:satisfy-ok','claim:fixture','OTHER','OTHER',repeat('f',64),'successful satisfaction'),
                 ('need:block-ok','claim:fixture','OTHER','OTHER',repeat('0',64),'successful block');
             INSERT INTO coverage_need_event
                 (id,coverage_need_id,event_type,from_status,to_status,attempt_number)
             VALUES
                 ('event:unrelated','need:owner','SEARCH_ATTEMPT','OPEN','SEARCHING',1);
             """)
        cls.store = ClaimEvidenceObservationStore(database_url=cls.database)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            _cmd([cls.pgctl, "-D", str(cls.pgdata), "-m", "fast", "-w", "stop"])
        finally:
            cls.temporary.cleanup()

    def need(self, need_id: str) -> dict:
        return json.loads(self.store.run("""
            SELECT row_to_json(n)::text
            FROM (SELECT status, attempt_count, blocker_code,
                         satisfied_by_evidence_id
                  FROM coverage_need WHERE id=:'need_id') n;
        """, need_id=need_id))

    def test_attempt_collision_must_not_consume_budget_without_new_receipt(self):
        before = self.need("need:attempt")
        response = self.store.record_coverage_need_attempt(
            coverage_need_id="need:attempt", event_id="event:unrelated"
        )
        self.assertFalse(response["changed"])
        self.assertEqual(self.need("need:attempt"), before)

    def test_satisfaction_collision_must_not_hide_missing_evidence(self):
        before = self.need("need:satisfy")
        result = self.store.satisfy_coverage_need(
            coverage_need_id="need:satisfy", event_id="event:unrelated",
            evidence_id="evidence:fixture",
        )
        self.assertNotEqual(result, "SATISFIED")
        self.assertEqual(self.need("need:satisfy"), before)

    def test_block_collision_must_not_hide_research_need(self):
        before = self.need("need:block")
        result = self.store.block_coverage_need(
            coverage_need_id="need:block", event_id="event:unrelated",
            blocker_code="SEARCH_BUDGET_EXHAUSTED",
        )
        self.assertNotEqual(result, "BLOCKED")
        self.assertEqual(self.need("need:block"), before)

    def test_normal_attempt_and_exact_replay_do_not_double_count(self):
        result = self.store.record_coverage_need_attempt(
            coverage_need_id="need:replay", event_id="event:real-attempt",
        )
        self.assertTrue(result["changed"])
        self.assertEqual(self.need("need:replay")["attempt_count"], 1)
        repeated = self.store.record_coverage_need_attempt(
            coverage_need_id="need:replay", event_id="event:real-attempt",
        )
        self.assertFalse(repeated["changed"])
        self.assertEqual(self.need("need:replay")["attempt_count"], 1)
        self.assertEqual(self.store.run("""
            SELECT count(*)::text FROM coverage_need_event WHERE id='event:real-attempt'
        """), "1")

    def test_normal_satisfaction_is_receipted_and_exact_replay_is_idempotent(self):
        params = {
            "coverage_need_id": "need:satisfy-ok",
            "event_id": "event:real-satisfaction",
            "evidence_id": "evidence:fixture",
        }
        self.assertEqual(self.store.satisfy_coverage_need(**params), "SATISFIED")
        self.assertEqual(self.need("need:satisfy-ok")["status"], "SATISFIED")
        self.assertEqual(self.store.satisfy_coverage_need(**params), "EXISTING")
        self.assertEqual(self.store.run("""
            SELECT count(*)::text FROM coverage_need_event
            WHERE id='event:real-satisfaction' AND event_type='SATISFIED'
        """), "1")

    def test_normal_block_is_receipted_and_exact_replay_is_idempotent(self):
        params = {
            "coverage_need_id": "need:block-ok",
            "event_id": "event:real-block",
            "blocker_code": "SEARCH_BUDGET_EXHAUSTED",
        }
        self.assertEqual(self.store.block_coverage_need(**params), "BLOCKED")
        self.assertEqual(self.need("need:block-ok")["status"], "BLOCKED")
        self.assertEqual(self.store.block_coverage_need(**params), "EXISTING")
        self.assertEqual(self.store.run("""
            SELECT count(*)::text FROM coverage_need_event
            WHERE id='event:real-block' AND event_type='BLOCKED'
        """), "1")


if __name__ == "__main__":
    unittest.main()
