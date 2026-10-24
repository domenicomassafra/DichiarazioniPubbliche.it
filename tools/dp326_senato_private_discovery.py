#!/usr/bin/env python3
"""One pinned official Senato metadata discovery, private and replayable.

Only observes official repository metadata. The XML body is not downloaded,
captured, submitted to a model, or made public. Existing append-only source
rights and ingestion-relevance registries remain authoritative.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ingestion_relevance import (
    append_ingestion_relevance_authority,
    replay_current_ingestion_relevance,
)
from dichiarazioni_pubbliche.licence_excerpt_decision_v1 import (
    SourceTermsEvidence, attest_licence_use,
)
from dichiarazioni_pubbliche.research_discovery import (
    DiscoveryAdapterResult, DiscoveryHitCandidate, ResearchDiscoveryStore,
    _url_content_id, load_discovery_manifest, run_discovery_manifest,
)
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRegistryStore, RightsSubject,
)
from dichiarazioni_pubbliche.studio_discovery_inbox_workflow import DiscoveryInboxWorkflow
from dp244_refresh_cycle_canary import (
    CURRENT_COMMIT, CURRENT_URL as SOURCE_URL, DOCUMENT as DOCUMENT_PATH,
    README_URL, SOURCE_FAMILY, SOURCE_ID,
)
from senato_akoma_official_readonly_smoke import (
    BLOB as CONTENT_BLOB_SHA1,
    REPOSITORY, _fetch, verify_pinned_official_license,
)

NOTICE_SHA256 = "cd01c53874c63df20d18ea151b3e5528af329dbc64ee573be4d480368f5a34dc"
LICENSE_SHA256 = "9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411"
COLLECTION_ID = "research:senato-akn-dp326"
MANIFEST_ID = "discovery-manifest:senato-akn-dp326"
RUN_ID = "discovery-run:senato-akn-dp326"
POLICY_VERSION = "dp326-official-ccby4-metadata-v1"
DP330_PRIVATE_CAPTURE_POLICY = "dp330-senato-ccby4-private-capture-20261024"
DP330_PRIVATE_CAPTURE_USES = ("DISCOVER_METADATA", "FETCH", "RESEARCH_CAPTURE_PRIVATE", "STORE_BODY")
ATTRIBUTION = "Senato della Repubblica"
REVIEWER_REF = "machine:licence-attestation-v1"
RELEVANCE_REVIEWER = "machine:official-record-source-v1"
RIGHTS_RECEIPT = f"licence:CC-BY-4.0:{NOTICE_SHA256}"


def verified_terms_evidence(license_observation: dict[str, object]) -> SourceTermsEvidence:
    expected = {
        "repository_commit_membership": "CONFIRMED_BY_GITHUB_API",
        "source_license_notice": "CC-BY-4.0",
        "license_notice_sha256": NOTICE_SHA256,
        "license_document_sha256": LICENSE_SHA256,
    }
    if not isinstance(license_observation, dict) or any(
        license_observation.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("DP326_OFFICIAL_LICENSE_UNVERIFIED")
    evidence = SourceTermsEvidence(
        terms_url=README_URL,
        terms_document_sha256=NOTICE_SHA256,
        terms_version=f"senato-akn-{CURRENT_COMMIT}",
        licence_id="CC-BY-4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        rightsholder=ATTRIBUTION,
        markers=("CC BY 4.0",),
    )
    if attest_licence_use(evidence).status != "APPROVED":
        raise ValueError("DP326_OFFICIAL_LICENSE_UNVERIFIED")
    return evidence


def verified_metadata_hit(
    license_observation: dict[str, object], document: dict[str, object],
) -> DiscoveryHitCandidate:
    verified_terms_evidence(license_observation)
    if not isinstance(document, dict) or (
        document.get("path") != DOCUMENT_PATH
        or document.get("sha") != CONTENT_BLOB_SHA1
        or document.get("type") != "file"
        or document.get("download_url") != SOURCE_URL
        or type(document.get("size")) is not int
        or not 0 < document["size"] <= 3_000_000
    ):
        raise ValueError("DP326_OFFICIAL_DOCUMENT_UNVERIFIED")
    return DiscoveryHitCandidate(
        canonical_url=SOURCE_URL,
        title="Senato della Repubblica - resoconto Akoma Ntoso Leg19 01457617",
        source_family=SOURCE_FAMILY,
        source_id=SOURCE_ID,
        external_id=f"{CURRENT_COMMIT}:01457617-ra.akn.xml",
        metadata={
            "platform": "official_github",
            "repository": REPOSITORY,
            "commit": CURRENT_COMMIT,
            "blob_sha1": CONTENT_BLOB_SHA1,
            "source_metadata_bytes": document["size"],
            "license_id": "CC-BY-4.0",
            "license_notice_sha256": NOTICE_SHA256,
            "license_document_sha256": LICENSE_SHA256,
            "attribution": ATTRIBUTION,
            "usage": "DISCOVER_METADATA",
        },
    )


def official_verified_hit() -> DiscoveryHitCandidate:
    license_observation = verify_pinned_official_license()
    commit_url = f"https://api.github.com/repos/{REPOSITORY}/git/commits/{CURRENT_COMMIT}"
    commit = json.loads(_fetch(commit_url, max_bytes=64_000))
    if commit.get("sha") != CURRENT_COMMIT:
        raise ValueError("DP326_OFFICIAL_DOCUMENT_UNVERIFIED")
    tree_sha = commit.get("tree", {}).get("sha")
    if not isinstance(tree_sha, str) or len(tree_sha) != 40:
        raise ValueError("DP326_OFFICIAL_DOCUMENT_UNVERIFIED")
    path_parts = DOCUMENT_PATH.split("/")
    document = None
    for index, part in enumerate(path_parts):
        tree_url = f"https://api.github.com/repos/{REPOSITORY}/git/trees/{tree_sha}"
        listing = json.loads(_fetch(tree_url, max_bytes=500_000))
        if listing.get("truncated") or listing.get("sha") != tree_sha:
            raise ValueError("DP326_OFFICIAL_DOCUMENT_UNVERIFIED")
        matches = [item for item in listing.get("tree", ()) if item.get("path") == part]
        if len(matches) != 1:
            raise ValueError("DP326_OFFICIAL_DOCUMENT_UNVERIFIED")
        document = matches[0]
        if index < len(path_parts) - 1:
            if document.get("type") != "tree":
                raise ValueError("DP326_OFFICIAL_DOCUMENT_UNVERIFIED")
            tree_sha = document.get("sha")
        elif document.get("type") != "blob":
            raise ValueError("DP326_OFFICIAL_DOCUMENT_UNVERIFIED")
    assert document is not None
    return verified_metadata_hit(license_observation, {
        "path": DOCUMENT_PATH,
        "sha": document.get("sha"),
        "type": "file",
        "size": document.get("size"),
        "download_url": SOURCE_URL,
    })


class SenatoMetadataAdapter:
    adapter_id = "senato_official_pinned_metadata"
    adapter_version = "senato-official-commit-metadata-v1"
    supported_families = frozenset({SOURCE_FAMILY})

    def __init__(self, hit: DiscoveryHitCandidate):
        if (hit.canonical_url != SOURCE_URL or hit.source_family != SOURCE_FAMILY
            or hit.source_id != SOURCE_ID
            or hit.metadata.get("blob_sha1") != CONTENT_BLOB_SHA1
            or hit.metadata.get("license_notice_sha256") != NOTICE_SHA256
            or hit.metadata.get("license_document_sha256") != LICENSE_SHA256):
            raise ValueError("DP326_ADAPTER_SOURCE_UNVERIFIED")
        self.hit = hit

    def cost_upper_bound_usd(self, request: object) -> Decimal:
        return Decimal("0")

    def discover(self, request: object) -> DiscoveryAdapterResult:
        if tuple(request.query.source_families) != (SOURCE_FAMILY,):
            return DiscoveryAdapterResult(status="BLOCKED", error_category="SOURCE_SCOPE_INVALID")
        return DiscoveryAdapterResult(
            hits=(self.hit,),
            cost_usd=Decimal("0"),
            provider_receipt={
                "repository": REPOSITORY,
                "commit": CURRENT_COMMIT,
                "blob_sha1": CONTENT_BLOB_SHA1,
                "license_notice_sha256": NOTICE_SHA256,
                "license_document_sha256": LICENSE_SHA256,
            },
        )


def senato_discovery_manifest():
    return load_discovery_manifest({
        "schema_version": 1,
        "id": MANIFEST_ID,
        "collection_id": COLLECTION_ID,
        "source_families": [SOURCE_FAMILY],
        "seeds": [{"kind": "term", "value": "senato-akn-leg19-01457617"}],
        "limits": {
            "max_results": 1,
            "max_results_per_host": 1,
            "cost_cap_usd": "0",
        },
        "queries": [{
            "id": "query:senato-akn-dp326",
            "query": "Senato XIX legislatura resoconto Akoma Ntoso",
            "source_families": [SOURCE_FAMILY],
            "adapter_ids": [SenatoMetadataAdapter.adapter_id],
            "max_results": 1,
        }],
        "metadata": {
            "visibility": "PRIVATE",
            "source_commit": CURRENT_COMMIT,
            "usage": "DISCOVER_METADATA",
            "bulk": False,
        },
    })


def _ensure_exact_source_collection(store: ResearchDiscoveryStore) -> None:
    store.run(
        """
        INSERT INTO source(id, canonical_name, source_type, canonical_url, language, country_code, metadata)
        VALUES (:'source_id', :'name', 'official_open_data',
                :'url', 'it', 'IT', :'metadata'::jsonb)
        ON CONFLICT (id) DO NOTHING;
        """,
        source_id=SOURCE_ID, name=ATTRIBUTION,
        url=f"https://github.com/{REPOSITORY}",
        metadata=json.dumps({"scope": "SENATO_AKN_PRIVATE_METADATA", "license": "CC-BY-4.0"}),
    )
    source = store.run(
        "SELECT canonical_url FROM source WHERE id=:'id';", id=SOURCE_ID,
    )
    if source != f"https://github.com/{REPOSITORY}":
        raise RuntimeError("DP326_SOURCE_ID_CONFLICT")
    store.run(
        """
        INSERT INTO research_collection(id, slug, name, scope_text,
                                        status, policy_version, metadata)
        VALUES (:'id', :'slug', :'name', :'scope', 'ACTIVE',
                :'policy_version', :'metadata'::jsonb)
        ON CONFLICT (id) DO NOTHING;
        """,
        id=COLLECTION_ID, slug="senato-akn-dp326",
        name="Senato Akoma Ntoso - canary privato DP-417",
        scope=f"Solo fonte ufficiale {REPOSITORY}, commit {CURRENT_COMMIT}, locator {DOCUMENT_PATH}",
        policy_version=POLICY_VERSION,
        metadata=json.dumps({"private_only": True, "case": "DP-417", "bulk_ingest": False}),
    )
    collection = json.loads(store.run(
        """SELECT row_to_json(c)::text FROM (
             SELECT slug, scope_text, status, policy_version
             FROM research_collection WHERE id=:'id'
           ) c;""", id=COLLECTION_ID,
    ) or "null")
    if collection != {
        "slug": "senato-akn-dp326",
        "scope_text": f"Solo fonte ufficiale {REPOSITORY}, commit {CURRENT_COMMIT}, locator {DOCUMENT_PATH}",
        "status": "ACTIVE",
        "policy_version": POLICY_VERSION,
    }:
        raise RuntimeError("DP326_COLLECTION_SCOPE_CONFLICT")


def _ensure_official_relevance(store: ResearchDiscoveryStore, now: datetime) -> None:
    content_ref = _url_content_id(SOURCE_URL)
    current = replay_current_ingestion_relevance(
        store.run, content_ref=content_ref, canonical_url=SOURCE_URL,
    )
    if current.allowed:
        if (current.authority.relevance_reason != "OFFICIAL_RECORD"
            or current.authority.reviewer_ref != RELEVANCE_REVIEWER
            or current.authority.audit_ref != f"senato-akn:{CONTENT_BLOB_SHA1}"):
            raise RuntimeError("DP326_RELEVANCE_SCOPE_CONFLICT")
        return
    if current.blocker != "INGESTION_RELEVANCE_MISSING":
        raise RuntimeError(f"DP326_RELEVANCE_BLOCKED:{current.blocker}")
    append_ingestion_relevance_authority(
        store.run,
        content_ref=content_ref,
        canonical_url=SOURCE_URL,
        relevance_reason="OFFICIAL_RECORD",
        reviewer_ref=RELEVANCE_REVIEWER,
        audit_ref=f"senato-akn:{CONTENT_BLOB_SHA1}",
        reviewed_at=now.isoformat(),
    )


def _record_exact_metadata_rights(
    store: PrivateRightsRegistryStore, content_id: str, now: datetime,
) -> str:
    subject = RightsSubject(
        source_family=SOURCE_FAMILY, locator_kind="URL",
        locator_value=SOURCE_URL, content_id=content_id,
    )
    current = store.read_current(subject)
    if current:
        # DP244 may upgrade this exact licensed Content from metadata discovery
        # to a bounded private Capture. Keep the original Run/Hit replay stable.
        scope_allowed = (
            (current.policy_version == POLICY_VERSION
             and current.permitted_uses == ("DISCOVER_METADATA",))
            or (current.policy_version == DP330_PRIVATE_CAPTURE_POLICY
                and current.permitted_uses == DP330_PRIVATE_CAPTURE_USES)
        )
        if (current.rights_status != "CLEARED"
            or current.rights_receipt_ref != RIGHTS_RECEIPT
            or not scope_allowed
            or current.reviewer_ref != REVIEWER_REF
            or current.version_state != "CURRENT"):
            raise RuntimeError("DP326_CURRENT_RIGHTS_CONFLICT")
        return current.id
    saved = store.record_rights(
        subject=subject,
        policy_version=POLICY_VERSION,
        rights_status="CLEARED",
        rights_receipt_ref=RIGHTS_RECEIPT,
        permitted_uses=("DISCOVER_METADATA",),
        attribution_requirements=("ATTRIBUTION_REQUIRED",),
        reviewed_at=now.isoformat(),
        expires_at=(now + timedelta(days=30)).isoformat(),
        reviewer_ref=REVIEWER_REF,
    )
    return saved.id


def run_private_metadata_discovery(database_url: str) -> dict[str, object]:
    # Verify upstream licence and exact immutable blob before any DB write.
    hit = official_verified_hit()
    now = datetime.now(timezone.utc)
    store = ResearchDiscoveryStore(database_url=database_url)
    _ensure_exact_source_collection(store)
    _ensure_official_relevance(store, now)
    manifest = senato_discovery_manifest()
    receipt = run_discovery_manifest(
        manifest, store, {SenatoMetadataAdapter.adapter_id: SenatoMetadataAdapter(hit)},
        run_id=RUN_ID,
    )
    if receipt.status != "COMPLETED" or receipt.accepted_hits != 1:
        raise RuntimeError(f"DP326_DISCOVERY_NOT_ACCEPTED:{receipt.status}")
    replay = run_discovery_manifest(
        manifest, store, {SenatoMetadataAdapter.adapter_id: SenatoMetadataAdapter(hit)},
        run_id=RUN_ID,
    )
    if replay != receipt:
        raise RuntimeError("DP326_DISCOVERY_REPLAY_MISMATCH")

    content_id = store.run(
        "SELECT id FROM content_item WHERE canonical_url=:'url';", url=SOURCE_URL,
    )
    if not content_id:
        raise RuntimeError("DP326_DISCOVERED_CONTENT_MISSING")
    rights_id = _record_exact_metadata_rights(
        PrivateRightsRegistryStore(database_url=database_url), content_id, now,
    )
    rows = DiscoveryInboxWorkflow(store).list_rows(collection_id=COLLECTION_ID, limit=2)
    if (len(rows["rows"]) != 1
        or rows["rows"][0]["source_metadata_rights_current"] is not True
        or rows["rows"][0]["run_state"] != "COMPLETED"
        or rows["rows"][0]["current"] is not True
        or rows["action_authorized"] is not False
        or rows["publication_authority"] is not False):
        raise RuntimeError("DP326_INBOX_REAL_READBACK_FAILED")
    return {
        "status": "PRIVATE_METADATA_DISCOVERY_VERIFIED",
        "collection_id": COLLECTION_ID,
        "manifest_id": MANIFEST_ID,
        "manifest_sha256": manifest.manifest_sha256,
        "run_id": RUN_ID,
        "hit_id": rows["rows"][0]["hit_id"],
        "content_id": content_id,
        "rights_record_id": rights_id,
        "source_commit": CURRENT_COMMIT,
        "license": "CC-BY-4.0",
        "license_notice_sha256": NOTICE_SHA256,
        "license_document_sha256": LICENSE_SHA256,
        "license_attribution": ATTRIBUTION,
        "accepted_hits": receipt.accepted_hits,
        "replay_same_receipt": True,
        "source_metadata_rights_current": True,
        "inbox_blockers": rows["rows"][0]["blockers"],
        "capture_authorized": False,
        "publication_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--run-one-private-metadata-discovery", action="store_true")
    args = parser.parse_args()
    if not args.run_one_private_metadata_discovery or not args.database_url:
        parser.error("Required: --run-one-private-metadata-discovery --database-url DATABASE")
    print(json.dumps(run_private_metadata_discovery(args.database_url), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
