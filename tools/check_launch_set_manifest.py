"""Check the real #97 release candidate without authorizing public output."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.launch_set_release import (  # noqa: E402
    validate_release_launch_set_document,
)
from dichiarazioni_pubbliche.launch_set_candidate import LaunchSetCandidateError  # noqa: E402


def main() -> int:
    path = ROOT / "docs" / "release" / "launch-set-v1.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        result = validate_release_launch_set_document(document, root=ROOT)
    except (OSError, ValueError, TypeError, KeyError, LaunchSetCandidateError) as exc:
        print(f"LAUNCH_SET_INVALID:{exc}", file=sys.stderr)
        return 1
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    print(json.dumps({
        "version": document["version"],
        "status": document["launch_state"],
        "publication_authorized": result.launch_authorized,
        "candidate_status": result.candidate_status,
        "source_families": sorted({row.source_family for row in result.rows}),
        "included": len(result.included_source_ids),
        "held": result.held_count,
        "blockers": list(result.blockers),
        "contract_sha256": result.manifest_sha256,
        "document_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "snapshot": document["snapshot"]["status"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
