"""Atomic, pseudonymous correction quota in the existing private account DB."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SqliteCorrectionQuota:
    path: Path
    per_actor_per_minute: int = 2
    global_per_minute: int = 4

    def reserve(self, actor: str, now: int) -> bool:
        if not isinstance(actor, str) or not re.fullmatch(r"oidc:[0-9a-f]{64}", actor):
            raise ValueError("CORRECTION_QUOTA_ACTOR_INVALID")
        if type(now) is not int or now <= 0:
            raise ValueError("CORRECTION_QUOTA_TIME_INVALID")
        if not 1 <= self.per_actor_per_minute <= self.global_per_minute <= 100:
            raise ValueError("CORRECTION_QUOTA_CONFIGURATION_INVALID")
        # The account DB already owns this table. Missing/misconfigured state
        # must fail closed and must never create a replacement database.
        if not self.path.is_file() or self.path.is_symlink():
            raise sqlite3.OperationalError("CORRECTION_QUOTA_DATABASE_UNAVAILABLE")
        minute = now // 60
        hashed_actor = hashlib.sha256(actor.encode()).hexdigest()
        buckets = (("correction:global", self.global_per_minute),
                   ("correction:actor:" + hashed_actor, self.per_actor_per_minute))
        with closing(sqlite3.connect(self.path, timeout=3)) as connection:
            with connection:
                connection.execute("PRAGMA busy_timeout=3000")
                connection.execute("BEGIN IMMEDIATE")
                counts = []
                for bucket, maximum in buckets:
                    row = connection.execute("SELECT window, used FROM throttle WHERE bucket=?", (bucket,)).fetchone()
                    used = row[1] if row is not None and row[0] == minute else 0
                    if used >= maximum:
                        connection.rollback()
                        return False
                    counts.append((bucket, used + 1))
                for bucket, used in counts:
                    connection.execute(
                        "INSERT INTO throttle(bucket,window,used) VALUES(?,?,?) "
                        "ON CONFLICT(bucket) DO UPDATE SET window=excluded.window,used=excluded.used",
                        (bucket, minute, used),
                    )
        return True
