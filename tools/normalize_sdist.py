#!/usr/bin/env python3
"""Normalize a Python sdist so its byte hash is reproducible.

Setuptools creates valid sdists whose tar/gzip timestamps depend on the build run.  DP-604
requires the release artifact hash to be reproducible from the same commit, so release
builds rewrite only archive metadata to the commit's SOURCE_DATE_EPOCH while preserving
the payload, paths, link targets, and file modes.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import os
import tarfile
import tempfile
from pathlib import Path


def normalize_sdist(path: Path, source_date_epoch: int) -> None:
    """Rewrite ``path`` atomically with deterministic tar and gzip metadata."""

    path = path.resolve()
    if not path.name.endswith(".tar.gz"):
        raise ValueError(f"expected a .tar.gz sdist, got {path.name}")

    with tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    ) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        with tarfile.open(path, "r:gz") as source, tmp_path.open("wb") as raw_output:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_output,
                mtime=source_date_epoch,
            ) as gzip_output:
                with tarfile.open(
                    fileobj=gzip_output,
                    mode="w",
                    format=tarfile.PAX_FORMAT,
                ) as target:
                    for original in sorted(source.getmembers(), key=lambda item: item.name):
                        member = copy.copy(original)
                        member.mtime = source_date_epoch
                        member.uid = 0
                        member.gid = 0
                        member.uname = ""
                        member.gname = ""
                        member.pax_headers = {}
                        payload = source.extractfile(original) if original.isfile() else None
                        target.addfile(member, payload)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="sdist .tar.gz files to normalize")
    parser.add_argument(
        "--source-date-epoch",
        required=True,
        type=int,
        help="canonical Unix timestamp, normally `git log -1 --format=%ct`",
    )
    args = parser.parse_args()

    for path in args.paths:
        normalize_sdist(path, args.source_date_epoch)
        print(f"normalized: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
