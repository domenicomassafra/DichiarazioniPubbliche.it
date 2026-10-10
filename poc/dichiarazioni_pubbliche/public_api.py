"""Static-first, read-only HTTP surface over the fail-closed public projection.

This module is a pure reader. It never opens a database connection, never calls a
provider or an LLM, and never re-implements the publication gate. Its only input is
a public projection bundle that was already produced and validated by
``dichiarazioni_pubbliche.public_projection`` / ``dichiarazioni_pubbliche.public_schema``.

Everything that decides a response body is expressed as a pure function over the
loaded bundle, so the HTTP layer stays a thin adapter and the contract is testable
without binding a socket.

Contract decisions (DP-402 gate 1 and 2)
----------------------------------------

* The stable public HTTP contract is ``/api/v1`` and it reads the
  ``dichiarazioni-pubbliche-public-v2`` projection bundle. Per the DP-105 "Resolved Discrepancy"
  note, ``dichiarazioni-pubbliche-public-v2`` is the authoritative public projection contract;
  the URL major version and the projection schema version are independent axes and
  this API pins ``(api=v1, schema=dichiarazioni-pubbliche-public-v2)``. A future
  ``dichiarazioni-pubbliche-public-v3`` is a new schema version under ``/api/v1`` only if it is
  backward compatible, otherwise under ``/v2``.
* The bundle path comes from ``DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH``, the same
  environment variable the web build already consumes.
* Stable public identifiers are the opaque strings already in the projection
  (``finding_id``, ``claim_id``, ``speaker.id``, ``source.content_id``). Nothing
  resolves a resource by a display name.
* DP-430 first-class subject Topics come only from the optional, reviewed
  ``topics`` collection in the projection. ``topic=`` on ``/findings`` is kept
  temporarily as the draft-contract compatibility alias for ``claim_type=``;
  the ``/topics`` resource never derives subject identity from claim type.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import formatdate, parsedate_to_datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, unquote, urlsplit
from urllib.parse import parse_qs

from dichiarazioni_pubbliche.public_account import (
    AccountService, AccountStore, GoogleOidcProvider,
    FLOW_COOKIE, SESSION_COOKIE, VISITOR_COOKIE, read_secret_file,
)

from dichiarazioni_pubbliche.domain_vocabulary import (
    ClaimType,
    DOMAIN_VOCABULARY_VERSION,
    RELATION_VERSION,
    VOCABULARIES,
    VERIFICATION_ASSESSMENT_VERSION,
)
from dichiarazioni_pubbliche.linked_data import (
    LINKED_DATA_VERSION,
    projection_linked_data_receipt,
)
from dichiarazioni_pubbliche.public_schema import (
    DOSSIER_ALLOWED_KEYS,
    DOSSIER_REQUIRED_KEYS,
    PROJECTION_BUNDLE_ALLOWED_KEYS,
    PUBLIC_FINDING_STATUSES,
    PUBLIC_SCHEMA_VERSION,
    PUBLISHABLE_ASSESSMENTS,
    PublicSchemaValidationError,
    validate_public_bundle,
)

API_CONTRACT_VERSION = "v1"
API_BASE_PATH = "/api/v1"
API_MAJOR_VERSION = 1
API_VERSION_HEADER = "X-Dichiarazioni-Pubbliche-Api-Version"
LLMS_PATH = "/llms.txt"
LINKED_DATA_PATH = "/index.nt"

DEFAULT_LIMIT = 25
MAX_LIMIT = 100
CURSOR_VERSION = 1

PROJECTION_PATH_ENV = "DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH"

# Cache policy. Collection/detail responses revalidate quickly because a
# correction or a right of reply can change a served finding; contract documents
# change only with a release.
DATA_MAX_AGE = 300
DOCUMENT_MAX_AGE = 3600
STALE_WHILE_REVALIDATE = 86400

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_ID_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_LIST_TOKEN_RE = re.compile(r"^[A-Za-z0-9 ._:'\"/-]{1,200}$")

# Filter name -> the kind of validation the value must pass. Anything not in this
# map is an unknown parameter and therefore a typed 400, never a silent no-op.
FILTER_ENUM_SOURCES: dict[str, frozenset[str]] = {
    "claim_type": frozenset(item.value for item in ClaimType),
    # Compatibility alias retained while the draft v1 API migrates away from
    # using the word "topic" for the claim-type taxonomy. First-class subject
    # Topics are served by /topics and are never inferred from claim_type.
    "topic": frozenset(item.value for item in ClaimType),
    "assessment": frozenset(PUBLISHABLE_ASSESSMENTS),
    "status": frozenset(PUBLIC_FINDING_STATUSES),
    "person": None,  # type: ignore[dict-item]
    "content": None,  # type: ignore[dict-item]
}
ID_FILTERS = frozenset({"person", "content"})
LIST_FILTERS = tuple(sorted(ID_FILTERS))
STRING_FILTERS = tuple(sorted(name for name in FILTER_ENUM_SOURCES if name not in ID_FILTERS))
DATE_FILTERS = ("published_from", "published_to")

# Public query name -> FindingEntry field. `status` is the public vocabulary
# term; the entry keeps the fully qualified `publication_status`.
STRING_FILTER_FIELDS = {
    "claim_type": "claim_type",
    "topic": "claim_type",
    "status": "publication_status",
}

ALLOWED_QUERY_PARAMS = frozenset({"limit", "cursor"}) | frozenset(STRING_FILTERS) | frozenset(
    LIST_FILTERS
) | frozenset(DATE_FILTERS)


class PublicApiError(Exception):
    """A transport-only failure with a stable, public, bounded representation."""

    def __init__(self, status: int, code: str, message: str, *, headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers or {}

    def payload(self, request_id: str) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": request_id,
            }
        }


def _bad_request(message: str, code: str = "INVALID_QUERY") -> PublicApiError:
    return PublicApiError(400, code, message)


def _not_found() -> PublicApiError:
    # Deliberately identical for unknown, private, unsafe, and non-projectable
    # resources: operational existence is never disclosed.
    return PublicApiError(404, "RESOURCE_NOT_FOUND", "Resource is not available in the public record.")


def _unavailable() -> PublicApiError:
    return PublicApiError(
        503,
        "PUBLIC_PROJECTION_UNAVAILABLE",
        "The public projection is missing, invalid, stale, or contract-incompatible.",
    )


# --------------------------------------------------------------------------- #
# Deterministic serialization
# --------------------------------------------------------------------------- #


def canonical_json_bytes(value: Any) -> bytes:
    """Sorted-key, tight-separator UTF-8 JSON. No float formatting drift."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


# --------------------------------------------------------------------------- #
# Bundle loading (fail-closed, cached on the file fingerprint)
# --------------------------------------------------------------------------- #

_LOCK = threading.Lock()
_CACHE: dict[str, tuple[tuple[int, int], "PublicIndex"]] = {}


def slugify(value: str) -> str:
    return _SLUG_RE.sub("-", str(value).strip().lower()).strip("-")


