from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Sequence


QUOTE_BINDING_VERSION = "exact-quote-binding-v1"
DISCONTINUOUS_QUOTE_BINDING_VERSION = "discontinuous-quote-binding-v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXPLICIT_OMISSION_MARKER = " […] "


@dataclass(frozen=True)
class QuoteBindingResult:
    status: str
    reason_code: str
    statement_text_sha256: str
    passage_text_sha256: str
    recomputed_text_sha256: str
    source_sha256: str
    start_char: int
    end_char: int
    version: str = QUOTE_BINDING_VERSION

    @property
    def verified(self) -> bool:
        return self.status == "VERIFIED"


@dataclass(frozen=True)
class BoundQuoteSpan:
    start_char: int
    end_char: int
    text_sha256: str


@dataclass(frozen=True)
class DiscontinuousQuoteBindingResult:
    status: str
    reason_code: str
    source_sha256: str
    statement_text_sha256: str
    rendered_text_sha256: str
    spans: tuple[BoundQuoteSpan, ...]
    omission_count: int
    binding_sha256: str
    version: str = DISCONTINUOUS_QUOTE_BINDING_VERSION

    @property
    def verified(self) -> bool:
        return self.status == "VERIFIED"


def _sha(value: str, field: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError(f"QUOTE_BINDING_{field.upper()}_INVALID")
    return normalized


def verify_written_quote_binding(
    *,
    statement_text_sha256: str,
    passage_text_sha256: str,
    private_text: str,
    selector_type: str,
    start_char: int | None,
    end_char: int | None,
    source_sha256: str,
) -> QuoteBindingResult:
    statement_hash = _sha(statement_text_sha256, "statement_text_sha256")
    passage_hash = _sha(passage_text_sha256, "passage_text_sha256")
    source_hash = _sha(source_sha256, "source_sha256")
    recomputed = hashlib.sha256(str(private_text or "").encode("utf-8")).hexdigest()

    if selector_type != "TEXT_POSITION":
        return QuoteBindingResult(
            status="BLOCKED",
            reason_code="QUOTE_SELECTOR_NOT_EXACT",
            statement_text_sha256=statement_hash,
            passage_text_sha256=passage_hash,
            recomputed_text_sha256=recomputed,
            source_sha256=source_hash,
            start_char=-1,
            end_char=-1,
        )
    if start_char is None or end_char is None:
        raise ValueError("QUOTE_BINDING_POSITION_REQUIRED")
    start = int(start_char)
    end = int(end_char)
    if start < 0 or end <= start:
        raise ValueError("QUOTE_BINDING_POSITION_INVALID")
    text = str(private_text or "")
    if end - start != len(text):
        return QuoteBindingResult(
            status="BLOCKED",
            reason_code="QUOTE_POSITION_LENGTH_MISMATCH",
            statement_text_sha256=statement_hash,
            passage_text_sha256=passage_hash,
            recomputed_text_sha256=recomputed,
            source_sha256=source_hash,
            start_char=start,
            end_char=end,
        )
    if recomputed != passage_hash:
        return QuoteBindingResult(
            status="BLOCKED",
            reason_code="PASSAGE_TEXT_HASH_MISMATCH",
            statement_text_sha256=statement_hash,
            passage_text_sha256=passage_hash,
            recomputed_text_sha256=recomputed,
            source_sha256=source_hash,
            start_char=start,
            end_char=end,
        )
    if statement_hash != passage_hash:
        return QuoteBindingResult(
            status="BLOCKED",
            reason_code="STATEMENT_NOT_EXACT_PASSAGE",
            statement_text_sha256=statement_hash,
            passage_text_sha256=passage_hash,
            recomputed_text_sha256=recomputed,
            source_sha256=source_hash,
            start_char=start,
            end_char=end,
        )
    return QuoteBindingResult(
        status="VERIFIED",
        reason_code="EXACT_SOURCE_SPAN_VERIFIED",
        statement_text_sha256=statement_hash,
        passage_text_sha256=passage_hash,
        recomputed_text_sha256=recomputed,
        source_sha256=source_hash,
        start_char=start,
        end_char=end,
    )


def verify_discontinuous_written_quote_binding(
    *,
    statement_text_sha256: str,
    source_text: str,
    source_sha256: str,
    spans: Sequence[tuple[int, int]],
) -> DiscontinuousQuoteBindingResult:
    """Verify a multi-span quote whose omissions must remain explicit.

    The rendered quote is reconstructed only from the private source body and the
    supplied source offsets. Non-adjacent spans are always separated by the canonical
    omission marker, so callers cannot turn distant clauses into an apparently
    contiguous source sentence. The result persists hashes/offsets only, never source
    text.
    """

    statement_hash = _sha(statement_text_sha256, "statement_text_sha256")
    source_hash = _sha(source_sha256, "source_sha256")
    text = str(source_text or "")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != source_hash:
        raise ValueError("QUOTE_BINDING_SOURCE_TEXT_HASH_MISMATCH")
    if len(spans) < 2:
        raise ValueError("DISCONTINUOUS_QUOTE_MULTIPLE_SPANS_REQUIRED")

    bound: list[BoundQuoteSpan] = []
    pieces: list[str] = []
    previous_end: int | None = None
    for raw_start, raw_end in spans:
        start = int(raw_start)
        end = int(raw_end)
        if start < 0 or end <= start or end > len(text):
            raise ValueError("DISCONTINUOUS_QUOTE_SPAN_INVALID")
        if previous_end is not None and start < previous_end:
            raise ValueError("DISCONTINUOUS_QUOTE_SPAN_ORDER_INVALID")
        if previous_end is not None and start == previous_end:
            raise ValueError("DISCONTINUOUS_QUOTE_ADJACENT_SPANS_REFUSED")
        piece = text[start:end]
        digest = hashlib.sha256(piece.encode("utf-8")).hexdigest()
        bound.append(BoundQuoteSpan(start, end, digest))
        pieces.append(piece)
        previous_end = end

    rendered = EXPLICIT_OMISSION_MARKER.join(pieces)
    rendered_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    material = {
        "source_sha256": source_hash,
        "statement_text_sha256": statement_hash,
        "rendered_text_sha256": rendered_hash,
        "spans": [
            {
                "start_char": item.start_char,
                "end_char": item.end_char,
                "text_sha256": item.text_sha256,
            }
            for item in bound
        ],
        "omission_count": len(bound) - 1,
        "omission_marker": EXPLICIT_OMISSION_MARKER,
        "version": DISCONTINUOUS_QUOTE_BINDING_VERSION,
    }
    binding_sha256 = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    verified = statement_hash == rendered_hash
    return DiscontinuousQuoteBindingResult(
        status="VERIFIED" if verified else "BLOCKED",
        reason_code=(
            "EXPLICIT_DISCONTINUOUS_SOURCE_SPANS_VERIFIED"
            if verified
            else "DISCONTINUOUS_QUOTE_RENDER_MISMATCH"
        ),
        source_sha256=source_hash,
        statement_text_sha256=statement_hash,
        rendered_text_sha256=rendered_hash,
        spans=tuple(bound),
        omission_count=len(bound) - 1,
        binding_sha256=binding_sha256,
    )


__all__ = [
    "BoundQuoteSpan",
    "DISCONTINUOUS_QUOTE_BINDING_VERSION",
    "DiscontinuousQuoteBindingResult",
    "EXPLICIT_OMISSION_MARKER",
    "QUOTE_BINDING_VERSION",
    "QuoteBindingResult",
    "verify_discontinuous_written_quote_binding",
    "verify_written_quote_binding",
]
