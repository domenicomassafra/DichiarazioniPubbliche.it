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
from dichiarazioni_pubbliche.senato_akoma_stenographic import SenatoAkomaCandidateImport
from dichiarazioni_pubbliche.wording_contract import assess_translation


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def probe_private_speech(
    imported: SenatoAkomaCandidateImport,
    *,
    ordinal: int,
    german_draft: str | None = None,
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
        # An AKN <speech> is not an independently verified complete turn.
        turn_complete=False,
        language="it",
    )
    verify_speech_act_context_metadata(
        original.to_metadata(), source_text=speech.review_text
    )
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
        german = german_draft.strip()
        derived = assess_speech_act_context(
            source_text=german, source_sha256=_sha(german),
            quote_start=0, quote_end=len(german), turn_start=0,
            turn_end=len(german), utterer_id="", turn_speaker_ids=(),
            source_part_ref=speech.speech_id + ":derived:de",
            turn_complete=False, language="de",
        )
        translated = assess_translation(
            source_text=speech.review_text, translated_text=german,
            source_language="it", target_language="de",
            method="HUMAN", human_reviewed=False,
        )
        if derived.state != "HOLD_FOR_CONTEXT" or derived.publication_authority:
            raise ValueError("DP331_UNREVIEWED_TRANSLATION_WAS_PROMOTED")
        receipt["german_draft"] = {
            "language": "de", "decision": "HOLD",
            "speech_act": derived.speech_act, "stance": derived.stance,
            "signals": derived.signal_codes,
            "context_binding": derived.binding_sha256,
            "translation_review": translated.state.value,
            "translation_risks": translated.signal_codes,
            "source_wording_approved": False,
        }
    return receipt
