#!/usr/bin/env python3
"""Fail-closed *artifact* audit for the approved-empty six-page informational preview.

Independent of the stable-v1 M7 release checker. A passing local bundle is never
permission to publish: counsel, privacy, domain, owner and live MiniPC decisions
are separate. Reads files only; never builds, uploads, approves or deploys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Mapping


PUBLIC_ROUTES = ("/", "/esplora/", "/metodo/", "/correzioni/", "/dati/", "/progetto/")
PRIVATE_UTILITY_ROUTES = ("/accedi/", "/account/")
PUBLIC_BASE = "https://dichiarazionipubbliche.it"
PUBLIC_SCHEMA = "dichiarazioni-pubbliche-public-v2"
SEARCH_SCHEMA = "dichiarazioni-pubbliche-search-index-v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
_PREVIEW_POLICY_TICKETS = ("DP-304", "DP-307", "DP-410", "DP-701", "DP-702")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_PRIVATE_OR_DEMO = re.compile(
    r"ambiente dimostrativo|finding[-_:]demo|person[-_:]demo|garlasco|"
    r"provider_receipt|raw_transcript|canonical_transcript|raw_text|"
    r"submitter_contact|private_reply|private_note|internal_prompt|"
    r"api[_-]?key|database_url|person_truth_score|fixture_only",
    re.IGNORECASE,
)
_SIGNOFF_GAPS = (
    "DP-304:approved_privacy_notice_and_retention_review",
    "DP-307:qualified_italy_eu_review_of_preview_scope",
    "DP-701:domain_holder_and_public_contact_acceptance",
    "DP-702:affected_surface_security_privacy_decision",
    "OWNER:explicit_preview_publication_authority",
    "RUNTIME:mini_pc_https_api_readback_and_rollback_receipt",
)


class PreviewPreflightError(ValueError):
    """An artifact violated the informational preview boundary."""


def require(test: bool, code: str) -> None:
    if not test:
        raise PreviewPreflightError(code)


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def load_json(path: Path, code: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PreviewPreflightError(code) from error
    require(type(value) is dict, code)
    return value


def no_private_markers(text: str, surface: str) -> None:
    require(_PRIVATE_OR_DEMO.search(text) is None, f"PRIVATE_OR_DEMO_MARKER:{surface}")


def check_preview_projection(path: Path, expected_fingerprint: str) -> dict:
    """Inspect a *separately supplied* source projection; do not infer approval."""
    path = Path(path)
    require(path.name != "demo-projection.json", "DEMO_SOURCE_PROJECTION")
    require(bool(_SHA.fullmatch(expected_fingerprint)), "EXPECTED_FINGERPRINT_REQUIRED")
    projection = load_json(path, "SOURCE_PROJECTION_UNAVAILABLE_OR_INVALID")
    no_private_markers(canonical(projection), "source_projection")
    require(projection.get("schema_version") == PUBLIC_SCHEMA, "SOURCE_PROJECTION_SCHEMA_DRIFT")
    methodology = projection.get("methodology")
    require(type(methodology) is dict and methodology.get("aggregate_person_score") is False,
            "SOURCE_PROJECTION_PERSON_SCORE_UNSAFE")
    require(all(projection.get(name) == [] for name in ("dossiers", "topics", "contents")),
            "SOURCE_PROJECTION_NOT_APPROVED_EMPTY")
    require(projection.get("dossier_count") == 0, "SOURCE_PROJECTION_COUNT_DRIFT")
    require(projection.get("dataset_sha256") == expected_fingerprint,
            "PROJECTION_FINGERPRINT_DRIFT")
    require(sha256({key: projection[key] for key in ("dossiers", "topics", "contents")})
            == expected_fingerprint, "PROJECTION_FINGERPRINT_CONTENT_TAMPERED")
    require(isinstance(projection.get("generated_at"), str) and projection["generated_at"],
            "PROJECTION_GENERATION_MISSING")
    return projection


def inspect_preview_governance(root: Path) -> dict:
    """Surface original-ticket and legal-register blockers without creating approvals.

    Every Q-306 row is retained because the qualified preview-scope carve-out is
    itself awaiting review. A project owner and qualified reviewer must decide
    which questions are applicable; an engineering script cannot do so.
    """
    sys.path.insert(0, str(REPO_ROOT / "poc"))
    from dichiarazioni_pubbliche.launch_preflight import (  # noqa: PLC0415
        REQUIRED_LEGAL_QUESTIONS,
        parse_legal_statuses,
        parse_plan_statuses,
        read_ticket_detail_statuses,
    )

    root = Path(root)
    try:
        plan = parse_plan_statuses((root / "PLAN.md").read_text(encoding="utf-8"))
        details = read_ticket_detail_statuses(root)
        legal = parse_legal_statuses(
            (root / "docs/policy/legal-closure-register.md").read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as error:
        raise PreviewPreflightError(f"PREVIEW_GOVERNANCE_REGISTER_INVALID:{error}") from error
    tickets = {}
    status_gaps = []
    for ticket_id in _PREVIEW_POLICY_TICKETS:
        plan_status = plan.get(ticket_id, "MISSING")
        detail_status = details.get(ticket_id, "MISSING")
        tickets[ticket_id] = {"plan": plan_status, "original_ticket": detail_status}
        if plan_status != "DONE" or detail_status != "DONE":
            status_gaps.append(f"PREVIEW_POLICY_NOT_CLOSED:{ticket_id}:{plan_status}:{detail_status}")
        if plan_status != detail_status:
            status_gaps.append(f"PREVIEW_POLICY_STATUS_MISMATCH:{ticket_id}")
    unresolved_legal = [
        f"{question_id}:{legal.get(question_id, 'MISSING')}"
        for question_id in REQUIRED_LEGAL_QUESTIONS
        if legal.get(question_id) != "DECIDED"
    ]
    return {
        "original_policy_ticket_statuses": tickets,
        "unresolved_qualified_review_rows": unresolved_legal,
        "mechanical_policy_blockers": status_gaps,
        "qualified_preview_scope_signed_off": False,
    }


def check_preview_bundle(
    dist: Path,
    expected_fingerprint: str,
    *,
    projection_path: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict:
    """Validate a prepared static bundle against a fingerprint pinned outside it.

    Passing with `projection_path=None` checks only the bundle, not its build
    provenance. The caller must independently establish owner/legal authority.
    """
    dist = Path(dist)
    env = os.environ if environment is None else environment
    require("DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION" not in env,
            "DEMO_OVERRIDE_SET")
    require(bool(_SHA.fullmatch(expected_fingerprint)), "EXPECTED_FINGERPRINT_REQUIRED")
    require(dist.is_dir() and not dist.is_symlink(), "DIST_UNAVAILABLE")
    require((dist / "search-index.v1.json").is_file(), "SEARCH_INDEX_UNAVAILABLE")
    if projection_path is not None:
        source = Path(projection_path)
        require(not source.resolve().is_relative_to(dist.resolve()),
                "SOURCE_PROJECTION_INSIDE_PUBLIC_BUNDLE")
        projection = check_preview_projection(source, expected_fingerprint)
    else:
        projection = None

    index = load_json(dist / "search-index.v1.json", "SEARCH_INDEX_UNAVAILABLE_OR_INVALID")
    require(index.get("schema_version") == SEARCH_SCHEMA and
            index.get("projection_schema_version") == PUBLIC_SCHEMA, "SEARCH_SCHEMA_DRIFT")
    require(index.get("projection_sha256") == expected_fingerprint,
            "SEARCH_FINGERPRINT_DRIFT")
    require(index.get("records") == [], "NONEMPTY_SEARCH_INDEX")
    require(isinstance(index.get("generated_at"), str) and index["generated_at"],
            "SEARCH_GENERATION_MISSING")
    claimed_index_sha = index.get("index_sha256")
    require(isinstance(claimed_index_sha, str) and bool(_SHA.fullmatch(claimed_index_sha)),
            "SEARCH_INDEX_HASH_INVALID")
    require(sha256({k: v for k, v in index.items() if k != "index_sha256"}) == claimed_index_sha,
            "SEARCH_INDEX_TAMPERED")
    if projection is not None:
        require(index["generated_at"] == projection["generated_at"],
                "SOURCE_SEARCH_GENERATION_DRIFT")

    files = sorted(dist.rglob("*"))
    for item in files:
        require(not item.is_symlink(), f"PUBLIC_BUNDLE_SYMLINK:{item.relative_to(dist)}")
    html_paths = {p.relative_to(dist).as_posix() for p in files if p.is_file() and p.suffix == ".html"}
    def html_route(route: str) -> str:
        return (route.lstrip("/") + "index.html")
    public_files = {html_route(route) for route in PUBLIC_ROUTES}
    private_files = {html_route(route) for route in PRIVATE_UTILITY_ROUTES}
    require(public_files.issubset(html_paths), "PUBLIC_ROUTE_MISSING")
    unexpected_html = html_paths - public_files - private_files
    require(not unexpected_html, f"UNEXPECTED_HTML_ROUTE:{','.join(sorted(unexpected_html))}")

    required_top_files = {"robots.txt", "sitemap.xml", "search-index.v1.json"}
    for item in files:
        if not item.is_file():
            continue
        rel = item.relative_to(dist).as_posix()
        require(not (rel.startswith("_astro/") and
                     re.search(r"(?:studio|fixture|demo)", item.name, re.IGNORECASE)),
                f"PRIVATE_STUDIO_OR_DEMO_ASSET:{rel}")
        approved_path = (
            rel in html_paths or rel in required_top_files or
            (rel.startswith("_astro/") and item.suffix in {
                ".js", ".css", ".woff", ".woff2", ".ttf", ".svg", ".png", ".jpg", ".webp", ".ico",
            })
        )
        require(approved_path, f"UNEXPECTED_PUBLIC_ARTIFACT:{rel}")
        if rel in html_paths or rel.endswith((".json", ".js", ".xml", ".txt")):
            no_private_markers(item.read_text(encoding="utf-8"), rel)

    for route in [*PUBLIC_ROUTES, *PRIVATE_UTILITY_ROUTES]:
        rel = html_route(route)
        if rel not in html_paths:
            continue
        html = (dist / rel).read_text(encoding="utf-8")
        canonical_match = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html, re.I)
        require(canonical_match is not None and canonical_match.group(1) == route,
                f"CANONICAL_DRIFT:{route}")
        robots_match = re.search(r'<meta\s+name="robots"\s+content="([^"]+)"', html, re.I)
        expected = "index,follow" if route in PUBLIC_ROUTES else "noindex,nofollow"
        require(robots_match is not None and robots_match.group(1) == expected,
                f"{'PUBLIC_ROBOTS_DRIFT' if route in PUBLIC_ROUTES else 'PRIVATE_ROUTE_INDEXABLE'}:{route}")
        require(len(re.findall(r"<h1\b", html, re.I)) == 1 and
                re.search(r'<main\s+id="main"', html, re.I) is not None,
                f"HTML_SEMANTICS_INVALID:{route}")

    robots = (dist / "robots.txt").read_text(encoding="utf-8")
    require(robots == f"User-agent: *\nAllow: /\nSitemap: {PUBLIC_BASE}/sitemap.xml\n",
            "ROBOTS_DRIFT")
    try:
        root = ET.fromstring((dist / "sitemap.xml").read_bytes())
    except (ET.ParseError, OSError) as error:
        raise PreviewPreflightError("SITEMAP_INVALID") from error
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    require(root.tag == namespace + "urlset", "SITEMAP_SCHEMA_DRIFT")
    entries = root.findall(f"{namespace}url")
    urls = [loc.text for entry in entries for loc in entry.findall(f"{namespace}loc")]
    require(len(entries) == len(PUBLIC_ROUTES) and
            sorted(urls) == sorted(PUBLIC_BASE + route for route in PUBLIC_ROUTES),
            "SITEMAP_DRIFT")

    proof = {
        "outcome": "BUNDLE-PASS-NO-LAUNCH-AUTHORITY",
        "projection_fingerprint": expected_fingerprint,
        "source_projection_checked": projection is not None,
        "public_routes": len(PUBLIC_ROUTES),
        "search_records": 0,
        "private_utility_routes_noindex": len(html_paths & private_files),
        "pending_external_signoffs": list(_SIGNOFF_GAPS),
        "launch_authorized": False,
    }
    proof["receipt_sha256"] = sha256(proof)
    return proof


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path(__file__).resolve().parents[1] / "web/dist")
    parser.add_argument("--expected-fingerprint", required=True,
                        help="64-char externally attested fingerprint, never inferred from web/dist")
    parser.add_argument("--projection", type=Path,
                        help="separately sourced public projection file; absence is reported explicitly")
    parser.add_argument("--repository-root", type=Path, default=REPO_ROOT,
                        help="ticket register authority root (read-only)")
    parser.add_argument("--bundle-only", action="store_true",
                        help="CI-only: exit 0 for a valid static bundle; never indicates launch readiness")
    args = parser.parse_args(argv)
    if args.bundle_only and args.projection is None:
        print("INFORMATIONAL_PREVIEW_FAIL:SOURCE_PROJECTION_REQUIRED_FOR_BUNDLE_ONLY", file=sys.stderr)
        return 1
    try:
        result = check_preview_bundle(args.dist, args.expected_fingerprint,
                                      projection_path=args.projection)
        result["governance"] = inspect_preview_governance(args.repository_root)
        # CLI receipt also commits to the live canonical ticket/legal snapshot.
        result["receipt_sha256"] = sha256({key: value for key, value in result.items()
                                          if key != "receipt_sha256"})
    except (PreviewPreflightError, OSError, UnicodeError) as error:
        print(f"INFORMATIONAL_PREVIEW_FAIL:{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not args.bundle_only:
        print("INFORMATIONAL_PREVIEW_HOLD:OWNER_AND_QUALIFIED_SIGNOFF_REQUIRED", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
