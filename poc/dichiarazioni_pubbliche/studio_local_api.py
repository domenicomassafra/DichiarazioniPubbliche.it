"""Explicitly started, operator-local, authenticated read-only Studio API.

There is no public route, remote bind option, cookie/session scheme, CORS
permission, HTTP mutation, static-asset delivery or automatic service startup.
An operator with existing local DB permission must deliberately start it and
provide a protected token file.  The API has no review/promotion authority.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import secrets
import stat
import subprocess
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Protocol

from dichiarazioni_pubbliche.candidate_matching import CandidateMatchingStore
from dichiarazioni_pubbliche.capture_pipeline import CapturePipelineStore
from dichiarazioni_pubbliche.corpus_search import CorpusSearchStore
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime, _clean
from dichiarazioni_pubbliche.studio_candidate_review import inspect_candidate_match_run
from dichiarazioni_pubbliche.studio_capture_inspector import inspect_capture_versions
from dichiarazioni_pubbliche.studio_operator_search import search_private_corpus
from dichiarazioni_pubbliche.studio_operator_queues import StudioOperatorQueues
from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page

STUDIO_LOCAL_API_VERSION = "studio-local-readonly-api-v1"
STUDIO_LOCAL_MAX_BODY_BYTES = 4096
_TOKEN_HEX = re.compile(r"^[0-9a-f]{64,128}$")
_ALLOWED_PATHS = frozenset({
    "/v1/corpus/search", "/v1/capture/compare", "/v1/candidate/matches",
    "/v1/collections/list", "/v1/discovery/list",
})

class _StudioReadOnlyDb(PsqlRuntime):
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


class _StudioCorpusReader(_StudioReadOnlyDb, CorpusSearchStore):
    pass


class _StudioCaptureReader(_StudioReadOnlyDb, CapturePipelineStore):
    pass


class _StudioCandidateReader(_StudioReadOnlyDb, CandidateMatchingStore):
    pass


class _StudioQueueReader(_StudioReadOnlyDb, StudioOperatorQueues):
    pass


class _CorpusReader(Protocol):
    def search(self, request: Any) -> list[Any]: ...


class _CaptureReader(Protocol):
    def find_capture(self, content_id: str, content_sha256: str) -> dict[str, Any] | None: ...


class _CandidateReader(Protocol):
    def get_run(self, run_id: str) -> dict[str, Any] | None: ...
    def load_results(self, run_id: str) -> tuple[dict[str, Any], ...]: ...

class _QueueReader(Protocol):
    def list_collections(self, *, limit: int, after_id: str | None) -> dict[str, object]: ...
    def list_discovery(self, *, limit: int, after_id: str | None) -> dict[str, object]: ...


@dataclass(frozen=True)
class StudioLocalReaders:
    corpus: _CorpusReader
    captures: _CaptureReader
    candidates: _CandidateReader
    queues: _QueueReader | None = None


def _fields(body: dict[str, Any], *, required: set[str], optional: set[str] | None = None) -> None:
    allowed = required | (optional or set())
    if body.keys() & required != required or body.keys() - allowed:
        raise ValueError("STUDIO_LOCAL_REQUEST_FIELDS_INVALID")


def _dispatch(readers: StudioLocalReaders, path: str, body: dict[str, Any]) -> dict[str, object]:
    if path == "/v1/corpus/search":
        _fields(body, required={"query"}, optional={"kinds", "source_id", "collection_id", "limit"})
        kinds = body.get("kinds", [])
        if not isinstance(kinds, list) or len(kinds) > 10 or any(not isinstance(k, str) for k in kinds):
            raise ValueError("STUDIO_LOCAL_KINDS_INVALID")
        receipt = search_private_corpus(
            readers.corpus,
            query=body["query"],
            kinds=tuple(kinds),
            source_id=body.get("source_id"),
            collection_id=body.get("collection_id"),
            limit=body.get("limit", 20),
        )
        return receipt.to_dict()
    if path == "/v1/capture/compare":
        _fields(body, required={"content_id", "earlier_hash", "later_hash"})
        return inspect_capture_versions(readers.captures, **body)
    if path == "/v1/candidate/matches":
        _fields(body, required={"run_id", "claim_candidate_id"})
        return inspect_candidate_match_run(readers.candidates, **body)
    if path in {"/v1/collections/list", "/v1/discovery/list"}:
        _fields(body, required=set(), optional={"limit", "after_id"})
        if readers.queues is None:
            raise RuntimeError("STUDIO_LOCAL_QUEUES_UNAVAILABLE")
        if path == "/v1/collections/list":
            return readers.queues.list_collections(**body)
        return readers.queues.list_discovery(**body)
    raise ValueError("STUDIO_LOCAL_PATH_NOT_ALLOWED")


def load_private_token(path: Path) -> str:
    """Refuse absent, symlinked, non-owner, group-readable or invalid token files."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    if path.is_symlink():
        raise ValueError("STUDIO_LOCAL_TOKEN_SYMLINK_FORBIDDEN")
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or not 64 <= info.st_size <= 129
        ):
            raise ValueError("STUDIO_LOCAL_TOKEN_FILE_UNSAFE")
        token = os.read(fd, 130).decode("ascii").strip()
        if not _TOKEN_HEX.fullmatch(token):
            raise ValueError("STUDIO_LOCAL_TOKEN_INVALID")
        return token
    finally:
        os.close(fd)


