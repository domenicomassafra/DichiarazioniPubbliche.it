"""DP-418: actual DP-117 promotion preflight against a disposable PostgreSQL DB."""

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

from dichiarazioni_pubbliche.claim_promotion import (  # noqa: E402
    ClaimPromotionStore, PromotionRequest, promote_claim_candidate,
)


def _exe(name: str) -> str:
    result = shutil.which(name)
    if result:
        return result
    raise unittest.SkipTest(f"PostgreSQL not installed: {name}")


def _run(args: list[str], *, stdin: str | None = None) -> str:
    result = subprocess.run(args, input=stdin, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError("isolated PostgreSQL failed: " + result.stderr[:1400])
    return result.stdout.strip()


class ClaimPromotionReviewPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        for name in ("initdb", "pg_ctl", "psql"):
            _exe(name)
        cls.temporary = tempfile.TemporaryDirectory(prefix="dp418-review-pg-")
        cls.root = Path(cls.temporary.name)
        cls.data = cls.root / "data"
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        cls.pgctl = _exe("pg_ctl")
        try:
            _run([_exe("initdb"), "-D", str(cls.data), "--username=postgres", "--auth=trust", "--no-locale"])
            _run([cls.pgctl, "-D", str(cls.data), "-l", str(cls.root / "postgres.log"),
                  "-o", f"-F -p {port} -h 127.0.0.1 -k {cls.root}", "-w", "start"])
            cls.database = f"postgresql://postgres@127.0.0.1:{port}/postgres"
            _run([_exe("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database,
                  "-f", str(ROOT / "db/schema.v1.sql")])
            cls.sql("""
                INSERT INTO person (id, canonical_name) VALUES ('person:1', 'Fixture Person');
                INSERT INTO content_item (id, canonical_url)
                    VALUES ('content:1', 'https://example.test/private-fixture');
                INSERT INTO content_capture
                    (id, content_id, observed_at, final_url, content_sha256,
                     retrieval_method, retrieval_version)
                    VALUES ('capture:1', 'content:1', now(), 'https://example.test/private-fixture',
                            repeat('a',64), 'MANUAL', 'v1');
                INSERT INTO passage
                    (id, content_id, capture_id, selector_type, start_char, end_char,
                     text_sha256, extraction_method, extraction_version)
                    VALUES ('passage:1', 'content:1', 'capture:1', 'TEXT_POSITION', 0, 5,
                            repeat('b',64), 'MANUAL', 'v1');
                INSERT INTO statement_candidate
                    (id, content_id, speaker_person_id, statement_text_hash,
                     normalized_statement, extraction_version, status)
                    VALUES ('statement:1', 'content:1', 'person:1', repeat('b',64),
                            'Fixture statement', 'v1', 'APPROVED');
                INSERT INTO statement_candidate_passage
                    (statement_candidate_id, passage_id, content_id)
                    VALUES ('statement:1', 'passage:1', 'content:1');
                INSERT INTO claim_candidate
                    (id, statement_candidate_id, content_id, normalized_claim,
                     proposed_claim_type, extraction_version)
                    VALUES ('candidate:1', 'statement:1', 'content:1',
                            'Fixture proposition', 'HISTORICAL_CLAIM', 'v1');
                INSERT INTO atomic_claim
                    (id, content_id, speaker_person_id, normalized_claim, claim_type)
                    VALUES ('claim:equivalent', 'content:1', 'person:1',
                            'Fixture proposition', 'HISTORICAL_CLAIM');
                INSERT INTO review_event
                    (id, entity_type, entity_id, action, actor_ref, created_at)
                    VALUES ('review:statement:old', 'STATEMENT_CANDIDATE', 'statement:1',
                            'APPROVED', 'human:1', now()-interval '3 days'),
                           ('review:claim:old', 'CLAIM_CANDIDATE', 'candidate:1',
                            'APPROVED', 'human:1', now()-interval '3 days');
            """)
            cls.store = ClaimPromotionStore(cls.database)
        except Exception:
            try:
                if cls.data.exists():
                    _run([cls.pgctl, "-D", str(cls.data), "-m", "immediate", "-w", "stop"])
            finally:
                cls.temporary.cleanup()
            raise

    @classmethod
    def sql(cls, sql: str) -> str:
        return _run([_exe("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database],
                    stdin=sql)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            _run([cls.pgctl, "-D", str(cls.data), "-m", "fast", "-w", "stop"])
        finally:
            cls.temporary.cleanup()

    def test_latest_rejection_revokes_persisted_candidate_and_statement_approval(self):
        original = self.store.context("candidate:1")
        self.assertTrue(original["claim_candidate_reviewed"])
        self.assertTrue(original["statement_reviewed"])
        self.sql("""
            INSERT INTO review_event
                (id, entity_type, entity_id, action, actor_ref, created_at)
            VALUES ('review:claim:new', 'CLAIM_CANDIDATE', 'candidate:1',
                    'REJECTED', 'human:2', now()-interval '1 day'),
                   ('review:statement:new', 'STATEMENT_CANDIDATE', 'statement:1',
                    'QUARANTINED', 'human:2', now()-interval '1 day');
        """)
        after = self.store.context("candidate:1")
        self.assertFalse(after["claim_candidate_reviewed"])
        self.assertFalse(after["statement_reviewed"])
        receipt = promote_claim_candidate(self.store, PromotionRequest(
            candidate_id="candidate:1", provenance_channel="WRITTEN", actor_ref="human:2",
        ))
        self.assertEqual(receipt.reason_code, "PROMOTION_CLAIM_CANDIDATE_NOT_REVIEWED")
        self.assertEqual(after["candidate_status"], "CANDIDATE")

    def test_identical_wording_is_same_proposition_until_duplicate_is_reviewed(self):
        context = self.store.context("candidate:1")
        self.assertEqual(context["duplicate_target_ids"], [])
        self.assertEqual(context["same_proposition_target_ids"], ["claim:equivalent"])
        self.sql("""
            INSERT INTO proposition_cluster (id, representative_text, cluster_method, status)
                VALUES ('cluster:reviewed-duplicate', 'Fixture proposition',
                        'MANUAL_REVIEW', 'APPROVED');
            INSERT INTO proposition_cluster_member
                (id, cluster_id, member_type, claim_candidate_id, match_class,
                 membership_method, status)
                VALUES ('member:candidate', 'cluster:reviewed-duplicate', 'CLAIM_CANDIDATE',
                        'candidate:1', 'DUPLICATE_EXTRACTION', 'MANUAL_REVIEW', 'APPROVED');
            INSERT INTO proposition_cluster_member
                (id, cluster_id, member_type, atomic_claim_id, match_class,
                 membership_method, status)
                VALUES ('member:atomic', 'cluster:reviewed-duplicate', 'ATOMIC_CLAIM',
                        'claim:equivalent', 'DUPLICATE_EXTRACTION', 'MANUAL_REVIEW', 'APPROVED');
        """)
        reviewed = self.store.context("candidate:1")
        self.assertEqual(reviewed["duplicate_target_ids"], ["claim:equivalent"])
        self.assertEqual(reviewed["same_proposition_target_ids"], [])


if __name__ == "__main__":
    unittest.main()
