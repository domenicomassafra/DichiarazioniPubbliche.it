"""Bounded, escaped private Discovery Inbox HTML fragment (no action controls)."""

from __future__ import annotations

import html
import re

from dichiarazioni_pubbliche.studio_discovery_triage_contract import _validated_ref

_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


def render_private_inbox_fragment(
    page: dict[str, object], *, version: str, dispositions: frozenset[str],
) -> str:
    """Render approved Inbox metadata only; never source bodies or mutation links."""
    if not isinstance(page, dict) or page.get("contract_version") != version:
        raise ValueError("STUDIO_INBOX_FRAGMENT_CONTRACT_INVALID")
    collection = _validated_ref(page.get("collection_id"))
    rows = page.get("rows")
    if not isinstance(rows, list) or len(rows) > 30:
        raise ValueError("STUDIO_INBOX_FRAGMENT_ROWS_INVALID")

    def safe(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("STUDIO_INBOX_FRAGMENT_FIELD_INVALID")
        return html.escape(value, quote=True)

    def reason(value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not _CODE.fullmatch(value):
            raise ValueError("STUDIO_INBOX_REASON_INVALID")
        return value

    result = [
        '<section class="studio-discovery-inbox" aria-labelledby="dp417-inbox-heading">',
        '<h2 id="dp417-inbox-heading">Discovery Inbox · sola lettura</h2>',
        f'<p>Raccolta: <code>{safe(collection)}</code>. '
        'Le annotazioni non autorizzano acquisizione, verifica o pubblicazione.</p>',
        '<ol class="studio-discovery-inbox__rows">',
    ]
    for row in rows:
        if not isinstance(row, dict) or row.get("collection_id") != collection:
            raise ValueError("STUDIO_INBOX_FRAGMENT_SCOPE_INVALID")
        hit_id = _validated_ref(row.get("hit_id"))
        queue = row.get("queue")
        if not isinstance(queue, str) or queue not in dispositions:
            raise ValueError("STUDIO_INBOX_STATE_INVALID")
        path = row.get("provenance_path")
        if not isinstance(path, dict) or path.get("hit_id") != hit_id or path.get("collection_id") != collection:
            raise ValueError("STUDIO_INBOX_FRAGMENT_PATH_INVALID")
        blocks = row.get("unblock_conditions")
        if not isinstance(blocks, list) or len(blocks) > 24:
            raise ValueError("STUDIO_INBOX_FRAGMENT_BLOCKERS_INVALID")
        result.append('<li class="studio-discovery-inbox__row">')
        result.append(f'<h3><code>{safe(hit_id)}</code> · {safe(queue)}</h3>')
        result.append('<details><summary>Provenienza e motivi del blocco</summary>')
        result.append('<dl>')
        for key, label in (("run_id", "Run"), ("attempt_id", "Tentativo"),
                           ("query_id", "Query ID"), ("manifest_id", "Manifest")):
            value = path.get(key)
            if key != "attempt_id" or value is not None:
                value = _validated_ref(value)
            result.append(f'<dt>{label}</dt><dd><code>{safe(value or "non disponibile")}</code></dd>')
        result.append('</dl><ul>')
        for block in blocks:
            if not isinstance(block, dict):
                raise ValueError("STUDIO_INBOX_FRAGMENT_BLOCKERS_INVALID")
            code = reason(block.get("blocker"))
            condition = reason(block.get("unblock_condition"))
            if code is None or condition is None:
                raise ValueError("STUDIO_INBOX_FRAGMENT_BLOCKERS_INVALID")
            result.append(f'<li><code>{safe(code)}</code> · {safe(condition)}</li>')
        result.append('</ul></details></li>')
    result.extend(['</ol>', '</section>'])
    return "".join(result)
