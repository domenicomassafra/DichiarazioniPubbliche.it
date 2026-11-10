"""Owner decision 49: load the versioned, fail-closed autopublication contract.

The contract authorizes the workflow, not the rights or review of any item.
Production still needs an authenticated review execution witness per item.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parents[2] / "config/autopublish.v1.json"
_CONTRACT = "dp-autopublish-owner49-2026-11-10"
_CHECKS = {
    "PROVENANCE", "WORDING", "SPEAKER", "PERSON", "RIGHTS_PRIVACY",
    "CURRENT_CHALLENGE", "EDITORIAL_REVIEW", "AUTHENTIC_EXECUTION",
    "PUBLIC_READBACK",
}


def load_autopublish_contract(path: str | None = None) -> dict[str, object]:
    """Fail closed if the configured authorization is missing or altered."""
    config_path = Path(path or os.environ.get(
        "DICHIARAZIONI_PUBBLICHE_AUTOPUBLISH_CONFIG", str(_DEFAULT),
    ))
    try:
        policy = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("DP_AUTOPUBLISH_CONTRACT_UNAVAILABLE") from exc
    checks = policy.get("required_checks") if isinstance(policy, dict) else None
    if (
        not isinstance(policy, dict)
        or policy.get("schema_version") != 1
        or policy.get("contract") != _CONTRACT
        or policy.get("owner_decision") != {
            "number": 49,
            "date": "2026-11-10",
            "source": "/Users/domenico/.dstack/docs/evidence/orchestrator-owner-decisions.md",
            "source_section": "Risposte numerate della seconda intervista",
            "issue": "https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/413",
        }
        or policy.get("publish_automatically") is not True
        or policy.get("per_record_owner_go") is not False
        or not isinstance(checks, list)
        or len(checks) != len(_CHECKS)
        or any(type(code) is not str for code in checks)
        or set(checks) != _CHECKS
        or policy.get("normal_review") != "ONE_EDITORIAL"
        or policy.get("uncertain_review") != "TWO_INDEPENDENT_PLUS_THIRD_AUDIT"
        or policy.get("uncertainty_disposition") != "HOLD_UNTIL_ESCALATED_REVIEW"
        or policy.get("withdraw_on_revoke_or_correction") is not True
        or policy.get("missing_authority_disposition") != "HOLD"
    ):
        raise ValueError("DP_AUTOPUBLISH_CONTRACT_INVALID")
    return policy


__all__ = ["load_autopublish_contract"]
