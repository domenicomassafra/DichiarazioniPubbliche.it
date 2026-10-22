"""DP-318 worker relation regressions kept separate from the legacy daemon suite."""

import unittest

from tests import test_worker_daemon as fixtures


class RelationStore(fixtures.FakeStore):
    def __init__(self, jobs):
        super().__init__(jobs)
        self.speaker_person_ids = {}
        self.statement_dates = {}

    def claim_context(self, claim_id):
        row = super().claim_context(claim_id)
        return {
            **row,
            "speaker_person_id": self.speaker_person_ids.get(claim_id),
            "statement_date": self.statement_dates.get(claim_id, "2026-09-21"),
        }


def payload():
    return {
        "prior": {
            "claim_id": "claim:a",
            "statement_date": "2025-01-01",
            "proposition_key": "policy-x",
            "stance": "SUPPORT",
            "scope_start": "2025-01-01",
            "scope_end": "2025-12-31",
        },
        "later": {
            "claim_id": "claim:b",
            "statement_date": "2025-06-01",
            "proposition_key": "policy-x",
            "stance": "OPPOSE",
            "scope_start": "2025-01-01",
            "scope_end": "2025-12-31",
        },
        "estimated_cost_usd": 0,
    }


def run_job(store):
    return fixtures.WorkerDaemonTests().make_worker(store).run(1)


class RelationWorkerJobTests(unittest.TestCase):
    def test_only_private_candidate_with_missing_speaker(self):
        request = payload()
        request["prior"]["statement_date"] = "2026-09-21"
        request["later"]["statement_date"] = "2026-09-21"
        store = RelationStore([fixtures.job("CLASSIFY_CLAIM_RELATION", request)])
        result = run_job(store)
        self.assertEqual(result.completed, 1)
        self.assertEqual(len(store.relation_candidates), 1)
        relation = store.relation_candidates[0]
        self.assertEqual(relation["status"], "CANDIDATE")
        self.assertEqual(relation["relation_type"], "SAME_PROPOSITION")
        self.assertIn(
            "PERSON_ID_UNVERIFIED_NO_POSITION_CHANGE", relation["rationale_codes"]
        )

    def test_persisted_speaker_overrides_forged_payload_identity(self):
        request = payload()
        request["prior"]["person_id"] = "person:forged-same"
        request["later"]["person_id"] = "person:forged-same"
        for speakers, expected in (
            ({"claim:a": "person:a", "claim:b": "person:b"}, "SAME_PROPOSITION"),
            ({"claim:a": "person:a", "claim:b": "person:a"}, "CONTRADICTION_CANDIDATE"),
        ):
            with self.subTest(speakers=speakers):
                store = RelationStore([fixtures.job("CLASSIFY_CLAIM_RELATION", request)])
                store.speaker_person_ids = speakers
                store.statement_dates = {
                    "claim:a": "2025-01-01", "claim:b": "2025-06-01"
                }
                self.assertEqual(run_job(store).completed, 1)
                self.assertEqual(store.relation_candidates[0]["relation_type"], expected)

    def test_same_person_missing_or_invalid_period_cannot_assert_position_change(self):
        # The legacy worker gets person identity from the store, but a job can
        # still supply absent or contradictory temporal scopes. Those cannot
        # substantiate a longitudinal position change.
        for first_scope, second_scope in (
            ({"scope_start": None, "scope_end": None},
             {"scope_start": None, "scope_end": None}),
            ({"scope_end": None}, {}),
            ({"scope_start": "2025-12-31", "scope_end": "2025-01-01"}, {}),
        ):
            with self.subTest(first_scope=first_scope, second_scope=second_scope):
                request = payload()
                request["prior"].update(first_scope)
                request["later"].update(second_scope)
                store = RelationStore([fixtures.job("CLASSIFY_CLAIM_RELATION", request)])
                store.speaker_person_ids = {"claim:a": "person:a", "claim:b": "person:a"}
                store.statement_dates = {
                    "claim:a": "2025-01-01", "claim:b": "2025-06-01"
                }
                self.assertEqual(run_job(store).completed, 1)
                relation = store.relation_candidates[0]
                self.assertEqual(relation["relation_type"], "SAME_PROPOSITION")
                self.assertIn(
                    "TEMPORAL_SCOPE_UNVERIFIED_NO_POSITION_CHANGE", relation["rationale_codes"]
                )

    def test_same_person_with_valid_distinct_periods_keeps_private_candidate(self):
        request = payload()
        request["prior"].update(scope_start="2024-01-01", scope_end="2024-12-31")
        request["later"].update(scope_start="2025-01-01", scope_end="2025-12-31")
        store = RelationStore([fixtures.job("CLASSIFY_CLAIM_RELATION", request)])
        store.speaker_person_ids = {"claim:a": "person:a", "claim:b": "person:a"}
        store.statement_dates = {"claim:a": "2025-01-01", "claim:b": "2025-06-01"}
        self.assertEqual(run_job(store).completed, 1)
        self.assertEqual(
            store.relation_candidates[0]["relation_type"], "POSITION_CHANGE_CANDIDATE"
        )

    def test_rejects_non_boolean_continuity(self):
        for value in ("false", "true", 1, None):
            with self.subTest(value=value):
                request = payload()
                request["later"]["asserts_past_continuity"] = value
                store = RelationStore([fixtures.job("CLASSIFY_CLAIM_RELATION", request)])
                self.assertEqual(run_job(store).blocked, 1)
                self.assertEqual(store.relation_candidates, [])
                self.assertEqual(
                    store.block_reasons["job:CLASSIFY_CLAIM_RELATION"],
                    "RELATION_CONTINUITY_INVALID",
                )

    def test_refuses_forged_or_unknown_persisted_statement_date(self):
        for stored_date, reason in (
            ("2026-09-21", "RELATION_STATEMENT_DATE_MISMATCH"),
            ("", "RELATION_STATEMENT_DATE_UNVERIFIED"),
        ):
            with self.subTest(stored_date=stored_date):
                store = RelationStore([fixtures.job("CLASSIFY_CLAIM_RELATION", payload())])
                store.statement_dates = {
                    "claim:a": stored_date, "claim:b": stored_date
                }
                self.assertEqual(run_job(store).blocked, 1)
                self.assertEqual(store.relation_candidates, [])
                self.assertEqual(
                    store.block_reasons["job:CLASSIFY_CLAIM_RELATION"], reason
                )


if __name__ == "__main__":
    unittest.main()
