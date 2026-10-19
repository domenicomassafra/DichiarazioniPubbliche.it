"""Security regression tests for the optional Authlib Google OIDC profile."""

import base64
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.public_account import (  # noqa: E402
    GoogleOidcProvider, OIDC_JWKS, OIDC_TOKEN, verify_google_id_token,
)


@unittest.skipUnless(
    importlib.util.find_spec("authlib") and importlib.util.find_spec("cryptography"),
    "optional Authlib account profile is not installed",
)
class AuthlibGoogleOidcTests(unittest.TestCase):
    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.old_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.now = 1760000000
        self.claims = {
            "iss": "https://accounts.google.com", "aud": "test-client",
            "sub": "google-sub-1", "email": "verified@example.org",
            "email_verified": True, "exp": self.now + 3600,
            "iat": self.now - 30, "nonce": "expected-nonce",
        }

    @staticmethod
    def _encode(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    def _jwk(self, key, kid):
        public = key.public_key().public_numbers()
        return {
            "kty": "RSA", "use": "sig", "alg": "RS256", "kid": kid,
            "n": self._encode(public.n.to_bytes(256, "big")),
            "e": self._encode(public.e.to_bytes(3, "big")),
        }

    def _token(self, claims=None, header=None, key=None):
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes

        header = header if header is not None else {"alg": "RS256", "typ": "JWT", "kid": "new"}
        signing = ".".join(self._encode(json.dumps(value).encode("utf-8"))
                           for value in (header, self.claims if claims is None else claims))
        signer = self.key if key is None else key
        signature = signer.sign(signing.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
        return signing + "." + self._encode(signature)

    def _verify(self, token, jwks=None):
        return verify_google_id_token(
            token, {"keys": [self._jwk(self.key, "new")]} if jwks is None else jwks,
            client_id="test-client", nonce="expected-nonce", now=self.now,
        )

    def test_authlib_verifies_real_signature_and_strict_claims(self):
        self.assertEqual(self._verify(self._token()), ("google-sub-1", "verified@example.org"))
        for updates in (
            {"iss": "https://other.example"},
            {"aud": ["test-client"]},
            {"aud": "other-client"},
            {"azp": "other-client"},
            {"nonce": "other-nonce"},
            {"nonce": None},
            {"exp": self.now - 1},
            {"exp": True},
            {"iat": True},
            {"iat": self.now + 61},
            {"iat": self.now - 86401},
            {"email_verified": False},
            {"sub": ""},
            {"email": "invalid"},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self._verify(self._token({**self.claims, **updates}))
        for missing in ("iss", "aud", "sub", "exp", "iat", "nonce"):
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                self._verify(self._token({k: v for k, v in self.claims.items() if k != missing}))

    def test_rejects_algorithm_kid_key_and_signature_confusion(self):
        for header in (
            {"kid": "new", "alg": "none", "typ": "JWT"},
            {"kid": "new", "alg": "HS256", "typ": "JWT"},
            {"kid": "missing", "alg": "RS256", "typ": "JWT"},
            {"kid": "new", "alg": "RS256", "typ": "OTHER"},
        ):
            with self.subTest(header=header), self.assertRaises(ValueError):
                self._verify(self._token(header=header))
        with self.assertRaises(ValueError):
            self._verify(self._token(key=self.old_key))
        for bad_key in (
            {**self._jwk(self.key, "new"), "kty": "oct"},
            {**self._jwk(self.key, "new"), "use": "enc"},
            {**self._jwk(self.key, "new"), "alg": "HS256"},
        ):
            with self.subTest(bad_key=bad_key["kty"] + bad_key.get("use", "")), self.assertRaises(ValueError):
                self._verify(self._token(), {"keys": [bad_key]})
        duplicate = self._jwk(self.key, "new")
        with self.assertRaises(ValueError):
            self._verify(self._token(), {"keys": [duplicate, dict(duplicate)]})
        with self.assertRaises(ValueError):
            self._verify("not-a.jwt", {"keys": [duplicate]})

    def test_jwks_key_rotation_retries_exactly_once(self):
        provider = GoogleOidcProvider("test-client", "fake-secret", "https://dichiarazionipubbliche.it/callback")
        token = self._token()
        requests = []

        def google_json(url, *, body=None):
            requests.append(url)
            if url == OIDC_TOKEN:
                self.assertIsNotNone(body)
                return {"id_token": token}
            self.assertEqual(url, OIDC_JWKS)
            if requests.count(OIDC_JWKS) == 1:
                return {"keys": [self._jwk(self.old_key, "old")]}
            return {"keys": [self._jwk(self.key, "new")]}

        with patch("dichiarazioni_pubbliche.public_account._google_json", side_effect=google_json):
            self.assertEqual(
                provider.exchange("auth-code", "pkce-verifier", "expected-nonce", now=self.now),
                ("google-sub-1", "verified@example.org"),
            )
        self.assertEqual(requests, [OIDC_TOKEN, OIDC_JWKS, OIDC_JWKS])


if __name__ == "__main__":
    unittest.main()
