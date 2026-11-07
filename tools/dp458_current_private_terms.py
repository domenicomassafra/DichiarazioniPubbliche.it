"""Current official source and licence evidence for the private EU AVS candidate."""
from __future__ import annotations

import hashlib
import html
import json
import re

from dichiarazioni_pubbliche.source_watcher import fetch_bytes


def current_private_rights_evidence(page: str, terms: str, quote: str) -> str:
    digests: dict[str, str] = {}
    for url, required in (
        (page, ("I-293056", "European Parliament", quote)),
        (terms, ("Creative Commons Attribution 4.0 International License",
                 "identifiable private individuals", "third parties",
                 "Any reuse must not distort")),
    ):
        response = fetch_bytes(url, max_response_bytes=400_000, allow_redirects=False)
        if response.status_code != 200 or response.final_url != url or response.media_type != "text/html":
            raise RuntimeError("DP458_RIGHTS_OFFICIAL_PAGE_UNAVAILABLE")
        visible = html.unescape(re.sub(r"<[^>]+>", " ", response.body.decode("utf-8", "replace")))
        visible = re.sub(r"\s+", " ", visible).casefold()
        if not all(term.casefold() in visible for term in required):
            raise RuntimeError("DP458_RIGHTS_OFFICIAL_EVIDENCE_CHANGED")
        digests[url] = hashlib.sha256(response.body).hexdigest()
    return hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()
