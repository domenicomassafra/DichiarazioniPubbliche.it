"""Regressions for tools/ci_matrix_capacity.py (DP-602, controlcenter#418).

The capacity report decides whether a per-run cap on the CI matrix is an
improvement. Every assertion below fails on a wrong implementation: a queue time
computed from the wrong timestamp, a cap that is silently ignored, or a replay
that does not actually serialize the shared pool.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ci_matrix_capacity as capacity  # noqa: E402


def job(name: str, labels: list[str], started: str | None, completed: str | None,
        conclusion: str = "success", status: str | None = None) -> dict:
    return {
        "name": name,
        "labels": labels,
        "created_at": "2026-10-20T10:00:00Z",
        "runner_id": 1 if completed else 0,
        "started_at": started,
        "completed_at": completed,
        "conclusion": conclusion,
        "status": status or ("completed" if completed else "queued"),
    }


def run(run_id: int, created: str, updated: str, event: str = "pull_request",
        status: str = "completed") -> dict:
    return {"id": run_id, "created_at": created, "updated_at": updated, "event": event,
            "status": status}


def write_export(directory: Path, runs: list[dict], jobs: dict[int, list[dict]]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "runs.json").write_text(
        json.dumps({"workflow_runs": runs}), encoding="utf-8"
    )
    for run_id, run_jobs in jobs.items():
        (directory / f"jobs-{run_id}.json").write_text(
            json.dumps({"jobs": run_jobs}), encoding="utf-8"
        )
    return directory


MACOS = ["macos-latest"]
UBUNTU = ["ubuntu-latest"]


class RunnerKindTests(unittest.TestCase):
    def test_labels_classify_the_pool(self):
        self.assertEqual(capacity.job_runner_kind(["macos-latest"]), capacity.MACOS)
        self.assertEqual(capacity.job_runner_kind(["ubuntu-latest"]), capacity.UBUNTU)
        self.assertEqual(capacity.job_runner_kind(["self-hosted", "linux"]), capacity.OTHER)
        self.assertEqual(capacity.job_runner_kind(None), capacity.OTHER)


class PercentileTests(unittest.TestCase):
    def test_nearest_rank_is_deterministic(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(capacity.percentile(values, 0.50), 3.0)
        self.assertEqual(capacity.percentile(values, 0.90), 5.0)
        self.assertEqual(capacity.percentile(values, 1.0), 5.0)
        self.assertEqual(capacity.percentile(values, 0.0), 1.0)
        self.assertIsNone(capacity.percentile([], 0.5))


class SummarizeTests(unittest.TestCase):
    def test_queue_is_measured_from_the_job_start_to_the_run_creation(self):
        runs = [run(1, "2026-10-20T10:00:00Z", "2026-10-20T10:08:00Z")]
        jobs = {
            1: [
                job("backend macos-latest / py3.11", MACOS,
                    "2026-10-20T10:03:00Z", "2026-10-20T10:06:00Z"),
                job("backend ubuntu-latest / py3.11", UBUNTU,
                    "2026-10-20T10:00:30Z", "2026-10-20T10:01:00Z"),
            ]
        }
        report = capacity.summarize({str(r["id"]): r for r in runs}, {str(k): v for k, v in jobs.items()})
        self.assertEqual(report["macos"]["queue_median"], 3.0)
        self.assertEqual(report["macos"]["execution_median"], 3.0)
        self.assertEqual(report["ubuntu"]["queue_median"], 0.5)
        self.assertEqual(report["run_wall"]["median"], 6.0)

    def test_queued_job_without_start_is_counted_but_not_timed(self):
        runs = [run(1, "2026-10-20T10:00:00Z", "2026-10-20T10:10:00Z")]
        jobs = {
            1: [
                job("backend macos-latest / py3.11", MACOS, "2026-10-20T10:02:00Z",
                    "2026-10-20T10:05:00Z", "cancelled"),
                job("backend macos-latest / py3.12", MACOS, None, None, "cancelled"),
            ]
        }
        report = capacity.summarize({str(r["id"]): r for r in runs}, {str(k): v for k, v in jobs.items()})
        self.assertEqual(report["macos"]["jobs"], 2)
        self.assertEqual(report["macos"]["queue_median"], 2.0)

    def test_pool_minutes_separate_runs_without_a_verdict(self):
        runs = [
            dict(run(1, "2026-10-20T10:00:00Z", "2026-10-20T10:10:00Z"), conclusion="cancelled"),
            run(2, "2026-10-20T10:00:00Z", "2026-10-20T10:20:00Z"),
        ]
        jobs = {
            1: [job("backend macos-latest / py3.11", MACOS, "2026-10-20T10:00:00Z",
                    "2026-10-20T10:04:00Z", "cancelled")],
            2: [job("backend macos-latest / py3.11", MACOS, "2026-10-20T10:00:00Z",
                    "2026-10-20T10:02:00Z", "success")],
        }
        report = capacity.summarize({str(r["id"]): r for r in runs}, {str(k): v for k, v in jobs.items()})
        pool = report["pool"]
        self.assertAlmostEqual(pool["macos_minutes"], 6.0)
        self.assertAlmostEqual(pool["macos_minutes_without_verdict"], 4.0)
        self.assertAlmostEqual(pool["macos_share_without_verdict"], 4.0 / 6.0)

    def test_a_queued_job_reports_no_queue_it_never_waited(self):
        # GitHub sets started_at when a job is enqueued, so a job with
        # status=queued would otherwise report a zero wait.
        runs = [run(1, "2026-10-20T10:00:00Z", "2026-10-20T10:20:00Z", status="in_progress")]
        jobs = {1: [
            job("backend macos-latest / py3.11", MACOS, "2026-10-20T10:12:00Z", None),
            job("backend macos-latest / py3.12", MACOS, "2026-10-20T10:05:00Z",
                "2026-10-20T10:09:00Z"),
        ]}
        report = capacity.summarize({str(r["id"]): r for r in runs}, {str(k): v for k, v in jobs.items()})
        self.assertEqual(report["macos"]["started"], 1)
        self.assertEqual(report["macos"]["queued_now"], 1)
        self.assertEqual(report["macos"]["queue_median"], 5.0)

    def test_a_run_still_in_flight_has_no_wall_clock(self):
        runs = [run(1, "2026-10-20T10:00:00Z", "2026-10-20T10:00:20Z", status="in_progress")]
        jobs = {1: [job("backend macos-latest / py3.11", MACOS, None, None, "queued")]}
        report = capacity.summarize({str(r["id"]): r for r in runs}, {str(k): v for k, v in jobs.items()})
        self.assertIsNone(report["run_wall"]["median"])
        self.assertEqual(report["macos"]["jobs"], 1)
        self.assertIsNone(report["macos"]["queue_median"])

    def test_utilisation_uses_the_macos_slot_capacity_of_the_window(self):
        runs = [run(1, "2026-10-20T10:00:00Z", "2026-10-20T10:10:00Z")]
        jobs = {1: [job("backend macos-latest / py3.11", MACOS,
                        "2026-10-20T10:00:00Z", "2026-10-20T10:05:00Z")]}
        report = capacity.summarize({str(r["id"]): r for r in runs}, {str(k): v for k, v in jobs.items()})
        # The recorded window ends at the last job, not a later run.updated_at.
        self.assertAlmostEqual(report["pool"]["macos_utilisation"], 5.0 / (5.0 * capacity.MACOS_SLOTS))


class ReplayTests(unittest.TestCase):
    def test_ample_pool_finishes_each_run_in_its_slowest_job(self):
        workload = [
            {"run": "a", "arrival": 0.0, "jobs": [
                {"kind": capacity.MACOS, "name": "m1", "seconds": 4.0},
            ]},
        ]
        result = capacity.replay(workload, macos_slots=5, ubuntu_slots=20)
        self.assertAlmostEqual(result["run_completion_median"], 4.0)
        self.assertAlmostEqual(result["macos_queue_median"], 0.0)

    def test_scarce_pool_serializes_runs_and_produces_a_queue(self):
        workload = [
            {"run": "a", "arrival": 0.0, "jobs": [
                {"kind": capacity.MACOS, "name": "m", "seconds": 4.0}]},
            {"run": "b", "arrival": 0.0, "jobs": [
                {"kind": capacity.MACOS, "name": "m", "seconds": 4.0}]},
        ]
        result = capacity.replay(workload, macos_slots=1, ubuntu_slots=20)
        self.assertAlmostEqual(result["macos_queue_p90"], 4.0)
        self.assertAlmostEqual(result["macos_queue_mean"], 2.0)
        self.assertAlmostEqual(result["run_completion_max"], 8.0)

    def test_per_run_cap_costs_completion_without_adding_capacity(self):
        workload = [
            {"run": "a", "arrival": 0.0, "jobs": [
                {"kind": capacity.MACOS, "name": "m1", "seconds": 4.0},
                {"kind": capacity.MACOS, "name": "m2", "seconds": 4.0},
                {"kind": capacity.UBUNTU, "name": "u1", "seconds": 1.0},
            ]},
        ]
        baseline = capacity.replay(workload, macos_slots=5, ubuntu_slots=20)
        capped = capacity.replay(workload, macos_slots=5, ubuntu_slots=20, macos_per_run=1)
        self.assertAlmostEqual(baseline["run_completion_median"], 4.0)
        self.assertAlmostEqual(capped["run_completion_median"], 8.0)
        self.assertGreater(capped["run_completion_median"], baseline["run_completion_median"])

    def test_needs_linux_delays_the_macos_jobs_of_a_run(self):
        workload = [
            {"run": "a", "arrival": 0.0, "jobs": [
                {"kind": capacity.MACOS, "name": "m1", "seconds": 4.0},
                {"kind": capacity.UBUNTU, "name": "u1", "seconds": 3.0},
            ]},
        ]
        baseline = capacity.replay(workload, macos_slots=5, ubuntu_slots=20)
        gated = capacity.replay(workload, macos_slots=5, ubuntu_slots=20, needs_linux=True)
        self.assertAlmostEqual(baseline["run_completion_median"], 4.0)
        self.assertAlmostEqual(gated["run_completion_median"], 7.0)

    def test_a_held_macos_job_never_holds_the_linux_jobs_behind_it(self):
        # A wrong implementation returns from release() at the first blocked job
        # and the run never finishes: this asserts the Linux job still starts.
        workload = [
            {"run": "a", "arrival": 0.0, "jobs": [
                {"kind": capacity.MACOS, "name": "m1", "seconds": 4.0},
                {"kind": capacity.UBUNTU, "name": "u1", "seconds": 3.0},
            ]},
        ]
        gated = capacity.replay(workload, macos_slots=5, ubuntu_slots=20, needs_linux=True)
        self.assertEqual(gated["runs"], 1)
        self.assertIsNotNone(gated["run_completion_median"])

    def test_replay_is_deterministic(self):
        workload = [
            {"run": "a", "arrival": 0.0, "jobs": [
                {"kind": capacity.MACOS, "name": "m", "seconds": 4.0}]},
            {"run": "b", "arrival": 1.0, "jobs": [
                {"kind": capacity.MACOS, "name": "m", "seconds": 4.0}]},
        ]
        first = capacity.replay(workload, macos_slots=1)
        second = capacity.replay(workload, macos_slots=1)
        self.assertEqual(first, second)


class ExportTests(unittest.TestCase):
    def test_load_export_reads_the_rest_payload_shapes(self):
        directory = write_export(
            Path(self.enterContext(_TempDirectory()).path),
            [run(7, "2026-10-20T10:00:00Z", "2026-10-20T10:05:00Z")],
            {7: [job("backend macos-latest / py3.11", MACOS,
                     "2026-10-20T10:01:00Z", "2026-10-20T10:04:00Z")]},
        )
        runs, jobs = capacity.load_export(directory)
        self.assertEqual(list(runs), ["7"])
        self.assertEqual(len(jobs["7"]), 1)

    def test_build_workload_skips_jobs_without_a_duration(self):
        runs = {"7": run(7, "2026-10-20T10:00:00Z", "2026-10-20T10:05:00Z")}
        jobs = {"7": [job("m", MACOS, None, None, "cancelled"),
                      job("m2", MACOS, "2026-10-20T10:01:00Z", "2026-10-20T10:03:00Z")]}
        workload = capacity.build_workload(runs, jobs)
        self.assertEqual(len(workload), 1)
        self.assertEqual([entry["name"] for entry in workload[0]["jobs"]], ["m2"])

    def test_cli_reports_and_refuses_a_missing_directory(self, ):
        directory = write_export(
            Path(self.enterContext(_TempDirectory()).path),
            [run(7, "2026-10-20T10:00:00Z", "2026-10-20T10:05:00Z")],
            {7: [job("backend macos-latest / py3.11", MACOS,
                     "2026-10-20T10:01:00Z", "2026-10-20T10:04:00Z")]},
        )
        self.assertEqual(capacity.main(["report", "--export", str(directory)]), 0)
        self.assertEqual(capacity.main(["replay", "--export", str(directory), "--max-parallel", "2"]), 0)
        self.assertEqual(capacity.main(["report", "--export", str(directory / "missing")]), 2)


class _TempDirectory:
    """Small helper so a test can use one throwaway directory."""

    def __init__(self) -> None:
        import tempfile

        self._temp = tempfile.TemporaryDirectory()
        self.path = self._temp.name

    def __enter__(self) -> "_TempDirectory":
        return self

    def __exit__(self, *_exc) -> None:
        self._temp.cleanup()


if __name__ == "__main__":
    unittest.main()
