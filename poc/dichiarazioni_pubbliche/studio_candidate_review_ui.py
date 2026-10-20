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
from typing import Any, Mapping, Protocol

from dichiarazioni_pubbliche.studio_candidate_review import (
    REVIEW_HANDOFF_VERSION,
    STUDIO_CANDIDATE_REVIEW_VERSION,
    inspect_candidate_review_readiness,
)
from dichiarazioni_pubbliche.candidate_matching import MATCHING_VERSION
from dichiarazioni_pubbliche.studio_candidate_source_guard import (
    validate_source_context as _target_source,
)

_ID = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_METHODS = {"EXACT_NORMALIZED", "LEXICAL_TRIGRAM", "SOURCE_SELECTOR_OVERLAP"}
_CLASSES = {
    "DUPLICATE_EXTRACTION",
    "SAME_PROPOSITION",
    "RELATED",
    "DIFFERENT",
    "UNCERTAIN",
}
_CLASS_EXPLANATIONS = {
    "DUPLICATE_EXTRACTION": "Possibile duplicato della stessa estrazione e dello stesso passaggio fonte",
    "SAME_PROPOSITION": "Stessa proposizione suggerita, senza prova di duplicazione dell'estrazione",
    "RELATED": "Proposizioni collegate, equivalenza non dimostrata",
    "DIFFERENT": "Proposizioni distinte nella classificazione proposta",
    "UNCERTAIN": "Confronto incerto: mantenere in verifica umana",
}
_DISPOSITIONS = {"PROPOSE_CLUSTER", "NO_CLUSTER", "HOLD"}

DP418_COMPARISON_VERSION = "studio-candidate-source-comparison-v1"


class PersistedTargetSourceReader(Protocol):
    """Read each target source separately from the persisted match suggestion."""

    def source_context(
        self, member_type: str, member_id: str
    ) -> Mapping[str, object] | None: ...


