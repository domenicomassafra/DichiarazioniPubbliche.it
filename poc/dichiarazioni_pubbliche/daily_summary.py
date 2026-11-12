"""DP-638 — the evening summary to the owner, through the existing delivery."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Sequence

from dichiarazioni_pubbliche.daily_config import DailyConfig
from dichiarazioni_pubbliche.daily_store import DailyStore
from dichiarazioni_pubbliche.daily_model import fetch_text
from dichiarazioni_pubbliche.daily_text import DailyMachineError, bounded_text


def evening_summary(
    store: DailyStore, day: str,
    *, fetcher: Callable[..., tuple[int, str]] = fetch_text,
) -> str:
    # Internal readiness is not publication: only the installed public API counts.
    status, text = fetcher("https://dichiarazionipubbliche.it/api/v1/index.json")
    if status != 200:
        raise DailyMachineError(f"PUBLICATION_READBACK_HTTP_{status}")
    try:
        bundle = json.loads(text)
        rows = [row for row in bundle["dossiers"] if str(row["finding"].get("published_at") or "")[:10] == day]
    except (ValueError, KeyError, TypeError) as exc:
        raise DailyMachineError("PUBLICATION_READBACK_INVALID") from exc
    published: list[tuple[dict[str, Any], str]] = []
    for row in rows:
        slug = re.sub(r"[^a-z0-9]+", "-", str(row.get("finding_id") or "").lower()).strip("-")
        if not slug:
            continue
        public_url = f"https://dichiarazionipubbliche.it/dichiarazioni/{slug}/"
        try:
            page_status, _ = fetcher(public_url, timeout=8)
        except DailyMachineError:
            continue
        if page_status == 200:
            published.append((row, public_url))
    if not published:
        return (
            "Dichiarazioni Pubbliche, "
            + day
            + ": nessuna dichiarazione pubblicata oggi con un verdetto."
        )
    lines = [f"Dichiarazioni Pubbliche, {day}: {len(published)} dichiarazioni pubblicate."]
    for row, public_url in published:
        lines.append(
            "- {speaker}: \"{quote}\" ({verdict}, {publisher}) {url}".format(
                speaker=(row.get("speaker") or {}).get("name") or "persona non risolta",
                quote=bounded_text(row.get("claim"), 160),
                verdict=(row.get("finding") or {}).get("assessment"),
                publisher="Dichiarazioni Pubbliche",
                url=public_url,
            )
        )
    return "\n".join(lines)


def deliver_evening_summary(
    text: str,
    *,
    config: DailyConfig,
    summary_file: Path | None,
    deliver: bool,
) -> dict[str, Any]:
    """Hand the summary to the already configured Hermes delivery.

    ``deliver`` is the only path that sends anything; the scheduled unit passes
    it, a proof run does not, so a dry run never reaches the owner.
    """

    evening = dict(config.raw.get("evening") or {})
    target = str(evening.get("target") or "")
    sender = evening.get("sender") or []
    result: dict[str, Any] = {
        "target": target,
        "chars": len(text),
        "delivered": False,
        "dry_run": not deliver,
    }
    if summary_file is not None:
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        summary_file.write_text(text, encoding="utf-8")
        result["summary_file"] = str(summary_file)
    if not deliver:
        return result
    if not evening.get("enabled", False):
        raise DailyMachineError("EVENING_DELIVERY_DISABLED")
    if not sender or summary_file is None:
        raise DailyMachineError("EVENING_DELIVERY_NOT_CONFIGURED")
    completed = subprocess.run(  # noqa: S603
        [*[str(part) for part in sender], "--file", str(summary_file)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    result["exit_code"] = completed.returncode
    if completed.returncode != 0:
        result["error"] = (completed.stderr or completed.stdout or "")[:400]
        return result
    result["delivered"] = True
    return result
