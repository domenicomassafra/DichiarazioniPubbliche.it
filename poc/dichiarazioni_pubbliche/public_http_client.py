from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Mapping

from dichiarazioni_pubbliche.openapi import OPENAPI_VERSION
from dichiarazioni_pubbliche.public_api import (
    API_BASE_PATH,
    API_CONTRACT_VERSION,
    API_VERSION_HEADER,
)
from dichiarazioni_pubbliche.public_schema import (
    DOSSIER_REQUIRED_KEYS,
    PUBLIC_SCHEMA_VERSION,
    PublicSchemaValidationError,
    validate_dossier,
)


PUBLIC_CLIENT_CONTRACT_VERSION = "public-http-client-contract-v1"
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
ABSOLUTE_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
ALLOWED_METHODS = frozenset({"GET", "HEAD"})
MAX_DEPRECATION_HEADER_CHARS = 256
MAX_SUNSET_HEADER_CHARS = 128

_CORRECTION_KEYS = frozenset(
    {"id", "finding_id", "previous_finding_id", "reason", "changed_fields", "created_at"}
)
_RIGHT_OF_REPLY_KEYS = frozenset(
    {"id", "submitter_name", "submitter_role", "submitted_at", "body", "evidence_urls", "status"}
)
_RELATION_KEYS = frozenset(
    {
        "id",
        "relation_type",
        "relation_version",
        "status",
        "role",
        "related_claim_id",
        "related_claim",
        "related_statement_date",
        "rationale_codes",
        "review_event_id",
    }
)
_PRIVATE_OR_RAW_EXACT_KEYS = frozenset(
    {
        "correction_reason_private",
        "evidence_body",
        "internal_note",
        "internal_notes",
        "private_note",
        "private_notes",
        "provider_prompt",
        "provider_receipt",
        "provider_receipts",
        "raw_body",
        "raw_evidence",
        "raw_transcript",
        "raw_transcript_text",
        "transcript_text",
    }
)


class PublicClientError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class PublicClientContractMetadata:
    client_contract_version: str
    supported_api_versions: tuple[str, ...]
    public_schema_version: str
    source_openapi_version: str


PUBLIC_CLIENT_METADATA = PublicClientContractMetadata(
    client_contract_version=PUBLIC_CLIENT_CONTRACT_VERSION,
    supported_api_versions=(API_CONTRACT_VERSION,),
    public_schema_version=PUBLIC_SCHEMA_VERSION,
    source_openapi_version=OPENAPI_VERSION,
)


@dataclass(frozen=True)
class PublicDeprecationMetadata:
    deprecation: str
    sunset: str


@dataclass(frozen=True)
class PublicClientResponse:
    status: int
    data: Any
    meta: Mapping[str, Any] | None
    etag: str | None
    last_modified: str | None
    cache_control: str | None
    api_version: str
    deprecation: PublicDeprecationMetadata | None = None
    not_modified: bool = False