def build_candidate_comparison_read_model(
    match_store: Any,
    promotion_store: Any,
    target_source_store: PersistedTargetSourceReader,
    *,
    run_id: str,
    claim_candidate_id: str,
) -> dict[str, object]:
    """Compare persisted matches against independently persisted source states."""
    packet = inspect_candidate_review_readiness(
        match_store,
        promotion_store,
        run_id=run_id,
        claim_candidate_id=claim_candidate_id,
    )
    if (
        packet.get("contract_version") != STUDIO_CANDIDATE_REVIEW_VERSION
        or packet.get("matching_version") != MATCHING_VERSION
        or packet.get("private_only") is not True
        or packet.get("review_authority") is not False
        or packet.get("publication_authority") is not False
        or packet.get("promotion_authority") is not False
        or packet.get("currentness") not in {"CURRENT", "STALE"}
    ):
        raise ValueError("DP418_COMPARISON_REPLAY_UNAVAILABLE")
    _reference(packet.get("claim_candidate_id"))
    _reference(packet.get("run_id"))
    _hash(packet.get("input_fingerprint"))
    _hash(packet.get("review_context_sha256"))
    source_refs = packet.get("source_references")
    if not isinstance(source_refs, list) or len(source_refs) != 1:
        raise ValueError("DP418_COMPARISON_CANDIDATE_SOURCE_MISSING")
    source = source_refs[0]
    if not isinstance(source, Mapping):
        raise ValueError("DP418_COMPARISON_CANDIDATE_SOURCE_MISSING")
    for key in ("passage_id", "capture_id"):
        _reference(source.get(key))
    _hash(source.get("capture_sha256"))
    # DP-117 context is already exact-bound to the candidate/Content by the
    # inspector; re-read the private occurrence for the held Capture state.
    candidate_input = match_store.load_candidate(claim_candidate_id)
    candidate = getattr(candidate_input, "proposition", None)
    if (
        getattr(candidate, "member_id", None) != claim_candidate_id
        or getattr(candidate, "member_type", None) != "CLAIM_CANDIDATE"
        or getattr(candidate, "provenance_key", None) != source["passage_id"]
    ):
        raise ValueError("DP418_COMPARISON_CANDIDATE_SOURCE_BINDING_INVALID")
    content_id = _reference(getattr(candidate, "content_id", None))
    context = promotion_store.context(claim_candidate_id)
    if (
        not isinstance(context, Mapping)
        or context.get("candidate_id") != claim_candidate_id
        or context.get("content_id") != content_id
        or not isinstance(context.get("passages"), list)
        or len(context["passages"]) != 1
        or not isinstance(context["passages"][0], Mapping)
    ):
        raise ValueError("DP418_COMPARISON_CANDIDATE_SOURCE_BINDING_INVALID")
    original = context["passages"][0]
    if (
        original.get("passage_id") != source["passage_id"]
        or original.get("capture_id") != source["capture_id"]
        or original.get("capture_sha256") != source["capture_sha256"]
    ):
        raise ValueError("DP418_COMPARISON_CANDIDATE_SOURCE_BINDING_INVALID")
    candidate_source = _target_source(
        target_source_store.source_context("CLAIM_CANDIDATE", claim_candidate_id),
        target_type="CLAIM_CANDIDATE",
        target_id=claim_candidate_id,
        content_id=content_id,
        provenance_key=source["passage_id"],
    )
    if candidate_source is not None and (
        candidate_source["capture_id"] != source["capture_id"]
        or candidate_source["capture_sha256"] != source["capture_sha256"]
    ):
        raise ValueError("DP418_COMPARISON_CANDIDATE_SOURCE_BINDING_INVALID")
    candidate_source_rights_blocked = candidate_source is not None and (
        candidate_source["rights_status"] != "CLEARED"
        or candidate_source["capture_status"] != "CAPTURED"
        or candidate_source["capture_hold_status"] != "NONE"
    )
    candidate_held = (
        original.get("capture_status") != "CAPTURED"
        or original.get("capture_hold_status") != "NONE"
    )
    raw_results = packet.get("results")
    raw_targets = match_store.load_targets(claim_candidate_id, limit=200)
    if not isinstance(raw_results, list) or not isinstance(raw_targets, (list, tuple)):
        raise ValueError("DP418_COMPARISON_MATCH_RESULTS_INVALID")
    by_target: dict[tuple[str, str], tuple[str, str]] = {}
    for target in raw_targets:
        proposition = getattr(target, "proposition", None)
        kind, identifier = (
            getattr(proposition, "member_type", None),
            getattr(proposition, "member_id", None),
        )
        if not isinstance(kind, str) or not isinstance(identifier, str):
            raise ValueError("DP418_COMPARISON_TARGET_BINDING_INVALID")
        key = (kind, identifier)
        if key in by_target:
            raise ValueError("DP418_COMPARISON_TARGET_BINDING_INVALID")
        by_target[key] = (
            _reference(getattr(proposition, "content_id", None)),
            _reference(getattr(proposition, "provenance_key", None)),
        )
    comparisons: list[dict[str, object]] = []
    initial_sources: dict[tuple[str, str], dict[str, str] | None] = {}
    for match in raw_results:
        if not isinstance(match, Mapping):
            raise ValueError("DP418_COMPARISON_MATCH_RESULTS_INVALID")
        kind, identifier = match.get("target_type"), match.get("target_id")
        key = (kind, identifier)
        if key not in by_target:
            raise ValueError("DP418_COMPARISON_TARGET_BINDING_INVALID")
        source_context = _target_source(
            target_source_store.source_context(kind, identifier),
            target_type=kind,
            target_id=identifier,
            content_id=by_target[key][0],
            provenance_key=by_target[key][1],
        )
        initial_sources[key] = source_context
        relation = match.get("match_class")
        method = match.get("matching_method")
        if relation not in _CLASSES or method not in _METHODS:
            raise ValueError("DP418_COMPARISON_MATCH_CLASS_INVALID")
        supports = match.get("supporting_feature_codes")
        contradicts = match.get("contradicting_feature_codes")
        _codes(supports)
        _codes(contradicts)
        if packet["currentness"] != "CURRENT":
            status, action = "BLOCKED_STALE_MATCH_RUN", "REFRESH_PERSISTED_MATCH_RUN"
        elif candidate_held:
            status, action = (
                "BLOCKED_CANDIDATE_SOURCE_HELD",
                "RECHECK_CANDIDATE_CAPTURE_RIGHTS",
            )
        elif candidate_source is None:
            status, action = (
                "BLOCKED_CANDIDATE_SOURCE_UNAVAILABLE",
                "RECOVER_CANDIDATE_CAPTURE_PASSAGE",
            )
        elif candidate_source_rights_blocked:
            status, action = (
                "BLOCKED_CANDIDATE_SOURCE_RIGHTS",
                "RECHECK_CANDIDATE_RIGHTS",
            )
        elif source_context is None:
            status, action = (
                "BLOCKED_TARGET_SOURCE_UNAVAILABLE",
                "RECOVER_TARGET_CAPTURE_PASSAGE",
            )
        elif (
            source_context["rights_status"] != "CLEARED"
            or source_context["capture_status"] != "CAPTURED"
            or source_context["capture_hold_status"] != "NONE"
        ):
            status, action = "BLOCKED_TARGET_SOURCE_RIGHTS", "RECHECK_TARGET_RIGHTS"
        elif relation == "DUPLICATE_EXTRACTION" and (
            source_context["content_id"] != content_id
            or source_context["passage_id"] != source["passage_id"]
            or source_context["capture_id"] != source["capture_id"]
            or source_context["capture_sha256"] != source["capture_sha256"]
        ):
            # Same wording/selector does not establish the same Capture version.
            status, action = (
                "BLOCKED_DUPLICATE_CAPTURE_MISMATCH",
                "COMPARE_EXACT_CAPTURE_VERSIONS",
            )
        elif relation == "DUPLICATE_EXTRACTION":
            status, action = "OPERATOR_COMPARE_PENDING", "CHECK_SAME_SOURCE_EXTRACTION"
        elif relation == "SAME_PROPOSITION":
            status, action = (
                "OPERATOR_COMPARE_PENDING",
                "REVIEW_SAME_PROPOSITION_NOT_DUPLICATE",
            )
        elif relation == "RELATED":
            status, action = "OPERATOR_COMPARE_PENDING", "REVIEW_RELATED_PROPOSITION"
        else:
            status, action = (
                "OPERATOR_COMPARE_PENDING",
                "INVESTIGATE_UNCERTAIN_OR_DISTINCT_MATCH",
            )
        comparisons.append(
            {
                "result_id": _reference(match.get("result_id")),
                "target_type": kind,
                "target_id": identifier,
                "relation": relation,
                "matching_method": method,
                "matching_version": packet["matching_version"],
                "supporting_feature_codes": tuple(supports),
                "contradicting_feature_codes": tuple(contradicts),
                "suggested_disposition": match.get("suggested_disposition"),
                "proposition_cluster_id": match.get("proposition_cluster_id"),
                "source": source_context,
                "operator_status": status,
                "action": action,
                "comparison_usable": status == "OPERATOR_COMPARE_PENDING",
                "equivalence_approved": False,
                "promotion_authority": False,
            }
        )
    again = inspect_candidate_review_readiness(
        match_store,
        promotion_store,
        run_id=run_id,
        claim_candidate_id=claim_candidate_id,
    )
    current_candidate_source = _target_source(
        target_source_store.source_context("CLAIM_CANDIDATE", claim_candidate_id),
        target_type="CLAIM_CANDIDATE",
        target_id=claim_candidate_id,
        content_id=content_id,
        provenance_key=source["passage_id"],
    )
    if packet != again or candidate_source != current_candidate_source or any(
        _target_source(
            target_source_store.source_context(*key),
            target_type=key[0],
            target_id=key[1],
            content_id=by_target[key][0],
            provenance_key=by_target[key][1],
        )
        != prior
        for key, prior in initial_sources.items()
    ):
        raise ValueError("DP418_COMPARISON_CHANGED_DURING_READ")
    blockers = list(packet["promotion_blockers"])
    if candidate_held:
        blockers.append("DP418_CANDIDATE_SOURCE_HELD")
    if candidate_source is None:
        blockers.append("DP418_CANDIDATE_SOURCE_UNAVAILABLE")
    elif candidate_source_rights_blocked:
        blockers.append("DP418_CANDIDATE_SOURCE_RIGHTS")
    if any(not row["comparison_usable"] for row in comparisons):
        blockers.append("DP418_MATCH_SOURCE_COMPARISON_INCOMPLETE")
    return {
        "contract_version": DP418_COMPARISON_VERSION,
        "private_only": True,
        "currentness": packet["currentness"],
        "run_id": packet["run_id"],
        "claim_candidate_id": claim_candidate_id,
        "input_fingerprint": packet["input_fingerprint"],
        "review_context_sha256": packet["review_context_sha256"],
        "matching_version": packet["matching_version"],
        "candidate": {
            "content_id": content_id,
            "passage_id": source["passage_id"],
            "capture_id": source["capture_id"],
            "capture_sha256": source["capture_sha256"],
            "capture_status": original["capture_status"],
            "capture_hold_status": original["capture_hold_status"],
            "rights_status": (
                candidate_source["rights_status"]
                if candidate_source is not None else "UNAVAILABLE"
            ),
        },
        "comparisons": tuple(comparisons),
        "promotion_blockers": tuple(dict.fromkeys(blockers)),
        "review_authority": False,
        "promotion_authority": False,
        "publication_authority": False,
    }


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


