"""Review regressions for controlcenter#418 / PR #235, before policy selection."""
import unittest

from tests.test_ci_matrix_capacity import MACOS, capacity, job, run


class CapacityReviewTests(unittest.TestCase):
    def cancelled_before_assignment(self):
        # REST run 39439000195, macOS jobs 118683584137/270/288/414.
        jobs = [dict(job(f"backend macos-latest / py3.{version}", MACOS,
                         "2026-10-20T14:25:08Z", "2026-10-20T14:35:53Z", "cancelled"),
                     created_at="2026-10-20T14:25:08Z", runner_id=0,
                     runner_name="", steps=[]) for version in range(11, 15)]
        return {"1": run(1, "2026-10-20T14:25:06Z", "2026-10-20T14:35:54Z")}, {"1": jobs}

    def test_cancelled_without_runner_has_no_execution_or_queue_sample(self):
        runs, jobs = self.cancelled_before_assignment()
        report = capacity.summarize(runs, jobs)
        self.assertEqual(report["macos"]["started"], 0)
        self.assertIsNone(report["macos"]["execution_median"])
        self.assertEqual(report["pool"]["macos_minutes"], 0)

    def test_workload_excludes_unexecuted_cancellations(self):
        runs, jobs = self.cancelled_before_assignment()
        self.assertEqual(capacity.build_workload(runs, jobs), [])

    def test_matrix_cap_does_not_throttle_web(self):
        work = [{"run": "a", "arrival": 0, "jobs": [
            {"kind": "macos", "name": "backend macos-latest / py3.11", "seconds": 4},
            {"kind": "macos", "name": "backend macos-latest / py3.12", "seconds": 4},
            {"kind": "ubuntu", "name": "web static frontend", "seconds": 1},
        ]}]
        self.assertEqual(capacity.replay(work, max_parallel=2)["run_completion_median"], 4)

    def test_matrix_cap_with_eight_backend_and_six_independent_jobs(self):
        jobs = [{"kind": kind, "name": f"backend {kind}-latest / py3.{version}", "seconds": 1}
                for kind in ("macos", "ubuntu") for version in range(11, 15)]
        jobs += [{"kind": "ubuntu", "name": f"independent {n}", "seconds": 1} for n in range(6)]
        result = capacity.replay([{"run": "a", "arrival": 0, "jobs": jobs}], max_parallel=2)
        self.assertEqual(result["run_completion_median"], 4)

    def test_queue_uses_job_creation_and_wall_uses_last_job_completion(self):
        runs = {"1": run(1, "2026-10-20T10:00:00Z", "2026-10-20T11:00:00Z")}
        jobs = {"1": [dict(job("backend macos-latest / py3.11", MACOS,
                              "2026-10-20T10:03:00Z", "2026-10-20T10:07:00Z"),
                          created_at="2026-10-20T10:02:00Z", runner_id=1)]}
        report = capacity.summarize(runs, jobs)
        self.assertEqual(report["macos"]["queue_mean"], 1)
        self.assertEqual(report["run_wall"]["median"], 7)

    def test_unmatched_job_export_is_reported_not_counted_as_a_run(self):
        _, jobs = self.cancelled_before_assignment()
        report = capacity.summarize({}, jobs)
        self.assertEqual(report["runs"], 0)
        self.assertEqual(report["unmatched_job_exports"], ["1"])

    def test_cancelled_run_cuts_off_pending_and_busy_jobs(self):
        work = [{"run": "cancelled", "arrival": 0, "cancelled_at": 2, "jobs": [
            {"kind": "macos", "name": "backend macos-latest / py3.11", "seconds": 4},
            {"kind": "macos", "name": "backend macos-latest / py3.12", "seconds": 4},
        ]}, {"run": "next", "arrival": 3, "jobs": [
            {"kind": "macos", "name": "backend macos-latest / py3.11", "seconds": 1},
        ]}]
        result = capacity.replay(work, macos_slots=1)
        self.assertEqual(result["runs"], 1)  # cancellations are not completed verdicts
        self.assertEqual(result["cancelled_runs"], 1)
        self.assertEqual(result["run_completion_max"], 1)
        self.assertEqual(result["macos_minutes"], 3)

    def test_successful_job_in_cancelled_run_counts_as_without_run_verdict(self):
        runs = {"1": dict(run(1, "2026-10-20T10:00:00Z", "2026-10-20T10:05:00Z"),
                          conclusion="cancelled")}
        jobs = {"1": [dict(job("backend macos-latest / py3.11", MACOS,
                              "2026-10-20T10:01:00Z", "2026-10-20T10:04:00Z"), runner_id=1)]}
        self.assertEqual(capacity.summarize(runs, jobs)["pool"]["macos_minutes_without_verdict"], 3)


if __name__ == "__main__":
    unittest.main()
