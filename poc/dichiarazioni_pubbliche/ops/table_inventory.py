"""Durable PostgreSQL table inventory for DP-502 backup/restore checks.

The repository schema and ordered migrations are the source declaration for
tables that a deployed database is expected to contain.  Backup still verifies
that declaration against PostgreSQL's live catalog before it writes a manifest,
so schema drift fails closed instead of silently producing a partial receipt.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Sequence


_CREATE_TABLE_START = re.compile(
    r"\bCREATE\s+(?:UNLOGGED\s+)?TABLE\b",
    re.IGNORECASE,
)
_CREATE_TABLE_NAME = re.compile(
    r"\bCREATE\s+(?:UNLOGGED\s+)?TABLE\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:(?P<schema>[a-zA-Z_][a-zA-Z0-9_]*)\.)?"
    r"(?P<table>[a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)
_SAFE_TABLE_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


def repository_sql_paths(repo_root: Path) -> tuple[Path, ...]:
    schema = repo_root / "db" / "schema.v1.sql"
    migrations = repo_root / "db" / "migrations"
    if not schema.is_file():
        raise ValueError(f"schema missing: {schema}")
    if not migrations.is_dir():
        raise ValueError(f"migration directory missing: {migrations}")
    return (schema, *tuple(sorted(migrations.glob("*.sql"))))


def declared_persistent_tables(sql_paths: Iterable[Path]) -> tuple[str, ...]:
    tables: set[str] = set()
    statement_count = 0
    parsed_count = 0

    for path in sql_paths:
        text = path.read_text(encoding="utf-8")
        starts = tuple(_CREATE_TABLE_START.finditer(text))
        matches = tuple(_CREATE_TABLE_NAME.finditer(text))
        statement_count += len(starts)
        parsed_count += len(matches)

        if len(starts) != len(matches):
            raise ValueError(
                f"unparseable CREATE TABLE statement in {path}: "
                f"starts={len(starts)} parsed={len(matches)}"
            )

        for match in matches:
            schema = (match.group("schema") or "public").lower()
            table = match.group("table").lower()
            if schema != "public":
                raise ValueError(
                    f"unsupported persistent table schema {schema!r} in {path}"
                )
            if not _SAFE_TABLE_NAME.fullmatch(table):
                raise ValueError(f"unsafe table identifier {table!r} in {path}")
            tables.add(table)

    if statement_count == 0 or parsed_count == 0 or not tables:
        raise ValueError("repository declares no persistent tables")
    return tuple(sorted(tables))


def repository_persistent_tables(repo_root: Path) -> tuple[str, ...]:
    return declared_persistent_tables(repository_sql_paths(repo_root))


def validate_table_names(tables: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in tables:
        table = str(value).strip()
        if not _SAFE_TABLE_NAME.fullmatch(table):
            raise ValueError(f"unsafe table identifier: {table!r}")
        if table in seen:
            raise ValueError(f"duplicate table identifier: {table}")
        seen.add(table)
        normalized.append(table)
    if not normalized:
        raise ValueError("table inventory is empty")
    return tuple(normalized)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the durable public-table inventory declared by schema+migrations."
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        tables = repository_persistent_tables(args.repo_root.resolve())
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"TABLE INVENTORY FAILED: {exc}", file=sys.stderr)
        return 2
    for table in tables:
        print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
