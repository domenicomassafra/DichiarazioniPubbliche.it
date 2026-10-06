#!/usr/bin/env python3
"""DP-604 — prove wheel and sdist hashes from two independent clean clones."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from normalize_sdist import normalize_sdist

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}")
    return result.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_once(source: Path, commit: str, epoch: int, destination: Path) -> dict[str, str]:
    clone = destination / "clone"
    dist = destination / "dist"
    run(["git", "clone", "--no-hardlinks", "--quiet", str(source), str(clone)], cwd=source)
    run(["git", "checkout", "--detach", "--quiet", commit], cwd=clone)
    if run(["git", "status", "--porcelain"], cwd=clone):
        raise RuntimeError("fresh clone is dirty before the build")

    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = str(epoch)
    run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(dist)],
        cwd=clone,
        env=env,
    )

    sdists = sorted(dist.glob("*.tar.gz"))
    if not sdists:
        raise RuntimeError("build produced no sdist")
    for archive in sdists:
        normalize_sdist(archive, epoch)

    artifacts = sorted(path for path in dist.iterdir() if path.is_file())
    if not artifacts:
        raise RuntimeError("build produced no package artifacts")
    return {path.name: sha256(path) for path in artifacts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT, help="Git source repository")
    args = parser.parse_args()
    source = args.source.resolve()

    # Looking up ``build.__main__`` raises ModuleNotFoundError when the parent
    # package is absent, which turns a missing optional dev tool into a traceback.
    # Probe the package itself so this release gate fails with the documented,
    # actionable exit code instead.
    if importlib.util.find_spec("build") is None:
        print(
            "FAIL: python-build is unavailable; install the bounded dev tooling "
            "(`python -m pip install 'build>=1.2,<2.0' 'packaging>=24,<26' "
            "'setuptools>=68,<81' 'wheel>=0.44,<0.46'`).",
            file=sys.stderr,
        )
        return 2

    try:
        commit = run(["git", "rev-parse", "HEAD"], cwd=source)
        epoch = int(run(["git", "show", "-s", "--format=%ct", commit], cwd=source))
        version = (source / "VERSION").read_text(encoding="utf-8").strip()
        with tempfile.TemporaryDirectory(prefix="dp604-repro-") as scratch:
            scratch_path = Path(scratch)
            first = build_once(source, commit, epoch, scratch_path / "first")
            second = build_once(source, commit, epoch, scratch_path / "second")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FAIL: reproducible package check could not complete: {exc}", file=sys.stderr)
        return 1

    if first.keys() != second.keys():
        print(
            f"FAIL: artifact sets differ: first={sorted(first)}, second={sorted(second)}",
            file=sys.stderr,
        )
        return 1

    mismatches = [name for name in first if first[name] != second[name]]
    if mismatches:
        for name in mismatches:
            print(f"FAIL: {name}: {first[name]} != {second[name]}", file=sys.stderr)
        return 1

    print(f"OK: reproducible package artifacts — commit={commit}, VERSION={version}")
    for name in sorted(first):
        print(f"  {first[name]}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
