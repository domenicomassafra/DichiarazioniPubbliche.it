"""Check private statement batches before source and publication review."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.research_discovery import canonicalize_discovery_url


REQUIRED_FIELDS = {"persona", "data", "testo", "fonte_url", "contesto"}
OPTIONAL_FIELDS = {"diritti_url"}
MAX_FILE_BYTES = 4 * 1024 * 1024


def _unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate JSON key")
    return result


def _parse_statement(row):
    if not isinstance(row, dict) or row.keys() - REQUIRED_FIELDS - OPTIONAL_FIELDS:
        raise ValueError("record")
    for field in sorted(REQUIRED_FIELDS | row.keys()):
        value = row.get(field)
        if (
            not isinstance(value, str)
            or not value.strip()
            or any(ord(ch) < 32 and ch not in "\n\r\t" for ch in value)
        ):
            raise ValueError(field)
        try:
            value.encode("utf-8")
            if field == "data":
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError(field)
            elif field in {"fonte_url", "diritti_url"}:
                if "\\" in value or any(ch.isspace() for ch in value):
                    raise ValueError(field)
                _, host = canonicalize_discovery_url(value)
                parsed = urlsplit(value)
                if "." not in host:
                    raise ValueError(field)
                locator = parsed.path.strip("/") or parsed.query or parsed.fragment
                if field == "fonte_url" and not locator:
                    raise ValueError(field)
        except (ValueError, UnicodeError):
            raise ValueError(field) from None

    return (
        row["persona"].strip().casefold(),
        row["data"],
        row["testo"],
        canonicalize_discovery_url(row["fonte_url"])[0],
    )


def inspect_batch(directory: Path) -> dict[str, object]:
    seen = set()
    errors = []
    duplicates = 0
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("batch directory unavailable")
    files = sorted(directory.glob("*.json"))
    for path in files:
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("invalid batch file")
            with path.open("rb") as batch:
                raw = batch.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise ValueError("batch file too large")
            rows = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
            if not isinstance(rows, list) or not rows:
                raise ValueError("batch array required")
        except (OSError, ValueError, RecursionError):
            errors.append({"file": path.name, "row": None, "field": "file"})
            continue

        for index, row in enumerate(rows, start=1):
            try:
                key = _parse_statement(row)
            except ValueError as exc:
                errors.append({"file": path.name, "row": index, "field": str(exc)})
                continue
            duplicates += key in seen
            seen.add(key)

    return {
        "files": len(files),
        "pending": len(seen),
        "duplicates": duplicates,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        report = inspect_batch(args.directory)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report))
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
