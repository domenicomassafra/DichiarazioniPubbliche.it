"""Source-bound private context assessments for extraction candidates."""

from __future__ import annotations

from typing import Any, Protocol

from dichiarazioni_pubbliche.context_integrity import (
    assess_context_integrity,
    assess_speech_act_context,
)


class CandidateContextSource(Protocol):
    text: str
    text_sha256: str
    passage_id: str
    language: str | None


def candidate_context_assessments(
    context: CandidateContextSource,
    *,
    quote_start: int,
    quote_end: int,
    speech_mode: str,
    media_speaker: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Unreviewed turns remain private even with a resolved segment speaker."""
    integrity = assess_context_integrity(
        source_text=context.text,
        source_sha256=context.text_sha256,
        quote_start=quote_start,
        quote_end=quote_end,
        speech_mode=speech_mode,
    )
    act = assess_speech_act_context(
        source_text=context.text,
        source_sha256=context.text_sha256,
        quote_start=quote_start,
        quote_end=quote_end,
        turn_start=0,
        turn_end=len(context.text),
        utterer_id=media_speaker or "",
        turn_speaker_ids=(media_speaker,) if media_speaker else (),
        source_part_ref=context.passage_id,
        turn_complete=False,
        language=context.language,
    )
    return integrity.to_metadata(), act.to_metadata()
