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

    def test_hardlinked_private_db_and_sqlite_sidecars_are_not_static_assets(self):
        # Same-device hardlinks have a public path and no symlink target to
        # resolve. Before the inode guard anonymous GET returned account bytes.
        sensitive = (self.store.path,)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(self.store.path) + suffix)
            sidecar.write_bytes(("synthetic account " + suffix).encode())
            sensitive += (sidecar,)
        for number, source in enumerate(sensitive):
            alias = self.public / f"public-asset-{number}.html"
            os.link(source, alias)
            for method in ("GET", "HEAD"):
                with self.subTest(source=source.name, method=method):
                    with build_server(
                        None,
                        host="127.0.0.1",
                        port=0,
                        static_dir=self.public,
                        account_service=self.service,
                    ) as server:
                        status, body = self.get(server, f"/{alias.name}", method=method)
                    self.assertNotEqual(status, 200)
                    if method == "HEAD":
                        self.assertEqual(body, b"")
                    self.assertNotIn(b"synthetic@example.invalid", body)

    def test_private_store_hardlinked_as_default_index_is_not_served(self):
        os.link(self.store.path, self.public / "index.html")
        with build_server(
            None,
            host="127.0.0.1",
            port=0,
            static_dir=self.public,
            account_service=self.service,
        ) as server:
            status, body = self.get(server, "/")
        self.assertNotEqual(status, 200)
        self.assertNotIn(b"synthetic@example.invalid", body)

    def test_private_oauth_secret_hardlink_must_not_be_served(self):
        secret_path = self.private / "oauth-secret.txt"
        secret_path.write_text("synthetic-oauth-secret-closed", encoding="utf-8")
        os.link(secret_path, self.public / "visible.css")
        with build_server(
            None,
            host="127.0.0.1",
            port=0,
            static_dir=self.public,
            account_service=self.service,
            account_private_secret_path=secret_path,
        ) as server:
            status, body = self.get(server, "/visible.css")
        self.assertNotEqual(status, 200)
        self.assertNotIn(b"synthetic-oauth-secret-closed", body)

    def test_programmatic_server_rejects_private_secret_inside_static_root(self):
        secret_path = self.public / "private-client-key.txt"
        secret_path.write_text("synthetic-client-key", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ACCOUNT_PRIVATE_FILE_IN_PUBLIC_ROOT"):
            build_server(
                None,
                host="127.0.0.1",
                port=0,
                static_dir=self.public,
                account_service=self.service,
                account_private_secret_path=secret_path,
            )

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
            root_status, root_body = self.get(server, "/")
        self.assertEqual((root_status, root_body), (200, b"PUBLIC TEST PAGE"))
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
