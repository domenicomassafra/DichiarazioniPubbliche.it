"""Operator-local, static, keyboard-native DP-418 review inspection.

This HTML is never part of the public web bundle and cannot make decisions.
It displays only whitelisted metadata from the validated Studio backend
receipt; source/candidate words and private evidence bodies stay server-side.
Review handoff status is supplied by actual queue.read(), not inferred from
the matching algorithm.
"""

from __future__ import annotations

from html import escape
import re
from typing import Mapping

from dichiarazioni_pubbliche.studio_candidate_review import (
    REVIEW_HANDOFF_VERSION, STUDIO_CANDIDATE_REVIEW_VERSION,
)

_ID = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_METHODS = {"EXACT_NORMALIZED", "LEXICAL_TRIGRAM", "SOURCE_SELECTOR_OVERLAP"}
_CLASSES = {"DUPLICATE_EXTRACTION", "SAME_PROPOSITION", "RELATED", "DIFFERENT", "UNCERTAIN"}
_DISPOSITIONS = {"PROPOSE_CLUSTER", "NO_CLUSTER", "HOLD"}


def _reference(value: object, *, optional: bool = False) -> str:
    if optional and value is None:
        return "—"
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("STUDIO_REVIEW_UI_REFERENCE_INVALID")
    return escape(value)


def _hash(value: object, *, optional: bool = False) -> str:
    if optional and value is None:
        return "—"
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError("STUDIO_REVIEW_UI_HASH_INVALID")
    return escape(value)


def _codes(values: object) -> str:
    if not isinstance(values, (list, tuple)) or len(values) > 24:
        raise ValueError("STUDIO_REVIEW_UI_CODES_INVALID")
    if any(not isinstance(v, str) or not _CODE.fullmatch(v) for v in values):
        raise ValueError("STUDIO_REVIEW_UI_CODE_INVALID")
    return ", ".join(escape(v) for v in values) or "—"


