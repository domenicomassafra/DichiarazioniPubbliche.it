"""Restore-drill CLI (DP-502).

The I/O half of the drill. ``deploy/ops/restore_drill.sh`` runs pg_dump/
pg_restore/psql and hands the observed numbers to this module, which applies
the pure comparison rules in :mod:`dichiarazioni_pubbliche.ops.restore_verify` and
prints the verdict.

This module deliberately cannot regenerate a projection or a row to make a
comparison pass. Its only inputs are observed counts and observed hashes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dichiarazioni_pubbliche.ops.restore_verify import (
    build_report,
    check_bundle,
    format_report,
    read_dataset_sha256,
    validate_drill,
)


def _load_counts(path: Path) -> dict[str, tuple[object, object]]:
    counts: dict[str, tuple[object, object]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        table, source, restored = parts
        counts[table] = (None if source == "null" else source,
                         None if restored == "null" else restored)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a PostgreSQL restore drill against its backup."
    )
    parser.add_argument("--counts", type=Path, required=True)
    parser.add_argument(
        "--bundle",
        action="append",
        default=[],
        metavar="LABEL:SOURCE_SHA:RESTORED_SHA",
        help=(
            "Compare a projection bundle dataset_sha256 across backup/restore, "
            "as a single colon-delimited argument."
        ),
    )
    parser.add_argument(
        "--rebuilt-bundle",
        action="append",
        default=[],
        metavar="LABEL:PATH",
        help=(
            "Compare a backed-up bundle's dataset_sha256 (read from PATH) "
            "against a bundle rebuilt from the restored database."
        ),
    )
    parser.add_argument(
        "--rebuilt-sha",
        action="append",
        default=[],
        metavar="LABEL:SHA",
        help="dataset_sha256 observed in a bundle rebuilt from the restored DB.",
    )
    args = parser.parse_args(argv)

    if not args.counts.is_file():
        print(f"RESTORE DRILL: counts file not found: {args.counts}", file=sys.stderr)
        return 2

    bundles = []
    for entry in args.bundle:
        parts = entry.split(":")
        if len(parts) != 3:
            print(
                f"RESTORE DRILL: malformed --bundle entry: {entry!r}", file=sys.stderr
            )
            return 2
        label, source_sha, restored_sha = parts
        bundles.append(
            check_bundle(
                label,
                None if source_sha in {"MISSING", "null", ""} else source_sha,
                None if restored_sha in {"MISSING", "null", ""} else restored_sha,
            )
        )

    rebuilt = dict(
        entry.split(":", 1)
        for entry in args.rebuilt_sha
        if len(entry.split(":", 1)) == 2
    )
    rebundled = list(bundles)
    for entry in args.rebuilt_bundle:
        parts = entry.split(":", 1)
        if len(parts) != 2:
            print(
                f"RESTORE DRILL: malformed --rebuilt-bundle entry: {entry!r}",
                file=sys.stderr,
            )
            return 2
        label, path = parts
        rebundled.append(
            check_bundle(label, read_dataset_sha256(path), rebuilt.get(label))
        )
    report = build_report(_load_counts(args.counts), rebundled)
    defects = validate_drill(report)
    print(format_report(report))
    if defects:
        print("RESTORE DRILL: DEFECTS " + "; ".join(defects), file=sys.stderr)
    return 0 if report.passed and not defects else 1


if __name__ == "__main__":
    raise SystemExit(main())
