from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


QUOTE_BINDING_VERSION = "exact-quote-binding-v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


__all__ = [
    "QUOTE_BINDING_VERSION",
    "QuoteBindingResult",
    "verify_written_quote_binding",
]
