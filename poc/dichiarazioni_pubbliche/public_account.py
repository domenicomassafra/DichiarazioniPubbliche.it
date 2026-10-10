"""Opt-in Google OIDC public accounts; no Studio/editorial authority.

The default public host never instantiates this service.  Enabling it requires
an explicit Google client, a protected private database and a confirmed HTTPS
origin. Account membership cannot grant permission to any review/publish API.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


OIDC_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OIDC_TOKEN = "https://oauth2.googleapis.com/token"
OIDC_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
SESSION_COOKIE = "__Host-dp-session"
FLOW_COOKIE = "__Host-dp-oidc"
VISITOR_COOKIE = "__Host-dp-visitor"
MAX_SESSION_SECONDS = 86400
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_SUB = re.compile(r"^[A-Za-z0-9_-]{1,255}$")
_KID = re.compile(r"^[A-Za-z0-9_-]{1,160}$")
_EMAIL = re.compile(r"^[^\s@<>]{1,100}@[^\s@<>]{1,150}$")


def _sha(raw: str) -> str:
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_segment(value: str) -> bytes:
    if len(value) > 8192 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("OIDC_JWT_ENCODING_INVALID")
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("OIDC_REDIRECT_REFUSED")


def _google_json(url: str, *, body: bytes | None = None) -> dict:
    # Fixed Google destinations; neither URL nor a redirect follows user input.
    if url not in (OIDC_TOKEN, OIDC_JWKS):
        raise ValueError("OIDC_DESTINATION_INVALID")
    request = Request(
        url, data=body, method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/x-www-form-urlencoded"} if body else {},
    )
    with build_opener(_NoRedirect()).open(request, timeout=6) as response:
        if response.status != 200 or response.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            raise ValueError("OIDC_GOOGLE_RESPONSE_INVALID")
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("OIDC_GOOGLE_RESPONSE_TOO_LARGE")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("OIDC_GOOGLE_RESPONSE_INVALID")
    return result


def verify_google_id_token(raw: str, jwks: dict, *, client_id: str, nonce: str, now: int) -> tuple[str, str]:
    """Verify RS256 signature, issuer, exact audience, nonce and strict claims."""
    try:
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        raise ValueError("OIDC_CRYPTOGRAPHY_REQUIRED") from None
    if not isinstance(raw, str) or len(raw) > 12000 or raw.count(".") != 2:
        raise ValueError("OIDC_JWT_INVALID")
    a, b, c = raw.split(".")
    try:
        header = json.loads(_decode_segment(a))
        claims = json.loads(_decode_segment(b))
        signature = _decode_segment(c)
        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise ValueError("OIDC_JWT_INVALID")
        if header.get("alg") != "RS256" or header.get("typ", "JWT") != "JWT":
            raise ValueError("OIDC_JWT_ALGORITHM_INVALID")
        kid = header.get("kid")
        if not isinstance(kid, str) or not _KID.fullmatch(kid):
            raise ValueError("OIDC_JWT_KEY_INVALID")
        keys = jwks.get("keys") if isinstance(jwks, dict) else None
        if not isinstance(keys, list) or len(keys) > 20:
            raise ValueError("OIDC_JWKS_INVALID")
        matches = [key for key in keys if isinstance(key, dict) and key.get("kid") == kid]
        if len(matches) != 1 or matches[0].get("kty") != "RSA" or matches[0].get("alg", "RS256") != "RS256" or matches[0].get("use", "sig") != "sig":
            raise ValueError("OIDC_JWT_KEY_INVALID")
        n = int.from_bytes(_decode_segment(matches[0]["n"]), "big")
        e = int.from_bytes(_decode_segment(matches[0]["e"]), "big")
        if not 2048 <= n.bit_length() <= 4096 or e != 65537:
            raise ValueError("OIDC_JWT_KEY_INVALID")
        rsa.RSAPublicNumbers(e, n).public_key().verify(
            signature, f"{a}.{b}".encode("ascii"), padding.PKCS1v15(), hashes.SHA256()
        )
        if claims.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
            raise ValueError("OIDC_ISSUER_INVALID")
        if claims.get("aud") != client_id or not isinstance(claims.get("aud"), str):
            raise ValueError("OIDC_AUDIENCE_INVALID")
        if "azp" in claims and claims["azp"] != client_id:
            raise ValueError("OIDC_AUTHORIZED_PARTY_INVALID")
        if not isinstance(claims.get("exp"), int) or isinstance(claims["exp"], bool) or claims["exp"] <= now:
            raise ValueError("OIDC_TOKEN_EXPIRED")
        if not isinstance(claims.get("iat"), int) or isinstance(claims["iat"], bool) or not now - 86400 <= claims["iat"] <= now + 60:
            raise ValueError("OIDC_ISSUED_AT_INVALID")
        if not isinstance(claims.get("nonce"), str) or not hmac.compare_digest(claims["nonce"], nonce):
            raise ValueError("OIDC_NONCE_INVALID")
        sub, email = claims.get("sub"), claims.get("email")
        if not isinstance(sub, str) or not _SUB.fullmatch(sub):
            raise ValueError("OIDC_SUBJECT_INVALID")
        if claims.get("email_verified") is not True or not isinstance(email, str) or not _EMAIL.fullmatch(email):
            raise ValueError("OIDC_VERIFIED_EMAIL_REQUIRED")
        return sub, email
    except (KeyError, TypeError, OverflowError, InvalidSignature, UnicodeError, json.JSONDecodeError, ValueError):
        raise ValueError("OIDC_TOKEN_VERIFICATION_FAILED") from None


class GoogleOidcProvider:
    def __init__(self, client_id: str, secret: str, redirect_uri: str):
        self.client_id = client_id
        self._secret = secret
        self.redirect_uri = redirect_uri
        self._jwks: dict | None = None
        self._expires = 0.0

    def exchange(self, code: str, verifier: str, nonce: str, *, now: int) -> tuple[str, str]:
        if not isinstance(code, str) or not 1 <= len(code) <= 2048 or "\n" in code or "\r" in code:
            raise ValueError("OIDC_CODE_INVALID")
        body = urlencode({
            "client_id": self.client_id, "client_secret": self._secret,
            "code": code, "code_verifier": verifier, "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }).encode("ascii")
        response = _google_json(OIDC_TOKEN, body=body)
        raw_token = response.get("id_token")
        if not isinstance(raw_token, str):
            raise ValueError("OIDC_ID_TOKEN_MISSING")
        if self._jwks is None or time.monotonic() >= self._expires:
            self._jwks = _google_json(OIDC_JWKS)
            self._expires = time.monotonic() + 900
        try:
            return verify_google_id_token(raw_token, self._jwks, client_id=self.client_id, nonce=nonce, now=now)
        except ValueError:
            # A legitimate key rotation is retried only once with fresh JWKS.
            self._jwks = _google_json(OIDC_JWKS)
            self._expires = time.monotonic() + 900
            return verify_google_id_token(raw_token, self._jwks, client_id=self.client_id, nonce=nonce, now=now)


def read_secret_file(path: Path) -> str:
    path = Path(path)
    if path.is_symlink():
        raise ValueError("ACCOUNT_SECRET_SYMLINK")
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        raise ValueError("ACCOUNT_SECRET_PERMISSIONS")
    raw = path.read_bytes()
    if not 8 <= len(raw) <= 512:
        raise ValueError("ACCOUNT_SECRET_INVALID")
    secret = raw.decode("ascii").strip()
    if len(secret) < 8 or any(ch.isspace() for ch in secret):
        raise ValueError("ACCOUNT_SECRET_INVALID")
    return secret


class AccountStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        parent = self.path.parent
        mode = parent.stat()
        if parent.is_symlink() or mode.st_uid != os.getuid() or mode.st_mode & 0o077:
            raise ValueError("ACCOUNT_PRIVATE_DIRECTORY_REQUIRED")
        if self.path.is_symlink():
            raise ValueError("ACCOUNT_DATABASE_SYMLINK")
        if self.path.exists() and (self.path.stat().st_uid != os.getuid() or self.path.stat().st_mode & 0o077):
            raise ValueError("ACCOUNT_DATABASE_PERMISSIONS")
        previous = os.umask(0o077)
        try:
            with self._connect() as db:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS pending(state_hash TEXT PRIMARY KEY,
                      browser_hash TEXT NOT NULL, verifier TEXT NOT NULL,
                      nonce TEXT NOT NULL, expires_at INTEGER NOT NULL);
                    CREATE TABLE IF NOT EXISTS users(subject TEXT PRIMARY KEY,
                      email TEXT NOT NULL, created_at INTEGER NOT NULL, last_login INTEGER NOT NULL);
                    CREATE TABLE IF NOT EXISTS sessions(session_hash TEXT PRIMARY KEY,
                      subject TEXT NOT NULL REFERENCES users(subject) ON DELETE CASCADE,
                      csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);
                    CREATE TABLE IF NOT EXISTS throttle(bucket TEXT PRIMARY KEY,
                      window INTEGER NOT NULL, used INTEGER NOT NULL);
                """)
        finally:
            os.umask(previous)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=3000")
            db.execute("PRAGMA secure_delete=ON")
            with db:
                yield db
        finally:
            db.close()

    def begin(self, state: str, browser: str, verifier: str, nonce: str, now: int, bucket: str) -> None:
        if not isinstance(bucket, str) or not re.fullmatch(r"[0-9a-f]{64}", bucket):
            raise ValueError("ACCOUNT_BUCKET_INVALID")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM pending WHERE expires_at <= ?", (now,))
            db.execute("DELETE FROM throttle WHERE window < ?", (now // 60 - 1,))
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            window = now // 60
            for key, limit in (("global", 120), (bucket, 5)):
                previous = db.execute("SELECT window, used FROM throttle WHERE bucket=?", (key,)).fetchone()
                if previous and previous[0] == window and previous[1] >= limit:
                    raise ValueError("ACCOUNT_LOGIN_RATE_LIMIT")
                db.execute("INSERT INTO throttle VALUES (?, ?, 1) ON CONFLICT(bucket) DO UPDATE SET window=?,used=?",
                           (key, window, window, previous[1] + 1 if previous and previous[0] == window else 1))
            db.execute("INSERT INTO pending VALUES (?, ?, ?, ?, ?)", (_sha(state), _sha(browser), verifier, nonce, now + 300))

    def take_flow(self, state: str, browser: str, now: int) -> tuple[str, str]:
        if not _TOKEN.fullmatch(state) or not _TOKEN.fullmatch(browser):
            raise ValueError("ACCOUNT_LOGIN_STATE_INVALID")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT browser_hash, verifier, nonce, expires_at FROM pending WHERE state_hash=?", (_sha(state),)).fetchone()
            db.execute("DELETE FROM pending WHERE state_hash=?", (_sha(state),))
        if not row or row[3] <= now or not hmac.compare_digest(row[0], _sha(browser)):
            raise ValueError("ACCOUNT_LOGIN_STATE_INVALID")
        return row[1], row[2]

    def login(self, subject: str, email: str, now: int) -> str:
        session = _b64(secrets.token_bytes(32))
        csrf = _b64(secrets.token_bytes(32))
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO users VALUES (?, ?, ?, ?) ON CONFLICT(subject) DO UPDATE SET email=excluded.email,last_login=excluded.last_login",
                       (subject, email, now, now))
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (_sha(session), subject, csrf, now + MAX_SESSION_SECONDS))
        return session

    def get_session(self, session: str, now: int) -> tuple[str, str, str] | None:
        if not isinstance(session, str) or not _TOKEN.fullmatch(session):
            return None
        with self._connect() as db:
            return db.execute("SELECT u.subject, u.email, s.csrf FROM sessions s JOIN users u ON u.subject=s.subject WHERE s.session_hash=? AND s.expires_at>?",
                              (_sha(session), now)).fetchone()

    def purge_expired(self, now: int) -> None:
        """Bound expired private OAuth state without retaining an IP or token."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM pending WHERE expires_at <= ?", (now,))
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            db.execute("DELETE FROM throttle WHERE window < ?", (now // 60 - 1,))

    def end(self, session: str, csrf: str, now: int, *, delete_account: bool) -> bool:
        current = self.get_session(session, now)
        if current is None or not isinstance(csrf, str) or not hmac.compare_digest(current[2], csrf):
            return False
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT subject, csrf FROM sessions WHERE session_hash=? AND expires_at>?",
                             (_sha(session), now)).fetchone()
            if row is None or not hmac.compare_digest(row[1], csrf):
                return False
            if delete_account:
                db.execute("DELETE FROM users WHERE subject=?", (row[0],))
            else:
                db.execute("DELETE FROM sessions WHERE session_hash=?", (_sha(session),))
        return True


@dataclass(frozen=True)
class AccountResponse:
    status: int
    body: bytes = b""
    location: str = ""
    cookie: str = ""
    clear_flow: bool = False
    content_type: str = "application/json; charset=utf-8"


def _cookie(name: str, value: str, seconds: int) -> str:
    return f"{name}={value}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age={seconds}"


def _json(status: int, data: dict) -> AccountResponse:
    return AccountResponse(status, json.dumps(data, separators=(",", ":")).encode("utf-8"))


class AccountService:
    def __init__(self, client_id: str, site_origin: str, store: AccountStore, provider: GoogleOidcProvider, *, visitor_key: str):
        if not re.fullmatch(r"[A-Za-z0-9_.-]{5,255}", client_id):
            raise ValueError("ACCOUNT_CLIENT_ID_INVALID")
        if not re.fullmatch(r"https://[a-z0-9.-]+(?::443)?", site_origin):
            raise ValueError("ACCOUNT_HTTPS_ORIGIN_REQUIRED")
        if site_origin.endswith(".") or ".." in site_origin or not site_origin.split("//", 1)[1].endswith(".it"):
            raise ValueError("ACCOUNT_ORIGIN_INVALID")
        self.client_id = client_id
        self.site_origin = site_origin
        self.store = store
        self.provider = provider
        if not isinstance(visitor_key, str) or len(visitor_key) < 8:
            raise ValueError("ACCOUNT_VISITOR_SIGNING_KEY_REQUIRED")
        self._visitor_key = visitor_key.encode("utf-8")

    def new_visitor(self) -> str:
        raw = _b64(secrets.token_bytes(32))
        mac = hmac.new(self._visitor_key, raw.encode("ascii"), hashlib.sha256).hexdigest()
        return raw + "." + mac

    def visitor_bucket(self, visitor: str) -> str:
        if not isinstance(visitor, str) or len(visitor) > 160 or visitor.count(".") != 1:
            raise ValueError("ACCOUNT_VISITOR_REQUIRED")
        raw, mac = visitor.split(".")
        if not _TOKEN.fullmatch(raw) or not re.fullmatch(r"[0-9a-f]{64}", mac):
            raise ValueError("ACCOUNT_VISITOR_INVALID")
        expected = hmac.new(self._visitor_key, raw.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected):
            raise ValueError("ACCOUNT_VISITOR_INVALID")
        return _sha(raw)

    @property
    def callback(self) -> str:
        return self.site_origin + "/account/oauth/callback"

    def start(self, now: int, visitor: str) -> AccountResponse:
        bucket = self.visitor_bucket(visitor)
        state, browser, nonce = (_b64(secrets.token_bytes(32)) for _ in range(3))
        verifier = _b64(secrets.token_bytes(48))
        self.store.begin(state, browser, verifier, nonce, now, bucket)
        challenge = _b64(hashlib.sha256(verifier.encode("ascii")).digest())
        location = OIDC_AUTHORIZE + "?" + urlencode({
            "client_id": self.client_id, "redirect_uri": self.callback,
            "response_type": "code", "scope": "openid email", "state": state,
            "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256",
            "prompt": "select_account",
        })
        return AccountResponse(303, location=location, cookie=_cookie(FLOW_COOKIE, browser, 300))

    def callback_response(self, state: str, code: str, browser: str, now: int) -> AccountResponse:
        verifier, nonce = self.store.take_flow(state, browser, now)
        subject, email = self.provider.exchange(code, verifier, nonce, now=now)
        session = self.store.login(subject, email, now)
        return AccountResponse(303, location="/account/", cookie=_cookie(SESSION_COOKIE, session, MAX_SESSION_SECONDS), clear_flow=True)

    def inspect(self, session: str, now: int) -> AccountResponse:
        self.store.purge_expired(now)
        current = self.store.get_session(session, now)
        if current is None:
            return _json(401, {"error": "ACCOUNT_LOGIN_REQUIRED"})
        return _json(200, {"authenticated": True, "email": current[1], "csrf": current[2]})

    def finish(self, session: str, csrf: str, now: int, *, delete_account: bool) -> AccountResponse:
        if not self.store.end(session, csrf, now, delete_account=delete_account):
            return _json(403, {"error": "ACCOUNT_AUTH_OR_CSRF_INVALID"})
        response = _json(200, {"ok": True})
        return AccountResponse(response.status, response.body, cookie=_cookie(SESSION_COOKIE, "", 0))


__all__ = ["AccountService", "AccountStore", "AccountResponse", "GoogleOidcProvider", "FLOW_COOKIE", "SESSION_COOKIE", "VISITOR_COOKIE", "read_secret_file", "verify_google_id_token"]
