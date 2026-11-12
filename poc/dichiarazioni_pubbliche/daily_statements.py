"""DP-638 — statements: exact quote, resolved speaker, moment, topic."""
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

from dichiarazioni_pubbliche.daily_capture import Capture, DiscoveredItem
from dichiarazioni_pubbliche.daily_model import ModelClient
from dichiarazioni_pubbliche.daily_text import (
    DailyMachineError,
    _search_form,
    bounded_text,
    find_verbatim,
    parse_model_json,
)

# --------------------------------------------------------------------------
STATEMENT_SYSTEM_PROMPT = (
    "Sei un estrattore di dichiarazioni pubbliche. Riporti solo frasi che una "
    "persona identificabile ha effettivamente pronunciato o scritto nel testo "
    "fornito. Non parafrasi, non completi, non correggi, non inventi. "
    "Rispondi esclusivamente con JSON valido."
)

STATEMENT_USER_TEMPLATE = """FONTE: {publisher} - {title}
URL: {url}
DATA: {published}

TESTO:
\"\"\"
{text}
\"\"\"

Estrai al massimo {limit} dichiarazioni. Rispondi con questo JSON:
{{"statements":[{{"quote":"...","speaker":"...","speaker_role":"...","moment":"...","topic":"...","nature":"FACTUAL"}}]}}

Regole vincolanti:
- quote: copia un frammento contiguo del TESTO qui sopra, parola per parola, senza aggiungere punteggiatura o virgolette. Se il TESTO non ha punteggiatura, non aggiungerla.
- Estrai solo discorso DIRETTO tra virgolette attribuito esplicitamente a una persona nel TESTO, oppure parole con etichetta del parlante in una trascrizione. Il discorso indiretto del giornalista non e' una citazione della persona.
- speaker: nome e cognome di una figura pubblica che pronuncia proprio la frase, presenti insieme nel TESTO con un verbo di dichiarazione o un'etichetta del parlante. Una persona menzionata o nel solo titolo non basta: in dubbio scrivi "".
- speaker_role: ruolo o carica se il testo lo dice, altrimenti "".
- moment: per un video/audio il minuto nel formato mm:ss; per un articolo il numero di paragrafo, per esempio "par. 3".
- topic: 2-5 parole, il tema della dichiarazione.
- nature: "FACTUAL" se afferma un fatto controllabile; "OPINION" se e' un giudizio, un'opinione o una promessa.
- Salta saluti, conduzione, pubblicita' e frasi senza un contenuto.
"""


@dataclass(frozen=True)
class ExtractedStatement:
    quote: str
    speaker: str
    speaker_role: str
    moment: str
    topic: str
    nature: str


def extract_statements(
    client: ModelClient,
    model: str,
    capture: Capture,
    item: DiscoveredItem,
    *,
    limit: int = 8,
    max_chars: int = 24000,
) -> list[ExtractedStatement]:
    text = capture.body[:max_chars]
    messages = [
        {"role": "system", "content": STATEMENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": STATEMENT_USER_TEMPLATE.format(
                publisher=item.source.publisher,
                title=item.content.title,
                url=item.content.canonical_url,
                published=item.content.published_at or item.published_day,
                text=text,
                limit=limit,
            ),
        },
    ]
    reply = client.complete(model, messages, operation="STATEMENT_EXTRACTION", max_tokens=6000)
    payload = parse_model_json(reply.text)
    rows = payload.get("statements") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    statements: list[ExtractedStatement] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        quote = bounded_text(row.get("quote"), 1200).strip()
        if not quote:
            continue
        nature = str(row.get("nature") or "FACTUAL").strip().upper()
        statements.append(
            ExtractedStatement(
                quote=quote,
                speaker=bounded_text(row.get("speaker"), 120).strip(),
                speaker_role=bounded_text(row.get("speaker_role"), 160).strip(),
                moment=bounded_text(row.get("moment"), 40).strip(),
                topic=bounded_text(row.get("topic"), 120).strip(),
                nature="OPINION" if nature == "OPINION" else "FACTUAL",
            )
        )
    return statements[:limit]


_NAME_TOKEN = re.compile(r"[^\W\d_][\w'’.-]{1,}", re.UNICODE)


def _name_tokens(name: str) -> list[str]:
    return [token for token in _NAME_TOKEN.findall(name or "") if len(token) >= 3]


ATTRIBUTION_VERSION = "direct-source-attribution-v2"
_SPEECH_VERB = r"(?:ha (?:detto|dichiarato|affermato|spiegato|aggiunto|sottolineato|scritto|ricordato|annunciato)|dice|dichiara|afferma|spiega|aggiunge|sottolinea|scrive|ricorda|annuncia)"


def resolve_speaker(statement: ExtractedStatement, capture: Capture, item: DiscoveredItem | None = None) -> str:
    """Bind a person to this direct quote, never to a name elsewhere on the page.

    shortcut: unlabelled media and surname-only/complex attributions stay held;
    broaden only with source-bound attribution fixtures and independent review.
    """
    tokens = _name_tokens(statement.speaker)
    if len(tokens) < 2:
        return ""
    found = find_verbatim(capture.body, statement.quote)
    if found is None:
        return ""
    name = r"(?<!\w)" + r"\s+".join(re.escape(token) for token in tokens) + r"(?!\w)"
    start, end = found
    body = capture.body
    if capture.kind in {"captions", "asr"}:
        line_start = body.rfind("\n", 0, start) + 1
        attributed = re.fullmatch(name + r"\s*:\s*", body[line_start:start], flags=re.I) is not None
    else:
        attributed = False
        for opening, closing in (("«", "»"), ("“", "”"), ('"', '"')):
            left = body.rfind(opening, 0, start + 1)
            right = body.find(closing, end)
            if left < 0 or right < 0 or start - left > 1200 or right - end > 1200:
                continue
            if closing in body[left + 1:start] or opening in body[end:right]:
                continue
            before = body[max(0, left - 200):left]
            after = body[right + 1:right + 201]
            attributed = bool(
                re.search(name + r"\s*[,]?\s*(?:" + _SPEECH_VERB + r")\s*:?\s*$", before, flags=re.I)
                or re.search(r"^[\s,–—-]*(?:" + _SPEECH_VERB + r")\s+" + name, after, flags=re.I)
                or re.search(name + r"\s*:\s*$", before, flags=re.I)
            )
            if attributed:
                break
    return "person:" + "-".join(token.casefold() for token in tokens) if attributed else ""


def moment_selection(
    quote_start: int,
    quote_end: int,
    capture: Capture,
    moment_label: str,
) -> dict[str, Any]:
    """Locate the moment of a quote in the capture: caption time or paragraph."""

    if capture.segments:
        search_text = "\n".join(segment.text for segment in capture.segments)
        found = find_verbatim(search_text, capture.body[quote_start:quote_end])
        if found is not None:
            consumed = 0
            for segment in capture.segments:
                consumed += len(segment.text) + 1
                if consumed > found[0]:
                    seconds = segment.start_ms // 1000
                    return {
                        "moment_ms": segment.start_ms,
                        "moment_label": f"{seconds // 60:02d}:{seconds % 60:02d}",
                        "moment_kind": "CAPTION_TIME",
                    }
    paragraph = capture.body[: quote_start].count("\n\n") + 1
    if capture.body[:quote_start].count("\n") > paragraph:
        paragraph = capture.body[:quote_start].count("\n") + 1
    return {
        "moment_ms": None,
        "moment_label": moment_label or f"par. {paragraph}",
        "moment_kind": "PARAGRAPH",
        "moment_paragraph": paragraph,
    }