@dataclass(frozen=True)
class FindingEntry:
    finding_id: str
    claim_id: str
    claim_type: str
    assessment: str
    publication_status: str
    person_id: str
    person_name: str | None
    content_id: str
    published_at: str | None
    published_epoch: int
    dossier: dict[str, Any]

    @property
    def summary(self) -> dict[str, Any]:
        """Bounded public summary. Never a person score, rank, or transcript body."""
        source = self.dossier["source"]
        return {
            "finding_id": self.finding_id,
            "claim_id": self.claim_id,
            "claim": self.dossier.get("claim"),
            "claim_type": self.claim_type,
            "assessment": self.assessment,
            "publication_status": self.publication_status,
            "published_at": self.published_at,
            "person_id": self.person_id,
            "person_name": self.person_name,
            "content_id": self.content_id,
            "content_url": source.get("url"),
            "correction_count": len(self.dossier.get("corrections") or []),
            "published_right_of_reply_count": len(self.dossier.get("rights_of_reply") or []),
            "link": f"{API_BASE_PATH}/findings/{self.finding_id}",
        }


@dataclass(frozen=True)
class PublicIndex:
    """An immutable, in-memory read model derived from one projection bundle."""

    schema_version: str
    generated_at: str
    dataset_sha256: str
    methodology: dict[str, Any]
    dossier_count: int
    omitted_count: int
    entries: tuple[FindingEntry, ...]
    findings_by_id: dict[str, FindingEntry]
    records: dict[str, dict[str, Any]]
    people: dict[str, dict[str, Any]]
    topics: dict[str, dict[str, Any]]
    topics_present: bool
    contents_present: bool
    source_path: str
    mtime: float

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(
            canonical_json_bytes(
                {
                    "schema_version": self.schema_version,
                    "generated_at": self.generated_at,
                    "dataset_sha256": self.dataset_sha256,
                    "dossier_count": self.dossier_count,
                }
            )
        ).hexdigest()


def build_index(bundle: dict[str, Any], *, source_path: str = "", mtime: float = 0.0) -> PublicIndex:
    """Derive the public read model from an already-validated bundle.

    This never re-checks the publication gate: ``validate_public_bundle`` has
    already rejected every non-public dossier, and a bundle that fails it is not
    loaded at all.
    """
    entries: list[FindingEntry] = []
    for dossier in bundle["dossiers"]:
        finding = dossier["finding"]
        speaker = dossier["speaker"]
        source = dossier["source"]
        published_at = finding.get("published_at")
        entries.append(
            FindingEntry(
                finding_id=str(dossier["finding_id"]),
                claim_id=str(dossier["claim_id"]),
                claim_type=str(dossier["claim_type"]),
                assessment=str(finding["assessment"]),
                publication_status=str(finding["publication_status"]),
                person_id=str(speaker["id"]),
                person_name=speaker.get("name"),
                content_id=str(source["content_id"]),
                published_at=published_at,
                published_epoch=parse_instant(published_at) or 0,
                dossier=dossier,
            )
        )
    # Newest publication first, stable finding id as the tie-breaker (DP-402).
    entries.sort(key=lambda item: (-item.published_epoch, item.finding_id))

    findings_by_id: dict[str, FindingEntry] = {}
    records: dict[str, dict[str, Any]] = {}
    people: dict[str, dict[str, Any]] = {}
    topics: dict[str, dict[str, Any]] = {}
    slug_owner: dict[str, str] = {}
    raw_contents = bundle.get("contents")

    for entry in entries:
        findings_by_id.setdefault(entry.finding_id, entry)

        if raw_contents is None:
            slug = slugify(entry.content_id)
            if not slug:
                raise PublicApiError(
                    503,
                    "PUBLIC_PROJECTION_UNAVAILABLE",
                    "The public projection contains a content identifier with no stable public slug.",
                )
            owner = slug_owner.get(slug)
            if owner is not None and owner != entry.content_id:
                # Legacy public-v2 has no reviewed Content slug. Ambiguous
                # derived slugs therefore fail closed.
                raise PublicApiError(
                    503,
                    "PUBLIC_PROJECTION_UNAVAILABLE",
                    "The public projection contains colliding public record slugs.",
                )
            slug_owner[slug] = entry.content_id
        person = people.setdefault(
            entry.person_id,
            {
                "person_id": entry.person_id,
                "name": entry.person_name,
                "finding_count": 0,
                "claim_types": set(),
                "topic_ids": set(),
            },
        )
        person["finding_count"] += 1
        person["claim_types"].add(entry.claim_type)

    for person in people.values():
        person["claim_types"] = sorted(person["claim_types"])

    if raw_contents is not None:
        for raw_content in raw_contents:
            slug = str(raw_content["slug"])
            content_id = str(raw_content["content_id"])
            owner = slug_owner.get(slug)
            if owner is not None and owner != content_id:
                raise PublicApiError(
                    503,
                    "PUBLIC_PROJECTION_UNAVAILABLE",
                    "The public projection contains colliding public record slugs.",
                )
            slug_owner[slug] = content_id
            findings = [
                findings_by_id[finding_id].summary
                for finding_id in raw_content.get("finding_ids") or []
                if finding_id in findings_by_id
            ]
            records[slug] = {
                "record_id": content_id,
                "content_id": content_id,
                "slug": slug,
                "url": raw_content.get("url"),
                "title": raw_content.get("title"),
                "published_at": raw_content.get("published_at"),
                "content_kind": raw_content.get("content_kind"),
                "duration_ms": raw_content.get("duration_ms"),
                "public_media_url": raw_content.get("public_media_url"),
                "media_policy_version": raw_content.get("media_policy_version"),
                "publication_version": raw_content.get("publication_version"),
                "review_event_ids": list(raw_content.get("review_event_ids") or []),
                "finding_count": len(findings),
                "findings": findings,
            }
    else:
        # Compatibility path for pre-DP-434 public-v2 bundles. Records remain
        # derivable from public findings until the first-class Content collection
        # is present in the bundle.
        for entry in entries:
            slug = slugify(entry.content_id)
            if not slug:
                continue
            if slug in records:
                continue
            dossier = entry.dossier
            same_content = [item for item in entries if item.content_id == entry.content_id]
            records[slug] = {
                "record_id": entry.content_id,
                "content_id": entry.content_id,
                "slug": slug,
                "url": dossier["source"].get("url"),
                "title": dossier["source"].get("title"),
                "published_at": dossier["source"].get("published_at"),
                "content_kind": None,
                "duration_ms": None,
                "public_media_url": None,
                "media_policy_version": None,
                "publication_version": None,
                "review_event_ids": [],
                "finding_count": len(same_content),
                "findings": [item.summary for item in same_content],
            }

    # DP-430: first-class public subject Topics. Older public-v2 bundles do not
    # carry the optional collection and therefore expose zero subject Topics;
    # there is deliberately no fallback to claim_type.
    for raw_topic in bundle.get("topics") or []:
        topic_id = str(raw_topic["topic_id"])
        memberships: list[dict[str, Any]] = []
        finding_ids: set[str] = set()
        people_ids: set[str] = set()
        for membership in raw_topic.get("memberships") or []:
            public_finding_ids = []
            for finding_id in membership.get("finding_ids") or []:
                entry = findings_by_id.get(str(finding_id))
                if entry is None:
                    continue
                public_finding_ids.append(entry.finding_id)
                finding_ids.add(entry.finding_id)
                people_ids.add(entry.person_id)
                if entry.person_id in people:
                    people[entry.person_id]["topic_ids"].add(topic_id)
            if public_finding_ids:
                memberships.append(
                    {
                        "membership_id": str(membership["membership_id"]),
                        "claim_id": str(membership["claim_id"]),
                        "finding_ids": sorted(public_finding_ids),
                        "review_event_ids": list(membership["review_event_ids"]),
                        "source_resolution_candidate_id": membership.get(
                            "source_resolution_candidate_id"
                        ),
                    }
                )
        topics[topic_id] = {
            "topic_id": topic_id,
            "slug": str(raw_topic["slug"]),
            "canonical_name": str(raw_topic["canonical_name"]),
            "scope_text": raw_topic.get("scope_text"),
            "entity_version": str(raw_topic["entity_version"]),
            "review_event_ids": list(raw_topic["review_event_ids"]),
            "memberships": memberships,
            "finding_ids": sorted(finding_ids),
            "people": sorted(people_ids),
        }

    for person in people.values():
        person["topic_ids"] = sorted(person["topic_ids"])

    return PublicIndex(
        schema_version=str(bundle["schema_version"]),
        generated_at=str(bundle["generated_at"]),
        dataset_sha256=str(bundle["dataset_sha256"]),
        methodology=dict(bundle["methodology"]),
        dossier_count=int(bundle["dossier_count"]),
        omitted_count=int(bundle["omitted_count"]),
        entries=tuple(entries),
        findings_by_id=findings_by_id,
        records=records,
        people=people,
        topics=topics,
        topics_present="topics" in bundle,
        contents_present="contents" in bundle,
        source_path=source_path,
        mtime=mtime,
    )


