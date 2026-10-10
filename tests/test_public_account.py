import base64
import hashlib
import http.client
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.public_account import (
    AccountService, AccountStore, GoogleOidcProvider, OIDC_AUTHORIZE,
    read_secret_file, verify_google_id_token,
)
from dichiarazioni_pubbliche.public_api import build_server


class FakeProvider:
    def exchange(self, code, verifier, nonce, *, now):
        if code != "authorized-code" or not verifier or not nonce:
            raise ValueError("OIDC_CALLBACK_REFUSED")
        return "google-user-123", "verified@example.org"


class PublicAccountTests(unittest.TestCase):
    @staticmethod
    def _service(root):
        return AccountService(
            "test-client.apps.googleusercontent.com", "https://dichiarazionipubbliche.it",
            AccountStore(Path(root) / "accounts.sqlite3"), FakeProvider(), visitor_key="test-account-visitor-secret",
        )

    def test_cookie_bound_pkce_nonce_one_time_login_and_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self._service(directory)
            visitor = service.new_visitor()
            start = service.start(1000, visitor)
            self.assertEqual(start.status, 303)
            params = parse_qs(urlsplit(start.location).query)
            self.assertEqual(urlsplit(start.location).scheme, "https")
            self.assertTrue(start.location.startswith(OIDC_AUTHORIZE))
            self.assertEqual(params["scope"], ["openid email"])
            self.assertEqual(params["code_challenge_method"], ["S256"])
            self.assertTrue(params["nonce"][0])
            self.assertEqual(params["redirect_uri"], [service.callback])
            browser = start.cookie.split(";", 1)[0].split("=", 1)[1]
            with self.assertRaises(ValueError):
                service.callback_response(params["state"][0], "authorized-code", "A" * 43, 1001)
            with self.assertRaises(ValueError):
                service.callback_response(params["state"][0], "authorized-code", browser, 1001)
            second = service.start(1001, visitor)
            state = parse_qs(urlsplit(second.location).query)["state"][0]
            browser = second.cookie.split(";", 1)[0].split("=", 1)[1]
            login = service.callback_response(state, "authorized-code", browser, 1002)
            self.assertEqual(login.location, "/account/")
            self.assertTrue(login.clear_flow)
            self.assertIn("Secure; HttpOnly; SameSite=Lax", login.cookie)
            session = login.cookie.split(";", 1)[0].split("=", 1)[1]
            info = json.loads(service.inspect(session, 1003).body)
            self.assertEqual(info["email"], "verified@example.org")
            self.assertEqual(service.finish(session, "wrong", 1004, delete_account=True).status, 403)
            self.assertEqual(service.inspect(session, 1004).status, 200)
            self.assertEqual(service.finish(session, info["csrf"], 1004, delete_account=True).status, 200)
            self.assertEqual(service.inspect(session, 1005).status, 401)
            with service.store._connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM users").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT count(*) FROM pending").fetchone()[0], 0)

    def test_rate_limit_and_expiration_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self._service(directory)
            visitor = service.new_visitor()
            with self.assertRaises(ValueError):
                service.start(1000, visitor[:-1] + ("a" if visitor[-1] != "a" else "b"))
            for _ in range(5):
                service.start(1000, visitor)
            with self.assertRaisesRegex(ValueError, "ACCOUNT_LOGIN_RATE_LIMIT"):
                service.start(1000, visitor)
            next_window = service.start(1080, visitor)
            state = parse_qs(urlsplit(next_window.location).query)["state"][0]
            browser = next_window.cookie.split(";", 1)[0].split("=", 1)[1]
            with self.assertRaises(ValueError):
                service.callback_response(state, "authorized-code", browser, 2000)
            self.assertEqual(service.inspect("nonsense", 2000).status, 401)
            with service.store._connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM pending").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT count(*) FROM throttle").fetchone()[0], 0)

    def test_private_storage_and_opt_in_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            db = self._service(directory).store.path
            self.assertEqual(db.stat().st_mode & 0o077, 0)
            self.assertFalse(db.is_symlink())
            keyfile = Path(directory) / "secret"
            keyfile.write_text("local-test-secret-123")
            os.chmod(keyfile, 0o644)
            with self.assertRaisesRegex(ValueError, "PERMISSIONS"):
                read_secret_file(keyfile)
            os.chmod(keyfile, 0o600)
            self.assertEqual(read_secret_file(keyfile), "local-test-secret-123")
            with tempfile.TemporaryDirectory() as unsafe:
                os.chmod(unsafe, 0o755)
                with self.assertRaisesRegex(ValueError, "PRIVATE_DIRECTORY"):
                    AccountStore(Path(unsafe) / "accounts.sqlite3")
            with self.assertRaisesRegex(ValueError, "HTTPS_ORIGIN"):
                AccountService("client_id", "http://dichiarazionipubbliche.it", self._service(directory).store, FakeProvider(), visitor_key="private-visitor-key")

    def test_public_http_is_read_only_by_default_and_loopback_only_with_accounts(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self._service(directory)
            with self.assertRaisesRegex(ValueError, "LOOPBACK"):
                build_server(None, host="0.0.0.0", account_service=service)
            with build_server(None, host="127.0.0.1", port=0) as server:
                self.assertIsNone(server.RequestHandlerClass.account_service)

    def test_http_origin_csrf_one_time_callback_and_cookie_cache_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self._service(directory)
            with build_server(None, host="127.0.0.1", port=0, account_service=service) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                def request(method, path, *, cookie="", origin=None, csrf=None, host="dichiarazionipubbliche.it"):
                    headers = {"Host": host, "Connection": "close"}
                    if cookie:
                        headers["Cookie"] = cookie
                    if origin is not None:
                        headers["Origin"] = origin
                    if csrf is not None:
                        headers["X-CSRF-Token"] = csrf
                    if method == "POST":
                        headers["Content-Length"] = "0"
                    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
                    try:
                        conn.request(method, path, headers=headers)
                        response = conn.getresponse()
                        observed = response.getheaders()
                        result_headers = dict(observed)
                        result_headers["Set-Cookies"] = [value for key, value in observed if key.lower() == "set-cookie"]
                        return response.status, result_headers, response.read()
                    finally:
                        conn.close()
                try:
                    self.assertEqual(request("POST", "/account/auth/google")[0], 403)
                    self.assertEqual(request("POST", "/account/auth/google", origin="https://evil.example")[0], 403)
                    self.assertEqual(request("GET", "/account/api/session", host="evil.example")[0], 403)
                    status, headers, _ = request("GET", "/account/api/session")
                    self.assertEqual(status, 401)
                    visitor = headers["Set-Cookie"].split(";", 1)[0]
                    self.assertEqual(request("HEAD", "/account/api/session")[0], 405)
                    status, headers, _ = request("POST", "/account/auth/google", cookie=visitor, origin=service.site_origin)
                    self.assertEqual(status, 303)
                    self.assertEqual(headers["Cache-Control"], "no-store, private")
                    self.assertEqual(headers["Vary"], "Cookie")
                    state = parse_qs(urlsplit(headers["Location"]).query)["state"][0]
                    browser = headers["Set-Cookie"].split(";", 1)[0]
                    status, headers, _ = request("GET", f"/account/oauth/callback?state={state}&code=authorized-code", cookie=browser)
                    self.assertEqual(status, 303)
                    self.assertTrue(any(item.startswith("__Host-dp-oidc=;") for item in headers["Set-Cookies"]))
                    session = next(item for item in headers["Set-Cookies"] if item.startswith("__Host-dp-session=")).split(";", 1)[0]
                    self.assertTrue(session.startswith("__Host-dp-session="))
                    self.assertEqual(request("GET", "/account/api/session", cookie=f"{session}; {session}")[0], 401)
                    self.assertEqual(request("GET", f"/account/oauth/callback?state={state}&code=authorized-code", cookie=browser)[0], 400)
                    status, headers, body = request("GET", "/account/api/session", cookie=session)
                    self.assertEqual(status, 200)
                    self.assertEqual(headers["Surrogate-Control"], "no-store")
                    details = json.loads(body)
                    self.assertEqual(details["email"], "verified@example.org")
                    self.assertEqual(request("POST", "/account/api/delete", cookie=session, origin=service.site_origin)[0], 403)
                    self.assertEqual(request("POST", "/account/api/delete", cookie=session, origin="https://evil.example", csrf=details["csrf"])[0], 403)
                    self.assertEqual(request("POST", "/account/api/logout", cookie=session, origin=service.site_origin, csrf=details["csrf"])[0], 200)
                    self.assertEqual(request("GET", "/account/api/session", cookie=session)[0], 401)
                finally:
                    server.shutdown()
                    thread.join(timeout=3)


class SignedGoogleTokenTests(unittest.TestCase):
    @unittest.skipUnless(__import__("importlib").util.find_spec("cryptography"), "explicit cryptography account profile not installed")
    def test_real_rs256_signature_and_strict_oidc_claims(self):
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = private_key.public_key().public_numbers()
        encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
        jwks = {"keys": [{
            "kty": "RSA", "use": "sig", "alg": "RS256", "kid": "test-key",
            "n": encode(numbers.n.to_bytes(256, "big")), "e": encode(numbers.e.to_bytes(3, "big")),
        }]}
        now = 1760000000
        claims = {
            "iss": "https://accounts.google.com", "aud": "test-client", "sub": "google-sub-1",
            "email": "verified@example.org", "email_verified": True,
            "exp": now + 3600, "iat": now - 30, "nonce": "expected-nonce",
        }
        def signed(data, header=None):
            header = header or {"kid": "test-key", "alg": "RS256", "typ": "JWT"}
            signing = ".".join(encode(json.dumps(obj).encode()) for obj in (header, data))
            return signing + "." + encode(private_key.sign(signing.encode(), padding.PKCS1v15(), hashes.SHA256()))
        token = signed(claims)
        self.assertEqual(verify_google_id_token(token, jwks, client_id="test-client", nonce="expected-nonce", now=now),
                         ("google-sub-1", "verified@example.org"))
        for change in ({"aud": "evil-client"}, {"azp": "other-client"}, {"nonce": "wrong"}, {"email_verified": False},
                       {"exp": now - 1}, {"iat": now + 1000}, {"iss": "https://evil.example"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_google_id_token(signed({**claims, **change}), jwks, client_id="test-client", nonce="expected-nonce", now=now)
        with self.assertRaises(ValueError):
            verify_google_id_token(signed(claims, {"kid": "test-key", "alg": "none"}), jwks,
                                   client_id="test-client", nonce="expected-nonce", now=now)
        with self.assertRaises(ValueError):
            verify_google_id_token(token[:-5] + "AAAAA", jwks, client_id="test-client", nonce="expected-nonce", now=now)


if __name__ == "__main__":
    unittest.main()
