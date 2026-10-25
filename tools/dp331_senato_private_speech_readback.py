#!/usr/bin/env python3
"""Read the #330 pinned private Capture and inspect speech roles; no DB writes."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, CapturePipelineStore
from dichiarazioni_pubbliche.dp331_private_speech_probe import (
    probe_private_speech, probe_private_statement_relation,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject
from dichiarazioni_pubbliche.senato_akoma_stenographic import import_senato_akoma_stenographic
from dp244_refresh_cycle_canary import CURRENT_URL, SOURCE_FAMILY
from dp326_senato_private_discovery import (
    DP330_PRIVATE_CAPTURE_POLICY, DP330_PRIVATE_CAPTURE_USES, CONTENT_BLOB_SHA1,
)
from dp330_senato_private_capture import BODY_SHA256, _context


def run(
    database_url: str,
    storage_root: Path,
    *,
    ordinals: tuple[int, ...],
    german_draft: str | None = None,
    italian_quote_span: tuple[int, int] | None = None,
    compare_relation: bool = False,
) -> dict[str, object]:
    if compare_relation and (
        len(ordinals) != 2 or ordinals[0] == ordinals[1]
        or german_draft is not None
    ):
        raise ValueError("DP333_TWO_DISTINCT_SPEECHES_REQUIRED")
    if german_draft is not None and len(ordinals) != 1:
        raise ValueError("DP331_ONE_SPEECH_PER_DERIVED_TRANSLATION")
    store = CapturePipelineStore(database_url=database_url)
    context = _context(store)
    subject = RightsSubject(
        source_family=SOURCE_FAMILY, locator_kind="URL",
        locator_value=CURRENT_URL, content_id=context["id"],
    )
    rights = PrivateRightsRegistryStore(database_url=database_url)
    current = rights.read_current(subject)
    if (
        current is None or current.rights_status != "CLEARED"
        or current.policy_version != DP330_PRIVATE_CAPTURE_POLICY
        or set(current.permitted_uses) not in (
            set(DP330_PRIVATE_CAPTURE_USES),
            set(DP330_PRIVATE_CAPTURE_USES) | {"PARSE_TEXT"},
        )
    ):
        raise RuntimeError("DP331_PRIVATE_RIGHTS_CURRENT_REQUIRED")
    guard = SourceFamilyUseGuard(
        read_current=rights.read_current, subject=subject,
        rights_record_id=current.id, policy_version=DP330_PRIVATE_CAPTURE_POLICY,
        expected_sha256=BODY_SHA256,
    )
    # Both exact private scopes above require RESEARCH_CAPTURE_PRIVATE.
    # The generic source-use guard recognizes STORE_BODY for captured bytes.
    guard.require("STORE_BODY", content_sha256=BODY_SHA256)
    if compare_relation:
        guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)
    found = store.find_capture(context["id"], BODY_SHA256)
    if not found or not found.get("body_ref"):
        raise RuntimeError("DP331_PINNED_PRIVATE_CAPTURE_MISSING")
    body = CaptureBodyStore.open_existing_readonly(storage_root).read(
        found["body_ref"], expected_sha256=BODY_SHA256, max_bytes=450000,
    )
    guard.require("STORE_BODY", content_sha256=BODY_SHA256)
    if compare_relation:
        guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)
    imported = import_senato_akoma_stenographic(
        body, source_raw_url=CURRENT_URL, expected_blob_sha1=CONTENT_BLOB_SHA1,
    )
    if imported.source_sha256 != BODY_SHA256:
        raise RuntimeError("DP331_CAPTURE_SOURCE_REVISION_MISMATCH")
    # Ordinals are explicit to prevent an accidental bulk extraction.
    observed = [
        probe_private_speech(
            imported, ordinal=ordinal, german_draft=german_draft,
            italian_quote_span=italian_quote_span,
        )
        for ordinal in ordinals
    ]
    result = {
        "source": "SenatoDellaRepubblica/AkomaNtosoBulkData",
        "capture_id": found["id"], "rights_record_id": current.id,
        "capture_observed_at": found["observed_at"],
        "rights_reviewed_at": current.reviewed_at,
        "rights_expires_at": current.expires_at,
        "rights_status": current.rights_status,
        "rights_permitted_uses": current.permitted_uses,
        "readback_at": datetime.now(timezone.utc).isoformat(),
        "sitting_date": imported.sitting_date,
        "source_sha256": imported.source_sha256,
        "source_commit": imported.source_commit_sha,
        "source_license_id": imported.source_license_id,
        "speech_count_in_document": len(imported.speeches),
        "unresolved_official_speech_count": len(imported.held_speeches),
        "observations": observed,
        "status": "PRIVATE_HOLD",
        "german_source_status": (
            "DERIVED_UNREVIEWED_HOLD" if german_draft is not None
            else "NOT_OBSERVED_DE_TRANSLATION_NEEDS_REVIEW"
        ),
        "extraction_authorized": False,
        "publication_authorized": False,
    }
    if compare_relation:
        result["relation"] = probe_private_statement_relation(
            imported, ordinals=ordinals,
        )
        # A grant may be revoked while a private relation is being evaluated.
        guard.require("PARSE_TEXT", content_sha256=BODY_SHA256)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--storage-root", type=Path, default=Path("~/.local/share/dichiarazioni-pubbliche-captures").expanduser())
    parser.add_argument("--ordinal", type=int, action="append", required=True)
    parser.add_argument("--compare-relation", action="store_true")
    parser.add_argument("--german-draft-file", type=Path)
    parser.add_argument("--quote-start", type=int)
    parser.add_argument("--quote-end", type=int)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url is required")
    if len(args.ordinal) > 3 or len(set(args.ordinal)) != len(args.ordinal):
        parser.error("only one to three unique speech ordinals are permitted")
    if args.compare_relation and (len(args.ordinal) != 2 or args.german_draft_file is not None):
        parser.error("--compare-relation requires exactly two ordinals and no translation")
    if args.german_draft_file is not None and (
        args.quote_start is None or args.quote_end is None
    ):
        parser.error("German draft requires exact Italian --quote-start and --quote-end")
    if args.german_draft_file is None and (
        args.quote_start is not None or args.quote_end is not None
    ):
        parser.error("Italian quote span requires --german-draft-file")
    german_draft = None
    if args.german_draft_file is not None:
        path = args.german_draft_file
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 4000:
            parser.error("German draft must be an existing regular file of at most 4000 bytes")
        german_draft = path.read_text(encoding="utf-8")
    print(json.dumps(run(
        args.database_url, args.storage_root,
        ordinals=tuple(args.ordinal), german_draft=german_draft,
        compare_relation=args.compare_relation,
        italian_quote_span=(
            (args.quote_start, args.quote_end) if german_draft is not None else None
        ),
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
