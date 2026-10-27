#!/usr/bin/env python3
"""DP-458: real MiniPC PostgreSQL + authenticated Studio loopback negative acceptance.

Read-only. It cannot grant a binding or turn a HELD candidate into playback.
The script deliberately expects fail-closed on the persisted unaligned source.
"""
from __future__ import annotations

import http.client
import json
import os
import secrets
import threading
from pathlib import Path

import dp458_real_source_packet as packet
from dichiarazioni_pubbliche.capture_pipeline import (
    CaptureBodyStore, CapturePipelineStore,
)
from dichiarazioni_pubbliche.studio_local_api import (
    _StudioCaptureReader, StudioLocalReaders, StudioLoopbackServer,
)
from dichiarazioni_pubbliche.studio_media_playback_http import StudioMediaRightsReader


def main() -> int:
    dsn = os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL")
    if not dsn:
        raise RuntimeError("DP458_DATABASE_ENV_MISSING")
    root = Path("~/.local/share/dichiarazioni-pubbliche/dp458").expanduser()
    state = packet.verify(CapturePipelineStore(database_url=dsn), root)
    if state["binding_count"] != 0 or state["independent_alignment"] != "HOLD":
        raise RuntimeError("DP458_PLAYBACK_STATE_CHANGED_REQUIRE_REVIEW")
    token = secrets.token_hex(32)
    server = StudioLoopbackServer(
        0,
        StudioLocalReaders(
            corpus=None, captures=_StudioCaptureReader(dsn), candidates=None,
            body_store=CaptureBodyStore.open_existing_readonly(root / "capture-bodies"),
            rights_reader=StudioMediaRightsReader(dsn),
        ),
        token,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method: str, path: str, body: dict | None = None, bearer: str = ""):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
        raw = json.dumps(body).encode() if body is not None else None
        headers = {"Authorization": "Bearer " + bearer, "Content-Type": "application/json"} if body else {}
        try:
            conn.request(method, path, body=raw, headers=headers)
            response = conn.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            conn.close()

    try:
        login_code, login_body, login_headers = request("GET", "/")
        if login_code != 200 or login_headers.get("Cache-Control") != "no-store, private":
            raise RuntimeError("DP458_STUDIO_LOGIN_UNVERIFIED")
        # HTML may include internal CSS/JS; never return it to console.
        if packet.URL.encode() in login_body or token.encode() in login_body:
            raise RuntimeError("DP458_STUDIO_HTML_PRIVATE_LEAK")
        playback = {"binding_id": "binding:dp458:I-293056:cue12:v2"}
        noauth, noauth_body, _ = request("POST", "/v1/media/playback", playback)
        denied, held_body, held_headers = request(
            "POST", "/v1/media/playback", playback, bearer=token
        )
        if noauth != 401 or denied not in (422, 503):
            raise RuntimeError("DP458_STUDIO_FAIL_CLOSED_UNVERIFIED")
        if held_headers.get("Cache-Control") != "no-store, private":
            raise RuntimeError("DP458_STUDIO_CACHE_HEADER_MISSING")
        if (
            packet.ORIGINAL_SHA.encode() in held_body
            or packet.URL.encode() in held_body
            or token.encode() in held_body
            or len(held_body) >= 1024
        ):
            raise RuntimeError("DP458_STUDIO_ERROR_LEAK")
        result = {
            "status": "REAL_STUDIO_LOOPBACK_MEDIA_HOLD",
            "source_id": packet.CONTENT,
            "statement_id": packet.CANDIDATE,
            "real_binding_rows": 0,
            "get_login_http": login_code,
            "unauthenticated_media_http": noauth,
            "authenticated_media_http": denied,
            "media_returned": False,
            "origin": "127.0.0.1",
            "cache_control": held_headers.get("Cache-Control"),
            "browser_native_seek": "NOT_AUTHORIZED",
            "publication_authorized": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
