from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urljoin, urlsplit

from dichiarazioni_pubbliche.corpus_repository import (
    ContentCaptureRecord,
    INSERT_PASSAGE_SQL_V1,
    PassageRecord,
    deterministic_corpus_id,
)
from dichiarazioni_pubbliche.capture_authorization import PrivateCaptureAuthorizationBlocked
from dichiarazioni_pubbliche.discovery_provenance import valid_discovery_hit_groups_sql
from dichiarazioni_pubbliche.corpus_retention import (
    COMPLETE_CAPTURE_ARCHIVE_SQL_V1,
    MARK_CAPTURE_ARCHIVE_PENDING_SQL_V1,
    REQUEST_CAPTURE_ARCHIVE_SQL_V1,
    lifecycle_event_id,
)
from dichiarazioni_pubbliche.ingestion_relevance import (
    deterministic_ingestion_operation_ref,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.source_watcher import (
    MAX_DISCOVERY_RESPONSE_BYTES,
    FetchedBytes,
    fetch_bytes,
)
from dichiarazioni_pubbliche.source_oembed_lookup import (
    fetch_oembed_json,
    lookup_vimeo_oembed,
)


CAPTURE_PIPELINE_VERSION = "capture-pipeline-v1"
SAFE_HTTP_RETRIEVAL_VERSION = "safe-http-capture-v1"
STDLIB_HTML_PARSER_VERSION = "stdlib-visible-text-v1"
MAX_PARSED_TEXT_CHARS = 512_000
MAX_PASSAGE_CHARS = 4_000
MAX_PASSAGES = 256

_SECRET_KEY_RE = re.compile(
    r"(?:authorization|cookie|credential|password|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)",
    re.I,
)


class CapturePipelineError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "CAPTURE_PIPELINE_FAILURE").strip().upper()[:120]
        super().__init__(self.code)


@dataclass(frozen=True)
class BodyStoreReceipt:
    state: str
    body_ref: str
    content_sha256: str
    bytes_written: int


@dataclass(frozen=True)
class ParsedSpan:
    start_char: int
    end_char: int
    text: str
    text_sha256: str


@dataclass(frozen=True)
class ParseResult:
    status: str
    parser_method: str
    parser_version: str
    canonical_text: str = ""
    spans: tuple[ParsedSpan, ...] = ()
    error_category: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArchiveResult:
    status: str
    provider: str
    receipt: dict[str, Any]


@dataclass(frozen=True)
class CaptureEnrichmentPolicy:
    metadata_enabled: bool = True
    archive_enabled: bool = True
    oembed_lookup_enabled: bool = False


def capture_enrichment_policy_from_source(
    source: Mapping[str, Any],
) -> CaptureEnrichmentPolicy:
    policy = source.get("content_policy") or {}
    if not isinstance(policy, Mapping):
        raise CapturePipelineError("SOURCE_CONTENT_POLICY_INVALID")

    values: dict[str, bool] = {}
    for key, output_key in (
        ("metadata_enrichment_enabled", "metadata_enabled"),
        ("archive_enabled", "archive_enabled"),
        ("oembed_lookup_enabled", "oembed_lookup_enabled"),
    ):
        value = policy.get(key, False if key == "oembed_lookup_enabled" else True)
        if not isinstance(value, bool):
            raise CapturePipelineError(f"SOURCE_{key.upper()}_INVALID")
        values[output_key] = value
    return CaptureEnrichmentPolicy(**values)


@dataclass(frozen=True)
class CapturePipelineReceipt:
    content_id: str
    primary_capture_id: str
    selected_capture_id: str
    capture_state: str
    content_sha256: str
    body_ref: str | None
    parse_status: str
    passage_ids: tuple[str, ...]
    passage_states: tuple[str, ...]
    browser_status: str
    archive_status: str
    reason_code: str
    oembed_status: str = "NOT_REQUESTED"


class ParserAdapter(Protocol):
    parser_method: str
    parser_version: str

    def parse(self, fetched: FetchedBytes) -> ParseResult: ...


class BrowserRenderer(Protocol):
    renderer_id: str
    renderer_version: str

    def render(self, url: str, *, max_response_bytes: int) -> FetchedBytes: ...


class ArchiveAdapter(Protocol):
    provider: str

    def archive(self, *, capture: ContentCaptureRecord, body_path: Path | None) -> ArchiveResult: ...


def _safe_mapping(value: Mapping[str, Any] | None, field_name: str) -> dict[str, Any]:
    value = dict(value or {})
    stack: list[Any] = [value]
    while stack:
        node = stack.pop()
        if isinstance(node, Mapping):
            for key, child in node.items():
                if _SECRET_KEY_RE.search(str(key)):
                    raise CapturePipelineError(f"{field_name.upper()}_SECRET_KEY_FORBIDDEN")
                if isinstance(child, (Mapping, list, tuple)):
                    stack.append(child)
        elif isinstance(node, (list, tuple)):
            stack.extend(x for x in node if isinstance(x, (Mapping, list, tuple)))
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > 32_768:
        raise CapturePipelineError(f"{field_name.upper()}_TOO_LARGE")
    return value


