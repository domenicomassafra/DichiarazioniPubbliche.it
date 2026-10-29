import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ops import provider_outage_drill as drill  # noqa: E402
from dichiarazioni_pubbliche.ops.provider_outage_drill import OutageClaimClient  # noqa: E402


class ProviderOutageClientTests(unittest.TestCase):
    def test_missing_credential_is_unhealthy_and_explicit(self):
        probe = OutageClaimClient("credential").probe()
        self.assertFalse(probe.healthy)
        self.assertEqual(probe.reason, "OMNIROUTE_API_KEY_MISSING")
        self.assertIsNone(probe.http_status)

    def test_http_failure_is_unhealthy_and_explicit(self):
        probe = OutageClaimClient("http").probe()
        self.assertFalse(probe.healthy)
        self.assertTrue(probe.reason.startswith("OMNIROUTE_HTTP_"))
        self.assertEqual(probe.http_status, 400)

    def test_extract_is_a_loud_invariant_violation_during_outage(self):
        client = OutageClaimClient("http")
        with self.assertRaisesRegex(RuntimeError, "DRILL_INVARIANT_VIOLATION"):
            client.extract()
        self.assertEqual(client.extract_calls, 1)

    def test_blank_explicit_url_never_reaches_psql_even_with_database_env(self):
        # Intercept the real PsqlRuntime runner: absolutely no database connection.
        for database_url in ("", " \t "):
            with self.subTest(database_url=repr(database_url)):
                intercepted_argv = []

                def fake_psql(argv, *_):
                    intercepted_argv.append(argv)
                    raise RuntimeError("fake psql: no database may be contacted")

                with (
                    patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_DATABASE_URL": "postgresql:///env-db"}),
                    patch("dichiarazioni_pubbliche.queue_runtime.execute_psql", side_effect=fake_psql),
                    redirect_stderr(io.StringIO()),
                ):
                    result = drill.main([
                        "--database-url", database_url,
                        "--registry", str(ROOT / "config" / "source-registry.v1.json"),
                    ])
                self.assertEqual(result, 2)
                self.assertEqual(intercepted_argv, [], "unsafe psql argv was constructed/executed")

    def test_shell_wrapper_never_invokes_mock_psql_for_blank_explicit_url(self):
        # Run the real wrapper with psql replaced by a recording stub in PATH.
        with tempfile.TemporaryDirectory() as tmp:
            fakebin = Path(tmp)
            psql_log = fakebin / "psql-argv.log"
            for name, script in (
                ("python3", '#!/bin/sh\nexec "$DRILL_TEST_PYTHON" "$@"\n'),
                ("psql", '#!/bin/sh\nprintf "%s\\n" "$@" >> "$DRILL_PSQL_ARGV_LOG"\nexit 77\n'),
            ):
                tool = fakebin / name
                tool.write_text(script)
                tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env.update({
                "PATH": str(fakebin) + os.pathsep + env.get("PATH", ""),
                "DRILL_TEST_PYTHON": sys.executable,
                "DRILL_PSQL_ARGV_LOG": str(psql_log),
                "DICHIARAZIONI_PUBBLICHE_DATABASE_URL": "postgresql:///env-db",
            })
            for value in ("", " \t "):
                with self.subTest(database_url=repr(value)):
                    proc = subprocess.run(
                        ["sh", str(ROOT / "deploy" / "ops" / "provider_outage_drill.sh"),
                         "--database-url", value],
                        env=env, capture_output=True, text=True, timeout=15, check=False,
                    )
                    self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                    self.assertFalse(psql_log.exists(), "shell wrapper invoked mock psql")

    def test_omitted_url_uses_environment_but_explicit_valid_url_wins(self):
        registry = str(ROOT / "config" / "source-registry.v1.json")
        for argv, expected_url in (
            (["--registry", registry], "postgresql:///env-db"),
            (["--database-url", "postgresql:///explicit-db", "--registry", registry],
             "postgresql:///explicit-db"),
        ):
            with self.subTest(argv=argv):
                with (
                    patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_DATABASE_URL": "postgresql:///env-db"}),
                    patch.object(drill, "run_drill", side_effect=RuntimeError("mock runner")) as runner,
                    redirect_stderr(io.StringIO()),
                ):
                    self.assertEqual(drill.main(argv), 2)
                runner.assert_called_once_with(expected_url, ROOT / "config" / "source-registry.v1.json", "credential", 2)

    def test_omitted_url_without_environment_fails_before_runner(self):
        with (
            patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_DATABASE_URL": ""}),
            patch.object(drill, "run_drill") as runner,
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(drill.main(["--registry", str(ROOT / "config" / "source-registry.v1.json")]), 2)
        runner.assert_not_called()

    def test_omitted_url_with_blank_environment_fails_before_runner(self):
        for value in ("", " \t "):
            with self.subTest(environment=repr(value)):
                with (
                    patch.dict(os.environ, {"DICHIARAZIONI_PUBBLICHE_DATABASE_URL": value}),
                    patch.object(drill, "run_drill") as runner,
                    redirect_stderr(io.StringIO()),
                ):
                    self.assertEqual(drill.main([
                        "--registry", str(ROOT / "config" / "source-registry.v1.json")
                    ]), 2)
                runner.assert_not_called()

    def test_shell_driver_uses_real_worker_drill_module(self):
        script = (ROOT / "deploy" / "ops" / "provider_outage_drill.sh").read_text()
        self.assertIn("dichiarazioni_pubbliche.ops.provider_outage_drill", script)
        self.assertIn("--database-url", script)
        self.assertNotIn("switch provider", script.lower())


if __name__ == "__main__":
    unittest.main()
