"""Bounded PostgreSQL command execution; CLI timeout rolls back its transaction."""

import subprocess


def execute_psql(args: list[str], sql: str, timeout_seconds: float | None) -> str:
    try:
        proc = subprocess.run(
            args, input=sql, text=True, capture_output=True,
            check=False, timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("PSQL_QUERY_TIMEOUT") from exc
    if proc.returncode:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        message = next(
            (line.strip() for line in detail if "ERROR:" in line or "FATAL:" in line),
            detail[-1] if detail else f"psql exited {proc.returncode}",
        )
        raise RuntimeError(message[:1200])
    return proc.stdout.strip()
