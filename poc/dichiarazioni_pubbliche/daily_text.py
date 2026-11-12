"""DP-638 — text primitives shared by the daily machine.

What is published is always the source's own characters: these helpers
match on a folded form and return offsets in the original text.
"""
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

class DailyMachineError(RuntimeError):
    """A step of the daily machine failed in a way the run must report."""


# --------------------------------------------------------------------------
_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u00b4": "'"})
_QUOTES = str.maketrans({"\u201c": '"', "\u201d": '"', "\u00ab": '"', "\u00bb": '"'})


def bounded_text(value: object, limit: int) -> str:
    text = "" if value is None else str(value)
    return text[:limit]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _search_form(value: str) -> tuple[str, list[int]]:
    """Lowercase, accent- and punctuation-free form plus an index map.

    The map lets a match found on the normalised form be turned back into the
    exact substring of the captured source, so what is stored and published is
    always the source's own characters and never the model's rendering.
    """

    normalized: list[str] = []
    index: list[int] = []
    for position, character in enumerate(value.translate(_APOSTROPHES).translate(_QUOTES)):
        folded = unicodedata.normalize("NFKD", character.casefold())
        for part in folded:
            if unicodedata.combining(part):
                continue
            if part.isalnum():
                normalized.append(part)
                index.append(position)
            else:
                normalized.append(" ")
                index.append(position)
    return "".join(normalized), index


def find_verbatim(haystack: str, needle: str, *, min_tokens: int = 4) -> tuple[int, int] | None:
    """Return the exact ``(start, end)`` of ``needle`` inside ``haystack``.

    Matching ignores case, accents, punctuation and whitespace runs, because
    automatic captions carry no punctuation and a model may add some. The
    returned offsets always point at the source text, so the caller can store
    the source's own characters.
    """

    target, index = _search_form(haystack)
    sought, _ = _search_form(needle)
    sought = " ".join(sought.split())
    if len(sought.split()) < min_tokens:
        return None
    compact_haystack = " ".join(target.split())
    position = compact_haystack.find(sought)
    if position < 0:
        return None
    # Map the compact-space position back to characters of the original.
    consumed = 0
    start_index = None
    end_index = None
    previous_space = True
    for original_position, character in enumerate(target):
        if character == " ":
            if previous_space:
                continue
            previous_space = True
            consumed += 1
        else:
            previous_space = False
            consumed += 1
        if start_index is None and consumed == position + 1:
            start_index = index[original_position]
        if start_index is not None and consumed == position + len(sought):
            end_index = index[original_position] + 1
            break
    if start_index is None or end_index is None:
        return None
    return start_index, end_index


_JSON_FENCE = re.compile(r"^\s*```(?:json)?|```\s*$", re.MULTILINE)


def parse_model_json(text: str) -> Any:
    cleaned = _JSON_FENCE.sub("", text or "").strip()
    if not cleaned:
        raise DailyMachineError("MODEL_EMPTY_RESPONSE")
    try:
        return json.loads(cleaned)
    except ValueError:
        first = cleaned.find("{")
        last = cleaned.rfind("}")
        if first < 0 or last <= first:
            raise DailyMachineError("MODEL_RESPONSE_NOT_JSON") from None
        try:
            return json.loads(cleaned[first : last + 1])
        except ValueError as exc:
            raise DailyMachineError("MODEL_RESPONSE_NOT_JSON") from exc


# --------------------------------------------------------------------------
# HTML -> readable text (no third-party parser is installed on the MiniPC)
# --------------------------------------------------------------------------

_SKIP_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "header",
    "footer",
    "nav",
    "aside",
    "form",
    "figure",
}
_BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "br", "blockquote", "section", "article"}


class _ParagraphParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.article_blocks: list[str] = []
        self._article_depth = 0
        self._buffer: list[str] = []
        self._skip_depth = 0
        self._title: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag == "title":
            self._in_title = True
            return
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in {"article", "main"}:
            self._article_depth += 1
        if tag in _BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            return
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in {"article", "main"} and self._article_depth:
            self._flush()
            self._article_depth -= 1
            return
        if tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title.append(data)
            return
        if self._skip_depth:
            return
        self._buffer.append(data)

    def _flush(self) -> None:
        value = " ".join("".join(self._buffer).split())
        if value:
            self.blocks.append(value)
            if self._article_depth:
                self.article_blocks.append(value)
        self._buffer = []

    def close(self) -> None:
        super().close()
        self._flush()

    @property
    def title(self) -> str:
        return " ".join("".join(self._title).split())


def html_to_text(markup: str) -> str:
    parser = _ParagraphParser()
    parser.feed(markup)
    parser.close()
    article = "\n".join(parser.article_blocks)
    if len(article) >= 400:
        return article
    paragraphs = [block for block in parser.blocks if len(block) > 40]
    if not paragraphs:
        paragraphs = [block for block in parser.blocks if block]
    return "\n".join(paragraphs)
