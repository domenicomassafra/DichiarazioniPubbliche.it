#!/usr/bin/env python3
"""DP-320/#64: loopback HTTP before/after for one fictional, isolated QA record.

The real HTTP reader is exercised; the SQLite epoch is the existing private
reference contract. Neither this fixture nor its timing attests CDN purge,
production read-fencing, source rights, or approval to publish.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import sqlite3
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from dichiarazioni_pubbliche.public_api import build_server
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256, validate_public_bundle
from dichiarazioni_pubbliche.revocation_epoch_fence import (
    IsolatedPublicationEpochStore,
    RevocationFenceHeld,
)
from dp518_minipc_canary import materialize


ROOT = Path(__file__).resolve().parents[1]
PATHS = (
    "/record.html", "/search-index.v1.json", "/sitemap.xml",
    "/linked-card.json", "/feed.xml", "/record.jsonld",
    "/api/v1/index.json", "/api/v1/findings", "/index.nt",
)


def require(value: bool, code: str) -> None:
    if not value:
        raise RuntimeError("DP320_ISSUE64_QA_" + code)


def _search_index_bytes(projection: dict) -> bytes:
    """Generate and validate the actual Astro Explore search asset."""
    script = """
import {buildSearchIndexMaterial,finalizeSearchIndex,validateSearchIndex,canonicalJson} from './src/lib/searchIndex.ts';
let input='';for await(const chunk of process.stdin) input+=chunk;
const projection=JSON.parse(input);
const index=await finalizeSearchIndex(buildSearchIndexMaterial(projection));
await validateSearchIndex(index,projection.dataset_sha256);
process.stdout.write(canonicalJson(index));
"""
    done = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        input=json.dumps(projection, ensure_ascii=False), text=True,
        cwd=ROOT / "web", capture_output=True, timeout=20,
        env={**os.environ, "NODE_NO_WARNINGS": "1"}, check=False,
    )
    require(done.returncode == 0, "SEARCH_BUILDER")
    return done.stdout.encode("utf-8")


def _static_release(root: Path, record_id: str, projection: dict, *, withdrawn: bool) -> None:
    root.mkdir()
    for name in PATHS[:6]:
        filename = root / name.lstrip("/")
        if withdrawn and name == "/record.html":
            continue  # The exact withdrawn route must become a 404.
        if name == "/search-index.v1.json":
            filename.write_bytes(_search_index_bytes(projection))
        elif withdrawn:
            filename.write_text("[]", encoding="utf-8")
        else:
            filename.write_text(record_id, encoding="utf-8")


def _get(server, path: str, etag: str = "") -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        headers = {"Cache-Control": "no-cache", "Accept-Encoding": "identity"}
        if etag:
            headers["If-None-Match"] = etag
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        data = response.read(512_001)
        require(len(data) <= 512_000, "RESPONSE_TOO_LARGE")
        return {
            "status": response.status,
            "sha256": hashlib.sha256(data).hexdigest(),
            "etag": response.getheader("ETag", ""),
            "no_store": response.getheader("Cache-Control") == "no-store",
            "edge_no_store": response.getheader("Surrogate-Control") == "no-store",
            "body": data,
        }
    finally:
        conn.close()


def _http_probe(static: Path, projection: Path, previous_etag: str = "") -> dict:
    with build_server(projection, host="127.0.0.1", port=0, static_dir=static) as server:
        runner = threading.Thread(target=server.serve_forever, daemon=True)
        runner.start()
        try:
            rows = {path: _get(server, path) for path in PATHS}
            if previous_etag:
                rows["conditional"] = _get(server, "/api/v1/findings", previous_etag)
            return rows
        finally:
            server.shutdown()
            runner.join(timeout=5)


def run_canary() -> dict:
    demo = json.loads((ROOT / "web/src/data/demo-projection.json").read_text("utf-8"))
    record_id = demo["dossiers"][0]["finding_id"]
    require(record_id.startswith("finding:demo:"), "NOT_FICTIONAL")
    safe = dict(demo, dossiers=[], dossier_count=0, topics=[], contents=[], omitted_count=0)
    safe["dataset_sha256"] = projection_dataset_sha256(safe)
    validate_public_bundle(safe)

    with tempfile.TemporaryDirectory(prefix="dp320-issue64-qa-") as temp:
        directory = Path(temp)
        old_static, new_static = directory / "before-static", directory / "after-static"
        _static_release(old_static, record_id, demo, withdrawn=False)
        _static_release(new_static, record_id, safe, withdrawn=True)
        old_projection = materialize(directory / "before-private", demo)
        new_projection = materialize(directory / "after-private", safe)

        with sqlite3.connect(directory / "fence.sqlite3") as conn:
            fence = IsolatedPublicationEpochStore(conn)
            fence.init_fixture_schema()
            material_sha = hashlib.sha256(old_projection.read_bytes()).hexdigest()
            fence.register_fixture_source("source:dp320-issue64-qa", material_sha)
            fence.register_fixture_source("rights:dp320-issue64-qa", "a" * 64)
            ticket = fence.mint(
                release_id="release:dp320-issue64-qa",
                dependency_ids=("source:dp320-issue64-qa", "rights:dp320-issue64-qa"),
            )
            fence.publish_reference(ticket=ticket, artifact_sha256=material_sha)
            require(fence.check_served(ticket, material_sha), "BEFORE_FENCE")

            before = _http_probe(old_static, old_projection)
            search_before = json.loads(before["/search-index.v1.json"]["body"])
            require(any(row["id"] == record_id for row in search_before["records"]),
                    "SEARCH_RECORD_MISSING")
            encoded_id = quote(record_id, safe="").encode("utf-8")
            for path, row in before.items():
                require(row["status"] == 200, "BEFORE_STATUS")
                require(row["no_store"] and row["edge_no_store"], "BEFORE_CACHE")
                identifier = encoded_id if path == "/index.nt" else record_id.encode()
                require(identifier in row["body"], "BEFORE_RECORD_MISSING")

            instant = datetime.now(timezone.utc)
            started = time.monotonic_ns()
            epoch = fence.revoke(
                source_id="rights:dp320-issue64-qa", event_id="event:dp320-issue64-qa",
                reason="RIGHTS_WITHDRAWN", now=instant,
            )
            require(epoch == 1, "EPOCH")
            require(fence.revoke(
                source_id="rights:dp320-issue64-qa", event_id="event:dp320-issue64-qa",
                reason="RIGHTS_WITHDRAWN", now=instant,
            ) == epoch, "REPLAY")
            try:
                fence.check_served(ticket, material_sha)
            except RevocationFenceHeld:
                pass
            else:
                require(False, "STALE_FENCE_ACCEPTED")
            require(len(fence.pending_invalidations()) == 1, "OUTBOX")

            after = _http_probe(new_static, new_projection,
                                previous_etag=before["/api/v1/findings"]["etag"])
            elapsed_ms = (time.monotonic_ns() - started) / 1_000_000
            for path, row in after.items():
                require(row["status"] == (404 if path == "/record.html" else 200),
                        "AFTER_STATUS")
                require(record_id.encode() not in row["body"] and
                        encoded_id not in row["body"], "STALE_RECORD")
                require(row["no_store"] and row["edge_no_store"], "AFTER_CACHE")
            require(after["conditional"]["status"] == 200, "STALE_304")
            require(json.loads(after["/api/v1/findings"]["body"])["data"] == [],
                    "AFTER_FINDINGS")
            require(json.loads(after["/api/v1/index.json"]["body"])["dossiers"] == [],
                    "AFTER_INDEX")
            require(not any(row["id"] == record_id for row in
                            json.loads(after["/search-index.v1.json"]["body"])["records"]),
                    "AFTER_SEARCH")
            return {
                "status": "PASS_ISOLATED_QA_ONLY",
                "record_id": record_id,
                "qa_scope": "dp320-issue64-qa (loopback, fictional, disposable)",
                "source_authorized_publicly": False,
                "before": {p: {k: v for k, v in row.items() if k != "body"}
                           for p, row in before.items()},
                "after": {p: {k: v for k, v in row.items() if k != "body"}
                          for p, row in after.items()},
                "epoch_after_revoke": epoch,
                "pending_invalidation_count": len(fence.pending_invalidations()),
                "observed_disposable_switch_ms": round(elapsed_ms, 2),
                "production_read_fence": False,
                "cdn_purge_verified": False,
                "production_slo_verified": False,
            }


if __name__ == "__main__":
    print(json.dumps(run_canary(), sort_keys=True))
