#!/usr/bin/env python3
"""Deterministic metadata-only DP-214 feasibility preview; never fetches a URL.

The URLs are operator-reviewed public-page *hints*, not durable Discovery,
capture permissions, source authentication, or license decisions. Optional
PostgreSQL aggregate input is produced separately by read-only SQL.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.garlasco_tracer import (  # noqa: E402
    REQUIRED_SOURCE_FAMILIES, _safe_url,
)

VERSION = "garlasco-source-feasibility-wave22-v1"
REGISTRY_VERSION = "garlasco-public-discovery-leads-v1"
MAX_JSON_BYTES = 128_000
_ID = re.compile(r"^lead:[a-z0-9:-]{1,150}$")
_EXPECTED_KEYS = frozenset({
    "id", "url", "publisher", "title", "observed_date", "date_meaning",
    "proposed_family", "page_role", "original_url", "origin_verified",
    "evidence_urls", "rights_status", "provenance_status", "capture_authorized",
})
_PAGE_ROLES = {
    "PLATFORM_DISTRIBUTION": "VIDEO_PODCAST",
    "BROADCASTER_ORIGINAL": "VIDEO_PODCAST",
    "NEWSROOM_REPORT": "SECONDARY_REPORTING",
    "CLAIMED_OFFICIAL_TEXT_REPRINT": "DUPLICATE_DERIVATION",
    "NEWSROOM_WITH_THIRD_PARTY_STATEMENT": "SECONDARY_REPORTING",
    "DIRECT_PUBLISHED_INTERVIEW": "DIRECT_INTERVIEW_ARTICLE",
    "OFFICIAL_PROCEDURAL_DOCUMENT": "OFFICIAL_PROCEDURAL",
}
_DERIVED_ROLES = frozenset({
    "NEWSROOM_WITH_THIRD_PARTY_STATEMENT",
})
_PINNED_OFFICIAL_ORIGIN = (
    "https://procura-pavia.giustizia.it/resources/cms/documents/Comunicato_Stampa_28.09.2026.pdf"
)
_PINNED_OFFICIAL_INDEX = "https://procura-pavia.giustizia.it/it/comunicati_stampa.page"
_DATE_MEANINGS = frozenset({
    "EPISODE_RELEASE", "BROADCAST_DATE_NOT_UPLOAD_TIMESTAMP",
    "EPISODE_DATE", "ARTICLE_PUBLICATION", "ARTICLE_DATELINE",
    "ARTICLE_PAGE_DATE", "OFFICIAL_DOCUMENT_DATE",
})
_SNAPSHOT_FIELDS = frozenset({
    "collection_id", "collection_status", "included_members",
    "rights_unknown_members", "discovery_hit_rows",
    "capture_authorized_members", "captures", "passages",
    "statement_candidates", "claim_candidates", "historical_claims",
})


class PreviewError(ValueError):
    pass


def _unique_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise PreviewError("SOURCE_PREVIEW_DUPLICATE_JSON_KEY")
        value[key] = item
    return value


def _read_json(path: Path) -> dict:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise PreviewError("SOURCE_PREVIEW_FILE_TOO_LARGE")
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreviewError("SOURCE_PREVIEW_FILE_INVALID") from exc
    if not isinstance(result, dict):
        raise PreviewError("SOURCE_PREVIEW_FILE_SCHEMA_INVALID")
    return result


def load_source_plan(registry_path: Path, plan_path: Path) -> dict:
    registry = _read_json(registry_path)
    plan = _read_json(plan_path)
    build_preview(registry, plan)
    return plan


def _url(value: object) -> str:
    if not isinstance(value, str) or not _safe_url(value):
        raise PreviewError("SOURCE_PREVIEW_URL_INVALID")
    return value


def _validate_snapshot(snapshot: object) -> dict:
    if not isinstance(snapshot, dict) or set(snapshot) != _SNAPSHOT_FIELDS:
        raise PreviewError("SOURCE_PREVIEW_SNAPSHOT_INVALID")
    if (snapshot["collection_id"] != "research:garlasco"
            or snapshot["collection_status"] not in {"PAUSED", "ACTIVE"}):
        raise PreviewError("SOURCE_PREVIEW_SNAPSHOT_INVALID")
    for key in _SNAPSHOT_FIELDS - {"collection_id", "collection_status"}:
        if type(snapshot[key]) is not int or not 0 <= snapshot[key] <= 100_000:
            raise PreviewError("SOURCE_PREVIEW_SNAPSHOT_INVALID")
    included = snapshot["included_members"]
    if (snapshot["rights_unknown_members"] > included
            or snapshot["capture_authorized_members"] > included):
        raise PreviewError("SOURCE_PREVIEW_SNAPSHOT_INVALID")
    return dict(snapshot)


def build_preview(registry: dict, plan: dict, *, historical_snapshot: dict | None = None) -> dict:
    if (not isinstance(registry, dict)
            or registry.get("version") != REGISTRY_VERSION
            or registry.get("state") != "UNREVIEWED_CANDIDATES_ONLY"):
        raise PreviewError("SOURCE_PREVIEW_REGISTRY_INVALID")
    if (not isinstance(plan, dict) or set(plan) != {
        "version", "observed_on", "purpose", "verified_existing_leads",
        "additional_verified_leads",
    } or plan["version"] != VERSION):
        raise PreviewError("SOURCE_PREVIEW_PLAN_INVALID")
    try:
        as_of = date.fromisoformat(plan["observed_on"])
    except (ValueError, TypeError) as exc:
        raise PreviewError("SOURCE_PREVIEW_DATE_INVALID") from exc
    registry_leads = registry.get("candidates")
    existing = plan["verified_existing_leads"]
    extra = plan["additional_verified_leads"]
    if (not isinstance(registry_leads, list) or not isinstance(existing, list)
            or not isinstance(extra, list) or not 1 <= len(existing) <= 200
            or len(extra) > 200 or len(existing) + len(extra) > 200):
        raise PreviewError("SOURCE_PREVIEW_BOUNDS_INVALID")
    try:
        registry_by_id = {item["id"]: item for item in registry_leads}
        original_ids = {item["id"] for item in registry_leads}
    except (TypeError, KeyError) as exc:
        raise PreviewError("SOURCE_PREVIEW_REGISTRY_INVALID") from exc
    if len(registry_by_id) != len(registry_leads):
        raise PreviewError("SOURCE_PREVIEW_REGISTRY_DUPLICATE_ID")
    seen_urls: set[str] = set()
    seen_ids: set[str] = set()
    families: Counter[str] = Counter()
    followups = 0
    for row in existing + extra:
        if not isinstance(row, dict) or set(row) != _EXPECTED_KEYS:
            raise PreviewError("SOURCE_PREVIEW_LEAD_SCHEMA_INVALID")
        lead_id = row["id"]
        if not isinstance(lead_id, str) or not _ID.fullmatch(lead_id) or lead_id in seen_ids:
            raise PreviewError("SOURCE_PREVIEW_DUPLICATE_OR_INVALID_ID")
        seen_ids.add(lead_id)
        url = _url(row["url"])
        if url in seen_urls:
            raise PreviewError("SOURCE_PREVIEW_DUPLICATE_URL")
        seen_urls.add(url)
        if (row["rights_status"] != "UNKNOWN"
                or row["provenance_status"] != "UNVERIFIED_IN_DATABASE"
                or row["capture_authorized"] is not False):
            raise PreviewError("SOURCE_PREVIEW_UNREVIEWED_ONLY")
        family = row["proposed_family"]
        if (not isinstance(family, str) or family not in REQUIRED_SOURCE_FAMILIES
                or row["page_role"] not in _PAGE_ROLES
                or _PAGE_ROLES[row["page_role"]] != family):
            raise PreviewError("SOURCE_PREVIEW_FAMILY_INVALID")
        families[family] += 1
        if (row["date_meaning"] not in _DATE_MEANINGS
                or not isinstance(row["publisher"], str)
                or not 1 <= len(row["publisher"].strip()) <= 250
                or not isinstance(row["title"], str)
                or not 1 <= len(row["title"].strip()) <= 300):
            raise PreviewError("SOURCE_PREVIEW_METADATA_INVALID")
        try:
            observed = date.fromisoformat(row["observed_date"])
        except (ValueError, TypeError) as exc:
            raise PreviewError("SOURCE_PREVIEW_DATE_INVALID") from exc
        if observed > as_of or observed.isoformat() != row["observed_date"]:
            raise PreviewError("SOURCE_PREVIEW_DATE_INVALID")
        evidence = row["evidence_urls"]
        if (not isinstance(evidence, list) or not 1 <= len(evidence) <= 6
                or not all(isinstance(u, str) for u in evidence)):
            raise PreviewError("SOURCE_PREVIEW_EVIDENCE_MISSING")
        proof_urls = [_url(item) for item in evidence]
        if url not in proof_urls or len(set(proof_urls)) != len(proof_urls):
            raise PreviewError("SOURCE_PREVIEW_EVIDENCE_MISSING")
        original_url = row["original_url"]
        origin_verified = row["origin_verified"]
        if type(origin_verified) is not bool:
            raise PreviewError("SOURCE_PREVIEW_ORIGIN_INVALID")
        if row["page_role"] in _DERIVED_ROLES:
            if origin_verified is not False or original_url is not None:
                raise PreviewError("SOURCE_PREVIEW_ORIGIN_NOT_PROVEN")
            followups += 1
        elif (origin_verified is not True or _url(original_url) not in proof_urls
              or (row["page_role"] == "PLATFORM_DISTRIBUTION" and original_url == url)):
            raise PreviewError("SOURCE_PREVIEW_ORIGIN_INVALID")
        if (row["page_role"] == "OFFICIAL_PROCEDURAL_DOCUMENT"
                and (url != _PINNED_OFFICIAL_ORIGIN
                     or original_url != url
                     or _PINNED_OFFICIAL_INDEX not in proof_urls)):
            raise PreviewError("SOURCE_PREVIEW_OFFICIAL_ORIGIN_INVALID")
        if (row["page_role"] == "CLAIMED_OFFICIAL_TEXT_REPRINT"
                and original_url != _PINNED_OFFICIAL_ORIGIN):
            raise PreviewError("SOURCE_PREVIEW_ORIGIN_NOT_PROVEN")
        if lead_id in original_ids:
            registry_item = registry_by_id[lead_id]
            if (url != registry_item.get("url")
                    or family != registry_item.get("proposed_family")
                    or registry_item.get("rights_status") != "UNKNOWN"
                    or registry_item.get("provenance_status") != "UNVERIFIED_IN_DATABASE"
                    or registry_item.get("candidate_only") is not True
                    or registry_item.get("capture_authorized") is not False):
                raise PreviewError("SOURCE_PREVIEW_REGISTRY_BINDING_MISMATCH")
        elif row in existing:
            raise PreviewError("SOURCE_PREVIEW_REGISTRY_BINDING_MISMATCH")
    if seen_ids.intersection(original_ids) != original_ids or len(existing) != len(original_ids):
        raise PreviewError("SOURCE_PREVIEW_REGISTRY_BINDING_MISMATCH")
    snapshot = None if historical_snapshot is None else _validate_snapshot(historical_snapshot)
    included = None if snapshot is None else snapshot["included_members"]
    optimistic = None if included is None else min(100, included + len(seen_urls))
    return {
        "version": VERSION,
        "observed_on": as_of.isoformat(),
        "mode": "PUBLIC_METADATA_ONLY_UNREVIEWED",
        "existing_verified_leads": len(existing),
        "additional_verified_leads": len(extra),
        "distinct_candidate_urls": len(seen_urls),
        "source_family_counts": {family: families.get(family, 0) for family in sorted(REQUIRED_SOURCE_FAMILIES)},
        "missing_required_source_families": sorted(set(REQUIRED_SOURCE_FAMILIES) - set(families)),
        "source_origin_followups": followups,
        "historical_database_snapshot": snapshot,
        "remaining_actual_included": None if included is None else max(0, 100 - included),
        "prospective_max_if_all_candidates_reviewed": optimistic,
        "remaining_after_hypothetical_review": None if optimistic is None else 100 - optimistic,
        "prospective_is_upper_bound_before_cross_database_dedup": True,
        "candidate_plan_persisted_discovery_hits": 0,
        "rights_verified": False,
        "capture_authorized": False,
        "publication_authorized": False,
        "dp214_ac_1_complete": False,
        "dp215_ac_9_complete": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline Garlasco public-source metadata feasibility preview")
    parser.add_argument("--registry", type=Path, default=ROOT / "config/garlasco-public-discovery-leads.v1.json")
    parser.add_argument("--plan", type=Path, default=ROOT / "config/garlasco-source-feasibility-wave22.v1.json")
    parser.add_argument("--snapshot-json", help="Optional read-only aggregate SQL JSON path, or '-' for stdin; not a live connection")
    args = parser.parse_args(argv)
    try:
        registry = _read_json(args.registry)
        plan = _read_json(args.plan)
        snapshot = None
        if args.snapshot_json:
            if args.snapshot_json == "-":
                raw = sys.stdin.read(MAX_JSON_BYTES + 1)
                if len(raw.encode("utf-8")) > MAX_JSON_BYTES:
                    raise PreviewError("SOURCE_PREVIEW_SNAPSHOT_TOO_LARGE")
                snapshot = json.loads(raw, object_pairs_hook=_unique_keys)
            else:
                snapshot = _read_json(Path(args.snapshot_json))
        result = build_preview(registry, plan, historical_snapshot=snapshot)
    except (PreviewError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED_METADATA_PREVIEW", "reason": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
