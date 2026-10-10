"""DP-233: official Senato AKN -> canonical private Capture/Passage/Candidate seam.

This hook is usable by ``capture_content(..., parser=SenatoAkomaParser(...))``
after the existing authorization/rights permit has been established.  The
standalone preparation path builds genuine corpus record contracts but never
writes operational tables, stores an unapproved body, resolves Person identities,
or changes the source registry.  A prepared statement is HELD for human review.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from dichiarazioni_pubbliche.capture_pipeline import (
    MAX_PASSAGE_CHARS,
    MAX_PASSAGES,
    ParseResult,
    ParsedSpan,
)
from dichiarazioni_pubbliche.corpus_repository import (
    ContentCaptureRecord,
    PassageRecord,
    StatementCandidateRecord,
    deterministic_corpus_id,
)
from dichiarazioni_pubbliche.senato_akoma_stenographic import (
    ADAPTER_VERSION,
    SenatoAkomaCandidateImport,
    SenatoAkomaError,
    SenatoAkomaHeldSpeech,
    import_senato_akoma_stenographic,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes


@dataclass(frozen=True)
class SenatoCorpusHandoff:
    capture: ContentCaptureRecord
    passages: tuple[PassageRecord, ...]
    statements: tuple[StatementCandidateRecord, ...]
    canonical_text_sha256: str
    held_speeches: tuple[SenatoAkomaHeldSpeech, ...]
    source: SenatoAkomaCandidateImport
    claim_extraction_status: str = "BLOCKED_PENDING_PRIVATE_RIGHTS_AND_PROVIDER"


def verify_senato_handoff_roundtrip(
    prepared: SenatoCorpusHandoff, xml_bytes: bytes
) -> None:
    """Readback verifier for held records against their pinned immutable bytes.

    Rebuild independently from source, then compare the complete canonical
    contracts. Modified text, selectors, IDs, rights status, source URL,
    publication flags or speaker resolution may never pass replay unchanged.
    """
    if not isinstance(prepared, SenatoCorpusHandoff):
        raise SenatoAkomaError("SENATO_AKN_HANDOFF_INVALID")
    rebuilt = prepare_senato_corpus_handoff(
        xml_bytes, source_raw_url=prepared.source.source_raw_url,
        expected_blob_sha1=prepared.source.source_blob_sha1,
        content_id=prepared.capture.content_id,
        observed_at=prepared.capture.observed_at,
    )
    if rebuilt != prepared:
        raise SenatoAkomaError("SENATO_AKN_HANDOFF_SOURCE_ROUNDTRIP_MISMATCH")


def _canonical_document(source: SenatoAkomaCandidateImport) -> tuple[str, tuple[ParsedSpan, ...], tuple[SenatoAkomaHeldSpeech, ...]]:
    pieces: list[str] = []
    spans: list[ParsedSpan] = []
    extra_holds: list[SenatoAkomaHeldSpeech] = []
    offset = 0
    for speech in source.speeches:
        review = speech.review_text
        if len(review) > MAX_PASSAGE_CHARS or len(spans) >= MAX_PASSAGES:
            extra_holds.append(SenatoAkomaHeldSpeech(speech.ordinal, "CANONICAL_PASSAGE_LIMIT", speech.source_speaker_ref))
            continue
        if pieces:
            pieces.append("\n\n")
            offset += 2
        pieces.append(review)
        spans.append(ParsedSpan(
            start_char=offset, end_char=offset + len(review), text=review,
            text_sha256=speech.review_text_sha256,
        ))
        offset += len(review)
    return "".join(pieces), tuple(spans), source.held_speeches + tuple(extra_holds)


class SenatoAkomaParser:
    """CapturePipeline.ParserAdapter for exact raw AKN source/commit/blob receipts."""

    parser_method = "OFFICIAL_SENATO_AKOMA_STENOGRAPHIC"
    parser_version = ADAPTER_VERSION

    def __init__(self, *, source_raw_url: str, expected_blob_sha1: str):
        self.source_raw_url = source_raw_url
        self.expected_blob_sha1 = expected_blob_sha1

    def parse(self, fetched: FetchedBytes) -> ParseResult:
        try:
            if fetched.final_url != self.source_raw_url:
                raise SenatoAkomaError("SENATO_AKN_SOURCE_REDIRECT_MISMATCH")
            if fetched.media_type not in {
                "application/xml", "text/xml", "application/akn+xml", "text/plain",
                "application/octet-stream",
            }:
                raise SenatoAkomaError("SENATO_AKN_MEDIA_TYPE_UNSUPPORTED")
            source = import_senato_akoma_stenographic(
                fetched.body,
                source_raw_url=self.source_raw_url,
                expected_blob_sha1=self.expected_blob_sha1,
            )
            canonical, spans, held = _canonical_document(source)
            if not spans:
                raise SenatoAkomaError("SENATO_AKN_NO_REVIEWABLE_PASSAGES")
            return ParseResult(
                status="SUCCEEDED", parser_method=self.parser_method,
                parser_version=self.parser_version,
                canonical_text=canonical, spans=spans,
                metadata={
                    "official_source_repository": "SenatoDellaRepubblica/AkomaNtosoBulkData",
                    "immutable_source_url": source.source_raw_url,
                    "source_commit_sha": source.source_commit_sha,
                    "source_blob_sha1": source.source_blob_sha1,
                    "source_sha256": source.source_sha256,
                    "source_license_id": source.source_license_id,
                    "source_license_url": source.source_license_url,
                    "source_rights_decision": source.source_rights_decision,
                    "speaker_and_quote_approval": "NOT_GRANTED",
                    "accepted_passage_count": len(spans),
                    "held_speech_count": len(held),
                },
            )
        except SenatoAkomaError as exc:
            return ParseResult(
                status="FAILED", parser_method=self.parser_method,
                parser_version=self.parser_version, error_category=str(exc),
            )


def prepare_senato_corpus_handoff(
    xml_bytes: bytes, *, source_raw_url: str, expected_blob_sha1: str,
    content_id: str, observed_at: str,
) -> SenatoCorpusHandoff:
    """Prepare held canonical records, with replayable actual byte-to-span checks.

    The Content identity is supplied by the authorized source registry. The
    function intentionally does not assert that Content is registered/persisted.
    Calling ``capture_content`` with this parser remains subject to the normal
    source rights, discovery and acquisition permit gates.
    """
    source = import_senato_akoma_stenographic(
        xml_bytes, source_raw_url=source_raw_url,
        expected_blob_sha1=expected_blob_sha1,
    )
    if not isinstance(observed_at, str):
        raise ValueError("SENATO_HANDOFF_OBSERVATION_REQUIRED")
    try:
        stamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("SENATO_HANDOFF_OBSERVATION_INVALID") from None
    if stamp.tzinfo is None:
        raise ValueError("SENATO_HANDOFF_OBSERVATION_TIMEZONE_REQUIRED")
    canonical, spans, held = _canonical_document(source)
    if not spans:
        raise SenatoAkomaError("SENATO_AKN_NO_REVIEWABLE_PASSAGES")
    parsed = SenatoAkomaParser(
        source_raw_url=source_raw_url, expected_blob_sha1=expected_blob_sha1
    ).parse(FetchedBytes(
        body=xml_bytes, final_url=source_raw_url, status_code=200,
        media_type="application/akn+xml", charset="utf-8",
        content_length=len(xml_bytes),
    ))
    if (parsed.status != "SUCCEEDED" or parsed.canonical_text != canonical
            or parsed.spans != spans or parsed.metadata.get("source_sha256") != source.source_sha256):
        raise SenatoAkomaError("SENATO_AKN_CANONICAL_SOURCE_BINDING_FAILED")
    capture_id = deterministic_corpus_id("capture", content_id, source.source_sha256)
    capture = ContentCaptureRecord(
        id=capture_id, content_id=content_id, observed_at=observed_at,
        final_url=source.source_raw_url, content_sha256=source.source_sha256,
        retrieval_method="OFFICIAL_GIT_BLOB_IN_MEMORY",
        retrieval_version=ADAPTER_VERSION, media_type="application/akn+xml",
        body_ref=None, parser_method=SenatoAkomaParser.parser_method,
        parser_version=ADAPTER_VERSION, rights_status="UNKNOWN",
        retention_class="POLICY_PENDING", hold_status="RIGHTS_HOLD",
        status="QUARANTINED",
        metadata={
            "source_commit_sha": source.source_commit_sha,
            "source_blob_sha1": source.source_blob_sha1,
            "source_license_id": source.source_license_id,
            "source_license_url": source.source_license_url,
            "canonical_text_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "source_rights_decision": source.source_rights_decision,
            "held_speech_count": len(held),
            "source_sitting_id": source.sitting_id,
            "content_registry_approval": "UNVERIFIED",
        },
    )
    included = [speech for speech in source.speeches if len(speech.review_text) <= MAX_PASSAGE_CHARS]
    included = included[:MAX_PASSAGES]
    passages: list[PassageRecord] = []
    statements: list[StatementCandidateRecord] = []
    for speech, span in zip(included, spans, strict=True):
        passage_id = deterministic_corpus_id(
            "passage", capture_id, ADAPTER_VERSION,
            str(span.start_char), str(span.end_char), span.text_sha256,
        )
        passage = PassageRecord(
            id=passage_id, content_id=content_id, capture_id=capture_id,
            selector_type="TEXT_POSITION", start_char=span.start_char,
            end_char=span.end_char, text_sha256=span.text_sha256,
            private_text=span.text, language="it",
            extraction_method=SenatoAkomaParser.parser_method,
            extraction_version=ADAPTER_VERSION,
            metadata={"source_speech_id": speech.speech_id, "source_speech_ordinal": speech.ordinal,
                      "source_review_text_only": True},
        )
        if (parsed.canonical_text[passage.start_char:passage.end_char] != passage.private_text
                or hashlib.sha256(passage.private_text.encode("utf-8")).hexdigest()
                != passage.text_sha256):
            raise SenatoAkomaError("SENATO_AKN_PASSAGE_SOURCE_BINDING_FAILED")
        passages.append(passage)
        statements.append(StatementCandidateRecord(
            id=deterministic_corpus_id("statement-candidate", passage_id, speech.speech_id),
            content_id=content_id, passage_ids=(passage_id,),
            statement_text_hash=speech.review_text_sha256,
            normalized_statement=speech.review_text,
            extraction_version=ADAPTER_VERSION, speaker_person_id=None,
            attribution_method=None, status="HELD",
            metadata={
                "source_speech_id": speech.speech_id,
                "source_speaker_ref": speech.source_speaker_ref,
                "source_official_person_uri": speech.official_person_uri,
                "speaker_resolution_status": "NOT_APPROVED",
                "quote_review_status": "UNREVIEWED_NORMALIZED_XML_TEXT",
                "source_content_sha256": source.source_sha256,
            },
        ))
    return SenatoCorpusHandoff(
        capture=capture, passages=tuple(passages), statements=tuple(statements),
        canonical_text_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        held_speeches=held, source=source,
    )
