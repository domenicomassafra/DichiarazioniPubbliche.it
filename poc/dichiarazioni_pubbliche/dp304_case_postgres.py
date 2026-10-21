"""Disposable PostgreSQL and release-file helpers for the DP-304 case rehearsal.

Local PostgreSQL binaries, an ephemeral cluster, the repository schema plus the
replay-safe additive privacy migrations, and byte digests of a written release.
Nothing here touches a live database, a deployment mirror or a service.
"""

from __future__ import annotations

import hashlib
import shutil
import socket
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parents[2]


def _bin(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for candidate in sorted(Path("/usr/lib/postgresql").glob(f"*/bin/{name}")):
        return str(candidate)
    raise RuntimeError("DP304_CANARY_POSTGRES_UNAVAILABLE_" + name)


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise RuntimeError(
            "DP304_CANARY_COMMAND_FAILED_" + (detail[-1] if detail else "unknown")
        )
    return proc.stdout


@contextmanager
def disposable_postgres(schema: Path | None = None) -> Iterator[str]:
    """Fresh cluster, repository schema and replay-safe privacy migrations."""
    schema = schema or ROOT / "db/schema.v1.sql"
    with tempfile.TemporaryDirectory(prefix="dp304-case-canary-") as temp:
        base = Path(temp)
        data_dir = base / "data"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        _run([_bin("initdb"), "-D", str(data_dir), "--username=postgres",
              "--auth=trust", "--encoding=UTF8", "--no-locale"])
        started = False
        try:
            _run([_bin("pg_ctl"), "-D", str(data_dir), "-l", str(base / "server.log"),
                  "-o", f"-F -p {port} -h 127.0.0.1 -k {base}", "-w", "start"])
            started = True
            admin = f"postgresql://postgres@127.0.0.1:{port}/postgres"
            _run([_bin("psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1", "--dbname", admin,
                  "-c", "CREATE DATABASE dp304_case_canary;"])
            url = f"postgresql://postgres@127.0.0.1:{port}/dp304_case_canary"
            _run([_bin("psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1", "--dbname", url,
                  "-f", str(schema)])
            for _ in range(2):
                _run([_bin("psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1", "--dbname", url,
                      "-f", str(ROOT / "db/migrations/"
                               "20261007-add-privacy-rights-access-ledgers.sql")])
            yield url
        finally:
            if started:
                subprocess.run([_bin("pg_ctl"), "-D", str(data_dir), "-m", "immediate",
                                "-w", "stop"], capture_output=True, text=True, check=False)


def file_hashes(directory: Path) -> dict[str, str]:
    """Byte digests of every file in a written release, for before/after proof."""
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }
