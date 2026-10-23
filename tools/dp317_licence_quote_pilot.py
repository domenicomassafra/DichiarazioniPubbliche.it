#!/usr/bin/env python3
"""DP-317 real-case pilot: one licence-granted quote and one refused quote.

Fetches two live official European Commission documents, binds an exact
original sentence to its capture, attests the CC BY 4.0 grant from the hashed
legal notice, and runs the licence excerpt decision. Then it proves the
refusals: no grant, tampered wording, revoked epoch.

Nothing is published. The rendered private text is written with mode 0600 into
a temporary directory and never printed; only hashes, lengths and codes go to
stdout. The revocation epoch is read from a local write-once ledger file, so no
production database is touched.

Usage:
    PYTHONPATH=poc python3 tools/dp317_licence_quote_pilot.py [--private-dir DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.licence_excerpt_decision_v1 import (  # noqa: E402
    AttributionStatement,
    LiveRevocationAuthority,
    SourceTermsEvidence,
    decide_licence_excerpt,
    licence_decision_receipt,
)
from dichiarazioni_pubbliche.lawful_exact_quote_preflight_v1 import (  # noqa: E402
    ExactQuoteRequest,
    ScopedQuoteRightsClaim,
    quote_scope_fingerprint,
)
from dichiarazioni_pubbliche.quote_binding import (  # noqa: E402
    verify_written_quote_binding,
)
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PRIVATE_RIGHTS_RECORD_VERSION,
    PrivateRightsRecord,
    RightsSubject,
    rights_subject_fingerprint,
)

MAX_BYTES = 512 * 1024
PROFILE_URL = "https://commission.europa.eu/about/organisation/president_en"
NOTICE_URL = "https://commission.europa.eu/legal-notice_en"
SOURCE_FAMILY = "EC_OFFICIAL_COMMISSION_PROFILE"
CONTENT_ID = "commission-president-profile-en"
POLICY_VERSION = "source-policy-v1"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _Paragraphs(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._depth = 0
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "blockquote", "li"}:
            self._depth += 1
            if self._depth == 1:
                self._buffer = []

    def handle_endtag(self, tag):
        if tag in {"p", "blockquote", "li"} and self._depth:
            self._depth -= 1
            if self._depth == 0:
                text = re.sub(r"\s+", " ", " ".join(self._buffer)).strip()
                if text:
                    self.blocks.append(text)
                self._buffer = []

    def handle_data(self, data):
        if self._depth:
            self._buffer.append(data)


def fetch(url: str) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SystemExit(f"DP317_PILOT_HTTPS_REQUIRED: {url}")
    request = Request(url, headers={"User-Agent": "dp317-pilot/1"}, method="GET")
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            body = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        raise SystemExit(f"DP317_PILOT_HTTP_{exc.code}: {url}") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise SystemExit(f"DP317_PILOT_FETCH_FAILED: {url} ({exc})") from None
    if len(body) > MAX_BYTES:
        raise SystemExit(f"DP317_PILOT_RESPONSE_TOO_LARGE: {url}")
    return body


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pick_quote(profile_html: bytes) -> tuple[str, int, int]:
    """First self-contained sentence of the profile page, whitespace-normalised."""
    parser = _Paragraphs()
    parser.feed(profile_html.decode("utf-8", "replace"))
    for block in parser.blocks:
        sentences = re.split(r"(?<=[.!?]) (?=[A-Z“\"'(])", block)
        for sentence in sentences:
            if 80 <= len(sentence) <= 400 and len(sentence.split()) >= 8:
                start = block.index(sentence)
                return sentence, start, start + len(sentence)
    raise SystemExit("DP317_PILOT_NO_QUOTE_CANDIDATE")


class LedgerAuthority(LiveRevocationAuthority):
    """Local write-once epoch file: stands in for the DP-320 read-time store."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def current_epoch(self) -> int:
        return int(self.path.read_text(encoding="utf-8").strip())

    def authority_ref(self) -> str:
        return f"file-ledger:{digest(self.path.read_bytes())[:16]}"


def write_once(path: Path, text: str, *, mode: int = 0o600) -> None:
    if path.exists():
        raise SystemExit(f"DP317_PILOT_REFUSES_OVERWRITE: {path.name}")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)


