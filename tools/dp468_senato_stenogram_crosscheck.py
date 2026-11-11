#!/usr/bin/env python3
"""Cross-check DP-468 HELD quotes with the separate official Senato HTML record.

The resulting receipt is evidence of a text/role match, never a grant, a
privacy decision, independent model review, or publication authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse

from dichiarazioni_pubbliche.senato_akoma_stenographic import import_senato_akoma_stenographic
from tools.dp468_senato_profile_crosscheck import MANIFEST, _ROW, read_batch

SOURCE_URL = (
    "https://raw.githubusercontent.com/SenatoDellaRepubblica/AkomaNtosoBulkData/"
    "bfac144eb5c54820971bc1020fece11aae56ec90/"
    "Leg19/Atto00055187/resaula/01457617-ra.akn.xml"
)
SOURCE_BLOB_SHA1 = "bec30c067a1a79e8b377af483cfc4bfb44d13896"
TOC_URL = (
    "https://www.senato.it/show-doc?id=1457617&leg=19&"
    "part=doc_dc-allegatoa_aa-ddltit_ddl1308-oggetto_a6ntadcdd&tipodoc=Resaula"
)
_RECEIPT_MARKER = b"\n__DP468_FINAL__:"


def fetch_html_or_xml(url: str, *, max_bytes: int = 600_000) -> tuple[str, bytes, str]:
    """Bounded native HTTPS fetch with a verified final URL and content type."""
    try:
        result = subprocess.run(
            [
                "curl", "-fsSL", "--max-time", "17", "--max-redirs", "3",
                "--max-filesize", str(max_bytes), "--proto", "=https",
                "--proto-redir", "=https",
                "-w", "\n__DP468_FINAL__:%{url_effective}\n%{content_type}", url,
            ],
            capture_output=True, check=True, timeout=19,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("DP468_STENOGRAM_HTTP_UNVERIFIED") from exc
    body, marker, rest = result.stdout.rpartition(_RECEIPT_MARKER)
    final, newline, content_type = rest.partition(b"\n")
    if not marker or not newline or not body or len(body) > max_bytes:
        raise ValueError("DP468_STENOGRAM_HTTP_UNVERIFIED")
    try:
        final_url = final.decode("ascii")
        mime = content_type.decode("ascii").split(";", 1)[0].strip()
    except UnicodeError as exc:
        raise ValueError("DP468_STENOGRAM_HTTP_UNVERIFIED") from exc
    if urlparse(final_url).scheme != "https":
        raise ValueError("DP468_STENOGRAM_HTTP_UNVERIFIED")
    return final_url, body, mime


class _TocLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current: tuple[str, list[str]] | None = None
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "a" and "toc-link" in (a.get("class") or "").split() and a.get("href"):
            self.current = (a["href"], [])

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current[1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current is not None:
            href, fragments = self.current
            self.links.append((" ".join("".join(fragments).split()), href))
            self.current = None


class _OfficialSpeech(HTMLParser):
    """Only rendered article content; navigation and injected scripts cannot match."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.ignored_content = 0
        self.chunks: list[str] = []
        self.person_dids: set[int] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "template", "noscript"}:
            self.ignored_content += 1
        a = dict(attrs)
        if tag == "div" and self.depth == 0 and "bgt" in (a.get("class") or "").split():
            self.depth = 1
        elif tag == "div" and self.depth:
            self.depth += 1
        if self.depth and tag == "a":
            parsed = urlparse(a.get("href") or "")
            qs = parse_qs(parsed.query)
            if parsed.hostname == "www.senato.it" and parsed.path == "/loc/link.asp":
                if qs.get("leg") == ["19"] and qs.get("tipodoc") == ["sanasen"]:
                    ids = qs.get("id", [])
                    if len(ids) == 1 and ids[0].isdigit():
                        self.person_dids.add(int(ids[0]))

    def handle_data(self, data: str) -> None:
        if self.depth and not self.ignored_content:
            self.chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template", "noscript"} and self.ignored_content:
            self.ignored_content -= 1
        if tag == "div" and self.depth:
            self.depth -= 1

    @property
    def text(self) -> str:
        return " ".join("".join(self.chunks).split())


def _require_official_intervention_url(url: str) -> None:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if (parsed.scheme != "https" or parsed.netloc != "www.senato.it"
            or parsed.path != "/show-doc" or set(qs) != {"id", "leg", "part", "tipodoc"}
            or qs["id"] != ["1457617"] or qs["leg"] != ["19"]
            or qs["tipodoc"] != ["Resaula"]
            or not qs["part"][0].startswith("doc_dc-ressten_rs-")
            or not re.search(r"[-_]intervento_", qs["part"][0])):
        raise ValueError("DP468_STENOGRAM_LINK_INVALID")


