"""Issue or inspect private Camera PARSE_TEXT authority on existing PostgreSQL Captures."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.camera_parse_authority import CameraParseAuthority, SOURCES
from dichiarazioni_pubbliche.reviewer_identity_authority import LocalFileReviewerIdentityAuthority
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    sub = parser.add_subparsers(dest="action", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--content-id", choices=tuple(SOURCES), required=True)
    inspect.add_argument("--use", default="PARSE_TEXT")
    issue = sub.add_parser("issue")
    issue.add_argument("--content-id", choices=tuple(SOURCES), required=True)
    issue.add_argument("--credential-id", required=True)
    args = parser.parse_args(argv)
    try:
        authority = CameraParseAuthority(
            PrivateRightsRegistryStore(database_url=args.database_url),
            LocalFileReviewerIdentityAuthority(args.authority_root),
        )
        content_sha256 = SOURCES[args.content_id][1]
        if args.action == "inspect":
            result = authority.inspect(
                content_id=args.content_id, capture_sha256=content_sha256, use=args.use,
            )
        else:
            result = authority.issue(
                content_id=args.content_id, capture_sha256=content_sha256,
                credential_id=args.credential_id,
                issued_at=datetime.now(timezone.utc).isoformat(),
            )
        print(json.dumps(result, sort_keys=True, ensure_ascii=True))
        return 0 if result["permitted"] else 2
    except (OSError, ValueError, RuntimeError):
        print("CAMERA_PARSE_AUTHORITY_OPERATION_FAILED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
