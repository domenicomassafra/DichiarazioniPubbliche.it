#!/usr/bin/env python3
"""DP-518: reproducible loopback-only MiniPC HTTP withdrawal rehearsal.

Uses fictional demo bytes in an isolated temporary release, never the live
document root or operational database. A passing rehearsal is neither source
approval nor CDN purge, immutable deployment, or production withdrawal proof.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import tempfile
import threading
import time
from pathlib import Path

from dichiarazioni_pubbliche.linked_data import (
    projection_linked_data_receipt,
    projection_ntriples,
)
from dichiarazioni_pubbliche.public_api import build_server
from dichiarazioni_pubbliche.public_schema import (
    projection_dataset_sha256,
    validate_public_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
CANARY = b"dp518-fictional-withdrawn-quote-do-not-publish"
PATHS = ("/", "/quote.html", "/search-index.v1.json", "/sitemap.xml",
         "/api/v1/index.json", "/api/v1/findings", "/index.nt", "/api/v1/health")


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError("DP518_CANARY_" + code)


def materialize(directory: Path, body: dict) -> Path:
    directory.mkdir()
    projection = directory / "index.json"
    projection.write_text(json.dumps(body, sort_keys=True), encoding="utf-8")
    (directory / "index.nt").write_text(projection_ntriples(body), encoding="utf-8")
    (directory / "linked-data-receipt.json").write_text(
        json.dumps(projection_linked_data_receipt(body), sort_keys=True), encoding="utf-8"
    )
    return projection


def static_release(directory: Path, *, withdrawn: bool) -> None:
    directory.mkdir()
    (directory / "index.html").write_bytes(b"<html><title>Canary only</title></html>")
    if withdrawn:
        (directory / "search-index.v1.json").write_bytes(b'{"records":[]}')
        (directory / "sitemap.xml").write_bytes(b"<urlset/>")
    else:
        (directory / "quote.html").write_bytes(CANARY)
        (directory / "search-index.v1.json").write_bytes(CANARY)
        (directory / "sitemap.xml").write_bytes(CANARY)


def read(server, path: str, *, previous_etag: str = "") -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=4)
    try:
        headers = {"Cache-Control": "no-cache", "Accept-Encoding": "identity"}
        if previous_etag:
            headers["If-None-Match"] = previous_etag
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        body = response.read(512_001)
        require(len(body) <= 512_000, "RESPONSE_OVERSIZED")
        return {
            "status": response.status,
            "sha256": digest(body),
            "etag": response.getheader("ETag", ""),
            "no_store": response.getheader("Cache-Control", "") == "no-store",
            "surrogate_no_store": response.getheader("Surrogate-Control", "") == "no-store",
            "contains_canary": CANARY in body,
            "json": json.loads(body) if path.startswith("/api/v1/") and response.status == 200 else None,
        }
    finally:
        conn.close()


def probe(static: Path, projection: Path, *, previous_etag: str = "") -> dict:
    with build_server(projection, host="127.0.0.1", port=0, static_dir=static) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            responses = {path: read(server, path) for path in PATHS}
            if previous_etag:
                responses["conditional_findings"] = read(
                    server, "/api/v1/findings", previous_etag=previous_etag
                )
            return responses
        finally:
            server.shutdown()
            thread.join(timeout=5)


def run_canary() -> dict:
    demo = json.loads((ROOT / "web/src/data/demo-projection.json").read_text(encoding="utf-8"))
    require(len(demo["dossiers"]) > 0, "DEMO_MISSING")
    safe = dict(demo, dossiers=[], dossier_count=0, topics=[], contents=[], omitted_count=0)
    safe["dataset_sha256"] = projection_dataset_sha256(safe)
    validate_public_bundle(safe)

    with tempfile.TemporaryDirectory(prefix="dp518-minipc-canary-") as temp:
        base = Path(temp)
        old_static, new_static = base / "old-static", base / "safe-static"
        static_release(old_static, withdrawn=False)
        static_release(new_static, withdrawn=True)
        old_projection = materialize(base / "old-private", demo)
        safe_projection = materialize(base / "safe-private", safe)

        before = probe(old_static, old_projection)
        require(before["/quote.html"]["contains_canary"], "BASELINE_QUOTE_ABSENT")
        require(before["/api/v1/findings"]["json"]["data"], "BASELINE_API_EMPTY")
        start = time.monotonic_ns()
        after = probe(new_static, safe_projection,
                      previous_etag=before["/api/v1/findings"]["etag"])
        elapsed_ms = (time.monotonic_ns() - start) / 1_000_000
        require(after["/quote.html"]["status"] == 404, "QUOTE_SURVIVES")
        require(after["/api/v1/findings"]["json"]["data"] == [], "API_SURVIVES")
        require(after["/api/v1/index.json"]["json"]["dossiers"] == [], "INDEX_SURVIVES")
        require(after["/api/v1/health"]["json"]["data"]["dossier_count"] == 0, "HEALTH_STALE")
        require(after["conditional_findings"]["status"] == 200, "OLD_ETAG_REUSED")
        for path, outcome in after.items():
            require(not outcome["contains_canary"], "OLD_BYTES_SURVIVE")
            if outcome["status"] == 200:
                require(outcome["no_store"] and outcome["surrogate_no_store"], "CACHE_UNSAFE")

        # Replaying an old candidate is correctly detected as unsafe; the
        # immutable safe release remains available and is re-read on rollback.
        rejected = probe(old_static, old_projection)
        require(rejected["/quote.html"]["status"] == 200, "ROLLBACK_NEGATIVE_MISSING")
        restored = probe(new_static, safe_projection)
        require(restored["/quote.html"]["status"] == 404, "SAFE_RESTORE_FAILED")

        return {
            "status": "PASS_ISOLATED_HOST_CANARY_UNATTESTED",
            "host": "127.0.0.1:ephemeral", "public_production_mutated": False,
            "before_api_count": len(before["/api/v1/findings"]["json"]["data"]),
            "after_api_count": len(after["/api/v1/findings"]["json"]["data"]),
            "before_release_sha256": digest(old_projection.read_bytes()),
            "safe_release_sha256": digest(safe_projection.read_bytes()),
            "old_quote_http": before["/quote.html"]["status"],
            "withdrawn_quote_http": after["/quote.html"]["status"],
            "unsafe_rollback_detected": True, "safe_rollback_readback": True,
            "observed_isolated_switch_ms": round(elapsed_ms, 1),
            "live_cdn_purge_verified": False, "immutable_production_pointer_verified": False,
            "production_slo_attested": False,
        }


if __name__ == "__main__":
    print(json.dumps(run_canary(), sort_keys=True))