def _bounded_text(value: object, *, field: str, maximum: int, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or len(value) > maximum:
        raise PublicClientError("RESPONSE_SCHEMA_INVALID", f"Public response {field} is invalid or unbounded.")
    return value


def _exact_keys(value: object, *, field: str, allowed: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != allowed:
        raise PublicClientError("RESPONSE_SCHEMA_INVALID", f"Public response {field} is outside the bounded schema.")
    return value


def _reject_private_or_raw_fields(value: object, *, path: str = "data") -> None:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key).strip().lower().replace("-", "_")
            current = f"{path}.{raw_key}"
            if (
                key in _PRIVATE_OR_RAW_EXACT_KEYS
                or key.startswith("private_")
                or key.startswith("raw_")
                or key.endswith("_private")
            ):
                raise PublicClientError(
                    "PRIVATE_FIELD_FORBIDDEN",
                    f"Public response contains a private/raw field at {current}.",
                )
            _reject_private_or_raw_fields(child, path=current)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_private_or_raw_fields(child, path=f"{path}[{index}]")


def _validate_dossier_extensions(dossier: dict[str, Any]) -> None:
    for index, raw in enumerate(dossier.get("corrections") or []):
        correction = _exact_keys(raw, field=f"corrections[{index}]", allowed=_CORRECTION_KEYS)
        _bounded_text(correction["id"], field="correction.id", maximum=512)
        _bounded_text(correction["finding_id"], field="correction.finding_id", maximum=300)
        _bounded_text(
            correction["previous_finding_id"], field="correction.previous_finding_id", maximum=300
        )
        _bounded_text(correction["reason"], field="correction.reason", maximum=2000)
        _bounded_text(correction["created_at"], field="correction.created_at", maximum=64)
        if not isinstance(correction["changed_fields"], dict):
            raise PublicClientError("RESPONSE_SCHEMA_INVALID", "Public correction changed_fields must be an object.")
        encoded = json.dumps(
            correction["changed_fields"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > 32_768:
            raise PublicClientError("RESPONSE_SCHEMA_INVALID", "Public correction changed_fields exceeds its bound.")

    for index, raw in enumerate(dossier.get("rights_of_reply") or []):
        reply = _exact_keys(raw, field=f"rights_of_reply[{index}]", allowed=_RIGHT_OF_REPLY_KEYS)
        _bounded_text(reply["id"], field="right_of_reply.id", maximum=512)
        _bounded_text(reply["submitter_name"], field="right_of_reply.submitter_name", maximum=300, allow_none=True)
        _bounded_text(reply["submitter_role"], field="right_of_reply.submitter_role", maximum=300, allow_none=True)
        _bounded_text(reply["submitted_at"], field="right_of_reply.submitted_at", maximum=64)
        _bounded_text(reply["body"], field="right_of_reply.body", maximum=4000)
        if reply["status"] != "PUBLISHED":
            raise PublicClientError("RESPONSE_SCHEMA_INVALID", "Only published right-of-reply data is public.")
        urls = reply["evidence_urls"]
        if not isinstance(urls, list) or len(urls) > 32:
            raise PublicClientError("RESPONSE_SCHEMA_INVALID", "Public right-of-reply evidence_urls is unbounded.")
        for url in urls:
            _bounded_text(url, field="right_of_reply.evidence_url", maximum=2048)

    for index, raw in enumerate(dossier.get("relations") or []):
        relation = _exact_keys(raw, field=f"relations[{index}]", allowed=_RELATION_KEYS)
        _bounded_text(relation["id"], field="relation.id", maximum=512)
        _bounded_text(relation["relation_type"], field="relation.relation_type", maximum=200)
        _bounded_text(relation["relation_version"], field="relation.relation_version", maximum=200)
        if relation["status"] != "APPROVED":
            raise PublicClientError("RESPONSE_SCHEMA_INVALID", "Candidate/unapproved relation data is not public.")
        _bounded_text(relation["role"], field="relation.role", maximum=200)
        _bounded_text(relation["related_claim_id"], field="relation.related_claim_id", maximum=300)
        _bounded_text(relation["related_claim"], field="relation.related_claim", maximum=4000)
        _bounded_text(
            relation["related_statement_date"],
            field="relation.related_statement_date",
            maximum=64,
            allow_none=True,
        )
        _bounded_text(relation["review_event_id"], field="relation.review_event_id", maximum=512)
        codes = relation["rationale_codes"]
        if not isinstance(codes, list) or len(codes) > 32:
            raise PublicClientError("RESPONSE_SCHEMA_INVALID", "Public relation rationale_codes is unbounded.")
        for code in codes:
            _bounded_text(code, field="relation.rationale_code", maximum=200)


def _validate_public_data(data: Any, *, request_path: str) -> None:
    _reject_private_or_raw_fields(data)
    is_finding_detail = request_path.startswith(API_BASE_PATH + "/findings/")
    looks_like_dossier = isinstance(data, dict) and bool(DOSSIER_REQUIRED_KEYS.intersection(data))
    if not is_finding_detail and not looks_like_dossier:
        return
    if not isinstance(data, dict):
        raise PublicClientError("RESPONSE_SCHEMA_INVALID", "Public finding detail must be an object.")
    try:
        validate_dossier(data)
    except PublicSchemaValidationError as exc:
        raise PublicClientError("RESPONSE_SCHEMA_INVALID", "Public finding detail violates the public schema.") from exc
    _validate_dossier_extensions(data)


def _deprecation_metadata(headers) -> PublicDeprecationMetadata | None:  # noqa: ANN001
    raw_deprecation = headers.get("Deprecation")
    raw_sunset = headers.get("Sunset")
    if raw_deprecation is None and raw_sunset is None:
        return None
    if raw_deprecation is None or raw_sunset is None:
        raise PublicClientError(
            "DEPRECATION_HEADERS_INVALID",
            "Deprecated endpoints must provide both Deprecation and Sunset headers.",
        )
    deprecation = str(raw_deprecation).strip()
    sunset = str(raw_sunset).strip()
    if (
        not deprecation
        or len(deprecation) > MAX_DEPRECATION_HEADER_CHARS
        or not sunset
        or len(sunset) > MAX_SUNSET_HEADER_CHARS
    ):
        raise PublicClientError("DEPRECATION_HEADERS_INVALID", "Deprecation metadata is missing or unbounded.")
    try:
        parsed_sunset = parsedate_to_datetime(sunset)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PublicClientError("DEPRECATION_HEADERS_INVALID", "Sunset must be a valid HTTP-date.") from exc
    if parsed_sunset.tzinfo is None:
        raise PublicClientError("DEPRECATION_HEADERS_INVALID", "Sunset must include a timezone.")
    return PublicDeprecationMetadata(deprecation=deprecation, sunset=sunset)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


def _validate_base_url(base_url: str, *, allow_test_loopback: bool) -> str:
    try:
        parsed = urllib.parse.urlsplit(base_url)
    except ValueError as exc:
        raise PublicClientError("BASE_URL_INVALID", "Invalid public API base URL.") from exc
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise PublicClientError("BASE_URL_INVALID", "Public API base URL must not contain credentials/query/fragment.")
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme == "https" and hostname:
        pass
    elif allow_test_loopback and parsed.scheme == "http" and hostname in {"127.0.0.1", "::1", "localhost"}:
        pass
    else:
        raise PublicClientError("BASE_URL_UNSAFE", "Public API base URL must use HTTPS (loopback HTTP is test-only).")
    path = parsed.path.rstrip("/")
    if path and path != API_BASE_PATH:
        raise PublicClientError("BASE_URL_PATH_INVALID", f"Expected base path {API_BASE_PATH}.")
    netloc = parsed.netloc
    return urllib.parse.urlunsplit((parsed.scheme, netloc, API_BASE_PATH, "", ""))


class PublicHttpClient:
    """Draft internal reader for the stable public HTTP contract.

    This is a contract harness, not a published SDK. It intentionally exposes no
    authentication, provider, database, filesystem, intake, approval or mutation API.
    """

    def __init__(
        self,
        base_url: str,
        *,
        expected_api_version: str = API_CONTRACT_VERSION,
        expected_schema_version: str = PUBLIC_SCHEMA_VERSION,
        expected_dataset_fingerprint: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_retries: int = 1,
        allow_test_loopback: bool = False,
    ) -> None:
        self.base_url = _validate_base_url(base_url, allow_test_loopback=allow_test_loopback)
        if expected_api_version != API_CONTRACT_VERSION:
            raise PublicClientError("CLIENT_API_VERSION_UNSUPPORTED", "Client only supports the accepted v1 contract.")
        if expected_schema_version != PUBLIC_SCHEMA_VERSION:
            raise PublicClientError("CLIENT_SCHEMA_VERSION_UNSUPPORTED", "Client only supports the accepted public schema.")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not (0 < timeout_seconds <= MAX_TIMEOUT_SECONDS):
            raise PublicClientError("TIMEOUT_INVALID", "Timeout must be positive and bounded.")
        if not isinstance(max_response_bytes, int) or isinstance(max_response_bytes, bool) or not (1 <= max_response_bytes <= ABSOLUTE_MAX_RESPONSE_BYTES):
            raise PublicClientError("RESPONSE_LIMIT_INVALID", "Response size limit is invalid.")
        if not isinstance(max_retries, int) or isinstance(max_retries, bool) or not (0 <= max_retries <= 2):
            raise PublicClientError("RETRY_LIMIT_INVALID", "Retry count must be between 0 and 2.")
        if expected_dataset_fingerprint is not None:
            fingerprint = str(expected_dataset_fingerprint).lower().strip()
            if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
                raise PublicClientError("DATASET_FINGERPRINT_INVALID", "Expected dataset fingerprint must be SHA-256.")
            self.expected_dataset_fingerprint = fingerprint
        else:
            self.expected_dataset_fingerprint = None
        self.expected_api_version = expected_api_version
        self.expected_schema_version = expected_schema_version
        self.timeout_seconds = float(timeout_seconds)
        self.max_response_bytes = max_response_bytes
        self.max_retries = max_retries
        self.contract_metadata = PUBLIC_CLIENT_METADATA
        self._opener = urllib.request.build_opener(_NoRedirect())

    def _url(self, relative_path: str) -> str:
        path = str(relative_path or "").strip()
        if not path.startswith("/"):
            path = "/" + path
        if path.startswith(API_BASE_PATH + "/") or path == API_BASE_PATH:
            full_path = path
        else:
            full_path = API_BASE_PATH + path
        split = urllib.parse.urlsplit(full_path)
        if split.scheme or split.netloc or ".." in split.path.split("/"):
            raise PublicClientError("CLIENT_PATH_INVALID", "Only bounded same-origin public API paths are allowed.")
        base = urllib.parse.urlsplit(self.base_url)
        return urllib.parse.urlunsplit((base.scheme, base.netloc, split.path, split.query, ""))

    def request(
        self,
        relative_path: str,
        *,
        method: str = "GET",
        etag: str | None = None,
    ) -> PublicClientResponse:
        normalized_method = str(method or "").upper()
        if normalized_method not in ALLOWED_METHODS:
            raise PublicClientError("METHOD_NOT_ALLOWED", "Draft public client is read-only; only GET and HEAD are allowed.", status=405)
        url = self._url(relative_path)
        headers = {
            "Accept": "application/json",
            "User-Agent": f"DichiarazioniPubblicheContractHarness/{PUBLIC_CLIENT_CONTRACT_VERSION}",
        }
        if etag:
            headers["If-None-Match"] = str(etag)[:256]
        attempts = self.max_retries + 1
        last_error: PublicClientError | None = None
        for attempt in range(attempts):
            request = urllib.request.Request(url, headers=headers, method=normalized_method)
            try:
                return self._perform(request, normalized_method)
            except PublicClientError as exc:
                last_error = exc
                if exc.status not in {502, 503, 504} or attempt + 1 >= attempts:
                    raise
            except (TimeoutError, socket.timeout) as exc:
                last_error = PublicClientError("TIMEOUT", "Public API request timed out.")
                if attempt + 1 >= attempts:
                    raise last_error from exc
        assert last_error is not None
        raise last_error

    def _perform(self, request: urllib.request.Request, method: str) -> PublicClientResponse:
        try:
            response = self._opener.open(request, timeout=self.timeout_seconds)
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                deprecation = self._validate_headers(exc.headers)
                return PublicClientResponse(
                    status=304,
                    data=None,
                    meta=None,
                    etag=exc.headers.get("ETag"),
                    last_modified=exc.headers.get("Last-Modified"),
                    cache_control=exc.headers.get("Cache-Control"),
                    api_version=self.expected_api_version,
                    deprecation=deprecation,
                    not_modified=True,
                )
            if 300 <= exc.code < 400:
                raise PublicClientError("REDIRECT_FORBIDDEN", "Public API redirects are not followed.", status=exc.code) from exc
            body = self._read_bounded(exc)
            code = "HTTP_ERROR"
            message = f"Public API returned HTTP {exc.code}."
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
                error = payload.get("error") if isinstance(payload, dict) else None
                if isinstance(error, dict):
                    code = str(error.get("code") or code)[:128]
                    message = str(error.get("message") or message)[:500]
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
            raise PublicClientError(code, message, status=exc.code) from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                raise PublicClientError("TIMEOUT", "Public API request timed out.") from exc
            raise PublicClientError("TRANSPORT_ERROR", "Public API transport failed.") from exc

        status = int(response.status)
        headers = response.headers
        deprecation = self._validate_headers(headers)
        content_type = str(headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise PublicClientError("CONTENT_TYPE_INVALID", "Public API response is not application/json.", status=status)
        body = b"" if method == "HEAD" else self._read_bounded(response)
        if method == "HEAD":
            return PublicClientResponse(
                status=status,
                data=None,
                meta=None,
                etag=headers.get("ETag"),
                last_modified=headers.get("Last-Modified"),
                cache_control=headers.get("Cache-Control"),
                api_version=self.expected_api_version,
                deprecation=deprecation,
            )
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PublicClientError("MALFORMED_JSON", "Public API returned malformed JSON.", status=status) from exc
        if not isinstance(payload, dict) or set(payload) != {"data", "meta"} or not isinstance(payload["meta"], dict):
            raise PublicClientError("ENVELOPE_INVALID", "Public API envelope is invalid.", status=status)
        meta = payload["meta"]
        if meta.get("api_version") != self.expected_api_version:
            raise PublicClientError("API_VERSION_MISMATCH", "Public API body version is incompatible.", status=status)
        if meta.get("public_schema_version") != self.expected_schema_version:
            raise PublicClientError("SCHEMA_VERSION_MISMATCH", "Public projection schema is incompatible.", status=status)
        fingerprint = str(meta.get("dataset_fingerprint") or "").lower()
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise PublicClientError("DATASET_FINGERPRINT_MISSING", "Public response lacks a valid dataset fingerprint.", status=status)
        if self.expected_dataset_fingerprint is not None and fingerprint != self.expected_dataset_fingerprint:
            raise PublicClientError("STALE_PROJECTION", "Public response does not match the expected projection fingerprint.", status=status)
        _validate_public_data(payload["data"], request_path=urllib.parse.urlsplit(request.full_url).path)
        return PublicClientResponse(
            status=status,
            data=payload["data"],
            meta=meta,
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
            cache_control=headers.get("Cache-Control"),
            api_version=self.expected_api_version,
            deprecation=deprecation,
        )

    def _validate_headers(self, headers) -> PublicDeprecationMetadata | None:  # noqa: ANN001
        version = str(headers.get(API_VERSION_HEADER) or "")
        if version != self.expected_api_version:
            raise PublicClientError("API_VERSION_HEADER_MISMATCH", "Public API version header is missing or incompatible.")
        return _deprecation_metadata(headers)

    def _read_bounded(self, response) -> bytes:  # noqa: ANN001
        length = response.headers.get("Content-Length")
        if length:
            try:
                if int(length) > self.max_response_bytes:
                    raise PublicClientError("RESPONSE_TOO_LARGE", "Public API response exceeds the configured size bound.")
            except ValueError as exc:
                raise PublicClientError("CONTENT_LENGTH_INVALID", "Public API Content-Length is invalid.") from exc
        body = response.read(self.max_response_bytes + 1)
        if len(body) > self.max_response_bytes:
            raise PublicClientError("RESPONSE_TOO_LARGE", "Public API response exceeds the configured size bound.")
        return body


__all__ = [
    "ABSOLUTE_MAX_RESPONSE_BYTES",
    "ALLOWED_METHODS",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_DEPRECATION_HEADER_CHARS",
    "MAX_SUNSET_HEADER_CHARS",
    "PUBLIC_CLIENT_CONTRACT_VERSION",
    "PUBLIC_CLIENT_METADATA",
    "PublicClientError",
    "PublicClientContractMetadata",
    "PublicDeprecationMetadata",
    "PublicClientResponse",
    "PublicHttpClient",
]
