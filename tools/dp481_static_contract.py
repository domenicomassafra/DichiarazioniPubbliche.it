"""Required public static files for immutable MiniPC releases."""

from __future__ import annotations

from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
from xml.etree import ElementTree
from urllib.parse import urlsplit


REQUIRED_STATIC_FILES = frozenset({
    "index.html", "esplora/index.html", "metodo/index.html",
    "correzioni/index.html", "dati/index.html", "progetto/index.html",
    "accedi/index.html", "account/index.html", "privacy/index.html",
    "segnalazioni/index.html", "favicon.svg", "robots.txt",
    "sitemap.xml", "search-index.v1.json",
})
VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"})


class _HTMLDocument(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.structure: list[str] = []
        self.icon = False
        self.stack: list[str] = []
        self.main_has_text = False
        self.has_main = False
        self.malformed = False
        self.references: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"html", "head", "body"}:
            self.structure.append("+" + tag)
        properties = dict(attrs)
        if tag not in VOID_TAGS:
            self.stack.append(tag)
        if tag == "main":
            self.has_main = True
        for attribute in ("href", "src"):
            value = properties.get(attribute)
            if value and value.startswith("/_astro/"):
                self.references.add(urlsplit(value).path.lstrip("/"))
        if (tag == "link" and "icon" in (properties.get("rel") or "").split()
                and properties.get("href") == "/favicon.svg"):
            self.icon = True

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack[-1] != tag:
            self.malformed = True
        else:
            self.stack.pop()
        if tag in {"html", "head", "body"}:
            self.structure.append("-" + tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if "main" in self.stack and not {"script", "style"}.intersection(self.stack) and data.strip():
            self.main_has_text = True


def check_static_contract(release: Path, assets: dict[str, str]) -> None:
    """Reject incomplete or malformed runtime bundles, including sealed releases."""
    static = release / "static"
    projection = release / "projection/index.json"
    if any(f"static/{name}" not in assets for name in REQUIRED_STATIC_FILES):
        raise ValueError("DP481_STATIC_ASSET_MISSING")
    try:
        for name in (n for n in REQUIRED_STATIC_FILES if n.endswith(".html")):
            parser = _HTMLDocument()
            parser.feed((static / name).read_text(encoding="utf-8"))
            parser.close()
            if name == "index.html" and not parser.icon:
                raise ValueError("DP481_STATIC_ICON_LINK_MISSING")
            if (parser.structure != ["+html", "+head", "-head", "+body", "-body", "-html"]
                    or parser.stack or parser.malformed or not parser.has_main or not parser.main_has_text):
                raise ValueError("DP481_STATIC_FORMAT_INVALID")
            if any(f"static/{ref}" not in assets for ref in parser.references):
                raise ValueError("DP481_STATIC_ASSET_MISSING")
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
        source = json.loads(projection.read_text(encoding="utf-8"))
        fields = {"schema_version", "projection_schema_version", "projection_sha256",
                  "generated_at", "index_sha256", "records"}
        if (not isinstance(search, dict) or not isinstance(source, dict)
                or set(search) != fields
                or search.get("schema_version") != "dichiarazioni-pubbliche-search-index-v1"
                or search.get("projection_schema_version") != source.get("schema_version")
                or search.get("projection_sha256") != source.get("dataset_sha256")
                or search.get("generated_at") != source.get("generated_at")
                or not isinstance(search.get("records"), list)
                or not re.fullmatch(r"[0-9a-f]{64}", str(search.get("index_sha256")))):
            raise ValueError("DP481_STATIC_FORMAT_INVALID")
        material = {key: value for key, value in search.items() if key != "index_sha256"}
        encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != search["index_sha256"]:
            raise ValueError("DP481_STATIC_FORMAT_INVALID")
    except (OSError, UnicodeError, ElementTree.ParseError, json.JSONDecodeError):
        raise ValueError("DP481_STATIC_FORMAT_INVALID") from None
