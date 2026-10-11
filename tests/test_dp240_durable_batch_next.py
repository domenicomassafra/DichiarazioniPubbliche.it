"""DP-240 real local SQLite isolation, restart and immutable attempt receipts."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.multi_person_batch_v1 import PrivateBatchResult  # noqa: E402
from dichiarazioni_pubbliche.multi_person_batch_store_v1 import (  # noqa: E402
    PrivateBatchSQLiteStore,
)
from tests.test_dp240_multi_person_batch import (  # noqa: E402
    manifest,
    plan,
    reviewed_contexts,
)


def observation(item, result="FAILED", reason="TIMEOUT"):
    return PrivateBatchResult(
        item.passage_id,
        item.content_id,
        item.capture_id,
        item.passage_sha256,
        result,
        None if result != "FAILED" else reason,
        "fixture:private:v1" if result == "CANDIDATE_EXTRACTED" else None,
    )


class DurableBatchNextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "batch.sqlite3"
        self.store = PrivateBatchSQLiteStore(self.path)
        batch = manifest()
        contexts = reviewed_contexts(batch)
        contexts["passage:0"] = replace(
            contexts["passage:0"], speaker_candidate_id="person:anna:source-a"
        )
        contexts["passage:1"] = replace(
            contexts["passage:1"], speaker_candidate_id="person:anna:source-b"
        )
        self.plan = plan(batch, contexts)

    def test_real_sqlite_partial_resume_and_process_restart(self):
        initial = self.store.register(self.plan)
        self.assertEqual((initial.revision, initial.index.pending_count), (0, 3))
        first, second, third = self.plan.items
        failed = observation(first)
        one = self.store.observe(
            self.plan,
            first,
            failed,
            attempt_key="attempt:source-a",
            expected_revision=0,
        )
        self.assertEqual((one.revision, one.index.failed_count), (1, 1))
        self.assertEqual(
            one.attempts[0].item.speaker_candidate_id, "person:anna:source-a"
        )
        self.assertEqual(one.attempts[0].item.source_sha256, first.source_sha256)
        self.assertEqual(
            one.attempts[0].item.selector_fingerprint, first.selector_fingerprint
        )
        self.assertEqual(one.readback.failed_count, 1)

        # Duplicate replay after a restart is a no-op even with the original CAS.
        reopened = PrivateBatchSQLiteStore(self.path)
        self.assertEqual(reopened.read(self.plan), one)
        self.assertEqual(
            reopened.observe(
                self.plan,
                first,
                failed,
                attempt_key="attempt:source-a",
                expected_revision=0,
            ),
            one,
        )
        done = reopened.observe(
            self.plan,
            third,
            observation(third, "CANDIDATE_EXTRACTED"),
            attempt_key="attempt:source-c",
            expected_revision=one.revision,
        )
        self.assertEqual((done.revision, done.index.pending_count), (2, 1))
        self.assertEqual(done.index.private_candidate_count, 1)
        self.assertEqual(done.index.items[0].status, "FAILED")
        self.assertEqual(done.index.items[1].status, "UNOBSERVED")
        self.assertEqual(done.index.items[2].status, "PRIVATE_CANDIDATE_UNVERIFIED")
        self.assertFalse(done.index.publication_authority)
        self.assertFalse(done.index.dispatch_authorized)

        # Fresh interpreter: read persisted state and finish only the unobserved item.
        script = """
import json, sys
from pathlib import Path
from dichiarazioni_pubbliche.multi_person_batch_store_v1 import PrivateBatchSQLiteStore
from tests.test_dp240_durable_batch_next import observation
store=PrivateBatchSQLiteStore(Path(sys.argv[1]))
planned=store.load_plan(sys.argv[2])
before=store.resume(sys.argv[2])
second=planned.items[1]
after=store.observe(planned,second,observation(second,'CANDIDATE_EXTRACTED'),
    attempt_key='attempt:source-b',expected_revision=before.revision)
print(json.dumps({'before':before.revision,'after':after.revision,
    'statuses':[i.status for i in after.index.items],
    'attempts':len(after.attempts)}))
