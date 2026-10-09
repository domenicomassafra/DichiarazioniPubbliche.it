"""DP-211/214: provenance- and rights-gated operator Passage -> private Candidates.

This is a bounded operator execution seam, not a grant of source rights, an
attribution review, a model approval, or any publication authority.
"""

from __future__ import annotations

import codecs
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from dichiarazioni_pubbliche.capture_pipeline import (
    CaptureBodyStore,
    CapturePipelineError,
    STDLIB_HTML_PARSER_VERSION,
    StdlibVisibleTextParser,
    verify_passage_roundtrip,
)
from dichiarazioni_pubbliche.capture_authorization import (
    PrivateCaptureAuthorizationBlocked,
    private_capture_rights_guard,
    require_private_capture_rights,
)
from dichiarazioni_pubbliche.ingestion_relevance import canonical_content_url
from dichiarazioni_pubbliche.private_capture_batch import require_persisted_discovery, CaptureBatchItem
from dichiarazioni_pubbliche.rights_registry import RightsSubject
from dichiarazioni_pubbliche.corpus_repository import PassageRecord
from dichiarazioni_pubbliche.source_watcher import MAX_DISCOVERY_RESPONSE_BYTES

VERSION = "private-research-candidate-batch-v1"
MAX_ITEMS = 16
MAX_MANIFEST_BYTES = 1_048_576
MODEL_USE = "OMNIROUTE_MODEL_EXTRACTION_PRIVATE"
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class CandidateBatchItem:
    passage_id: str
    content_id: str
    capture_id: str
    passage_sha256: str
    canonical_url: str
    source_family: str
    rights_record_id: str


