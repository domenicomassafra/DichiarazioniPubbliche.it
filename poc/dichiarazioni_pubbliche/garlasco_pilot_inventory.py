"""Read-only reconstruction of the existing Garlasco 30-claim / 18-Content seed.

This is an inventory and **incomplete draft**, NOT a discovered, approved,
rights-cleared 100-item DP-214 manifest. No fetch, processing, approval or
database mutation is performed. An optional private 0600 output helps an
operator add independently verified discovery provenance and source families.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from dichiarazioni_pubbliche.garlasco_tracer import (
    GARLASCO_COLLECTION_ID,
    GARLASCO_EXPECTED_BASELINE_CLAIMS,
    GARLASCO_PILOT_SIZE,
    PilotItem,
    TracerManifest,
    evaluate_preflight,
    manifest_sha256,
    _safe_url,
)
from dichiarazioni_pubbliche.studio_local_api import _StudioReadOnlyDb
from dichiarazioni_pubbliche.studio_local_api import _StudioCorpusReader
from dichiarazioni_pubbliche.corpus_search import CorpusSearchRequest

GARLASCO_INVENTORY_VERSION = "garlasco-pilot-inventory-v1"
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9:_./-]{0,179}$")
_RIGHTS_STATES = frozenset({
    "UNKNOWN", "UNRESOLVED", "REVIEW_REQUIRED", "APPROVED", "RESTRICTED",
    "BLOCKED", "DENIED", "PUBLIC_DOMAIN", "LICENSED", "PERMISSION_GRANTED",
})

_INVENTORY_SQL = """
WITH claims AS (
    SELECT id, content_id
    FROM atomic_claim
    WHERE id LIKE 'claim:garlasco:%'
), contents AS (
    SELECT DISTINCT content_id FROM claims
)
SELECT json_build_object(
    'claims', (SELECT count(*) FROM claims),
    'unique_claim_ids', (SELECT count(DISTINCT id) FROM claims),
    'content_ids', (SELECT count(*) FROM contents),
    'linked_claims', (
        SELECT count(*) FROM claims c JOIN content_item content ON content.id=c.content_id
    ),
    'approved_text_attributions', (
        SELECT count(DISTINCT ctp.claim_id)
        FROM claim_text_provenance ctp JOIN claims c ON c.id=ctp.claim_id
        WHERE ctp.status='APPROVED'
    ),
    'captures', (
        SELECT count(*) FROM content_capture capture
        JOIN contents content ON content.content_id=capture.content_id
    ),
    'passages', (
        SELECT count(*) FROM passage passage
        JOIN contents content ON content.content_id=passage.content_id
    ),
    'statement_candidates', (
        SELECT count(*) FROM statement_candidate candidate
        JOIN contents content ON content.content_id=candidate.content_id
    ),
    'claim_candidates', (
        SELECT count(*) FROM claim_candidate candidate
        JOIN contents content ON content.content_id=candidate.content_id
    ),
    'collection_rows', (SELECT count(*) FROM research_collection WHERE id='research:garlasco'),
    'collection_members', (
        SELECT count(*) FROM research_collection_content
        WHERE collection_id='research:garlasco' AND status='INCLUDED'
    ),
    'discovery_hits', (SELECT count(*) FROM research_discovery_hit),
    'collection_coverage_needs', (
        SELECT count(*) FROM coverage_need WHERE collection_id='research:garlasco'
    ),
    'public_findings', (SELECT count(*) FROM finding WHERE publication_status='PUBLISH')
)::text;
""".strip()

_CONTENT_SQL = """
SELECT json_build_object(
    'id', content.id,
    'source_id', content.source_id,
    'canonical_url', content.canonical_url,
    'rights_status', content.rights_status,
    'source_present', (source.id IS NOT NULL),
    'active_source_profile_count', (
        SELECT count(*) FROM source_profile profile
        WHERE profile.source_id=content.source_id AND profile.status='ACTIVE'
    )
)::text
FROM content_item content
LEFT JOIN source source ON source.id=content.source_id
WHERE content.id IN (
    SELECT DISTINCT claim.content_id FROM atomic_claim claim
    WHERE claim.id LIKE 'claim:garlasco:%'
)
ORDER BY content.id;
""".strip()

_CLAIM_SQL = """
SELECT id
FROM atomic_claim
WHERE id LIKE 'claim:garlasco:%'
ORDER BY id;
""".strip()

_RETRIEVAL_SQL = """
SELECT json_build_object(
    'id', id, 'content_id', content_id, 'normalized_claim', normalized_claim
)::text
FROM atomic_claim
WHERE id LIKE 'claim:garlasco:%'
ORDER BY id;
""".strip()


class _InventoryReader(Protocol):
    def run(self, sql: str, **kwargs: object) -> str: ...

class _ClaimSearcher(Protocol):
    def search(self, request: CorpusSearchRequest) -> list[Any]: ...


def _safe_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"GARLASCO_INVENTORY_{label}_INVALID")
    return value


def _bounded_json_lines(raw: str, maximum: int) -> list[dict[str, Any]]:
    if not isinstance(raw, str) or len(raw) > 65_536:
        raise ValueError("GARLASCO_INVENTORY_RESULT_OVERSIZED")
    values = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(values) > maximum or any(not isinstance(row, dict) for row in values):
        raise ValueError("GARLASCO_INVENTORY_RESULTS_INVALID")
    return values


@dataclass(frozen=True)
class GarlascoInventory:
    summary: Mapping[str, int]
    seed_manifest: TracerManifest
    blockers: tuple[str, ...]
    source_bindings: tuple[tuple[str, str], ...] = ()

    def receipt(self) -> dict[str, object]:
        """No raw URLs, source prose, quote bodies or private metadata in stdout."""
        numbers = dict(self.summary)
        return {
            "version": GARLASCO_INVENTORY_VERSION,
            "private_only": True,
            "publication_authority": False,
            "complete_pilot": False,
            "seed_sha256": manifest_sha256(self.seed_manifest),
            "seed_items": len(self.seed_manifest.items),
            "required_items": GARLASCO_PILOT_SIZE,
            "missing_items": max(0, GARLASCO_PILOT_SIZE - len(self.seed_manifest.items)),
            "baseline_claims": len(self.seed_manifest.baseline_claim_ids),
            "required_claims": GARLASCO_EXPECTED_BASELINE_CLAIMS,
            "counts": numbers,
            "blockers": list(self.blockers),
        }

    def draft_payload(self) -> dict[str, object]:
        """Restricted local export only; no untrusted provenance is synthesized."""
        return {
            "version": self.seed_manifest.version,
            "collection_id": self.seed_manifest.collection_id,
            "status": "INCOMPLETE_UNREVIEWED_SEED_NOT_FOR_INGESTION",
            "publication_authority": False,
            "manifest_sha256": manifest_sha256(self.seed_manifest),
            "items": [
                {
                    "item_id": item.item_id,
                    "canonical_url": item.canonical_url,
                    "discovery_ref": "",  # no fabricated DP-209 persisted run/hit.
                    "source_family": "UNCLASSIFIED",  # source roles need assessment.
                    "rights_status": item.rights_status,
                }
                for item in self.seed_manifest.items
            ],
            "baseline_claim_ids": list(self.seed_manifest.baseline_claim_ids),
            "blockers": list(self.blockers),
        }


def build_live_inventory(reader: _InventoryReader) -> GarlascoInventory:
    try:
        totals = _bounded_json_lines(reader.run(_INVENTORY_SQL), 1)
        records = _bounded_json_lines(reader.run(_CONTENT_SQL), GARLASCO_PILOT_SIZE)
        claim_ids = reader.run(_CLAIM_SQL).splitlines()
    except (ValueError, TypeError, json.JSONDecodeError):
        raise ValueError("GARLASCO_INVENTORY_READBACK_INVALID") from None
    except Exception:
        raise RuntimeError("GARLASCO_INVENTORY_DATABASE_UNAVAILABLE") from None
    if len(totals) != 1 or len(claim_ids) > GARLASCO_EXPECTED_BASELINE_CLAIMS + 200:
        raise ValueError("GARLASCO_INVENTORY_TOTALS_INVALID")
    summary = totals[0]
    required = {
        "claims", "unique_claim_ids", "content_ids", "linked_claims",
        "approved_text_attributions", "captures", "passages",
        "statement_candidates", "claim_candidates", "collection_rows",
        "collection_members", "discovery_hits", "collection_coverage_needs",
        "public_findings",
    }
    if set(summary) != required or any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in summary.values()
    ):
        raise ValueError("GARLASCO_INVENTORY_TOTALS_SCHEMA_INVALID")
    claim_ids = [_safe_id(value, "CLAIM_ID") for value in claim_ids]
    items: list[PilotItem] = []
    source_bindings: list[tuple[str, str]] = []
    verified_source = 0
    unprofiled = 0
    unknown_rights = 0
    for record in records:
        content_id = _safe_id(record.get("id"), "CONTENT_ID")
        if not content_id.startswith("content:garlasco:"):
            raise ValueError("GARLASCO_INVENTORY_OUT_OF_SCOPE_CONTENT")
        source_id = _safe_id(record.get("source_id"), "SOURCE_ID")
        url = record.get("canonical_url")
        if not isinstance(url, str) or len(url) > 2048 or not _safe_url(url):
            raise ValueError("GARLASCO_INVENTORY_SOURCE_URL_UNSAFE")
        rights = record.get("rights_status")
        if not isinstance(rights, str) or rights not in _RIGHTS_STATES:
            raise ValueError("GARLASCO_INVENTORY_RIGHTS_UNKNOWN_ENUM")
        if not isinstance(record.get("source_present"), bool):
            raise ValueError("GARLASCO_INVENTORY_SOURCE_STATE_INVALID")
        profiles = record.get("active_source_profile_count")
        if not isinstance(profiles, int) or isinstance(profiles, bool) or profiles < 0:
            raise ValueError("GARLASCO_INVENTORY_PROFILE_COUNT_INVALID")
        verified_source += int(record["source_present"])
        unprofiled += int(profiles == 0)
        unknown_rights += int(rights in {"UNKNOWN", "UNRESOLVED", "REVIEW_REQUIRED"})
        items.append(PilotItem(content_id, url, "", "UNCLASSIFIED", rights))
        source_bindings.append((content_id, source_id))
    if (
        len(set(row.item_id for row in items)) != len(items)
        or len(set(row.canonical_url for row in items)) != len(items)
        or len(set(claim_ids)) != len(claim_ids)
        or summary["claims"] != len(claim_ids)
        or summary["unique_claim_ids"] != len(claim_ids)
        or summary["content_ids"] != len(items)
    ):
        raise ValueError("GARLASCO_INVENTORY_COUNT_OR_ID_DRIFT")
    manifest = TracerManifest(
        collection_id=GARLASCO_COLLECTION_ID,
        items=tuple(items),
        baseline_claim_ids=tuple(sorted(claim_ids)),
    )
    structural = evaluate_preflight(manifest, observed_baseline_claim_ids=claim_ids)
    blockers = list(structural.blockers)
    if summary["linked_claims"] != len(claim_ids):
        blockers.append("BASELINE_CLAIM_CONTENT_LINK_MISSING")
    if len(claim_ids) != GARLASCO_EXPECTED_BASELINE_CLAIMS:
        blockers.append("BASELINE_CLAIM_COUNT_NOT_30")
    if verified_source != len(items):
        blockers.append("SOURCE_REFERENCE_MISSING")
    if unprofiled:
        blockers.append("SOURCE_INTELLIGENCE_PROFILE_MISSING")
    if unknown_rights:
        blockers.append("CONTENT_RIGHTS_UNRESOLVED")
    if summary["collection_rows"] != 1 or summary["collection_members"] != GARLASCO_PILOT_SIZE:
        blockers.append("PERSISTED_COLLECTION_INCOMPLETE")
    if summary["captures"] < 1 or summary["passages"] < 1:
        blockers.append("CAPTURE_PASSAGE_COVERAGE_MISSING")
    if summary["collection_coverage_needs"] == 0:
        blockers.append("COLLECTION_COVERAGE_NEEDS_MISSING")
    if summary["discovery_hits"] == 0:
        blockers.append("DISCOVERY_RUN_PROVENANCE_MISSING")
    return GarlascoInventory(
        summary, manifest, tuple(sorted(set(blockers))), tuple(source_bindings)
    )


def verify_baseline_retrieval(
    reader: _InventoryReader,
    searcher: _ClaimSearcher,
) -> dict[str, object]:
    """Run every real historic claim against indexed private corpus retrieval.

    No raw claim text or query, passage/snippet, ranking score or database
    diagnostic reaches the receipt. This checks *baseline searchability*,
    not content accuracy, source rights or DP-214 full-pilot readiness.
    """
    try:
        rows = _bounded_json_lines(reader.run(_RETRIEVAL_SQL), 200)
    except (ValueError, TypeError, json.JSONDecodeError):
        raise ValueError("GARLASCO_BASELINE_READBACK_INVALID") from None
    except Exception:
        raise RuntimeError("GARLASCO_BASELINE_DATABASE_UNAVAILABLE") from None
    expected_ids: set[str] = set()
    cases: list[tuple[str, str, str]] = []
    for row in rows:
        claim_id = _safe_id(row.get("id"), "CLAIM_ID")
        content_id = _safe_id(row.get("content_id"), "CONTENT_ID")
        raw_claim = row.get("normalized_claim")
        if (
            claim_id in expected_ids
            or not claim_id.startswith("claim:garlasco:")
            or not isinstance(raw_claim, str)
            or not 1 <= len(raw_claim.strip()) <= 4_096
        ):
            raise ValueError("GARLASCO_BASELINE_ROW_INVALID")
        expected_ids.add(claim_id)
        cases.append((claim_id, content_id, raw_claim))
    if len(cases) != GARLASCO_EXPECTED_BASELINE_CLAIMS:
        raise ValueError("GARLASCO_BASELINE_NOT_30")
    found = 0
    for claim_id, content_id, statement in cases:
        try:
            results = searcher.search(
                CorpusSearchRequest(
                    query=statement, kinds=("ATOMIC_CLAIM",), limit=20,
                )
            )
        except Exception:
            raise RuntimeError("GARLASCO_BASELINE_SEARCH_UNAVAILABLE") from None
        if any(
            result.id == claim_id
            and result.kind == "ATOMIC_CLAIM"
            and result.content_id == content_id
            for result in results
        ):
            found += 1
    return {
        "version": "garlasco-baseline-retrieval-v1",
        "private_only": True,
        "publication_authority": False,
        "baseline_claims": len(cases),
        "searchable_and_linkable": found,
        "missing": len(cases) - found,
        "all_30_retrievable": found == GARLASCO_EXPECTED_BASELINE_CLAIMS,
    }


def write_private_draft(path: Path, inventory: GarlascoInventory) -> None:
    """Create only once; prevent public-world-readable or symlinked destinations."""
    if path.is_symlink() or not path.parent.is_dir():
        raise ValueError("GARLASCO_DRAFT_DESTINATION_UNSAFE")
    content = json.dumps(inventory.draft_payload(), sort_keys=True, indent=2) + "\n"
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    try:
        directory_fd = os.open(path.parent, directory_flags)
    except OSError as exc:
        raise ValueError("GARLASCO_DRAFT_DESTINATION_UNSAFE") from exc
    try:
        parent = os.fstat(directory_fd)
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_mode & 0o077
                or parent.st_uid != os.getuid()):
            raise ValueError("GARLASCO_DRAFT_DIRECTORY_PERMISSIONS_INVALID")
        # Detect an already substituted path. File creation is anchored to
        # the verified descriptor even if the path changes after this check.
        current = path.parent.lstat()
        if (not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino) != (parent.st_dev, parent.st_ino)):
            raise ValueError("GARLASCO_DRAFT_DESTINATION_UNSAFE")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path.name, flags, 0o600, dir_fd=directory_fd)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("GARLASCO_DRAFT_NOT_REGULAR_FILE")
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                fd = -1
                stream.write(content)
        finally:
            if fd >= 0:
                os.close(fd)
    finally:
        os.close(directory_fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Garlasco corpus seed inventory")
    parser.add_argument("--write-private-draft", type=Path)
    parser.add_argument("--verify-baseline-search", action="store_true")
    args = parser.parse_args(argv)
    try:
        inventory = build_live_inventory(_StudioReadOnlyDb())
        if args.write_private_draft:
            write_private_draft(args.write_private_draft, inventory)
        baseline = (
            verify_baseline_retrieval(_StudioReadOnlyDb(), _StudioCorpusReader())
            if args.verify_baseline_search else None
        )
    except (ValueError, RuntimeError, OSError):
        print(json.dumps({"status": "BLOCKED", "reason_code": "GARLASCO_INVENTORY_UNAVAILABLE"}))
        return 2
    response = inventory.receipt()
    if baseline is not None:
        response["baseline_retrieval"] = baseline
    print(json.dumps(response, sort_keys=True))
    return 0 if baseline is None or baseline["all_30_retrievable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
