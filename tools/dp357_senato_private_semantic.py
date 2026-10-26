#!/usr/bin/env python3
"""DP-357: one rights-gated, private, real-weight Senato semantic canary.

All comparison variants are synthetic and ephemeral. No candidate, vector,
identification, result or publication decision is persisted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.candidate_matching import MatchingInput, rank_candidate_matches
from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, CapturePipelineStore
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard, SourceUseBlocked
from dichiarazioni_pubbliche.private_semantic_matching import run_private_semantic_matching
from dichiarazioni_pubbliche.proposition_clustering import PropositionInput
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject
from dp244_refresh_cycle_canary import CURRENT_COMMIT, CURRENT_URL, SOURCE_FAMILY
from dp326_senato_private_discovery import (
    CONTENT_BLOB_SHA1, DP330_PRIVATE_CAPTURE_POLICY, DP330_PRIVATE_CAPTURE_USES,
    RIGHTS_RECEIPT, REVIEWER_REF, official_verified_hit,
)
from dp330_senato_private_capture import BODY_SHA256, _context

EXPECTED_CAPTURE = "capture:a2849fbebd69aa54acc01a259db47379bc9587ec6c67f09720db3dca0768fb4a"
EXPECTED_TEXT = "PRESIDENTE. Non essendovi osservazioni, il processo verbale è approvato."
EXPECTED_SPEAKER = "#p32600"
SOURCE_DATE = "2025-05-29"  # FRBRdate 'presentazione' in the exact pinned XML


def _case_from_capture(body: bytes, capture_id: str, content_id: str) -> tuple[MatchingInput, tuple[MatchingInput, ...]]:
    """Extract the pinned source sentence and construct *unpersisted* comparisons."""
    if hashlib.sha256(body).hexdigest() != BODY_SHA256 or capture_id != EXPECTED_CAPTURE:
        raise ValueError("DP357_CAPTURE_HASH_OR_ID_MISMATCH")
    root = ElementTree.fromstring(body)
    dates = [
        element.attrib.get("date")
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "FRBRdate"
        and element.attrib.get("name") == "presentazione"
    ]
    passages = [
        element
        for speech in root.iter()
        if speech.tag.rsplit("}", 1)[-1] == "speech"
        and speech.attrib.get("by") == EXPECTED_SPEAKER
        for element in speech.iter()
        if element.tag.rsplit("}", 1)[-1] == "p"
        and " ".join("".join(element.itertext()).split()) == EXPECTED_TEXT
    ]
    if len(passages) != 1 or not dates or set(dates) != {SOURCE_DATE}:
        raise ValueError("DP357_SOURCE_PASSAGE_OR_DATE_UNVERIFIED")
    scope = {"reference_period": SOURCE_DATE}
    # This key is only a source-local speech pointer, NEVER identification of a
    # natural person; no two people are inferred to be the same speaker.
    source_pointer = ("akn:speech:" + EXPECTED_SPEAKER,)

    def sample(identifier: str, text: str, *, claim_type: str = "PROCEDURAL_STATEMENT",
               scope_value: dict | None = None, entity_keys: tuple[str, ...] = source_pointer) -> MatchingInput:
        return MatchingInput(
            proposition=PropositionInput(
                member_type="CLAIM_CANDIDATE", member_id="synthetic:dp357:" + identifier,
                content_id=content_id, normalized_text=text,
                provenance_key="private-canary:" + capture_id + ":" + identifier,
                entity_keys=entity_keys,
            ), claim_type=claim_type,
            temporal_scope=scope if scope_value is None else scope_value,
        )

    original = sample("source", EXPECTED_TEXT)
    targets = (
        sample("paraphrase", "PRESIDENTE. Il processo verbale è stato approvato, non essendoci osservazioni."),
        sample("negation", "PRESIDENTE. Non essendovi osservazioni, il processo verbale non è approvato."),
        sample("quotation", '"' + EXPECTED_TEXT + '"'),
        sample("speaker", "PRESIDENTE. Non vi sono osservazioni, il verbale è approvato.",
               entity_keys=("akn:speech:#another-unverified-speaker",)),
        sample("period", "PRESIDENTE. Non essendovi osservazioni, il verbale è approvato.",
               scope_value={"reference_period": "2024-05-29"}),
        sample("type", "PRESIDENTE. Non essendovi osservazioni, il verbale è approvato.",
               claim_type="OPINION"),
    )
    return original, targets


def _authorize_parse(rights: PrivateRightsRegistryStore, subject: RightsSubject, current) -> object:
    """Supersede only the exact existing Senate capture rights with PARSE_TEXT."""
    if current is None or current.policy_version != DP330_PRIVATE_CAPTURE_POLICY or (
        current.rights_status != "CLEARED" or current.rights_receipt_ref != RIGHTS_RECEIPT
    ):
        raise SourceUseBlocked("DP357_EXISTING_RIGHTS_UNVERIFIED")
    uses = set(current.permitted_uses)
    if uses in (
        set(DP330_PRIVATE_CAPTURE_USES) | {"PARSE_TEXT"},
        set(DP330_PRIVATE_CAPTURE_USES) | {"PARSE_TEXT", "EXTRACT_CANDIDATES"},
    ):
        return current
    if uses != set(DP330_PRIVATE_CAPTURE_USES):
        raise SourceUseBlocked("DP357_EXISTING_RIGHTS_SCOPE_CONFLICT")
    now = datetime.now(timezone.utc)
    if not current.expires_at or datetime.fromisoformat(current.expires_at) <= now:
        raise SourceUseBlocked("DP357_RIGHTS_EXPIRED")
    official = official_verified_hit()
    if (official.canonical_url != CURRENT_URL
            or official.metadata.get("commit") != CURRENT_COMMIT
            or official.metadata.get("blob_sha1") != CONTENT_BLOB_SHA1
            or official.metadata.get("license_id") != "CC-BY-4.0"
            or official.metadata.get("license_notice_sha256") != RIGHTS_RECEIPT.rsplit(":", 1)[-1]):
        raise SourceUseBlocked("DP357_OFFICIAL_LICENSE_UNVERIFIED")
    return rights.record_rights(
        subject=subject, policy_version=DP330_PRIVATE_CAPTURE_POLICY,
        rights_status="CLEARED", rights_receipt_ref=RIGHTS_RECEIPT,
        permitted_uses=tuple(sorted(uses | {"PARSE_TEXT"})),
        attribution_requirements=current.attribution_requirements,
        reviewed_at=now.isoformat(), expires_at=current.expires_at,
        reviewer_ref=REVIEWER_REF, supersedes_record_id=current.id,
    )


def run(database_url: str, storage_root: Path, *, apply_parse_rights: bool = False) -> dict[str, object]:
    store = CapturePipelineStore(database_url=database_url)
    context = _context(store)
    subject = RightsSubject(source_family=SOURCE_FAMILY, locator_kind="URL",
                            locator_value=CURRENT_URL, content_id=context["id"])
    rights = PrivateRightsRegistryStore(database_url=database_url)
    current = rights.read_current(subject)
    if apply_parse_rights:
        current = _authorize_parse(rights, subject, current)
    if current is None:
        raise SourceUseBlocked("SOURCE_USE_RECORD_MISSING")
    guard = SourceFamilyUseGuard(
        read_current=rights.read_current, subject=subject, rights_record_id=current.id,
        policy_version=DP330_PRIVATE_CAPTURE_POLICY, expected_sha256=BODY_SHA256,
    )
    guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)
    capture = store.find_capture(context["id"], BODY_SHA256)
    if not capture or capture["id"] != EXPECTED_CAPTURE or not capture.get("body_ref"):
        raise ValueError("DP357_PERSISTENT_CAPTURE_MISSING")
    body = CaptureBodyStore.open_existing_readonly(storage_root).read(
        capture["body_ref"], expected_sha256=BODY_SHA256, max_bytes=500_000
    )
    # The current grant is re-read after reading, before the model touches text.
    guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)
    candidate, targets = _case_from_capture(body, capture["id"], context["id"])
    deterministic = rank_candidate_matches(candidate, targets)
    model = run_private_semantic_matching(candidate, targets)
    if model.state != "HOLD":
        return {"state": "BLOCKED", "reason": model.reason, "hints": [],
                "capture_id": capture["id"], "rights_record_id": current.id}
    # Re-read after inference, so expiry/revocation during execution blocks even
    # private delivery of the result.
    guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)
    return {
        "state": "HOLD", "reason": "PRIVATE_REVIEW_ONLY",
        "capture_id": capture["id"], "capture_sha256": BODY_SHA256,
        "rights_record_id": current.id, "rights_use": "PARSE_TEXT",
        "source_commit": CURRENT_COMMIT, "source_attribution": "Senato della Repubblica",
        "source_license": "CC-BY-4.0", "source_date_field": "FRBRdate:presentazione",
        "source_date": SOURCE_DATE, "model_id": model.model_id,
        "model_revision": model.revision, "model_receipt_sha256": model.receipt_sha256,
        "deterministic": {row.target.proposition.member_id: row.disposition for row in deterministic},
        "hints": [
            {"target": hint.target_id, "similarity": hint.similarity,
             "match_class": hint.match_class, "disposition": hint.disposition}
            for hint in model.hints
        ],
        "published": False, "persisted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--storage-root", type=Path,
                        default=Path("~/.local/share/dichiarazioni-pubbliche-captures").expanduser())
    parser.add_argument("--apply-parse-rights", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url is required")
    try:
        result = run(args.database_url, args.storage_root, apply_parse_rights=args.apply_parse_rights)
    except (SourceUseBlocked, ValueError) as exc:
        result = {"state": "BLOCKED", "reason": str(exc), "hints": []}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "HOLD" else 2


if __name__ == "__main__":
    raise SystemExit(main())