@dataclass(frozen=True)
class CandidateBatch:
    collection_id: str
    items: tuple[CandidateBatchItem, ...]
    sha256: str


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("CANDIDATE_BATCH_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _batch_digest(batch: CandidateBatch) -> str:
    payload = {
        "version": VERSION,
        "collection_id": batch.collection_id,
        "items": [vars(item) for item in batch.items],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _validate_batch(batch: CandidateBatch) -> None:
    """The file loader and direct preflight enforce the same bounded identities."""
    if not isinstance(batch, CandidateBatch):
        raise ValueError("CANDIDATE_BATCH_SCHEMA_INVALID")
    if not isinstance(batch.collection_id, str) or not _REF.fullmatch(batch.collection_id):
        raise ValueError("CANDIDATE_BATCH_COLLECTION_INVALID")
    if not isinstance(batch.items, tuple) or not 1 <= len(batch.items) <= MAX_ITEMS:
        raise ValueError("CANDIDATE_BATCH_SIZE_INVALID")
    passages: set[str] = set()
    urls_by_content: dict[str, str] = {}
    contents_by_url: dict[str, str] = {}
    for item in batch.items:
        if not isinstance(item, CandidateBatchItem):
            raise ValueError("CANDIDATE_BATCH_ITEM_SCHEMA_INVALID")
        for key, value in vars(item).items():
            if not isinstance(value, str) or not value or len(value) > 2048:
                raise ValueError("CANDIDATE_BATCH_ITEM_VALUE_INVALID")
            if key.endswith("_id") and not _REF.fullmatch(value):
                raise ValueError("CANDIDATE_BATCH_ITEM_REF_INVALID")
        if not _SHA.fullmatch(item.passage_sha256):
            raise ValueError("CANDIDATE_BATCH_PASSAGE_HASH_INVALID")
        try:
            canonical = canonical_content_url(item.canonical_url)
        except ValueError as exc:
            raise ValueError("CANDIDATE_BATCH_URL_INVALID") from exc
        if canonical != item.canonical_url:
            raise ValueError("CANDIDATE_BATCH_URL_NONCANONICAL")
        if item.passage_id in passages:
            raise ValueError("CANDIDATE_BATCH_PASSAGE_DUPLICATE")
        if (item.content_id in urls_by_content
                and urls_by_content[item.content_id] != canonical):
            raise ValueError("CANDIDATE_BATCH_CONTENT_URL_COLLISION")
        if canonical in contents_by_url and contents_by_url[canonical] != item.content_id:
            raise ValueError("CANDIDATE_BATCH_URL_CONTENT_COLLISION")
        passages.add(item.passage_id)
        urls_by_content[item.content_id] = canonical
        contents_by_url[canonical] = item.content_id
    if not isinstance(batch.sha256, str) or batch.sha256 != _batch_digest(batch):
        raise ValueError("CANDIDATE_BATCH_MANIFEST_HASH_MISMATCH")


def load_candidate_batch(path: Path) -> CandidateBatch:
    with path.open("rb") as manifest_file:
        encoded = manifest_file.read(MAX_MANIFEST_BYTES + 1)
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ValueError("CANDIDATE_BATCH_FILE_TOO_LARGE")
    payload = json.loads(encoded.decode("utf-8"), object_pairs_hook=_unique_json_object)
    if not isinstance(payload, dict) or set(payload) != {"version", "collection_id", "items"}:
        raise ValueError("CANDIDATE_BATCH_SCHEMA_INVALID")
    if payload["version"] != VERSION:
        raise ValueError("CANDIDATE_BATCH_VERSION_INVALID")
    raw_items = payload["items"]
    if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= MAX_ITEMS:
        raise ValueError("CANDIDATE_BATCH_SIZE_INVALID")
    required = set(CandidateBatchItem.__dataclass_fields__)
    for raw in raw_items:
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError("CANDIDATE_BATCH_ITEM_SCHEMA_INVALID")
    batch = CandidateBatch(payload["collection_id"], tuple(CandidateBatchItem(**raw) for raw in raw_items), "")
    batch = CandidateBatch(batch.collection_id, batch.items, _batch_digest(batch))
    _validate_batch(batch)
    return batch


def require_private_passage_state(row: Mapping[str, Any] | None, item: CandidateBatchItem) -> None:
    if not row or row.get("passage_id") != item.passage_id or row.get("content_id") != item.content_id:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_PASSAGE_MISSING")
    if row.get("capture_id") != item.capture_id:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_CAPTURE_BINDING_MISMATCH")
    if row.get("passage_sha256") != item.passage_sha256:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_PASSAGE_HASH_STALE")
    if row.get("capture_status") != "CAPTURED" or row.get("capture_hold_status") != "NONE":
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_CAPTURE_HELD")
    if row.get("capture_rights_status") != "CLEARED":
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_CAPTURE_RIGHTS_NOT_CLEARED")
    if row.get("capture_retention_class") not in {"EPHEMERAL", "DURABLE_PRIVATE", "DURABLE_PROVENANCE"}:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_RETENTION_POLICY_PENDING")
    # The PostgreSQL expression returns a boolean. An arbitrary truthy
    # string/number must not be promoted to proof of an available body.
    if row.get("body_ref") is not True:
        raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_CAPTURE_BODY_UNAVAILABLE")


def require_immutable_capture_passage_binding(
    row: Mapping[str, Any] | None,
    item: CandidateBatchItem,
    *,
    storage_root: Path,
) -> None:
    """Prove a persisted selector against private Capture bytes, not against its own hash.

    The joined source row must come from the current persisted Capture and
    Passage, never an operator assertion. No result/body text is logged or
    returned. Missing legacy charset/parser evidence cannot be guessed.
    """
    blocked = PrivateCaptureAuthorizationBlocked
    if not isinstance(row, Mapping):
        raise blocked("PRIVATE_ANALYSIS_SOURCE_BINDING_MISSING")
    for key, expected in (
        ("passage_id", item.passage_id),
        ("content_id", item.content_id),
        ("capture_id", item.capture_id),
        ("passage_sha256", item.passage_sha256),
        ("selector_type", "TEXT_POSITION"),
    ):
        if row.get(key) != expected:
            raise blocked("PRIVATE_ANALYSIS_SOURCE_BINDING_MISMATCH")

    start, end = row.get("start_char"), row.get("end_char")
    private_text = row.get("passage_text")
    if (
        type(start) is not int or type(end) is not int
        or not isinstance(private_text, str) or not private_text.strip()
        or start < 0 or end <= start or end - start != len(private_text)
        or hashlib.sha256(private_text.encode("utf-8")).hexdigest() != item.passage_sha256
    ):
        raise blocked("PRIVATE_ANALYSIS_SOURCE_SELECTOR_INVALID")

    parser = StdlibVisibleTextParser(extract_metadata=False)
    if (
        row.get("capture_parser_method") != parser.parser_method
        or row.get("capture_parser_version") != STDLIB_HTML_PARSER_VERSION
        or row.get("extraction_method") != parser.parser_method
        or row.get("extraction_version") != STDLIB_HTML_PARSER_VERSION
        or row.get("capture_media_type") not in {"text/plain", "text/html", "application/xhtml+xml"}
    ):
        raise blocked("PRIVATE_ANALYSIS_SOURCE_PARSER_UNSUPPORTED")
    charset = row.get("capture_charset")
    if not isinstance(charset, str) or not charset or charset.strip() != charset:
        raise blocked("PRIVATE_ANALYSIS_SOURCE_CHARSET_MISSING")
    try:
        codecs.lookup(charset)
    except LookupError as exc:
        raise blocked("PRIVATE_ANALYSIS_SOURCE_CHARSET_UNSUPPORTED") from exc
    source_sha = row.get("capture_content_sha256")
    body_ref = row.get("capture_body_ref")
    if not isinstance(source_sha, str) or not _SHA.fullmatch(source_sha):
        raise blocked("PRIVATE_ANALYSIS_SOURCE_HASH_INVALID")
    if body_ref != CaptureBodyStore._relative_ref(item.capture_id):
        raise blocked("PRIVATE_ANALYSIS_SOURCE_BODY_REFERENCE_MISMATCH")

    root = Path(storage_root)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise blocked("PRIVATE_ANALYSIS_STORAGE_ROOT_UNAVAILABLE")
    try:
        body_store = CaptureBodyStore.open_existing_readonly(root)
        body_path = body_store.path(body_ref)
        if not body_path.is_file() or body_path.stat().st_size > MAX_DISCOVERY_RESPONSE_BYTES:
            raise blocked("PRIVATE_ANALYSIS_SOURCE_BODY_UNAVAILABLE")
        raw_body = body_store.read(
            body_ref, expected_sha256=source_sha,
            max_bytes=MAX_DISCOVERY_RESPONSE_BYTES,
        )
        # The source parser tolerates encoding fallbacks when capturing; a
        # verifier must never silently reinterpret unknown/mislabelled bytes.
        raw_body.decode(charset, errors="strict")
        source_passage = PassageRecord(
            id=item.passage_id,
            content_id=item.content_id,
            capture_id=item.capture_id,
            selector_type="TEXT_POSITION",
            start_char=start,
            end_char=end,
            private_text=private_text,
            text_sha256=item.passage_sha256,
            extraction_method=parser.parser_method,
            extraction_version=parser.parser_version,
        )
        valid = verify_passage_roundtrip(
            body=raw_body,
            media_type=row["capture_media_type"],
            charset=charset,
            passage=source_passage,
            parser=parser,
        )
    except (OSError, ValueError, TypeError, UnicodeError, CapturePipelineError) as exc:
        raise blocked("PRIVATE_ANALYSIS_SOURCE_ROUNDTRIP_UNAVAILABLE") from exc
    if not valid:
        raise blocked("PRIVATE_ANALYSIS_SOURCE_SELECTOR_MISMATCH")


def preflight_candidate_batch(
    batch: CandidateBatch,
    *,
    capture_store: Any,
    candidate_store: Any,
    rights_store: Any,
    storage_root: Path | None = None,
) -> tuple[Callable[[], None], ...]:
    """No provider I/O or database mutation.

    A storage-root-free call is a non-authoritative legacy unit-fixture seam.
    The operator entrypoint MUST configure a real private storage root and
    reuse the returned guards before provider/replay and commit.
    """
    try:
        _validate_batch(batch)
    except ValueError as exc:
        raise PrivateCaptureAuthorizationBlocked(str(exc)) from exc
    guards = []
    for item in batch.items:
        source_item = CaptureBatchItem(item.content_id, item.canonical_url, item.source_family, item.rights_record_id)

        def read_exact_content_state(content_id=item.content_id, *, expected_url=item.canonical_url):
            state = capture_store.read_operator_capture_content_state(content_id)
            # SQL candidate persistence binds the raw canonical URL exactly.
            # Reject a differently spelled database locator before model I/O,
            # even if the capture authorization helper can normalize it.
            if state and state.get("canonical_url") != expected_url:
                raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_CONTENT_URL_NONCANONICAL")
            return state

        rights_guard = private_capture_rights_guard(
            read_current=rights_store.read_current,
            read_content_state=read_exact_content_state,
            rights_record_id=item.rights_record_id,
            content_id=item.content_id,
            canonical_url=item.canonical_url,
            source_family=item.source_family,
        )
        subject = RightsSubject(source_family=item.source_family, locator_kind="URL", locator_value=item.canonical_url, content_id=item.content_id)

        def check(item=item, source_item=source_item, rights_guard=rights_guard, subject=subject):
            require_persisted_discovery(
                capture_store.read_research_capture_context(batch.collection_id, item.content_id),
                collection_id=batch.collection_id,
                item=source_item,
            )
            # A capture's historical ingestion permit does not grant perpetual
            # privacy relevance for downstream model processing.
            try:
                capture_store.require_current_ingestion_relevance(
                    content_ref=item.content_id,
                    canonical_url=item.canonical_url,
                )
            except RuntimeError as exc:
                raise PrivateCaptureAuthorizationBlocked(
                    "PRIVATE_ANALYSIS_RELEVANCE_MISSING_OR_STALE"
                ) from exc
            rights_guard()
            rights = rights_store.read_current(subject)
            require_private_capture_rights(
                rights,
                rights_record_id=item.rights_record_id,
                content_id=item.content_id,
                canonical_url=item.canonical_url,
                source_family=item.source_family,
            )
            if rights.locator_value != item.canonical_url:
                raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_RIGHTS_URL_NONCANONICAL")
            if MODEL_USE not in rights.permitted_uses:
                raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_MODEL_USE_NOT_AUTHORIZED")
            require_private_passage_state(candidate_store.read_operator_passage_state(item.passage_id), item)
            if storage_root is not None:
                read_binding = getattr(candidate_store, "read_private_passage_source_binding", None)
                if not callable(read_binding):
                    raise PrivateCaptureAuthorizationBlocked("PRIVATE_ANALYSIS_SOURCE_BINDING_UNAVAILABLE")
                require_immutable_capture_passage_binding(
                    read_binding(item.passage_id), item, storage_root=storage_root,
                )

        check()
        guards.append(check)
    return tuple(guards)
