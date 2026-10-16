"""DP-243: private historical corpus manifest preflight, with no acquisition ability.

This module checks caller-supplied synthetic or independently acquired metadata.
It cannot authenticate archive identity, private-rights receipts, OCR, historical
attribution, historical facts, or source-recovery authority. A passing result is
only an offline review proposal; neither storage nor fetching nor publication
is authorized by this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dichiarazioni_pubbliche.original_source_resolver import (
    ExactSourceLocatorResolution,
)
from dichiarazioni_pubbliche.private_capture_rights import evaluate_source_use
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRecord, RightsSubject


VERSION = "private-historical-corpus-preflight-v1"
SUBJECT_LANGUAGES = {"MUSSOLINI": "it", "HITLER": "de"}
SOURCE_KINDS = frozenset(
    {
        "PRIMARY_ORIGINAL",
        "ARCHIVE_COPY",
        "EDITORIAL_TRANSLATION",
        "SECONDARY_SCHOLARSHIP",
    }
)
MEDIA_TYPES = frozenset(
    {
        "text/plain",
        "text/html",
        "application/pdf",
        "image/jpeg",
        "image/png",
        "video/mp4",
        "audio/mpeg",
    }
)
MAX_ITEMS = 8
MAX_PER_MANIFEST = 8
MAX_PREVIOUS = 16
_SHA = re.compile(r"^[a-f0-9]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_./-]{0,199}$")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"DP243_{label}_INVALID")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(f"DP243_{label}_INVALID")
    return value


def _utc(value: object, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"DP243_{label}_AWARE_REQUIRED")
    return value.astimezone(timezone.utc)


def _fingerprint(material: object) -> str:
    return hashlib.sha256(
        json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=lambda obj: (
                obj.isoformat() if isinstance(obj, datetime) else str(obj)
            ),
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class HistoricalEntry:
    entry_id: str
    subject: str
    collection_id: str
    content_id: str
    source_family: str
    locator_url: str
    source_kind: str
    original_language: str
    media_type: str
    source_version_sha256: str
    selector_fingerprint: str
    observed_at: datetime
    event_at: datetime
    event_timezone: str
    attribution_role: str  # AUTHOR, SPEAKER, NARRATOR, ACTOR, REPORTED, UNKNOWN
    role_review_ref: str | None
    origin_content_id: str | None
    origin_sha256: str | None
    rights_subject: RightsSubject
    rights_record: PrivateRightsRecord | None
    rights_record_id: str
    rights_policy_version: str
    exact_locator: ExactSourceLocatorResolution | None
    supersedes_sha256: str | None = None
    edition_method: str | None = None
    edition_date: datetime | None = None
    additional_collection_ids: tuple[str, ...] = ()
    version: str = VERSION


@dataclass(frozen=True)
class HistoricalManifest:
    subject: str
    person_id: str
    collection_id: str
    coverage_start: datetime
    coverage_horizon: datetime
    coverage_scope_ref: str
    entries: tuple[HistoricalEntry, ...]
    version: str = VERSION


@dataclass(frozen=True)
class HistoricalEntryDecision:
    entry_id: str
    content_id: str
    source_version_sha256: str
    root_content_id: str | None
    source_kind: str
    state: str  # HELD or PRIVATE_REVIEW_ONLY; never acquisition permission
    holds: tuple[str, ...]
    permission_fingerprints: tuple[str, ...]
    collections: tuple[str, ...]
    dispatch_authorized: bool = False
    public_eligible: bool = False


@dataclass(frozen=True)
class HistoricalCorpusPreflight:
    version: str
    manifest_fingerprint: str
    rows: tuple[HistoricalEntryDecision, ...]
    logical_content_ids: tuple[str, ...]
    revalidation_content_ids: tuple[str, ...]
    missing_primary_subjects: tuple[str, ...] = ()
    coverage_state: str = "SCOPED_UNVERIFIED"
    dispatch_authorized: bool = False
    public_eligible: bool = False


def _validate_entry(
    entry: HistoricalEntry, *, manifest: HistoricalManifest, now: datetime
) -> None:
    if not isinstance(entry, HistoricalEntry) or entry.version != VERSION:
        raise ValueError("DP243_ENTRY_CONTRACT_INVALID")
    for name in (
        "entry_id",
        "collection_id",
        "content_id",
        "source_family",
        "rights_record_id",
        "rights_policy_version",
    ):
        _text(getattr(entry, name), name.upper())
    if (
        entry.subject != manifest.subject
        or entry.collection_id != manifest.collection_id
    ):
        raise ValueError("DP243_ENTRY_COLLECTION_OR_SUBJECT_MISMATCH")
    if entry.source_kind not in SOURCE_KINDS:
        raise ValueError("DP243_SOURCE_KIND_INVALID")
    if (
        entry.original_language not in {"de", "it"}
        or entry.media_type not in MEDIA_TYPES
    ):
        raise ValueError("DP243_LANGUAGE_OR_MEDIA_INVALID")
    _digest(entry.source_version_sha256, "SOURCE_VERSION_HASH")
    _digest(entry.selector_fingerprint, "SELECTOR_HASH")
    if entry.supersedes_sha256 is not None:
        _digest(entry.supersedes_sha256, "SUPERSEDES_HASH")
    _utc(entry.observed_at, "OBSERVED_AT")
    moment = _utc(entry.event_at, "EVENT_AT")
    if _utc(entry.observed_at, "OBSERVED_AT") > now:
        raise ValueError("DP243_FUTURE_OBSERVATION")
    if (
        not _utc(manifest.coverage_start, "COVERAGE_START")
        <= moment
        <= _utc(manifest.coverage_horizon, "COVERAGE_HORIZON")
    ):
        raise ValueError("DP243_EVENT_OUTSIDE_COVERAGE_SCOPE")
    if not isinstance(entry.event_timezone, str) or len(entry.event_timezone) > 80:
        raise ValueError("DP243_EVENT_TIMEZONE_INVALID")
    try:
        ZoneInfo(entry.event_timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise ValueError("DP243_EVENT_TIMEZONE_INVALID") from exc
    if entry.attribution_role not in {
        "AUTHOR",
        "SPEAKER",
        "NARRATOR",
        "ACTOR",
        "REPORTED",
        "UNKNOWN",
    }:
        raise ValueError("DP243_SPEECH_ACT_INVALID")
    if entry.role_review_ref is not None:
        _text(entry.role_review_ref, "ROLE_REVIEW_REF")
    if entry.origin_content_id is not None:
        _text(entry.origin_content_id, "ORIGIN_CONTENT")
    if entry.origin_sha256 is not None:
        _digest(entry.origin_sha256, "ORIGIN_HASH")
    if (entry.origin_content_id is None) != (entry.origin_sha256 is None):
        raise ValueError("DP243_ORIGIN_PAIR_INVALID")
    if entry.source_kind == "PRIMARY_ORIGINAL" and entry.origin_content_id is not None:
        raise ValueError("DP243_PRIMARY_CANNOT_HAVE_PARENT")
    if entry.edition_method is not None:
        _text(entry.edition_method, "EDITION_METHOD")
    if entry.edition_date is not None:
        _utc(entry.edition_date, "EDITION_DATE")
        if _utc(entry.edition_date, "EDITION_DATE") > now:
            raise ValueError("DP243_FUTURE_EDITION")
    if (
        not isinstance(entry.additional_collection_ids, tuple)
        or len(entry.additional_collection_ids) > 4
    ):
        raise ValueError("DP243_COLLECTION_MEMBERSHIP_INVALID")
    if len(set(entry.additional_collection_ids)) != len(
        entry.additional_collection_ids
    ):
        raise ValueError("DP243_COLLECTION_MEMBERSHIP_INVALID")
    for collection_id in entry.additional_collection_ids:
        _text(collection_id, "ADDITIONAL_COLLECTION")
        if collection_id == manifest.collection_id:
            raise ValueError("DP243_COLLECTION_MEMBERSHIP_INVALID")
    if not isinstance(entry.locator_url, str) or len(entry.locator_url) > 2048:
        raise ValueError("DP243_SOURCE_URL_INVALID")
    try:
        parsed = urlsplit(entry.locator_url)
        valid_url = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and parsed.port in (None, 443)
            and not any(char.isspace() for char in entry.locator_url)
        )
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ValueError("DP243_SOURCE_URL_INVALID")
    if not isinstance(entry.rights_subject, RightsSubject):
        raise ValueError("DP243_RIGHTS_SUBJECT_INVALID")
    if entry.rights_record is not None and not isinstance(
        entry.rights_record, PrivateRightsRecord
    ):
        raise ValueError("DP243_RIGHTS_RECORD_INVALID")
    if entry.exact_locator is not None and not isinstance(
        entry.exact_locator, ExactSourceLocatorResolution
    ):
        raise ValueError("DP243_EXACT_LOCATOR_INVALID")


def _identity(entry: HistoricalEntry) -> tuple[object, ...]:
    """A Content in two collections has one pinned immutable source identity."""
    return (
        entry.entry_id,
        entry.subject,
        entry.content_id,
        entry.source_family,
        entry.locator_url,
        entry.source_kind,
        entry.original_language,
        entry.media_type,
        entry.source_version_sha256,
        entry.selector_fingerprint,
        entry.observed_at,
        entry.event_at,
        entry.event_timezone,
        entry.attribution_role,
        entry.role_review_ref,
        entry.origin_content_id,
        entry.origin_sha256,
        entry.rights_subject,
        entry.rights_record,
        entry.rights_record_id,
        entry.rights_policy_version,
        entry.exact_locator,
        entry.supersedes_sha256,
        entry.edition_method,
        entry.edition_date,
    )


def _source_material(entry: HistoricalEntry) -> dict[str, object]:
    """Encode one logical immutable input independently of its collection memberships."""
    material = asdict(entry)
    material.pop("additional_collection_ids")
    return material


def _rights(
    entry: HistoricalEntry, *, now: datetime, additional_use: str | None = None
) -> tuple[set[str], tuple[str, ...]]:
    uses = ["FETCH", "STORE_BODY"]
    if entry.media_type in {"application/pdf", "image/jpeg", "image/png"}:
        uses.append("PARSE_OCR")
    elif entry.media_type.startswith(("video/", "audio/")):
        uses.append("ASR_MEDIA")
    else:
        uses.append("PARSE_TEXT")
    if entry.source_kind == "ARCHIVE_COPY":
        uses.append("ARCHIVE")
    if additional_use is not None:
        uses = [additional_use]
    holds: set[str] = set()
    fingerprints: set[str] = set()
    if (
        entry.rights_subject.source_family != entry.source_family
        or entry.rights_subject.locator_kind != "URL"
        or entry.rights_subject.locator_value != entry.locator_url
        or entry.rights_subject.content_id != entry.content_id
        or any(
            (
                entry.rights_subject.evidence_id,
                entry.rights_subject.transcript_segment_id,
                entry.rights_subject.canonical_segment_id,
                entry.rights_subject.passage_id,
            )
        )
    ):
        holds.add("RIGHTS_ARTIFACT_BINDING_INVALID")
    for use in uses:
        decision = evaluate_source_use(
            entry.rights_record,
            subject=entry.rights_subject,
            rights_record_id=entry.rights_record_id,
            policy_version=entry.rights_policy_version,
            use=use,
            now=now,
        )
        if not decision.permitted or holds:
            holds.add(
                decision.reason_code
                if not decision.permitted
                else "RIGHTS_ARTIFACT_BINDING_INVALID"
            )
        elif decision.decision_fingerprint is not None:
            fingerprints.add(decision.decision_fingerprint)
        else:
            holds.add("RIGHTS_FINGERPRINT_MISSING")
    return holds, tuple(sorted(fingerprints))


def preflight_historical_corpus(
    manifests: tuple[HistoricalManifest, ...],
    *,
    now: datetime,
    previous: tuple[HistoricalEntry, ...] = (),
) -> HistoricalCorpusPreflight:
    """Evaluate two tightly bounded synthetic/private manifests without side effects.

    Passing rights records, role reviewers and locator resolutions are **inputs**,
    not authenticated proof. Runtime must re-read current authority and perform
    separate approved, bounded acquisition; this never dispatches it.
    """
    clock = _utc(now, "CLOCK")
    if (
        not isinstance(manifests, tuple)
        or len(manifests) != 2
        or not all(isinstance(x, HistoricalManifest) for x in manifests)
        or {x.subject for x in manifests} != set(SUBJECT_LANGUAGES)
    ):
        raise ValueError("DP243_TWO_SUBJECTS_REQUIRED")
    if not isinstance(previous, tuple) or len(previous) > MAX_PREVIOUS:
        raise ValueError("DP243_PREVIOUS_CAP_INVALID")
    if len({x.person_id for x in manifests}) != 2:
        raise ValueError("DP243_PERSON_SCOPE_INVALID")
    if len({x.collection_id for x in manifests}) != 2:
        raise ValueError("DP243_COLLECTION_SCOPE_INVALID")

    canonical = sorted(
        manifests, key=lambda item: ("MUSSOLINI", "HITLER").index(item.subject)
    )
    indexed: dict[str, HistoricalEntry] = {}
    memberships: dict[str, set[str]] = {}
    entry_ids: dict[str, str] = {}
    for manifest in canonical:
        if manifest.version != VERSION:
            raise ValueError("DP243_MANIFEST_VERSION_INVALID")
        for field in ("person_id", "collection_id", "coverage_scope_ref"):
            _text(getattr(manifest, field), field.upper())
        if (
            _utc(manifest.coverage_start, "COVERAGE_START")
            >= _utc(manifest.coverage_horizon, "COVERAGE_HORIZON")
            or _utc(manifest.coverage_horizon, "COVERAGE_HORIZON") > clock
        ):
            raise ValueError("DP243_HORIZON_INVALID")
        if (
            not isinstance(manifest.entries, tuple)
            or len(manifest.entries) > MAX_PER_MANIFEST
        ):
            raise ValueError("DP243_ITEM_CAP_EXCEEDED")
        for item in manifest.entries:
            _validate_entry(item, manifest=manifest, now=clock)
            if (
                item.source_kind == "PRIMARY_ORIGINAL"
                and item.original_language != SUBJECT_LANGUAGES[item.subject]
            ):
                raise ValueError("DP243_ORIGINAL_LANGUAGE_MISMATCH")
            if (
                item.entry_id in entry_ids
                and entry_ids[item.entry_id] != item.content_id
            ):
                raise ValueError("DP243_ENTRY_ID_CONFLICT")
            entry_ids[item.entry_id] = item.content_id
            old = indexed.get(item.content_id)
            if old is not None and _identity(old) != _identity(item):
                raise ValueError("DP243_CONTENT_CONFLICT")
            indexed[item.content_id] = item
            memberships.setdefault(item.content_id, set()).update(
                (manifest.collection_id, *item.additional_collection_ids)
            )
    if len(indexed) > MAX_ITEMS:
        raise ValueError("DP243_ITEM_CAP_EXCEEDED")

    before: dict[str, HistoricalEntry] = {}
    for record in previous:
        if not isinstance(record, HistoricalEntry):
            raise ValueError("DP243_PREVIOUS_INVALID")
        _digest(record.source_version_sha256, "PREVIOUS_SOURCE_VERSION")
        _text(record.content_id, "PREVIOUS_CONTENT")
        old = before.get(record.content_id)
        if old is not None and _identity(old) != _identity(record):
            raise ValueError("DP243_PREVIOUS_CONTENT_CONFLICT")
        before[record.content_id] = record

    rows: list[HistoricalEntryDecision] = []
    changed: set[str] = set()
    for item in sorted(
        indexed.values(),
        key=lambda row: (("MUSSOLINI", "HITLER").index(row.subject), row.content_id),
    ):
        holds, receipts = _rights(item, now=clock)
        root_id: str | None = (
            item.content_id if item.source_kind == "PRIMARY_ORIGINAL" else None
        )
        if item.source_kind not in {"PRIMARY_ORIGINAL", "SECONDARY_SCHOLARSHIP"}:
            parent = indexed.get(item.origin_content_id or "")
            if (
                parent is None
                or parent.source_kind != "PRIMARY_ORIGINAL"
                or item.origin_content_id == item.content_id
                or parent.subject != item.subject
                or parent.source_version_sha256 != item.origin_sha256
                or (
                    item.source_kind == "EDITORIAL_TRANSLATION"
                    and parent.source_version_sha256 == item.source_version_sha256
                )
            ):
                holds.add("ORIGIN_UNVERIFIED")
            else:
                root_id = parent.content_id
                if item.source_kind == "EDITORIAL_TRANSLATION":
                    parent_holds, parent_receipts = _rights(
                        parent, now=clock, additional_use="TRANSLATE"
                    )
                    if parent_holds:
                        holds.add("PARENT_TRANSLATION_RIGHTS_UNVERIFIED")
                    receipts = tuple(sorted(set(receipts) | set(parent_receipts)))
                    if (
                        parent.original_language != "de"
                        or item.original_language != "it"
                        or item.edition_method is None
                        or item.edition_date is None
                    ):
                        holds.add("TRANSLATION_DERIVATION_UNVERIFIED")
                    if parent.event_at > item.observed_at or (
                        item.edition_date is not None
                        and (
                            item.edition_date < parent.event_at
                            or item.edition_date > item.observed_at
                        )
                    ):
                        holds.add("TRANSLATION_CHRONOLOGY_UNVERIFIED")
        if (
            item.source_kind == "SECONDARY_SCHOLARSHIP"
            and item.origin_content_id is not None
        ):
            holds.add("SCHOLARSHIP_ORIGIN_NOT_PRIMARY")
        if (
            item.attribution_role not in {"AUTHOR", "SPEAKER"}
            or not item.role_review_ref
        ):
            holds.add("SPEECH_ACT_UNVERIFIED")
        if (
            item.exact_locator is None
            or item.exact_locator.status != "LOCATED"
            or item.exact_locator.content_id != item.content_id
            or item.exact_locator.source_version_sha256 != item.source_version_sha256
            or item.exact_locator.locator_fingerprint != item.selector_fingerprint
        ):
            holds.add("EXACT_SOURCE_UNVERIFIED")
        old = before.get(item.content_id)
        if old is not None and old.source_version_sha256 != item.source_version_sha256:
            changed.add(item.content_id)
            if (
                item.supersedes_sha256 != old.source_version_sha256
                or item.rights_record_id == old.rights_record_id
                or item.observed_at <= old.observed_at
            ):
                holds.add("REVISION_UNVERIFIED")
            else:
                holds.add("REVISION_REVALIDATION_REQUIRED")
        elif item.supersedes_sha256 is not None:
            holds.add("SUPERSESSION_WITHOUT_BASE")
        rows.append(
            HistoricalEntryDecision(
                item.entry_id,
                item.content_id,
                item.source_version_sha256,
                root_id,
                item.source_kind,
                "HELD" if holds else "PRIVATE_REVIEW_ONLY",
                tuple(sorted(holds)),
                receipts,
                tuple(sorted(memberships[item.content_id])),
            )
        )

    # A derivative cannot acquire a clean review state from its own receipt
    # while the linked original is held for speaker, source, rights or revision.
    # Resolve this after all rows: content-id ordering can place a copy first.
    original_holds = {
        row.content_id: row.holds
        for row in rows
        if row.source_kind == "PRIMARY_ORIGINAL"
    }
    for index, row in enumerate(rows):
        if (
            row.source_kind in {"ARCHIVE_COPY", "EDITORIAL_TRANSLATION"}
            and row.root_content_id is not None
            and original_holds.get(row.root_content_id)
        ):
            rows[index] = replace(
                row,
                state="HELD",
                holds=tuple(sorted(set(row.holds) | {"PARENT_SOURCE_UNVERIFIED"})),
            )

    # The manifest fingerprint is an integrity tag for deterministic replay; it is
    # not a signature, a source authenticity attestation, or an authority token.
    material = {
        "version": VERSION,
        "manifests": [
            [
                m.subject,
                m.person_id,
                m.collection_id,
                _utc(m.coverage_start, "COVERAGE_START").isoformat(),
                _utc(m.coverage_horizon, "COVERAGE_HORIZON").isoformat(),
                m.coverage_scope_ref,
            ]
            for m in canonical
        ],
        "rows": [
            [
                row.entry_id,
                row.content_id,
                row.source_version_sha256,
                row.root_content_id,
                row.source_kind,
                row.state,
                row.holds,
                row.permission_fingerprints,
                row.collections,
            ]
            for row in rows
        ],
        "immutable_entries": [
            _source_material(item)
            for item in sorted(
                indexed.values(), key=lambda item: (item.subject, item.content_id)
            )
        ],
        "previous_source_versions": [
            asdict(item)
            for item in sorted(
                before.values(), key=lambda item: (item.subject, item.content_id)
            )
        ],
        "changes": sorted(changed),
    }
    missing_primary = tuple(
        subject
        for subject in SUBJECT_LANGUAGES
        if not any(
            item.subject == subject and item.source_kind == "PRIMARY_ORIGINAL"
            for item in indexed.values()
        )
    )
    return HistoricalCorpusPreflight(
        VERSION,
        _fingerprint(material),
        tuple(rows),
        tuple(sorted(indexed)),
        tuple(sorted(changed)),
        missing_primary,
    )


__all__ = [
    "VERSION",
    "MAX_ITEMS",
    "HistoricalEntry",
    "HistoricalManifest",
    "HistoricalEntryDecision",
    "HistoricalCorpusPreflight",
    "preflight_historical_corpus",
]
