"""DP-638 — the verdict: one model pass plus one independent check pass."""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from dichiarazioni_pubbliche.daily_model import ModelClient, fetch_text
from dichiarazioni_pubbliche.daily_statements import ExtractedStatement
from dichiarazioni_pubbliche.daily_text import (
    DailyMachineError,
    _search_form,
    bounded_text,
    find_verbatim,
    html_to_text,
    parse_model_json,
)

# --------------------------------------------------------------------------
VERDICT_SYSTEM_PROMPT = (
    "Sei un fact-checker italiano. Giudichi una sola dichiarazione alla volta e "
    "rispondi esclusivamente con JSON valido. Non inventi fonti: se non hai una "
    "fonte indipendente con un indirizzo web reale, il verdetto e' NOT_VERIFIABLE."
)

VERDICT_USER_TEMPLATE = """DICHIARAZIONE: "{quote}"
PERSONA: {speaker} ({role})
DATA: {statement_date}
FONTE ORIGINALE: {source_url}

CONTESTO DELLA FONTE:
{context}

ALTRE FONTI GIA' SCARICATE OGGI:
{others}

Rispondi con questo JSON:
{{"verdict":"TRUE|FALSE|PARTLY_TRUE|NOT_VERIFIABLE|OPINION","explanation":"2 frasi in italiano","evidence":[{{"url":"https://...","title":"...","publisher":"..."}}]}}

Regole:
- TRUE se i fatti della dichiarazione sono confermati; FALSE se sono smentiti; PARTLY_TRUE se una parte e' confermata e una no.
- OPINION solo se la dichiarazione non contiene alcun fatto controllabile: nessun numero, nessuna decisione, nessun evento, nessuna data. Un giudizio su un fatto (per esempio un commento su una legge o su un provvedimento) resta un fatto controllabile.
- NOT_VERIFIABLE se afferma un fatto ma nessuna fonte disponibile lo conferma o lo smentisce. In dubbio fra OPINION e NOT_VERIFIABLE scegli NOT_VERIFIABLE.
- Ogni verdetto TRUE, FALSE o PARTLY_TRUE deve indicare almeno una fonte indipendente con URL reale che conferma o smentisce. Puoi citare solo URL presenti qui sopra o pagine ufficiali che conosci con certezza.
- explanation: cosa dicono le fonti, in italiano, senza parafrasare la dichiarazione.
"""

CHECK_SYSTEM_PROMPT = (
    "Sei un revisore indipendente. Ricevi una dichiarazione, un verdetto proposto "
    "e le fonti gia' scaricate. Verifichi se il verdetto regge su quelle fonti. "
    "Rispondi esclusivamente con JSON valido."
)

CHECK_USER_TEMPLATE = """DICHIARAZIONE: "{quote}"
PERSONA: {speaker}
FONTE ORIGINALE: {source_url}
VERDETTO PROPOSTO: {verdict} - {explanation}

ESTRATTI DELLE FONTI INDIPENDENTI:
{evidence}

Rispondi con questo JSON:
{{"verdict":"TRUE|FALSE|PARTLY_TRUE|NOT_VERIFIABLE","explanation":"perche' il verdetto regge o non regge"}}
"""


@dataclass(frozen=True)
class EvidenceCheck:
    url: str
    title: str
    publisher: str
    status: int
    chars: int
    excerpt: str

    @property
    def usable(self) -> bool:
        return self.status == 200 and self.chars >= 200


_CLAIM_STOPWORDS = frozenset(
    "della delle degli della nello nella negli sul sulla sono stato stata anni anno oggi ieri "
    "questo questa anche come dove quando perche essere stato fatto fatto piu molto senza "
    "tutti tutte altri altre loro della delle quale quali quindi dopo prima contro verso".split()
)


def _claim_tokens(quote: str) -> set[str]:
    tokens, _ = _search_form(quote)
    return {
        token
        for token in tokens.split()
        if len(token) >= 4 and token not in _CLAIM_STOPWORDS
    }


def verify_evidence(
    entry: dict[str, Any],
    *,
    quote: str,
    source_url: str,
    fetcher: Callable[..., tuple[int, str]] = fetch_text,
    timeout: float = 12.0,
) -> EvidenceCheck | None:
    url = str(entry.get("url") or "").strip()
    if not url.startswith(("http://", "https://")) or url.rstrip("/") == source_url.rstrip("/"):
        return None
    try:
        status, markup = fetcher(url, timeout=timeout)
    except DailyMachineError:
        return None
    text = html_to_text(markup) if markup else ""
    tokens = _claim_tokens(quote)
    evidence_tokens, _ = _search_form(text)
    overlap = sum(1 for token in tokens if token in evidence_tokens)
    excerpt = ""
    if text:
        excerpt = text[:1200]
    usable_status = status
    if tokens and overlap == 0 and status == 200:
        return EvidenceCheck(
            url=url,
            title=str(entry.get("title") or ""),
            publisher=str(entry.get("publisher") or ""),
            status=status,
            chars=len(text),
            excerpt="",
        )
    return EvidenceCheck(
        url=url,
        title=bounded_text(entry.get("title"), 200),
        publisher=bounded_text(entry.get("publisher"), 120),
        status=usable_status,
        chars=len(text),
        excerpt=excerpt,
    )


def decide_verdict(
    client: ModelClient,
    *,
    verdict_model: str,
    check_model: str,
    statement: ExtractedStatement,
    statement_date: str,
    source_url: str,
    speaker: str,
    speaker_role: str,
    context: str,
    other_sources: Sequence[dict[str, str]] = (),
    fetcher: Callable[..., tuple[int, str]] = fetch_text,
) -> dict[str, Any]:
    started = time.monotonic()
    calls_before = len(client.calls)
    others = "\n\n".join(
        f"[{source['publisher']}] {source['title']} ({source['url']})\n{source['text'][:2000]}"
        for source in list(other_sources)[:3]
    ) or "(nessuna)"
    first = client.complete(
        verdict_model,
        [
            {"role": "system", "content": VERDICT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": VERDICT_USER_TEMPLATE.format(
                    quote=statement.quote,
                    speaker=speaker,
                    role=speaker_role or "persona pubblica",
                    statement_date=statement_date,
                    source_url=source_url,
                    context=context,
                    others=others,
                ),
            },
        ],
        operation="VERDICT",
        max_tokens=1200,
    )
    try:
        proposal = parse_model_json(first.text)
    except DailyMachineError:
        proposal = {}
    if not isinstance(proposal, dict):
        proposal = {}
    verdict = str(proposal.get("verdict") or "NOT_VERIFIABLE").upper()
    if verdict not in {"TRUE", "FALSE", "PARTLY_TRUE", "NOT_VERIFIABLE", "OPINION"}:
        verdict = "NOT_VERIFIABLE"
    if verdict == "OPINION":
        return {
            "verdict": "OPINION",
            "explanation": bounded_text(proposal.get("explanation"), 1200).strip()
            or "Giudizio, opinione o promessa: nessun verdetto di vero o falso.",
            "evidence": [],
            "first_pass": proposal,
            "check_pass": {},
            "agreement": "OPINION",
            "models": verdict_model,
            "model_calls": len(client.calls) - calls_before,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    explanation = bounded_text(proposal.get("explanation"), 1200).strip()
    evidence_rows = proposal.get("evidence") if isinstance(proposal.get("evidence"), list) else []
    checked: list[dict[str, Any]] = []
    for entry in evidence_rows[:3]:
        if not isinstance(entry, dict):
            continue
        check = verify_evidence(entry, quote=statement.quote, source_url=source_url, fetcher=fetcher)
        if check is None or not check.usable:
            continue
        checked.append(
            {
                "url": check.url,
                "title": check.title,
                "publisher": check.publisher,
                "excerpt": check.excerpt,
            }
        )
    if verdict != "NOT_VERIFIABLE" and not checked:
        verdict = "NOT_VERIFIABLE"
        explanation = (
            explanation
            + " Nessuna fonte indipendente verificabile: il verdetto non e' pubblicabile."
        ).strip()
    check_pass: dict[str, Any] = {}
    agreement = "SINGLE"
    if verdict != "NOT_VERIFIABLE" and checked:
        evidence_text = "\n\n".join(
            f"[{index + 1}] {row['publisher']} - {row['title']} ({row['url']})\n{row['excerpt'][:1200]}"
            for index, row in enumerate(checked[:4])
        )
        second = client.complete(
            check_model,
            [
                {"role": "system", "content": CHECK_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": CHECK_USER_TEMPLATE.format(
                        quote=statement.quote,
                        speaker=speaker,
                        source_url=source_url,
                        verdict=verdict,
                        explanation=explanation,
                        evidence=evidence_text,
                    ),
                },
            ],
            operation="VERDICT_CHECK",
            max_tokens=800,
        )
        try:
            check_pass = parse_model_json(second.text)
        except DailyMachineError:
            check_pass = {}
        if not isinstance(check_pass, dict):
            check_pass = {}
        confirmed = str(check_pass.get("verdict") or "NOT_VERIFIABLE").upper()
        agreement = "AGREE" if confirmed == verdict else "DISAGREE"
        if agreement == "DISAGREE":
            verdict = "NOT_VERIFIABLE"
            explanation = (
                "I due passaggi non concordano ("
                + verdict
                + " / "
                + confirmed
                + "): la dichiarazione non e' verificabile. "
                + explanation
            ).strip()
    return {
        "verdict": verdict,
        "explanation": explanation,
        "evidence": checked,
        "first_pass": proposal,
        "check_pass": check_pass,
        "agreement": agreement,
        "models": f"{verdict_model}|{check_model}",
        "model_calls": len(client.calls) - calls_before,
        "duration_seconds": round(time.monotonic() - started, 3),
    }


