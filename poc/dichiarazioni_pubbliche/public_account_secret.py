"""Read private account secrets from a verified, non-symlinked file descriptor."""
from __future__ import annotations

import errno
import os
import stat
from pathlib import Path


def read_secret_file(path: Path) -> str:
    # Check the opened inode, not a pathname which can be replaced after stat.
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError("ACCOUNT_SECRET_SYMLINK") from None
        raise
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
            raise ValueError("ACCOUNT_SECRET_PERMISSIONS")
        raw = os.read(fd, 513)
    finally:
        os.close(fd)
    if not 8 <= len(raw) <= 512:
        raise ValueError("ACCOUNT_SECRET_INVALID")
    secret = raw.decode("ascii").strip()
    if len(secret) < 8 or any(ch.isspace() for ch in secret):
        raise ValueError("ACCOUNT_SECRET_INVALID")
    return secret