def build_request(quote: str, profile_sha: str, start: int, end: int):
    subject = RightsSubject(
        source_family=SOURCE_FAMILY,
        locator_kind="URL",
        locator_value=PROFILE_URL,
        content_id=CONTENT_ID,
    )
    request = ExactQuoteRequest(
        subject=subject,
        capture_id=f"capture-ec-president-{datetime.now(UTC):%Y-%m-%d}",
        capture_version=f"html-{profile_sha[:16]}",
        capture_sha256=profile_sha,
        representation_sha256=profile_sha,
        quotation_sha256=digest(quote.encode("utf-8")),
        context_sha256=digest(("context:" + quote).encode("utf-8")),
        selector_start=start,
        selector_end=end,
        representation="WRITTEN_ORIGINAL",
        text_role="SOURCE_ORIGINAL",
        source_language="en",
        displayed_language="en",
        public_use="STATEMENT",
        purpose="PUBLIC_QUOTATION",
        jurisdiction="IT",
        attribution_ref="private:ec-attribution",
        translation_parent_sha256=None,
        representation_derivation_ref="private:html-text-extraction-v1",
    )
    return subject, request


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", default=None)
    options = parser.parse_args(argv)
    private_dir = Path(options.private_dir or tempfile.mkdtemp(prefix="dp317-pilot-"))
    private_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)

    profile_html = fetch(PROFILE_URL)
    notice_html = fetch(NOTICE_URL)
    profile_sha, notice_sha = digest(profile_html), digest(notice_html)
    notice_text = re.sub(r"\s+", " ", html.unescape(
        notice_html.decode("utf-8", "replace")))
    notice_text = re.sub(r"<[^>]+>", " ", notice_text)
    markers = tuple(
        marker
        for marker in ("Attribution 4.0 International", "CC BY 4.0")
        if marker in notice_text
    )
    if len(markers) != 2:
        raise SystemExit("DP317_PILOT_LICENCE_MARKERS_NOT_OBSERVED")

    quote, start, end = pick_quote(profile_html)
    subject, request = build_request(quote, profile_sha, start, end)
    binding = verify_written_quote_binding(
        statement_text_sha256=request.quotation_sha256,
        passage_text_sha256=request.quotation_sha256,
        private_text=quote,
        selector_type="TEXT_POSITION",
        start_char=start,
        end_char=end,
        source_sha256=profile_sha,
    )
    terms = SourceTermsEvidence(
        terms_url=NOTICE_URL,
        terms_document_sha256=notice_sha,
        terms_version=f"legal-notice-en-{notice_sha[:16]}",
        licence_id="CC-BY-4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        rightsholder="European Commission",
        markers=markers,
    )
    statement = AttributionStatement(
        creator="European Commission",
        work_title="President of the European Commission — official profile",
        source_url=PROFILE_URL,
        licence_id="CC-BY-4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        modified=False,
    )
    ledger = private_dir / "revocation-epoch.txt"
    write_once(ledger, "1\n")
    authority = LedgerAuthority(ledger)
    record = PrivateRightsRecord(
        id="rights:ec-president-pilot",
        subject_fingerprint=rights_subject_fingerprint(subject),
        source_family=subject.source_family,
        locator_kind="URL",
        locator_value=PROFILE_URL,
        content_id=CONTENT_ID,
        evidence_id=None,
        transcript_segment_id=None,
        canonical_segment_id=None,
        passage_id=None,
        rights_status="CLEARED",
        rights_receipt_ref=f"licence:CC-BY-4.0:{notice_sha}",
        permitted_uses=("STORE_BODY",),
        attribution_requirements=(),
        reviewed_at=(now - timedelta(hours=1)).isoformat(),
        expires_at=(now + timedelta(days=30)).isoformat(),
        reviewer_ref="machine:licence-attestation-v1",
        policy_version=POLICY_VERSION,
        record_visibility="PRIVATE",
        supersedes_id=None,
        version_state="CURRENT",
        record_version=PRIVATE_RIGHTS_RECORD_VERSION,
    )

    def claim(scope, **changes):
        value = ScopedQuoteRightsClaim(
            documented_scope=scope,
            scope_fingerprint=quote_scope_fingerprint(scope),
            decision_version="dp317-v1",
            status="CASE_REVIEWED",
            legal_basis="SOURCE_SPECIFIC_LICENCE",
            source_terms_ref=NOTICE_URL,
            source_terms_version=terms.terms_version,
            lawful_basis_receipt_ref=f"licence:CC-BY-4.0:{notice_sha}",
            qualified_reviewer_ref="machine:licence-attestation-v1",
            owner_decision_ref="private:owner-release-2026-10-23",
            reviewed_at=(now - timedelta(hours=1)).isoformat(),
            effective_at=(now - timedelta(hours=1)).isoformat(),
            expires_at=(now + timedelta(days=30)).isoformat(),
            max_quotation_chars=len(quote),
            necessity_ref="private:necessity-and-context-review",
            attribution_required=True,
            conditions_satisfied=True,
            version_state="CURRENT",
            revocation_state="CURRENT",
            revocation_epoch=1,
        )
        return replace(value, **changes)

    def decide(scope, rights_claim, *, text=quote, revocation=authority):
        return decide_licence_excerpt(
            request=scope,
            binding=binding if text == quote else verify_written_quote_binding(
                statement_text_sha256=digest(text.encode("utf-8")),
                passage_text_sha256=digest(text.encode("utf-8")),
                private_text=text,
                selector_type="TEXT_POSITION",
                start_char=start,
                end_char=end,
                source_sha256=profile_sha,
            ),
            rights_claim=rights_claim,
            private_rights_record=record,
            private_rights_record_id=record.id,
            private_rights_policy_version=POLICY_VERSION,
            terms_evidence=terms,
            attribution=statement,
            live_revocation=revocation,
            private_quote_text=text,
            now=now,
        )

    allowed = decide(request, claim(request))
    no_grant = decide(request, claim(request, legal_basis="CASE_SPECIFIC_PERMISSION"))
    tampered = decide(
        request, claim(request), text=quote.replace(quote.split()[0], "Altered", 1)
    )
    revoked_scope = claim(request, revocation_state="REVOKED")
    revoked = decide(request, revoked_scope)

    assert allowed.status == "PERMITTED", allowed.reason_code
    assert allowed.quote_chars == end - start
    assert allowed.publication_authorized is False
    assert no_grant.status == "PROHIBITED", no_grant.reason_code
    assert no_grant.private_rendered_text is None
    assert tampered.status == "HELD", tampered.reason_code
    assert tampered.private_rendered_text is None
    assert revoked.status == "PROHIBITED", revoked.reason_code

    rendered = private_dir / "licence-excerpt-rendering.html"
    write_once(rendered, allowed.private_rendered_text + "\n")
    receipt = licence_decision_receipt(allowed, request)
    write_once(private_dir / "licence-excerpt-receipt.json", json.dumps(
        {
            "receipt_sha256": receipt,
            "decision": asdict(allowed),
            "request": asdict(request),
            "terms": asdict(terms),
            "quote_sha256": request.quotation_sha256,
        },
        indent=2,
        sort_keys=True,
    ) + "\n")

    print(json.dumps(
        {
            "pilot": "DP317_LICENCE_QUOTE_PILOT",
            "profile_url": PROFILE_URL,
            "profile_sha256": profile_sha,
            "profile_bytes": len(profile_html),
            "notice_url": NOTICE_URL,
            "notice_sha256": notice_sha,
            "notice_bytes": len(notice_html),
            "licence_markers": list(markers),
            "quote_chars": allowed.quote_chars,
            "quote_sha256": request.quotation_sha256,
            "selector": [start, end],
            "binding": binding.reason_code,
            "permitted": {
                "status": allowed.status,
                "reason_code": allowed.reason_code,
                "licence_id": allowed.licence_id,
                "revocation_epoch": allowed.revocation_epoch,
                "publication_authorized": allowed.publication_authorized,
                "receipt_sha256": receipt,
            },
            "refused": {
                "no_grant": [no_grant.status, no_grant.reason_code],
                "tampered": [tampered.status, tampered.reason_code],
                "revoked": [revoked.status, revoked.reason_code],
            },
            "private_dir": str(private_dir),
            "private_artifacts": sorted(p.name for p in private_dir.iterdir()),
            "verdict": "PASS",
            "checked_at": now.isoformat(),
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
