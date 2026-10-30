"""Required public static files for immutable MiniPC releases."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


REQUIRED_STATIC_FILES = frozenset({
    "index.html", "esplora/index.html", "metodo/index.html",
    "correzioni/index.html", "dati/index.html", "progetto/index.html",
    "accedi/index.html", "account/index.html", "privacy/index.html",
    "segnalazioni/index.html", "favicon.svg", "robots.txt",
    "sitemap.xml", "search-index.v1.json",
})


class _IconLink(HTMLParser):
    found = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        properties = dict(attrs)
        if (tag == "link" and "icon" in (properties.get("rel") or "").split()
                and properties.get("href") == "/favicon.svg"):
            self.found = True


def check_static_contract(static: Path, assets: dict[str, str]) -> None:
    """Reject incomplete runtime bundles, including historically signed releases."""
    if any(f"static/{name}" not in assets for name in REQUIRED_STATIC_FILES):
        raise ValueError("DP481_STATIC_ASSET_MISSING")
    try:
        parser = _IconLink()
        parser.feed((static / "index.html").read_text(encoding="utf-8"))
        parser.close()
    except (OSError, UnicodeError):
        raise ValueError("DP481_STATIC_ICON_LINK_MISSING") from None
    if not parser.found:
        raise ValueError("DP481_STATIC_ICON_LINK_MISSING")
