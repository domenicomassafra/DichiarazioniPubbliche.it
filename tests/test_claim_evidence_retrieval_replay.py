"""Real PostgreSQL regression: retrieval replays must not undo reviewed evidence.

Exercises the actual ClaimEvidenceObservationStore SQL against a disposable
local database. No production data, credentials or external providers.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore  # noqa: E402


def _bin(name: str) -> str:
    executable = shutil.which(name)
    if executable:
        return executable
    config = shutil.which("pg_config")
    if config:
        prefix = subprocess.run([config, "--bindir"], capture_output=True, text=True, check=True).stdout.strip()
        resolved = Path(prefix) / name
        if resolved.is_file():
            return str(resolved)
    raise unittest.SkipTest(f"PostgreSQL unavailable: {name}")


def _cmd(arguments: list[str], *, stdin: str | None = None) -> str:
    proc = subprocess.run(arguments, input=stdin, capture_output=True, text=True, check=False)
    if proc.returncode:
        raise RuntimeError(f"temporary PostgreSQL command failed: {proc.stderr[:1200]}")
    return proc.stdout.strip()


class ClaimEvidenceRetrievalReplayPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        for name in ("initdb", "pg_ctl", "psql"):
            _bin(name)
        cls.temporary = tempfile.TemporaryDirectory(prefix="dp229-retrieval-replay-")
        cls.root = Path(cls.temporary.name)
        cls.pgdata = cls.root / "pg"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        _cmd([_bin("initdb"), "-D", str(cls.pgdata), "--username=postgres", "--auth=trust", "--no-locale"])
        cls.pgctl = _bin("pg_ctl")
        _cmd([cls.pgctl, "-D", str(cls.pgdata), "-l", str(cls.root / "postgres.log"),
              "-o", f"-F -p {port} -h 127.0.0.1 -k {cls.root}", "-w", "start"])
        cls.database = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        # Minimal legitimate dependencies for the *actual* claim-evidence
        # migration; no replacement for the migration's reviewed status enum.
        _cmd([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database],
             stdin="""
             CREATE TABLE atomic_claim (id text PRIMARY KEY);
             CREATE TABLE evidence (
               id text PRIMARY KEY, canonical_url text, content_sha256 text
             );
             CREATE TABLE review_event (
               id text PRIMARY KEY, entity_type text, entity_id text,
               action text, actor_ref text, reason text, metadata jsonb
             );
             INSERT INTO atomic_claim (id) VALUES
               ('claim:reviewed'), ('claim:rejected'), ('claim:open'),
               ('claim:prior-reviewed'), ('claim:quarantined'),
               ('claim:collision');
             INSERT INTO evidence (id) VALUES
               ('evidence:reviewed'), ('evidence:rejected'), ('evidence:open'),
               ('evidence:prior-reviewed'), ('evidence:quarantined'),
               ('evidence:collision');
             """)
        for _ in range(2):
            _cmd([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database,
                  "-f", str(ROOT / "db/migrations/20260922-add-claim-evidence-ledger.sql")])
        # Extract the actual canonical schema of evidence_observation rather
        # than reimplementing its status constraints in this regression.
        schema = (ROOT / "db/schema.v1.sql").read_text(encoding="utf-8")
        observation_ddl = "CREATE TABLE IF NOT EXISTS evidence_observation (\n" + (
            schema.split("CREATE TABLE IF NOT EXISTS evidence_observation (\n", 1)[1]
            .split("\nCREATE INDEX IF NOT EXISTS evidence_observation_metric_idx", 1)[0]
        )
        _cmd([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database],
             stdin=observation_ddl)
        _cmd([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database],
             stdin="""
             INSERT INTO evidence_observation
                (id, evidence_id, observation_type, value_text,
                 extraction_method, extraction_version)
             VALUES
                ('obs:approved', 'evidence:reviewed', 'QUOTED', 'recorded',
                 'manual', 'v1'),
                ('obs:collision', 'evidence:collision', 'QUOTED', 'recorded',
                 'manual', 'v1'),
                ('obs:stale', 'evidence:rejected', 'QUOTED', 'recorded',
                 'manual', 'v1');
             """)
        cls.store = QueueRuntimeStore(cls.database)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            _cmd([cls.pgctl, "-D", str(cls.pgdata), "-m", "fast", "-w", "stop"])
        finally:
            cls.temporary.cleanup()

    def state(self, claim_id: str, evidence_id: str) -> dict[str, object]:
        return json.loads(self.store.run("""
            SELECT row_to_json(t)::text FROM (
                SELECT relation_candidate, status, score, statement_cutoff,
                       metadata, retrieval_method, retrieval_version
                FROM claim_evidence_candidate
                WHERE claim_id = :'claim_id' AND evidence_id = :'evidence_id'
                      AND retrieval_version = 'retriever-v1'
            ) AS t;
        """, claim_id=claim_id, evidence_id=evidence_id))

    def link(self, suffix: str, *, relation: str, score: float, note: str) -> bool:
        return self.store.link_claim_evidence(
            claim_id=f"claim:{suffix}", evidence_id=f"evidence:{suffix}",
            retrieval_method="OFFICIAL_INDEX", retrieval_version="retriever-v1",
            relation_candidate=relation, score=score,
            metadata={"note": note},
        )

    def test_approved_review_cannot_be_demoted_or_rewritten_by_retrieval_replay(self):
        self.assertTrue(self.link("reviewed", relation="CONTRADICT", score=0.9, note="original"))
        approved = self.store.approve_claim_evidence_with_review(
            claim_id="claim:reviewed", evidence_id="evidence:reviewed",
            retrieval_version="retriever-v1", event_id="review:dp229:approved",
            actor_ref="reviewer:fixture", reason="checked",
        )
        self.assertTrue(approved)
        before = self.state("claim:reviewed", "evidence:reviewed")
        self.assertEqual(before["status"], "APPROVED")
        self.assertTrue(self.store.approve_claim_evidence_with_review(
            claim_id="claim:reviewed", evidence_id="evidence:reviewed",
            retrieval_version="retriever-v1", event_id="review:dp229:approved",
            actor_ref="reviewer:fixture", reason="checked",
        ))
        self.assertFalse(self.store.approve_claim_evidence_with_review(
            claim_id="claim:reviewed", evidence_id="evidence:reviewed",
            retrieval_version="retriever-v1", event_id="review:dp229:approved",
            actor_ref="reviewer:impersonated", reason="checked",
        ))
        self.assertFalse(self.store.approve_claim_evidence_with_review(
            claim_id="claim:reviewed", evidence_id="evidence:reviewed",
            retrieval_version="retriever-v1", event_id="review:dp229:approved",
            actor_ref="reviewer:fixture", reason="rewritten reason",
        ))

        # The same job can be retried after human approval. Only the
        # reviewer-controlled path may supersede this material.
        self.assertFalse(self.link("reviewed", relation="SUPPORT", score=0.1, note="replay forgery"))
        self.assertEqual(self.state("claim:reviewed", "evidence:reviewed"), before)
        self.assertEqual(self.store.run("SELECT count(*)::text FROM review_event"), "1")

    def test_rejected_material_cannot_resurrect_on_retry(self):
        self.assertTrue(self.link("rejected", relation="CONTRADICT", score=0.8, note="pre-review"))
        self.assertTrue(self.store.update_claim_evidence_status(
            claim_id="claim:rejected", evidence_id="evidence:rejected",
            retrieval_version="retriever-v1", status="REJECTED",
        ))
        before = self.state("claim:rejected", "evidence:rejected")
        self.assertFalse(self.link("rejected", relation="SUPPORT", score=1, note="resurrect"))
        self.assertEqual(self.state("claim:rejected", "evidence:rejected"), before)

    def test_unreviewed_material_can_be_retried_and_remains_unapproved(self):
        self.assertTrue(self.link("open", relation="UNKNOWN", score=0.2, note="old"))
        self.assertFalse(self.link("open", relation="CONTEXT", score=0.3, note="new"))
        row = self.state("claim:open", "evidence:open")
        self.assertEqual(row["status"], "RETRIEVED")
        self.assertEqual(row["relation_candidate"], "CONTEXT")
        self.assertEqual(row["metadata"], {"note": "new"})

    def test_historical_approval_event_blocks_retriever_even_if_status_was_previously_demoted(self):
        self.assertTrue(self.link("prior-reviewed", relation="CONTRADICT", score=0.8, note="source"))
        self.assertTrue(self.store.approve_claim_evidence_with_review(
            claim_id="claim:prior-reviewed", evidence_id="evidence:prior-reviewed",
            retrieval_version="retriever-v1", event_id="review:dp229:historical",
            actor_ref="reviewer:fixture", reason="approved historical source",
        ))
        # Model the bad prior version of the RETRIEVED writer, not a legitimate
        # review reversal: a status can already have been corrupted before upgrade.
        self.store.run("""
            UPDATE claim_evidence_candidate SET status='RETRIEVED'
            WHERE claim_id='claim:prior-reviewed'
        """)
        before = self.state("claim:prior-reviewed", "evidence:prior-reviewed")
        self.assertFalse(self.link("prior-reviewed", relation="SUPPORT", score=0.1, note="spoof"))
        self.assertEqual(self.state("claim:prior-reviewed", "evidence:prior-reviewed"), before)
        self.assertFalse(self.store.approve_claim_evidence_with_review(
            claim_id="claim:prior-reviewed", evidence_id="evidence:prior-reviewed",
            retrieval_version="retriever-v1", event_id="review:dp229:historical",
            actor_ref="reviewer:fixture", reason="approved historical source",
        ))
        self.assertEqual(self.state("claim:prior-reviewed", "evidence:prior-reviewed"), before)

    def test_quarantined_material_cannot_be_reset_to_unreviewed_on_replay(self):
        self.assertTrue(self.link("quarantined", relation="CONTRADICT", score=0.9, note="unsafe"))
        self.assertTrue(self.store.update_claim_evidence_status(
            claim_id="claim:quarantined", evidence_id="evidence:quarantined",
            retrieval_version="retriever-v1", status="QUARANTINED",
        ))
        before = self.state("claim:quarantined", "evidence:quarantined")
        self.assertFalse(self.link("quarantined", relation="SUPPORT", score=0.1, note="resurrect"))
        self.assertEqual(self.state("claim:quarantined", "evidence:quarantined"), before)

    def test_reused_review_event_id_cannot_approve_an_unrelated_candidate(self):
        self.assertTrue(self.link("collision", relation="CONTRADICT", score=0.9, note="candidate"))
        # This event belongs to an unrelated entity. A forged request reusing
        # its identifier must not be able to approve another evidence row.
        self.store.run("""
            INSERT INTO review_event
              (id,entity_type,entity_id,action,actor_ref,reason)
            VALUES
              ('review:collision','CLAIM_EVIDENCE_CANDIDATE',
               'claim:other|evidence:other|retriever-v1',
               'APPROVED','reviewer:other','unrelated');
        """)
        self.assertFalse(self.store.approve_claim_evidence_with_review(
            claim_id="claim:collision", evidence_id="evidence:collision",
            retrieval_version="retriever-v1",
            event_id="review:collision",
            actor_ref="reviewer:fixture", reason="approve",
        ))
        self.assertEqual(self.state("claim:collision", "evidence:collision")["status"], "RETRIEVED")

    def test_observation_review_event_collision_must_not_approve_another_observation(self):
        self.store.run("""
            INSERT INTO review_event
              (id,entity_type,entity_id,action,actor_ref,reason)
            VALUES ('review:observation:collision','EVIDENCE_OBSERVATION',
                    'obs:elsewhere','APPROVED','reviewer:other','elsewhere')
        """)
        self.assertFalse(self.store.approve_evidence_observation_with_review(
            observation_id="obs:collision", event_id="review:observation:collision",
            actor_ref="reviewer:fixture", reason="independent decision",
        ))
        self.assertEqual(self.store.run("""
            SELECT status FROM evidence_observation WHERE id = 'obs:collision'
        """), "CANDIDATE")

    def test_observation_replay_requires_exact_event_and_current_approved_status(self):
        kwargs = {
            "observation_id": "obs:approved",
            "event_id": "review:observation:approved",
            "actor_ref": "reviewer:fixture",
            "reason": "reviewed observation",
        }
        self.assertTrue(self.store.approve_evidence_observation_with_review(**kwargs))
        self.assertTrue(self.store.approve_evidence_observation_with_review(**kwargs))
        self.assertFalse(self.store.approve_evidence_observation_with_review(
            **{**kwargs, "actor_ref": "reviewer:impersonated"},
        ))
        self.assertFalse(self.store.approve_evidence_observation_with_review(
            **{**kwargs, "reason": "different reasoning"},
        ))
        self.store.run("""
            UPDATE evidence_observation
            SET status='CANDIDATE'
            WHERE id='obs:approved'
        """)
        self.assertFalse(self.store.approve_evidence_observation_with_review(**kwargs))
        self.assertEqual(self.store.run("""
            SELECT status FROM evidence_observation WHERE id = 'obs:approved'
        """), "CANDIDATE")


if __name__ == "__main__":
    unittest.main()
