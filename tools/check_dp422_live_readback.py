#!/usr/bin/env python3
"""Read-only DP-422 approved-empty MiniPC same-origin cross-surface acceptance.

This is *not* a populated approval/canary or a DP-422 DONE certificate.
`--ssh-target minipc` executes these very same script bytes over one SSH
connection, without copying anything to the MiniPC or modifying production.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


CANONICAL_ROUTES = ("/", "/esplora/", "/metodo/", "/correzioni/", "/dati/", "/progetto/")
PRIVATE_OR_UNAPPROVED = (
    "/persone/person-demo-maintenance/",
    "/dichiarazioni/finding-demo-maintenance/",
    "/temi/servizi-pubblici/",
    "/contenuti/content-demo-maintenance/",
    "/tracce/relation-demo-public-services-update/",
    "/fact-check/finding-demo-maintenance/",
    "/compare/relation-demo-public-services-update/",
    "/studio/corpus/",
)
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")


class ReadbackError(RuntimeError):
    pass


def require(condition: bool, error: str) -> None:
    if not condition:
        raise ReadbackError(error)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_read(origin: str, path: str) -> tuple[int, bytes]:
    request = Request(origin + path, headers={"Accept-Encoding": "identity", "Cache-Control": "no-cache"})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=6) as response:
            body = response.read(2_000_001)
            require(len(body) <= 2_000_000, f"DP422_OVERSIZED_RESPONSE:{path}")
            return response.status, body
    except HTTPError as exc:
        return exc.code, exc.read(4096)


def check_readback(read, fingerprint: str) -> dict:
    require(bool(_FINGERPRINT.fullmatch(fingerprint)), "DP422_INVALID_EXPECTED_FINGERPRINT")

    def get(path: str, status: int = 200) -> bytes:
        actual, body = read(path)
        require(actual == status, f"DP422_HTTP_STATUS:{path}:{actual}:expected={status}")
        return body

    index = json.loads(get("/search-index.v1.json"))
    require(index.get("schema_version") == "dichiarazioni-pubbliche-search-index-v1", "DP422_SEARCH_SCHEMA_INVALID")
    require(index.get("projection_sha256") == fingerprint, "DP422_SEARCH_PROJECTION_DRIFT")
    require(index.get("records") == [], "DP422_RUNTIME_NOT_APPROVED_EMPTY")

    projection = json.loads(get("/api/v1/index.json"))
    require(projection.get("dataset_sha256") == fingerprint, "DP422_API_PROJECTION_DRIFT")
    require(projection.get("schema_version") == "dichiarazioni-pubbliche-public-v2", "DP422_API_SCHEMA_DRIFT")
    require(projection.get("methodology", {}).get("aggregate_person_score") is False,
            "DP422_PERSON_SCORE_UNSAFE")
    require(all(projection.get(key) == [] for key in ("dossiers", "topics", "contents")),
            "DP422_API_NOT_APPROVED_EMPTY")

    health = json.loads(get("/api/v1/health"))
    require(health.get("data", {}).get("dataset_fingerprint") == fingerprint,
            "DP422_HEALTH_PROJECTION_DRIFT")
    require(health.get("data", {}).get("dossier_count") == 0, "DP422_HEALTH_NOT_EMPTY")
    for resource in ("findings", "people", "topics", "records"):
        response = json.loads(get("/api/v1/" + resource))
        require(response.get("data") == [], f"DP422_API_LEAKED_{resource.upper()}")
        require(response.get("meta", {}).get("dataset_fingerprint") == fingerprint,
                f"DP422_API_FINGERPRINT_DRIFT:{resource}")

    sitemap = get("/sitemap.xml").decode("utf-8")
    listed = re.findall(r"<loc>https://dichiarazionipubbliche\.it(/[^<]*)</loc>", sitemap)
    require(sorted(listed) == sorted(CANONICAL_ROUTES), "DP422_SITEMAP_CANONICAL_SET_DRIFT")
    require(get("/robots.txt").decode("utf-8") ==
            "User-agent: *\nAllow: /\nSitemap: https://dichiarazionipubbliche.it/sitemap.xml\n",
            "DP422_ROBOTS_POLICY_DRIFT")

    assets_checked: set[str] = set()
    for route in CANONICAL_ROUTES:
        html = get(route).decode("utf-8")
        require(re.search(r'<link rel="canonical" href="' + re.escape(route) + r'"', html) is not None,
                f"DP422_CANONICAL_DRIFT:{route}")
        require('<meta name="robots" content="index,follow">' in html,
                f"DP422_ROBOTS_META_DRIFT:{route}")
        require(len(re.findall(r"<h1\b", html)) == 1 and '<main id="main">' in html,
                f"DP422_HTML_SEMANTICS_INVALID:{route}")
        require('href="/esplora/"' in html and 'href="/metodo/"' in html,
                f"DP422_MISSING_READER_NAV:{route}")
        require(not re.search(r"ambiente dimostrativo|finding-demo-|person_score|raw_transcript|provider_receipt", html, re.I),
                f"DP422_DEMO_OR_PRIVATE_LEAK:{route}")
        require('/studio/' not in html, f"DP422_STUDIO_LEAK:{route}")
        for asset in re.findall(r'(?:src|href)="(/_astro/[^"?#]+)"', html):
            if asset not in assets_checked:
                require(len(get(asset)) > 0, f"DP422_EMPTY_ASSET:{asset}")
                assets_checked.add(asset)
    require(assets_checked, "DP422_NO_STATIC_ASSETS")

    for path in PRIVATE_OR_UNAPPROVED:
        get(path, 404)

    return {
        "result": "PASS_APPROVED_EMPTY_ONLY",
        "projection_fingerprint": fingerprint,
        "static_canonical_routes_http_200": len(CANONICAL_ROUTES),
        "rejected_demo_private_legacy_paths_http_404": len(PRIVATE_OR_UNAPPROVED),
        "static_assets_http_200": len(assets_checked),
        "api_resource_lists_empty": 4,
        "production_dynamic_route_approval": False,
        "dp422_done": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:18090")
    parser.add_argument("--expected-fingerprint", required=True)
    parser.add_argument("--ssh-target", help="Read-only SSH runner; sends source on stdin, saves nothing remotely")
    args = parser.parse_args(argv)
    if args.origin != "http://127.0.0.1:18090" and not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{2,5}", args.origin):
        parser.error("origin must be a loopback HTTP service")
    if not _FINGERPRINT.fullmatch(args.expected_fingerprint):
        parser.error("expected fingerprint must be independent 64-character sha256")
    if args.ssh_target:
        # `__file__` is available on the Mac, not the remote Python stdin.
        from pathlib import Path
        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:@[A-Za-z0-9_.-]+)?", args.ssh_target):
            parser.error("invalid SSH destination")
        source = Path(__file__).read_bytes()
        command = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
                   args.ssh_target, "python3", "-", "--origin", args.origin,
                   "--expected-fingerprint", args.expected_fingerprint]
        result = subprocess.run(command, input=source, capture_output=True, timeout=40, check=False)
        sys.stdout.write(result.stdout.decode("utf-8", "replace"))
        sys.stderr.write(result.stderr.decode("utf-8", "replace"))
        return result.returncode
    try:
        report = check_readback(lambda path: http_read(args.origin, path), args.expected_fingerprint)
    except (ReadbackError, ValueError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        print(f"DP422 APPROVED-EMPTY READBACK FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