def render_candidate_comparison_workspace(model: Mapping[str, object]) -> bytes:
    """Static operator-facing source comparison; no form, action or approval."""
    if (
        not isinstance(model, Mapping)
        or model.get("contract_version") != DP418_COMPARISON_VERSION
        or model.get("private_only") is not True
        or any(
            model.get(flag) is not False
            for flag in (
                "review_authority",
                "promotion_authority",
                "publication_authority",
            )
        )
        or model.get("currentness") not in {"CURRENT", "STALE"}
        or not isinstance(model.get("candidate"), Mapping)
        or not isinstance(model.get("comparisons"), tuple)
        or len(model["comparisons"]) > 30
    ):
        raise ValueError("DP418_COMPARISON_VIEW_INVALID")
    original = model["candidate"]
    header = (
        "<p>Candidate "
        + _reference(model.get("claim_candidate_id"))
        + " · Run "
        + _reference(model.get("run_id"))
        + " · Matching "
        + escape(str(model.get("matching_version")))
        + "</p>"
        + "<p>Content "
        + _reference(original.get("content_id"))
        + " · Passage "
        + _reference(original.get("passage_id"))
        + " · Capture "
        + _reference(original.get("capture_id"))
        + " · SHA "
        + _hash(original.get("capture_sha256"))
        + " · Diritti fonte "
        + _codes([original.get("rights_status")])
        + "</p>"
        + "<p role='status'>Attualità: "
        + escape(str(model["currentness"]))
        + " · Blocchi pre-promozione: "
        + _codes(model.get("promotion_blockers"))
        + "</p>"
    )
    comparisons: list[str] = []
    for row in model["comparisons"]:
        if not isinstance(row, Mapping) or row.get("relation") not in _CLASSES:
            raise ValueError("DP418_COMPARISON_VIEW_RESULT_INVALID")
        if row.get("comparison_usable") not in {True, False} or any(
            row.get(flag) is not False
            for flag in ("equivalence_approved", "promotion_authority")
        ):
            raise ValueError("DP418_COMPARISON_VIEW_AUTHORITY_INVALID")
        kind = row["relation"]
        source = row.get("source")
        if source is None:
            source_line = "<p>Fonte target non recuperata; confronto bloccato.</p>"
        elif isinstance(source, Mapping):
            source_line = (
                "<p>Content "
                + _reference(source.get("content_id"))
                + " · Passage "
                + _reference(source.get("passage_id"))
                + " · Capture "
                + _reference(source.get("capture_id"))
                + " · SHA "
                + _hash(source.get("capture_sha256"))
                + " · Diritti "
                + _codes([source.get("rights_status")])
                + "</p>"
            )
        else:
            raise ValueError("DP418_COMPARISON_VIEW_SOURCE_INVALID")
        comparisons.append(
            "<article><h3>"
            + _reference(row.get("target_id"))
            + " · "
            + escape(kind)
            + "</h3>"
            + "<p>"
            + escape(_CLASS_EXPLANATIONS[kind])
            + "</p>"
            + source_line
            + "<dl><dt>Metodo / versione</dt><dd>"
            + escape(str(row.get("matching_method")))
            + " / "
            + escape(str(row.get("matching_version")))
            + "</dd>"
            + "<dt>Elementi a favore</dt><dd>"
            + _codes(row.get("supporting_feature_codes"))
            + "</dd>"
            + "<dt>Elementi contrari</dt><dd>"
            + _codes(row.get("contradicting_feature_codes"))
            + "</dd>"
            + "<dt>Stato / azione</dt><dd>"
            + _codes([row.get("operator_status"), row.get("action")])
            + "</dd></dl><p>Proposta non approvata; nessuna equivalenza o promozione autorizzata.</p></article>"
        )
    return (
        "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow,noarchive'>"
        "<title>Studio locale · confronto candidati</title>"
        "<style>body{font:1rem/1.6 system-ui,sans-serif;max-width:72rem;margin:auto;padding:1rem}"
        "main{min-width:0}article{border:1px solid #637081;padding:1rem;margin:1rem 0}"
        "p,dd{overflow-wrap:anywhere}dt{font-weight:600}dd{margin:0 0 1rem}</style></head>"
        "<body><main><h1>Confronto privato con risultati persistiti</h1>"
        + header
        + "<section aria-label='Confronti fonte e match'>"
        + "".join(comparisons)
        + "</section></main></body></html>"
    ).encode("utf-8")


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
    if (
        not isinstance(packet, Mapping)
        or packet.get("contract_version") != STUDIO_CANDIDATE_REVIEW_VERSION
        or packet.get("private_only") is not True
        or packet.get("review_authority") is not False
        or packet.get("publication_authority") is not False
        or packet.get("promotion_authority") is not False
        or packet.get("currentness") not in {"CURRENT", "STALE", "UNVERIFIED"}
        or not isinstance(packet.get("results"), list)
        or len(packet["results"]) > 30
    ):
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
            "<li>Passage "
            + _reference(row.get("passage_id"), optional=True)
            + " · Capture "
            + _reference(row.get("capture_id"), optional=True)
            + " · Segmento "
            + _reference(row.get("segment_id"), optional=True)
            + " · SHA "
            + _hash(row.get("capture_sha256"), optional=True)
            + "</li>"
        )
    matches: list[str] = []
    for row in packet["results"]:
        if not isinstance(row, Mapping):
            raise ValueError("STUDIO_REVIEW_UI_RESULT_INVALID")
        cls = row.get("match_class")
        method = row.get("matching_method")
        disposition = row.get("suggested_disposition")
        if (
            cls not in _CLASSES
            or method not in _METHODS
            or disposition not in _DISPOSITIONS
        ):
            raise ValueError("STUDIO_REVIEW_UI_RESULT_CLASS_INVALID")
        matches.append(
            "<details><summary>"
            + escape(cls)
            + " · "
            + _reference(row.get("target_id"))
            + "</summary><dl>"
            + "<dt>Significato del confronto</dt><dd>"
            + escape(_CLASS_EXPLANATIONS[cls])
            + "</dd>"
            + "<dt>Risultato</dt><dd>"
            + _reference(row.get("result_id"))
            + "</dd>"
            + "<dt>Tipo target</dt><dd>"
            + _codes([row.get("target_type")])
            + "</dd>"
            + "<dt>Metodo</dt><dd>"
            + escape(method)
            + "</dd>"
            + "<dt>Proposta automatica, non approvata</dt><dd>"
            + escape(disposition)
            + "</dd>"
            + "<dt>Cluster proposto</dt><dd>"
            + _reference(row.get("proposition_cluster_id"), optional=True)
            + "</dd>"
            + "<dt>Elementi a favore</dt><dd>"
            + _codes(row.get("supporting_feature_codes"))
            + "</dd>"
            + "<dt>Elementi contrari</dt><dd>"
            + _codes(row.get("contradicting_feature_codes"))
            + "</dd>"
            + "</dl></details>"
        )
    handoff_text = "Nessuna richiesta di revisione registrata."
    if persisted_handoff is not None:
        if (
            not isinstance(persisted_handoff, Mapping)
            or persisted_handoff.get("contract_version") != REVIEW_HANDOFF_VERSION
            or persisted_handoff.get("status") != "QUEUED_FOR_HUMAN_REVIEW"
            or persisted_handoff.get("candidate_id") != packet["claim_candidate_id"]
            or persisted_handoff.get("run_id") != packet["run_id"]
            or persisted_handoff.get("input_fingerprint") != packet["input_fingerprint"]
            or persisted_handoff.get("review_authority") is not False
            or persisted_handoff.get("promotion_authority") is not False
            or persisted_handoff.get("publication_authority") is not False
        ):
            raise ValueError("STUDIO_REVIEW_UI_HANDOFF_INVALID")
        handoff_text = (
            "Richiesta persistita "
            + _reference(persisted_handoff.get("handoff_id"))
            + ": "
            + escape(str(persisted_handoff["status"]))
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
        "<ul>"
        + ("".join(sources) or "<li>Nessun passaggio verificato.</li>")
        + "</ul></section><section aria-labelledby='matches'><h2 id='matches'>Candidati e cluster</h2>"
        + ("".join(matches) or "<p>Nessun risultato.</p>")
        + "</section></div>"
        "<section aria-label='Coda revisione'><h2>Stato della richiesta</h2><p>"
        + handoff_text
        + "</p></section></main></body></html>"
    ).encode("utf-8")


__all__ = [
    "DP418_COMPARISON_VERSION",
    "PersistedTargetSourceReader",
    "build_candidate_comparison_read_model",
    "render_candidate_comparison_workspace",
    "render_candidate_review_workspace",
]
