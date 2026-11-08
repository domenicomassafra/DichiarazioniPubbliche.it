"""Bounded, no-redirect HTTP verification of immutable MiniPC release bytes."""

from __future__ import annotations

import hashlib
import hmac
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


def http_readback(origin: str, path: str, *, expected_hash: str | None = None,
                  expected_status: int = 200) -> bytes:
    address = urlsplit(origin)
    if address.scheme != "http" or address.hostname not in ("127.0.0.1", "localhost"):
        raise ValueError("DP481_ORIGIN_NOT_LOOPBACK")
    if address.path not in ("", "/") or address.query or address.fragment or address.username:
        raise ValueError("DP481_ORIGIN_INVALID")
    request = Request(origin.rstrip("/") + quote(path, safe="/"),
                      headers={"Accept-Encoding": "identity", "Cache-Control": "no-cache"})

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    try:
        with build_opener(NoRedirect).open(request, timeout=10) as result:
            if (expected_status != 200 or result.status != 200 or
                    result.headers.get("Content-Encoding", "identity") != "identity"):
                raise ValueError("DP481_HTTP_MISMATCH")
            sha = hashlib.sha256()
            size = 0
            chunks = []
            while (chunk := result.read(1024 * 1024)):
                sha.update(chunk)
                size += len(chunk)
                if size > 100 * 1024 * 1024:
                    raise ValueError("DP481_HTTP_OVERSIZED")
                if expected_hash is None:
                    chunks.append(chunk)
            if expected_hash is not None:
                if not hmac.compare_digest(sha.hexdigest(), expected_hash):
                    raise ValueError("DP481_HTTP_MISMATCH")
                return b""
            return b"".join(chunks)
    except HTTPError as exc:
        if expected_status == 404 and exc.code == 404:
            exc.close()
            return b""
        exc.close()
        raise ValueError("DP481_HTTP_MISMATCH") from exc
    except (URLError, OSError) as exc:
        raise ValueError("DP481_HTTP_MISMATCH") from exc
