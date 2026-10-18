#!/usr/bin/env python3
"""DP-244 private, read-only inventory of *attempted* source polling.

Polling rows are not evidence that a source's historical publication interval
has been enumerated. A covered interval requires separately reviewed
CoverageObservation receipts; this command never manufactures them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime  # noqa: E402


SOURCE_ATTEMPTS_SQL = """
SELECT coalesce(json_agg(row_to_json(item) ORDER BY item.source_type,
                         item.canonical_name, item.source_id), '[]'::json)::text
FROM (
    SELECT s.id AS source_id, s.canonical_name, s.source_type,
           s.language,
           count(p.id)::integer AS scheduler_decisions,
           count(p.id) FILTER (WHERE p.status IN (
               'HEALTHY', 'FAILED', 'BLOCKED', 'BUDGET_BLOCKED'
           ))::integer AS attempts,
           min(p.run_date) FILTER (WHERE p.status IN (
               'HEALTHY', 'FAILED', 'BLOCKED', 'BUDGET_BLOCKED'
           ))::text AS first_attempt_date,
           max(p.run_date) FILTER (WHERE p.status IN (
               'HEALTHY', 'FAILED', 'BLOCKED', 'BUDGET_BLOCKED'
           ))::text AS last_attempt_date,
           max(p.run_date) FILTER (WHERE p.status = 'HEALTHY')::text AS last_healthy_date,
           count(p.id) FILTER (WHERE p.status = 'HEALTHY')::integer AS healthy_attempts,
           count(p.id) FILTER (WHERE p.status = 'FAILED')::integer AS failed_attempts,
           count(p.id) FILTER (WHERE p.status = 'BLOCKED')::integer AS blocked_attempts,
           count(p.id) FILTER (WHERE p.status = 'BUDGET_BLOCKED')::integer AS budget_blocked_attempts,
           count(p.id) FILTER (WHERE p.status LIKE 'SKIPPED_%')::integer AS skipped_decisions,
           count(p.id) FILTER (WHERE p.status = 'RUNNING')::integer AS pending_decisions,
           (SELECT count(*)::integer FROM content_item c WHERE c.source_id = s.id) AS content_rows,
           (SELECT count(*)::integer FROM content_capture cap
              JOIN content_item c ON c.id = cap.content_id
              WHERE c.source_id = s.id) AS capture_rows
    FROM source s
    LEFT JOIN source_poll_run_source p ON p.source_id = s.id
    GROUP BY s.id, s.canonical_name, s.source_type, s.language
) item;
"""

_FIELDS = frozenset(
    {
        "source_id",
        "canonical_name",
        "source_type",
        "language",
        "scheduler_decisions",
        "attempts",
        "first_attempt_date",
        "last_attempt_date",
        "last_healthy_date",
        "healthy_attempts",
        "failed_attempts",
        "blocked_attempts",
        "budget_blocked_attempts",
        "skipped_decisions",
        "pending_decisions",
        "content_rows",
        "capture_rows",
    }
)


def validate_inventory(raw: object) -> list[dict]:
    """Reject malformed DB output instead of showing false zero coverage."""
    if type(raw) is not list or len(raw) > 10000:
        raise ValueError("COVERAGE_REPORT_ROWS_INVALID")
    rows = []
    seen = set()
    for row in raw:
        if type(row) is not dict or set(row) != _FIELDS:
            raise ValueError("COVERAGE_REPORT_SCHEMA_INVALID")
        for field in ("source_id", "canonical_name", "source_type"):
            value = row[field]
            if type(value) is not str or not value.strip() or len(value) > 400:
                raise ValueError("COVERAGE_REPORT_SOURCE_INVALID")
        if row["source_id"] in seen:
            raise ValueError("COVERAGE_REPORT_DUPLICATE_SOURCE")
        seen.add(row["source_id"])
        if row["language"] is not None and (
            type(row["language"]) is not str or len(row["language"]) > 40
        ):
            raise ValueError("COVERAGE_REPORT_LANGUAGE_INVALID")
        for field in (
            "scheduler_decisions",
            "attempts",
            "healthy_attempts",
            "failed_attempts",
            "blocked_attempts",
            "budget_blocked_attempts",
            "skipped_decisions",
            "pending_decisions",
            "content_rows",
            "capture_rows",
        ):
            if type(row[field]) is not int or row[field] < 0:
                raise ValueError("COVERAGE_REPORT_COUNT_INVALID")
        if (
            row["healthy_attempts"]
            + row["failed_attempts"]
            + row["blocked_attempts"]
            + row["budget_blocked_attempts"]
            != row["attempts"]
        ):
            raise ValueError("COVERAGE_REPORT_ATTEMPTS_INVALID")
        if (
            row["attempts"] + row["skipped_decisions"] + row["pending_decisions"]
            != row["scheduler_decisions"]
        ):
            raise ValueError("COVERAGE_REPORT_DECISIONS_INVALID")
        first, last = row["first_attempt_date"], row["last_attempt_date"]
        if row["attempts"] == 0:
            if first is not None or last is not None:
                raise ValueError("COVERAGE_REPORT_WINDOW_INVALID")
        else:
            try:
                if not (
                    type(first) is str
                    and type(last) is str
                    and datetime.fromisoformat(first).date()
                    <= datetime.fromisoformat(last).date()
                    and len(first) == len(last) == 10
                ):
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise ValueError("COVERAGE_REPORT_WINDOW_INVALID") from exc
        healthy_date = row["last_healthy_date"]
        if healthy_date is not None:
            try:
                if (
                    row["healthy_attempts"] == 0
                    or type(healthy_date) is not str
                    or len(healthy_date) != 10
                    or not (first <= healthy_date <= last)
                    or datetime.fromisoformat(healthy_date).date().isoformat()
                    != healthy_date
                ):
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise ValueError("COVERAGE_REPORT_HEALTHY_DATE_INVALID") from exc
        elif row["healthy_attempts"]:
            raise ValueError("COVERAGE_REPORT_HEALTHY_DATE_INVALID")
        rows.append(row)
    return sorted(
        rows, key=lambda r: (r["source_type"], r["canonical_name"], r["source_id"])
    )


def _cell(value: object) -> str:
    return (
        str(value if value is not None else "sconosciuta")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def render_report(rows: list[dict], *, generated_at: str) -> str:
    """Human-readable private report with deliberately conservative semantics."""
    decisions = sum(row["scheduler_decisions"] for row in rows)
    attempts = sum(row["attempts"] for row in rows)
    skipped = sum(row["skipped_decisions"] for row in rows)
    pending = sum(row["pending_decisions"] for row in rows)
    captures = sum(row["capture_rows"] for row in rows)
    lines = [
        "# Copertura delle fonti — osservazioni disponibili",
        "",
        f"Rilevazione UTC: {generated_at}. Fonti censite: {len(rows)}; "
        f"decisioni scheduler: {decisions}; esiti di tentativo: {attempts}; "
        f"saltati: {skipped}; in corso: {pending}; Capture: {captures}.",
        "",
        "Le date indicano **solo i giorni di esiti di tentativo registrati**, "
        "esclusi i poll saltati. FAILED e BLOCKED descrivono anche tentativi "
        "senza recupero di documenti. Un'esecuzione diagnostica non attesta "
        "di per sé un'acquisizione. Non indicano che tutti i documenti del "
        "periodo siano stati raccolti.",
        "Nessun intervallo è dichiarato *coperto integralmente*: "
        "mancano qui attestazioni indipendenti di enumerazione e relativi diritti.",
        "",
        "| Fonte | Famiglia | Lingua | Esiti (primo → ultimo) | Ultimo poll sano | Sani / falliti / bloccati / budget | Saltati / in corso | Contenuti / Capture | Lacuna |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        window = (
            f"{row['first_attempt_date']} → {row['last_attempt_date']}"
            if row["attempts"]
            else "nessun esito di tentativo"
        )
        gap = (
            "nessun esito di tentativo; copertura sconosciuta"
            if not row["attempts"]
            else "periodi non enumerati / completezza da verificare"
        )
        lines.append(
            f"| {_cell(row['canonical_name'])} | {_cell(row['source_type'])} | {_cell(row['language'])}"
            f" | {window} | {_cell(row['last_healthy_date']) if row['last_healthy_date'] else 'nessuno'}"
            f" | {row['healthy_attempts']} / {row['failed_attempts']} / {row['blocked_attempts']} / {row['budget_blocked_attempts']}"
            f" | {row['skipped_decisions']} / {row['pending_decisions']}"
            f" | {row['content_rows']} / {row['capture_rows']} | {gap} |"
        )
    lines.extend(
        [
            "",
            "Lacune comuni: estremi storici dell'archivio, periodi tra i tentativi, "
            "versioni corrette e permessi d'uso non verificati. "
            "Un tentativo HEALTHY attesta il solo esito del poll, non copertura esaustiva, "
            "verità fattuale né autorizzazione a pubblicare.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL")
    )
    parser.add_argument(
        "--output", type=Path, help="New private Markdown file; must not exist"
    )
    args = parser.parse_args()
    data = PsqlRuntime(args.database_url).run(SOURCE_ATTEMPTS_SQL)
    rows = validate_inventory(json.loads(data))
    rendered = render_report(
        rows, generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    if args.output:
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
