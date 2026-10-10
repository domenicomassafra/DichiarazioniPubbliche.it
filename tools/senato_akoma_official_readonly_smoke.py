"""Repeatable DP-233 authentic Senato XML format smoke, held corpus, isolated readback.

No operational database/provider, launch-source approval, human reviewer, or
production source-family proof is implied. All source bytes remain in memory;
serialized private held records exist only in an auto-cleaned /tmp directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import urllib.request
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from dichiarazioni_pubbliche.corpus_repository import (
    normalize_content_capture,
    normalize_passage,
    normalize_statement_candidate,
)
from dichiarazioni_pubbliche.senato_akoma_corpus_handoff import (
    prepare_senato_corpus_handoff,
    verify_senato_handoff_roundtrip,
)


REPOSITORY = "SenatoDellaRepubblica/AkomaNtosoBulkData"
PATH = "Leg19/Atto00055187/resaula/01457617-ra.akn.xml"
COMMIT = "bfac144eb5c54820971bc1020fece11aae56ec90"
BLOB = "bec30c067a1a79e8b377af483cfc4bfb44d13896"
MAX_SOURCE_BYTES = 3_000_000
MAX_METADATA_BYTES = 64_000


def _fetch(source_url: str, *, max_bytes: int = MAX_SOURCE_BYTES) -> bytes:
    request = urllib.request.Request(
        source_url,
        headers={"User-Agent": "DichiarazioniPubbliche-DP233-source-format-readonly"},
    )
    with urllib.request.urlopen(request, timeout=18) as response:
        if response.url != source_url or response.status != 200:
            raise ValueError("DP233_OFFICIAL_RAW_SOURCE_REDIRECT_OR_STATUS")
        raw = response.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise ValueError("DP233_OFFICIAL_RAW_SOURCE_SIZE_INVALID")
    return raw


def verify_pinned_official_license() -> dict[str, object]:
    """Independent repository, commit and license evidence for owner review.

    The public license and GitHub membership are observations, *not* an
    owner's source-family/rights approval, nor proof of a particular excerpt.
    Fetch from fixed official hosts and one exact immutable commit only.
    """
    api = f"https://api.github.com/repos/{REPOSITORY}/commits/{COMMIT}"
    readme = f"https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/README.MD"
    license_url = f"https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/LICENSE.MD"
    try:
        record = json.loads(_fetch(api, max_bytes=MAX_METADATA_BYTES))
    except (ValueError, UnicodeError):
        raise ValueError("DP233_OFFICIAL_COMMIT_RECEIPT_INVALID") from None
    if (not isinstance(record, dict) or record.get("sha") != COMMIT
            or record.get("html_url") != f"https://github.com/{REPOSITORY}/commit/{COMMIT}"
            or record.get("url") != api):
        raise ValueError("DP233_OFFICIAL_COMMIT_MEMBERSHIP_UNVERIFIED")
    raw_readme = _fetch(readme, max_bytes=MAX_METADATA_BYTES)
    raw_license = _fetch(license_url, max_bytes=MAX_METADATA_BYTES)
    try:
        readme_text = raw_readme.decode("utf-8")
        license_text = raw_license.decode("utf-8")
    except UnicodeError:
        raise ValueError("DP233_OFFICIAL_LICENSE_RECEIPT_INVALID") from None
    if (not re.search(r"(?im)^## Licenza ##\s*\n\s*CC BY 4\.0\s*$", readme_text)
            or "Creative Commons Attribution 4.0 International Public License"
            not in license_text):
        raise ValueError("DP233_OFFICIAL_LICENSE_RECEIPT_MISMATCH")
    return {
        "repository_commit_membership": "CONFIRMED_BY_GITHUB_API",
        "source_license_notice": "CC-BY-4.0",
        "license_notice_url": readme,
        "license_document_url": license_url,
        "license_notice_sha256": hashlib.sha256(raw_readme).hexdigest(),
        "license_document_sha256": hashlib.sha256(raw_license).hexdigest(),
        "license_observation_is_owner_approval": False,
        "rights_review_required": True,
    }


def run() -> dict[str, object]:
    official_license = verify_pinned_official_license()
    source_url = f"https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/{PATH}"
    raw = _fetch(source_url)
    handoff = prepare_senato_corpus_handoff(
        raw, source_raw_url=source_url, expected_blob_sha1=BLOB,
        content_id="content:senato:akn:leg19:atto00055187:01457617",
        observed_at=datetime.now(timezone.utc).isoformat(),
    )
    verify_senato_handoff_roundtrip(handoff, raw)
    with tempfile.TemporaryDirectory(prefix="dp233-akn-readonly-") as directory:
        path = Path(directory) / "held-private-corpus-records.json"
        path.write_text(json.dumps({
            "capture": handoff.capture.to_dict(),
            "passages": [p.to_dict() for p in handoff.passages],
            "statements": [s.to_dict() for s in handoff.statements],
        }, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        # This readback goes through real repository record validation and exact
        # byte replay before deleting the private temporary staging directory.
        recovered = json.loads(path.read_text(encoding="utf-8"))
        verified = replace(
            handoff, capture=normalize_content_capture(recovered["capture"]),
            passages=tuple(normalize_passage(p) for p in recovered["passages"]),
            statements=tuple(normalize_statement_candidate(s) for s in recovered["statements"]),
        )
        verify_senato_handoff_roundtrip(verified, raw)
        persisted_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "status": "AUTHENTIC_FORMAT_PROOF_ONLY_SOURCE_FAMILY_UNAPPROVED",
        "sitting_id": handoff.source.sitting_id,
        "source_raw_url": handoff.source.source_raw_url,
        "source_commit_sha": handoff.source.source_commit_sha,
        "source_blob_sha1": handoff.source.source_blob_sha1,
        "source_sha256": handoff.source.source_sha256,
        "source_bytes": len(raw),
        "license_scope": handoff.source.source_license_id,
        "license_url": handoff.source.source_license_url,
        "official_license_evidence": official_license,
        "source_rights_decision": handoff.source.source_rights_decision,
        "source_registry_approval": "NOT_PRESENT",
        "capture_rights": handoff.capture.rights_status,
        "capture_status": handoff.capture.status,
        "capture_hold": handoff.capture.hold_status,
        "capture_retention": handoff.capture.retention_class,
        "passage_count": len(handoff.passages),
        "held_statement_count": len(handoff.statements),
        "unresolved_or_oversize_speech_count": len(handoff.held_speeches),
        "all_statement_speakers_unapproved": all(s.speaker_person_id is None for s in handoff.statements),
        "isolated_persisted_readback_sha256": persisted_sha256,
        "isolated_temp_store_deleted": not path.exists(),
        "dp233_ac10_closed": False,
        "publication_authorized": False,
    }


if __name__ == "__main__":
    # Explicit operator dry-run prevents accidental automatic source admission.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-readonly-format-probe", action="store_true")
    args = parser.parse_args()
    if not args.official_readonly_format_probe:
        parser.error("Pass --official-readonly-format-probe for an explicit test run")
    try:
        print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        # Do not surface upstream body/transcript/provider response in receipts.
        code = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r"[A-Z0-9_]{8,120}", str(exc)) else "DP233_OFFICIAL_FORMAT_PROBE_FAILED"
        print(json.dumps({"status": "FAILED", "reason_code": code}), file=sys.stderr)
        raise SystemExit(2) from None