def load_index(path: str | os.PathLike[str] | None, *, use_cache: bool = True) -> PublicIndex:
    """Load and validate a projection bundle. Any failure is a 503, never a 200."""
    if path is None:
        configured = os.environ.get(PROJECTION_PATH_ENV)
        if not configured:
            raise _unavailable()
        path = configured
    resolved = Path(path)
    try:
        stat = resolved.stat()
    except OSError as exc:
        raise _unavailable() from exc
    key = str(resolved)
    stamp = (stat.st_mtime_ns, stat.st_size)
    if use_cache:
        with _LOCK:
            cached = _CACHE.get(key)
        if cached is not None and cached[0] == stamp:
            return cached[1]
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise _unavailable() from exc
    try:
        bundle = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _unavailable() from exc
    try:
        validate_public_bundle(bundle)
    except PublicSchemaValidationError as exc:
        # Fail closed: a bundle carrying a non-public, tampered, or incompatible
        # dossier is never partially served.
        raise _unavailable() from exc
    index = build_index(bundle, source_path=key, mtime=stat.st_mtime)
    if use_cache:
        with _LOCK:
            _CACHE[key] = (stamp, index)
    return index


def projection_path_from_env() -> str | None:
    return os.environ.get(PROJECTION_PATH_ENV)


# --------------------------------------------------------------------------- #
# Pure value parsing
# --------------------------------------------------------------------------- #


