"""DP-517 anonymous local HTTP/static-root privacy regression; synthetic only."""

from __future__ import annotations

from contextlib import redirect_stderr
import http.client
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from dichiarazioni_pubbliche.public_account import AccountService, AccountStore
from dichiarazioni_pubbliche.public_api import build_server, main


class _ProviderNotCalled:
    def exchange(self, *args, **kwargs):
        raise AssertionError("No provider calls in DP517 static-root tests")


class AccountStaticExposureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.public = self.base / "public"
        self.public.mkdir()
        self.private = self.base / "private"
        self.private.mkdir(mode=0o700)
        self.store = AccountStore(self.private / "accounts.sqlite3")
        self.store.login("synthetic-sub", "synthetic@example.invalid", 1000)
        self.service = AccountService(
            "test-client.apps.googleusercontent.com",
            "https://dichiarazionipubbliche.it",
            self.store,
            _ProviderNotCalled(),
            visitor_key="synthetic-visitor-key",
        )

    def get(self, server, path, *, method="GET"):
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=3
        )
        try:
            connection.request(
                method, path, headers={"Host": "dichiarazionipubbliche.it"}
            )
            result = connection.getresponse()
            return result.status, result.read()
        finally:
            connection.close()
            server.shutdown()
            thread.join(timeout=3)

    def test_db_under_static_root_cannot_be_downloaded_anonymously(self):
        # Before guard: this setup returned 200 and raw SQLite with private email.
        try:
            server = build_server(
                None,
                host="127.0.0.1",
                port=0,
                static_dir=self.private,
                account_service=self.service,
            )
        except ValueError as exc:
            self.assertIn("ACCOUNT_PRIVATE_FILE_IN_PUBLIC_ROOT", str(exc))
            return
        with server:
            status, body = self.get(server, "/accounts.sqlite3")
        self.assertNotEqual(status, 200)
        self.assertNotIn(b"SQLite format 3", body)
        self.assertNotIn(b"synthetic@example.invalid", body)

    def test_public_symlink_to_private_store_cannot_be_downloaded(self):
        (self.public / "account-backup.sqlite3").symlink_to(self.store.path)
        with build_server(
            None,
            host="127.0.0.1",
            port=0,
            static_dir=self.public,
            account_service=self.service,
        ) as server:
            status, body = self.get(server, "/account-backup.sqlite3")
        self.assertNotEqual(status, 200)
        self.assertNotIn(b"synthetic@example.invalid", body)
        with build_server(
            None,
            host="127.0.0.1",
            port=0,
            static_dir=self.public,
            account_service=self.service,
        ) as server:
            status, body = self.get(server, "/account-backup.sqlite3", method="HEAD")
        self.assertNotEqual(status, 200)
        self.assertEqual(body, b"")

    def test_symlinked_static_root_alias_of_private_db_directory_is_refused(self):
        alias = self.base / "site-alias"
        alias.symlink_to(self.private, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "ACCOUNT_PRIVATE_FILE_IN_PUBLIC_ROOT"):
            build_server(
                None,
                host="127.0.0.1",
                port=0,
                static_dir=alias,
                account_service=self.service,
            )

    def test_safe_static_assets_still_serve_and_account_route_is_private(self):
        (self.public / "index.html").write_text("PUBLIC TEST PAGE", encoding="utf-8")
        with build_server(
            None,
            host="127.0.0.1",
            port=0,
            static_dir=self.public,
            account_service=self.service,
        ) as server:
            status, body = self.get(server, "/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"PUBLIC TEST PAGE")
        with build_server(
            None,
            host="127.0.0.1",
            port=0,
            static_dir=self.public,
            account_service=self.service,
        ) as server:
            status, body = self.get(server, "/index.html", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        with build_server(
            None,
            host="127.0.0.1",
            port=0,
            static_dir=self.public,
            account_service=self.service,
        ) as server:
            status, body = self.get(server, "/account/api/session")
        self.assertEqual(status, 401)
        self.assertNotIn(b"synthetic@example.invalid", body)

    def test_cli_never_starts_with_google_secret_inside_public_static_root(self):
        secret_path = self.public / "client-secret.txt"
        secret_path.write_text("synthetic-google-client-secret", encoding="utf-8")
        os.chmod(secret_path, 0o600)
        args = [
            "--projection-path",
            str(self.base / "dummy-projection.json"),
            "--static-dir",
            str(self.public),
            "--account-client-id",
            "test-client.apps.googleusercontent.com",
            "--account-client-secret-file",
            str(secret_path),
            "--account-db",
            str(self.store.path),
            "--account-site-origin",
            "https://dichiarazionipubbliche.it",
            "--port",
            "0",
        ]
        with (
            patch(
                "dichiarazioni_pubbliche.public_api.build_server",
                side_effect=AssertionError("Unsafe account server was constructed"),
            ),
            redirect_stderr(io.StringIO()) as errors,
        ):
            with self.assertRaises(SystemExit):
                main(args)
        self.assertIn("ACCOUNT_PRIVATE_FILE_IN_PUBLIC_ROOT", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
