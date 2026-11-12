#!/usr/bin/env python3
"""Cross-check held Senato speakers against Radio Radicale's session index.

The separate publisher's speaker index corroborates a session and speaker,
not the exact spoken words or public rights/privacy/review authority.
"""

from __future__ import annotations

import hashlib
from datetime import date as calendar_date, datetime, timedelta
from html import unescape
import json
import re
import subprocess
from urllib.parse import urlparse

from tools.dp468_senato_profile_crosscheck import MANIFEST, read_batch


URL = "https://www.radioradicale.it/scheda/760686/seduta-310a-xix-legislatura"
PROFILES = MANIFEST.with_name("dp468-senato-profile-crosscheck-20261111.json")
_ITEM = re.compile(r'<li class="[^"<>]*\bintervento\b[^"<>]*">(.*?)</li>', re.S)
_LINK = re.compile(r'<span class="subject">\s*<a href="([^"<>]+)">([^<>]+)</a>')
_DATE = re.compile(r'<span class="date-display-single"[^>]*\bcontent="([^"]+)"')
_PROFILE_NAME = re.compile(
    r"Scheda di attività di (.+?) - XIX Legislatura \| Senato della Repubblica\Z"
)


def fetch_index() -> tuple[str, bytes]:
    try:
        result = subprocess.run(
            ["curl", "-fsSL", "--max-time", "15", "--max-redirs", "3",
             "--max-filesize", "250000", "--proto", "=https",
             "--proto-redir", "=https",
             "-w", "\n__DP468_RR_FINAL__:%{url_effective}\n%{content_type}", URL],
            capture_output=True, check=True, timeout=17,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("DP468_RR_HTTP_UNVERIFIED") from exc
    body, marker, meta = result.stdout.rpartition(b"\n__DP468_RR_FINAL__:")
    final, sep, mime = meta.partition(b"\n")
    if (not marker or not body or len(body) > 250_000
            or not sep or not mime.startswith(b"text/html")):
        raise ValueError("DP468_RR_HTTP_UNVERIFIED")
    return final.decode("ascii"), body


def crosscheck(
    source_hash: str, batch: list[tuple[int, str, int]], profiles: dict,
    final_url: str, body: bytes,
) -> dict:
    if final_url != URL or not body or len(body) > 250_000:
        raise ValueError("DP468_RR_SOURCE_UNVERIFIED")
    html = body.decode("utf-8")
    if (not re.search(r'<h1[^>]*>\s*Seduta 310ª \(XIX legislatura\)', html)
            or '"uploadDate":"2025-05-29"' not in html
            or "id='vp-index-list'" not in html):
        raise ValueError("DP468_RR_SESSION_MISMATCH")
    if (profiles.get("matched") != len(batch)
            or profiles.get("original_source_sha256") != source_hash
            or profiles.get("identity_approved") is not False
            or profiles.get("publication_authorized") is not False):
        raise ValueError("DP468_RR_PROFILE_RECEIPT_INVALID")
    profile_rows = {p["ordinal"]: p for p in profiles.get("observations", [])}
    if len(profile_rows) != len(batch):
        raise ValueError("DP468_RR_PROFILE_RECEIPT_INVALID")

    # Only indexed video interventions with a dated, direct segment URL count.
    index = html.split("id='vp-index-list'", 1)[1].split("</ul>", 1)[0]
    events = []
    for item in _ITEM.findall(index):
        link, date = _LINK.search(item), _DATE.search(item)
        if not link or not date:
            continue
        try:
            start = datetime.fromisoformat(date.group(1))
        except ValueError:
            continue
        if (start.date() != calendar_date(2025, 5, 29)
                or start.utcoffset() != timedelta(hours=2)):
            continue
        link_url, name = link.groups()
        parsed = urlparse(unescape(link_url))
        if (parsed.scheme != "https" or parsed.hostname != "www.radioradicale.it"
                or parsed.path != urlparse(URL).path or parsed.query
                or re.fullmatch(r"i=[0-9]+", parsed.fragment) is None):
            continue
        events.append((unescape(name).strip(), unescape(link_url), date.group(1)))

    observations, last_index = [], -1
    for ordinal, surname, did in batch:
        profile = profile_rows.get(ordinal)
        if (not isinstance(profile, dict) or profile.get("did") != did
                or profile.get("surname") != surname
                or profile.get("status") != "PROFILE_DOCUMENT_MATCH_ONLY"
                or profile.get("speaker_attribution_approved") is not False):
            raise ValueError("DP468_RR_PROFILE_RECEIPT_INVALID")
        match = _PROFILE_NAME.fullmatch(str(profile.get("title", "")))
        if not match or match.group(1).split()[-1].casefold() != surname.casefold():
            raise ValueError("DP468_RR_PROFILE_RECEIPT_INVALID")
        wanted = match.group(1).casefold()
        found = next((i for i, event in enumerate(events)
                      if i > last_index and event[0].casefold() == wanted), None)
        if found is None:
            raise ValueError("DP468_RR_SPEAKER_INDEX_MISMATCH")
        last_index = found
        name, speech_url, started_at = events[found]
        observations.append({
            "ordinal": ordinal, "person_did": did, "speaker": name,
            "segment_url": speech_url, "started_at": started_at,
            "status": "INDEPENDENT_PUBLISHER_INDEX_MATCH_ONLY",
            "speaker_attribution_approved": False, "publication_authorized": False,
        })
    return {
        "radio_radicale_url": URL,
        "radio_radicale_html_sha256": hashlib.sha256(body).hexdigest(),
        "original_senato_source_sha256": source_hash,
        "senato_profile_receipt_sha256": hashlib.sha256(PROFILES.read_bytes()).hexdigest(),
        "matched": len(observations), "candidates": len(batch),
        "identity_approved": False, "publication_authorized": False,
        "observations": observations,
    }


def main() -> int:
    source_hash, batch = read_batch(MANIFEST.read_text(encoding="utf-8"))
    try:
        result = crosscheck(source_hash, batch, json.loads(PROFILES.read_text()), *fetch_index())
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "HOLD_INDEPENDENT_PUBLISHER_UNVERIFIED", "reason": str(exc),
                          "publication_authorized": False}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
