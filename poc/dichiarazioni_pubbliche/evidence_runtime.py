from __future__ import annotations

import fcntl
import hashlib
import ipaddress
import json
import os
import socket
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "config" / "evidence-sources.v1.json"
DEFAULT_CACHE_ROOT = Path.home() / ".local" / "share" / "dichiarazioni-pubbliche" / "evidence"
DEFAULT_RATE_STATE = Path.home() / ".local" / "state" / "dichiarazioni-pubbliche" / "evidence-rate.json"


class EvidencePolicyError(RuntimeError):
    pass


class EvidenceRateLimited(RuntimeError):
    def __init__(self, source_id: str, retry_after_seconds: float) -> None:
        self.source_id = source_id
        self.retry_after_seconds = max(float(retry_after_seconds), 0.0)
        super().__init__(
            f"EVIDENCE_RATE_LIMITED:{source_id}:{self.retry_after_seconds:.3f}"
        )


@dataclass(frozen=True)
class EvidenceFetchReceipt:
    source_id: str
    canonical_url: str
    final_url: str
    fetched_at: str
    http_status: int
    content_type: str
    content_sha256: str
    response_bytes: int
    etag: str | None
    last_modified: str | None
    from_cache: bool
    cache_age_seconds: float | None
    authoritative: bool
    evidence_class: str
    publisher: str


@dataclass(frozen=True)
class EvidenceFetchResult:
    receipt: EvidenceFetchReceipt
    body_path: Path


def load_evidence_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported evidence source registry schema")
    return payload


def get_evidence_source(registry: dict[str, Any], source_id: str) -> dict[str, Any]:
    for source in registry.get("sources", []):
        if source.get("id") == source_id:
            return source
    raise KeyError(f"Unknown evidence source: {source_id}")


def _atomic_private_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def normalized_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "/",
            parsed.query,
            "",
        )
    )


def _host_matches(host: str, allowed_hosts: list[str]) -> bool:
    host = host.rstrip(".").lower()
    for allowed in allowed_hosts:
        allowed = allowed.rstrip(".").lower()
        if host == allowed:
            return True
        if host.endswith("." + allowed):
            return True
    return False


