"""DP-203: accepted parent work advances in bounded, replayable batches."""

import unittest

from tests import test_worker_daemon as worker_fixtures

from tests.test_worker_daemon import (
    FakeClaimClient,
    FakeStore,
    job,
)
from dichiarazioni_pubbliche.queue_runtime import ProcessingJob


class BatchStore(FakeStore):
    def enqueue_jobs_bulk(self, jobs):
        seen = {row["id"] for row in self.bulk_jobs}
        added = [row for row in jobs if row["id"] not in seen]
        self.bulk_jobs.extend(added)
        return len(added)

    def unfinished_sibling_jobs(self, *, content_id, job_type, exclude_job_id):
        return sum(
            row["content_id"] == content_id
            and row["job_type"] == job_type
            and row["id"] != exclude_job_id
            and self.states.get(row["id"]) != "COMPLETED"
            for row in self.bulk_jobs
        )


def segments(count):
    return [
        {
            "id": f"canonical:{index}",
            "segment_index": index,
            "start_ms": index * 120_000,
            "end_ms": index * 120_000 + 1000,
            "canonical_text": f"La dichiarazione {index} contiene un fatto verificabile.",
            "transcript_status": "RESOLVED",
            "publication_blocked": False,
            "sensitive_signature": [],
        }
        for index in range(count)
    ]