def _json(value: Mapping[str, Any] | None) -> str:
    return json.dumps(
        _safe_mapping(value, "metadata"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_media_type(value: str | None) -> str:
    return str(value or "application/octet-stream").split(";", 1)[0].strip().lower()


def _validate_fetched_resource(fetched: FetchedBytes, *, max_response_bytes: int) -> None:
    if not isinstance(fetched.body, bytes):
        raise CapturePipelineError("CAPTURE_BODY_INVALID")
    if len(fetched.body) > max(int(max_response_bytes), 1):
        raise CapturePipelineError("CAPTURE_RESPONSE_TOO_LARGE")
    if int(fetched.content_length) != len(fetched.body):
        raise CapturePipelineError("CAPTURE_CONTENT_LENGTH_MISMATCH")
    if not 200 <= int(fetched.status_code) < 400:
        raise CapturePipelineError("CAPTURE_HTTP_STATUS_BLOCKED")
    parsed = urlsplit(str(fetched.final_url or "").strip())
    try:
        port = parsed.port
    except ValueError as exc:
        raise CapturePipelineError("CAPTURE_FINAL_URL_INVALID") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise CapturePipelineError("CAPTURE_FINAL_URL_HTTPS_REQUIRED")
    if parsed.username is not None or parsed.password is not None or port not in {None, 443}:
        raise CapturePipelineError("CAPTURE_FINAL_URL_AUTHORITY_REFUSED")
    try:
        literal = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise CapturePipelineError("CAPTURE_FINAL_URL_NONPUBLIC_IP")


def _decode(body: bytes, charset: str | None) -> str:
    candidates = [charset, "utf-8", "latin-1"]
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        key = str(candidate).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        try:
            return body.decode(key)
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", errors="replace")


class _VisibleTextHTMLParser(HTMLParser):
    _SKIP = {"script", "style", "noscript", "template", "svg", "canvas"}
    _BLOCK = {
        "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
        "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6",
        "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table",
        "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._fragments: list[str] = []

    def _boundary(self) -> None:
        if self._fragments and self._fragments[-1] != "\n\n":
            self._fragments.append("\n\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        clean = tag.casefold()
        if clean in self._SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and clean in self._BLOCK:
            self._boundary()

    def handle_endtag(self, tag: str) -> None:
        clean = tag.casefold()
        if clean in self._SKIP:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth == 0 and clean in self._BLOCK:
            self._boundary()

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data:
            self._fragments.append(data)

    def text(self) -> str:
        raw = "".join(self._fragments)
        blocks: list[str] = []
        for block in re.split(r"\n\s*\n+", raw):
            normalized = re.sub(r"\s+", " ", block).strip()
            if normalized:
                blocks.append(normalized)
        return "\n\n".join(blocks)


class _SourceMetadataHTMLParser(HTMLParser):
    _MAX_META_VALUE = 4096
    _MAX_JSON_LD_BLOCKS = 8
    _MAX_JSON_LD_CHARS = 32_768

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.meta: dict[str, str] = {}
        self.canonical_candidates: list[str] = []
        self.oembed_candidates: list[dict[str, str]] = []
        self.jsonld_blocks: list[str] = []
        self._jsonld_depth = 0
        self._jsonld_fragments: list[str] = []

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {
            str(key).casefold(): str(value or "").strip()
            for key, value in attrs
            if str(key or "").strip()
        }

    def _url(self, value: str) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        absolute = urljoin(self.base_url, raw)
        parsed = urlsplit(absolute)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        return absolute[:4096]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        clean = tag.casefold()
        values = self._attrs(attrs)
        if clean == "meta":
            key = values.get("property") or values.get("name")
            content = values.get("content")
            if key and content:
                normalized = key.casefold()[:256]
                if normalized not in self.meta:
                    self.meta[normalized] = content[: self._MAX_META_VALUE]
        elif clean == "link":
            rel = {value.casefold() for value in values.get("rel", "").split() if value}
            href = self._url(values.get("href", ""))
            if href and "canonical" in rel:
                self.canonical_candidates.append(href)
            media_type = values.get("type", "").casefold()
            if href and "alternate" in rel and media_type in {
                "application/json+oembed",
                "text/xml+oembed",
            }:
                self.oembed_candidates.append({"url": href, "type": media_type})
        elif clean == "script" and values.get("type", "").casefold() == "application/ld+json":
            if len(self.jsonld_blocks) < self._MAX_JSON_LD_BLOCKS:
                self._jsonld_depth = 1
                self._jsonld_fragments = []

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._jsonld_depth:
            raw = "".join(self._jsonld_fragments).strip()
            if raw:
                self.jsonld_blocks.append(raw[: self._MAX_JSON_LD_CHARS])
            self._jsonld_depth = 0
            self._jsonld_fragments = []

    def handle_data(self, data: str) -> None:
        if self._jsonld_depth and data:
            current = sum(len(value) for value in self._jsonld_fragments)
            remaining = max(0, self._MAX_JSON_LD_CHARS - current)
            if remaining:
                self._jsonld_fragments.append(data[:remaining])


def _jsonld_identity(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list):
        items = [item for item in (_jsonld_identity(row) for row in value[:32]) if item]
        return {"items": items} if items else None
    if not isinstance(value, Mapping):
        return None
    allowed_scalar = {
        "@type",
        "@id",
        "url",
        "name",
        "headline",
        "datePublished",
        "dateModified",
    }
    output: dict[str, Any] = {}
    for key in allowed_scalar:
        raw = value.get(key)
        if isinstance(raw, (str, int, float)) and not isinstance(raw, bool):
            output[key] = str(raw)[:4096]
    for key in ("author", "publisher"):
        raw = value.get(key)
        if isinstance(raw, Mapping):
            nested = {
                nested_key: str(raw[nested_key])[:4096]
                for nested_key in ("@type", "@id", "name", "url")
                if isinstance(raw.get(nested_key), (str, int, float))
                and not isinstance(raw.get(nested_key), bool)
            }
            if nested:
                output[key] = nested
        elif isinstance(raw, str):
            output[key] = raw[:4096]
    return output or None


def extract_source_metadata(html_text: str, *, base_url: str) -> dict[str, Any]:
    parser = _SourceMetadataHTMLParser(base_url)
    try:
        parser.feed(html_text)
        parser.close()
    except Exception as exc:
        raise CapturePipelineError("PARSER_METADATA_HTML_ERROR") from exc
    jsonld: list[dict[str, Any]] = []
    for raw in parser.jsonld_blocks:
        try:
            decoded = json.loads(raw)
        except (TypeError, ValueError):
            continue
        identity = _jsonld_identity(decoded)
        if identity:
            jsonld.append(identity)
    return {
        "canonical_url_candidates": list(dict.fromkeys(parser.canonical_candidates))[:8],
        "oembed_candidates": parser.oembed_candidates[:8],
        "meta": dict(sorted(parser.meta.items())),
        "jsonld_identity": jsonld[:8],
    }


def _split_canonical_text(text: str) -> tuple[ParsedSpan, ...]:
    spans: list[ParsedSpan] = []
    if len(text) > MAX_PARSED_TEXT_CHARS:
        raise CapturePipelineError("PARSER_TEXT_TOO_LARGE")
    cursor = 0
    for block in text.split("\n\n"):
        if not block:
            cursor += 2
            continue
        block_start = cursor
        remaining = block
        local = 0
        while remaining:
            if len(remaining) <= MAX_PASSAGE_CHARS:
                piece = remaining
            else:
                cut = remaining.rfind(" ", 0, MAX_PASSAGE_CHARS + 1)
                if cut < max(64, MAX_PASSAGE_CHARS // 2):
                    cut = MAX_PASSAGE_CHARS
                piece = remaining[:cut].rstrip()
            if not piece:
                break
            start = block_start + local
            end = start + len(piece)
            spans.append(
                ParsedSpan(
                    start_char=start,
                    end_char=end,
                    text=piece,
                    text_sha256=hashlib.sha256(piece.encode("utf-8")).hexdigest(),
                )
            )
            if len(spans) > MAX_PASSAGES:
                raise CapturePipelineError("PARSER_PASSAGE_LIMIT")
            consumed = len(piece)
            remaining = remaining[consumed:]
            skipped = len(remaining) - len(remaining.lstrip())
            remaining = remaining.lstrip()
            local += consumed + skipped
        cursor += len(block) + 2
    return tuple(spans)


class StdlibVisibleTextParser:
    parser_method = "STDLIB_VISIBLE_TEXT"
    parser_version = STDLIB_HTML_PARSER_VERSION

    def __init__(self, *, extract_metadata: bool = True) -> None:
        self.extract_metadata = bool(extract_metadata)

    def parse(self, fetched: FetchedBytes) -> ParseResult:
        media_type = _normalize_media_type(fetched.media_type)
        if media_type == "text/plain":
            raw = _decode(fetched.body, fetched.charset)
            blocks = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n+", raw)]
            canonical = "\n\n".join(part for part in blocks if part)
        elif media_type in {"text/html", "application/xhtml+xml"}:
            decoded = _decode(fetched.body, fetched.charset)
            parser = _VisibleTextHTMLParser()
            try:
                parser.feed(decoded)
                parser.close()
            except Exception:
                return ParseResult(
                    status="FAILED",
                    parser_method=self.parser_method,
                    parser_version=self.parser_version,
                    error_category="PARSER_HTML_ERROR",
                )
            canonical = parser.text()
            if self.extract_metadata:
                try:
                    metadata = extract_source_metadata(decoded, base_url=fetched.final_url)
                except CapturePipelineError:
                    metadata = {"metadata_parse_status": "FAILED"}
            else:
                metadata = {}
        else:
            return ParseResult(
                status="FAILED",
                parser_method=self.parser_method,
                parser_version=self.parser_version,
                error_category="PARSER_UNSUPPORTED_MEDIA_TYPE",
            )
        if not canonical.strip():
            return ParseResult(
                status="FAILED",
                parser_method=self.parser_method,
                parser_version=self.parser_version,
                error_category="PARSER_EMPTY_TEXT",
            )
        try:
            spans = _split_canonical_text(canonical)
        except CapturePipelineError as exc:
            return ParseResult(
                status="FAILED",
                parser_method=self.parser_method,
                parser_version=self.parser_version,
                error_category=exc.code,
            )
        if not spans:
            return ParseResult(
                status="FAILED",
                parser_method=self.parser_method,
                parser_version=self.parser_version,
                error_category="PARSER_EMPTY_TEXT",
            )
        return ParseResult(
            status="SUCCEEDED",
            parser_method=self.parser_method,
            parser_version=self.parser_version,
            canonical_text=canonical,
            spans=spans,
            metadata=(metadata if media_type in {"text/html", "application/xhtml+xml"} else {}),
        )


class CaptureBodyStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass

    @staticmethod
    def _relative_ref(capture_id: str) -> str:
        digest = hashlib.sha256(capture_id.encode("utf-8")).hexdigest()
        return f"captures/{digest[:2]}/{digest}.body"

    def _path(self, body_ref: str) -> Path:
        rel = Path(body_ref)
        if rel.is_absolute() or ".." in rel.parts or "://" in body_ref:
            raise CapturePipelineError("BODY_REF_INVALID")
        target = (self.root / rel).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise CapturePipelineError("BODY_REF_OUTSIDE_ROOT") from exc
        return target

    def write(self, *, capture_id: str, body: bytes, content_sha256: str) -> BodyStoreReceipt:
        if hashlib.sha256(body).hexdigest() != content_sha256:
            raise CapturePipelineError("BODY_HASH_MISMATCH_BEFORE_WRITE")
        body_ref = self._relative_ref(capture_id)
        target = self._path(body_ref)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(target.parent, 0o700)
        except OSError:
            pass
        if target.exists():
            if target.is_symlink() or not target.is_file():
                raise CapturePipelineError("BODY_STORE_TARGET_INVALID")
            existing = target.read_bytes()
            if hashlib.sha256(existing).hexdigest() != content_sha256:
                raise CapturePipelineError("BODY_STORE_EXISTING_HASH_MISMATCH")
            return BodyStoreReceipt("EXISTING", body_ref, content_sha256, len(existing))
        fd, tmp_name = tempfile.mkstemp(prefix=".capture-", dir=str(target.parent))
        tmp = Path(tmp_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
            try:
                os.chmod(target, 0o600)
            except OSError:
                pass
        finally:
            if tmp.exists():
                tmp.unlink()
        return BodyStoreReceipt("WRITTEN", body_ref, content_sha256, len(body))

    def read(self, body_ref: str, *, expected_sha256: str | None = None) -> bytes:
        target = self._path(body_ref)
        if not target.exists() or not target.is_file() or target.is_symlink():
            raise CapturePipelineError("BODY_FILE_MISSING")
        body = target.read_bytes()
        if expected_sha256 and hashlib.sha256(body).hexdigest() != expected_sha256:
            raise CapturePipelineError("BODY_FILE_HASH_MISMATCH")
        return body

    def path(self, body_ref: str) -> Path:
        return self._path(body_ref)


_FIND_CAPTURE_SQL = r"""
SELECT json_build_object(
    'id', id,
    'content_id', content_id,
    'observed_at', observed_at,
    'final_url', final_url,
    'media_type', media_type,
    'content_sha256', content_sha256,
    'body_ref', body_ref,
    'retrieval_method', retrieval_method,
    'retrieval_version', retrieval_version,
    'parser_method', parser_method,
    'parser_version', parser_version,
    'rights_status', rights_status,
    'retention_class', retention_class,
    'hold_status', hold_status,
    'archive_status', archive_status,
    'archive_provider', archive_provider,
    'archive_requested_at', archive_requested_at,
    'archive_completed_at', archive_completed_at,
    'archive_receipt', archive_receipt,
    'body_purged_at', body_purged_at,
    'purge_reason', purge_reason,
    'purge_receipt', purge_receipt,
    'status', status,
    'metadata', metadata
)::text
FROM content_capture
WHERE content_id=:'content_id' AND content_sha256=:'content_sha256';
""".strip()


_UPSERT_CAPTURE_SQL = r"""
WITH inserted AS (
    INSERT INTO content_capture (
        id, content_id, observed_at, final_url, media_type, content_sha256, body_ref,
        retrieval_method, retrieval_version, parser_method, parser_version,
        rights_status, retention_class, status, metadata
    ) VALUES (
        :'id', :'content_id', :'observed_at'::timestamptz, :'final_url', NULLIF(:'media_type',''),
        :'content_sha256', NULLIF(:'body_ref',''), :'retrieval_method', :'retrieval_version',
        NULLIF(:'parser_method',''), NULLIF(:'parser_version',''), :'rights_status',
        :'retention_class', 'CAPTURED', :'metadata'::jsonb
    )
    ON CONFLICT (content_id, content_sha256) DO NOTHING
    RETURNING id, body_ref, status, archive_status, retention_class, hold_status,
              final_url, retrieval_method, retrieval_version, parser_method, parser_version,
              observed_at, media_type, rights_status, archive_provider, archive_requested_at,
              archive_completed_at, archive_receipt, body_purged_at, purge_reason, purge_receipt, metadata
), current AS (
    SELECT 'INSERTED'::text AS state, * FROM inserted
    UNION ALL
    SELECT 'EXISTING', c.id, c.body_ref, c.status, c.archive_status, c.retention_class,
           c.hold_status, c.final_url, c.retrieval_method, c.retrieval_version,
           c.parser_method, c.parser_version, c.observed_at, c.media_type, c.rights_status,
           c.archive_provider, c.archive_requested_at, c.archive_completed_at, c.archive_receipt,
           c.body_purged_at, c.purge_reason, c.purge_receipt, c.metadata
    FROM content_capture c
    WHERE c.content_id=:'content_id' AND c.content_sha256=:'content_sha256'
      AND NOT EXISTS(SELECT 1 FROM inserted)
)
SELECT json_build_object(
    'state', state, 'id', id, 'body_ref', body_ref, 'status', status,
    'archive_status', archive_status, 'retention_class', retention_class,
    'hold_status', hold_status, 'final_url', final_url,
    'retrieval_method', retrieval_method, 'retrieval_version', retrieval_version,
    'parser_method', parser_method, 'parser_version', parser_version,
    'observed_at', observed_at, 'media_type', media_type, 'rights_status', rights_status,
    'archive_provider', archive_provider, 'archive_requested_at', archive_requested_at,
    'archive_completed_at', archive_completed_at, 'archive_receipt', archive_receipt,
    'body_purged_at', body_purged_at, 'purge_reason', purge_reason,
    'purge_receipt', purge_receipt, 'metadata', metadata
)::text FROM current;
""".strip()


_APPEND_PIPELINE_EVENT_SQL = r"""
WITH inserted AS (
    INSERT INTO capture_lifecycle_event (
        id, capture_id, event_type, event_version, actor_ref,
        previous_state, new_state, receipt
    ) VALUES (
        :'event_id', :'capture_id', :'event_type', 'capture-lifecycle-v1', :'actor_ref',
        :'previous_state'::jsonb, :'new_state'::jsonb, :'receipt'::jsonb
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), existing AS (
    SELECT id FROM capture_lifecycle_event
    WHERE id=:'event_id' AND capture_id=:'capture_id' AND event_type=:'event_type'
      AND actor_ref=:'actor_ref' AND previous_state=:'previous_state'::jsonb
      AND new_state=:'new_state'::jsonb AND receipt=:'receipt'::jsonb
)
SELECT CASE
    WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
    WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING'
    ELSE 'CONFLICT'
END;
""".strip()


_LIST_CAPTURE_PASSAGES_SQL = r"""
SELECT json_build_object(
    'id', id, 'content_id', content_id, 'capture_id', capture_id,
    'selector_type', selector_type, 'start_char', start_char, 'end_char', end_char,
    'text_sha256', text_sha256, 'private_text', private_text,
    'language', language, 'extraction_method', extraction_method,
    'extraction_version', extraction_version, 'metadata', metadata
)::text
FROM passage
WHERE capture_id=:'capture_id'
ORDER BY start_char NULLS LAST, id;
""".strip()


class CapturePipelineStore(PsqlRuntime):
    def read_private_capture_safety_counts(self) -> dict[str, int]:
        """Only a coarse, read-only side-effect guard, not publication authority."""
        raw = self.run(
            """
            SELECT json_build_object(
                'atomic_claim', (SELECT count(*) FROM atomic_claim),
                'publish_finding', (SELECT count(*) FROM finding WHERE publication_status='PUBLISH'),
                'statement_candidate', (SELECT count(*) FROM statement_candidate),
                'claim_candidate', (SELECT count(*) FROM claim_candidate)
            )::text;
            """
        )
        if not raw:
            raise CapturePipelineError("PRIVATE_CAPTURE_SAFETY_COUNTS_MISSING")
        value = json.loads(raw)
        return {key: int(value[key]) for key in (
            "atomic_claim", "publish_finding", "statement_candidate", "claim_candidate"
        )}

    def read_research_capture_context(self, collection_id: str, content_id: str) -> dict[str, Any] | None:
        valid_groups = valid_discovery_hit_groups_sql(
            collection_id_sql="collection.id",
            content_id_sql="content.id",
            canonical_url_sql="content.canonical_url",
        )
        raw = self.run(
            f"""
            SELECT json_build_object(
                'collection_id', collection.id,
                'collection_status', collection.status,
                'membership_status', member.status,
                'capture_authorized', member.metadata->'capture_authorized',
                'content_id', content.id,
                'canonical_url', content.canonical_url,
                'accepted_discovery_hits', provenance.hit_count,
                'accepted_discovery_groups', provenance.family_groups
            )::text
            FROM research_collection collection
            JOIN research_collection_content member ON member.collection_id=collection.id
            JOIN content_item content ON content.id=member.content_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(sum(grouped.hit_count), 0)::integer AS hit_count,
                    COALESCE(json_agg(json_build_object(
                        'source_family', grouped.source_family,
                        'hit_count', grouped.hit_count
                    ) ORDER BY grouped.source_family), '[]'::json) AS family_groups
                FROM ({valid_groups}) grouped
            ) provenance
            WHERE collection.id=:'collection_id' AND content.id=:'content_id';
            """,
            collection_id=collection_id,
            content_id=content_id,
        )
        return json.loads(raw) if raw else None

    def read_operator_capture_content_state(self, content_id: str) -> dict[str, Any] | None:
        """Read-only Content/collection authority snapshot for the operator guard."""
        raw = self.run(
            """
            SELECT json_build_object(
                'id', content.id,
                'canonical_url', content.canonical_url,
                'rights_status', content.rights_status,
                'inactive_collection_count', (
                    SELECT count(*) FROM research_collection_content member
                    JOIN research_collection collection ON collection.id=member.collection_id
                    WHERE member.content_id=content.id
                      AND member.status='INCLUDED'
                      AND collection.status <> 'ACTIVE'
                ),
                'forbidden_membership_count', (
                    SELECT count(*) FROM research_collection_content member
                    WHERE member.content_id=content.id
                      AND member.status='INCLUDED'
                      AND member.metadata->>'capture_authorized' = 'false'
                )
            )::text
            FROM content_item content
            WHERE content.id=:'content_id';
            """,
            content_id=content_id,
        )
        return json.loads(raw) if raw else None

    def find_capture(self, content_id: str, content_sha256: str) -> dict[str, Any] | None:
        raw = self.run(_FIND_CAPTURE_SQL, content_id=content_id, content_sha256=content_sha256)
        return json.loads(raw) if raw else None

    def upsert_capture(self, record: ContentCaptureRecord) -> dict[str, Any]:
        raw = self.run(
            _UPSERT_CAPTURE_SQL,
            id=record.id,
            content_id=record.content_id,
            observed_at=record.observed_at,
            final_url=record.final_url,
            media_type=record.media_type or "",
            content_sha256=record.content_sha256,
            body_ref=record.body_ref or "",
            retrieval_method=record.retrieval_method,
            retrieval_version=record.retrieval_version,
            parser_method=record.parser_method or "",
            parser_version=record.parser_version or "",
            rights_status=record.rights_status,
            retention_class=record.retention_class,
            metadata=_json(record.metadata),
        )
        if not raw:
            raise CapturePipelineError("CAPTURE_UPSERT_EMPTY")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict) or parsed.get("state") not in {"INSERTED", "EXISTING"}:
            raise CapturePipelineError("CAPTURE_UPSERT_CONFLICT")
        return parsed

    def append_event(
        self,
        *,
        capture_id: str,
        event_type: str,
        operation_key: str,
        actor_ref: str,
        previous_state: Mapping[str, Any] | None,
        new_state: Mapping[str, Any] | None,
        receipt: Mapping[str, Any] | None,
    ) -> str:
        event_id = lifecycle_event_id(capture_id, event_type, operation_key)
        state = self.run(
            _APPEND_PIPELINE_EVENT_SQL,
            event_id=event_id,
            capture_id=capture_id,
            event_type=event_type,
            actor_ref=actor_ref,
            previous_state=_json(previous_state),
            new_state=_json(new_state),
            receipt=_json(receipt),
        ).strip()
        if state not in {"INSERTED", "EXISTING"}:
            raise CapturePipelineError("CAPTURE_EVENT_CONFLICT")
        return state

    def insert_passage(self, record: PassageRecord) -> str:
        state = self.run(
            INSERT_PASSAGE_SQL_V1,
            id=record.id,
            content_id=record.content_id,
            capture_id=record.capture_id or "",
            canonical_segment_id=record.canonical_segment_id or "",
            selector_type=record.selector_type,
            start_char="" if record.start_char is None else record.start_char,
            end_char="" if record.end_char is None else record.end_char,
            page_start="" if record.page_start is None else record.page_start,
            page_end="" if record.page_end is None else record.page_end,
            text_sha256=record.text_sha256,
            private_text=record.private_text or "",
            language=record.language or "",
            extraction_method=record.extraction_method,
            extraction_version=record.extraction_version,
            metadata=_json(record.metadata),
        ).strip()
        if state not in {"INSERTED", "EXISTING"}:
            raise CapturePipelineError("PASSAGE_INSERT_CONFLICT")
        return state

    def list_passages(self, capture_id: str) -> list[dict[str, Any]]:
        raw = self.run(_LIST_CAPTURE_PASSAGES_SQL, capture_id=capture_id)
        return [json.loads(line) for line in raw.splitlines() if line.strip()]

    def request_archive(
        self,
        *,
        capture_id: str,
        provider: str,
        actor_ref: str,
        receipt: Mapping[str, Any],
    ) -> str:
        return self.run(
            REQUEST_CAPTURE_ARCHIVE_SQL_V1,
            capture_id=capture_id,
            event_id=lifecycle_event_id(capture_id, "ARCHIVE_REQUESTED", provider),
            actor_ref=actor_ref,
            archive_provider=provider,
            request_receipt=_json(receipt),
        ).strip()

    def mark_archive_pending(
        self,
        *,
        capture_id: str,
        provider: str,
        actor_ref: str,
        receipt: Mapping[str, Any],
    ) -> str:
        return self.run(
            MARK_CAPTURE_ARCHIVE_PENDING_SQL_V1,
            capture_id=capture_id,
            event_id=lifecycle_event_id(capture_id, "ARCHIVE_PENDING", provider),
            actor_ref=actor_ref,
            receipt=_json(receipt),
        ).strip()

    def complete_archive(
        self,
        *,
        capture_id: str,
        provider: str,
        actor_ref: str,
        outcome: str,
        receipt: Mapping[str, Any],
    ) -> str:
        return self.run(
            COMPLETE_CAPTURE_ARCHIVE_SQL_V1,
            capture_id=capture_id,
            event_id=lifecycle_event_id(capture_id, f"ARCHIVE_{outcome}", provider),
            actor_ref=actor_ref,
            outcome=outcome,
            archive_receipt=_json(receipt),
        ).strip()


def _capture_id(content_id: str, content_sha256: str) -> str:
    return deterministic_corpus_id("capture", content_id, content_sha256)


def _passage_records(
    *,
    content_id: str,
    capture_id: str,
    parse: ParseResult,
    language: str | None,
) -> tuple[PassageRecord, ...]:
    records: list[PassageRecord] = []
    for span in parse.spans:
        passage_id = deterministic_corpus_id(
            "passage",
            capture_id,
            parse.parser_version,
            str(span.start_char),
            str(span.end_char),
            span.text_sha256,
        )
        records.append(
            PassageRecord(
                id=passage_id,
                content_id=content_id,
                capture_id=capture_id,
                selector_type="TEXT_POSITION",
                start_char=span.start_char,
                end_char=span.end_char,
                text_sha256=span.text_sha256,
                private_text=span.text,
                language=language,
                extraction_method=parse.parser_method,
                extraction_version=parse.parser_version,
                metadata={"capture_pipeline_version": CAPTURE_PIPELINE_VERSION},
            )
        )
    return tuple(records)


def verify_passage_roundtrip(
    *,
    body: bytes,
    media_type: str,
    charset: str | None,
    passage: PassageRecord,
    parser: ParserAdapter | None = None,
) -> bool:
    parser = parser or StdlibVisibleTextParser()
    fetched = FetchedBytes(
        body=body,
        final_url="https://roundtrip.invalid/",
        status_code=200,
        media_type=media_type,
        charset=charset,
        content_length=len(body),
    )
    parsed = parser.parse(fetched)
    if parsed.status != "SUCCEEDED" or passage.start_char is None or passage.end_char is None:
        return False
    if passage.end_char > len(parsed.canonical_text):
        return False
    text = parsed.canonical_text[passage.start_char:passage.end_char]
    return (
        text == (passage.private_text or "")
        and hashlib.sha256(text.encode("utf-8")).hexdigest() == passage.text_sha256
    )


def _capture_record(
    *,
    content_id: str,
    capture_id: str,
    observed_at: str,
    fetched: FetchedBytes,
    content_sha256: str,
    body_ref: str | None,
    retrieval_method: str,
    retrieval_version: str,
    parse: ParseResult,
    rights_status: str,
    retention_class: str,
    metadata_enabled: bool,
    archive_enabled: bool,
) -> ContentCaptureRecord:
    return ContentCaptureRecord(
        id=capture_id,
        content_id=content_id,
        observed_at=observed_at,
        final_url=fetched.final_url,
        media_type=_normalize_media_type(fetched.media_type),
        content_sha256=content_sha256,
        body_ref=body_ref,
        retrieval_method=retrieval_method,
        retrieval_version=retrieval_version,
        parser_method=parse.parser_method,
        parser_version=parse.parser_version,
        rights_status=rights_status,
        retention_class=retention_class,
        metadata={
            "capture_pipeline_version": CAPTURE_PIPELINE_VERSION,
            "http_status": fetched.status_code,
            "response_bytes": fetched.content_length,
            "etag": fetched.etag,
            "last_modified": fetched.last_modified,
            "parse_status": parse.status,
            "parse_error_category": parse.error_category,
            "source_metadata_policy": "ENABLED" if metadata_enabled else "DISABLED",
            "source_archive_policy": "ENABLED" if archive_enabled else "DISABLED",
            "source_metadata": parse.metadata,
        },
    )


def _archive_capture(
    *,
    store: CapturePipelineStore,
    capture: ContentCaptureRecord,
    body_store: CaptureBodyStore,
    adapter: ArchiveAdapter,
    actor_ref: str,
) -> str:
    provider = str(adapter.provider or "").strip()
    if not provider:
        return "ARCHIVE_PROVIDER_REQUIRED"
    request_state = store.request_archive(
        capture_id=capture.id,
        provider=provider,
        actor_ref=actor_ref,
        receipt={"pipeline": CAPTURE_PIPELINE_VERSION},
    )
    if request_state not in {"ARCHIVE_REQUESTED"}:
        return request_state
    body_path = body_store.path(capture.body_ref) if capture.body_ref else None
    try:
        result = adapter.archive(capture=capture, body_path=body_path)
        receipt = _safe_mapping(result.receipt, "archive_receipt")
        if not receipt:
            receipt = {"code": "ARCHIVE_EMPTY_RECEIPT"}
        status = str(result.status or "").upper()
        if status == "PENDING":
            return store.mark_archive_pending(
                capture_id=capture.id,
                provider=provider,
                actor_ref=actor_ref,
                receipt=receipt,
            )
        if status == "SUCCEEDED":
            archive_url = str(receipt.get("archive_url") or "").strip()
            parsed_archive_url = urlsplit(archive_url)
            try:
                archive_port = parsed_archive_url.port
            except ValueError:
                archive_port = -1
            if (
                parsed_archive_url.scheme.lower() != "https"
                or not parsed_archive_url.hostname
                or parsed_archive_url.username is not None
                or parsed_archive_url.password is not None
                or archive_port not in {None, 443}
            ):
                status = "FAILED"
                receipt = {
                    "error_category": "ARCHIVE_SUCCESS_LOCATOR_INVALID",
                    "pipeline": CAPTURE_PIPELINE_VERSION,
                }
        if status not in {"SUCCEEDED", "FAILED"}:
            status = "FAILED"
            receipt = {**receipt, "error_category": "ARCHIVE_STATUS_INVALID"}
        return store.complete_archive(
            capture_id=capture.id,
            provider=provider,
            actor_ref=actor_ref,
            outcome=status,
            receipt=receipt,
        )
    except Exception:
        return store.complete_archive(
            capture_id=capture.id,
            provider=provider,
            actor_ref=actor_ref,
            outcome="FAILED",
            receipt={"error_category": "ARCHIVE_ADAPTER_FAILURE", "pipeline": CAPTURE_PIPELINE_VERSION},
        )


def _persist_fetched_capture(
    *,
    content_id: str,
    fetched: FetchedBytes,
    observed_at: str,
    retrieval_method: str,
    retrieval_version: str,
    store: CapturePipelineStore,
    body_store: CaptureBodyStore,
    parser: ParserAdapter,
    actor_ref: str,
    rights_status: str,
    retention_class: str,
    language: str | None,
    metadata_enabled: bool,
    archive_enabled: bool,
    permit_id: str,
    permit_canonical_url: str,
    permit_operation_ref: str,
    rights_guard: Callable[[], None] | None = None,
) -> tuple[ContentCaptureRecord, str, ParseResult, tuple[PassageRecord, ...], tuple[str, ...]]:
    _validate_fetched_resource(fetched, max_response_bytes=MAX_DISCOVERY_RESPONSE_BYTES)
    try:
        store.require_ingestion_acquisition_permit(
            permit_id=permit_id,
            content_ref=content_id,
            canonical_url=permit_canonical_url,
            operation_kind="CAPTURE_FETCH",
            operation_ref=permit_operation_ref,
        )
    except RuntimeError as exc:
        raise CapturePipelineError(str(exc)) from exc
    content_sha256 = hashlib.sha256(fetched.body).hexdigest()
    existing = store.find_capture(content_id, content_sha256)
    if rights_guard is not None:
        rights_guard()
    proposed_id = str(existing.get("id")) if existing else _capture_id(content_id, content_sha256)
    body_ref: str | None = None
    if existing:
        body_ref = existing.get("body_ref")
    else:
        body_ref = body_store.write(
            capture_id=proposed_id,
            body=fetched.body,
            content_sha256=content_sha256,
        ).body_ref
    parse = parser.parse(fetched)
    if not metadata_enabled and parse.metadata:
        parse = ParseResult(
            status=parse.status,
            parser_method=parse.parser_method,
            parser_version=parse.parser_version,
            canonical_text=parse.canonical_text,
            spans=parse.spans,
            error_category=parse.error_category,
            metadata={},
        )
    record = _capture_record(
        content_id=content_id,
        capture_id=proposed_id,
        observed_at=observed_at,
        fetched=fetched,
        content_sha256=content_sha256,
        body_ref=body_ref,
        retrieval_method=retrieval_method,
        retrieval_version=retrieval_version,
        parse=parse,
        rights_status=rights_status,
        retention_class=retention_class,
        metadata_enabled=metadata_enabled,
        archive_enabled=archive_enabled,
    )
    if rights_guard is not None:
        rights_guard()
    persisted = store.upsert_capture(record)
    actual_id = str(persisted["id"])
    if actual_id != record.id:
        record = ContentCaptureRecord(
            **{
                **record.to_dict(),
                "id": actual_id,
                "observed_at": str(persisted.get("observed_at") or record.observed_at),
                "final_url": str(persisted.get("final_url") or record.final_url),
                "media_type": persisted.get("media_type") or record.media_type,
                "body_ref": persisted.get("body_ref"),
                "retrieval_method": str(persisted.get("retrieval_method") or record.retrieval_method),
                "retrieval_version": str(persisted.get("retrieval_version") or record.retrieval_version),
                "parser_method": persisted.get("parser_method"),
                "parser_version": persisted.get("parser_version"),
                "rights_status": str(persisted.get("rights_status") or record.rights_status),
                "retention_class": str(persisted.get("retention_class") or record.retention_class),
                "hold_status": str(persisted.get("hold_status") or record.hold_status),
                "archive_status": str(persisted.get("archive_status") or record.archive_status),
                "archive_provider": persisted.get("archive_provider"),
                "archive_requested_at": persisted.get("archive_requested_at"),
                "archive_completed_at": persisted.get("archive_completed_at"),
                "archive_receipt": persisted.get("archive_receipt") or {},
                "body_purged_at": persisted.get("body_purged_at"),
                "purge_reason": persisted.get("purge_reason"),
                "purge_receipt": persisted.get("purge_receipt") or {},
                "status": str(persisted.get("status") or record.status),
                "metadata": persisted.get("metadata") or record.metadata,
            }
        )
    capture_state = str(persisted["state"])
    if capture_state == "EXISTING":
        store.append_event(
            capture_id=actual_id,
            event_type="CAPTURE_REOBSERVED",
            operation_key=observed_at,
            actor_ref=actor_ref,
            previous_state={"content_sha256": content_sha256},
            new_state={"observed_at": observed_at},
            receipt={
                "final_url": fetched.final_url,
                "retrieval_method": retrieval_method,
                "retrieval_version": retrieval_version,
                "response_bytes": fetched.content_length,
            },
        )
    passages: tuple[PassageRecord, ...] = ()
    passage_states: tuple[str, ...] = ()
    if parse.status == "SUCCEEDED":
        if rights_guard is not None:
            rights_guard()
        passages = _passage_records(
            content_id=content_id,
            capture_id=actual_id,
            parse=parse,
            language=language,
        )
        states = [store.insert_passage(passage) for passage in passages]
        passage_states = tuple(states)
        store.append_event(
            capture_id=actual_id,
            event_type="PARSE_SUCCEEDED",
            operation_key=f"{parse.parser_method}:{parse.parser_version}",
            actor_ref=actor_ref,
            previous_state={},
            new_state={"parse_status": "SUCCEEDED", "passage_count": len(passages)},
            receipt={
                "parser_method": parse.parser_method,
                "parser_version": parse.parser_version,
                "canonical_text_sha256": hashlib.sha256(parse.canonical_text.encode("utf-8")).hexdigest(),
                "canonical_text_chars": len(parse.canonical_text),
            },
        )
    else:
        store.append_event(
            capture_id=actual_id,
            event_type="PARSE_FAILED",
            operation_key=f"{parse.parser_method}:{parse.parser_version}:{parse.error_category or 'UNKNOWN'}",
            actor_ref=actor_ref,
            previous_state={},
            new_state={"parse_status": "FAILED"},
            receipt={
                "parser_method": parse.parser_method,
                "parser_version": parse.parser_version,
                "error_category": parse.error_category or "PARSER_FAILURE",
            },
        )
    return record, capture_state, parse, passages, passage_states


def capture_content(
    *,
    content_id: str,
    url: str,
    store: CapturePipelineStore,
    body_store: CaptureBodyStore,
    actor_ref: str = "capture-pipeline",
    observed_at: str | None = None,
    retention_class: str = "EPHEMERAL",
    rights_status: str = "UNKNOWN",
    language: str | None = "it",
    parser: ParserAdapter | None = None,
    fetcher: Callable[..., FetchedBytes] = fetch_bytes,
    browser_renderer: BrowserRenderer | None = None,
    archive_adapter: ArchiveAdapter | None = None,
    enrichment_policy: CaptureEnrichmentPolicy | None = None,
    oembed_fetcher: Callable[..., FetchedBytes] = fetch_oembed_json,
    max_response_bytes: int = MAX_DISCOVERY_RESPONSE_BYTES,
    rights_guard: Callable[[], None] | None = None,
) -> CapturePipelineReceipt:
    if not isinstance(content_id, str) or not content_id.strip():
        raise CapturePipelineError("CONTENT_ID_REQUIRED")
    parsed_url = urlsplit(str(url).strip())
    if parsed_url.scheme.lower() != "https" or not parsed_url.hostname:
        raise CapturePipelineError("CAPTURE_URL_HTTPS_REQUIRED")
    enrichment_policy = enrichment_policy or CaptureEnrichmentPolicy()
    parser = parser or StdlibVisibleTextParser(
        extract_metadata=enrichment_policy.metadata_enabled
    )
    observed_at = observed_at or _now_iso()
    try:
        datetime.fromisoformat(observed_at[:-1] + "+00:00" if observed_at.endswith("Z") else observed_at)
    except ValueError as exc:
        raise CapturePipelineError("OBSERVED_AT_INVALID") from exc

    if rights_guard is not None:
        rights_guard()
    try:
        operation_ref = deterministic_ingestion_operation_ref(
            "CAPTURE_FETCH",
            content_id,
            observed_at,
        )
        permit = store.issue_ingestion_acquisition_permit(
            content_ref=content_id,
            canonical_url=url,
            operation_kind="CAPTURE_FETCH",
            operation_ref=operation_ref,
        )
    except RuntimeError as exc:
        raise CapturePipelineError(str(exc)) from exc

    fetched = fetcher(url, max_response_bytes=max_response_bytes)
    _validate_fetched_resource(fetched, max_response_bytes=max_response_bytes)
    if rights_guard is not None:
        rights_guard()
    primary, state, parse, passages, passage_states = _persist_fetched_capture(
        content_id=content_id,
        fetched=fetched,
        observed_at=observed_at,
        retrieval_method="SAFE_HTTP",
        retrieval_version=SAFE_HTTP_RETRIEVAL_VERSION,
        store=store,
        body_store=body_store,
        parser=parser,
        actor_ref=actor_ref,
        rights_status=rights_status,
        retention_class=retention_class,
        language=language,
        metadata_enabled=enrichment_policy.metadata_enabled,
        archive_enabled=enrichment_policy.archive_enabled,
        permit_id=permit.permit_id,
        permit_canonical_url=url,
        permit_operation_ref=operation_ref,
        rights_guard=rights_guard,
    )
    selected = primary
    selected_parse = parse
    selected_passages = passages
    selected_states = passage_states
    browser_status = "NOT_REQUESTED"

    if parse.status != "SUCCEEDED" and browser_renderer is not None and _normalize_media_type(fetched.media_type) in {"text/html", "application/xhtml+xml"}:
        if rights_guard is not None:
            rights_guard()
        try:
            store.require_ingestion_acquisition_permit(
                permit_id=permit.permit_id,
                content_ref=content_id,
                canonical_url=url,
                operation_kind="CAPTURE_FETCH",
                operation_ref=operation_ref,
            )
        except RuntimeError as exc:
            raise CapturePipelineError(str(exc)) from exc
        try:
            rendered = browser_renderer.render(url, max_response_bytes=max_response_bytes)
            _validate_fetched_resource(rendered, max_response_bytes=max_response_bytes)
            if rights_guard is not None:
                rights_guard()
            selected, _, selected_parse, selected_passages, selected_states = _persist_fetched_capture(
                content_id=content_id,
                fetched=rendered,
                observed_at=observed_at,
                retrieval_method=f"BROWSER_RENDER:{browser_renderer.renderer_id}",
                retrieval_version=str(browser_renderer.renderer_version),
                store=store,
                body_store=body_store,
                parser=parser,
                actor_ref=actor_ref,
                rights_status=rights_status,
                retention_class=retention_class,
                language=language,
                metadata_enabled=enrichment_policy.metadata_enabled,
                archive_enabled=enrichment_policy.archive_enabled,
                permit_id=permit.permit_id,
                permit_canonical_url=url,
                permit_operation_ref=operation_ref,
                rights_guard=rights_guard,
            )
            browser_status = "SUCCEEDED" if selected_parse.status == "SUCCEEDED" else "PARSE_FAILED"
        except PrivateCaptureAuthorizationBlocked:
            # A revoked/paused authority is not an optional browser-render failure.
            raise
        except Exception:
            browser_status = "FAILED"
            store.append_event(
                capture_id=primary.id,
                event_type="BROWSER_FALLBACK_FAILED",
                operation_key=f"{browser_renderer.renderer_id}:{browser_renderer.renderer_version}",
                actor_ref=actor_ref,
                previous_state={"parse_status": parse.status},
                new_state={"browser_status": "FAILED"},
                receipt={
                    "renderer_id": browser_renderer.renderer_id,
                    "renderer_version": browser_renderer.renderer_version,
                    "error_category": "BROWSER_RENDER_FAILURE",
                },
            )

    archive_status = "NOT_REQUESTED"
    if archive_adapter is not None and not enrichment_policy.archive_enabled:
        archive_status = "DISABLED_POLICY"
    elif archive_adapter is not None and state == "INSERTED":
        if rights_guard is not None:
            rights_guard()
        try:
            store.require_ingestion_acquisition_permit(
                permit_id=permit.permit_id,
                content_ref=content_id,
                canonical_url=url,
                operation_kind="CAPTURE_FETCH",
                operation_ref=operation_ref,
            )
        except RuntimeError as exc:
            raise CapturePipelineError(str(exc)) from exc
        archive_status = _archive_capture(
            store=store,
            capture=primary,
            body_store=body_store,
            adapter=archive_adapter,
            actor_ref=actor_ref,
        )

    oembed_status = "NOT_REQUESTED"
    if (
        enrichment_policy.oembed_lookup_enabled
        and enrichment_policy.metadata_enabled
        and state == "INSERTED"
    ):
        if rights_guard is not None:
            rights_guard()
        # This is a separate, explicitly allowed *private* enrichment event,
        # not a mutation of the immutable captured source or a public finding.
        try:
            store.require_ingestion_acquisition_permit(
                permit_id=permit.permit_id,
                content_ref=content_id,
                canonical_url=url,
                operation_kind="CAPTURE_FETCH",
                operation_ref=operation_ref,
            )
        except RuntimeError as exc:
            raise CapturePipelineError(str(exc)) from exc
        result = lookup_vimeo_oembed(selected.final_url, fetcher=oembed_fetcher)
        oembed_status = result.status
        if oembed_status != "NOT_APPLICABLE":
            try:
                event_state = store.append_event(
                    capture_id=selected.id,
                    event_type="PRIVATE_OEMBED_LOOKUP",
                    operation_key=f"{observed_at}:{result.contract_version}",
                    actor_ref=actor_ref,
                    previous_state={},
                    new_state={"oembed_status": oembed_status},
                    receipt=result.to_dict(),
                )
                if event_state not in {"INSERTED", "EXISTING"}:
                    oembed_status = "FAILED_EVENT_PERSISTENCE"
            except Exception:
                oembed_status = "FAILED_EVENT_PERSISTENCE"
    elif enrichment_policy.oembed_lookup_enabled and state == "EXISTING":
        oembed_status = "SKIPPED_REPLAY"

    reason = "CAPTURE_PARSED" if selected_parse.status == "SUCCEEDED" else (
        selected_parse.error_category or "CAPTURE_PARSE_FAILED"
    )
    return CapturePipelineReceipt(
        content_id=content_id,
        primary_capture_id=primary.id,
        selected_capture_id=selected.id,
        capture_state=state,
        content_sha256=primary.content_sha256,
        body_ref=primary.body_ref,
        parse_status=selected_parse.status,
        passage_ids=tuple(p.id for p in selected_passages),
        passage_states=selected_states,
        browser_status=browser_status,
        archive_status=archive_status,
        oembed_status=oembed_status,
        reason_code=reason,
    )


__all__ = [
    "ArchiveAdapter",
    "ArchiveResult",
    "BodyStoreReceipt",
    "CAPTURE_PIPELINE_VERSION",
    "CaptureBodyStore",
    "CaptureEnrichmentPolicy",
    "capture_enrichment_policy_from_source",
    "CapturePipelineError",
    "CapturePipelineReceipt",
    "CapturePipelineStore",
    "MAX_PARSED_TEXT_CHARS",
    "MAX_PASSAGE_CHARS",
    "MAX_PASSAGES",
    "ParseResult",
    "ParsedSpan",
    "extract_source_metadata",
    "ParserAdapter",
    "STDLIB_HTML_PARSER_VERSION",
    "StdlibVisibleTextParser",
    "capture_content",
    "verify_passage_roundtrip",
]