def validate_intervention(url: str, body: bytes, did: int, quote: str) -> str:
    _require_official_intervention_url(url)
    article = _OfficialSpeech()
    article.feed(body.decode("utf-8"))
    if did not in article.person_dids or " ".join(quote.split()) not in article.text:
        raise ValueError("DP468_STENOGRAM_WORDING_OR_SPEAKER_MISMATCH")
    return hashlib.sha256(body).hexdigest()


def _candidate_links(links: list[tuple[str, str]], surname: str) -> list[str]:
    matched = []
    for label, href in links:
        if re.match(rf"^{re.escape(surname)}(?!\w)", label, flags=re.IGNORECASE):
            url = urljoin(TOC_URL, href)
            _require_official_intervention_url(url)
            if url not in matched:
                matched.append(url)
    if not 1 <= len(matched) <= 25:
        raise ValueError("DP468_STENOGRAM_TOC_SPEAKER_MISSING")
    return matched


def real_readback(*, fetch=fetch_html_or_xml) -> dict[str, object]:
    manifest = MANIFEST.read_text(encoding="utf-8")
    source_hash, rows = read_batch(manifest)
    selected = manifest.split("## New first-batch text selection", 1)[1].split("\n## ", 1)[0]
    pins = {
        int(ordinal): (int(start), int(end), digest)
        for ordinal, _, _, start, end, digest in _ROW.findall(selected)
    }
    source_url, raw, mime = fetch(SOURCE_URL, max_bytes=3_000_000)
    if (source_url != SOURCE_URL or mime not in {"application/xml", "text/plain", "text/xml"}
            or hashlib.sha256(raw).hexdigest() != source_hash):
        raise ValueError("DP468_STENOGRAM_SOURCE_CHANGED")
    imported = import_senato_akoma_stenographic(
        raw, source_raw_url=SOURCE_URL, expected_blob_sha1=SOURCE_BLOB_SHA1,
    )
    toc_url, toc_bytes, toc_mime = fetch(TOC_URL)
    if toc_url != TOC_URL or toc_mime != "text/html":
        raise ValueError("DP468_STENOGRAM_TOC_UNVERIFIED")
    toc = _TocLinks()
    toc.feed(toc_bytes.decode("utf-8"))
    observations: list[dict[str, object]] = []
    page_cache: dict[str, tuple[str, bytes, str]] = {}
    for ordinal, surname, did in rows:
        result: dict[str, object] = {
            "ordinal": ordinal, "did": did, "surname": surname,
            "status": "HOLD_STENOGRAM_UNVERIFIED",
            "speaker_attribution_approved": False, "publication_authorized": False,
        }
        try:
            speech = next(item for item in imported.speeches if item.ordinal == ordinal)
            start, end, digest = pins[ordinal]
            quote = speech.review_text[start:end]
            if (speech.official_person_uri.rsplit("/", 1)[-1] != str(did)
                    or hashlib.sha256(quote.encode()).hexdigest() != digest):
                raise ValueError("DP468_STENOGRAM_PIN_MISMATCH")
            for url in _candidate_links(toc.links, surname):
                if url not in page_cache:
                    page_cache[url] = fetch(url)
                final, body, mime = page_cache[url]
                if mime != "text/html":
                    continue
                try:
                    observed_hash = validate_intervention(final, body, did, quote)
                except (UnicodeError, ValueError):
                    continue
                result.update({
                    "status": "OFFICIAL_STENOGRAM_TEXT_DID_MATCH_ONLY",
                    "intervention_url": final, "html_sha256": observed_hash,
                    "source_quote_sha256": digest,
                })
                break
        except (OSError, UnicodeError, ValueError, KeyError, StopIteration) as exc:
            result["reason"] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        observations.append(result)
    matched = sum(x["status"] == "OFFICIAL_STENOGRAM_TEXT_DID_MATCH_ONLY" for x in observations)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "original_source_sha256": source_hash,
        "official_toc_url": TOC_URL,
        "official_toc_html_sha256": hashlib.sha256(toc_bytes).hexdigest(),
        "candidates": len(rows), "matched": matched,
        "identity_approved": False, "publication_authorized": False,
        "observations": observations,
    }


def main() -> int:
    try:
        result = real_readback()
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "PRIVATE_HOLD", "reason": str(exc),
                          "publication_authorized": False}))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["matched"] == result["candidates"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
