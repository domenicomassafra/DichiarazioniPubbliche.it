"""Optional, provider-pinned oEmbed metadata lookup (private capture context only).

Never use untrusted HTML-discovered endpoint URLs as network destinations. The only
supported provider is Vimeo's documented JSON endpoint; all requests are explicit
source-policy opt-ins, bounded and refused on redirect or non-public DNS answers.
"""

from __future__ import annotations

import hashlib
import json
import re
import socket
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable
from urllib.parse import quote, urlsplit

from dichiarazioni_pubbliche.source_watcher import (
    FetchedBytes, _DiscoveryHTTPSHandler, validate_discovery_url,
)

OEMBED_LOOKUP_VERSION = "private-oembed-lookup-v1"
OEMBED_MAX_RESPONSE_BYTES = 8_192
OEMBED_TIMEOUT_SECONDS = 3.0
_VIMEO_ENDPOINT = "https://vimeo.com/api/oembed.json"
_VIMEO_PATH = re.compile(r"/[0-9]{1,20}/?")


@dataclass(frozen=True)
class OEmbedLookupReceipt:
    status: str
    reason_code: str
    provider: str = "vimeo"
    title_candidate: str | None = None
    author_candidate: str | None = None
    provider_candidate: str | None = None
    response_sha256: str | None = None
    contract_version: str = OEMBED_LOOKUP_VERSION
    publication_authority: bool = False
    identity_mutation_allowed: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _DuplicateOEmbedKey(ValueError):
    """An ambiguous provider payload cannot establish a canonical identity."""


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateOEmbedKey("OEMBED_JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def fetch_oembed_json(url: str, *, timeout: float, max_response_bytes: int) -> FetchedBytes:
    """Perform one GET, with no redirects/cookies/auth and the existing DNS SSRF guard."""
    if type(max_response_bytes) is not int or not 1 <= max_response_bytes <= OEMBED_MAX_RESPONSE_BYTES:
        raise ValueError("OEMBED_RESPONSE_LIMIT_INVALID")
    validate_discovery_url(url)
    # URL prevalidation by itself is not a socket-level SSRF guarantee: DNS
    # may change between validation and urllib's TCP connection. Reuse the
    # HTTPS transport that vets answers again at connect and pins the peer,
    # preserving the original hostname for TLS SNI/certificate validation.
    opener = urllib.request.build_opener(
        _NoRedirect(), urllib.request.ProxyHandler({}),
        _DiscoveryHTTPSHandler(socket.getaddrinfo),
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "DichiarazioniPubbliche.it/0.0.1",
        },
        method="GET",
    )
    with opener.open(request, timeout=timeout) as response:
        if response.geturl() != url:
            raise ValueError("OEMBED_REDIRECT_REFUSED")
        if type(response.status) is not int or response.status != 200:
            raise ValueError("OEMBED_HTTP_STATUS_INVALID")
        declared = response.headers.get("Content-Length")
        if declared is not None:
            try:
                expected_length = int(declared)
            except (TypeError, ValueError):
                raise ValueError("OEMBED_CONTENT_LENGTH_INVALID") from None
            if expected_length < 0:
                raise ValueError("OEMBED_CONTENT_LENGTH_INVALID")
            if expected_length > max_response_bytes:
                raise ValueError("OEMBED_RESPONSE_TOO_LARGE")
        body = response.read(max_response_bytes + 1)
        if len(body) > max_response_bytes:
            raise ValueError("OEMBED_RESPONSE_TOO_LARGE")
        if declared is not None and len(body) != expected_length:
            raise ValueError("OEMBED_RESPONSE_INCOMPLETE")
        content_type = response.headers.get_content_type()
        if content_type != "application/json":
            raise ValueError("OEMBED_CONTENT_TYPE_INVALID")
        return FetchedBytes(
            body=body,
            final_url=url,
            status_code=response.status,
            media_type=content_type,
            charset=response.headers.get_content_charset(),
            content_length=len(body),
        )


