"""Required public static files for immutable MiniPC releases."""

from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
from xml.etree import ElementTree


REQUIRED_STATIC_FILES = frozenset({
    "index.html", "esplora/index.html", "metodo/index.html",
    "correzioni/index.html", "dati/index.html", "progetto/index.html",
    "accedi/index.html", "account/index.html", "privacy/index.html",
    "segnalazioni/index.html", "favicon.svg", "robots.txt",
    "sitemap.xml", "search-index.v1.json",
})


class _HTMLDocument(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.structure: list[str] = []
        self.icon = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"html", "head", "body"}:
            self.structure.append("+" + tag)
        properties = dict(attrs)
        if (tag == "link" and "icon" in (properties.get("rel") or "").split()
                and properties.get("href") == "/favicon.svg"):
            self.icon = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"html", "head", "body"}:
            self.structure.append("-" + tag)


def check_static_contract(static: Path, assets: dict[str, str]) -> None:
    """Reject incomplete or malformed runtime bundles, including sealed releases."""
    if any(f"static/{name}" not in assets for name in REQUIRED_STATIC_FILES):
        raise ValueError("DP481_STATIC_ASSET_MISSING")
    try:
        for name in (n for n in REQUIRED_STATIC_FILES if n.endswith(".html")):
            parser = _HTMLDocument()
            parser.feed((static / name).read_text(encoding="utf-8"))
            parser.close()
            if name == "index.html" and not parser.icon:
                raise ValueError("DP481_STATIC_ICON_LINK_MISSING")
            if parser.structure != ["+html", "+head", "-head", "+body", "-body", "-html"]:
                raise ValueError("DP481_STATIC_FORMAT_INVALID")
        favicon = ElementTree.fromstring((static / "favicon.svg").read_bytes())
        if favicon.tag != "{http://www.w3.org/2000/svg}svg":
            raise ValueError("DP481_STATIC_FORMAT_INVALID")
        sitemap = ElementTree.fromstring((static / "sitemap.xml").read_bytes())
        if sitemap.tag.rsplit("}", 1)[-1] != "urlset":
            raise ValueError("DP481_STATIC_FORMAT_INVALID")
        robots = (static / "robots.txt").read_text(encoding="utf-8")
        lines = [line.strip() for line in robots.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        if (not any(re.fullmatch(r"User-agent\s*:\s*\S+", line, re.I) for line in lines)
                or any(not re.fullmatch(r"[A-Za-z][A-Za-z-]*\s*:\s*\S+.*", line) for line in lines)):
            raise ValueError("DP481_STATIC_FORMAT_INVALID")
        search = json.loads((static / "search-index.v1.json").read_text(encoding="utf-8"))
        if not isinstance(search, dict):
            raise ValueError("DP481_STATIC_FORMAT_INVALID")
    except (OSError, UnicodeError, ElementTree.ParseError, json.JSONDecodeError):
        raise ValueError("DP481_STATIC_FORMAT_INVALID") from None
