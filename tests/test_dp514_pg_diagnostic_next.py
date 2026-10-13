"""DP514: opt-in, metadata-only CI diagnostics for disposable PG failures."""

from __future__ import annotations

import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))
from dichiarazioni_pubbliche.ops.monthly_liability_pg_v1 import (  # noqa: E402
    DisposableMonthlyLiabilityPg,
)

DISPOSABLE = "postgresql://postgres@127.0.0.1:5432/dp512_test_billing"
PRIVATE = "receipt:private-person password=DO_NOT_LOG provider=PRIVATE_API_KEY"


class MonthlyLiabilityPgDiagnosticTests(unittest.TestCase):
    def setUp(self):
        # The entire unit surface mocks psql subprocess.run, including the
        # success path. Also mock the existing executable-presence preflight:
        # macOS CI deliberately does not install PostgreSQL binaries, and a
        # synthetic test must not depend on an external CLI installation.
        executable = patch(
            "dichiarazioni_pubbliche.ops.billing_pg_fence_v1.shutil.which",
            return_value="/disposable-test-only/psql",
        )
        executable.start()
        self.addCleanup(executable.stop)

    def fail_psql(self, *, code=3, stderr=""):
        return subprocess.CompletedProcess([], code, "", stderr)

    def test_opt_in_verbose_sqlstate_and_secret_redaction(self):
        secret_error = (
            "psql: ERROR:  57014: canceling statement due to statement timeout "
            + PRIVATE
            + "\nSTATEMENT: SELECT * FROM private_receipts\n"
        )
        captured = io.StringIO()
        with (
            patch.dict(os.environ, {"CI": "true", "DP514_CI_PG_DIAGNOSTIC": "1"}),
            patch(
                "dichiarazioni_pubbliche.ops.monthly_liability_pg_v1.subprocess.run",
                return_value=self.fail_psql(stderr=secret_error),
            ) as run,
            redirect_stderr(captured),
            self.assertRaisesRegex(RuntimeError, "^DP514_PG_TRANSACTION_FAILED$"),
        ):
            DisposableMonthlyLiabilityPg(DISPOSABLE)._snapshot()
        logged = captured.getvalue()
        self.assertIn("DP514_CI_PG_DIAGNOSTIC", logged)
        self.assertIn("operation=SNAPSHOT", logged)
        self.assertIn("sqlstate=57014", logged)
        self.assertIn("exit_code=3", logged)
        self.assertIn("category=QUERY_CANCELED", logged)
        self.assertRegex(logged, r"elapsed_ms=\d{1,5}\b")
        for secret in (
            PRIVATE,
            "DO_NOT_LOG",
            "private_receipts",
            "STATEMENT",
            "SELECT",
        ):
            self.assertNotIn(secret, logged)
        self.assertIn("VERBOSITY=verbose", run.call_args.args[0])

    def test_ineligible_environments_and_non_disposable_urls_silent(self):
        configurations = (
            ({"CI": "false", "DP514_CI_PG_DIAGNOSTIC": "1"}, DISPOSABLE),
            ({"CI": "true", "DP514_CI_PG_DIAGNOSTIC": "0"}, DISPOSABLE),
            (
                {"CI": "true", "DP514_CI_PG_DIAGNOSTIC": "1"},
                "postgresql://postgres:secret@127.0.0.1:5432/dp512_test_billing",
            ),
        )
        for environment, dsn in configurations:
            with self.subTest(environment=environment, dsn=dsn):
                captured = io.StringIO()
                with (
                    patch.dict(os.environ, environment),
                    patch(
                        "dichiarazioni_pubbliche.ops.monthly_liability_pg_v1.subprocess.run",
                        return_value=self.fail_psql(stderr=PRIVATE),
                    ) as run,
                    redirect_stderr(captured),
                    self.assertRaisesRegex(
                        RuntimeError, "^DP514_PG_TRANSACTION_FAILED$"
                    ),
                ):
                    DisposableMonthlyLiabilityPg(dsn)._snapshot()
                self.assertEqual(captured.getvalue(), "")
                self.assertNotIn("VERBOSITY=verbose", run.call_args.args[0])

    def test_rejects_non_disposable_dsn_before_any_psql(self):
        for dsn in (
            "postgresql://postgres@127.0.0.1:5432/production",
            "postgresql://other.host:5432/dp512_test_billing",
        ):
            with (
                self.subTest(dsn=dsn),
                self.assertRaisesRegex(ValueError, "BILLING_DISPOSABLE_DSN_REQUIRED"),
            ):
                DisposableMonthlyLiabilityPg(dsn)

    def test_unrecognized_sqlstate_and_other_error_secrets_are_never_echoed(self):
        captured = io.StringIO()
        with (
            patch.dict(os.environ, {"CI": "true", "DP514_CI_PG_DIAGNOSTIC": "1"}),
            patch(
                "dichiarazioni_pubbliche.ops.monthly_liability_pg_v1.subprocess.run",
                return_value=self.fail_psql(code=7, stderr="ERROR:  99999: " + PRIVATE),
            ),
            redirect_stderr(captured),
            self.assertRaisesRegex(RuntimeError, "^DP514_PG_TRANSACTION_FAILED$"),
        ):
            DisposableMonthlyLiabilityPg(DISPOSABLE)._snapshot()
        logged = captured.getvalue()
        self.assertIn("sqlstate=UNKNOWN", logged)
        self.assertIn("category=UNKNOWN", logged)
        self.assertIn("exit_code=7", logged)
        self.assertNotIn(PRIVATE, logged)
        self.assertNotIn("99999", logged)

    def test_expected_domain_error_is_unchanged_and_emits_no_diagnostic(self):
        captured = io.StringIO()
        with (
            patch.dict(os.environ, {"CI": "true", "DP514_CI_PG_DIAGNOSTIC": "1"}),
            patch(
                "dichiarazioni_pubbliche.ops.monthly_liability_pg_v1.subprocess.run",
                return_value=self.fail_psql(
                    stderr="ERROR: DP514_REVISION_CONFLICT " + PRIVATE
                ),
            ),
            redirect_stderr(captured),
            self.assertRaisesRegex(ValueError, "^DP514_REVISION_CONFLICT$"),
        ):
            DisposableMonthlyLiabilityPg(DISPOSABLE)._run("SELECT 1")
        self.assertEqual(captured.getvalue(), "")

    def test_success_path_keeps_result_unmodified(self):
        with (
            patch.dict(os.environ, {"CI": "true", "DP514_CI_PG_DIAGNOSTIC": "1"}),
            patch(
                "dichiarazioni_pubbliche.ops.monthly_liability_pg_v1.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, "  []\n", ""),
            ),
        ):
            self.assertEqual(DisposableMonthlyLiabilityPg(DISPOSABLE)._snapshot(), [])


if __name__ == "__main__":
    unittest.main()