def _bounded(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    clean = " ".join(value.split()).strip()
    if (
        not clean
        or len(clean) > 1024
        or any(ord(char) < 32 for char in clean)
        or "<" in clean
        or ">" in clean
    ):
        return None
    return clean


def _eligible_vimeo_url(content_url: str) -> str | None:
    if not isinstance(content_url, str) or len(content_url) > 2048:
        return None
    try:
        parsed = urlsplit(content_url)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"vimeo.com", "www.vimeo.com"}
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.fragment
        or parsed.query
        or not _VIMEO_PATH.fullmatch(parsed.path)
    ):
        return None
    return "https://vimeo.com" + parsed.path.rstrip("/")


def lookup_vimeo_oembed(
    content_url: str,
    *,
    fetcher: Callable[..., FetchedBytes] = fetch_oembed_json,
) -> OEmbedLookupReceipt:
    """Fetch only a public Vimeo video, return allowlisted non-authoritative fields.

    Failure never contains the raw untrusted endpoint, response, HTML or exception.
    The caller is responsible for source permission and private-only persistence.
    """
    safe_video_url = _eligible_vimeo_url(content_url)
    if safe_video_url is None:
        return OEmbedLookupReceipt(status="NOT_APPLICABLE", reason_code="PROVIDER_OR_URL_NOT_ALLOWED")
    endpoint = _VIMEO_ENDPOINT + "?url=" + quote(safe_video_url, safe="")
    try:
        fetched = fetcher(
            endpoint,
            timeout=OEMBED_TIMEOUT_SECONDS,
            max_response_bytes=OEMBED_MAX_RESPONSE_BYTES,
        )
        if (
            not isinstance(fetched, FetchedBytes)
            or
            fetched.final_url != endpoint
            or type(fetched.status_code) is not int
            or fetched.status_code != 200
            or not isinstance(fetched.media_type, str)
            or fetched.media_type.split(";", 1)[0].strip().lower() != "application/json"
            or not isinstance(fetched.body, bytes)
            or len(fetched.body) > OEMBED_MAX_RESPONSE_BYTES
            or type(fetched.content_length) is not int
            or fetched.content_length != len(fetched.body)
        ):
            return OEmbedLookupReceipt(status="FAILED", reason_code="OEMBED_RESPONSE_INVALID")
        try:
            payload = json.loads(
                fetched.body.decode("utf-8"), object_pairs_hook=_unique_json_object,
            )
        except _DuplicateOEmbedKey:
            return OEmbedLookupReceipt(status="FAILED", reason_code="OEMBED_SCHEMA_INVALID")
        if (
            not isinstance(payload, dict)
            or payload.get("version") != "1.0"
            or payload.get("type") != "video"
            or payload.get("provider_name") != "Vimeo"
        ):
            return OEmbedLookupReceipt(status="FAILED", reason_code="OEMBED_SCHEMA_INVALID")
        title = _bounded(payload.get("title"))
        author = _bounded(payload.get("author_name"))
        if title is None and author is None:
            return OEmbedLookupReceipt(status="FAILED", reason_code="OEMBED_NO_SAFE_FIELDS")
        return OEmbedLookupReceipt(
            status="SUCCEEDED",
            reason_code="OEMBED_METADATA_PRIVATE",
            title_candidate=title,
            author_candidate=author,
            provider_candidate="Vimeo",
            response_sha256=hashlib.sha256(fetched.body).hexdigest(),
        )
    except Exception:
        # Custom adapters may raise exceptions containing credentials or source
        # metadata. Return only the stable, non-sensitive failure receipt.
        return OEmbedLookupReceipt(status="FAILED", reason_code="OEMBED_FETCH_OR_PARSE_FAILED")


__all__ = [
    "OEMBED_LOOKUP_VERSION",
    "OEMBED_MAX_RESPONSE_BYTES",
    "OEMBED_TIMEOUT_SECONDS",
    "OEmbedLookupReceipt",
    "fetch_oembed_json",
    "lookup_vimeo_oembed",
]