def validate_evidence_url(
    source: dict[str, Any],
    url: str,
    *,
    resolver: Callable[..., Any] = socket.getaddrinfo,
) -> str:
    canonical = normalized_url(url)
    parsed = urllib.parse.urlsplit(canonical)
    if parsed.scheme != "https":
        raise EvidencePolicyError("EVIDENCE_HTTPS_REQUIRED")
    if parsed.username or parsed.password:
        raise EvidencePolicyError("EVIDENCE_USERINFO_REFUSED")
    if parsed.port not in {None, 443}:
        raise EvidencePolicyError("EVIDENCE_NONSTANDARD_PORT_REFUSED")
    host = parsed.hostname or ""
    if not host or not _host_matches(host, list(source.get("allowed_hosts") or [])):
        raise EvidencePolicyError("EVIDENCE_HOST_NOT_ALLOWLISTED")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise EvidencePolicyError("EVIDENCE_IP_LITERAL_REFUSED")
    prefixes = list(source.get("allowed_path_prefixes") or ["/"])
    if not any(parsed.path.startswith(prefix) for prefix in prefixes):
        raise EvidencePolicyError("EVIDENCE_PATH_NOT_ALLOWLISTED")
    try:
        infos = resolver(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise EvidencePolicyError("EVIDENCE_DNS_FAILED") from exc
    addresses = {
        info[4][0]
        for info in infos
        if info and len(info) > 4 and info[4]
    }
    if not addresses:
        raise EvidencePolicyError("EVIDENCE_DNS_EMPTY")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        if not ip.is_global:
            raise EvidencePolicyError("EVIDENCE_NONPUBLIC_IP_REFUSED")
    return canonical


class FileRateLimiter:
    def __init__(self, path: Path = DEFAULT_RATE_STATE) -> None:
        self.path = path.expanduser()

    def acquire(
        self,
        source_id: str,
        *,
        requests: int,
        window_seconds: int,
        now: float | None = None,
    ) -> None:
        maximum = max(int(requests), 1)
        window = max(int(window_seconds), 1)
        current = time.time() if now is None else float(now)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            with os.fdopen(fd, "r+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    text = handle.read().strip()
                    state = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    state = {}
                recent = [
                    float(value)
                    for value in state.get(source_id, [])
                    if current - float(value) < window
                ]
                if len(recent) >= maximum:
                    retry = window - (current - min(recent))
                    raise EvidenceRateLimited(source_id, retry)
                recent.append(current)
                state[source_id] = recent
                handle.seek(0)
                handle.truncate()
                json.dump(state, handle, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
                os.fchmod(handle.fileno(), 0o600)
        finally:
            pass


class EvidenceCache:
    def __init__(self, root: Path = DEFAULT_CACHE_ROOT) -> None:
        self.root = root.expanduser()

    def _url_key(
        self,
        source_id: str,
        url: str,
        *,
        method: str = "GET",
        request_body_sha256: str = "",
    ) -> str:
        return hashlib.sha256(
            "\0".join(
                (
                    source_id,
                    method.upper(),
                    normalized_url(url),
                    request_body_sha256.lower(),
                )
            ).encode()
        ).hexdigest()

    def index_path(
        self,
        source_id: str,
        url: str,
        *,
        method: str = "GET",
        request_body_sha256: str = "",
    ) -> Path:
        return self.root / "url" / (
            self._url_key(
                source_id,
                url,
                method=method,
                request_body_sha256=request_body_sha256,
            )
            + ".json"
        )

    def body_path(self, content_sha256: str) -> Path:
        return self.root / "sha256" / content_sha256[:2] / content_sha256 / "body"

    @staticmethod
    def _ensure_private_directory(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path, 0o700)

    def _ensure_private_tree(self, path: Path) -> None:
        current = self.root
        self._ensure_private_directory(current)
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise EvidencePolicyError("EVIDENCE_CACHE_PATH_OUTSIDE_ROOT") from exc
        for part in relative.parts:
            current = current / part
            self._ensure_private_directory(current)

    def load_index(
        self,
        source_id: str,
        url: str,
        *,
        method: str = "GET",
        request_body_sha256: str = "",
    ) -> dict[str, Any] | None:
        path = self.index_path(
            source_id,
            url,
            method=method,
            request_body_sha256=request_body_sha256,
        )
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        body = self.body_path(str(payload.get("content_sha256") or ""))
        if not body.is_file():
            return None
        return payload

    def store(
        self,
        source_id: str,
        url: str,
        body: bytes,
        metadata: dict[str, Any],
        *,
        method: str = "GET",
        request_body_sha256: str = "",
    ) -> Path:
        digest = hashlib.sha256(body).hexdigest()
        body_path = self.body_path(digest)
        self._ensure_private_tree(body_path.parent)
        if not body_path.is_file():
            _atomic_private_write(body_path, body)
        index = {
            **metadata,
            "source_id": source_id,
            "canonical_url": normalized_url(url),
            "content_sha256": digest,
        }
        index_path = self.index_path(
            source_id,
            url,
            method=method,
            request_body_sha256=request_body_sha256,
        )
        self._ensure_private_tree(index_path.parent)
        _atomic_private_write(
            index_path,
            (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode(),
        )
        return body_path


class _PolicyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(
        self,
        source: dict[str, Any],
        resolver: Callable[..., Any],
        max_redirects: int,
    ) -> None:
        super().__init__()
        self.source = source
        self.resolver = resolver
        self.max_redirects = max(int(max_redirects), 0)
        self.redirects = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirects += 1
        if self.redirects > self.max_redirects:
            raise EvidencePolicyError("EVIDENCE_REDIRECT_LIMIT_EXCEEDED")
        safe = validate_evidence_url(
            self.source,
            newurl,
            resolver=self.resolver,
        )
        return super().redirect_request(req, fp, code, msg, headers, safe)


class SafeEvidenceFetcher:
    def __init__(
        self,
        *,
        registry: dict[str, Any] | None = None,
        cache: EvidenceCache | None = None,
        rate_limiter: FileRateLimiter | None = None,
        resolver: Callable[..., Any] = socket.getaddrinfo,
    ) -> None:
        self.registry = registry or load_evidence_registry()
        self.cache = cache or EvidenceCache()
        self.rate_limiter = rate_limiter or FileRateLimiter()
        self.resolver = resolver

    def _config(self, source: dict[str, Any], key: str, fallback: Any) -> Any:
        if key in source:
            return source[key]
        return self.registry.get("defaults", {}).get(key, fallback)

    def fetch(self, source_id: str, url: str) -> EvidenceFetchResult:
        return self.request(source_id, url, method="GET")

    def request(
        self,
        source_id: str,
        url: str,
        *,
        method: str,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> EvidenceFetchResult:
        source = get_evidence_source(self.registry, source_id)
        method = method.upper().strip()
        allowed_methods = {
            str(value).upper()
            for value in source.get("allowed_methods") or ["GET"]
        }
        if method not in allowed_methods:
            raise EvidencePolicyError("EVIDENCE_METHOD_NOT_ALLOWED")
        if method not in {"GET", "POST"}:
            raise EvidencePolicyError("EVIDENCE_METHOD_UNSUPPORTED")
        body = body or b""
        if method == "GET" and body:
            raise EvidencePolicyError("EVIDENCE_GET_BODY_REFUSED")
        max_request_bytes = int(
            self._config(source, "max_request_bytes", 65_536)
        )
        if len(body) > max_request_bytes:
            raise EvidencePolicyError("EVIDENCE_REQUEST_TOO_LARGE")
        request_body_sha256 = hashlib.sha256(body).hexdigest() if body else ""
        canonical = validate_evidence_url(
            source,
            url,
            resolver=self.resolver,
        )
        ttl = int(self._config(source, "cache_ttl_seconds", 3600))
        cached = self.cache.load_index(
            source_id,
            canonical,
            method=method,
            request_body_sha256=request_body_sha256,
        )
        now = time.time()
        if cached is not None:
            fetched_epoch = float(cached.get("fetched_epoch") or 0)
            age = max(now - fetched_epoch, 0.0)
            if age <= ttl:
                return EvidenceFetchResult(
                    receipt=self._receipt_from_index(cached, True, age),
                    body_path=self.cache.body_path(cached["content_sha256"]),
                )

        rate = source.get("rate_limit") or {"requests": 10, "window_seconds": 60}
        self.rate_limiter.acquire(
            source_id,
            requests=int(rate.get("requests", 10)),
            window_seconds=int(rate.get("window_seconds", 60)),
            now=now,
        )
        headers = {
            "User-Agent": str(
                self.registry.get("defaults", {}).get(
                    "user_agent", "DichiarazioniPubbliche/0.1 evidence-retrieval"
                )
            ),
            "Accept": ", ".join(source.get("accepted_content_types") or ["*/*"]),
            "Accept-Encoding": "identity",
        }
        if body:
            if not content_type:
                raise EvidencePolicyError("EVIDENCE_POST_CONTENT_TYPE_REQUIRED")
            headers["Content-Type"] = content_type
        if cached:
            if cached.get("etag"):
                headers["If-None-Match"] = str(cached["etag"])
            if cached.get("last_modified"):
                headers["If-Modified-Since"] = str(cached["last_modified"])

        request = urllib.request.Request(
            canonical,
            data=body if body else None,
            headers=headers,
            method=method,
        )
        opener = urllib.request.build_opener(
            _PolicyRedirectHandler(
                source,
                self.resolver,
                int(self._config(source, "redirect_limit", 4)),
            )
        )
        timeout = float(self._config(source, "read_timeout_seconds", 20))
        limit = int(self._config(source, "max_response_bytes", 8_388_608))
        try:
            response = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 304 and cached:
                cached = {**cached, "fetched_epoch": now, "fetched_at": _iso_now()}
                body = self.cache.body_path(cached["content_sha256"]).read_bytes()
                self.cache.store(
                    source_id,
                    canonical,
                    body,
                    cached,
                    method=method,
                    request_body_sha256=request_body_sha256,
                )
                return EvidenceFetchResult(
                    receipt=self._receipt_from_index(cached, True, 0.0),
                    body_path=self.cache.body_path(cached["content_sha256"]),
                )
            raise
        with response:
            final_url = validate_evidence_url(
                source,
                response.geturl(),
                resolver=self.resolver,
            )
            status = int(getattr(response, "status", 200))
            if status != 200:
                raise EvidencePolicyError(f"EVIDENCE_HTTP_{status}")
            content_type = response.headers.get_content_type().lower()
            accepted = [
                value.lower()
                for value in source.get("accepted_content_types") or []
            ]
            if accepted and not any(
                content_type == value or content_type.startswith(value)
                for value in accepted
            ):
                raise EvidencePolicyError(
                    f"EVIDENCE_CONTENT_TYPE_REFUSED:{content_type}"
                )
            body = response.read(limit + 1)
            if len(body) > limit:
                raise EvidencePolicyError("EVIDENCE_RESPONSE_TOO_LARGE")
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except (TypeError, ValueError) as exc:
                    raise EvidencePolicyError(
                        "EVIDENCE_CONTENT_LENGTH_INVALID"
                    ) from exc
                if declared_length < 0:
                    raise EvidencePolicyError("EVIDENCE_CONTENT_LENGTH_INVALID")
                if declared_length > limit:
                    raise EvidencePolicyError("EVIDENCE_RESPONSE_TOO_LARGE")
                if len(body) != declared_length:
                    raise EvidencePolicyError("EVIDENCE_RESPONSE_INCOMPLETE")
            digest = hashlib.sha256(body).hexdigest()
            fetched_at = _iso_now()
            metadata = {
                "source_id": source_id,
                "canonical_url": canonical,
                "final_url": final_url,
                "fetched_epoch": now,
                "fetched_at": fetched_at,
                "http_status": status,
                "content_type": content_type,
                "content_sha256": digest,
                "response_bytes": len(body),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "authoritative": bool(source.get("authoritative", False)),
                "evidence_class": str(source.get("evidence_class") or ""),
                "publisher": str(source.get("publisher") or source_id),
                "request_method": method,
                "request_body_sha256": request_body_sha256 or None,
            }
            body_path = self.cache.store(
                source_id,
                canonical,
                body,
                metadata,
                method=method,
                request_body_sha256=request_body_sha256,
            )
            return EvidenceFetchResult(
                receipt=self._receipt_from_index(metadata, False, None),
                body_path=body_path,
            )

    @staticmethod
    def _receipt_from_index(
        payload: dict[str, Any],
        from_cache: bool,
        cache_age_seconds: float | None,
    ) -> EvidenceFetchReceipt:
        return EvidenceFetchReceipt(
            source_id=str(payload["source_id"]),
            canonical_url=str(payload["canonical_url"]),
            final_url=str(payload["final_url"]),
            fetched_at=str(payload["fetched_at"]),
            http_status=int(payload["http_status"]),
            content_type=str(payload["content_type"]),
            content_sha256=str(payload["content_sha256"]),
            response_bytes=int(payload["response_bytes"]),
            etag=payload.get("etag"),
            last_modified=payload.get("last_modified"),
            from_cache=from_cache,
            cache_age_seconds=(
                round(float(cache_age_seconds), 3)
                if cache_age_seconds is not None
                else None
            ),
            authoritative=bool(payload.get("authoritative", False)),
            evidence_class=str(payload.get("evidence_class") or ""),
            publisher=str(payload.get("publisher") or ""),
        )


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def deterministic_evidence_id(
    source_id: str,
    canonical_url: str,
    content_sha256: str,
) -> str:
    material = "\0".join(
        (source_id, normalized_url(canonical_url), content_sha256.lower())
    ).encode()
    return "evidence:" + hashlib.sha256(material).hexdigest()


def receipt_json(result: EvidenceFetchResult) -> dict[str, Any]:
    payload = asdict(result.receipt)
    payload["body_path"] = "<private-content-addressed>"
    return payload