class ControlledFanoutTests(unittest.TestCase):
    def worker(self, store, *, enabled=False, size=2, client=None):
        helper = worker_fixtures.WorkerDaemonTests()
        worker = helper.make_worker(
            store, claim_client=client or FakeClaimClient(), claim_rate=0.15
        )
        worker.claim_fanout_verified = enabled
        worker.claim_window_batch_size = size
        return worker

    def test_remote_claim_jobs_hold_until_upstream_acceptance(self):
        store = BatchStore([job("CLAIM_PREPARE", {"variant_id": "v1"})])
        store.canonical_rows = segments(5)
        client = FakeClaimClient()
        result = self.worker(store, client=client).run(1)
        self.assertEqual(result.blocked, 1)
        self.assertEqual(store.bulk_jobs, [])
        self.assertEqual(client.extracts, 0)
        self.assertIn("CLAIM_FANOUT", store.block_reasons["job:CLAIM_PREPARE"])

    def test_parent_releases_two_windows_only_after_previous_batch_finishes(self):
        store = BatchStore([job("CLAIM_PREPARE", {"variant_id": "v1"})])
        store.canonical_rows = segments(5)
        worker = self.worker(store, enabled=True)
        self.assertEqual(worker.run(1).completed, 1)
        self.assertEqual(len(store.bulk_jobs), 2)
        self.assertEqual(store.followups, [])

        for start, end in ((0, 2), (2, 4), (4, 5)):
            for child in store.bulk_jobs[start:end]:
                store.jobs.append(ProcessingJob(
                    job_id=child["id"], content_id=child["content_id"],
                    job_type=child["job_type"], attempt=1,
                    payload=child["payload"],
                ))
            worker.run(end - start - 1)
            self.assertEqual(len(store.bulk_jobs), end)
            self.assertEqual(len(store.followups), start // 2)
            worker.run(1)
            if end < 5:
                self.assertEqual(len(store.followups), end // 2)
                continuation = store.followups[-1]
                self.assertEqual(continuation["payload"]["claim_window_offset"], end)
                store.jobs.append(ProcessingJob(
                    job_id=f"job:prepare:{end}",
                    content_id="content:pulp64", job_type="CLAIM_PREPARE",
                    attempt=1, payload=continuation["payload"],
                ))
                worker.run(1)
                self.assertEqual(len(store.bulk_jobs), min(end + 2, 5))

        self.assertEqual(len(store.bulk_jobs), 5)
        self.assertEqual(len(store.followups), 2)
        self.assertEqual(store.status_updates[-1][1], "CLAIMS_EXTRACTED")

    def test_parent_replay_preserves_existing_window_ids(self):
        store = BatchStore([job("CLAIM_PREPARE", {"variant_id": "v1"})])
        store.canonical_rows = segments(4)
        worker = self.worker(store, enabled=True)
        worker.run(1)
        first_ids = [row["id"] for row in store.bulk_jobs]
        store.jobs.append(job("CLAIM_PREPARE", {"variant_id": "v1"}))
        worker.run(1)
        self.assertEqual([row["id"] for row in store.bulk_jobs], first_ids)

    def test_changed_canonical_windows_hold_a_followup_without_enqueuing(self):
        store = BatchStore([job("CLAIM_PREPARE", {"variant_id": "v1"})])
        store.canonical_rows = segments(3)
        worker = self.worker(store, enabled=True)
        worker.run(1)
        first = store.bulk_jobs[0]["payload"]
        store.canonical_rows[2]["canonical_text"] = "Questa fonte è cambiata."
        store.jobs.append(job("CLAIM_PREPARE", {
            "variant_id": "v1", "claim_window_offset": 2,
            "claim_batch_manifest_sha256": first["claim_batch_manifest_sha256"],
        }))
        result = worker.run(1)
        self.assertEqual(result.blocked, 1)
        self.assertEqual(len(store.bulk_jobs), 2)
        self.assertIn("CLAIM_BATCH_MANIFEST_DRIFT", store.block_reasons["job:CLAIM_PREPARE"])

    def test_model_change_between_batches_holds_remaining_windows(self):
        store = BatchStore([job("CLAIM_PREPARE", {"variant_id": "v1"})])
        store.canonical_rows = segments(3)
        client = FakeClaimClient()
        worker = self.worker(store, enabled=True, client=client)
        worker.run(1)
        first = store.bulk_jobs[0]["payload"]
        client.model = "unapproved-new-model"
        store.jobs.append(job("CLAIM_PREPARE", {
            "variant_id": "v1", "claim_window_offset": 2,
            "claim_batch_manifest_sha256": first["claim_batch_manifest_sha256"],
        }))
        self.assertEqual(worker.run(1).blocked, 1)
        self.assertEqual(len(store.bulk_jobs), 2)
        self.assertEqual(store.block_reasons["job:CLAIM_PREPARE"], "CLAIM_BATCH_MANIFEST_DRIFT")

    def test_queued_window_holds_before_provider_when_model_or_prompt_drifts(self):
        for field, changed_value in (("model", "other-model"),
                                     ("prompt_version", "other-prompt")):
            with self.subTest(field=field):
                store = BatchStore([job("CLAIM_PREPARE", {"variant_id": "v1"})])
                store.canonical_rows = segments(3)
                client = FakeClaimClient()
                worker = self.worker(store, enabled=True, client=client)
                self.assertEqual(worker.run(1).completed, 1)
                queued = store.bulk_jobs[0]
                setattr(client, field, changed_value)
                store.jobs.append(ProcessingJob(
                    job_id=queued["id"], content_id=queued["content_id"],
                    job_type=queued["job_type"], attempt=1,
                    payload=queued["payload"],
                ))
                self.assertEqual(worker.run(1).blocked, 1)
                self.assertEqual(client.extracts, 0)
                self.assertEqual(store.budget_reservations, [])
                self.assertEqual(store.block_reasons[queued["id"]],
                                 "CLAIM_WINDOW_CLIENT_DRIFT")

    def test_retryable_provider_outage_never_unlocks_next_batch(self):
        class OutageClient(FakeClaimClient):
            def extract(self, **kwargs):
                self.extracts += 1
                raise RuntimeError("HTTP_503")

        store = BatchStore([job("CLAIM_PREPARE", {"variant_id": "v1"})])
        store.canonical_rows = segments(3)
        client = OutageClient()
        worker = self.worker(store, enabled=True, client=client)
        worker.run(1)
        for child in store.bulk_jobs:
            store.jobs.append(ProcessingJob(
                job_id=child["id"], content_id=child["content_id"],
                job_type=child["job_type"], attempt=1,
                payload=child["payload"],
            ))
        result = worker.run(2)
        self.assertEqual(result.retried, 2)
        self.assertEqual(len(store.bulk_jobs), 2)
        self.assertEqual(store.followups, [])
        self.assertEqual(store.receipts, [])

    def test_invalid_continuation_leaves_explicit_hold_after_last_completion(self):
        store = BatchStore([job("CLAIM_PREPARE", {"variant_id": "v1"})])
        store.canonical_rows = segments(3)
        worker = self.worker(store, enabled=True)
        worker.run(1)
        for child in store.bulk_jobs:
            payload = {**child["payload"], "claim_batch_next_offset": -1}
            store.jobs.append(ProcessingJob(
                job_id=child["id"], content_id=child["content_id"],
                job_type=child["job_type"], attempt=1, payload=payload,
            ))
        result = worker.run(2)
        self.assertEqual(result.completed, 2)
        self.assertEqual(store.followups, [])
        self.assertEqual(store.status_updates[-1][1], "CLAIM_EXTRACTION_BLOCKED")
        self.assertEqual(
            store.status_updates[-1][2]["runtime_blocker"],
            "CLAIM_BATCH_CONTINUATION_INVALID",
        )


if __name__ == "__main__":
    unittest.main()