def parse_instant(value: object) -> int | None:
    """Parse an ISO 8601 date or timestamp into a UTC epoch second, or None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(text), datetime.min.time())
        except ValueError:
            raise _bad_request(
                "Date parameters must be ISO 8601 dates or timestamps with an explicit timezone.",
                code="INVALID_PARAMETER_VALUE",
            ) from None
    if parsed.tzinfo is None:
        raise _bad_request(
            "Date parameters must carry an explicit timezone.",
            code="INVALID_PARAMETER_VALUE",
        )
    return int(parsed.astimezone(timezone.utc).timestamp())


def parse_query(query: str) -> dict[str, str]:
    """Parse a query string, rejecting anything ambiguous rather than guessing."""
    if not query:
        return {}
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise _bad_request("Malformed query string.") from exc
    parsed: dict[str, str] = {}
    for key, value in pairs:
        if key in parsed:
            raise _bad_request(f"Query parameter '{key}' is repeated.", code="INVALID_PARAMETER")
        parsed[key] = value
    return parsed


def validate_params(params: dict[str, str]) -> dict[str, Any]:
    """Validate the whole query shape. An unknown or malformed parameter is a 400."""
    unknown = sorted(set(params) - ALLOWED_QUERY_PARAMS)
    if unknown:
        raise _bad_request(
            "Unsupported query parameter(s): " + ", ".join(unknown),
            code="UNSUPPORTED_PARAMETER",
        )
    cleaned: dict[str, Any] = {"limit": DEFAULT_LIMIT, "filters": {}}
    if "limit" in params:
        raw = params["limit"].strip()
        if not raw.isdigit():
            raise _bad_request("'limit' must be a positive integer.", code="INVALID_PARAMETER_VALUE")
        limit = int(raw)
        if limit < 1 or limit > MAX_LIMIT:
            raise _bad_request(
                f"'limit' must be between 1 and {MAX_LIMIT}.", code="INVALID_PARAMETER_VALUE"
            )
        cleaned["limit"] = limit
    for name in STRING_FILTERS:
        if name not in params:
            continue
        allowed = FILTER_ENUM_SOURCES[name] or frozenset()
        values = []
        for token in params[name].split(","):
            token = token.strip()
            if not token or not _LIST_TOKEN_RE.match(token) or token not in allowed:
                raise _bad_request(
                    f"Unsupported value for '{name}'.", code="INVALID_PARAMETER_VALUE"
                )
            values.append(token)
        cleaned["filters"][name] = tuple(sorted(set(values)))
    for name in LIST_FILTERS:
        if name not in params:
            continue
        values = []
        for token in params[name].split(","):
            token = token.strip()
            if not _ID_TOKEN_RE.match(token):
                raise _bad_request(
                    f"Unsupported value for '{name}'.", code="INVALID_PARAMETER_VALUE"
                )
            values.append(token)
        cleaned["filters"][name] = tuple(sorted(set(values)))
    for name in DATE_FILTERS:
        if name not in params:
            continue
        cleaned["filters"][name] = parse_instant(params[name])
    if "cursor" in params:
        cleaned["cursor"] = params["cursor"]
    return cleaned


def filter_fingerprint(filters: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(filters)).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Opaque, version-checked, filter-bound cursor
# --------------------------------------------------------------------------- #


def encode_cursor(entry: FindingEntry, filters: dict[str, Any]) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "p": [entry.published_epoch, entry.finding_id],
        "f": filter_fingerprint(filters),
    }
    return base64.urlsafe_b64encode(canonical_json_bytes(payload)).decode("ascii").rstrip("=")


def decode_cursor(cursor: str, filters: dict[str, Any]) -> tuple[int, str]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, binascii.Error, UnicodeEncodeError) as exc:
        raise _bad_request("Invalid cursor.", code="INVALID_CURSOR") from exc
    if not isinstance(payload, dict) or payload.get("v") != CURSOR_VERSION:
        raise _bad_request(
            "Cursor was issued for a different contract version.", code="INVALID_CURSOR"
        )
    if payload.get("f") != filter_fingerprint(filters):
        raise _bad_request(
            "Cursor was issued for a different filter set.", code="INVALID_CURSOR"
        )
    position = payload.get("p")
    if (
        not isinstance(position, list)
        or len(position) != 2
        or not isinstance(position[0], int)
        or not isinstance(position[1], str)
    ):
        raise _bad_request("Invalid cursor.", code="INVALID_CURSOR")
    return int(position[0]), str(position[1])


# --------------------------------------------------------------------------- #
# Pure query functions over the index
# --------------------------------------------------------------------------- #


def _matches(entry: FindingEntry, filters: dict[str, Any]) -> bool:
    for name in STRING_FILTERS:
        values = filters.get(name)
        if values and getattr(entry, STRING_FILTER_FIELDS.get(name, name)) not in values:
            return False
    persons = filters.get("person")
    if persons and entry.person_id not in persons:
        return False
    contents = filters.get("content")
    if contents and entry.content_id not in contents:
        return False
    start = filters.get("published_from")
    if start is not None and (entry.published_epoch == 0 or entry.published_epoch < start):
        return False
    end = filters.get("published_to")
    if end is not None and (entry.published_epoch == 0 or entry.published_epoch > end):
        return False
    return True


def select_findings(index: PublicIndex, filters: dict[str, Any]) -> list[FindingEntry]:
    return [entry for entry in index.entries if _matches(entry, filters)]


def query_findings(index: PublicIndex, params: dict[str, Any]) -> dict[str, Any]:
    """Bounded, deterministic finding collection with a stable continuation cursor."""
    cleaned = validate_params(params)
    filters = cleaned["filters"]
    limit = cleaned["limit"]
    selected = select_findings(index, filters)
    if cleaned.get("cursor"):
        epoch, finding_id = decode_cursor(str(cleaned["cursor"]), filters)
        anchor = (epoch, finding_id)
        selected = [
            entry
            for entry in selected
            if (-entry.published_epoch, entry.finding_id) > (-anchor[0], anchor[1])
        ]
    page = selected[:limit]
    next_cursor = (
        encode_cursor(page[-1], filters)
        if page and len(selected) > len(page)
        else None
    )
    return {
        "items": [entry.summary for entry in page],
        "next_cursor": next_cursor,
        "limit": limit,
        "total": len(selected),
    }


def get_finding(index: PublicIndex, finding_id: str) -> dict[str, Any]:
    entry = index.findings_by_id.get(finding_id)
    if entry is None:
        raise _not_found()
    return entry.dossier


def get_record(index: PublicIndex, slug: str) -> dict[str, Any]:
    record = index.records.get(slug)
    if record is None:
        raise _not_found()
    return dict(record)


def list_records(index: PublicIndex) -> list[dict[str, Any]]:
    rows = [dict(record) for record in index.records.values()]
    rows.sort(
        key=lambda row: (
            str(row.get("published_at") or ""),
            str(row.get("content_id") or ""),
        ),
        reverse=True,
    )
    return rows


def list_people(index: PublicIndex) -> list[dict[str, Any]]:
    rows = [
        {
            "person_id": person_id,
            "name": person["name"],
            "finding_count": person["finding_count"],
            # `topics` is the compatibility alias from the draft pre-DP-430
            # contract; it means claim-type codes and is explicitly deprecated.
            "topics": person["claim_types"],
            "claim_types": person["claim_types"],
            "subject_topic_ids": person["topic_ids"],
        }
        for person_id, person in index.people.items()
    ]
    rows.sort(key=lambda row: row["person_id"])
    return rows


def list_topics(index: PublicIndex) -> list[dict[str, Any]]:
    rows = []
    for topic in index.topics.values():
        rows.append(
            {
                "topic_id": topic["topic_id"],
                "slug": topic["slug"],
                "canonical_name": topic["canonical_name"],
                "scope_text": topic["scope_text"],
                "entity_version": topic["entity_version"],
                "review_event_ids": topic["review_event_ids"],
                "memberships": topic["memberships"],
                "finding_count": len(topic["finding_ids"]),
                "people": topic["people"],
            }
        )
    rows.sort(key=lambda row: (row["canonical_name"].casefold(), row["topic_id"]))
    return rows


def health_payload(index: PublicIndex) -> dict[str, Any]:
    return {
        "status": "ok",
        "api_version": API_CONTRACT_VERSION,
        "public_schema_version": index.schema_version,
        "domain_vocabulary_version": DOMAIN_VOCABULARY_VERSION,
        "projection_generated_at": index.generated_at,
        "dataset_fingerprint": index.dataset_sha256,
        "dossier_count": index.dossier_count,
        "omitted_count": index.omitted_count,
    }


def schema_payload(index: PublicIndex) -> dict[str, Any]:
    """The public contract descriptor served at /api/v1/schema.

    Derived from the same constants the projection validator uses, so the
    descriptor cannot drift into a second data contract.
    """
    return {
        "api_version": API_CONTRACT_VERSION,
        "public_schema_version": index.schema_version,
        "domain_vocabulary_version": DOMAIN_VOCABULARY_VERSION,
        "vocabulary_versions": {
            "claim_type": VOCABULARIES["claim_type"][0],
            "finding_publication_status": VOCABULARIES["finding_publication_status"][0],
            "relation_candidate": VOCABULARIES["relation_candidate"][0],
            "verification_assessment": VERIFICATION_ASSESSMENT_VERSION,
            "claim_relation": RELATION_VERSION,
        },
        "vocabularies": {
            name: list(values) for name, (_version, values) in VOCABULARIES.items()
        },
        "public_finding_statuses": sorted(PUBLIC_FINDING_STATUSES),
        "publishable_assessments": sorted(PUBLISHABLE_ASSESSMENTS),
        "dossier_required_keys": sorted(DOSSIER_REQUIRED_KEYS),
        "dossier_allowed_keys": sorted(DOSSIER_ALLOWED_KEYS),
        "bundle_allowed_keys": sorted(PROJECTION_BUNDLE_ALLOWED_KEYS),
        "methodology": index.methodology,
        "facets": {
            "topic": (
                "DEPRECATED compatibility alias for projection claim_type; "
                "first-class subject Topics are the /topics resource"
            ),
            "claim_type": "projection claim_type",
            "person": "projection speaker.id",
            "content": "projection source.content_id",
        },
        "pagination": {
            "default_limit": DEFAULT_LIMIT,
            "max_limit": MAX_LIMIT,
            "order": "published_at desc, finding_id asc",
            "cursor": "opaque, versioned, bound to the request filter set",
        },
        "guarantees": {
            "llm_in_request_path": False,
            "database_in_request_path": False,
            "read_only": True,
            "publication_gate": "the fail-closed public projection is the only input",
            "person_score": False,
            "ranking": False,
        },
    }


# --------------------------------------------------------------------------- #
# Response model and routing
# --------------------------------------------------------------------------- #


@dataclass
class ApiResponse:
    status: int
    body: bytes
    content_type: str
    headers: dict[str, str] = field(default_factory=dict)
    # HEAD responses carry the length the GET body would have, per RFC 9110.
    content_length: int | None = None

    @property
    def length(self) -> int:
        return len(self.body) if self.content_length is None else self.content_length


def _envelope(index: PublicIndex, data: Any, meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "data": data,
        "meta": {
            "api_version": API_CONTRACT_VERSION,
            "public_schema_version": index.schema_version,
            "contract_status": "DRAFT",
            "dataset_fingerprint": index.dataset_sha256,
            "projection_generated_at": index.generated_at,
            **meta,
        },
    }


Handler = Callable[[PublicIndex, dict[str, str]], dict[str, Any]]


def _h_findings(index: PublicIndex, params: dict[str, str]) -> dict[str, Any]:
    page = query_findings(index, params)
    return _envelope(
        index,
        page["items"],
        {
            "count": len(page["items"]),
            "limit": page["limit"],
            "total": page["total"],
            "next_cursor": page["next_cursor"],
            "link": f"{API_BASE_PATH}/findings",
        },
    )


def _h_topics(index: PublicIndex, params: dict[str, str]) -> dict[str, Any]:
    validate_params(params)
    items = list_topics(index)
    return _envelope(index, items, {"count": len(items), "link": f"{API_BASE_PATH}/topics"})


def _h_records(index: PublicIndex, params: dict[str, str]) -> dict[str, Any]:
    validate_params(params)
    items = list_records(index)
    return _envelope(index, items, {"count": len(items), "link": f"{API_BASE_PATH}/records"})


def _h_people(index: PublicIndex, params: dict[str, str]) -> dict[str, Any]:
    validate_params(params)
    items = list_people(index)
    return _envelope(index, items, {"count": len(items), "link": f"{API_BASE_PATH}/people"})


def _h_health(index: PublicIndex, params: dict[str, str]) -> dict[str, Any]:
    validate_params(params)
    return _envelope(index, health_payload(index), {"link": f"{API_BASE_PATH}/health"})


def _h_schema(index: PublicIndex, params: dict[str, str]) -> dict[str, Any]:
    validate_params(params)
    return _envelope(index, schema_payload(index), {"link": f"{API_BASE_PATH}/schema"})


def _h_index_json(index: PublicIndex, params: dict[str, str]) -> dict[str, Any]:
    validate_params(params)
    return index_full_bundle_payload(index)


def _h_openapi(index: PublicIndex, params: dict[str, str]) -> dict[str, Any]:
    validate_params(params)
    from dichiarazioni_pubbliche.openapi import build_openapi_document

    return build_openapi_document(index)


def index_full_bundle_payload(index: PublicIndex) -> dict[str, Any]:
    """The projection bundle, re-served deterministically.

    The bundle is itself the fail-closed artifact, so re-serializing the parsed
    bundle yields byte-identical canonical JSON to the projection writer.
    """
    payload = {
        "schema_version": index.schema_version,
        "generated_at": index.generated_at,
        "dataset_sha256": index.dataset_sha256,
        "methodology": index.methodology,
        "dossier_count": index.dossier_count,
        "omitted_count": index.omitted_count,
        "dossiers": [entry.dossier for entry in index.entries],
    }
    if index.topics_present:
        payload["topics"] = [
            {
                "topic_id": topic["topic_id"],
                "slug": topic["slug"],
                "canonical_name": topic["canonical_name"],
                "scope_text": topic["scope_text"],
                "entity_version": topic["entity_version"],
                "review_event_ids": topic["review_event_ids"],
                "memberships": topic["memberships"],
            }
            for topic in sorted(
                index.topics.values(),
                key=lambda item: (item["canonical_name"].casefold(), item["topic_id"]),
            )
        ]
    first_class_contents = [
        {
            key: record.get(key)
            for key in (
                "content_id",
                "slug",
                "url",
                "title",
                "published_at",
                "content_kind",
                "duration_ms",
                "public_media_url",
                "media_policy_version",
                "publication_version",
                "review_event_ids",
            )
        }
        | {"finding_ids": [item["finding_id"] for item in record["findings"]]}
        for record in index.records.values()
        if record.get("publication_version") == "public-content-v1"
    ]
    if index.contents_present:
        first_class_contents.sort(key=lambda item: (str(item["title"]).casefold(), str(item["content_id"])))
        payload["contents"] = first_class_contents
    return payload


def _load_linked_data_artifact(index: PublicIndex) -> tuple[bytes, float]:
    """Load the generated N-Triples sibling only when it matches this projection.

    ``index.nt`` and its receipt are projection-owned build artifacts.  The host
    never derives public RDF from operational state: it validates the already
    generated files against the same validated ``index.json`` currently serving
    the API and fails closed on any missing, stale, or tampered artifact.
    """
    root = Path(index.source_path).parent
    artifact_path = root / "index.nt"
    receipt_path = root / "linked-data-receipt.json"
    try:
        artifact_stat = artifact_path.stat()
        receipt_stat = receipt_path.stat()
        body = artifact_path.read_bytes()
        receipt_raw = receipt_path.read_bytes()
    except OSError as exc:
        raise _unavailable() from exc
    try:
        receipt = json.loads(receipt_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _unavailable() from exc
    if not isinstance(receipt, dict):
        raise _unavailable()

    expected = projection_linked_data_receipt(index_full_bundle_payload(index))
    if receipt != expected:
        raise _unavailable()
    if receipt.get("linked_data_version") != LINKED_DATA_VERSION:
        raise _unavailable()
    if hashlib.sha256(body).hexdigest() != receipt.get("ntriples_sha256"):
        raise _unavailable()
    if len(body) != receipt.get("byte_count"):
        raise _unavailable()
    try:
        body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _unavailable() from exc
    triple_count = sum(1 for line in body.splitlines() if line.strip())
    if triple_count != receipt.get("triple_count"):
        raise _unavailable()
    return body, max(index.mtime, artifact_stat.st_mtime, receipt_stat.st_mtime)


@dataclass(frozen=True)
class Route:
    name: str
    methods: tuple[str, ...]
    pattern: str  # "/api/v1/findings/{finding_id}"
    handler: Handler | None = None
    # (path parameter name, pure resolver, canonical link template)
    detail: tuple[str, Callable[[PublicIndex, str], Any], str] | None = None
    document_cache: bool = False


ROUTES: tuple[Route, ...] = (
    Route("health", ("GET", "HEAD"), f"{API_BASE_PATH}/health", _h_health),
    Route("schema", ("GET", "HEAD"), f"{API_BASE_PATH}/schema", _h_schema, document_cache=True),
    Route("findings", ("GET", "HEAD"), f"{API_BASE_PATH}/findings", _h_findings),
    Route("records", ("GET", "HEAD"), f"{API_BASE_PATH}/records", _h_records),
    Route(
        "finding",
        ("GET", "HEAD"),
        f"{API_BASE_PATH}/findings/{{finding_id}}",
        detail=("finding_id", get_finding, f"{API_BASE_PATH}/findings/{{value}}"),
    ),
    Route(
        "record",
        ("GET", "HEAD"),
        f"{API_BASE_PATH}/records/{{slug}}",
        detail=("slug", get_record, f"{API_BASE_PATH}/records/{{value}}"),
    ),
    Route("topics", ("GET", "HEAD"), f"{API_BASE_PATH}/topics", _h_topics),
    Route("people", ("GET", "HEAD"), f"{API_BASE_PATH}/people", _h_people),
    Route("openapi", ("GET", "HEAD"), f"{API_BASE_PATH}/openapi.json", _h_openapi, document_cache=True),
    Route("index", ("GET", "HEAD"), f"{API_BASE_PATH}/index.json", _h_index_json, document_cache=True),
)

JSON_CONTENT_TYPE = "application/json; charset=utf-8"
LLMS_CONTENT_TYPE = "text/plain; charset=utf-8"
NTRIPLES_CONTENT_TYPE = "application/n-triples"
ALLOWED_ACCEPT = ("application/json", "*/*", "application/*")
LINKED_DATA_ACCEPT = (NTRIPLES_CONTENT_TYPE, "*/*", "application/*")


def _discovery_link_header() -> str:
    return (
        f'<{API_BASE_PATH}/openapi.json>; rel="service-desc", '
        f'<{LINKED_DATA_PATH}>; rel="alternate"; type="{NTRIPLES_CONTENT_TYPE}"'
    )


def match_route(path: str) -> tuple[Route, dict[str, str]]:
    """Resolve a path to a route. Unknown paths are 404, never a name lookup."""
    normalized = path if path.startswith("/") else "/" + path
    if normalized.endswith("/") and len(normalized) > 1:
        normalized = normalized.rstrip("/")
    segments = [segment for segment in normalized.split("/") if segment != ""]
    for route in ROUTES:
        route_segments = [s for s in route.pattern.split("/") if s != ""]
        if len(route_segments) != len(segments):
            continue
        params: dict[str, str] = {}
        ok = True
        for expected, actual in zip(route_segments, segments):
            if expected.startswith("{") and expected.endswith("}"):
                name = expected[1:-1]
                value = unquote(actual)
                if not value:
                    ok = False
                    break
                params[name] = value
            elif expected != actual:
                ok = False
                break
        if ok:
            return route, params
    raise _not_found()


def _http_date(epoch: float) -> str:
    return formatdate(epoch, usegmt=True)


def build_response(
    index: PublicIndex,
    route: Route,
    path_params: dict[str, str],
    query: str,
    *,
    request_id: str,
    method: str = "GET",
    conditional_headers: dict[str, str] | None = None,
) -> ApiResponse:
    """Pure request-to-response function, including validators."""
    params = parse_query(query)
    if route.detail is not None:
        param_name, resolver, link_template = route.detail
        validate_params(params)
        value = path_params[param_name]
        data = resolver(index, value)
        payload: Any = _envelope(
            index,
            data,
            {"link": link_template.replace("{value}", value)},
        )
    else:
        assert route.handler is not None
        payload = route.handler(index, params)

    body = canonical_json_bytes(payload)
    etag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'
    last_modified = _http_date(index.mtime)
    max_age = DOCUMENT_MAX_AGE if route.document_cache else DATA_MAX_AGE
    headers = {
        "ETag": etag,
        "Last-Modified": last_modified,
        "Cache-Control": (
            f"public, max-age={max_age}, stale-while-revalidate={STALE_WHILE_REVALIDATE}"
        ),
        API_VERSION_HEADER: API_CONTRACT_VERSION,
        "X-Content-Type-Options": "nosniff",
        "Vary": "Accept",
        "Link": _discovery_link_header(),
    }
    conditional = conditional_headers or {}
    if _is_fresh(conditional, etag, last_modified):
        return ApiResponse(304, b"", JSON_CONTENT_TYPE, headers)
    if method == "HEAD":
        # Same status, headers, and validators as GET, without a body.
        return ApiResponse(200, b"", JSON_CONTENT_TYPE, headers, content_length=len(body))
    return ApiResponse(200, body, JSON_CONTENT_TYPE, headers)


def _is_fresh(headers: dict[str, str], etag: str, last_modified: str) -> bool:
    if_none_match = headers.get("if-none-match")
    if if_none_match:
        candidates = {token.strip() for token in if_none_match.split(",")}
        if "*" in candidates or etag in candidates or etag.strip('"') in {
            token.strip('"') for token in candidates
        }:
            return True
        return False
    if_modified_since = headers.get("if-modified-since")
    if if_modified_since:
        try:
            since = parsedate_to_datetime(if_modified_since)
        except (TypeError, ValueError):
            return False
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        current = parsedate_to_datetime(last_modified)
        return current <= since
    return False


def error_response(
    error: PublicApiError, *, request_id: str, method: str = "GET"
) -> ApiResponse:
    body = canonical_json_bytes(error.payload(request_id))
    headers = {
        "Cache-Control": "no-store",
        API_VERSION_HEADER: API_CONTRACT_VERSION,
        "X-Content-Type-Options": "nosniff",
        "Vary": "Accept",
    }
    headers.update(error.headers)
    return ApiResponse(error.status, b"" if method == "HEAD" else body, JSON_CONTENT_TYPE, headers)


def _accepts_json(value: str | None) -> bool:
    if not value:
        return True
    for item in value.split(","):
        media_type = item.split(";", 1)[0].strip().lower()
        if media_type in ALLOWED_ACCEPT:
            return True
    return False


def _accepts_ntriples(value: str | None) -> bool:
    if not value:
        return True
    for item in value.split(","):
        media_type = item.split(";", 1)[0].strip().lower()
        if media_type in LINKED_DATA_ACCEPT:
            return True
    return False


def llms_response(
    method: str,
    *,
    projection_path: str | os.PathLike[str] | None,
    conditional_headers: dict[str, str] | None = None,
) -> ApiResponse:
    """Generate the same-origin agent discovery document from the public projection."""
    index = load_index(projection_path)
    from dichiarazioni_pubbliche.openapi import build_llms_txt

    body = build_llms_txt(index).encode("utf-8")
    etag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'
    last_modified = _http_date(index.mtime)
    headers = {
        "ETag": etag,
        "Last-Modified": last_modified,
        "Cache-Control": (
            f"public, max-age={DOCUMENT_MAX_AGE}, "
            f"stale-while-revalidate={STALE_WHILE_REVALIDATE}"
        ),
        "X-Content-Type-Options": "nosniff",
        "Link": _discovery_link_header(),
    }
    if _is_fresh(conditional_headers or {}, etag, last_modified):
        return ApiResponse(304, b"", LLMS_CONTENT_TYPE, headers)
    if method == "HEAD":
        return ApiResponse(200, b"", LLMS_CONTENT_TYPE, headers, content_length=len(body))
    return ApiResponse(200, body, LLMS_CONTENT_TYPE, headers)


def linked_data_response(
    method: str,
    *,
    projection_path: str | os.PathLike[str] | None,
    conditional_headers: dict[str, str] | None = None,
    accept: str | None = None,
) -> ApiResponse:
    """Serve the generated projection ``index.nt`` from the approved bundle only."""
    if not _accepts_ntriples(accept):
        raise PublicApiError(
            406,
            "NOT_ACCEPTABLE",
            f"This resource serves {NTRIPLES_CONTENT_TYPE}.",
        )
    index = load_index(projection_path)
    body, artifact_mtime = _load_linked_data_artifact(index)
    etag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'
    last_modified = _http_date(artifact_mtime)
    headers = {
        "ETag": etag,
        "Last-Modified": last_modified,
        "Cache-Control": (
            f"public, max-age={DOCUMENT_MAX_AGE}, "
            f"stale-while-revalidate={STALE_WHILE_REVALIDATE}"
        ),
        "X-Content-Type-Options": "nosniff",
        "Vary": "Accept",
        "Link": (
            f'<{API_BASE_PATH}/index.json>; rel="alternate"; type="application/json", '
            f'<{API_BASE_PATH}/openapi.json>; rel="service-desc"'
        ),
    }
    if _is_fresh(conditional_headers or {}, etag, last_modified):
        return ApiResponse(304, b"", NTRIPLES_CONTENT_TYPE, headers)
    if method == "HEAD":
        return ApiResponse(200, b"", NTRIPLES_CONTENT_TYPE, headers, content_length=len(body))
    return ApiResponse(200, body, NTRIPLES_CONTENT_TYPE, headers)


def dispatch(
    method: str,
    path: str,
    *,
    projection_path: str | os.PathLike[str] | None = None,
    conditional_headers: dict[str, str] | None = None,
    request_id: str = "req",
    accept: str | None = None,
) -> ApiResponse:
    """Transport-agnostic entry point: method + path + query -> ApiResponse.

    Used directly by the tests and by the bundled HTTP server, so the tested
    contract is the served contract.
    """
    split = urlsplit(path)
    try:
        if method not in ("GET", "HEAD"):
            raise PublicApiError(
                405,
                "METHOD_NOT_ALLOWED",
                "This API is read-only.",
                headers={"Allow": "GET, HEAD"},
            )
        if split.path == LINKED_DATA_PATH:
            linked_params = parse_query(split.query)
            if method == "GET" and "_method" in linked_params:
                raise PublicApiError(
                    405,
                    "METHOD_NOT_ALLOWED",
                    "This public host is read-only.",
                    headers={"Allow": "GET, HEAD"},
                )
            if linked_params:
                raise _bad_request(
                    "The linked-data export does not accept query parameters.",
                    code="UNSUPPORTED_PARAMETER",
                )
            return linked_data_response(
                method,
                projection_path=projection_path,
                conditional_headers=conditional_headers,
                accept=accept,
            )
        if not _accepts_json(accept):
            raise PublicApiError(
                406,
                "NOT_ACCEPTABLE",
                "This API serves application/json.",
            )
        if method == "GET" and "_method" in parse_query(split.query):
            raise PublicApiError(
                405,
                "METHOD_NOT_ALLOWED",
                "This API is read-only.",
                headers={"Allow": "GET, HEAD"},
            )
        if not split.path.startswith(API_BASE_PATH):
            raise _not_found()
        try:
            index = load_index(projection_path)
        except PublicApiError:
            raise
        route, path_params = match_route(split.path)
        return build_response(
            index,
            route,
            path_params,
            split.query,
            request_id=request_id,
            method=method,
            conditional_headers=conditional_headers,
        )
    except PublicApiError as exc:
        return error_response(exc, request_id=request_id, method=method)
    except Exception:  # pragma: no cover - defensive: never leak internals
        return error_response(
            PublicApiError(500, "INTERNAL_ERROR", "Unexpected server error."),
            request_id=request_id,
            method=method,
        )


# --------------------------------------------------------------------------- #
# Stdlib HTTP adapter
# --------------------------------------------------------------------------- #

class PublicApiRequestHandler(SimpleHTTPRequestHandler):
    server_version = "DichiarazioniPubblichePublicHost/1.0"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    projection_path: str | None = None
    static_dir: str | None = None
    quiet: bool = True
    account_service: AccountService | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        directory = type(self).static_dir
        if directory is not None:
            kwargs["directory"] = directory
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        if not self.quiet:  # pragma: no cover - operational only
            super().log_message(format, *args)

    def _request_id(self) -> str:
        incoming = self.headers.get("X-Request-Id")
        if incoming and len(incoming) <= 128:
            return incoming
        return hashlib.sha256(
            f"{self.command}:{self.path}:{id(self)}".encode()
        ).hexdigest()[:32]

    def _conditional_headers(self) -> dict[str, str]:
        return {
            "if-none-match": self.headers.get("If-None-Match", ""),
            "if-modified-since": self.headers.get("If-Modified-Since", ""),
        }

    def _write_response(self, response: ApiResponse) -> None:
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(response.length))
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.end_headers()
        if response.body:
            self.wfile.write(response.body)

    def _serve_api(self, method: str) -> None:
        response = dispatch(
            method,
            self.path,
            projection_path=type(self).projection_path,
            conditional_headers=self._conditional_headers(),
            request_id=self._request_id(),
            accept=self.headers.get("Accept"),
        )
        self._write_response(response)

    def _serve_llms(self, method: str) -> None:
        try:
            response = llms_response(
                method,
                projection_path=type(self).projection_path,
                conditional_headers=self._conditional_headers(),
            )
        except PublicApiError as exc:
            response = error_response(exc, request_id=self._request_id(), method=method)
        self._write_response(response)

    def _is_api_path(self) -> bool:
        path = urlsplit(self.path).path
        return path == API_BASE_PATH or path.startswith(API_BASE_PATH + "/")

    def _account_cookie(self, name: str) -> str:
        # Duplicate headers/keys are ambiguous and must never select one
        # attacker-chosen session or OAuth browser binding.
        values = self.headers.get_all("Cookie", [])
        if len(values) != 1 or len(values[0]) > 1024:
            return ""
        items = [entry.strip().split("=", 1) for entry in values[0].split(";")]
        matches = [item[1] for item in items if len(item) == 2 and item[0] == name]
        return matches[0] if len(matches) == 1 else ""

    def _serve_account(self) -> None:
        service = type(self).account_service
        path = urlsplit(self.path).path
        self.close_connection = True  # Never parse a rejected POST body as another request.

        def reply(status: int, body: bytes = b"", *, location: str = "", cookie: str = "", clear_flow: bool = False) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Vary", "Cookie")
            self.send_header("Surrogate-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
            self.send_header("Connection", "close")
            if location:
                self.send_header("Location", location)
            if cookie:
                self.send_header("Set-Cookie", cookie)
            if clear_flow:
                self.send_header("Set-Cookie", f"{FLOW_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0")
            self.end_headers()
            if self.command != "HEAD" and body:
                self.wfile.write(body)

        if service is None:
            reply(404)
            return
        from urllib.parse import urlsplit as _split
        expected_host = _split(service.site_origin).netloc
        if (self.headers.get_all("Host", []) != [expected_host]
                or self.headers.get("Transfer-Encoding")
                or self.headers.get_all("Cookie", []) and len(self.headers.get_all("Cookie", [])) != 1):
            reply(403)
            return
        now = int(__import__("time").time())
        try:
            if self.command == "POST":
                if self.headers.get_all("Origin", []) != [service.site_origin]:
                    reply(403)
                    return
                if self.headers.get("Sec-Fetch-Site", "same-origin") != "same-origin":
                    reply(403)
                    return
                lengths = self.headers.get_all("Content-Length", [])
                if lengths not in ([], ["0"]):
                    reply(413)
                    return
                if urlsplit(self.path).query:
                    reply(400)
                    return
                if path == "/account/auth/google":
                    result = service.start(now, self._account_cookie(VISITOR_COOKIE))
                elif path in ("/account/api/logout", "/account/api/delete"):
                    values = self.headers.get_all("X-CSRF-Token", [])
                    token = values[0] if len(values) == 1 and len(values[0]) <= 128 else ""
                    result = service.finish(self._account_cookie(SESSION_COOKIE), token, now,
                                            delete_account=path.endswith("/delete"))
                else:
                    reply(404)
                    return
            elif self.command == "GET":
                if path == "/account/api/session" and not urlsplit(self.path).query:
                    result = service.inspect(self._account_cookie(SESSION_COOKIE), now)
                    if result.status == 401:
                        reply(401, result.body, cookie=(
                            f"{VISITOR_COOKIE}={service.new_visitor()}; Path=/; Secure; "
                            "HttpOnly; SameSite=Lax; Max-Age=2592000"
                        ))
                        return
                elif path == "/account/oauth/callback":
                    query = urlsplit(self.path).query
                    if len(query) > 4096:
                        raise ValueError("ACCOUNT_CALLBACK_TOO_LARGE")
                    args = parse_qs(query, keep_blank_values=True, strict_parsing=True)
                    if set(args) != {"state", "code"} or any(len(values) != 1 for values in args.values()):
                        raise ValueError("ACCOUNT_CALLBACK_INVALID")
                    result = service.callback_response(args["state"][0], args["code"][0],
                                                       self._account_cookie(FLOW_COOKIE), now)
                else:
                    reply(404)
                    return
            else:
                reply(405)
                return
            reply(result.status, result.body, location=result.location, cookie=result.cookie,
                  clear_flow=result.clear_flow)
        except Exception as exc:
            # Provider failures never expose token, email, identity or status to
            # public callers or to the HTTP access log.
            reply(429 if isinstance(exc, ValueError) and str(exc) == "ACCOUNT_LOGIN_RATE_LIMIT" else
                  (503 if path == "/account/auth/google" else 400),
                  b'{"error":"ACCOUNT_OPERATION_UNAVAILABLE"}')

    def _is_account_path(self) -> bool:
        return urlsplit(self.path).path in {
            "/account/auth/google", "/account/oauth/callback",
            "/account/api/session", "/account/api/logout", "/account/api/delete",
        }

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if self._is_account_path():
            self._serve_account()
        elif self._is_api_path() or path == LINKED_DATA_PATH:
            self._serve_api("GET")
        elif path == LLMS_PATH:
            self._serve_llms("GET")
        elif type(self).static_dir is not None:
            super().do_GET()
        else:
            self._serve_api("GET")

    def do_HEAD(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if self._is_account_path():
            self.close_connection = True
            self.send_error(405)
        elif self._is_api_path() or path == LINKED_DATA_PATH:
            self._serve_api("HEAD")
        elif path == LLMS_PATH:
            self._serve_llms("HEAD")
        elif type(self).static_dir is not None:
            super().do_HEAD()
        else:
            self._serve_api("HEAD")

    def _reject(self) -> None:
        if self._is_account_path():
            self._serve_account()
            return
        request_id = self._request_id()
        response = error_response(
            PublicApiError(
                405, "METHOD_NOT_ALLOWED", "This API is read-only.", headers={"Allow": "GET, HEAD"}
            ),
            request_id=request_id,
            method=self.command,
        )
        self._write_response(response)

    do_POST = _reject  # noqa: N815
    do_PUT = _reject  # noqa: N815
    do_PATCH = _reject  # noqa: N815
    do_DELETE = _reject  # noqa: N815
    do_OPTIONS = _reject  # noqa: N815


def build_server(
    projection_path: str | os.PathLike[str] | None,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    static_dir: str | os.PathLike[str] | None = None,
    account_service: AccountService | None = None,
) -> ThreadingHTTPServer:
    if account_service is not None and host not in ("127.0.0.1", "::1"):
        raise ValueError("ACCOUNT_LOOPBACK_BIND_REQUIRED")
    resolved_static = str(Path(static_dir).resolve()) if static_dir is not None else None
    handler = type(
        "BoundPublicApiRequestHandler",
        (PublicApiRequestHandler,),
        {
            "projection_path": str(projection_path) if projection_path else None,
            "static_dir": resolved_static,
            "account_service": account_service,
        },
    )
    return ThreadingHTTPServer((host, port), handler)


def main(argv: Iterable[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Serve the read-only public API over a public projection bundle."
    )
    parser.add_argument("--projection-path", default=projection_path_from_env())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--account-client-id", default="")
    parser.add_argument("--account-client-secret-file", type=Path)
    parser.add_argument("--account-db", type=Path)
    parser.add_argument("--account-site-origin", default="")
    parser.add_argument(
        "--static-dir",
        help="Optional static site directory to serve from the same origin as /api/v1.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.projection_path:
        parser.error(f"set {PROJECTION_PATH_ENV} or pass --projection-path")
    if args.static_dir and not Path(args.static_dir).is_dir():
        parser.error(f"static directory does not exist: {args.static_dir}")
    account_options = (args.account_client_id, args.account_client_secret_file,
                       args.account_db, args.account_site_origin)
    if any(account_options) and not all(account_options):
        parser.error("account OIDC requires client ID, protected secret file, private DB and HTTPS site origin")
    account_service = None
    if all(account_options):
        try:
            secret = read_secret_file(args.account_client_secret_file)
            store = AccountStore(args.account_db)
            provider = GoogleOidcProvider(args.account_client_id, secret,
                                          args.account_site_origin + "/account/oauth/callback")
            account_service = AccountService(args.account_client_id,
                                             args.account_site_origin, store, provider,
                                             visitor_key=secret)
        except (OSError, ValueError, UnicodeError) as exc:
            parser.error(f"account OIDC configuration refused: {exc}")
    server = build_server(
        args.projection_path,
        host=args.host,
        port=args.port,
        static_dir=args.static_dir,
        account_service=account_service,
    )
    host, port = server.server_address[0], server.server_address[1]
    surface = "public host" if args.static_dir else "public API"
    print(f"Dichiarazioni Pubbliche {surface} ({API_CONTRACT_VERSION}) on http://{host}:{port}{API_BASE_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - operational only
        pass
    finally:
        server.server_close()
    return 0


__all__ = [
    "ALLOWED_ACCEPT",
    "ALLOWED_QUERY_PARAMS",
    "API_BASE_PATH",
    "API_CONTRACT_VERSION",
    "API_MAJOR_VERSION",
    "API_VERSION_HEADER",
    "LINKED_DATA_PATH",
    "LLMS_PATH",
    "NTRIPLES_CONTENT_TYPE",
    "CURSOR_VERSION",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "PROJECTION_PATH_ENV",
    "PUBLIC_SCHEMA_VERSION",
    "ROUTES",
    "ApiResponse",
    "FindingEntry",
    "PublicApiError",
    "PublicApiRequestHandler",
    "PublicIndex",
    "Route",
    "build_index",
    "build_response",
    "build_server",
    "canonical_json_bytes",
    "decode_cursor",
    "dispatch",
    "encode_cursor",
    "get_finding",
    "get_record",
    "health_payload",
    "index_full_bundle_payload",
    "linked_data_response",
    "llms_response",
    "list_people",
    "list_topics",
    "list_records",
    "load_index",
    "match_route",
    "parse_instant",
    "parse_query",
    "projection_path_from_env",
    "query_findings",
    "schema_payload",
    "select_findings",
    "slugify",
    "validate_params",
]


if __name__ == "__main__":
    raise SystemExit(main())