def render_candidate_review_workspace(
    packet: Mapping[str, object],
    *,
    persisted_handoff: Mapping[str, object] | None = None,
) -> bytes:
    """Render one private operator response; caller enforces local authentication.

    The optional handoff must have already been read and verified from
    LocalCandidateReviewHandoffQueue. An arbitrary match suggestion is never
    displayed as a persisted human review decision.
    """
    if (not isinstance(packet, Mapping)
            or packet.get("contract_version") != STUDIO_CANDIDATE_REVIEW_VERSION
            or packet.get("private_only") is not True
            or packet.get("review_authority") is not False
            or packet.get("publication_authority") is not False
            or packet.get("promotion_authority") is not False
            or packet.get("currentness") not in {"CURRENT", "STALE", "UNVERIFIED"}
            or not isinstance(packet.get("results"), list)
            or len(packet["results"]) > 30):
        raise ValueError("STUDIO_REVIEW_UI_PACKET_INVALID")
    candidate_id = _reference(packet.get("claim_candidate_id"))
    run_id = _reference(packet.get("run_id"))
    fingerprint = _hash(packet.get("input_fingerprint"))
    currentness = escape(str(packet["currentness"]))
    blockers = _codes(packet.get("promotion_blockers"))
    source = packet.get("source_references")
    if not isinstance(source, list) or len(source) > 2:
        raise ValueError("STUDIO_REVIEW_UI_SOURCE_INVALID")
    sources: list[str] = []
    for row in source:
        if not isinstance(row, Mapping):
            raise ValueError("STUDIO_REVIEW_UI_SOURCE_INVALID")
        sources.append(
            "<li>Passage " + _reference(row.get("passage_id"), optional=True)
            + " · Capture " + _reference(row.get("capture_id"), optional=True)
            + " · Segmento " + _reference(row.get("segment_id"), optional=True)
            + " · SHA " + _hash(row.get("capture_sha256"), optional=True) + "</li>"
        )
    matches: list[str] = []
    for row in packet["results"]:
        if not isinstance(row, Mapping):
            raise ValueError("STUDIO_REVIEW_UI_RESULT_INVALID")
        cls = row.get("match_class")
        method = row.get("matching_method")
        disposition = row.get("suggested_disposition")
        if cls not in _CLASSES or method not in _METHODS or disposition not in _DISPOSITIONS:
            raise ValueError("STUDIO_REVIEW_UI_RESULT_CLASS_INVALID")
        matches.append(
            "<details><summary>" + escape(cls) + " · "
            + _reference(row.get("target_id")) + "</summary><dl>"
            + "<dt>Risultato</dt><dd>" + _reference(row.get("result_id")) + "</dd>"
            + "<dt>Tipo target</dt><dd>" + _codes([row.get("target_type")]) + "</dd>"
            + "<dt>Metodo</dt><dd>" + escape(method) + "</dd>"
            + "<dt>Proposta automatica, non approvata</dt><dd>" + escape(disposition) + "</dd>"
            + "<dt>Cluster proposto</dt><dd>" + _reference(row.get("proposition_cluster_id"), optional=True) + "</dd>"
            + "<dt>Elementi a favore</dt><dd>" + _codes(row.get("supporting_feature_codes")) + "</dd>"
            + "<dt>Elementi contrari</dt><dd>" + _codes(row.get("contradicting_feature_codes")) + "</dd>"
            + "</dl></details>"
        )
    handoff_text = "Nessuna richiesta di revisione registrata."
    if persisted_handoff is not None:
        if (not isinstance(persisted_handoff, Mapping)
                or persisted_handoff.get("contract_version") != REVIEW_HANDOFF_VERSION
                or persisted_handoff.get("status") != "QUEUED_FOR_HUMAN_REVIEW"
                or persisted_handoff.get("candidate_id") != packet["claim_candidate_id"]
                or persisted_handoff.get("run_id") != packet["run_id"]
                or persisted_handoff.get("input_fingerprint") != packet["input_fingerprint"]
                or persisted_handoff.get("review_authority") is not False
                or persisted_handoff.get("promotion_authority") is not False
                or persisted_handoff.get("publication_authority") is not False):
            raise ValueError("STUDIO_REVIEW_UI_HANDOFF_INVALID")
        handoff_text = (
            "Richiesta persistita " + _reference(persisted_handoff.get("handoff_id"))
            + ": " + escape(str(persisted_handoff["status"]))
            + ". In attesa di decisione umana, nessuna approvazione."
        )
    return (
        "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow,noarchive'>"
        "<title>Studio locale · revisione candidati</title>"
        "<style>body{font:1rem/1.6 system-ui,sans-serif;max-width:70rem;margin:auto;padding:1rem}"
        ".columns{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,20rem),1fr));gap:1rem}"
        "section{border:1px solid #637081;padding:1rem;min-width:0}dd,li{overflow-wrap:anywhere}"
        "dt{font-weight:bold}dd{margin:0 0 .8rem}details{border-top:1px solid #637081;padding:.8rem 0}"
        "summary{cursor:pointer;font-weight:600}:focus-visible{outline:3px solid #0757c8;outline-offset:3px}"
        "@media(max-width:45rem){.columns{display:block}section{margin-bottom:1rem}}</style></head>"
        "<body><main><h1>Revisione privata delle corrispondenze</h1>"
        "<p>Solo riferimenti verificabili. Nessuna approvazione, promozione o pubblicazione automatica.</p>"
        "<p>Candidate " + candidate_id + " · Run " + run_id + "</p>"
        "<p>Fingerprint input: " + fingerprint + "</p>"
        "<p role='status'>Attualità: " + currentness + "</p>"
        "<p>Blocchi alla promozione: " + blockers + "</p>"
        "<div class='columns'><section aria-labelledby='source'><h2 id='source'>Riferimenti fonte e passaggi</h2>"
        "<ul>" + ("".join(sources) or "<li>Nessun passaggio verificato.</li>")
        + "</ul></section><section aria-labelledby='matches'><h2 id='matches'>Candidati e cluster</h2>"
        + ("".join(matches) or "<p>Nessun risultato.</p>") + "</section></div>"
        "<section aria-label='Coda revisione'><h2>Stato della richiesta</h2><p>"
        + handoff_text + "</p></section></main></body></html>"
    ).encode("utf-8")


__all__ = ["render_candidate_review_workspace"]
