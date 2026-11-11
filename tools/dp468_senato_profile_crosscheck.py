#!/usr/bin/env python3
"""Recheck official Senato Person cards for the 16 held DP-468 text candidates.

This is a second *document* cross-check, not independent speech attribution
or authority to publish a quotation.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MANIFEST = Path(__file__).resolve().parents[1] / "docs/ops/dp468-senato-public-v3-source.md"
_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*"
    r"(\d+):(\d+)\s*\|\s*`([0-9a-f]{64})`\s*\|$", re.MULTILINE,
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class _Title(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.chunks.append(data)


def read_batch(manifest: str) -> tuple[str, list[tuple[int, str, int]]]:
    if "## New first-batch text selection" not in manifest:
        raise ValueError("DP468_MANIFEST_SELECTION_MISSING")
    section = manifest.split("## New first-batch text selection", 1)[1].split("\n## ", 1)[0]
    source = re.search(r"content SHA-256\s*`([0-9a-f]{64})`", section)
    rows = [
        (int(ordinal), surname.strip(), int(did))
        for ordinal, surname, did, start, end, digest in _ROW.findall(section)
        if int(start) < int(end) and _SHA256.fullmatch(digest)
    ]
    if (source is None or len(rows) != 16
            or len({row[0] for row in rows}) != len(rows)
            or len({row[2] for row in rows}) != len(rows)
            or any(not re.fullmatch(r"[A-Za-zÀ-ÿ' -]{2,70}", row[1]) for row in rows)):
        raise ValueError("DP468_MANIFEST_SELECTION_INVALID")
    return source.group(1), rows


def fetch_profile(did: int) -> tuple[str, bytes]:
    url = f"https://www.senato.it/leg/19/BGT/Schede/Attsen/{did:08d}.htm"
    # Senato returned HTTP 202 with an empty body to Python urllib on Studio;
    # its existing HTTPS endpoint gave HTTP 200 to the native curl CLI.
    try:
        response = subprocess.run(
            ["curl", "-fsSL", "--max-time", "15", "--max-redirs", "4",
             "--max-filesize", "250000", "--proto", "=https",
             "--proto-redir", "=https",
             "-w", "\n__DP468_FINAL__:%{url_effective}\n%{content_type}", url],
            capture_output=True, check=True, timeout=17,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("DP468_PROFILE_HTTP_UNVERIFIED") from exc
    body, marker, metadata = response.stdout.rpartition(b"\n__DP468_FINAL__:")
    if not marker or not body or len(body) > 250_000:
        raise ValueError("DP468_PROFILE_HTTP_UNVERIFIED")
    final_url, separator, mime = metadata.partition(b"\n")
    if not separator or not mime.startswith(b"text/html"):
        raise ValueError("DP468_PROFILE_HTTP_UNVERIFIED")
    return final_url.decode("ascii"), body


def crosscheck(did: int, surname: str, *, fetch=fetch_profile) -> dict[str, object]:
    url, body = fetch(did)
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "www.senato.it"
            or parsed.path != "/composizione/senatori/elenco-alfabetico/scheda-attivita"
            or parse_qs(parsed.query) != {"did": [f"{did:08d}"]}):
        raise ValueError("DP468_PROFILE_DID_MISMATCH")
    title = _Title()
    title.feed(body.decode("utf-8"))
    observed = " ".join("".join(title.chunks).split())
    if (not re.search(rf"(?<!\w){re.escape(surname)}(?!\w)", observed, re.IGNORECASE)
            or "XIX Legislatura" not in observed
            or "Senato della Repubblica" not in observed):
        raise ValueError("DP468_PROFILE_IDENTITY_MISMATCH")
    return {
        "did": did, "surname": surname, "profile_url": url,
        "html_sha256": hashlib.sha256(body).hexdigest(),
        "title": observed, "status": "PROFILE_DOCUMENT_MATCH_ONLY",
        "speaker_attribution_approved": False, "publication_authorized": False,
    }


def main() -> int:
    source_hash, batch = read_batch(MANIFEST.read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []
    for ordinal, surname, did in batch:
        try:
            result = crosscheck(did, surname)
        except (OSError, UnicodeError, ValueError) as exc:
            result = {
                "did": did, "surname": surname, "status": "HOLD_PROFILE_UNVERIFIED",
                "reason": type(exc).__name__ if isinstance(exc, OSError) else str(exc),
                "speaker_attribution_approved": False, "publication_authorized": False,
            }
        results.append({"ordinal": ordinal, **result})
    matched = sum(row["status"] == "PROFILE_DOCUMENT_MATCH_ONLY" for row in results)
    print(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "original_source_sha256": source_hash, "matched": matched,
        "candidates": len(batch), "identity_approved": False,
        "publication_authorized": False, "observations": results,
    }, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if matched == len(batch) else 1


if __name__ == "__main__":
    raise SystemExit(main())
