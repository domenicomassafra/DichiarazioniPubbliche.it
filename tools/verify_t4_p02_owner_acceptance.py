#!/usr/bin/env python3
"""Reproduce the five T4-p02 owner acceptances on one authentic Garlasco speech.

Reads one official Camera page, prepares a real exact-text candidate and checks
an isolated private JSON roundtrip. Never publishes, changes the operational DB,
downloads video, or treats an editorial quotation decision as a bulk fetch grant.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

from dichiarazioni_pubbliche.corpus_repository import (
    ContentCaptureRecord,
    PassageRecord,
    StatementCandidateRecord,
    deterministic_corpus_id,
    normalize_content_capture,
    normalize_passage,
    normalize_statement_candidate,
)
from dichiarazioni_pubbliche.parliamentary_official_adapter import normalize_parliamentary_official_record
from evaluate_garlasco_source_governance_wave26 import WAVE22, WAVE26, evaluate_packet, read_packet_file

CAMERA_URL = "https://documenti.camera.it/leg19/resoconti/assemblea/html/sed0607/stenografico.htm"
LEAD_ID = "wave26:camera:leg19:sed607"
PARAGRAPH_ID = "iv.289"
PRECEDING_SPEAKER_ID = "sed0607.stenografico.tit00100.sub00010.int00340"
SPEAKER_TITLE = "Vai alla scheda personale: BALDINO Vittoria"
EXCERPT_FIRST = "Stanno strumentalizzando i casi di cronaca nera"
EXCERPT_LAST = "non ci sarà più un caso Garlasco."
MAX_HTML_BYTES = 1_000_000


class _Paragraphs(HTMLParser):
    """Capture rendered official paragraph text and the speaker-link title."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[str, str, str, tuple[str, ...]]] = []
        self.active: dict | None = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "p":
            self.active = {"id": attributes.get("id", ""), "class": attributes.get("class", ""),
                           "parts": [], "titles": []}
        elif tag == "a" and self.active is not None and attributes.get("title"):
            self.active["titles"].append(attributes["title"])

    def handle_data(self, data):
        if self.active is not None:
            self.active["parts"].append(data)

    def handle_endtag(self, tag):
        if tag == "p" and self.active is not None:
            row = self.active
            self.rows.append((row["id"], row["class"], "".join(row["parts"]).strip(),
                              tuple(row["titles"])))
            self.active = None


