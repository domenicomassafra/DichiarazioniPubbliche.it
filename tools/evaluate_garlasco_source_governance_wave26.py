#!/usr/bin/env python3
"""Review-only primary-source/rights packet for DP-214/215/233 Wave26.

No networking, provider use, SQL, DB writes, source-body download, or body
retention. Evidence URLs were manually observed; all grants remain UNKNOWN.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
WAVE22 = ROOT / "config/garlasco-source-feasibility-wave22.v1.json"
WAVE26 = ROOT / "config/garlasco-source-governance-wave26.v1.json"
MAX_BYTES = 128_000

# Identity and applicable page-specific rights observations, reviewed against
# external primary pages on 2026-10-10. Updating a value needs new human proof.
RIGHTS_OBSERVATIONS = {
    "lead:garlasco:burnout-2026-01": "NO_ITEM_SPECIFIC_LICENSE_VERIFIED",
    "lead:garlasco:mediaset-interview": "AUTOMATED_SCRAPING_AND_AI_TRAINING_EXPRESSLY_PROHIBITED",
    "lead:garlasco:raiplay-farwest-2026-04": "NO_ITEM_SPECIFIC_LICENSE_VERIFIED",
    "lead:garlasco:ansa-report-2026-05": "REPRODUCTION_RESERVED",
    "lead:garlasco:ilticino-communique-2026-09": "NO_ITEM_SPECIFIC_LICENSE_VERIFIED",
    "lead:garlasco:rai-legal-communique-2026-05": "NO_ITEM_SPECIFIC_LICENSE_VERIFIED",
    "lead:garlasco:lanazione-interview-2026-05": "REPRODUCTION_RESERVED",
    "lead:garlasco:procura-pavia-communique-2026-09": "OFFICIAL_SITE_LEGAL_PAGE_PLACEHOLDER_NOT_A_LICENSE",
}
RIGHTS_PROOF_URLS = {
    "lead:garlasco:burnout-2026-01": "https://podcasts.apple.com/it/podcast/burnout-ep-16-garlasco-ha-una-regia/id1772323196?i=1000747146238",
    "lead:garlasco:mediaset-interview": "https://mediasetinfinity.mediaset.it/video/quartogrado/caso-garlasco-lintervista-a-roberta-bruzzone_F314087301028C11",
    "lead:garlasco:raiplay-farwest-2026-04": "https://www.raiplay.it/video/2026/04/Cappa-Garlasco-tra-nuovi-rilievi-e-audio-sospetti---FarWest---21042026-13577568-35e2-4786-b6f6-b0b2e3044ab8.html",
    "lead:garlasco:ansa-report-2026-05": "https://www.ansa.it/lombardia/notizie/2026/05/07/procura-di-pavia-chiude-le-indagini-su-garlasco-chiara-uccisa-da-sempio_5838528d-4418-49e3-8047-613fa7b0a63e.html",
    "lead:garlasco:ilticino-communique-2026-09": "https://ilticino.it/2026/09/28/dlelitto-di-garlasco-notificato-dalla-procura-di-pavia-lavviso-di-chiusura-delle-indagini/",
    "lead:garlasco:rai-legal-communique-2026-05": "https://www.chilhavisto.rai.it/dl/clv/News/ContentItem-bbe55c13-870b-42f8-9eb3-3300927e12a0.html",
    "lead:garlasco:lanazione-interview-2026-05": "https://www.lanazione.it/cronaca/bruzzone-qjyn2h3v",
    "lead:garlasco:procura-pavia-communique-2026-09": "https://procura-pavia.giustizia.it/it/note_legali.page",
}
SOURCE_RELATIONS = {
    "lead:garlasco:burnout-2026-01": "DISTRIBUTOR_LINKS_PUBLISHER_EPISODE",
    "lead:garlasco:mediaset-interview": "BROADCASTER_FIRST_PARTY_PAGE",
    "lead:garlasco:raiplay-farwest-2026-04": "BROADCASTER_FIRST_PARTY_PAGE",
    "lead:garlasco:ansa-report-2026-05": "ORIGINAL_NEWSROOM_REPORT_NOT_OFFICIAL_ACT",
    "lead:garlasco:ilticino-communique-2026-09": "PROPOSED_DERIVATION_OF_OFFICIAL_DOCUMENT",
    "lead:garlasco:rai-legal-communique-2026-05": "NEWSROOM_REPRODUCES_UNLOCATED_LAWYER_STATEMENT",
    "lead:garlasco:lanazione-interview-2026-05": "DIRECT_NEWSPAPER_INTERVIEW",
    "lead:garlasco:procura-pavia-communique-2026-09": "ORIGINAL_OFFICIAL_PROCEDURAL_COMMUNIQUE",
}
OFFICIAL_ID = "lead:garlasco:procura-pavia-communique-2026-09"
REPRINT_ID = "lead:garlasco:ilticino-communique-2026-09"
UNRESOLVED_ID = "lead:garlasco:rai-legal-communique-2026-05"
OFFICIAL_PDF = "https://procura-pavia.giustizia.it/resources/cms/documents/Comunicato_Stampa_28.09.2026.pdf"
OFFICIAL_INDEX = "https://procura-pavia.giustizia.it/it/comunicati_stampa.page"

PARLIAMENTARY_BINDINGS = {
    "wave26:camera:leg19:sed607": (
        "CAMERA", 19, 607, "2026-02-03", "Vittoria Baldino",
        "VITTORIA BALDINO (M5S)",
        "https://documenti.camera.it/leg19/resoconti/assemblea/html/sed0607/stenografico.htm",
        "https://webtv.camera.it/evento/30272/589615",
        "CAMERA_WEBTV_NONCOMMERCIAL_INFORMATION_USE_LIMITS",
    ),
    "wave26:camera:leg19:sed703": (
        "CAMERA", 19, 703, "2026-08-04", "Andrea Orsini",
        "ANDREA ORSINI (FI-PPE)",
        "https://www.camera.it/leg19/410?idSeduta=0703&tipo=stenografico",
        "https://webtv.camera.it/archivio?NumeroLegislatura=19&NumeroSeduta=703",
        "CAMERA_WEBTV_NONCOMMERCIAL_INFORMATION_USE_LIMITS",
    ),
    "wave26:senato:leg19:sed441": (
        "SENATO", 19, 441, "2026-07-23", "Luca Pirondini",
        "PIRONDINI (M5S)",
        "https://www.senato.it/show-doc?id=1516683&idoggetto=0&leg=19&part=doc_dc&tipodoc=Resaula",
        None, "SENATO_CC_BY_3_DATASET_SCOPE_ONLY_NOT_SPEECH_GRANT",
    ),
}

EXPECTED_REVIEW_KEYS = {
    "lead_id", "issuer_or_publisher", "original_status", "original_url",
    "identity_evidence_url", "observed_date", "rights_evidence_status",
    "rights_evidence_url", "source_relation", "dependent_on_lead_id",
    "review_action", "rights_status",
}
EXPECTED_PROBE_KEYS = {
    "probe_id", "chamber", "legislature", "session", "session_date",
    "transcript_url", "video_index_url", "speaker_label",
    "speaker_evidence_label", "spoken_topic_reference", "source_role",
    "transcript_version_status", "segment_time_verified",
    "speaker_approval_recorded", "rights_evidence_status",
    "rights_evidence_url", "rights_status",
}
_ALLOWED_ORIGIN = {
    "PUBLISHER_EPISODE_PAGE_LINKED", "BROADCASTER_PAGE_OBSERVED",
    "NEWSROOM_FIRST_PARTY_ARTICLE", "OFFICIAL_DOCUMENT_LOCATED_DERIVATION_UNREVIEWED",
    "THIRD_PARTY_STATEMENT_ORIGINAL_UNLOCATED", "NEWSPAPER_ORIGINAL_INTERVIEW",
    "FIRST_PARTY_GOVERNMENT_DOCUMENT_INDEXED",
}
_ALLOWED_RELATION = {
    "DISTRIBUTOR_LINKS_PUBLISHER_EPISODE", "BROADCASTER_FIRST_PARTY_PAGE",
    "ORIGINAL_NEWSROOM_REPORT_NOT_OFFICIAL_ACT", "PROPOSED_DERIVATION_OF_OFFICIAL_DOCUMENT",
    "NEWSROOM_REPRODUCES_UNLOCATED_LAWYER_STATEMENT", "DIRECT_NEWSPAPER_INTERVIEW",
    "ORIGINAL_OFFICIAL_PROCEDURAL_COMMUNIQUE",
}
_ALLOWED_REVIEW_ACTIONS = {
    "REVIEW_EPISODE_METADATA_AND_CREATOR_PERMISSION", "LINK_ONLY_UNTIL_PUBLISHER_PERMISSION",
    "REVIEW_BROADCAST_RIGHTS_AND_ATTRIBUTION", "LINK_ONLY_OR_SEEK_EDITORIAL_LICENSE",
    "REVIEW_SOURCE_DERIVATION_EQUIVALENCE", "FIND_LAWYER_ORIGINAL_BEFORE_STATEMENT_ATTRIBUTION",
    "REVIEW_PERMITTED_PRIVATE_USE_WITH_INSTITUTION",
}


class PacketBlocked(ValueError):
    """Operator-visible fail-closed reason, never echoes unsafe source text."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise PacketBlocked(f"WAVE26_{reason}")


