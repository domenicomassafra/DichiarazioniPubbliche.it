#!/usr/bin/env python3
"""Read-only canonical backlog status report."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ROW = re.compile(r"^\| (DP-\d{3}) \| (DONE|IN PROGRESS|BLOCKED|FUTURE|READY) \|", re.M)
_STATUS = re.compile(r"^Status:\s*([^\r\n]+)", re.M)


def ticket_snapshot(root: Path = ROOT) -> dict[str, object]:
    """Return counts only when PLAN and all corresponding ticket headers agree."""
    plan = (root / "PLAN.md").read_text(encoding="utf-8")
    rows = _ROW.findall(plan)
    ids = [ticket for ticket, _ in rows]
    if not rows or len(set(ids)) != len(rows):
        raise ValueError("TICKET_PLAN_DUPLICATE_OR_EMPTY")
    statuses = dict(rows)
    files: dict[str, Path] = {}
    for path in (root / "docs/tickets").glob("DP-*.md"):
        match = re.match(r"^(DP-\d{3})(?:-|\.md$)", path.name)
        if not match or match.group(1) in files:
            raise ValueError("TICKET_FILE_DUPLICATE_OR_INVALID")
        files[match.group(1)] = path
    if set(statuses) != set(files):
        raise ValueError("TICKET_PLAN_FILE_SET_DRIFT")
    for ticket, path in files.items():
        match = _STATUS.search(path.read_text(encoding="utf-8"))
        if match is None:
            raise ValueError(f"TICKET_STATUS_HEADER_MISSING:{ticket}")
        actual = match.group(1).strip().replace("IN_PROGRESS", "IN PROGRESS").split(" (", 1)[0]
        if actual != statuses[ticket]:
            raise ValueError(f"TICKET_STATUS_DRIFT:{ticket}")
    counts = Counter(statuses.values())
    open_tickets = sorted(ticket for ticket, status in statuses.items() if status != "DONE")
    return {
        "version": "ticket-status-snapshot-v1",
        "total": len(rows),
        "done": counts["DONE"],
        "in_progress": counts["IN PROGRESS"],
        "blocked": counts["BLOCKED"],
        "future": counts["FUTURE"],
        "ready": counts["READY"],
        "not_done": len(open_tickets),
        "not_done_ticket_ids": open_tickets,
        "files_agree_with_plan": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = ticket_snapshot()
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"{report['not_done']} ticket mancanti su {report['total']}; "
              f"{report['done']} DONE, {report['in_progress']} IN PROGRESS, "
              f"{report['blocked']} BLOCKED, {report['future']} FUTURE, "
              f"{report['ready']} READY.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