class StudioLoopbackServer(HTTPServer):
    allow_reuse_address = False

    def __init__(self, port: int, readers: StudioLocalReaders, token: str):
        if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
            raise ValueError("STUDIO_LOCAL_PORT_INVALID")
        if not isinstance(token, str) or not _TOKEN_HEX.fullmatch(token):
            raise ValueError("STUDIO_LOCAL_TOKEN_INVALID")
        self.readers = readers
        self.token = token
        super().__init__(("127.0.0.1", port), StudioLocalHandler)


class StudioLocalHandler(BaseHTTPRequestHandler):
    server: StudioLoopbackServer
    protocol_version = "HTTP/1.0"

    def setup(self) -> None:
        # A local misbehaving client must not stall the sole read-only listener.
        self.request.settimeout(4.0)
        super().setup()

    def log_message(self, fmt: str, *args: object) -> None:
        # Never log tokens, query strings, request bodies, client-controlled paths.
        return

    def _reply(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(encoded)
            except OSError:
                pass

    def _login_page(self) -> None:
        nonce = secrets.token_hex(16)
        encoded = render_studio_login_page(nonce)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
            f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
            "connect-src 'self'; form-action 'none'",
        )
        self.end_headers()
        self.wfile.write(encoded)

    def _allowed_client(self) -> bool:
        hosts = self.headers.get_all("Host", [])
        expected = f"127.0.0.1:{self.server.server_port}"
        if hosts != [expected] or self.client_address[0] != "127.0.0.1":
            return False
        origins = self.headers.get_all("Origin", [])
        if origins and origins != [f"http://{expected}"]:
            return False
        if self.headers.get("Cookie") or self.headers.get("Transfer-Encoding"):
            return False
        return True

    def _authorized(self) -> bool:
        values = self.headers.get_all("Authorization", [])
        expected = "Bearer " + self.server.token
        if len(values) != 1 or len(values[0]) > 140:
            return False
        return hmac.compare_digest(values[0], expected)

    def _process(self) -> None:
        if not self._allowed_client():
            self._reply(403, {"error": "STUDIO_LOCAL_ORIGIN_OR_HOST_REFUSED"})
            return
        if self.command == "GET" and self.path == "/":
            self._login_page()
            return
        if not self._authorized():
            self._reply(401, {"error": "STUDIO_LOCAL_AUTH_REQUIRED"})
            return
        if self.command != "POST":
            self._reply(405, {"error": "STUDIO_LOCAL_METHOD_NOT_ALLOWED"})
            return
        if self.path not in _ALLOWED_PATHS:
            self._reply(404, {"error": "STUDIO_LOCAL_PATH_NOT_ALLOWED"})
            return
        if self.headers.get_all("Content-Type", []) != ["application/json"]:
            self._reply(415, {"error": "STUDIO_LOCAL_JSON_REQUIRED"})
            return
        lengths = self.headers.get_all("Content-Length", [])
        if (
            len(lengths) != 1 or len(lengths[0]) > 5
            or not lengths[0].isascii() or not lengths[0].isdigit()
        ):
            self._reply(400, {"error": "STUDIO_LOCAL_CONTENT_LENGTH_INVALID"})
            return
        length = int(lengths[0])
        if not 1 <= length <= STUDIO_LOCAL_MAX_BODY_BYTES:
            self._reply(413, {"error": "STUDIO_LOCAL_BODY_LIMIT"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("STUDIO_LOCAL_OBJECT_REQUIRED")
            response = _dispatch(self.server.readers, self.path, payload)
            self._reply(200, {"contract_version": STUDIO_LOCAL_API_VERSION, "data": response})
        except (ValueError, TypeError, UnicodeError):
            self._reply(422, {"error": "STUDIO_LOCAL_REQUEST_OR_DATA_INVALID"})
        except Exception:
            self._reply(503, {"error": "STUDIO_LOCAL_BACKEND_UNAVAILABLE"})

    do_POST = _process
    do_GET = _process
    do_HEAD = _process
    do_PUT = _process
    do_PATCH = _process
    do_DELETE = _process
    do_OPTIONS = _process


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Studio loopback API; never run behind an edge proxy")
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18777)
    args = parser.parse_args(argv)
    try:
        token = load_private_token(args.token_file)
        readers = StudioLocalReaders(
            corpus=_StudioCorpusReader(), captures=_StudioCaptureReader(),
            candidates=_StudioCandidateReader(), queues=_StudioQueueReader(),
        )
        with StudioLoopbackServer(args.port, readers, token) as server:
            print(f"Studio local API ready on 127.0.0.1:{server.server_port} (read-only)", flush=True)
            server.serve_forever(poll_interval=0.2)
    except (OSError, ValueError, UnicodeError):
        print("STUDIO_LOCAL_STARTUP_REFUSED", flush=True)
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
