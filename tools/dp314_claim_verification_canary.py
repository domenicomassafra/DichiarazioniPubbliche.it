#!/usr/bin/env python3
"""DP-314 real-case canary: one claim classified three ways, plus the HOLDs.

Fetches the official press statement of 4 March 2025 and the European
Commission legal notice, attests the CC BY 4.0 grant from the hashed terms
document, then classifies:

* VERIFIABLE — the statement about EUR 150 billion of loans, whose counter-case
  ("they were grants") is refuted by the same reviewed source;
* FALSE — the negated claim about grants, refuted by that source while the
  counter-case is supported;
* NOT_VERIFIABLE — a non-factual proposition;
* HELD — the same VERIFIABLE claim without attested rights and without a
  counter-case.

No verdict is published: every result is private, carries no finding or
publication authority, and no database, provider or publication is touched.
Only hashes, codes and counts are printed.

Usage:
    PYTHONPATH=poc python3 tools/dp314_claim_verification_canary.py
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.dp314_general_verifier_v1 import (  # noqa: E402
    CounterCase,
    classify_claim,
)
from dichiarazioni_pubbliche.licence_excerpt_decision_v1 import (  # noqa: E402
    SourceTermsEvidence,
    attest_licence_use,
)
from dichiarazioni_pubbliche.verification_requirements_v1 import (  # noqa: E402
    RequirementClaim,
    RequirementEvidence,
)

MAX_BYTES = 512 * 1024
STATEMENT_URL = (
    "https://cyprus.representation.ec.europa.eu/news/"
    "press-statement-president-von-der-leyen-defence-package-2025-03-04_en"
)
NOTICE_URL = "https://commission.europa.eu/legal-notice_en"
PASSAGE = "It will provide EUR 150 billion of loans to Member States for defence investment"
STATEMENT_DATE = "2025-03-04"
REVIEW_CUTOFF = "2025-03-31"
JURISDICTION = "jurisdiction:eu"
POLICY_VERSION = "policy:dp314-canary:v1"
ROOT = "commission.europa.eu"
FAMILY = "ec_official_press_statement"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url: str) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SystemExit(f"DP314_CANARY_HTTPS_REQUIRED: {url}")
    request = Request(url, headers={"User-Agent": "dp314-canary/1"}, method="GET")
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            body = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        raise SystemExit(f"DP314_CANARY_HTTP_{exc.code}: {url}") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise SystemExit(f"DP314_CANARY_FETCH_FAILED: {url} ({exc})") from None
    if len(body) > MAX_BYTES:
        raise SystemExit(f"DP314_CANARY_RESPONSE_TOO_LARGE: {url}")
    return body


def sha(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def plain_text(document: bytes) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(document.decode("utf-8", "replace")))
    return re.sub(r"\s+", " ", text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-no-network", action="store_true")
    options = parser.parse_args(argv)
    if options.expect_no_network:
        raise SystemExit("DP314_CANARY_NEEDS_NETWORK")
    now = datetime.now(UTC)

    statement_html = fetch(STATEMENT_URL)
    notice_html = fetch(NOTICE_URL)
    statement_text, notice_text = plain_text(statement_html), plain_text(notice_html)
    if PASSAGE not in statement_text:
        raise SystemExit("DP314_CANARY_PASSAGE_NOT_IN_SOURCE")
    markers = tuple(
        marker
        for marker in ("Attribution 4.0 International", "CC BY 4.0")
        if marker in notice_text
    )
    terms = SourceTermsEvidence(
        terms_url=NOTICE_URL,
        terms_document_sha256=sha(notice_html),
        terms_version=f"legal-notice-en-{sha(notice_html)[:16]}",
        licence_id="CC-BY-4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        rightsholder="European Commission",
        markers=markers,
    )
    attestation = attest_licence_use(terms)
    if attestation.status != "APPROVED":
        raise SystemExit(f"DP314_CANARY_RIGHTS_{attestation.reason_code}")
    approved = attestation.status

    evidence = RequirementEvidence(
        evidence_id="evidence:ec-press-2025-03-04",
        evidence_sha256=sha(PASSAGE),
        primary_root_ref=ROOT,
        source_family_ref=FAMILY,
        locator_ref="locator:ec-press-2025-03-04",
        evidence_role="PRIMARY_STATISTICS",
        published_date=STATEMENT_DATE,
        jurisdiction_ref=JURISDICTION,
        stance="SUPPORT",
        source_use_status=approved,
        evidence_review_status=approved,
    )
    refuting = replace(evidence, stance="REFUTE")

    def claim(kind, proposition, **changes):
        value = RequirementClaim(
            claim_id=f"claim:dp314-canary:{kind.lower()}",
            claim_kind=kind,
            statement_date=STATEMENT_DATE,
            jurisdiction_ref=JURISDICTION,
            proposition_sha256=sha(proposition),
            policy_version=POLICY_VERSION,
            review_cutoff_date=REVIEW_CUTOFF,
            run_state="COMPLETED",
        )
        return replace(value, **changes)

    loans = claim(
        "NUMERIC",
        "Il 4 marzo 2025 la Commissione ha proposto 150 miliardi di EUR in prestiti "
        "agli Stati membri per investimenti nella difesa.",
    )
    grants = claim(
        "NUMERIC",
        "Il 4 marzo 2025 la Commissione ha proposto 150 miliardi di EUR in "
        "sovvenzioni (grants) agli Stati membri.",
    )
    opinion = claim("NON_FACTUAL", "Il pacchetto di difesa è la scelta giusta.")
    counter_case = CounterCase(
        counter_ref="counter:dp314-canary:grants-not-loans",
        hypothesis_sha256=sha("I 150 miliardi erano sovvenzioni, non prestiti."),
        outcome="SOURCE_REFUTES_COUNTER",
        evidence_ids=(evidence.evidence_id,),
    )
    counter_loans = replace(
        counter_case,
        outcome="SOURCE_SUPPORTS_COUNTER",
        hypothesis_sha256=sha("I 150 miliardi erano prestiti."),
    )

    verifiable = classify_claim(loans, (evidence,), counter_case)
    false_result = classify_claim(grants, (refuting,), counter_loans)
    not_verifiable = classify_claim(opinion, (), None)
    held_rights = classify_claim(
        loans, (replace(evidence, source_use_status="HELD"),), counter_case
    )
    held_counter = classify_claim(loans, (evidence,), None)

    assert verifiable.status == "VERIFIABLE", verifiable.reason_code
    assert false_result.status == "FALSE", false_result.reason_code
    assert not_verifiable.status == "NOT_VERIFIABLE", not_verifiable.reason_code
    assert held_rights.status == "HELD", held_rights.reason_code
    assert held_counter.status == "HELD", held_counter.reason_code
    for result in (verifiable, false_result, not_verifiable, held_rights, held_counter):
        assert result.verdict is None
        assert result.private_only is True
        assert result.finding_authority is False
        assert result.publication_authority is False

    print(json.dumps(
        {
            "canary": "DP314_CLAIM_VERIFICATION_CANARY",
            "statement_url": STATEMENT_URL,
            "statement_sha256": sha(statement_html),
            "statement_bytes": len(statement_html),
            "notice_url": NOTICE_URL,
            "notice_sha256": sha(notice_html),
            "notice_bytes": len(notice_html),
            "licence_markers": list(markers),
            "rights_attestation": attestation.reason_code,
            "passage_sha256": sha(PASSAGE),
            "passage_chars": len(PASSAGE),
            "classifications": {
                "verifiable": [verifiable.status, verifiable.reason_code,
                               list(verifiable.eligible_evidence_ids)],
                "false": [false_result.status, false_result.reason_code],
                "not_verifiable": [not_verifiable.status,
                                   not_verifiable.reason_code],
                "held_rights": [held_rights.status, held_rights.reason_code,
                                list(held_rights.reason_codes)],
                "held_counter": [held_counter.status, held_counter.reason_code],
            },
            "snapshots": {
                "verifiable": verifiable.snapshot_sha256,
                "false": false_result.snapshot_sha256,
            },
            "result_contract": {
                key: asdict(verifiable)[key]
                for key in ("verdict", "private_only", "finding_authority",
                            "publication_authority")
            },
            "verdict": "PASS",
            "checked_at": now.isoformat(),
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
