"""Private DP-217/DP-220 review provenance for exact source spans.

The ledgers in this module are review evidence, not publication authority. Transcript
reviews preserve the immutable machine/provider variant and create a derived in-memory
``HUMAN_AUDIO_VERIFIED`` candidate only from a current APPROVED review. Context reviews
store hashes and offsets only; surrounding source text is never copied into the ledger.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from dichiarazioni_pubbliche.context_integrity import ContextIntegrityAssessment
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.transcript_contract import TranscriptCandidate


TRANSCRIPT_VERBATIM_REVIEW_VERSION = "transcript-verbatim-review-v1"
CONTEXT_INTEGRITY_REVIEW_VERSION = "context-integrity-review-v1"
_CODE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{0,127}$")


class SourceSpanReviewError(ValueError):
    pass


@dataclass(frozen=True)
class TranscriptVerbatimReview:
    id: str
    content_id: str
    source_variant_id: str
    source_segment_id: str
    source_variant_sha256: str
    source_segment_sha256: str
    start_ms: int
    end_ms: int
    reviewed_text: str
    reviewed_text_sha256: str
    decision: str
    reviewer_ref: str
    reason_codes: tuple[str, ...]
    review_version: str = TRANSCRIPT_VERBATIM_REVIEW_VERSION

    def as_transcript_candidate(self) -> TranscriptCandidate:
        if self.decision != "APPROVED":
            raise SourceSpanReviewError("TRANSCRIPT_REVIEW_NOT_APPROVED")
        return TranscriptCandidate(
            candidate_id=self.id,
            provider_id="human-audio-review",
            text=self.reviewed_text,
            start_ms=self.start_ms,
            end_ms=self.end_ms,
            source_kind="HUMAN_AUDIO_VERIFIED",
        )


@dataclass(frozen=True)
class ContextIntegrityReview:
    id: str
    record_id: str
    source_sha256: str
    quote_sha256: str
    context_sha256: str
    quote_start: int
    quote_end: int
    context_start: int
    context_end: int
    signal_codes: tuple[str, ...]
    decision: str
    reviewer_ref: str
    reason_codes: tuple[str, ...]
    review_version: str = CONTEXT_INTEGRITY_REVIEW_VERSION


@dataclass(frozen=True)
class ReviewFreshness:
    current: bool
    blockers: tuple[str, ...]


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _text(value: object, field: str, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or "\x00" in text:
        raise SourceSpanReviewError(f"SOURCE_SPAN_REVIEW_{field}_INVALID")
    return text


def _body_text(value: object, field: str, maximum: int) -> str:
    text = str(value or "")
    if not text.strip() or len(text) > maximum or "\x00" in text:
        raise SourceSpanReviewError(f"SOURCE_SPAN_REVIEW_{field}_INVALID")
    return text


def _sha256(value: object, field: str) -> str:
    text = _text(value, field, 64).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise SourceSpanReviewError(f"SOURCE_SPAN_REVIEW_{field}_INVALID")
    return text


def _decision(value: object) -> str:
    decision = _text(value, "DECISION", 16).upper()
    if decision not in {"APPROVED", "REJECTED"}:
        raise SourceSpanReviewError("SOURCE_SPAN_REVIEW_DECISION_INVALID")
    return decision


def _codes(values: Iterable[object], field: str) -> tuple[str, ...]:
    result: list[str] = []
    for raw in values:
        code = _text(raw, field, 128).upper()
        if not _CODE.fullmatch(code):
            raise SourceSpanReviewError(f"SOURCE_SPAN_REVIEW_{field}_INVALID")
        if code not in result:
            result.append(code)
    if len(result) > 32:
        raise SourceSpanReviewError(f"SOURCE_SPAN_REVIEW_{field}_TOO_MANY")
    return tuple(sorted(result))


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _deterministic_id(prefix: str, payload: Mapping[str, object]) -> str:
    digest = hashlib.sha256(_stable_json(dict(payload)).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def transcript_review_freshness(
    review: TranscriptVerbatimReview,
    *,
    source_variant_sha256: str,
    source_segment_sha256: str,
    start_ms: int,
    end_ms: int,
) -> ReviewFreshness:
    blockers: list[str] = []
    if review.decision != "APPROVED":
        blockers.append("TRANSCRIPT_REVIEW_NOT_APPROVED")
    if _sha256(source_variant_sha256, "SOURCE_VARIANT_SHA256") != review.source_variant_sha256:
        blockers.append("TRANSCRIPT_SOURCE_VERSION_CHANGED")
    if _sha256(source_segment_sha256, "SOURCE_SEGMENT_SHA256") != review.source_segment_sha256:
        blockers.append("TRANSCRIPT_SOURCE_SEGMENT_CHANGED")
    if int(start_ms) != review.start_ms or int(end_ms) != review.end_ms:
        blockers.append("TRANSCRIPT_REVIEW_RANGE_CHANGED")
    normalized = tuple(dict.fromkeys(blockers))
    return ReviewFreshness(not normalized, normalized)


def context_review_freshness(
    review: ContextIntegrityReview,
    current: ContextIntegrityAssessment | Mapping[str, object],
) -> ReviewFreshness:
    values = current.to_metadata() if isinstance(current, ContextIntegrityAssessment) else dict(current)
    blockers: list[str] = []
    if review.decision != "APPROVED":
        blockers.append("CONTEXT_REVIEW_NOT_APPROVED")
    comparisons = (
        ("source_sha256", "CONTEXT_SOURCE_CHANGED"),
        ("quote_sha256", "CONTEXT_QUOTE_CHANGED"),
        ("context_sha256", "CONTEXT_WINDOW_CHANGED"),
        ("quote_start", "CONTEXT_QUOTE_RANGE_CHANGED"),
        ("quote_end", "CONTEXT_QUOTE_RANGE_CHANGED"),
        ("context_start", "CONTEXT_WINDOW_RANGE_CHANGED"),
        ("context_end", "CONTEXT_WINDOW_RANGE_CHANGED"),
    )
    for key, blocker in comparisons:
        expected = getattr(review, key)
        actual = values.get(key)
        if key.endswith("sha256"):
            try:
                actual = _sha256(actual, key.upper())
            except SourceSpanReviewError:
                actual = None
        else:
            try:
                actual = int(actual) if actual is not None else None
            except (TypeError, ValueError):
                actual = None
        if actual != expected:
            blockers.append(blocker)
    normalized = tuple(dict.fromkeys(blockers))
    return ReviewFreshness(not normalized, normalized)


class SourceSpanReviewStore(PsqlRuntime):
    def record_transcript_review(
        self,
        *,
        content_id: str,
        source_variant_id: str,
        source_segment_id: str,
        start_ms: int,
        end_ms: int,
        reviewed_text: str,
        decision: str,
        reviewer_ref: str,
        reason_codes: Iterable[object] = (),
    ) -> TranscriptVerbatimReview:
        content = _text(content_id, "CONTENT_ID", 512)
        variant = _text(source_variant_id, "SOURCE_VARIANT_ID", 512)
        segment = _text(source_segment_id, "SOURCE_SEGMENT_ID", 512)
        reviewer = _text(reviewer_ref, "REVIEWER_REF", 512)
        reviewed = _body_text(reviewed_text, "REVIEWED_TEXT", 200000)
        action = _decision(decision)
        reasons = _codes(reason_codes, "REASON_CODE")
        start = int(start_ms)
        end = int(end_ms)
        if start < 0 or end <= start:
            raise SourceSpanReviewError("SOURCE_SPAN_REVIEW_RANGE_INVALID")

        raw = self.run(
            """
            SELECT COALESCE(json_build_object(
                'content_id', variant.content_id,
                'source_variant_sha256', variant.raw_text_sha256,
                'source_segment_text', segment.text,
                'segment_start_ms', segment.start_ms,
                'segment_end_ms', segment.end_ms
            )::text, '')
            FROM transcript_segment segment
            JOIN transcript_variant variant ON variant.id=segment.variant_id
            WHERE variant.id=:'variant_id'
              AND segment.id=:'segment_id'
              AND variant.content_id=:'content_id';
            """,
            variant_id=variant,
            segment_id=segment,
            content_id=content,
        )
        if not raw:
            raise SourceSpanReviewError("TRANSCRIPT_REVIEW_SOURCE_BINDING_NOT_FOUND")
        source = json.loads(raw)
        if start < int(source["segment_start_ms"]) or end > int(source["segment_end_ms"]):
            raise SourceSpanReviewError("TRANSCRIPT_REVIEW_RANGE_OUTSIDE_SOURCE_SEGMENT")
        variant_sha = _sha256(source["source_variant_sha256"], "SOURCE_VARIANT_SHA256")
        segment_sha = _hash_text(str(source["source_segment_text"]))
        reviewed_sha = _hash_text(reviewed)
        material = {
            "content_id": content,
            "source_variant_id": variant,
            "source_segment_id": segment,
            "source_variant_sha256": variant_sha,
            "source_segment_sha256": segment_sha,
            "start_ms": start,
            "end_ms": end,
            "reviewed_text_sha256": reviewed_sha,
            "decision": action,
            "reviewer_ref": reviewer,
            "reason_codes": reasons,
            "review_version": TRANSCRIPT_VERBATIM_REVIEW_VERSION,
        }
        review_id = _deterministic_id("transcript-verbatim-review", material)
        self.run(
            """
            INSERT INTO transcript_verbatim_review_event(
                id,content_id,source_variant_id,source_segment_id,source_variant_sha256,
                source_segment_sha256,start_ms,end_ms,reviewed_text,reviewed_text_sha256,
                decision,reviewer_ref,reason_codes,review_version
            ) VALUES (
                :'id',:'content_id',:'source_variant_id',:'source_segment_id',
                :'source_variant_sha256',:'source_segment_sha256',:'start_ms'::bigint,
                :'end_ms'::bigint,:'reviewed_text',:'reviewed_text_sha256',:'decision',
                :'reviewer_ref',:'reason_codes'::text[],:'review_version'
            ) ON CONFLICT (id) DO NOTHING
            RETURNING id;
            """,
            id=review_id,
            content_id=content,
            source_variant_id=variant,
            source_segment_id=segment,
            source_variant_sha256=variant_sha,
            source_segment_sha256=segment_sha,
            start_ms=start,
            end_ms=end,
            reviewed_text=reviewed,
            reviewed_text_sha256=reviewed_sha,
            decision=action,
            reviewer_ref=reviewer,
            reason_codes="{" + ",".join(reasons) + "}",
            review_version=TRANSCRIPT_VERBATIM_REVIEW_VERSION,
        )
        return TranscriptVerbatimReview(
            id=review_id,
            content_id=content,
            source_variant_id=variant,
            source_segment_id=segment,
            source_variant_sha256=variant_sha,
            source_segment_sha256=segment_sha,
            start_ms=start,
            end_ms=end,
            reviewed_text=reviewed,
            reviewed_text_sha256=reviewed_sha,
            decision=action,
            reviewer_ref=reviewer,
            reason_codes=reasons,
        )

    def record_context_review(
        self,
        *,
        record_id: str,
        assessment: ContextIntegrityAssessment,
        decision: str,
        reviewer_ref: str,
        reason_codes: Iterable[object] = (),
    ) -> ContextIntegrityReview:
        record = _text(record_id, "RECORD_ID", 512)
        reviewer = _text(reviewer_ref, "REVIEWER_REF", 512)
        action = _decision(decision)
        reasons = _codes(reason_codes, "REASON_CODE")
        signals = _codes(assessment.signal_codes, "SIGNAL_CODE")
        if not assessment.context_sha256:
            raise SourceSpanReviewError("CONTEXT_REVIEW_CONTEXT_HASH_REQUIRED")
        material = {
            "record_id": record,
            "source_sha256": assessment.source_sha256,
            "quote_sha256": assessment.quote_sha256,
            "context_sha256": assessment.context_sha256,
            "quote_start": assessment.quote_start,
            "quote_end": assessment.quote_end,
            "context_start": assessment.context_start,
            "context_end": assessment.context_end,
            "signal_codes": signals,
            "decision": action,
            "reviewer_ref": reviewer,
            "reason_codes": reasons,
            "review_version": CONTEXT_INTEGRITY_REVIEW_VERSION,
        }
        review_id = _deterministic_id("context-integrity-review", material)
        self.run(
            """
            INSERT INTO context_integrity_review_event(
                id,record_id,source_sha256,quote_sha256,context_sha256,quote_start,quote_end,
                context_start,context_end,signal_codes,decision,reviewer_ref,reason_codes,
                review_version
            ) VALUES (
                :'id',:'record_id',:'source_sha256',:'quote_sha256',:'context_sha256',
                :'quote_start'::integer,:'quote_end'::integer,:'context_start'::integer,
                :'context_end'::integer,:'signal_codes'::text[],:'decision',:'reviewer_ref',
                :'reason_codes'::text[],:'review_version'
            ) ON CONFLICT (id) DO NOTHING
            RETURNING id;
            """,
            id=review_id,
            record_id=record,
            source_sha256=assessment.source_sha256,
            quote_sha256=assessment.quote_sha256,
            context_sha256=assessment.context_sha256,
            quote_start=assessment.quote_start,
            quote_end=assessment.quote_end,
            context_start=assessment.context_start,
            context_end=assessment.context_end,
            signal_codes="{" + ",".join(signals) + "}",
            decision=action,
            reviewer_ref=reviewer,
            reason_codes="{" + ",".join(reasons) + "}",
            review_version=CONTEXT_INTEGRITY_REVIEW_VERSION,
        )
        return ContextIntegrityReview(
            id=review_id,
            record_id=record,
            source_sha256=assessment.source_sha256,
            quote_sha256=assessment.quote_sha256,
            context_sha256=assessment.context_sha256,
            quote_start=assessment.quote_start,
            quote_end=assessment.quote_end,
            context_start=assessment.context_start,
            context_end=assessment.context_end,
            signal_codes=signals,
            decision=action,
            reviewer_ref=reviewer,
            reason_codes=reasons,
        )


__all__ = [
    "CONTEXT_INTEGRITY_REVIEW_VERSION",
    "TRANSCRIPT_VERBATIM_REVIEW_VERSION",
    "ContextIntegrityReview",
    "ReviewFreshness",
    "SourceSpanReviewError",
    "SourceSpanReviewStore",
    "TranscriptVerbatimReview",
    "context_review_freshness",
    "transcript_review_freshness",
]
