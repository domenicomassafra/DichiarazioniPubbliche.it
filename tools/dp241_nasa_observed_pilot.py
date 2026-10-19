"""Run one bounded DP-241 pilot against NASA's public Apollo 11 originals.

The two hosts and three GETs are fixed by the operator, not model-generated.
No media/audio is downloaded, no paid search and no rights/review grant occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord, PassageRecord
from dichiarazioni_pubbliche.original_source_investigation_v1 import (
    LocalSourceRecoveryTimelineJournal, OriginalCandidateProof, RecoveryMethod,
    RecoveryReceipt, SourceRecoveryTarget, make_recovery_plan,
)
from dichiarazioni_pubbliche.original_source_observation_v1 import LocalObservedRecoveryJournal
from dichiarazioni_pubbliche.original_source_resolver import ExactSourceLocator
from dichiarazioni_pubbliche.private_capture_rights import SourceUseDecision
from dichiarazioni_pubbliche.research_plan import ResearchAssignment


CASE_ID = "dp241-nasa-apollo11-smallstep"
QUESTION = "Quali parole seguono il breve filmato ufficiale del primo passo di Armstrong?"
EXCEPTION = "Il transcript NASA integrale e il filmato breve coincidono nella resa di 'a man' e nell'identita temporale?"
SHORT_URI = "https://heasarc.gsfc.nasa.gov/Videos/historical/smallstep.txt"
SHORT_VIDEO = "https://heasarc.gsfc.nasa.gov/Videos/historical/smallstep.avi"
LONG_URI = "https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11transcript_tec.html"
MEDIA_RIGHTS_URI = "https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/video11.html"
RAW_RIGHTS_URI = "https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11trans.html"
FAMILY = "NASA_APOLLO_11_SINGLE_ROOT"


def digest(blob: bytes | str) -> str:
    return hashlib.sha256(blob.encode() if isinstance(blob, str) else blob).hexdigest()


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str):
        self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def fetch(url: str, *, limit: int = 1_800_000) -> tuple[bytes, str]:
    """An explicit bounded GET; a redirect may stay only on NASA .gov hosts."""
    if url not in {SHORT_URI, LONG_URI, MEDIA_RIGHTS_URI, RAW_RIGHTS_URI}:
        raise ValueError("DP241_PILOT_HOST_OR_URL_NOT_REVIEWED")
    with urlopen(Request(url, headers={"User-Agent": "DP241-operator-pilot/1.0"}), timeout=15) as response:
        from urllib.parse import urlsplit
        final = response.geturl()
        host = urlsplit(final).hostname or ""
        if (urlsplit(final).scheme != "https" or
                not (host == "nasa.gov" or host.endswith(".nasa.gov"))):
            raise ValueError("DP241_PILOT_REDIRECT_UNREVIEWED")
        if response.status != 200:
            raise ValueError("DP241_PILOT_HTTP_NOT_OK")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("DP241_PILOT_RESPONSE_UNBOUNDED")
        return data, final


def probe_media() -> int:
    """Check the shortened official film exists without copying its media."""
    with urlopen(Request(SHORT_VIDEO, method="HEAD",
                         headers={"User-Agent": "DP241-operator-pilot/1.0"}), timeout=15) as response:
        from urllib.parse import urlsplit
        host = urlsplit(response.geturl()).hostname
        size = int(response.headers.get("Content-Length", "0"))
        if (host != "heasarc.gsfc.nasa.gov" or response.status != 200
                or not 0 < size <= 10_000_000
                or not response.headers.get("Content-Type", "").startswith("video/")):
            raise ValueError("DP241_PILOT_MEDIA_NOT_VERIFIED")
        return size


def locator(content_id: str, text: str, start: int, end: int, body: bytes,
            uri: str, observed_at: str):
    quote = text[start:end]
    capture_id = "capture:" + content_id
    passage_id = "passage:" + content_id
    capture = ContentCaptureRecord(
        id=capture_id, content_id=content_id, observed_at=observed_at,
        final_url=uri, content_sha256=digest(body), retrieval_method="HTTPS_GET",
        retrieval_version="dp241-operator-1", parser_method="HTML_PARSER" if text != body.decode(errors="replace") else "TEXT",
        parser_version="stdlib-v1", media_type="text/html" if uri == LONG_URI else "text/plain",
        body_ref="private:dp241:observed", rights_status="CLEARED",
        metadata={"parse_status": "SUCCEEDED"},
    )
    passage = PassageRecord(
        id=passage_id, content_id=content_id, capture_id=capture_id,
        selector_type="TEXT_POSITION", start_char=start, end_char=end,
        text_sha256=digest(quote), private_text=quote,
        extraction_method=capture.parser_method, extraction_version=capture.parser_version,
        language="en",
    )
    exact = ExactSourceLocator(
        content_id=content_id, capture_id=capture_id, passage_id=passage_id,
        selector_type="TEXT_POSITION", quote_start=start, quote_end=end,
        quote_sha256=digest(quote), capture_sha256=digest(body),
    )
    return capture, passage, exact, quote


def method(need_id: str, lane: str, label: str, rights_sha: str, rights_ref: str) -> RecoveryMethod:
    assignment = ResearchAssignment(
        assignment_id="assignment:dp241-nasa-" + label,
        coverage_need_id=need_id, lane=lane, question=QUESTION,
        adapter_ids=("operator-reviewed:https-" + label,),
        max_queries=1, max_results=1, max_results_per_host=1,
        cost_cap_usd=Decimal("0"), temporal_constraints={}, authority_scope={},
        stop_conditions=("TWO_ATTEMPTS_OR_CONTEXT_HOLD",),
    )
    def decision(operation: str) -> SourceUseDecision:
        return SourceUseDecision(
            operation, "PERMITTED", "SOURCE_USE_PERMITTED", "NONE",
            "rights:dp241-nasa-" + label,
            digest(rights_sha + rights_ref + operation),
        )
    return RecoveryMethod(
        assignment=assignment, source_family="nasa-apollo-11",
        adapter_id=assignment.adapter_ids[0], validated_query_ref="reviewed-query:dp241-nasa-" + label,
        query_validation_sha256=digest(label + QUESTION),
        discover_permission=decision("DISCOVER_METADATA"),
        fetch_permission=decision("FETCH"), estimate_usd=Decimal("0"),
    )


def observe(root: Path, *, recheck: bool = False) -> dict[str, object]:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    observed = LocalObservedRecoveryJournal(root)
    previous = observed.read(CASE_ID) if observed.history(CASE_ID) else None
    if previous and not recheck:
        return previous  # replay never performs a second external attempt
    short, short_final = fetch(SHORT_URI)
    media_size = probe_media()
    full, full_final = fetch(LONG_URI)
    media_rights, _ = fetch(MEDIA_RIGHTS_URI)
    raw_rights, _ = fetch(RAW_RIGHTS_URI)
    if b"public domain" not in media_rights.lower() or b"no copyright is asserted" not in raw_rights.lower():
        raise ValueError("DP241_PILOT_RIGHTS_NOTICE_CHANGED")
    short_text = short.decode("utf-8")
    parsed = TextExtractor()
    parsed.feed(full.decode("utf-8", errors="replace"))
    full_text = parsed.text()
    match = re.search(r"That's one small step.*?mankind\.", short_text, flags=re.I | re.S)
    raw_match = re.search(r"THAT'S ONE SMALL STEP.*?MANKIND\.", full_text, flags=re.I | re.S)
    follow = full_text.lower().find("surface is fine and powdery", raw_match.end() if raw_match else 0)
    if not match or not raw_match or not 0 < follow - raw_match.end() < 700:
        raise ValueError("DP241_PILOT_SOURCE_CONTEXT_UNRESOLVED")
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    target_capture, target_passage, target_locator, target_quote = locator(
        "content:nasa-apollo11-short", short_text, match.start(), match.end(),
        short, short_final, observed_at,
    )
    full_end = min(len(full_text), follow + len("surface is fine and powdery") + 100)
    longer_capture, longer_passage, longer_locator, longer_quote = locator(
        "content:nasa-apollo11-technical-transcript", full_text,
        raw_match.start(), full_end, full, full_final, observed_at,
    )
    target = SourceRecoveryTarget(
        need_id="need:dp241-nasa-apollo11", question=QUESTION,
        expected_person_id="person:neil-armstrong", event_date="1969-07-20",
        locator=target_locator, passage=target_passage, quote_text=target_quote,
        capture=target_capture, source_body=short, canonical_text=short_text,
    )
    plan = make_recovery_plan(target, (
        method(target.need_id, "ORIGINAL_MEDIA", "short-media", digest(media_rights), MEDIA_RIGHTS_URI),
        method(target.need_id, "OFFICIAL_STRUCTURED", "technical-transcript", digest(raw_rights), RAW_RIGHTS_URI),
    ), max_attempts=2, cost_cap_usd=Decimal("0"))
    if plan.status != "READY_PRIVATE_PLAN":
        raise ValueError("DP241_PILOT_METHODS_UNAUTHORIZED")
    by_family = {row.method_family: row for row in plan.methods}
    receipts = (
        RecoveryReceipt(
            by_family["ORIGINAL_PUBLISHER"].attempt_id, plan.plan_id,
            "CHECKED_INSUFFICIENT", digest(SHORT_VIDEO + digest(short)), Decimal("0"),
        ),
        RecoveryReceipt(
            by_family["OFFICIAL_RECORD"].attempt_id, plan.plan_id,
            "FOUND_CANDIDATE", digest(LONG_URI + digest(full)), Decimal("0"),
            OriginalCandidateProof(
                locator=longer_locator, passage=longer_passage, quote_text=longer_quote,
                capture=longer_capture, source_body=full, canonical_text=full_text,
                # No invented approved family/derivation edge or qualified reviewer.
                approved_families=(), approved_edges=(),
                observed_person_id="person:neil-armstrong", observed_event_date="1969-07-20",
            ),
        ),
    )
    timeline_root = root / "timelines"
    timeline_root.mkdir(mode=0o700, exist_ok=True)
    canonical = LocalSourceRecoveryTimelineJournal(timeline_root).append(plan, target, receipts)
    attempts = []
    for family, uri, final, body, start, end, quote, rights_url, result, reason in (
        ("ORIGINAL_PUBLISHER", SHORT_URI, short_final, short, match.start(), match.end(),
         target_quote, MEDIA_RIGHTS_URI, "METADATA_ONLY", "SHORT_CLIP_ONLY"),
        ("OFFICIAL_RECORD", LONG_URI, full_final, full, raw_match.start(), full_end,
         longer_quote, RAW_RIGHTS_URI, "CONTEXT_LOCATED_HELD", "ROOT_LINEAGE_REVIEW_REQUIRED"),
    ):
        attempts.append({
            "attempt_id": by_family[family].attempt_id, "method_family": family,
            "source_family": FAMILY, "lookup_uri": uri, "final_uri": final,
            "observed_at": observed_at, "http_status": 200,
            "source_version_sha256": digest(body), "selector_type": "TEXT_POSITION",
            "selector_start": start, "selector_end": end, "selector_sha256": digest(quote),
            "result": result, "reason_code": reason, "rights_basis_uri": rights_url,
            "spent_usd": "0", "next_trigger": "QUALIFIED_SOURCE_AND_CONTEXT_REVIEW",
        })
    changed = bool(previous and previous["record"]["target"]["version_sha256"] != digest(short))
    record = {
        "contract_version": "dp241-observed-source-recovery-v1", "case_id": CASE_ID,
        "plan_id": plan.plan_id, "timeline_snapshot_id": canonical["snapshot_id"],
        "private_only": True, "review_authority": False, "rights_clearance": False,
        "publication_authority": False, "external_receipts_independently_verified": False,
        "case_question": QUESTION, "exception_question": EXCEPTION,
        "target": {
            "content_id": target_locator.content_id, "capture_id": target_locator.capture_id,
            "passage_id": target_locator.passage_id, "uri": short_final,
            "version_sha256": digest(short), "selector_type": "TEXT_POSITION",
            "selector_start": match.start(), "selector_end": match.end(),
            "selector_sha256": digest(target_quote),
            "media_uri": SHORT_VIDEO, "media_http_status": 200,
            "media_content_length": media_size,
        },
        "attempt_cap": 2, "cost_cap_usd": "0", "spent_usd": "0", "attempts": attempts,
        "status": "SOURCE_STALE" if changed else "HELD_FOR_REVIEW",
        "reason_code": "RECOVERY_TARGET_VERSION_CHANGED" if changed else "RECOVERY_INDEPENDENT_LINEAGE_REVIEW_REQUIRED",
        "next_action": "DP511_SOURCE_REVALIDATION" if changed else "REVIEW_SOURCE_AND_DP511",
        "reanalysis_required": True, "root_lineage": FAMILY,
    }
    if previous and not changed and all(
            old["source_version_sha256"] == new["source_version_sha256"]
            for old, new in zip(previous["record"]["attempts"], attempts)) \
            and "media_uri" in previous["record"]["target"]:
        return previous
    observed.append(record)
    return observed.read(CASE_ID)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded official NASA DP-241 observed pilot")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--recheck", action="store_true")
    args = parser.parse_args()
    result = observe(args.root, recheck=args.recheck)
    print(json.dumps({
        "case_id": result["case_id"], "snapshot_id": result["snapshot_id"],
        "status": result["record"]["status"], "history_count": result["history_count"],
        "methods": [r["method_family"] + ":" + r["result"] for r in result["record"]["attempts"]],
        "timeline_snapshot_id": result["record"]["timeline_snapshot_id"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
