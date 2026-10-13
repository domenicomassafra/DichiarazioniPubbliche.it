"""DP-514 disposable CI PostgreSQL wait witness: narrow, redacted, opt-in."""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))
from dichiarazioni_pubbliche.ops import monthly_liability_pg_v1 as liability  # noqa: E402

DISPOSABLE = "postgresql://postgres@127.0.0.1:5432/dp512_test_billing"
PRIVATE = "receipt:private-person password=SECRET_TOKEN provider=PRIVATE_PROVIDER"
DIAGNOSTIC_ENV = {
    "CI": "true",
    "DP514_CI_PG_DIAGNOSTIC": "1",
    "DP514_CI_PG_WAIT_WITNESS": "1",
}
PG_CANCELED = "psql: ERROR:  57014: canceling statement due to statement timeout " + PRIVATE


class FakeWitness:
    instances = []
    samples = [("active", "Lock", "relation", "1", "1")]

    def __init__(self, dsn, app_name):
        self.dsn = dsn
        self.app_name = app_name
        self.started = False
        self.stopped = False
        self.__class__.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True
        return self.samples


class MonthlyLiabilityPgWaitWitnessTests(unittest.TestCase):
    def setUp(self):
        FakeWitness.instances.clear()
        executable = patch(
            "dichiarazioni_pubbliche.ops.billing_pg_fence_v1.shutil.which",
            return_value="/disposable-test-only/psql",
        )
        executable.start()
        self.addCleanup(executable.stop)

    @staticmethod
    def canceled():
        return subprocess.CompletedProcess([], 3, "", PG_CANCELED)

    def test_only_canceled_disposable_snapshot_emits_sanitized_witness(self):
        output = io.StringIO()
        with (
            patch.dict(os.environ, DIAGNOSTIC_ENV),
            patch.object(liability, "_CiWaitWitness", FakeWitness),
            patch.object(liability.subprocess, "run", return_value=self.canceled()) as run,
            redirect_stderr(output),
            self.assertRaisesRegex(RuntimeError, "^DP514_PG_TRANSACTION_FAILED$"),
        ):
            liability.DisposableMonthlyLiabilityPg(DISPOSABLE)._snapshot()
        log = output.getvalue()
        self.assertEqual(len(FakeWitness.instances), 1)
        self.assertTrue(FakeWitness.instances[0].started)
        self.assertTrue(FakeWitness.instances[0].stopped)
        self.assertIn("DP514_CI_PG_WAIT_WITNESS", log)
        self.assertIn("samples=1", log)
        self.assertIn("wait_type=Lock", log)
        self.assertIn("wait_event=relation", log)
        self.assertIn("ungranted_lock=1", log)
        self.assertIn("blocker=1", log)
        self.assertIn("sqlstate=57014", log)
        self.assertEqual(run.call_count, 1)
        self.assertRegex(run.call_args.kwargs["env"]["PGAPPNAME"],
                         r"^dp514_ci_snapshot_[0-9a-f]{32}$")
        self.assertEqual(FakeWitness.instances[0].app_name,
                         run.call_args.kwargs["env"]["PGAPPNAME"])
        for sensitive in (PRIVATE, "SECRET_TOKEN", "PRIVATE_PROVIDER", "receipt:", "SELECT", "STATEMENT", DISPOSABLE):
            self.assertNotIn(sensitive, log)

    def test_disabled_or_other_operation_never_starts_sampler(self):
        options = (
            ({**DIAGNOSTIC_ENV, "DP514_CI_PG_WAIT_WITNESS": "0"}, "SNAPSHOT"),
            ({**DIAGNOSTIC_ENV, "DP514_CI_PG_DIAGNOSTIC": "0"}, "SNAPSHOT"),
            ({**DIAGNOSTIC_ENV, "CI": "false"}, "SNAPSHOT"),
            (DIAGNOSTIC_ENV, "APPEND"),
        )
        for env, family in options:
            output = io.StringIO()
            with (
                self.subTest(env=env, family=family),
                patch.dict(os.environ, env),
                patch.object(liability, "_CiWaitWitness", FakeWitness),
                patch.object(liability.subprocess, "run", return_value=self.canceled()) as run,
                redirect_stderr(output),
                self.assertRaisesRegex(RuntimeError, "^DP514_PG_TRANSACTION_FAILED$"),
            ):
                liability.DisposableMonthlyLiabilityPg(DISPOSABLE)._run("SELECT 1", _family=family)
            self.assertEqual(len(FakeWitness.instances), 0)
            self.assertNotIn("DP514_CI_PG_WAIT_WITNESS", output.getvalue())
            self.assertNotIn("env", run.call_args.kwargs)

    def test_non_57014_failure_and_success_do_not_print_witness(self):
        for reply in (
            subprocess.CompletedProcess([], 3, "", "ERROR:  55P03: blocked"),
            subprocess.CompletedProcess([], 0, "[]", ""),
        ):
            output = io.StringIO()
            with (
                self.subTest(code=reply.returncode),
                patch.dict(os.environ, DIAGNOSTIC_ENV),
                patch.object(liability, "_CiWaitWitness", FakeWitness),
                patch.object(liability.subprocess, "run", return_value=reply),
                redirect_stderr(output),
            ):
                try:
                    result = liability.DisposableMonthlyLiabilityPg(DISPOSABLE)._snapshot()
                    self.assertEqual(result, [])
                except RuntimeError as exc:
                    self.assertEqual(str(exc), "DP514_PG_TRANSACTION_FAILED")
                self.assertNotIn("DP514_CI_PG_WAIT_WITNESS", output.getvalue())
                self.assertTrue(FakeWitness.instances[-1].stopped)

    def test_probe_reads_only_metadata_and_rejects_untrusted_values(self):
        app = "dp514_ci_snapshot_" + "a" * 32
        good = subprocess.CompletedProcess([], 0, "active|IO|DataFileRead|0|0\n", "")
        with patch.object(liability.subprocess, "run", return_value=good) as run:
            self.assertEqual(liability._ci_wait_probe(DISPOSABLE, app),
                             ("active", "IO", "DataFileRead", "0", "0"))
        args = run.call_args.args[0]
        self.assertIn("pg_stat_activity", args[-1])
        self.assertIn("pg_locks", args[-1])
        self.assertIn("pg_blocking_pids", args[-1])
        self.assertIn("application_name", args[-1])
        self.assertIn(app, args[-1])
        self.assertIn("LIMIT 2", args[-1])
        self.assertNotIn("LIMIT 1", args[-1])
        self.assertEqual(run.call_args.kwargs["timeout"], 1)
        for unsafe in (
            "active|Lock|relation|1|1\n" + PRIVATE,
            "active|Lock|relation|UNKNOWN|1\n",
        ):
            with (
                self.subTest(unsafe=unsafe),
                patch.object(liability.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, unsafe, "")),
            ):
                self.assertIsNone(liability._ci_wait_probe(DISPOSABLE, app))
        with patch.object(
            liability.subprocess, "run",
            return_value=subprocess.CompletedProcess([], 0, "active|Lock|" + PRIVATE + "|1|1\n", ""),
        ):
            self.assertEqual(liability._ci_wait_probe(DISPOSABLE, app),
                             ("active", "Lock", "OTHER", "1", "1"))

    def test_two_concurrent_matching_backends_fail_closed(self):
        app = "dp514_ci_snapshot_" + "a" * 32
        # Backend B is blocked, A is not. Returning B's sample for A would
        # misdiagnose an unrelated 57014 under the historical LIMIT 1 query.
        multiple = subprocess.CompletedProcess(
            [], 0, "active|IO|DataFileRead|0|0\nactive|Lock|relation|1|1\n", "",
        )
        with patch.object(liability.subprocess, "run", return_value=multiple) as run:
            self.assertIsNone(liability._ci_wait_probe(DISPOSABLE, app))
        self.assertIn("LIMIT 2", run.call_args.args[0][-1])

    def test_parallel_snapshots_use_distinct_private_application_names(self):
        barrier = threading.Barrier(2)
        names = []
        gate = threading.Lock()

        def two_in_flight(*args, **kwargs):
            with gate:
                names.append(kwargs["env"]["PGAPPNAME"])
            barrier.wait(timeout=4)
            return self.canceled()

        logged = io.StringIO()
        with (
            patch.dict(os.environ, DIAGNOSTIC_ENV),
            patch.object(liability, "_CiWaitWitness", FakeWitness),
            patch.object(liability.subprocess, "run", side_effect=two_in_flight),
            redirect_stderr(logged),
        ):
            def canceled_snapshot():
                with self.assertRaisesRegex(RuntimeError, "^DP514_PG_TRANSACTION_FAILED$"):
                    liability.DisposableMonthlyLiabilityPg(DISPOSABLE)._snapshot()

            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda _: canceled_snapshot(), range(2)))
        self.assertEqual(len(names), 2)
        self.assertNotEqual(names[0], names[1])
        self.assertEqual(set(names), {w.app_name for w in FakeWitness.instances})
        self.assertTrue(all(re.fullmatch(r"dp514_ci_snapshot_[0-9a-f]{32}", n)
                            for n in names))
        self.assertEqual(logged.getvalue().count("DP514_CI_PG_WAIT_WITNESS"), 2)
        for name in names:
            self.assertNotIn(name, logged.getvalue())

    def test_probe_error_and_non_disposable_dsn_fail_closed(self):
        app = "dp514_ci_snapshot_" + "a" * 32
        for failure in (
            subprocess.CompletedProcess([], 3, "", "ERROR: " + PRIVATE),
            subprocess.TimeoutExpired("psql", 1),
        ):
            result = failure if isinstance(failure, subprocess.CompletedProcess) else None
            error = None if result is not None else failure
            with (
                self.subTest(failure=type(failure).__name__),
                patch.object(liability.subprocess, "run", return_value=result, side_effect=error),
            ):
                self.assertIsNone(liability._ci_wait_probe(DISPOSABLE, app))
        with patch.object(liability.subprocess, "run") as run:
            self.assertIsNone(liability._ci_wait_probe("postgresql://postgres@127.0.0.1:5432/production", app))
            self.assertIsNone(liability._ci_wait_probe(DISPOSABLE, "dp514_ci_snapshot_' OR TRUE--"))
        run.assert_not_called()

    def test_missing_samples_or_injected_private_metadata_fail_closed(self):
        self.assertEqual(liability._ci_wait_summary([]), "status=NO_SAMPLE samples=0")
        self.assertEqual(liability._ci_wait_summary(
            [("active", "Lock", PRIVATE, "1", "1")]
        ), "status=NO_SAMPLE samples=0")

    def test_transient_blocker_does_not_override_last_cleared_wait(self):
        samples = [("active", "Lock", "relation", "1", "1")]
        samples.extend([("active", "Timeout", "PgSleep", "0", "0")] * 15)
        summary = liability._ci_wait_summary(samples)
        self.assertIn("status=OBSERVED samples=16", summary)
        self.assertIn("wait_type=Timeout wait_event=PgSleep", summary)
        self.assertIn("ungranted_lock=0 blocker=0", summary)
        self.assertIn("historical_blocker_seen=1", summary)
        self.assertNotIn("wait_type=Lock", summary)

    def test_last_sample_blocker_remains_visible(self):
        samples = [ ("active", "Timeout", "PgSleep", "0", "0") ] * 15
        samples.append(("active", "Lock", "relation", "1", "1"))
        summary = liability._ci_wait_summary(samples)
        self.assertIn("wait_type=Lock wait_event=relation", summary)
        self.assertIn("ungranted_lock=1 blocker=1", summary)
        self.assertIn("historical_blocker_seen=0", summary)


if __name__ == "__main__":
    unittest.main()
