#!/usr/bin/env python3
"""Compare tracked Mac source with the MiniPC mirror without remote writes.

The mirror is deliberately not a Git checkout. This program sends only tracked
relative path names to a read-only remote Python process, then compares hashes.
No provider, database, public endpoint or service is invoked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import sys


DEFAULT_MIRROR = "/home/udodo/src/DichiarazioniPubbliche.it"
RUNTIME_PREFIXES = ("poc/", "tools/", "tests/", "config/", "db/", "deploy/", "web/src/")

REMOTE_PROBE = r"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

root = Path(sys.argv[1]).resolve()
out = {}
for name in json.load(sys.stdin):
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError('Unsafe path')
    target = root.joinpath(*rel.parts)
    if target.is_symlink() or not target.resolve().is_relative_to(root):
        out[name] = {'status': 'UNSAFE_PATH'}
    elif not target.is_file():
        out[name] = {'status': 'ABSENT'}
    else:
        sha = hashlib.sha256()
        with target.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                sha.update(chunk)
        out[name] = {'status': 'FILE', 'sha256': sha.hexdigest()}
print(json.dumps(out, sort_keys=True))
"""


def tracked_paths(repo: Path, base: str | None = None) -> list[str]:
    if base:
        args = ["git", "diff", "--name-only", "-z", "--no-renames", base, "HEAD", "--"]
    else:
        args = ["git", "ls-files", "-z", "--"]
    raw = subprocess.check_output(args, cwd=repo)
    result = sorted(set(raw.decode("utf-8").strip("\0").split("\0")))
    return [name for name in result if name and safe_relative_path(name)]


def safe_relative_path(name: str) -> bool:
    value = PurePosixPath(name)
    return bool(value.parts) and not value.is_absolute() and ".." not in value.parts


def sha256_path(path: Path) -> str | None:
    if path.is_symlink():
        raise ValueError(f"Symlink in source selection: {path}")
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compare_paths(repo: Path, paths: list[str], observed: dict) -> list[dict[str, str | None]]:
    if set(observed) != set(paths):
        raise ValueError("Remote path list does not match requested paths")
    rows = []
    for name in paths:
        if not safe_relative_path(name):
            raise ValueError(f"Unsafe tracked path: {name}")
        local = sha256_path(repo / name)
        record = observed[name]
        if not isinstance(record, dict) or record.get("status") not in {"ABSENT", "FILE", "UNSAFE_PATH"}:
            raise ValueError(f"Invalid remote result for {name}")
        remote = record.get("sha256") if record["status"] == "FILE" else None
        if record["status"] == "FILE" and (not isinstance(remote, str) or len(remote) != 64):
            raise ValueError(f"Missing or malformed remote digest for {name}")
        if record["status"] == "UNSAFE_PATH":
            state = "UNSAFE_PATH"
        elif local == remote:
            state = "MATCH"
        elif local is None:
            state = "STALE_REMOTE"
        elif remote is None:
            state = "MISSING"
        else:
            state = "DRIFT"
        rows.append({"status": state, "path": name, "source_sha256": local, "mirror_sha256": remote})
    return rows


def probe_remote(host: str, mirror: str, paths: list[str]) -> dict:
    command = f"python3 -c {shlex.quote(REMOTE_PROBE)} {shlex.quote(mirror)}"
    result = subprocess.run(
        ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, command],
        input=json.dumps(paths).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=40,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Read-only remote hash probe failed (SSH exit {result.returncode})")
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError("Remote probe did not return a path manifest")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="minipc", help="Existing SSH host alias")
    parser.add_argument("--mirror", default=DEFAULT_MIRROR)
    parser.add_argument("--base", help="Compare only paths changed from this Git revision to HEAD")
    parser.add_argument("--all-tracked", action="store_true", help="Include docs, web pages and other Git-tracked files")
    parser.add_argument("--json", action="store_true", help="Show full machine-readable SHA-256 evidence")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    paths = tracked_paths(repo, args.base)
    if not args.all_tracked and not args.base:
        paths = [name for name in paths if name.startswith(RUNTIME_PREFIXES)]
    try:
        rows = compare_paths(repo, paths, probe_remote(args.host, args.mirror, paths))
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"PARITY_PROBE_ERROR: {exc}", file=sys.stderr)
        return 2
    counts = {state: sum(row["status"] == state for row in rows) for state in ("MATCH", "DRIFT", "MISSING", "STALE_REMOTE", "UNSAFE_PATH")}
    if args.json:
        print(json.dumps({"host": args.host, "mirror": args.mirror, "counts": counts, "files": rows}, indent=2))
    else:
        for row in rows:
            if row["status"] != "MATCH":
                print(f"{row['status']:12} {row['path']} Mac={row['source_sha256'] or '-'} MiniPC={row['mirror_sha256'] or '-'}")
        print("SUMMARY", json.dumps(counts, sort_keys=True))
    return 0 if counts["MATCH"] == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
