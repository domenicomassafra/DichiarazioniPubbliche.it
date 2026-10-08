#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

# Historical operator name delegates to the reviewed private-batch path.
# The old bare --passage-id invocation is no longer allowed to bypass rights.
from extract_research_candidates import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
