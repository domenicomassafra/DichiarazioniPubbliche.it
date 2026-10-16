from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Any

from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord, PassageRecord
from dichiarazioni_pubbliche.corpus_retention import capture_downstream_use_decision


RESOLVING_RELATIONS = frozenset(
    {
        "REPUBLICATION",
        "SYNDICATION",
        "QUOTATION",
        "PRESS_RELEASE_DERIVED",
    }
)


@dataclass(frozen=True)
class DerivationEdge:
    edge_id: str
    family_id: str
    derived_content_id: str
    origin_content_id: str
    relation_type: str
    status: str = "CANDIDATE"

    def __post_init__(self) -> None:
        for name in (
            "edge_id",
            "family_id",
            "derived_content_id",
            "origin_content_id",
            "relation_type",
            "status",
        ):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"DERIVATION_EDGE_{name.upper()}_REQUIRED")
        if self.derived_content_id == self.origin_content_id:
            raise ValueError("DERIVATION_EDGE_SELF_REFUSED")


@dataclass(frozen=True)
class OriginalSourceResolution:
    content_id: str
    status: str
    root_content_id: str | None
    path_content_ids: tuple[str, ...]
    path_edge_ids: tuple[str, ...]
    blockers: tuple[str, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.status in {"SELF_ORIGINAL", "RESOLVED"}


def _edge_from_mapping(value: Mapping[str, Any] | DerivationEdge) -> DerivationEdge:
    if isinstance(value, DerivationEdge):
        return value
    return DerivationEdge(
        edge_id=str(value.get("id") or value.get("edge_id") or ""),
        family_id=str(value.get("family_id") or ""),
        derived_content_id=str(value.get("derived_content_id") or ""),
        origin_content_id=str(value.get("origin_content_id") or ""),
        relation_type=str(value.get("relation_type") or ""),
        status=str(value.get("status") or "CANDIDATE"),
    )


def resolve_original_source(
    content_id: str,
    edges: Iterable[Mapping[str, Any] | DerivationEdge],
    *,
    expected_family_id: str | None = None,
    family_root_content_id: str | None = None,
) -> OriginalSourceResolution:
    """Resolve an approved derivation chain to its original/root Content.

    Only already-approved derivation edges participate. The resolver never turns
    lexical/model similarity into provenance authority. Ambiguous roots, cycles,
    unknown-derivation-only paths, or an expected family root that cannot be reached
    fail closed.
    """

    start = str(content_id or "").strip()
    if not start:
        raise ValueError("ORIGINAL_SOURCE_CONTENT_REQUIRED")
    family_id = str(expected_family_id or "").strip() or None
    expected_root = str(family_root_content_id or "").strip() or None

    approved = []
    for raw in edges:
        edge = _edge_from_mapping(raw)
        if edge.status != "APPROVED":
            continue
        if family_id is not None and edge.family_id != family_id:
            continue
        approved.append(edge)

    by_derived: dict[str, list[DerivationEdge]] = {}
    for edge in approved:
        by_derived.setdefault(edge.derived_content_id, []).append(edge)

    current = start
    content_path = [start]
    edge_path: list[str] = []
    seen = {start}

    if expected_root == start:
        return OriginalSourceResolution(
            content_id=start,
            status="SELF_ORIGINAL",
            root_content_id=start,
            path_content_ids=(start,),
            path_edge_ids=(),
        )

    while True:
        candidates = by_derived.get(current, [])
        resolving = [e for e in candidates if e.relation_type in RESOLVING_RELATIONS]

        if not resolving:
            if candidates:
                return OriginalSourceResolution(
                    content_id=start,
                    status="UNRESOLVED",
                    root_content_id=None,
                    path_content_ids=tuple(content_path),
                    path_edge_ids=tuple(edge_path),
                    blockers=("UNKNOWN_DERIVATION_RELATION",),
                )
            if expected_root is not None and current != expected_root:
                return OriginalSourceResolution(
                    content_id=start,
                    status="UNRESOLVED",
                    root_content_id=None,
                    path_content_ids=tuple(content_path),
                    path_edge_ids=tuple(edge_path),
                    blockers=("EXPECTED_ROOT_NOT_REACHED",),
                )
            return OriginalSourceResolution(
                content_id=start,
                status="SELF_ORIGINAL" if current == start else "RESOLVED",
                root_content_id=current,
                path_content_ids=tuple(content_path),
                path_edge_ids=tuple(edge_path),
            )

        origins = {edge.origin_content_id for edge in resolving}
        if len(origins) != 1:
            return OriginalSourceResolution(
                content_id=start,
                status="UNRESOLVED",
                root_content_id=None,
                path_content_ids=tuple(content_path),
                path_edge_ids=tuple(edge_path),
                blockers=("CONFLICTING_APPROVED_ORIGINS",),
            )

        origin = next(iter(origins))
        selected = sorted(
            (edge for edge in resolving if edge.origin_content_id == origin),
            key=lambda edge: (edge.relation_type, edge.edge_id),
        )[0]

        if origin in seen:
            return OriginalSourceResolution(
                content_id=start,
                status="UNRESOLVED",
                root_content_id=None,
                path_content_ids=tuple(content_path + [origin]),
                path_edge_ids=tuple(edge_path + [selected.edge_id]),
                blockers=("DERIVATION_CYCLE",),
            )

        edge_path.append(selected.edge_id)
        content_path.append(origin)
        seen.add(origin)
        current = origin

        if expected_root is not None and current == expected_root:
            return OriginalSourceResolution(
                content_id=start,
                status="RESOLVED",
                root_content_id=current,
                path_content_ids=tuple(content_path),
                path_edge_ids=tuple(edge_path),
            )


def resolve_reviewed_original_source(
    content_id: str,
    *,
    families: Iterable[Mapping[str, Any]],
    edges: Iterable[Mapping[str, Any] | DerivationEdge],
) -> OriginalSourceResolution:
    """Resolve only when an approved derivation family establishes the root."""

    start = str(content_id or "").strip()
    if not start:
        raise ValueError("ORIGINAL_SOURCE_CONTENT_REQUIRED")
    approved_families = [
        dict(row)
        for row in families
        if str(row.get("status") or "") == "APPROVED"
    ]
    if not approved_families:
        return OriginalSourceResolution(
            content_id=start,
            status="UNRESOLVED",
            root_content_id=None,
            path_content_ids=(start,),
            path_edge_ids=(),
            blockers=("NO_APPROVED_DERIVATION_FAMILY",),
        )
    roots = {
        str(row.get("root_content_id") or "").strip()
        for row in approved_families
        if str(row.get("root_content_id") or "").strip()
    }
    if len(roots) != 1:
        return OriginalSourceResolution(
            content_id=start,
            status="UNRESOLVED",
            root_content_id=None,
            path_content_ids=(start,),
            path_edge_ids=(),
            blockers=("CONFLICTING_APPROVED_FAMILY_ROOTS",),
        )
    root = next(iter(roots))
    if start == root:
        return OriginalSourceResolution(
            content_id=start,
            status="SELF_ORIGINAL",
            root_content_id=root,
            path_content_ids=(start,),
            path_edge_ids=(),
        )
    return resolve_original_source(
        start,
        edges,
        family_root_content_id=root,
    )


# DP-237: an independent, private locator check. It does not mint a review
# event, approve an original-source relation, or grant publication rights.
EXACT_SOURCE_LOCATOR_VERSION = "exact-source-locator-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ExactSourceLocator:
    """A quote within one immutable Passage, in its original coordinate system.

    For TEXT_POSITION offsets are absolute in the parsed canonical text; for
    PAGE_RANGE they are within one PDF page; for MEDIA_SEGMENT_REF they are
    relative to the original transcript segment text, with full-segment time.
    Media locators must pin a nonempty speaker ID matching the observed segment.
    Mixed selectors and stitched spans are not supported.
    """

    content_id: str
    passage_id: str
    selector_type: str
    quote_start: int
    quote_end: int
    quote_sha256: str
    capture_id: str | None = None
    capture_sha256: str | None = None
    page_number: int | None = None
    canonical_segment_id: str | None = None
    transcript_variant_id: str | None = None
    transcript_variant_sha256: str | None = None
    source_segment_id: str | None = None
    source_segment_sha256: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    speaker_person_id: str | None = None
    locator_version: str = EXACT_SOURCE_LOCATOR_VERSION


@dataclass(frozen=True)
class ObservedMediaSegment:
    """Trusted private snapshot to validate a single transcript media selector.

    Source variant text and its character offsets are supplied by the caller;
    a segment timestamp is not a word-level timestamp or speaker approval.
    """

    content_id: str
    canonical_segment_id: str
    transcript_variant_id: str
    transcript_variant_sha256: str
    source_segment_id: str
    source_segment_sha256: str
    variant_text: str
    segment_text: str
    variant_start_char: int
    variant_end_char: int
    start_ms: int
    end_ms: int
    speaker_person_id: str | None = None


@dataclass(frozen=True)
class ExactSourceLocatorResolution:
    status: str  # LOCATED, STALE, UNAVAILABLE, BLOCKED
    blockers: tuple[str, ...]
    content_id: str
    passage_id: str
    selector_type: str
    source_version_sha256: str | None = None
    locator_fingerprint: str | None = None

    @property
    def located(self) -> bool:
        """The pinned source is verified; freshness is checked only if supplied."""
        return self.status == "LOCATED"


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_exact_source_locator(
    locator: ExactSourceLocator,
    *,
    passage: PassageRecord,
    quote_text: str,
    capture: ContentCaptureRecord | None = None,
    source_body: bytes | None = None,
    canonical_text: str | None = None,
    page_text: str | None = None,
    media_segment: ObservedMediaSegment | None = None,
    current_source_sha256: str | None = None,
) -> ExactSourceLocatorResolution:
    """Verify one private source locator against an observed immutable version.

    For written documents, the caller must independently reparse the verified
    source bytes to obtain canonical/page text using the recorded parser. For
    media, it must supply an independently observed transcript variant/segment.
    This checks their consistency; it cannot itself authenticate a parser,
    establish speaker identity, rights, or external player seek support.
    Supplying current_source_sha256 additionally checks freshness; otherwise
    LOCATED means pinned-version validity, not that this is the newest source.
    """
    def blocked(
        code: str, status: str = "BLOCKED", version_sha256: str | None = None,
    ) -> ExactSourceLocatorResolution:
        return ExactSourceLocatorResolution(
            status, (code,), locator.content_id, locator.passage_id, locator.selector_type,
            source_version_sha256=version_sha256,
        )

    if locator.locator_version != EXACT_SOURCE_LOCATOR_VERSION:
        return blocked("LOCATOR_VERSION_UNSUPPORTED")
    if (
        not all(isinstance(x, str) and bool(x) for x in
                (locator.content_id, locator.passage_id, locator.selector_type))
        or not _valid_hash(locator.quote_sha256)
        or type(locator.quote_start) is not int or type(locator.quote_end) is not int
        or locator.quote_start < 0 or locator.quote_end <= locator.quote_start
        or not isinstance(quote_text, str) or not quote_text
    ):
        return blocked("LOCATOR_QUOTE_INVALID")
    if (
        passage.id != locator.passage_id or passage.content_id != locator.content_id
        or passage.selector_type != locator.selector_type
    ):
        return blocked("LOCATOR_PASSAGE_SOURCE_MISMATCH")
    if current_source_sha256 is not None and not _valid_hash(current_source_sha256):
        return blocked("LOCATOR_CURRENT_VERSION_INVALID")

    source_version: str
    if locator.selector_type in {"TEXT_POSITION", "PAGE_RANGE"}:
        if (
            capture is None
            or capture.id != locator.capture_id
            or capture.content_id != locator.content_id
            or passage.capture_id != locator.capture_id
            or passage.canonical_segment_id is not None
            or not _valid_hash(locator.capture_sha256)
        ):
            return blocked("LOCATOR_CAPTURE_BINDING_MISMATCH")
        if locator.capture_sha256 != capture.content_sha256:
            return blocked("LOCATOR_CAPTURE_VERSION_MISMATCH")
        if (
            locator.canonical_segment_id is not None
            or any(x is not None for x in (
                locator.transcript_variant_id, locator.transcript_variant_sha256,
                locator.source_segment_id, locator.source_segment_sha256,
                locator.start_ms, locator.end_ms, locator.speaker_person_id,
            ))
        ):
            return blocked("LOCATOR_WRITTEN_MEDIA_FIELDS_FORBIDDEN")
        if (
            not capture.parser_method or not capture.parser_version
            or capture.parser_method != passage.extraction_method
            or capture.parser_version != passage.extraction_version
            or capture.metadata.get("parse_status") not in (None, "SUCCEEDED")
        ):
            return blocked("LOCATOR_PARSER_VERSION_MISMATCH")
        if capture.status == "PURGED_BODY" or capture.body_ref is None:
            return blocked("LOCATOR_BODY_UNAVAILABLE", "UNAVAILABLE", capture.content_sha256)
        # Byte/hash equality does not override a private Capture hold, active
        # quarantine or pending purge. Reuse the corpus lifecycle use gate,
        # without treating it as evidence of source rights or publication.
        if not capture_downstream_use_decision(capture, requires_body=True).allowed:
            return blocked("LOCATOR_CAPTURE_USE_BLOCKED", version_sha256=capture.content_sha256)
        if not isinstance(source_body, bytes):
            return blocked("LOCATOR_BODY_UNAVAILABLE", "UNAVAILABLE", capture.content_sha256)
        if hashlib.sha256(source_body).hexdigest() != capture.content_sha256:
            return blocked("LOCATOR_SOURCE_BYTES_CHANGED")
        if (
            not isinstance(passage.private_text, str)
            or _hash_text(passage.private_text) != passage.text_sha256
        ):
            return blocked("LOCATOR_PASSAGE_TEXT_CHANGED")
        if locator.selector_type == "TEXT_POSITION":
            if (
                locator.page_number is not None
                or passage.start_char is None or passage.end_char is None
                or passage.page_start is not None or passage.page_end is not None
                or not isinstance(canonical_text, str)
                or any(x is not None for x in (page_text, media_segment))
                or type(passage.start_char) is not int or type(passage.end_char) is not int
                or passage.start_char < 0 or passage.end_char > len(canonical_text)
                or canonical_text[passage.start_char:passage.end_char] != passage.private_text
                or not (passage.start_char <= locator.quote_start
                        < locator.quote_end <= passage.end_char)
            ):
                return blocked("LOCATOR_TEXT_SELECTOR_INVALID")
            observed_quote = canonical_text[locator.quote_start:locator.quote_end]
        else:
            # One-page quotes only: a PAGE_RANGE spanning multiple pages has no
            # precise quotation boundary without separate page-level passages.
            if (
                not isinstance(page_text, str) or canonical_text is not None
                or media_segment is not None or capture.media_type != "application/pdf"
                or type(locator.page_number) is not int or locator.page_number < 1
                or type(passage.page_start) is not int
                or type(passage.page_end) is not int
                or passage.start_char is not None or passage.end_char is not None
                or passage.page_start != locator.page_number
                or passage.page_end != locator.page_number
                # PAGE_RANGE needs independently recorded PDF page count; a
                # fabricated page index is otherwise indistinguishable.
                or type(capture.metadata.get("page_count")) is not int
                or capture.metadata["page_count"] < locator.page_number
                or page_text != passage.private_text
                or locator.quote_end > len(page_text)
            ):
                return blocked("LOCATOR_PAGE_SELECTOR_INVALID")
            observed_quote = page_text[locator.quote_start:locator.quote_end]
        source_version = capture.content_sha256
    elif locator.selector_type == "MEDIA_SEGMENT_REF":
        if (
            capture is not None or source_body is not None
            or canonical_text is not None or page_text is not None
            or media_segment is None or locator.capture_id is not None
            or locator.capture_sha256 is not None or locator.page_number is not None
            or passage.capture_id is not None
            or passage.canonical_segment_id != locator.canonical_segment_id
            or any(x is not None for x in (
                passage.start_char, passage.end_char,
                passage.page_start, passage.page_end,
            ))
        ):
            return blocked("LOCATOR_MEDIA_SOURCE_MISMATCH")
        segment = media_segment
        if (
            segment.content_id != locator.content_id
            or segment.canonical_segment_id != locator.canonical_segment_id
            or segment.transcript_variant_id != locator.transcript_variant_id
            or segment.source_segment_id != locator.source_segment_id
            or not _valid_hash(locator.transcript_variant_sha256)
            or not _valid_hash(locator.source_segment_sha256)
            or segment.transcript_variant_sha256 != locator.transcript_variant_sha256
            or segment.source_segment_sha256 != locator.source_segment_sha256
        ):
            return blocked("LOCATOR_MEDIA_VERSION_MISMATCH")
        if (
            not isinstance(segment.variant_text, str)
            or not isinstance(segment.segment_text, str)
            or _hash_text(segment.variant_text) != segment.transcript_variant_sha256
            or _hash_text(segment.segment_text) != segment.source_segment_sha256
            or _hash_text(segment.segment_text) != passage.text_sha256
            or (passage.private_text is not None and passage.private_text != segment.segment_text)
            or type(segment.variant_start_char) is not int
            or type(segment.variant_end_char) is not int
            or segment.variant_start_char < 0
            or segment.variant_end_char <= segment.variant_start_char
            or segment.variant_end_char > len(segment.variant_text)
            or segment.variant_text[segment.variant_start_char:segment.variant_end_char]
            != segment.segment_text
        ):
            return blocked("LOCATOR_MEDIA_TEXT_MISMATCH")
        if (
            type(segment.start_ms) is not int or type(segment.end_ms) is not int
            or type(locator.start_ms) is not int or type(locator.end_ms) is not int
            or segment.start_ms < 0 or segment.end_ms <= segment.start_ms
            or locator.start_ms != segment.start_ms or locator.end_ms != segment.end_ms
            or locator.quote_end > len(segment.segment_text)
        ):
            return blocked("LOCATOR_MEDIA_TIME_OR_RANGE_MISMATCH")
        if (
            not isinstance(locator.speaker_person_id, str)
            or not locator.speaker_person_id.strip()
            or locator.speaker_person_id != segment.speaker_person_id
        ):
            return blocked("LOCATOR_MEDIA_SPEAKER_MISMATCH")
        observed_quote = segment.segment_text[locator.quote_start:locator.quote_end]
        source_version = segment.transcript_variant_sha256
    else:
        return blocked("LOCATOR_SELECTOR_UNSUPPORTED")

    if observed_quote != quote_text or _hash_text(observed_quote) != locator.quote_sha256:
        return blocked("LOCATOR_QUOTE_SPAN_MISMATCH")

    fingerprint = hashlib.sha256(
        json.dumps(
            {"version": EXACT_SOURCE_LOCATOR_VERSION, "locator": asdict(locator)},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if current_source_sha256 is not None and current_source_sha256 != source_version:
        return ExactSourceLocatorResolution(
            "STALE", ("LOCATOR_NEWER_SOURCE_VERSION",), locator.content_id,
            locator.passage_id, locator.selector_type, source_version, fingerprint,
        )
    return ExactSourceLocatorResolution(
        "LOCATED", (), locator.content_id, locator.passage_id,
        locator.selector_type, source_version, fingerprint,
    )


__all__ = [
    "DerivationEdge",
    "EXACT_SOURCE_LOCATOR_VERSION",
    "ExactSourceLocator",
    "ExactSourceLocatorResolution",
    "ObservedMediaSegment",
    "OriginalSourceResolution",
    "RESOLVING_RELATIONS",
    "resolve_exact_source_locator",
    "resolve_original_source",
    "resolve_reviewed_original_source",
]
