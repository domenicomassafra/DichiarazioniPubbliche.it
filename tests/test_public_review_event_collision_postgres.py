"""Public reply/correction state must never advance without its own review event.

Uses the production SQL writers on disposable PostgreSQL, with only the tables
and columns those public transitions require. No public projection or prod data.
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
from dichiarazioni_pubbliche.queue_store import ReviewPublicationDecisionStore  # noqa: E402


class PublicReviewEventCollisionPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp302-303-review-collision-")
        cls.root = Path(cls.tmp.name)
        cls.pgdata = cls.root / "pg"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.pgctl = _bin("pg_ctl")
        _cmd([_bin("initdb"), "-D", str(cls.pgdata), "--username=postgres", "--auth=trust", "--no-locale"])
        _cmd([cls.pgctl, "-D", str(cls.pgdata), "-l", str(cls.root / "postgres.log"),
              "-o", f"-F -p {port} -h 127.0.0.1 -k {cls.root}", "-w", "start"])
        cls.database = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        _cmd([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname", cls.database],
             stdin="""
             CREATE TABLE finding (
               id text PRIMARY KEY, claim_id text NOT NULL,
               publication_status text NOT NULL,
               supersedes_id text
             );
             CREATE TABLE right_of_reply (
               id text PRIMARY KEY, finding_id text NOT NULL,
               status text NOT NULL, reanalysis_job_id text,
               public_visibility text NOT NULL
             );
             CREATE TABLE correction (
               id text PRIMARY KEY, finding_id text NOT NULL,
               previous_finding_id text NOT NULL,
               public_visibility text NOT NULL
             );
             CREATE TABLE reanalysis_trigger (
               id text PRIMARY KEY, claim_id text NOT NULL,
               trigger_type text NOT NULL, source_type text NOT NULL,
               source_id text NOT NULL, status text NOT NULL
             );
             CREATE TABLE review_event (
               id text PRIMARY KEY, entity_type text NOT NULL,
               entity_id text NOT NULL, action text NOT NULL,
               actor_ref text NOT NULL, reason text, metadata jsonb NOT NULL DEFAULT '{}'
             );
             INSERT INTO finding(id,claim_id,publication_status,supersedes_id) VALUES
               ('finding:prior','claim:test','PUBLISH',NULL),
               ('finding:current','claim:test','PUBLISH','finding:prior');
             INSERT INTO review_event(id,entity_type,entity_id,action,actor_ref)
               VALUES ('review:finding:prior','FINDING','finding:prior','APPROVED','reviewer:prior'),
                      ('review:finding:current','FINDING','finding:current','APPROVED','reviewer:current'),
                      ('review:collision','RIGHT_OF_REPLY','reply:other','APPROVED','reviewer:other');
             INSERT INTO right_of_reply(id,finding_id,status,reanalysis_job_id,public_visibility) VALUES
               ('reply:collision','finding:prior','UNDER_REVIEW','job:proof','PRIVATE'),
               ('reply:valid','finding:prior','UNDER_REVIEW','job:proof','PRIVATE');
             INSERT INTO correction(id,finding_id,previous_finding_id,public_visibility) VALUES
               ('correction:collision','finding:current','finding:prior','PRIVATE'),
               ('correction:valid','finding:current','finding:prior','PRIVATE');
             INSERT INTO reanalysis_trigger(id,claim_id,trigger_type,source_type,source_id,status) VALUES
               ('trigger:reply:collision','claim:test','RIGHT_OF_REPLY','RIGHT_OF_REPLY','reply:collision','PROCESSED'),
               ('trigger:reply:valid','claim:test','RIGHT_OF_REPLY','RIGHT_OF_REPLY','reply:valid','PROCESSED'),
               ('trigger:correction:collision','claim:test','CORRECTION','CORRECTION','correction:collision','PROCESSED'),
               ('trigger:correction:valid','claim:test','CORRECTION','CORRECTION','correction:valid','PROCESSED');
             """)
        cls.store = ReviewPublicationDecisionStore(cls.database)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            _cmd([cls.pgctl, "-D", str(cls.pgdata), "-m", "fast", "-w", "stop"])
        finally:
            cls.tmp.cleanup()

    def reply_state(self, id: str) -> dict:
        return json.loads(self.store.run("""
            SELECT row_to_json(r)::text FROM
            (SELECT status,public_visibility FROM right_of_reply WHERE id=:'id') r;
        """, id=id))

    def test_reply_event_collision_must_not_make_private_reply_public(self):
        before = self.reply_state("reply:collision")
        self.assertFalse(self.store.publish_right_of_reply_with_review(
            reply_id="reply:collision", event_id="review:collision",
            actor_ref="reviewer:forged", reason="not authorized event",
        ))
        self.assertEqual(self.reply_state("reply:collision"), before)

    def test_correction_event_collision_must_not_publish_or_rewrite_prior_finding(self):
        self.store.run("""
            INSERT INTO review_event
              (id,entity_type,entity_id,action,actor_ref)
            VALUES
              ('review:correction:collision','CORRECTION','correction:other',
               'APPROVED','reviewer:other')
        """)
        self.assertFalse(self.store.publish_correction_with_review(
            correction_id="correction:collision",
            event_id="review:correction:collision",
            actor_ref="reviewer:forged",
            reason="not authorized event",
        ))
        self.assertEqual(self.store.run("""
            SELECT public_visibility FROM correction
            WHERE id='correction:collision'
        """), "PRIVATE")
        self.assertEqual(self.store.run("""
            SELECT publication_status FROM finding
            WHERE id='finding:prior'
        """), "PUBLISH")

    def test_valid_reply_review_is_idempotent_and_rejects_another_reviewer(self):
        args = dict(reply_id="reply:valid", event_id="review:reply:valid",
                    actor_ref="reviewer:actual", reason="independent review")
        self.assertTrue(self.store.publish_right_of_reply_with_review(**args))
        self.assertTrue(self.store.publish_right_of_reply_with_review(**args))
        self.assertEqual(self.reply_state("reply:valid")["public_visibility"], "PUBLIC")
        self.assertFalse(self.store.publish_right_of_reply_with_review(
            **{**args, "actor_ref": "reviewer:impostor"}
        ))

    def test_valid_correction_review_is_idempotent_and_rejects_changed_reason(self):
        args = dict(correction_id="correction:valid", event_id="review:correction:valid",
                    actor_ref="reviewer:actual", reason="verified correction")
        self.assertTrue(self.store.publish_correction_with_review(**args))
        self.assertTrue(self.store.publish_correction_with_review(**args))
        self.assertEqual(self.store.run("""
            SELECT public_visibility FROM correction WHERE id='correction:valid'
        """), "PUBLIC")
        self.assertFalse(self.store.publish_correction_with_review(
            **{**args, "reason": "forged reason"}
        ))


if __name__ == "__main__":
    unittest.main()