def verify_source(html_bytes: bytes, inventory: list[dict], *, observed_at: str) -> dict:
    """Make an independently replayable held candidate from one catalogued source."""
    if not html_bytes or len(html_bytes) > MAX_HTML_BYTES:
        raise ValueError("CAMERA_SOURCE_SIZE_INVALID")
    source_sha = hashlib.sha256(html_bytes).hexdigest()
    parsed = _Paragraphs()
    parsed.feed(html_bytes.decode("utf-8"))
    matches = [i for i, row in enumerate(parsed.rows) if row[0] == PARAGRAPH_ID]
    if len(matches) != 1 or matches[0] == 0:
        raise ValueError("CAMERA_EXACT_PARAGRAPH_MISSING")
    index = matches[0]
    previous, target = parsed.rows[index - 1], parsed.rows[index]
    if (previous[0] != PRECEDING_SPEAKER_ID or SPEAKER_TITLE not in previous[3]
            or target[1] != "interventoVirtuale"):
        raise ValueError("CAMERA_SPEAKER_CONTEXT_MISMATCH")
    text = target[2]
    start = text.find(EXCERPT_FIRST)
    end = text.find(EXCERPT_LAST, start) + len(EXCERPT_LAST)
    if start < 0 or end <= start or text.count(EXCERPT_FIRST) != 1:
        raise ValueError("CAMERA_EXACT_WORDING_MISMATCH")
    quote = text[start:end]
    if quote.count("Garlasco") != 2:
        raise ValueError("CAMERA_QUOTE_SCOPE_MISMATCH")
    lead = next((row for row in inventory if row["id"] == LEAD_ID), None)
    if (lead is None or lead["url"] != CAMERA_URL
            or lead["speaker_label_from_official_record"] != "Vittoria Baldino"
            or not lead["video_session_url"]):
        raise ValueError("CAMERA_CATALOG_BINDING_MISMATCH")
    official = normalize_parliamentary_official_record({
        "chamber": "CAMERA",
        "sitting": {"id": "camera:leg19:sed607", "date": "2026-02-03"},
        "speaker": {"id": "camera:persona:307435", "name": "Vittoria Baldino", "role": "deputata"},
        "statement": {"id": "camera:leg19:sed607:iv289:garlasco", "speaker_id": "camera:persona:307435",
                      "date": "2026-02-03", "text": quote, "start_char": start, "end_char": end},
        "transcript": {"url": CAMERA_URL, "source_version": source_sha, "text": text},
        # A WebTV session index is known; there is no verified excerpt timecode.
        "video": None,
    })
    content_id = "content:camera:leg19:sed607:garlasco:iv289"
    capture_id = deterministic_corpus_id("capture", content_id, source_sha)
    passage_id = deterministic_corpus_id("passage", capture_id, str(start), str(end),
                                         hashlib.sha256(quote.encode("utf-8")).hexdigest())
    capture = ContentCaptureRecord(
        id=capture_id, content_id=content_id, observed_at=observed_at,
        final_url=CAMERA_URL, content_sha256=source_sha,
        retrieval_method="OFFICIAL_CAMERA_HTTPS_BOUNDED", retrieval_version="t4-p02-v1",
        media_type="text/html", body_ref=None, parser_method="CAMERA_OFFICIAL_PARAGRAPH",
        parser_version="t4-p02-v1", rights_status="UNKNOWN", retention_class="EPHEMERAL",
        hold_status="RIGHTS_HOLD", status="QUARANTINED",
        metadata={"catalog_lead_id": LEAD_ID, "official_provenance_id": official.provenance_id,
                  "html_paragraph_id": PARAGRAPH_ID, "body_not_retained": True},
    )
    passage = PassageRecord(
        id=passage_id, content_id=content_id, capture_id=capture_id,
        selector_type="TEXT_POSITION", start_char=start, end_char=end,
        text_sha256=hashlib.sha256(quote.encode("utf-8")).hexdigest(),
        private_text=quote, language="it", extraction_method="CAMERA_OFFICIAL_PARAGRAPH",
        extraction_version="t4-p02-v1", metadata={"html_paragraph_id": PARAGRAPH_ID},
    )
    statement = StatementCandidateRecord(
        id=deterministic_corpus_id("statement-candidate", passage_id),
        content_id=content_id, passage_ids=(passage_id,),
        statement_text_hash=passage.text_sha256, normalized_statement=quote,
        extraction_version="t4-p02-v1", speaker_person_id=None,
        attribution_method=None, status="HELD",
        metadata={"official_speaker_name": official.speaker.speaker_name,
                  "official_speaker_ref": official.speaker.speaker_id,
                  "speaker_review_status": "PENDING_PRIVATE_REVIEW",
                  "official_provenance_id": official.provenance_id},
    )
    with tempfile.TemporaryDirectory(prefix="t4-p02-private-") as private_directory:
        private_file = Path(private_directory) / "camera-private-candidate.json"
        private_file.write_text(json.dumps({"capture": capture.to_dict(), "passage": passage.to_dict(),
                                            "statement": statement.to_dict()}, ensure_ascii=False), encoding="utf-8")
        saved = json.loads(private_file.read_text(encoding="utf-8"))
        recovered = (normalize_content_capture(saved["capture"]),
                     normalize_passage(saved["passage"]),
                     normalize_statement_candidate(saved["statement"]))
        if recovered != (capture, passage, statement):
            raise ValueError("CAMERA_PRIVATE_READBACK_MISMATCH")
        if (text[passage.start_char:passage.end_char] != passage.private_text
                or passage.private_text != statement.normalized_statement
                or hashlib.sha256(passage.private_text.encode("utf-8")).hexdigest() != passage.text_sha256):
            raise ValueError("CAMERA_EXACT_QUOTE_READBACK_MISMATCH")
        private_record_sha = hashlib.sha256(private_file.read_bytes()).hexdigest()
    return {
        "collection_source_lead": LEAD_ID, "collection_context": "research:garlasco",
        "source_url": CAMERA_URL, "source_html_sha256": source_sha,
        "source_date": official.session.sitting_date,
        "speaker_as_recorded": official.speaker.speaker_name,
        "official_speaker_id": official.speaker.speaker_id,
        "transcript_paragraph": PARAGRAPH_ID,
        "video_session_url": lead["video_session_url"],
        "video_excerpt_timecode": None,
        "quote_text_sha256": passage.text_sha256,
        "quote_start_char": start, "quote_end_char": end,
        "quote_character_count": len(quote),
        "private_capture_status": capture.status,
        "private_candidate_status": statement.status,
        "private_record_readback_sha256": private_record_sha,
        "private_temp_deleted": not private_file.exists(),
        "published": False, "production_db_changed": False,
    }


def run() -> dict:
    catalog = evaluate_packet(read_packet_file(WAVE22), read_packet_file(WAVE26))
    request = Request(CAMERA_URL, headers={"User-Agent": "DichiarazioniPubbliche-T4-p02-owner-proof"})
    with urlopen(request, timeout=18) as response:
        if response.status != 200 or response.url != CAMERA_URL:
            raise ValueError("CAMERA_OFFICIAL_SOURCE_FETCH_INVALID")
        source = response.read(MAX_HTML_BYTES + 1)
    result = verify_source(source, catalog["source_inventory"],
                           observed_at=datetime.now(timezone.utc).isoformat())
    return {"status": "OWNER_ACCEPTANCE_PRIVATE_PILOT_VERIFIED", "catalog_items": len(catalog["source_inventory"]),
            "catalog_originals_and_derivatives_distinguished": True,
            "source_usage_decisions_present": all(
                row["rights"].get("quote_exact_excerpt_with_source_link")
                and row["rights"].get("fetch_source_body")
                and row["rights"].get("analyze_or_translate_body")
                for row in catalog["source_inventory"]), **result}


if __name__ == "__main__":
    try:
        print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "reason_code": str(exc) if isinstance(exc, ValueError)
                          else "CAMERA_OWNER_PROOF_ERROR"}), file=sys.stderr)
        raise SystemExit(2) from None
