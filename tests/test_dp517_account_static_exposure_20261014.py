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

    def test_account_disabled_does_not_reenable_private_symlink_or_hardlink(self):
        # Disabling account routes is not a grant to expose leftover private
        # account files through the static server on rollback/restart.
        (self.public / "private-link.html").symlink_to(self.store.path)
        os.link(self.store.path, self.public / "private-alias.html")
        for relative in ("private-link.html", "private-alias.html"):
            for method in ("GET", "HEAD"):
                with self.subTest(relative=relative, method=method):
                    with build_server(
                        None, static_dir=self.public, account_service=None,
                    ) as server:
                        status, body = self.get(server, f"/{relative}", method=method)
                    self.assertNotEqual(status, 200)
                    self.assertNotIn(b"synthetic@example.invalid", body)

    def test_account_disabled_never_serves_private_db_index_or_sqlite_name(self):
        os.link(self.store.path, self.public / "index.html")
        for method in ("GET", "HEAD"):
            with build_server(None, static_dir=self.public, account_service=None) as server:
                status, body = self.get(server, "/", method=method)
            self.assertNotEqual(status, 200)
            self.assertNotIn(b"synthetic@example.invalid", body)
        (self.public / "index.html").unlink()
        (self.public / "backup.sqlite3").write_bytes(b"SQLite format 3\x00private")
        with build_server(None, static_dir=self.public, account_service=None) as server:
            status, body = self.get(server, "/backup.sqlite3")
        self.assertNotEqual(status, 200)
        self.assertNotIn(b"SQLite format 3", body)

    def test_account_rollback_does_not_expose_hidden_config_or_credential_paths(self):
        (self.public / "index.html").write_bytes(b"PUBLIC APPROVED STATIC CONTENT")
        (self.public / ".env.production").write_bytes(b"PRIVATE SYNTHETIC ENV CONTENT")
        (self.public / ".git").mkdir()
        (self.public / ".git" / "config").write_bytes(
            b"PRIVATE SYNTHETIC GIT CREDENTIAL"
        )
        (self.public / "nested").mkdir()
        (self.public / "nested" / ".env.local").write_bytes(
            b"PRIVATE SYNTHETIC LOCAL ENV"
        )
        (self.public / ".well-known").mkdir()
        (self.public / ".well-known" / "security.txt").write_bytes(
            b"PUBLIC SECURITY CONTACT"
        )
        for method in ("GET", "HEAD"):
            for path in ("/.env.production", "/.git/config", "/nested/.env.local"):
                with self.subTest(method=method, path=path):
                    with build_server(
                        None, static_dir=self.public, account_service=None
                    ) as server:
                        status, body = self.get(server, path, method=method)
                    self.assertEqual(status, 404)
                    self.assertNotIn(b"PRIVATE SYNTHETIC", body)
            for path in ("/index.html", "/.well-known/security.txt"):
                with self.subTest(method=method, path=path):
                    with build_server(
                        None, static_dir=self.public, account_service=None
                    ) as server:
                        status, body = self.get(server, path, method=method)
                    self.assertEqual(status, 200)
                    if method == "HEAD":
                        self.assertEqual(body, b"")

    def test_atomic_static_open_refuses_symlink_swapped_after_directory_check(self):
        public_asset = self.public / "layout.css"
        public_asset.write_bytes(b"body { color: black; }")
        private_secret = self.private / "synthetic-secret.txt"
        private_secret.write_bytes(b"PRIVATE SYNTHETIC CREDENTIAL")
        original_open = os.open
        replaced = False

        def race_open(path, flags, *args, **kwargs):
            nonlocal replaced
            if path == "layout.css" and kwargs.get("dir_fd") is not None and not replaced:
                replaced = True
                public_asset.unlink()
                public_asset.symlink_to(private_secret)
            return original_open(path, flags, *args, **kwargs)

        with patch("dichiarazioni_pubbliche.public_api.os.open", side_effect=race_open):
            with build_server(None, static_dir=self.public, account_service=None) as server:
                status, body = self.get(server, "/layout.css")
        self.assertTrue(replaced, "Regression did not exercise descriptor opening")
        self.assertNotEqual(status, 200)
        self.assertNotIn(private_secret.read_bytes(), body)

    def test_safe_nested_static_index_keeps_canonical_slash_redirect(self):
        folder = self.public / "esplora"
        folder.mkdir()
        (folder / "index.html").write_bytes(b"SAFE STATIC INDEX")
        with build_server(None, static_dir=self.public, account_service=None) as server:
            redirect, body = self.get(server, "/esplora")
        self.assertEqual(redirect, 301)
        self.assertEqual(body, b"")
        with build_server(None, static_dir=self.public, account_service=None) as server:
            status, body = self.get(server, "/esplora/")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"SAFE STATIC INDEX")
        with build_server(None, static_dir=self.public, account_service=None) as server:
            status, body = self.get(server, "/esplora/index.html/")
        self.assertNotEqual(status, 200)
        self.assertNotIn(b"SAFE STATIC INDEX", body)

    def test_pinned_static_root_refuses_ancestor_swap_without_private_bytes(self):
        parent = self.base / "configured"
        public = parent / "public"
        public.mkdir(parents=True)
        (public / "index.html").write_bytes(b"ORIGINAL APPROVED STATIC ROOT")
        foreign_parent = self.base / "foreign-private"
        foreign_public = foreign_parent / "public"
        foreign_public.mkdir(parents=True)
        (foreign_public / "index.html").write_bytes(b"PRIVATE SYNTHETIC FILE CONTENT")
        with build_server(None, static_dir=public, account_service=None) as server:
            # Swap a *parent* pathname, not the final file: O_NOFOLLOW on the
            # last path component alone would still follow this symlink.
            parent.rename(self.base / "original-relocated")
            parent.symlink_to(foreign_parent, target_is_directory=True)
            status, body = self.get(server, "/")
        # The pinned descriptor still protects against redirected private
        # bytes, but a rotated release must also withdraw the old response.
        self.assertEqual(status, 404)
        self.assertEqual(body, b"")
        self.assertNotIn(b"PRIVATE SYNTHETIC FILE CONTENT", body)

    def test_shutdown_cannot_reuse_root_descriptor_during_inflight_http_get(self):
        (self.public / "index.html").write_bytes(b"APPROVED ROOT CONTENT")
        (self.private / "index.html").write_bytes(b"PRIVATE SYNTHETIC CLOSED-FD CONTENT")
        waiting = threading.Event()
        resume = threading.Event()
        closed = threading.Event()
        results = []
        original_dup = os.dup
        private_fd = []
        with build_server(None, static_dir=self.public, account_service=None) as server:
            root_fd = server.static_root_fd

            def block_before_dup(fd):
                if fd == root_fd and threading.current_thread() is not threading.main_thread():
                    waiting.set()
                    if not resume.wait(5):
                        raise TimeoutError("root duplication gate timed out")
                return original_dup(fd)

            def fetch():
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    connection.request("GET", "/")
                    reply = connection.getresponse()
                    results.append((reply.status, reply.read()))
                finally:
                    connection.close()

            def close_and_reuse():
                server.server_close()
                private_fd.append(os.open(self.private, os.O_RDONLY | os.O_DIRECTORY))
                closed.set()

            listener = threading.Thread(target=server.serve_forever, daemon=True)
            client = threading.Thread(target=fetch, daemon=True)
            closer = threading.Thread(target=close_and_reuse, daemon=True)
            with patch("dichiarazioni_pubbliche.public_api.os.dup", side_effect=block_before_dup):
                listener.start()
                client.start()
                try:
                    self.assertTrue(waiting.wait(3), "HTTP request never reached root fd duplication")
                    closer.start()
                    # Before synchronization, server_close releases the fd and
                    # a private directory reuses its integer before os.dup.
                    closed.wait(0.4)
                finally:
                    resume.set()
                    client.join(timeout=6)
                    closer.join(timeout=6)
                    server.shutdown()
                    listener.join(timeout=3)
                    for fd in private_fd:
                        os.close(fd)
            self.assertFalse(client.is_alive())
            self.assertFalse(closer.is_alive())
            self.assertEqual(results, [(200, b"APPROVED ROOT CONTENT")])

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
