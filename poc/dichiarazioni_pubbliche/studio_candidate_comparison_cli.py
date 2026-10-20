"""Opt-in, read-only DP-418 local comparison export for a qualified operator.

Usage (on the private host with its existing PostgreSQL read credentials):
  python -m dichiarazioni_pubbliche.studio_candidate_comparison_cli \
    --run-id RUN_ID --candidate-id CANDIDATE_ID --output /private/review.html

The generated file contains only allowlisted source metadata and an ephemeral
browser-only quote comparison; it never exports private passage text.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re

from dichiarazioni_pubbliche.studio_candidate_review_ui import (
    build_candidate_comparison_read_model,
    render_candidate_comparison_workspace,
)
from dichiarazioni_pubbliche.studio_candidate_target_pg import StudioCandidateTargetPg
from dichiarazioni_pubbliche.studio_local_api import (
    _StudioCandidateReader, _StudioPromotionContextReader,
)

_REF = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a private, read-only DP-418 review page")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if any(not _REF.fullmatch(value) or ".." in value
           for value in (args.run_id, args.candidate_id)):
        raise ValueError("DP418_COMPARISON_CLI_REFERENCE_INVALID")
    model = build_candidate_comparison_read_model(
        _StudioCandidateReader(), _StudioPromotionContextReader(),
        StudioCandidateTargetPg(),
        run_id=args.run_id, claim_candidate_id=args.candidate_id,
    )
    html = render_candidate_comparison_workspace(model)
    # O_EXCL refuses overwrites and symlinks; only newly created files are used.
    fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(html)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
