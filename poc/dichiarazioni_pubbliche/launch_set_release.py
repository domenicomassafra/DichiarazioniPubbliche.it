"""Validate the pinned #97 launch inventory, with no publication authority."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping

from .launch_set_candidate import (
    _HEX40_64, _sha, _sha256, MAX_SOURCE_ROWS, MIN_INCLUDED_SOURCE_FAMILIES,
    LaunchSetCandidateError, LaunchSetCandidateManifest, validate_launch_set_candidate,
)

def validate_release_launch_set_document(
    document: Mapping[str, object], *, root: Path
) -> LaunchSetCandidateManifest:
    """Validate the evidence-backed, non-publishing #97 candidate at its file boundary."""
    if document.get("version") != "launch-set-v1":
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_VERSION_INVALID")
    if document.get("launch_state") != "HOLD" or document.get("publication_authorized") is not False:
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_AUTHORITY_INVALID")

    snapshot = document.get("snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("status") != "NOT_BUILT":
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_SNAPSHOT_MUST_BE_UNBUILT")
    if snapshot.get("public_item_ids") != []:
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_PUBLIC_ITEMS_FORBIDDEN")
    if snapshot.get("projection_sha256") is not None or snapshot.get("rollback_receipt") is not None:
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_UNEXECUTED_RECEIPT_REQUIRED")
    if snapshot.get("candidate_commit") != document.get("candidate_base_commit"):
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_BASE_COMMIT_MISMATCH")
    if (not isinstance(document.get("candidate_base_commit"), str)
            or not _HEX40_64.fullmatch(document["candidate_base_commit"])):
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_BASE_COMMIT_INVALID")
    registry = document.get("source_registry")
    if not isinstance(registry, dict) or registry.get("path") != "config/source-registry.v1.json":
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_REGISTRY_INVALID")
    if hashlib.sha256((root / registry["path"]).read_bytes()).hexdigest() != registry.get("sha256"):
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_REGISTRY_HASH_MISMATCH")
    if snapshot.get("source_registry_sha256") != registry["sha256"]:
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_SNAPSHOT_REGISTRY_MISMATCH")
    disclosure = document.get("disclosure")
    required_disclosure = ("method", "statement_time", "source_publication_time",
                           "observation_time", "evidence_cutoff", "provider", "review",
                           "correction_and_reply", "operator_contact", "source_attribution")
    if not isinstance(disclosure, dict) or any(not disclosure.get(k) for k in required_disclosure):
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_DISCLOSURE_INCOMPLETE")

    sources = document.get("sources")
    if not isinstance(sources, list) or not 3 <= len(sources) <= MAX_SOURCE_ROWS:
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_FAMILY_INVENTORY_INVALID")
    rows: list[dict[str, object]] = []
    forbidden = {"raw_body", "raw_transcript_body", "transcript_body", "evidence_body",
                 "credentials", "token", "private_reply", "internal_note", "prompt_body"}
    def contains_private_field(value: object) -> bool:
        if isinstance(value, dict):
            return bool(forbidden.intersection(value)) or any(
                contains_private_field(item) for item in value.values()
            )
        if isinstance(value, list):
            return any(contains_private_field(item) for item in value)
        return False

    if contains_private_field(document):
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_PRIVATE_FIELD_FORBIDDEN")
    for source in sources:
        if not isinstance(source, dict):
            raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_SOURCE_FIELDS_REQUIRED")
        if source.get("state") != "HELD":
            raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_INCLUDED_WITHOUT_CLEARANCE")
        provenance = source.get("provenance")
        rights = source.get("rights")
        acquisition = source.get("acquisition")
        processing = source.get("processing")
        if not all(isinstance(part, dict) for part in (provenance, rights, acquisition, processing)):
            raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_SOURCE_FIELDS_REQUIRED")
        if not (str(provenance.get("locator", "")).startswith("https://")
                and provenance.get("observed_at")
                and provenance.get("source_version")
                and provenance.get("name")
                and provenance.get("platform")):
            raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_PROVENANCE_REQUIRED")
        if not (rights.get("license") and rights.get("attribution")
                and str(rights.get("terms_url", "")).startswith("https://")
                and rights.get("public_excerpt") == "HELD"
                and rights.get("retention") and rights.get("takedown")):
            raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_RIGHTS_REQUIRED")
        terms_digest = rights.get("terms_sha256")
        if terms_digest is not None:
            _sha256(terms_digest, "RIGHTS_EVIDENCE_SHA256")
        reference = rights.get("local_evidence")
        if reference:
            evidence_path = (root / str(reference)).resolve()
            if not evidence_path.is_relative_to(root.resolve()) or not evidence_path.is_file():
                raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_RIGHTS_EVIDENCE_INVALID")
            if not terms_digest or terms_digest not in evidence_path.read_text(encoding="utf-8"):
                raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_RIGHTS_EVIDENCE_MISMATCH")
        if not (acquisition.get("mode") and acquisition.get("language")
                and acquisition.get("content_types")
                and acquisition.get("max_items") == 1
                and acquisition.get("timezone") == "UTC"):
            raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_ACQUISITION_UNBOUNDED")
        if processing.get("public_projection") is not False:
            raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_PUBLIC_PROJECTION_FORBIDDEN")
        rows.append({
            "source_id": source["source_id"],
            "source_family": source["source_family"],
            "state": source["state"],
            "rights_state": source["rights_state"],
            "privacy_state": source["privacy_state"],
            "provider_state": source["provider_state"],
            "rights_decision_ref": rights.get("decision_ref"),
            "privacy_decision_ref": rights.get("privacy_decision_ref"),
            "policy_decision_ref": document.get("policy_decision_ref"),
            "discovery_path_id": processing.get("discovery"),
            "transcript_path_id": processing.get("transcript"),
            "speaker_path_id": processing.get("speaker"),
            "evidence_path_id": processing.get("evidence"),
            "provider_path_id": processing.get("provider"),
            "health_owner": processing.get("health_owner"),
            "disclosure_decision_ref": document.get("disclosure_decision_ref"),
            "config_sha256": _sha(acquisition),
        })
    manifest = validate_launch_set_candidate(rows)
    if len({row.source_family for row in manifest.rows}) < MIN_INCLUDED_SOURCE_FAMILIES:
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_FAMILY_INVENTORY_TOO_SMALL")
    if snapshot.get("held_count") != manifest.held_count:
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_HELD_COUNT_MISMATCH")
    if snapshot.get("omitted_count") != manifest.omitted_count:
        raise LaunchSetCandidateError("LAUNCH_SET_RELEASE_OMITTED_COUNT_MISMATCH")
    return manifest