def _valid_date(value: object, *, observed_on: date) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed.isoformat() == value and parsed <= observed_on


def _unique_keys(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, "DUPLICATE_JSON_KEY")
        value[key] = item
    return value


def read_packet_file(path: Path) -> dict:
    """Bounded local JSON load; no URLs are accessed and no content is stored."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        _require(len(raw) <= MAX_BYTES, "FILE_TOO_LARGE")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PacketBlocked("WAVE26_FILE_INVALID") from exc
    _require(isinstance(data, dict), "FILE_INVALID")
    return data


def evaluate_packet(wave22: dict, wave26: dict) -> dict:
    """Require verified URL bindings and output *review tasks*, never grants."""
    _require(isinstance(wave22, dict) and wave22.get("version") == "garlasco-source-feasibility-wave22-v1", "BASELINE_INVALID")
    _require(isinstance(wave26, dict) and set(wave26) == {
        "version", "observed_on", "authority", "original_wave22_source",
        "rights_status", "source_reviews", "parliamentary_probes",
    }, "PACKET_INVALID")
    _require(wave26["version"] == "garlasco-source-governance-wave26-v1"
             and wave26["authority"] == "PUBLIC_METADATA_ONLY_NO_RETENTION"
             and wave26["original_wave22_source"] == "config/garlasco-source-feasibility-wave22.v1.json", "PACKET_INVALID")
    _require(wave26["rights_status"] == "UNKNOWN", "RIGHTS_UNREVIEWED_REQUIRED")
    _require(_valid_date(wave26["observed_on"], observed_on=date.today()), "OBSERVED_DATE_INVALID")
    observed_on = date.fromisoformat(wave26["observed_on"])
    source_rows = wave26["source_reviews"]
    probe_rows = wave26["parliamentary_probes"]
    _require(isinstance(source_rows, list) and len(source_rows) == 8, "SOURCE_COUNT_INVALID")
    _require(isinstance(probe_rows, list) and len(probe_rows) == 3, "PARLIAMENTARY_COUNT_INVALID")
    wave22_rows = wave22.get("verified_existing_leads", []) + wave22.get("additional_verified_leads", [])
    _require(len(wave22_rows) == 8, "BASELINE_COUNT_INVALID")
    original_by_id = {r["id"]: r for r in wave22_rows}
    _require(set(original_by_id) == set(RIGHTS_OBSERVATIONS), "BASELINE_IDENTITIES_INVALID")
    source_by_id = {r.get("lead_id"): r for r in source_rows if isinstance(r, dict)}
    _require(len(source_by_id) == len(source_rows)
             and set(source_by_id) == set(original_by_id), "SOURCE_IDENTITIES_INVALID")
    review_queue: list[dict[str, str]] = []
    for lead_id in sorted(source_by_id):
        row = source_by_id[lead_id]
        original = original_by_id[lead_id]
        _require(set(row) == EXPECTED_REVIEW_KEYS, "SOURCE_SCHEMA_INVALID")
        _require(row["rights_status"] == "UNKNOWN", "RIGHTS_UNREVIEWED_REQUIRED")
        _require(row["rights_evidence_status"] == RIGHTS_OBSERVATIONS[lead_id], "RIGHTS_EVIDENCE_INVALID")
        _require(row["rights_evidence_url"] == RIGHTS_PROOF_URLS[lead_id], "RIGHTS_PROOF_URL_INVALID")
        _require(row["source_relation"] == SOURCE_RELATIONS[lead_id], "SOURCE_SEMANTICS_INVALID")
        _require(row["original_url"] == original["original_url"]
                 and row["observed_date"] == original["observed_date"]
                 and _valid_date(row["observed_date"], observed_on=observed_on), "BASELINE_BINDING_INVALID")
        _require(row["original_status"] in _ALLOWED_ORIGIN
                 and row["source_relation"] in _ALLOWED_RELATION
                 and row["review_action"] in _ALLOWED_REVIEW_ACTIONS
                 and isinstance(row["issuer_or_publisher"], str)
                 and 1 <= len(row["issuer_or_publisher"].strip()) <= 180, "SOURCE_METADATA_INVALID")
        _require(row["identity_evidence_url"] in original["evidence_urls"]
                 and isinstance(row["rights_evidence_url"], str)
                 and row["rights_evidence_url"].startswith("https://"), "PROOF_URL_INVALID")
        if lead_id == REPRINT_ID:
            _require(row["dependent_on_lead_id"] == OFFICIAL_ID
                     and row["original_url"] == OFFICIAL_PDF
                     and row["source_relation"] == "PROPOSED_DERIVATION_OF_OFFICIAL_DOCUMENT", "DERIVATION_MISMATCH")
        elif lead_id == OFFICIAL_ID:
            _require(row["original_url"] == OFFICIAL_PDF
                     and row["identity_evidence_url"] == OFFICIAL_INDEX
                     and row["rights_evidence_status"] == "OFFICIAL_SITE_LEGAL_PAGE_PLACEHOLDER_NOT_A_LICENSE", "OFFICIAL_ORIGIN_INVALID")
            _require(row["dependent_on_lead_id"] is None, "DERIVATION_MISMATCH")
        else:
            _require(row["dependent_on_lead_id"] is None, "DERIVATION_MISMATCH")
        if lead_id == UNRESOLVED_ID:
            _require(row["original_url"] is None
                     and row["original_status"] == "THIRD_PARTY_STATEMENT_ORIGINAL_UNLOCATED", "ORIGINAL_UNLOCATED")
        review_queue.append({
            "id": lead_id, "type": "PUBLIC_SOURCE_CANDIDATE",
            "next_action": "HUMAN_" + row["review_action"],
            "can_capture_body": "NO", "can_call_provider": "NO",
        })

    probe_by_id = {r.get("probe_id"): r for r in probe_rows if isinstance(r, dict)}
    _require(len(probe_by_id) == len(probe_rows)
             and set(probe_by_id) == set(PARLIAMENTARY_BINDINGS), "PARLIAMENTARY_IDENTITIES_INVALID")
    chamber_counts = Counter()
    official_text_video_pairs = 0
    for probe_id in sorted(probe_by_id):
        row = probe_by_id[probe_id]
        _require(set(row) == EXPECTED_PROBE_KEYS, "PARLIAMENTARY_SCHEMA_INVALID")
        _require(row["rights_status"] == "UNKNOWN", "RIGHTS_UNREVIEWED_REQUIRED")
        _require(row["segment_time_verified"] is False
                 and row["speaker_approval_recorded"] is False, "PARLIAMENTARY_APPROVAL_UNPROVEN")
        chamber, leg, number, day, speaker, label, transcript, video, rights = PARLIAMENTARY_BINDINGS[probe_id]
        _require((row["chamber"], row["legislature"], row["session"], row["session_date"],
                  row["speaker_label"], row["speaker_evidence_label"], row["transcript_url"],
                  row["video_index_url"], row["rights_evidence_status"])
                 == (chamber, leg, number, day, speaker, label, transcript, video, rights), "PARLIAMENTARY_BINDING_INVALID")
        _require(row["spoken_topic_reference"] == "Garlasco"
                 and row["source_role"] == "OFFICIAL_PARLIAMENTARY_SPEECH"
                 and row["rights_evidence_url"] in (video, "https://dati.senato.it/sito/19?testo_generico=24")
                 and row["transcript_version_status"].startswith("OFFICIAL_"), "PARLIAMENTARY_BINDING_INVALID")
        _require(_valid_date(day, observed_on=observed_on), "PARLIAMENTARY_DATE_INVALID")
        chamber_counts[chamber] += 1
        if video is not None:
            official_text_video_pairs += 1
        review_queue.append({
            "id": probe_id, "type": "DP233_PARLIAMENTARY_SOURCE_CANDIDATE",
            "next_action": "HUMAN_REVIEW_PARLIAMENTARY_TRANSCRIPT_VIDEO_RIGHTS_SPEAKER_TIME",
            "can_capture_body": "NO", "can_call_provider": "NO",
        })
    return {
        "version": "garlasco-source-governance-wave26-report-v1",
        "status": "GOVERNED_METADATA_REVIEW_READY_NOT_INGESTION",
        "wave22_existing_candidates": len(source_rows),
        "new_parliamentary_document_candidates": len(probe_rows),
        "official_source_candidates": 1 + len(probe_rows),
        "matched_camera_transcript_video_sessions": official_text_video_pairs,
        "unpaired_senato_transcript_sessions": chamber_counts["SENATO"],
        "unresolved_original_statement_sources": 1,
        "rights_status": "UNKNOWN",
        "source_reuse_permissions_proven": 0,
        "source_body_capture_authorized": 0,
        "provider_call_authorized": 0,
        "persisted_discovery_hits_proven": 0,
        "operator_review_queue": review_queue,
        "dp214_215_233_acceptance_proven": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline, governed Wave26 sources and rights review packet")
    parser.add_argument("--wave22", type=Path, default=WAVE22)
    parser.add_argument("--wave26", type=Path, default=WAVE26)
    args = parser.parse_args(argv)
    try:
        report = evaluate_packet(read_packet_file(args.wave22), read_packet_file(args.wave26))
    except PacketBlocked as exc:
        print(json.dumps({"status": "BLOCKED", "reason_code": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
