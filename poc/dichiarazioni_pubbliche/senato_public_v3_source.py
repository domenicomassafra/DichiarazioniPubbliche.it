"""DP-468: pinned Senato AKN source -> fail-closed Statement v3 producer seam.

This is a read-only ProjectionSource adapter, not a rights, identity, agent
review, challenge or release authority. Callers must provide separate live,
authenticated readers for each; an absent reader never fabricates a receipt.
The existing public_projection builder independently checks all five lanes and
the autonomous two-model gate before emitting any Statement.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping
from .private_capture_rights import SourceUseBlocked

from .senato_akoma_corpus_handoff import _canonical_document
from .senato_akoma_stenographic import import_senato_akoma_stenographic

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_CANDIDATE_KEYS = frozenset({
    "statement_id", "version_id", "status", "content_id", "source_version",
    "speech_id", "official_person_uri", "person_id", "speaker_name",
    "start_char", "end_char",
})
_MAX_CANDIDATES = 32


@dataclass(frozen=True)
class PinnedSenatoV3Source:
    content_id: str
    source_raw_url: str
    xml_sha256: str
    git_blob_sha1: str
    canonical_text_sha256: str

    def __post_init__(self) -> None:
        if (not isinstance(self.content_id, str) or not self.content_id.strip()
                or not isinstance(self.xml_sha256, str)
                or _SHA256.fullmatch(self.xml_sha256) is None
                or not isinstance(self.git_blob_sha1, str)
                or _SHA1.fullmatch(self.git_blob_sha1) is None
                or not isinstance(self.canonical_text_sha256, str)
                or _SHA256.fullmatch(self.canonical_text_sha256) is None):
            raise ValueError("DP468_SOURCE_PINS_REQUIRED")


class CurrentSenatoCaptureBytes:
    """Concrete read-only bridge to current Capture, body and private-use guard.

    The guard uses the existing revocable, exact-subject private rights record
    for PARSE_TEXT. This allows inspecting bytes, NEVER public quotation.
    """

    def __init__(self, pins: PinnedSenatoV3Source, *, capture_store: object,
                 body_store: object, private_source_guard: object):
        if (not isinstance(pins, PinnedSenatoV3Source)
                or not callable(getattr(capture_store, "find_capture", None))
                or not callable(getattr(body_store, "read", None))
                or not callable(getattr(private_source_guard, "require", None))
                or not callable(getattr(private_source_guard, "bind_capture", None))):
            raise ValueError("DP468_TRUSTED_CAPTURE_READER_REQUIRED")
        self.pins = pins
        self.capture_store = capture_store
        self.body_store = body_store
        self.private_source_guard = private_source_guard

    def __call__(self) -> bytes:
        if getattr(self.private_source_guard.subject, "source_family", None) != "senato_open_data_akn":
            raise SourceUseBlocked("DP468_SENATO_SOURCE_FAMILY_MISMATCH")
        self.private_source_guard.bind_capture(
            content_id=self.pins.content_id, url=self.pins.source_raw_url,
        )
        self.private_source_guard.require("PARSE_TEXT", content_sha256=self.pins.xml_sha256)
        row = self.capture_store.find_capture(self.pins.content_id, self.pins.xml_sha256)
        if (not isinstance(row, dict)
                or row.get("content_id") != self.pins.content_id
                or row.get("content_sha256") != self.pins.xml_sha256
                or row.get("final_url") != self.pins.source_raw_url
                or row.get("status") != "CAPTURED"
                or row.get("hold_status") != "NONE"
                or row.get("rights_status") != "CLEARED"
                or row.get("body_purged_at") is not None
                or not isinstance(row.get("body_ref"), str)
                or not row["body_ref"]):
            raise ValueError("DP468_CURRENT_CAPTURE_UNAVAILABLE")
        body = self.body_store.read(
            row["body_ref"], expected_sha256=self.pins.xml_sha256,
            max_bytes=3_000_000,
        )
        self.private_source_guard.require("PARSE_TEXT", content_sha256=self.pins.xml_sha256)
        current = self.capture_store.find_capture(self.pins.content_id, self.pins.xml_sha256)
        if current != row:
            raise ValueError("DP468_CAPTURE_CHANGED_DURING_READ")
        return body


class SenatoPublicV3Source:
    """Read a real immutable XML and delegate authority to independent stores.

    `read_original_bytes` must recheck the current authorized Capture on each
    call. `read_current_candidates` must replay the live approved candidate
    status and identity, not accept an operator's in-memory JSON as authority.
    The three optional review/challenge readers intentionally default to
    unavailable: they can only be wired to real persistent authorities.
    """

    def __init__(
        self,
        pins: PinnedSenatoV3Source,
        *,
        read_original_bytes: Callable[[], bytes],
        read_current_candidates: Callable[[], Iterable[Mapping[str, Any]]] | None = None,
        read_current_attestations: Callable[[str, str], dict[str, Any] | None] | None = None,
        read_current_autonomous_evidence: Callable[[str, str], object] | None = None,
        read_current_challenge_hold: Callable[[str, str], bool | None] | None = None,
    ) -> None:
        if not isinstance(pins, PinnedSenatoV3Source) or not callable(read_original_bytes):
            raise ValueError("DP468_TRUSTED_CAPTURE_READER_REQUIRED")
        for reader in (
            read_current_candidates, read_current_attestations,
            read_current_autonomous_evidence, read_current_challenge_hold,
        ):
            if reader is not None and not callable(reader):
                raise ValueError("DP468_AUTHORITY_READER_INVALID")
        self.pins = pins
        self._read_bytes = read_original_bytes
        self._candidates = read_current_candidates
        self._attestations = read_current_attestations
        self._autonomous = read_current_autonomous_evidence
        self._challenges = read_current_challenge_hold

    def _source(self) -> tuple[str, dict[str, tuple[str, int, int]], str]:
        raw = self._read_bytes()
        if (not isinstance(raw, bytes)
                or hashlib.sha256(raw).hexdigest() != self.pins.xml_sha256):
            raise ValueError("DP468_IMMUTABLE_XML_MISMATCH")
        imported = import_senato_akoma_stenographic(
            raw, source_raw_url=self.pins.source_raw_url,
            expected_blob_sha1=self.pins.git_blob_sha1,
        )
        canonical, spans, _, included = _canonical_document(imported)
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != self.pins.canonical_text_sha256:
            raise ValueError("DP468_CANONICAL_TEXT_MISMATCH")
        speeches: dict[str, tuple[str, int, int]] = {}
        for speech, indexes in included:
            if indexes:
                speeches[speech.speech_id] = (
                    speech.official_person_uri,
                    spans[indexes[0]].start_char,
                    spans[indexes[-1]].end_char,
                )
        return canonical, speeches, imported.sitting_date

    def projectable_findings(self) -> list[dict[str, Any]]:
        # No authority to migrate v2 Findings from private corpus.
        return []

    def projectable_public_statements(self) -> list[dict[str, Any]]:
        if self._candidates is None:
            return []
        canonical, speeches, date = self._source()
        observed = self._candidates()
        if not isinstance(observed, (list, tuple)) or len(observed) > _MAX_CANDIDATES:
            raise ValueError("DP468_CANDIDATE_REPLAY_INVALID")
        rows: list[dict[str, Any]] = []
        identifiers: set[str] = set()
        conflicted: set[str] = set()
        for record in observed:
            if not isinstance(record, Mapping) or set(record) != _CANDIDATE_KEYS:
                continue
            if record["status"] != "APPROVED":
                continue
            if (record["content_id"] != self.pins.content_id
                    or record["source_version"] != self.pins.xml_sha256):
                continue
            span = speeches.get(record["speech_id"])
            start, end = record["start_char"], record["end_char"]
            if (span is None or span[0] != record["official_person_uri"]
                    or type(start) is not int or type(end) is not int
                    or not span[1] <= start < end <= span[2]):
                continue
            for key in ("statement_id", "version_id", "person_id", "speaker_name"):
                if not isinstance(record[key], str) or not record[key].strip():
                    break
            else:
                identifier = record["statement_id"]
                if identifier in identifiers:
                    conflicted.add(identifier)
                identifiers.add(identifier)
                quote = canonical[start:end]
                if not quote.strip() or len(quote) > 300:
                    continue
                rows.append({
                    "statement_id": identifier,
                    "version_id": record["version_id"],
                    "person_id": record["person_id"],
                    "speaker_name": record["speaker_name"],
                    "content_id": self.pins.content_id,
                    "source_title": f"Resoconto stenografico Senato {date}",
                    "source_url": self.pins.source_raw_url,
                    "source_version": self.pins.xml_sha256,
                    "source_sha256": self.pins.canonical_text_sha256,
                    "original_text": quote,
                    "language": "it",
                    "statement_date": date,
                    "source_kind": "WRITTEN",
                    "locator": {"start_char": start, "end_char": end},
                    "finding_id": None,
                    "summary": None,
                    "translation": None,
                })
        return [row for row in rows if row["statement_id"] not in conflicted]

    def get_statement_source_text(self, content_id: str, source_version: str) -> str:
        if (content_id != self.pins.content_id
                or source_version != self.pins.xml_sha256):
            raise ValueError("DP468_SOURCE_VERSION_NOT_CURRENT")
        canonical, _, _ = self._source()
        return canonical

    def statement_publication_attestations(
        self, statement_id: str, version_id: str,
    ) -> dict[str, Any] | None:
        if self._attestations is None:
            return None
        return self._attestations(statement_id, version_id)

    def autonomous_publication_evidence(self, statement_id: str, version_id: str) -> object:
        if self._autonomous is None:
            return None
        return self._autonomous(statement_id, version_id)

    def current_statement_challenge_hold(self, statement_id: str, version_id: str) -> bool | None:
        if self._challenges is None:
            return None
        return self._challenges(statement_id, version_id)
