#!/usr/bin/env python3
"""DP244: one licensed pinned Senate XML, persisted as a private Capture.

Reuse the real DP326 Discovery Hit/Collection and the native guarded capture
pipeline; cover one official immutable revision, without parsing or publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.capture_authorization import private_capture_rights_guard
from dichiarazioni_pubbliche.capture_pipeline import (
    CaptureBodyStore, CaptureEnrichmentPolicy, CapturePipelineStore,
    ParseResult, capture_content,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject
from dichiarazioni_pubbliche.source_watcher import fetch_bytes
from dp244_refresh_cycle_canary import CURRENT_URL, SOURCE_FAMILY, SOURCE_ID
from dp326_senato_private_discovery import (
    COLLECTION_ID, CONTENT_BLOB_SHA1, POLICY_VERSION as DISCOVERY_POLICY,
    DP330_PRIVATE_CAPTURE_POLICY as POLICY, DP330_PRIVATE_CAPTURE_USES as RIGHTS_USE,
    RIGHTS_RECEIPT, REVIEWER_REF, SOURCE_URL, official_verified_hit,
)

BODY_SHA256 = "1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476"


class CoverageOnlyParser:
    parser_method = "DP244_COVERAGE_BYTES_ONLY"
    parser_version = "dp244-coverage-only-v1"

    def parse(self, fetched):
        # A source-version receipt is not a licence to extract statements.
        return ParseResult(
            status="FAILED", parser_method=self.parser_method,
            parser_version=self.parser_version,
            error_category="NOT_REQUESTED_COVERAGE_ONLY",
        )


def _context(store):
    raw = store.run(
        """SELECT json_build_object(
            'id', ci.id, 'url', ci.canonical_url, 'source_id', ci.source_id,
            'rights_status', ci.rights_status, 'member_status', member.status,
            'collection_status', col.status, 'membership', member.metadata,
            'discovery_hits', (SELECT count(*) FROM research_discovery_hit hit
                WHERE hit.content_id=ci.id AND hit.run_id='discovery-run:senato-akn-dp326'
                AND hit.disposition IN ('NEW_CONTENT', 'EXISTING_CONTENT'))
        )::text
        FROM content_item ci
        JOIN research_collection_content member ON member.content_id=ci.id
        JOIN research_collection col ON col.id=member.collection_id
        WHERE ci.canonical_url=:'url' AND member.collection_id=:'collection';""",
        url=SOURCE_URL, collection=COLLECTION_ID,
    )
    if not raw:
        raise RuntimeError("DP330_DISCOVERED_CONTENT_MISSING")
    result = json.loads(raw)
    if (
        result["url"] != CURRENT_URL or result["source_id"] != SOURCE_ID
        or result["member_status"] != "INCLUDED"
        or result["collection_status"] != "ACTIVE"
        or result["discovery_hits"] != 1
        or result["rights_status"] not in {"UNKNOWN", "CLEARED"}
        or result["membership"].get("run_id") != "discovery-run:senato-akn-dp326"
    ):
        raise RuntimeError("DP330_COLLECTION_OR_LINEAGE_MISMATCH")
    return result


def run(database_url: str, storage_root: Path, *, apply: bool) -> dict[str, object]:
    # Official pinned GitHub commit + Git Trees + README and LICENSE verifiers.
    hit = official_verified_hit()
    if (
        hit.canonical_url != CURRENT_URL or hit.metadata.get("blob_sha1") != CONTENT_BLOB_SHA1
        or hit.metadata.get("license_id") != "CC-BY-4.0"
        or hit.metadata.get("license_notice_sha256") != RIGHTS_RECEIPT.rsplit(":", 1)[-1]
    ):
        raise RuntimeError("DP330_OFFICIAL_SOURCE_NOT_VERIFIED")

    store = CapturePipelineStore(database_url=database_url)
    context = _context(store)
    subject = RightsSubject(
        source_family=SOURCE_FAMILY, locator_kind="URL",
        locator_value=CURRENT_URL, content_id=context["id"],
    )
    rights = PrivateRightsRegistryStore(database_url=database_url)
    current = rights.read_current(subject)
    if current is None or current.rights_status != "CLEARED":
        raise RuntimeError("DP330_PREEXISTING_METADATA_RIGHTS_MISSING")
    if current.rights_receipt_ref != RIGHTS_RECEIPT or (
        current.policy_version not in (DISCOVERY_POLICY, POLICY)
    ):
        raise RuntimeError("DP330_PREEXISTING_RIGHTS_CONFLICT")
    # A later private text-use attestation may add PARSE_TEXT without revoking
    # the original, separately verified capture grant.
    if current.policy_version == POLICY and set(current.permitted_uses) not in (
        set(RIGHTS_USE), set(RIGHTS_USE) | {"PARSE_TEXT"}
    ):
        raise RuntimeError("DP330_PREEXISTING_RIGHTS_CONFLICT")
    if current.policy_version == DISCOVERY_POLICY and current.permitted_uses != ("DISCOVER_METADATA",):
        raise RuntimeError("DP330_METADATA_RIGHTS_SCOPE_CONFLICT")
    if not apply:
        return {
            "status": "READY_FOR_PRIVATE_CAPTURE",
            "content_id": context["id"], "collection_id": COLLECTION_ID,
            "rights_record_id": current.id, "source_commit": hit.metadata["commit"],
            "license": "CC-BY-4.0", "capture_performed": False,
        }

    if current.policy_version == DISCOVERY_POLICY:
        now = datetime.now(timezone.utc)
        current = rights.record_rights(
            subject=subject, policy_version=POLICY, rights_status="CLEARED",
            rights_receipt_ref=RIGHTS_RECEIPT, permitted_uses=RIGHTS_USE,
            attribution_requirements=("ATTRIBUTION_REQUIRED",),
            reviewed_at=now.isoformat(),
            expires_at=(now + timedelta(days=30)).isoformat(),
            reviewer_ref=REVIEWER_REF, supersedes_record_id=current.id,
        )

    # Restrict the two Content/Collection updates to the exact existing Hit.
    authorized = store.run(
        """WITH updated AS (
            UPDATE content_item SET rights_status='CLEARED',
                metadata=metadata || :'proof'::jsonb
            WHERE id=:'id' AND canonical_url=:'url' AND source_id=:'source'
              AND rights_status IN ('UNKNOWN', 'CLEARED')
            RETURNING id
        ), membership AS (
            UPDATE research_collection_content member
            SET metadata=member.metadata || :'grant'::jsonb
            WHERE collection_id=:'collection' AND content_id=:'id'
              AND status='INCLUDED' AND EXISTS (SELECT 1 FROM updated)
            RETURNING content_id
        )
        SELECT count(*) FROM membership;""",
        id=context["id"], url=CURRENT_URL, source=SOURCE_ID,
        collection=COLLECTION_ID,
        proof=json.dumps({
            "dp330_license_id": "CC-BY-4.0",
            "dp330_license_notice_sha256": hit.metadata["license_notice_sha256"],
            "dp330_license_document_sha256": hit.metadata["license_document_sha256"],
            "dp330_blob_sha1": CONTENT_BLOB_SHA1,
        }),
        grant=json.dumps({
            "capture_authorized": True, "rights_clearance": True,
            "dp330_capture_scope": "ONE_PINNED_DOCUMENT",
        }),
    )
    if authorized != "1":
        raise RuntimeError("DP330_CAPTURE_MEMBERSHIP_CAS_FAILED")

    guard = private_capture_rights_guard(
        read_current=rights.read_current, rights_record_id=current.id,
        content_id=context["id"], canonical_url=CURRENT_URL,
        source_family=SOURCE_FAMILY,
        read_content_state=store.read_operator_capture_content_state,
    )
    exact = SourceFamilyUseGuard(
        read_current=rights.read_current, subject=subject,
        rights_record_id=current.id, policy_version=POLICY,
        expected_sha256=BODY_SHA256,
    )
    guard()
    exact.require("FETCH")

    def checked_fetch(url, *, max_response_bytes):
        guard()
        exact.require("FETCH")
        observed = fetch_bytes(url, max_response_bytes=max_response_bytes)
        digest = hashlib.sha256(observed.body).hexdigest()
        if (
            observed.final_url != CURRENT_URL or digest != BODY_SHA256
            or len(observed.body) != 393817
        ):
            raise RuntimeError("DP330_PINNED_BODY_MISMATCH")
        exact.bind_fetched(final_url=observed.final_url)
        exact.require("FETCH", content_sha256=digest, media_type=observed.media_type)
        exact.require("STORE_BODY", content_sha256=digest, media_type=observed.media_type)
        guard()
        return observed

    body_store = CaptureBodyStore(storage_root)
    receipt = capture_content(
        content_id=context["id"], url=CURRENT_URL,
        store=store, body_store=body_store,
        actor_ref="machine:dp330-official-license-check",
        retention_class="DURABLE_PRIVATE", rights_status="CLEARED",
        parser=CoverageOnlyParser(), fetcher=checked_fetch,
        enrichment_policy=CaptureEnrichmentPolicy(metadata_enabled=False, archive_enabled=False),
        rights_guard=guard,
    )
    found = store.find_capture(context["id"], BODY_SHA256)
    if not found or found["id"] != receipt.primary_capture_id or not found.get("body_ref"):
        raise RuntimeError("DP330_PERSISTENT_CAPTURE_READBACK_FAILED")
    body_store.read(found["body_ref"], expected_sha256=BODY_SHA256)
    return {
        "status": "PRIVATE_CAPTURE_PERSISTED",
        "collection_id": COLLECTION_ID, "content_id": context["id"],
        "capture_id": found["id"], "capture_state": receipt.capture_state,
        "body_ref": found["body_ref"], "source_sha256": BODY_SHA256,
        "source_commit": hit.metadata["commit"], "blob_sha1": CONTENT_BLOB_SHA1,
        "rights_record_id": current.id, "permitted_uses": list(current.permitted_uses),
        "license": "CC-BY-4.0", "reviewer_ref": REVIEWER_REF,
        "parser_status": receipt.parse_status,
        "cost_micro_eur": None, "publication_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--storage-root", type=Path, default=Path("~/.local/share/dichiarazioni-pubbliche-captures").expanduser())
    parser.add_argument("--apply-private-capture", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url required")
    print(json.dumps(run(args.database_url, args.storage_root, apply=args.apply_private_capture), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
