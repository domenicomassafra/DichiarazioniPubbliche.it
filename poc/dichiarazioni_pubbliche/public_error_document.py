"""DP-544 public error document for an ordinary missing static page.

The public static server used to answer every miss with `Content-Length: 0`,
so a browser showed its own bare network error with no navigation back to the
archive. This module keeps the miss response in one place:

* an ordinary missing page in a live release renders the bundled `404.html`;
* a withheld release, a hidden or private path, a control file and an API
  route keep the historical empty body, so a probe learns nothing beyond the
  status code;
* a release that predates the error document still answers 404, never 500.

The page bytes are read through the server's pinned static-root descriptor:
no symlink, no hardlink alias and no oversized file can become the page.
"""

from __future__ import annotations

import os
import stat

NOT_FOUND_PAGE = "404.html"
NOT_FOUND_PAGE_MAX_BYTES = 512 * 1024


def read_error_document(handler) -> bytes:
    """Return the release's own error page bytes, or b"" when unavailable."""
    current_fd = handler.server.dup_static_root()
    if current_fd is None:
        return b""
    try:
        try:
            opened_fd = os.open(NOT_FOUND_PAGE, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                               dir_fd=current_fd)
        except OSError:
            return b""
        with os.fdopen(opened_fd, "rb") as opened:
            info = os.fstat(opened.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or not 0 < info.st_size <= NOT_FOUND_PAGE_MAX_BYTES):
                return b""
            return opened.read()
    finally:
        os.close(current_fd)


def send_static_not_found(handler, cache_control: str, *, page: bool = False) -> None:
    """Emit the 404 for a static miss; `page` selects the error document."""
    body = (read_error_document(handler)
            if page and handler.command in ("GET", "HEAD") else b"")
    handler.send_response(404)
    handler.send_header("Cache-Control", cache_control)
    handler.send_header("Surrogate-Control", "no-store")
    if body:
        handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    if body and handler.command == "GET":
        handler.wfile.write(body)
