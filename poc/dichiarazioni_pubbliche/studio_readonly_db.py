"""PostgreSQL read-only session fence used by private Studio readers."""
from __future__ import annotations
import os
import subprocess
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime, _clean


class StudioReadOnlyDb(PsqlRuntime):
    """Guard even a mistakenly invoked write at the PostgreSQL session layer."""

    def run(self, sql: str, **variables: object) -> str:
        args = self._args()
        for key, value in variables.items():
            args.extend(["-v", f"{key}={_clean(value)}"])
        environment = os.environ.copy()
        environment["PGOPTIONS"] = (
            environment.get("PGOPTIONS", "")
            + " -c default_transaction_read_only=on"
            + " -c statement_timeout=3000"
            + " -c lock_timeout=1000"
        ).strip()
        environment["PGCONNECT_TIMEOUT"] = "3"
        try:
            process = subprocess.run(
                args, input=sql, text=True, capture_output=True, check=False,
                env=environment, timeout=8,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("STUDIO_LOCAL_DB_TIMEOUT_OR_UNAVAILABLE") from None
        if process.returncode != 0:
            raise RuntimeError("STUDIO_LOCAL_DB_QUERY_REFUSED")
        if len(process.stdout) > 128_000:
            raise RuntimeError("STUDIO_LOCAL_DB_RESULT_TOO_LARGE")
        return process.stdout.strip()
