#!/usr/bin/env python3
"""DP-424: independently verify and privately persist two authentic Senate versions.

The second observation is a replay of an *older pinned commit*, not a live
change at today's URL. Retain the DP-244 Coverage-only Capture unchanged.
Only one source-bound Passage per version is selected; no candidates or public
projection are written. An exact current licence grant is checked at every
persistence stage and each HTTP source is pinned to its real bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_authorization import (
    private_capture_rights_guard, require_operator_capture_content,
)
from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, CapturePipelineStore
from dichiarazioni_pubbliche.ingestion_relevance import deterministic_ingestion_operation_ref
from dichiarazioni_pubbliche.licence_excerpt_decision_v1 import SourceTermsEvidence, attest_licence_use
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject
from dichiarazioni_pubbliche.senato_akoma_corpus_handoff import (
    prepare_senato_corpus_handoff, verify_senato_handoff_roundtrip,
)
from dichiarazioni_pubbliche.source_watcher import fetch_bytes
from dichiarazioni_pubbliche.studio_capture_inspector import inspect_capture_versions
from dichiarazioni_pubbliche.studio_local_api import _StudioCaptureReader

from dp244_refresh_cycle_canary import (
    CURRENT_URL, DOCUMENT, PREVIOUS_COMMIT, PREVIOUS_README_URL, PREVIOUS_URL, SOURCE_FAMILY,
)
from dp326_senato_private_discovery import (
    CONTENT_BLOB_SHA1, DP330_PRIVATE_CAPTURE_POLICY, RIGHTS_RECEIPT,
    official_verified_hit,
)
from dp330_senato_private_capture import BODY_SHA256, _context
from senato_akoma_official_readonly_smoke import REPOSITORY, _fetch

OLD_SHA256 = "6afe4c8a1ad2d32a85124ca379966adf7412bfd0894da432871c25f53cb80f14"
OLD_BLOB_SHA1 = "54ac1686e7d1bf016cbdffed4e00b1b93c84def8"
OLD_README_SHA256 = "da14a99295c65f32dcc01f322e4cd5fe163817cb1caa413fdf89e81b72e3c57c"
OLD_RIGHTS_RECEIPT = "licence:CC-BY-3.0:" + OLD_README_SHA256
OLD_POLICY = "dp424-senato-historic-ccby3-private-20261025"
OLD_USES = ("FETCH", "PARSE_TEXT", "RESEARCH_CAPTURE_PRIVATE", "STORE_BODY")
OLD_BYTES = 394147
CURRENT_BYTES = 393817


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def _verified_historic_license():
    # Distinguish a real official Git commit from a fabricated URL or replayed fixture.
    commit_url = f"https://api.github.com/repos/{REPOSITORY}/git/commits/{PREVIOUS_COMMIT}"
    commit = json.loads(_fetch(commit_url, max_bytes=64_000))
    require(commit.get("sha") == PREVIOUS_COMMIT,
            "DP424_HISTORIC_COMMIT_UNVERIFIED")
    tree_sha = commit.get("tree", {}).get("sha")
    require(isinstance(tree_sha, str) and len(tree_sha) == 40,
            "DP424_HISTORIC_TREE_UNVERIFIED")
    for index, part in enumerate(DOCUMENT.split("/")):
        tree_url = f"https://api.github.com/repos/{REPOSITORY}/git/trees/{tree_sha}"
        listing = json.loads(_fetch(tree_url, max_bytes=500_000))
        require(not listing.get("truncated") and listing.get("sha") == tree_sha,
                "DP424_HISTORIC_TREE_UNVERIFIED")
        matches = [row for row in listing.get("tree", []) if row.get("path") == part]
        require(len(matches) == 1, "DP424_HISTORIC_BLOB_UNVERIFIED")
        node = matches[0]
        if index < len(DOCUMENT.split("/")) - 1:
            require(node.get("type") == "tree", "DP424_HISTORIC_TREE_UNVERIFIED")
            tree_sha = node.get("sha")
        else:
            require(node.get("type") == "blob" and node.get("sha") == OLD_BLOB_SHA1,
                    "DP424_HISTORIC_BLOB_UNVERIFIED")
    notice = _fetch(PREVIOUS_README_URL, max_bytes=64_000)
    require(
        hashlib.sha256(notice).hexdigest() == OLD_README_SHA256
        and b"CC BY 3.0" in notice,
        "DP424_HISTORIC_LICENSE_NOTICE_MISMATCH",
    )
    terms = SourceTermsEvidence(
        terms_url=PREVIOUS_README_URL, terms_document_sha256=OLD_README_SHA256,
        terms_version=f"senato-akn-{PREVIOUS_COMMIT}",
        licence_id="CC-BY-3.0", licence_url="https://creativecommons.org/licenses/by/3.0/",
        rightsholder="Senato della Repubblica", markers=("CC BY 3.0",),
    )
    require(attest_licence_use(terms).status == "APPROVED",
            "DP424_HISTORIC_LICENSE_NOT_CLEARED")


def _verified_historic_observation(guard: SourceFamilyUseGuard):
    # The exact CURRENT source-use grant and relevance permit precede any body fetch.
    guard.require("FETCH")
    fetched = fetch_bytes(PREVIOUS_URL, max_response_bytes=500_000)
    guard.bind_fetched(final_url=fetched.final_url)
    blob = hashlib.sha1(
        b"blob " + str(len(fetched.body)).encode("ascii") + b"\x00" + fetched.body
    ).hexdigest()
    require(
        fetched.final_url == PREVIOUS_URL and fetched.status_code == 200
        and len(fetched.body) == OLD_BYTES
        and hashlib.sha256(fetched.body).hexdigest() == OLD_SHA256
        and blob == OLD_BLOB_SHA1,
        "DP424_HISTORIC_BODY_UNVERIFIED",
    )
    guard.require("FETCH", content_sha256=OLD_SHA256, media_type=fetched.media_type)
    return fetched


def _passage_pair(current, historic):
    # The two XML bytes genuinely differ. Their extracted speech wording happens
    # to be identical, so never claim a textual quote was revised.
    present = {p.metadata["source_speech_id"]: p for p in current.passages}
    shared = [
        (present[p.metadata["source_speech_id"]], p)
        for p in historic.passages if p.metadata["source_speech_id"] in present
    ]
    require(bool(shared), "DP424_SHARED_SPEECH_MISSING")
    first, second = shared[0]
    require(
        first.text_sha256 == second.text_sha256
        and first.private_text == second.private_text
        and first.capture_id != second.capture_id,
        "DP424_HISTORIC_PASSAGE_REPLAY_MISMATCH",
    )
    return first, second


def run(database_url: str, storage_root: Path, *, apply: bool = False) -> dict[str, object]:
    store = CapturePipelineStore(database_url=database_url)
    ctx = _context(store)
    content_id = ctx["id"]
    require(official_verified_hit().metadata["blob_sha1"] == CONTENT_BLOB_SHA1,
            "DP424_CURRENT_OFFICIAL_LICENSE_UNVERIFIED")
    current_subject = RightsSubject(
        source_family=SOURCE_FAMILY, locator_kind="URL",
        locator_value=CURRENT_URL, content_id=content_id,
    )
    historic_subject = RightsSubject(
        source_family=SOURCE_FAMILY, locator_kind="URL",
        locator_value=PREVIOUS_URL, content_id=content_id,
    )
    rights = PrivateRightsRegistryStore(database_url=database_url)
    grant = rights.read_current(current_subject)
    require(
        grant is not None and grant.policy_version == DP330_PRIVATE_CAPTURE_POLICY
        and grant.rights_receipt_ref == RIGHTS_RECEIPT,
        "DP424_CURRENT_SOURCE_GRANT_MISSING",
    )
    current_guard = SourceFamilyUseGuard(
        read_current=rights.read_current, subject=current_subject,
        rights_record_id=grant.id, policy_version=DP330_PRIVATE_CAPTURE_POLICY,
        expected_sha256=BODY_SHA256,
    )
    private_guard = private_capture_rights_guard(
        read_current=rights.read_current, rights_record_id=grant.id,
        content_id=content_id, canonical_url=CURRENT_URL,
        source_family=SOURCE_FAMILY,
        read_content_state=store.read_operator_capture_content_state,
    )
    private_guard()
    current_guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)
    existing = store.find_capture(content_id, BODY_SHA256)
    require(
        existing is not None and existing.get("content_sha256") == BODY_SHA256
        and existing.get("media_type") == "text/plain"
        and existing.get("status") == "CAPTURED"
        and existing.get("hold_status") == "NONE"
        and existing.get("parser_method") == "DP244_COVERAGE_BYTES_ONLY"
        and existing.get("body_ref") is not None,
        "DP424_HISTORICAL_DP244_CAPTURE_CHANGED",
    )
    body_store = CaptureBodyStore.open_existing_readonly(storage_root)
    original = body_store.read(
        existing["body_ref"], expected_sha256=BODY_SHA256, max_bytes=450_000,
    )
    require(len(original) == CURRENT_BYTES, "DP424_ORIGINAL_BODY_LENGTH_CHANGED")
    current = prepare_senato_corpus_handoff(
        original, source_raw_url=CURRENT_URL, expected_blob_sha1=CONTENT_BLOB_SHA1,
        content_id=content_id, observed_at=existing["observed_at"],
    )
    verify_senato_handoff_roundtrip(current, original)
    current_guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)

    _verified_historic_license()
    require_operator_capture_content(
        store.read_operator_capture_content_state(content_id),
        content_id=content_id, canonical_url=CURRENT_URL,
    )
    historical_rights = rights.read_current(historic_subject)
    if apply and historical_rights is None:
        now = datetime.now(timezone.utc)
        historical_rights = rights.record_rights(
            subject=historic_subject, policy_version=OLD_POLICY,
            rights_status="CLEARED", rights_receipt_ref=OLD_RIGHTS_RECEIPT,
            permitted_uses=OLD_USES, attribution_requirements=("ATTRIBUTION_REQUIRED",),
            reviewed_at=now.isoformat(), expires_at=(now + timedelta(days=30)).isoformat(),
            reviewer_ref="machine:licence-attestation-v1",
        )
    if historical_rights is None:
        return {
            "status": "HOLD_HISTORIC_GRANT_NOT_PERSISTED",
            "content_id": content_id,
            "historic_source_commit": PREVIOUS_COMMIT,
            "historic_source_license": "CC-BY-3.0",
            "historic_license_receipt_sha256": OLD_README_SHA256,
            "historic_body_fetched": False, "database_mutated": False,
            "publication_authority": False,
        }
    require(
        historical_rights.rights_receipt_ref == OLD_RIGHTS_RECEIPT
        and historical_rights.policy_version == OLD_POLICY
        and set(historical_rights.permitted_uses) == set(OLD_USES),
        "DP424_HISTORIC_RIGHTS_CONFLICT",
    )
    previous_guard = SourceFamilyUseGuard(
        read_current=rights.read_current, subject=historic_subject,
        rights_record_id=historical_rights.id, policy_version=OLD_POLICY,
        expected_sha256=OLD_SHA256, expected_media_type="text/plain",
    )
    previous_guard.bind_capture(content_id=content_id, url=PREVIOUS_URL)
    observed_at = datetime.now(timezone.utc).isoformat()
    before = store.find_capture(content_id, OLD_SHA256)
    if apply and before is None:
        operation_ref = deterministic_ingestion_operation_ref(
            "CAPTURE_FETCH", content_id, observed_at,
        )
        store.issue_ingestion_acquisition_permit(
            content_ref=content_id, canonical_url=CURRENT_URL,
            operation_kind="CAPTURE_FETCH", operation_ref=operation_ref,
        )
    fetched = _verified_historic_observation(previous_guard)
    historic = prepare_senato_corpus_handoff(
        fetched.body, source_raw_url=PREVIOUS_URL, expected_blob_sha1=OLD_BLOB_SHA1,
        content_id=content_id, observed_at=observed_at, source_license_id="CC-BY-3.0",
    )
    verify_senato_handoff_roundtrip(historic, fetched.body)
    newer_passage, older_passage = _passage_pair(current, historic)
    require(current.capture.id == existing["id"]
            and historic.capture.id != existing["id"],
            "DP424_CAPTURE_IDS_INVALID")
    observed = {
        "status": "VERIFIED_PRIVATE_SOURCE" if not apply else "PERSISTED_PRIVATE_REPLAY",
        "content_id": content_id, "current_capture_id": existing["id"],
        "current_sha256": BODY_SHA256,
        "historic_capture_id": historic.capture.id, "historic_sha256": OLD_SHA256,
        "current_source_commit": current.source.source_commit_sha,
        "historic_source_commit": PREVIOUS_COMMIT,
        "current_source_license": "CC-BY-4.0",
        "historic_source_license": "CC-BY-3.0",
        "historic_license_receipt_sha256": OLD_README_SHA256,
        "speech_wording_changed": False, "xml_bytes_changed": True,
        "real_source_versions": 2, "source_attribution": "Senato della Repubblica",
        "publication_authority": False, "excerpt_public": False,
    }
    if not apply:
        observed["database_mutated"] = False
        return observed

    # The logical Content relevance authority refers to its current canonical URL;
    # the older immutable locator has separately checked CURRENT source-use rights.
    previous_guard.require("FETCH", content_sha256=OLD_SHA256, media_type=fetched.media_type)
    decision = previous_guard.require(
        "STORE_BODY", content_sha256=OLD_SHA256, media_type=fetched.media_type,
    )
    previous_guard.require("PARSE_TEXT", content_sha256=OLD_SHA256)
    fingerprint = hashlib.sha256(
        (decision.decision_fingerprint + ":" + OLD_SHA256).encode("ascii")
    ).hexdigest()
    if before is None:
        private_guard()
        previous_guard.require("PARSE_TEXT", content_sha256=OLD_SHA256)
        stored = CaptureBodyStore(storage_root).write(
            capture_id=historic.capture.id,
            body=fetched.body, content_sha256=OLD_SHA256,
        )
        record = replace(
            historic.capture, status="CAPTURED", hold_status="NONE",
            rights_status="CLEARED", retention_class="DURABLE_PRIVATE",
            body_ref=stored.body_ref, media_type=fetched.media_type,
            retrieval_method="SAFE_HTTP_PINNED_GIT",
            retrieval_version="dp424-historic-replay-v1",
            metadata={
                "parse_status": "SUCCEEDED",
                "source_commit_sha": PREVIOUS_COMMIT,
                "source_blob_sha1": OLD_BLOB_SHA1,
                "source_license_id": "CC-BY-3.0",
                "source_license_readme_sha256": OLD_README_SHA256,
                "source_use_fingerprint": fingerprint,
                "canonical_text_sha256": historic.canonical_text_sha256,
                "historical_revision_observed_later": True,
                "source_rights_decision": "PRIVATE_CAPTURE_ONLY",
            },
        )
        saved = store.upsert_capture(record)
        require(saved["state"] == "INSERTED", "DP424_CAPTURE_INSERT_COLLISION")
    else:
        saved = before
        require(
            saved.get("id") == historic.capture.id
            and saved.get("status") == "CAPTURED"
            and saved.get("hold_status") == "NONE"
            and saved.get("rights_status") == "CLEARED"
            and saved.get("parser_method") == historic.capture.parser_method
            and saved.get("parser_version") == historic.capture.parser_version
            and saved.get("metadata", {}).get("source_use_fingerprint") == fingerprint
            and saved.get("body_ref") is not None,
            "DP424_EXISTING_HISTORIC_CAPTURE_CONFLICT",
        )
        record = replace(
            historic.capture, observed_at=saved["observed_at"],
            status="CAPTURED", hold_status="NONE",
            rights_status="CLEARED", retention_class="DURABLE_PRIVATE",
            media_type=saved["media_type"], body_ref=saved["body_ref"],
            metadata=saved["metadata"],
        )
    private_guard()
    previous_guard.require("PARSE_TEXT", content_sha256=OLD_SHA256)
    CaptureBodyStore.open_existing_readonly(storage_root).read(
        record.body_ref, expected_sha256=OLD_SHA256, max_bytes=450_000,
    )
    # Row-level SQL fence checks the historic Capture rights/state and fingerprint.
    historical_state = store.insert_private_document_passages(
        capture=record, passages=(older_passage,), use_fingerprint=fingerprint,
    )
    current_guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)
    private_guard()
    current_readback = store.find_capture(content_id, BODY_SHA256)
    require(
        current_readback is not None
        and current_readback.get("id") == existing["id"]
        and current_readback.get("status") == "CAPTURED"
        and current_readback.get("hold_status") == "NONE"
        and current_readback.get("rights_status") == "CLEARED"
        and current_readback.get("body_ref") == existing["body_ref"]
        and current_readback.get("body_purged_at") is None,
        "DP424_CURRENT_CAPTURE_HELD",
    )
    current_state = store.insert_passage(newer_passage)
    reader = _StudioCaptureReader(database_url=database_url)
    compared = inspect_capture_versions(
        reader, content_id=content_id,
        earlier_hash=BODY_SHA256, later_hash=OLD_SHA256,
        include_selector_diff=True,
    )
    require(compared["changes"]["body_hash_changed"]
            and compared["earlier"]["id"] == existing["id"]
            and compared["later"]["id"] == historic.capture.id,
            "DP424_STUDIO_COMPARE_MISMATCH")
    require(
        any(p["id"] == newer_passage.id for p in store.list_passages(existing["id"]))
        and any(p["id"] == older_passage.id for p in store.list_passages(historic.capture.id)),
        "DP424_PASSAGE_READBACK_MISSING",
    )
    reread_current = store.find_capture(content_id, BODY_SHA256)
    require(
        reread_current["parser_method"] == "DP244_COVERAGE_BYTES_ONLY"
        and reread_current["observed_at"] == existing["observed_at"]
        and reread_current["content_sha256"] == existing["content_sha256"],
        "DP424_LEGACY_CAPTURE_MUTATED",
    )
    observed.update({
        "database_mutated": True,
        "current_passage_id": newer_passage.id,
        "historic_passage_id": older_passage.id,
        "current_passage_state": current_state,
        "historic_passage_state": historical_state[0],
        "historic_rights_record_id": historical_rights.id,
        "studio_compare_state": "VERSION_HASH_CHANGED",
        "readback_private": True,
        "historic_observed_at": record.observed_at,
        "current_observed_at": existing["observed_at"],
    })
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DICHIARAZIONI_PUBBLICHE_DATABASE_URL", "dichiarazioni_pubbliche"))
    parser.add_argument(
        "--storage-root", type=Path,
        default=Path("~/.local/share/dichiarazioni-pubbliche-captures").expanduser(),
    )
    parser.add_argument("--apply-private-replay", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.database_url, args.storage_root, apply=args.apply_private_replay), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
