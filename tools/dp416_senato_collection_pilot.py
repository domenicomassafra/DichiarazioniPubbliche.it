#!/usr/bin/env python3
"""One exact licensed Senato Capture -> Passage -> held Statement Candidate.

Default is read-only. An explicit --apply uses the native versioned private
rights registry and corpus writers; it never calls an LLM or publishes data.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, CapturePipelineStore
from dichiarazioni_pubbliche.corpus_repository import INSERT_STATEMENT_CANDIDATE_SQL_V1
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard, SourceUseBlocked
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject
from dichiarazioni_pubbliche.senato_akoma_corpus_handoff import (
    prepare_senato_corpus_handoff, verify_senato_handoff_roundtrip,
)
from dp244_refresh_cycle_canary import CURRENT_COMMIT, CURRENT_URL, SOURCE_FAMILY
from dp326_senato_private_discovery import (
    COLLECTION_ID, CONTENT_BLOB_SHA1, DP330_PRIVATE_CAPTURE_POLICY,
    DP330_PRIVATE_CAPTURE_USES, REVIEWER_REF, RIGHTS_RECEIPT, official_verified_hit,
)
from dp330_senato_private_capture import BODY_SHA256, _context
from dp357_senato_private_semantic import EXPECTED_CAPTURE, EXPECTED_SPEAKER, EXPECTED_TEXT


_BASE_USES = set(DP330_PRIVATE_CAPTURE_USES) | {"PARSE_TEXT"}
_CANDIDATE_USE = "EXTRACT_CANDIDATES"
_TARGET_STATEMENT = "statement-candidate:02a3e35af85163740ebc6dd0b37aa01681c1862954daa5b9cbbc2ff79ee48cf1"
_TARGET_PASSAGE = "passage:48733afb58735720304507820b22110eb18110d6ba91b52954706d3e38c8706a"


def _select(handoff):
    matches = [
        statement for statement in handoff.statements
        if statement.id == _TARGET_STATEMENT
        and EXPECTED_TEXT in statement.normalized_statement
        and statement.metadata.get("source_speaker_ref") == EXPECTED_SPEAKER
        and statement.status == "HELD" and statement.speaker_person_id is None
        and statement.attribution_method is None
        and statement.passage_ids == (_TARGET_PASSAGE,)
    ]
    passages = [p for p in handoff.passages if p.id == _TARGET_PASSAGE]
    if (handoff.capture.id != EXPECTED_CAPTURE or len(matches) != 1
            or len(passages) != 1 or passages[0].capture_id != EXPECTED_CAPTURE
            or passages[0].text_sha256 != matches[0].statement_text_hash
            or passages[0].private_text != matches[0].normalized_statement):
        raise ValueError("DP416_PINNED_SPEECH_OR_PASSAGE_MISMATCH")
    return passages[0], matches[0]


def _grant_private_derivation(rights, subject, original):
    current = rights.read_current(subject)
    if current is None or current.id != original.id:
        raise SourceUseBlocked("DP416_RIGHTS_CHANGED_BEFORE_GRANT")
    uses = set(current.permitted_uses)
    if uses == _BASE_USES | {_CANDIDATE_USE}:
        return current
    if uses != _BASE_USES:
        raise SourceUseBlocked("DP416_PRIVATE_DERIVATION_SCOPE_CONFLICT")
    if current.expires_at is None:
        raise SourceUseBlocked("DP416_PRIVATE_DERIVATION_EXPIRY_REQUIRED")
    # The official CC BY 4.0 source permits this private derivative; recording
    # the use is an explicit machine-verifiable decision, not publication review.
    return rights.record_rights(
        subject=subject, policy_version=DP330_PRIVATE_CAPTURE_POLICY,
        rights_status="CLEARED", rights_receipt_ref=RIGHTS_RECEIPT,
        permitted_uses=tuple(sorted(uses | {_CANDIDATE_USE})),
        attribution_requirements=current.attribution_requirements,
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        expires_at=current.expires_at, reviewer_ref=REVIEWER_REF,
        supersedes_record_id=current.id,
    )


def run(database_url: str, storage_root: Path, *, apply: bool = False) -> dict[str, object]:
    official = official_verified_hit()
    if (official.canonical_url != CURRENT_URL
            or official.metadata.get("commit") != CURRENT_COMMIT
            or official.metadata.get("blob_sha1") != CONTENT_BLOB_SHA1
            or official.metadata.get("license_id") != "CC-BY-4.0"
            or official.metadata.get("license_notice_sha256") != RIGHTS_RECEIPT.rsplit(":", 1)[-1]):
        raise ValueError("DP416_OFFICIAL_SOURCE_LICENCE_INVALID")

    store = CapturePipelineStore(database_url=database_url)
    context = _context(store)
    subject = RightsSubject(
        source_family=SOURCE_FAMILY, locator_kind="URL",
        locator_value=CURRENT_URL, content_id=context["id"],
    )
    rights = PrivateRightsRegistryStore(database_url=database_url)
    current = rights.read_current(subject)
    if (current is None or current.policy_version != DP330_PRIVATE_CAPTURE_POLICY
            or current.rights_status != "CLEARED"
            or current.rights_receipt_ref != RIGHTS_RECEIPT
            or set(current.permitted_uses) not in (_BASE_USES, _BASE_USES | {_CANDIDATE_USE})
            or current.reviewer_ref != REVIEWER_REF
            or "ATTRIBUTION_REQUIRED" not in current.attribution_requirements):
        raise SourceUseBlocked("DP416_PRIVATE_SOURCE_RIGHTS_INVALID")
    guard = SourceFamilyUseGuard(
        read_current=rights.read_current, subject=subject,
        rights_record_id=current.id, policy_version=DP330_PRIVATE_CAPTURE_POLICY,
        expected_sha256=BODY_SHA256,
    )
    guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)
    capture = store.find_capture(context["id"], BODY_SHA256)
    if (capture is None or capture["id"] != EXPECTED_CAPTURE
            or capture.get("status") != "CAPTURED" or capture.get("hold_status") != "NONE"
            or capture.get("rights_status") != "CLEARED"
            or capture.get("retention_class") != "DURABLE_PRIVATE"
            or capture.get("body_purged_at") is not None or not capture.get("body_ref")):
        raise ValueError("DP416_PINNED_CAPTURE_NOT_CURRENT")
    body = CaptureBodyStore.open_existing_readonly(storage_root).read(
        capture["body_ref"], expected_sha256=BODY_SHA256, max_bytes=500_000,
    )
    guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)
    prepared = prepare_senato_corpus_handoff(
        body, source_raw_url=CURRENT_URL, expected_blob_sha1=CONTENT_BLOB_SHA1,
        content_id=context["id"], observed_at=capture["observed_at"],
    )
    verify_senato_handoff_roundtrip(prepared, body)
    passage, statement = _select(prepared)
    guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)

    status = "READY_FOR_PRIVATE_DERIVATION"
    states: dict[str, str] = {}
    if apply:
        current = _grant_private_derivation(rights, subject, current)
        guard = SourceFamilyUseGuard(
            read_current=rights.read_current, subject=subject,
            rights_record_id=current.id, policy_version=DP330_PRIVATE_CAPTURE_POLICY,
            expected_sha256=BODY_SHA256,
        )
        guard.require(_CANDIDATE_USE, content_sha256=BODY_SHA256)
        states["passage"] = store.insert_passage(passage)
        guard.require(_CANDIDATE_USE, content_sha256=BODY_SHA256)
        states["statement_candidate"] = store.run(
            INSERT_STATEMENT_CANDIDATE_SQL_V1,
            id=statement.id, content_id=statement.content_id,
            speaker_person_id="", statement_text_hash=statement.statement_text_hash,
            normalized_statement=statement.normalized_statement,
            statement_at="", attribution_method="", extraction_model="",
            extraction_version=statement.extraction_version,
            status=statement.status, metadata=json.dumps(statement.metadata),
            passage_ids=json.dumps(list(statement.passage_ids)),
        ).strip()
        if states["statement_candidate"] not in {"INSERTED", "EXISTING"}:
            raise RuntimeError("DP416_HELD_CANDIDATE_WRITE_CONFLICT")
        guard.require(_CANDIDATE_USE, content_sha256=BODY_SHA256)
        readback = store.run(
            """SELECT count(*) FROM statement_candidate s
               JOIN statement_candidate_passage l ON l.statement_candidate_id=s.id
               JOIN passage p ON p.id=l.passage_id AND p.content_id=l.content_id
               WHERE s.id=:'statement' AND p.id=:'passage'
                 AND p.capture_id=:'capture' AND s.status='HELD'
                 AND s.speaker_person_id IS NULL AND s.attribution_method IS NULL;""",
            statement=statement.id, passage=passage.id, capture=EXPECTED_CAPTURE,
        )
        if readback.strip() != "1":
            raise RuntimeError("DP416_PRIVATE_COLLECTION_READBACK_FAILED")
        status = "PRIVATE_PASSAGE_AND_HELD_CANDIDATE_PERSISTED"
    return {
        "status": status, "collection_id": COLLECTION_ID, "content_id": context["id"],
        "capture_id": EXPECTED_CAPTURE, "capture_sha256": BODY_SHA256,
        "passage_id": passage.id, "passage_sha256": passage.text_sha256,
        "statement_candidate_id": statement.id, "candidate_status": "HELD",
        "rights_record_id": current.id, "permitted_uses": list(current.permitted_uses),
        "source_commit": CURRENT_COMMIT, "source_license": "CC-BY-4.0",
        "source_attribution": "Senato della Repubblica",
        "writes": states, "model_called": False, "claim_candidate_created": False,
        "publication_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--storage-root", type=Path,
                        default=Path("~/.local/share/dichiarazioni-pubbliche-captures").expanduser())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url required")
    try:
        result = run(args.database_url, args.storage_root, apply=args.apply)
    except (ValueError, RuntimeError, SourceUseBlocked) as exc:
        # psql diagnostics can include private inputs and connection strings.
        code = str(exc)
        if not re.fullmatch(r"(?:DP416|SOURCE_USE|SENATO_AKN|RIGHTS_REGISTRY)_[A-Z0-9_]+", code):
            code = "DP416_PRIVATE_OPERATOR_FAILED"
        result = {"status": "BLOCKED", "reason": code, "publication_authorized": False}
    print(json.dumps(result, sort_keys=True))
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
