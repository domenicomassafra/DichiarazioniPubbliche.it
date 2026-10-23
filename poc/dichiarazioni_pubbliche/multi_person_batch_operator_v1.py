"""DP-240 private operator bridge for already rights-gated Passage batches.

The review context file is an operator assertion, never an identity/rights
approval. Existing capture, rights and model-use guards remain mandatory.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import fields
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.candidate_extraction import EXTRACTOR_VERSION
from dichiarazioni_pubbliche.multi_person_batch_v1 import (
    PrivateBatchResult,
    ReviewedPassageContext,
    plan_isolated_candidate_batch,
)
from dichiarazioni_pubbliche.private_candidate_batch import CandidateBatch


_CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("MULTIPERSON_OPERATOR_CONTEXT_INVALID")
        result[key] = value
    return result


def load_operator_plan(
    batch: CandidateBatch, context_path: Path, candidate_store: Any,
    *, provider_capability_ready: bool,
):
    """Bind reviewed metadata to current, independently persisted source bytes.

    Called only after the existing read-only rights/Capture/Passage preflight.
    A SHA or context-review string alone is not reviewer authority.
    """
    try:
        if context_path.is_symlink() or not context_path.is_file():
            raise ValueError("MULTIPERSON_OPERATOR_CONTEXT_INVALID")
        if context_path.stat().st_size > 65536:
            raise ValueError("MULTIPERSON_OPERATOR_CONTEXT_INVALID")
        raw = json.loads(context_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("MULTIPERSON_OPERATOR_CONTEXT_INVALID") from exc
    if not isinstance(raw, dict) or set(raw) != {item.passage_id for item in batch.items}:
        raise ValueError("MULTIPERSON_OPERATOR_CONTEXT_INVALID")
    expected = {field.name for field in fields(ReviewedPassageContext)}
    contexts: dict[str, ReviewedPassageContext] = {}
    for item in batch.items:
        row = raw[item.passage_id]
        if not isinstance(row, dict) or set(row) != expected:
            raise ValueError("MULTIPERSON_OPERATOR_CONTEXT_INVALID")
        try:
            context = ReviewedPassageContext(**row)
        except (TypeError, ValueError) as exc:
            raise ValueError("MULTIPERSON_OPERATOR_CONTEXT_INVALID") from exc
        persisted = candidate_store.read_private_passage_source_binding(item.passage_id)
        if not isinstance(persisted, dict):
            raise ValueError("MULTIPERSON_OPERATOR_SOURCE_MISMATCH")
        if (
            context.source_sha256 != persisted.get("capture_content_sha256")
            or context.selector_fingerprint != (
                f"TEXT_POSITION:{persisted.get('start_char')}:{persisted.get('end_char')}"
            )
            or persisted.get("selector_type") != "TEXT_POSITION"
        ):
            raise ValueError("MULTIPERSON_OPERATOR_SOURCE_MISMATCH")
        contexts[item.passage_id] = context
    return plan_isolated_candidate_batch(
        batch, contexts,
        total_token_cap=sum(context.estimated_tokens for context in contexts.values()),
        provider_capability_ready=provider_capability_ready,
    )


def attempt_key(plan_sha256: str, passage_id: str) -> str:
    """Stable per-item key: a resumed run cannot duplicate an attempt."""
    return "dp240:" + hashlib.sha256(f"{plan_sha256}:{passage_id}".encode()).hexdigest()


def private_observation(
    item, receipt, *, accepted: bool, failure_override: str | None = None,
) -> PrivateBatchResult:
    """Never interpret an untrusted provider response as a new Person approval."""
    reason = failure_override or getattr(receipt, "reason_code", None)
    if not isinstance(reason, str) or not _CODE.fullmatch(reason):
        reason = "CANDIDATE_EXTRACTION_FAILED"
    return PrivateBatchResult(
        passage_id=item.passage_id,
        content_id=item.content_id,
        capture_id=item.capture_id,
        passage_sha256=item.passage_sha256,
        result="CANDIDATE_EXTRACTED" if accepted else "FAILED",
        failure_reason=None if accepted else reason,
        extraction_version=EXTRACTOR_VERSION if accepted else None,
    )
