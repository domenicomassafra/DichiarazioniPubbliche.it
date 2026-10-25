"""Keep an HTTP static reader on one safe root and detect release rotation."""

from __future__ import annotations

import os
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any


def static_path_matches_fd(entry_path: str | None, fd: int | None) -> bool:
    """Withdraw old build bytes if a release path or ancestor was replaced."""
    if entry_path is None or fd is None:
        return False
    try:
        live = os.stat(entry_path)
        opened = os.fstat(fd)
    except OSError:
        return False
    return (live.st_dev, live.st_ino) == (opened.st_dev, opened.st_ino)


class PinnedStaticHTTPServer(ThreadingHTTPServer):
    """Own a document-root dirfd; protect against shutdown/descriptor reuse."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # TCPServer may call server_close() during failed construction.
        self._static_root_lock = threading.Lock()
        self.static_root_fd: int | None = None
        self.static_entry_path: str | None = None
        super().__init__(*args, **kwargs)

    def dup_static_root(self) -> int | None:
        with self._static_root_lock:
            if not static_path_matches_fd(self.static_entry_path, self.static_root_fd):
                return None
            return os.dup(self.static_root_fd)

    def server_close(self) -> None:
        with self._static_root_lock:
            try:
                super().server_close()
            finally:
                if self.static_root_fd is not None:
                    os.close(self.static_root_fd)
                    self.static_root_fd = None


def open_static_root(directory: Path) -> int:
    """Open every absolute path component without following symlinks."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    opened = os.open("/", flags)
    try:
        for component in directory.parts[1:]:
            next_fd = os.open(component, flags, dir_fd=opened)
            os.close(opened)
            opened = next_fd
        return opened
    except BaseException:
        os.close(opened)
        raise