"""
        env = {
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "poc")
            + os.pathsep
            + str(Path(__file__).resolve().parents[1]),
        }
        proc = subprocess.run(
            [sys.executable, "-c", script, str(self.path), self.plan.plan_sha256],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        self.assertEqual(
            json.loads(proc.stdout),
            {
                "before": 2,
                "after": 3,
                "statuses": [
                    "FAILED",
                    "PRIVATE_CANDIDATE_UNVERIFIED",
                    "PRIVATE_CANDIDATE_UNVERIFIED",
                ],
                "attempts": 3,
            },
        )
        after_restart = self.store.read(self.plan)
        self.assertEqual(self.store.load_plan(self.plan.plan_sha256), self.plan)
        self.assertEqual(self.store.resume(self.plan.plan_sha256), after_restart)
        self.assertEqual(after_restart.revision, 3)
        self.assertEqual(after_restart.index.observed_count, 3)
        self.assertEqual(after_restart.readback.private_candidate_count, 2)

    def test_exact_person_source_passage_capture_segment_binding_and_atomic_refusal(
        self,
    ):
        self.store.register(self.plan)
        first, second, _ = self.plan.items
        matching = observation(first, "CANDIDATE_EXTRACTED")
        mismatches = (
            replace(first, content_id=second.content_id),
            replace(first, capture_id=second.capture_id),
            replace(first, source_sha256="f" * 64),
            replace(first, passage_sha256=second.passage_sha256),
            replace(first, selector_fingerprint="selector:foreign"),
            replace(first, partition_id=second.partition_id),
            replace(first, speaker_candidate_id=second.speaker_candidate_id),
            replace(first, context_review_id="review:other"),
        )
        for foreign in mismatches:
            with (
                self.subTest(foreign=foreign),
                self.assertRaisesRegex(ValueError, "SOURCE_BINDING_MISMATCH"),
            ):
                self.store.observe(
                    self.plan,
                    foreign,
                    matching,
                    attempt_key="bad-attempt",
                    expected_revision=0,
                )
        with self.assertRaisesRegex(ValueError, "SOURCE_BINDING_MISMATCH"):
            self.store.observe(
                self.plan,
                first,
                replace(matching, content_id=second.content_id),
                attempt_key="wrong-result",
                expected_revision=0,
            )
        # Both rows belong to the same manifest, but an observation for A
        # may never be attached to item B under a valid idempotency key.
        with self.assertRaisesRegex(ValueError, "SOURCE_BINDING_MISMATCH"):
            self.store.observe(
                self.plan,
                second,
                matching,
                attempt_key="foreign-item",
                expected_revision=0,
            )
        self.assertEqual(self.store.read(self.plan).revision, 0)
        with self.assertRaisesRegex(ValueError, "SOURCE_MISMATCH"):
            self.store.lookup(
                self.plan,
                passage_id=first.passage_id,
                content_id=second.content_id,
                capture_id=first.capture_id,
                source_sha256=first.source_sha256,
                passage_sha256=first.passage_sha256,
                selector_fingerprint=first.selector_fingerprint,
                speaker_candidate_id=first.speaker_candidate_id,
            )
        receipt = self.store.lookup(
            self.plan,
            passage_id=first.passage_id,
            content_id=first.content_id,
            capture_id=first.capture_id,
            source_sha256=first.source_sha256,
            passage_sha256=first.passage_sha256,
            selector_fingerprint=first.selector_fingerprint,
            speaker_candidate_id=first.speaker_candidate_id,
        )
        self.assertEqual(receipt.status, "UNOBSERVED")

    def test_cas_conflict_immutable_failures_and_idempotency_key_collision(self):
        self.store.register(self.plan)
        first, second, _ = self.plan.items
        failed = observation(first)
        baseline = PrivateBatchSQLiteStore(self.path).read(self.plan)
        one = self.store.observe(
            self.plan, first, failed, attempt_key="request:1", expected_revision=0
        )
        with self.assertRaisesRegex(ValueError, "REVISION_CONFLICT"):
            PrivateBatchSQLiteStore(self.path).observe(
                self.plan,
                second,
                observation(second),
                attempt_key="request:2",
                expected_revision=baseline.revision,
            )
        with self.assertRaisesRegex(ValueError, "ATTEMPT_REPLAY_CONFLICT"):
            self.store.observe(
                self.plan,
                first,
                observation(first, "CANDIDATE_EXTRACTED"),
                attempt_key="request:1",
                expected_revision=one.revision,
            )
        with self.assertRaisesRegex(ValueError, "ITEM_ALREADY_OBSERVED"):
            self.store.observe(
                self.plan,
                first,
                observation(first, "CANDIDATE_EXTRACTED"),
                attempt_key="request:new",
                expected_revision=one.revision,
            )
        with self.assertRaisesRegex(ValueError, "ATTEMPT_KEY_COLLISION"):
            self.store.observe(
                self.plan,
                second,
                observation(second),
                attempt_key="request:1",
                expected_revision=one.revision,
            )
        self.assertEqual(self.store.read(self.plan), one)
        self.assertEqual(self.store.register(self.plan), one)

    def test_held_or_failed_never_authorizes_later_extraction(self):
        batch = manifest()
        contexts = reviewed_contexts(batch)
        contexts["passage:0"] = replace(
            contexts["passage:0"],
            speech_role="QUOTED_SPEAKER",
            speech_act="REPORTED_QUOTE",
        )
        contexts["passage:1"] = replace(contexts["passage:1"], rights_status="REVOKED")
        held_plan = plan(batch, contexts)
        state = self.store.register(held_plan)
        self.assertEqual(
            [item.status for item in state.index.items],
            [
                "HELD",
                "HELD",
                "UNOBSERVED",
            ],
        )
        for item in held_plan.items[:2]:
            for result in ("FAILED", "CANDIDATE_EXTRACTED"):
                with (
                    self.subTest(item=item, result=result),
                    self.assertRaisesRegex(
                        ValueError, "UNAUTHORIZED_(?:RESULT|SUCCESS)"
                    ),
                ):
                    self.store.observe(
                        held_plan,
                        item,
                        observation(item, result),
                        attempt_key=f"held:{item.passage_id}:{result}",
                        expected_revision=0,
                    )
        self.assertEqual(self.store.read(held_plan), state)

    def test_observed_hold_is_terminal_even_when_plan_originally_proposed_extraction(
        self,
    ):
        self.store.register(self.plan)
        first, second, _ = self.plan.items
        held = self.store.observe(
            self.plan,
            first,
            observation(first, "HELD"),
            attempt_key="attempt:held",
            expected_revision=0,
        )
        self.assertEqual(held.index.items[0].status, "HELD")
        self.assertEqual(held.index.items[0].observation_result, "HELD")
        self.assertEqual(held.index.observed_count, 1)
        with self.assertRaisesRegex(ValueError, "ITEM_ALREADY_OBSERVED"):
            self.store.observe(
                self.plan,
                first,
                observation(first, "CANDIDATE_EXTRACTED"),
                attempt_key="attempt:retry-held",
                expected_revision=held.revision,
            )
        self.assertEqual(
            self.store.observe(
                self.plan,
                second,
                observation(second, "CANDIDATE_EXTRACTED"),
                attempt_key="attempt:unrelated",
                expected_revision=held.revision,
            )
            .index.items[0]
            .status,
            "HELD",
        )

    def test_stored_plan_and_receipts_detect_mutation_not_hash_as_authority(self):
        self.store.register(self.plan)
        first = self.plan.items[0]
        one = self.store.observe(
            self.plan,
            first,
            observation(first),
            attempt_key="one",
            expected_revision=0,
        )
        with self.assertRaisesRegex(ValueError, "PLAN_ORDER_INVALID"):
            self.store.read(replace(self.plan, items=tuple(reversed(self.plan.items))))
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "UPDATE dp240_attempts SET observation_json = ? WHERE plan_sha256 = ?",
                ('{"result":"CANDIDATE_EXTRACTED"}', self.plan.plan_sha256),
            )
        with self.assertRaisesRegex(ValueError, "ATTEMPT_INTEGRITY_INVALID"):
            self.store.read(self.plan)
        self.assertEqual(one.revision, 1)

    def test_loaded_plan_rejects_tampered_person_even_with_valid_sqlite_row(self):
        self.store.register(self.plan)
        original = self.store.load_plan(self.plan.plan_sha256)
        self.assertEqual(original, self.plan)
        with sqlite3.connect(self.path) as connection:
            payload = json.loads(
                connection.execute(
                    "SELECT plan_json FROM dp240_plans WHERE plan_sha256=?",
                    (self.plan.plan_sha256,),
                ).fetchone()[0]
            )
            payload["items"][0]["speaker_candidate_id"] = "person:other"
            connection.execute(
                "UPDATE dp240_plans SET plan_json=? WHERE plan_sha256=?",
                (
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    self.plan.plan_sha256,
                ),
            )
        with self.assertRaisesRegex(ValueError, "PLAN_INTEGRITY_INVALID"):
            self.store.load_plan(self.plan.plan_sha256)
        with self.assertRaisesRegex(ValueError, "PLAN_INTEGRITY_INVALID"):
            self.store.resume(self.plan.plan_sha256)

    def test_failed_transaction_rolls_back_attempt_and_revision_together(self):
        self.store.register(self.plan)
        first = self.plan.items[0]
        # Force the revision CAS UPDATE to abort *after* the attempt INSERT.
        with sqlite3.connect(self.path) as connection:
            connection.execute("""
                CREATE TRIGGER dp240_reject_increment BEFORE UPDATE OF revision
                ON dp240_plans BEGIN SELECT RAISE(ABORT, 'fault-injection'); END;
            """)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "fault-injection"):
            self.store.observe(
                self.plan,
                first,
                observation(first),
                attempt_key="crash:test",
                expected_revision=0,
            )
        self.assertEqual(self.store.read(self.plan).revision, 0)
        self.assertEqual(self.store.read(self.plan).index.observed_count, 0)
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM dp240_attempts").fetchone()[0],
                0,
            )
            connection.execute("DROP TRIGGER dp240_reject_increment")
        self.assertEqual(
            self.store.observe(
                self.plan,
                first,
                observation(first),
                attempt_key="crash:test",
                expected_revision=0,
            ).revision,
            1,
        )

    def test_two_separate_writers_cannot_commit_at_same_revision(self):
        self.store.register(self.plan)
        first, second, _ = self.plan.items
        barrier = Barrier(2)

        def writer(item, key):
            writer_store = PrivateBatchSQLiteStore(self.path)
            barrier.wait(timeout=5)
            try:
                return writer_store.observe(
                    self.plan,
                    item,
                    observation(item),
                    attempt_key=key,
                    expected_revision=0,
                ).revision
            except ValueError as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(writer, first, "writer:first")
            b = pool.submit(writer, second, "writer:second")
            outcomes = (a.result(timeout=10), b.result(timeout=10))
        self.assertEqual(
            sorted(map(str, outcomes)),
            [
                "1",
                "MULTIPERSON_STORE_REVISION_CONFLICT",
            ],
        )
        readback = self.store.read(self.plan)
        self.assertEqual(readback.revision, 1)
        self.assertEqual(readback.index.observed_count, 1)
        self.assertEqual(len(readback.attempts), 1)

    def test_distinct_manifest_replay_does_not_borrow_observed_items(self):
        original = self.store.register(self.plan)
        first = self.plan.items[0]
        committed = self.store.observe(
            self.plan,
            first,
            observation(first),
            attempt_key="original:first",
            expected_revision=original.revision,
        )
        reversed_plan = plan(manifest(reverse=True))
        self.assertEqual(reversed_plan.items[0].passage_id, first.passage_id)
        self.assertNotEqual(reversed_plan.plan_sha256, self.plan.plan_sha256)
        unrelated = self.store.register(reversed_plan)
        self.assertEqual(unrelated.index.observed_count, 0)
        self.assertEqual(unrelated.revision, 0)
        self.assertEqual(self.store.read(self.plan), committed)

    def test_unknown_store_read_never_creates_file_or_persists_private_text(self):
        new_path = self.path.with_name("never-created.sqlite3")
        with self.assertRaisesRegex(ValueError, "PATH_INVALID"):
            PrivateBatchSQLiteStore(new_path).read(self.plan)
        self.assertFalse(new_path.exists())
        self.store.register(self.plan)
        first = self.plan.items[0]
        for malformed in (
            replace(
                observation(first), failure_reason="provider said: raw source words"
            ),
            replace(
                observation(first, "CANDIDATE_EXTRACTED"),
                extraction_version="private quote\ntext",
            ),
        ):
            with (
                self.subTest(malformed=malformed),
                self.assertRaisesRegex(
                    ValueError,
                    "PRIVATE_FIELD_INVALID",
                ),
            ):
                self.store.observe(
                    self.plan,
                    first,
                    malformed,
                    attempt_key="metadata:bad",
                    expected_revision=0,
                )
        self.assertEqual(self.store.read(self.plan).revision, 0)


if __name__ == "__main__":
    unittest.main()
