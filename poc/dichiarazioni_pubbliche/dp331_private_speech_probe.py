"""Read-only DP-312 diagnostic over an already imported private Senate source.

The returned fields are review hypotheses, never candidate promotion or a
source-use/extraction authorization. No content or translated text is emitted.
"""

from __future__ import annotations

import hashlib

from dichiarazioni_pubbliche.context_integrity import (
    assess_speech_act_context,
    verify_speech_act_context_metadata,
)
from dichiarazioni_pubbliche.relation_runtime import (
    ScopedStatementRelationInput,
    StatementRelationKind,
    StatementRelationScope,
    evaluate_scoped_statement_relation,
)
from dichiarazioni_pubbliche.senato_akoma_stenographic import (
    SenatoAkomaCandidateImport, SenatoAkomaSpeechCandidate,
)
from dichiarazioni_pubbliche.wording_contract import (
    DERIVED_REPRESENTATION_ROLE,
    WordingType,
    assess_translation,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _original_context(speech: SenatoAkomaSpeechCandidate):
    if _sha(speech.review_text) != speech.review_text_sha256:
        raise ValueError("DP331_SPEECH_SOURCE_HASH_MISMATCH")
    original = assess_speech_act_context(
        source_text=speech.review_text,
        source_sha256=speech.review_text_sha256,
        quote_start=0, quote_end=len(speech.review_text),
        turn_start=0, turn_end=len(speech.review_text),
        utterer_id=speech.official_person_uri,
        turn_speaker_ids=(speech.official_person_uri,),
        source_part_ref=speech.speech_id,
        turn_complete=False,
        language="it",
    )
    verify_speech_act_context_metadata(
        original.to_metadata(), source_text=speech.review_text,
    )
    return original


def probe_private_statement_relation(
    imported: SenatoAkomaCandidateImport, *, ordinals: tuple[int, int],
) -> dict[str, object]:
    """Exercise DP-318 on original source turns without inventing editorial review.

    The official speaker URI is only a *candidate*. Unknown Person, proposition,
    statement kind and stance must remain unknown in the Statement seam.
    """
    if len(ordinals) != 2 or ordinals[0] == ordinals[1]:
        raise ValueError("DP333_TWO_DISTINCT_SPEECHES_REQUIRED")
    if imported.source_license_id != "CC-BY-4.0":
        raise ValueError("DP331_SOURCE_LICENSE_UNSUPPORTED")
    scope = StatementRelationScope(
        jurisdiction_ref="jurisdiction:it",
        subject_ref="subject:unresolved",
        period_start=imported.sitting_date,
        period_end=imported.sitting_date,
        modality="UNKNOWN",
        condition_ref="NONE",
        location_ref="location:unresolved",
    )
    statements = []
    for ordinal in ordinals:
        speech = next((s for s in imported.speeches if s.ordinal == ordinal), None)
        if speech is None:
            raise ValueError("DP331_SPEECH_NOT_AVAILABLE")
        statements.append(ScopedStatementRelationInput(
            statement_id=speech.speech_id,
            person_id="person:unresolved",
            statement_date=imported.sitting_date,
            proposition_key=None,
            equivalence_review_ref=None,
            statement_kind="UNKNOWN",
            position="UNKNOWN",
            scope=scope,
            speech_act=_original_context(speech),
        ))
    decision = evaluate_scoped_statement_relation(*statements)
    if decision.kind != StatementRelationKind.HOLD:
        raise ValueError("DP333_UNREVIEWED_RELATION_WAS_PROMOTED")
    return {
        "kind": decision.kind.value,
        "state": decision.state,
        "person_cardinality": decision.person_cardinality,
        "source_context_bindings": list(decision.source_context_bindings),
        "rationale_codes": list(decision.rationale_codes),
        "review_authority": decision.review_authority,
        "publication_authority": decision.publication_authority,
    }


def probe_private_speech(
    imported: SenatoAkomaCandidateImport,
    *,
    ordinal: int,
    german_draft: str | None = None,
    italian_quote_span: tuple[int, int] | None = None,
) -> dict[str, object]:
    """Inspect one source-attested speaker reference without granting a speech act.

    Completeness and quote author are not inferred from XML labels or a
    generated translation; every output remains HOLD.
    """
    if imported.source_license_id != "CC-BY-4.0":
        raise ValueError("DP331_SOURCE_LICENSE_UNSUPPORTED")
    if type(ordinal) is not int:
        raise ValueError("DP331_SPEECH_NOT_AVAILABLE")
    speech = next((item for item in imported.speeches if item.ordinal == ordinal), None)
    if speech is None:
        raise ValueError("DP331_SPEECH_NOT_AVAILABLE")
    if german_draft is None and italian_quote_span is not None:
        raise ValueError("DP331_ITALIAN_QUOTE_SPAN_REQUIRES_DRAFT")
    if german_draft is not None and (
        not isinstance(italian_quote_span, tuple)
        or len(italian_quote_span) != 2
        or any(type(offset) is not int for offset in italian_quote_span)
        or not (0 <= italian_quote_span[0] < italian_quote_span[1] <= len(speech.review_text))
        or italian_quote_span[1] - italian_quote_span[0] > 500
    ):
        raise ValueError("DP331_ITALIAN_QUOTE_SPAN_INVALID")

    original = _original_context(speech)
    if original.state != "HOLD_FOR_CONTEXT" or original.publication_authority:
        raise ValueError("DP331_UNREVIEWED_SPEECH_WAS_PROMOTED")
    receipt: dict[str, object] = {
        "speech_id": speech.speech_id,
        "source_sha256": imported.source_sha256,
        "source_commit": imported.source_commit_sha,
        "source_blob_sha1": imported.source_blob_sha1,
        "source_role_label": speech.presentation_label,
        "source_author_candidate": None,
        "utterer_candidate": speech.official_person_uri,
        "quoted_author_candidate": None,
        "speech_act": original.speech_act,
        "stance": original.stance,
        "language": "it",
        "decision": "HOLD",
        "signals": original.signal_codes,
        "context_binding": original.binding_sha256,
        "source_revision_binding": _sha(
            imported.source_sha256 + ":" + speech.speech_id + ":"
            + original.binding_sha256
        ),
        "attribution_approved": False,
        "extraction_authorized": False,
        "publication_authorized": False,
        "german_draft": None,
    }
    if german_draft is not None:
        if not isinstance(german_draft, str) or not german_draft.strip() or len(german_draft) > 2000:
            raise ValueError("DP331_GERMAN_DRAFT_INVALID")
        if italian_quote_span is None:
            raise ValueError("DP331_ITALIAN_QUOTE_SPAN_INVALID")
        start, end = italian_quote_span
        italian_quote = speech.review_text[start:end]
        quote_decision = assess_speech_act_context(
            source_text=speech.review_text, source_sha256=speech.review_text_sha256,
            quote_start=start, quote_end=end, turn_start=0,
            turn_end=len(speech.review_text), utterer_id=speech.official_person_uri,
            turn_speaker_ids=(speech.official_person_uri,),
            source_part_ref=speech.speech_id, turn_complete=False, language="it",
        )
        if quote_decision.state != "HOLD_FOR_CONTEXT" or quote_decision.publication_authority:
            raise ValueError("DP331_UNREVIEWED_SOURCE_QUOTE_WAS_PROMOTED")
        german = german_draft.strip()
        derived = assess_speech_act_context(
            source_text=german, source_sha256=_sha(german),
            quote_start=0, quote_end=len(german), turn_start=0,
            turn_end=len(german), utterer_id="", turn_speaker_ids=(),
            source_part_ref=speech.speech_id + ":derived:de",
            turn_complete=False, language="de",
        )
        translated = assess_translation(
            source_text=italian_quote, translated_text=german,
            source_language="it", target_language="de",
            method="MACHINE", human_reviewed=False,
        )
        if derived.state != "HOLD_FOR_CONTEXT" or derived.publication_authority:
            raise ValueError("DP331_UNREVIEWED_TRANSLATION_WAS_PROMOTED")
        receipt["german_draft"] = {
            "language": "de", "decision": "HOLD",
            "wording_type": WordingType.TRANSLATION.value,
            "representation_role": DERIVED_REPRESENTATION_ROLE,
            "translation_method": translated.method,
            "source_quote_start": start, "source_quote_end": end,
            "source_quote_sha256": _sha(italian_quote),
            "source_quote_speech_act": quote_decision.speech_act,
            "source_quote_stance": quote_decision.stance,
            "source_quote_context_binding": quote_decision.binding_sha256,
            "source_quote_signals": quote_decision.signal_codes,
            "translation_sha256": translated.translation_sha256,
            "speech_act": derived.speech_act, "stance": derived.stance,
            "signals": derived.signal_codes,
            "context_binding": derived.binding_sha256,
            "translation_review": translated.state.value,
            "translation_risks": translated.signal_codes,
            "source_wording_approved": False,
        }
    return receipt
