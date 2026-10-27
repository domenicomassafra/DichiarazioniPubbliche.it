"""List durable challenge targets for the public withdrawal fence.

An item remains guarded after a new projection no longer includes it: static
HTML from a previous release may still reference the old published Finding.
"""

from __future__ import annotations

import json
from typing import Any


def challenged_findings(ledger: Any) -> tuple[str, ...]:
    if hasattr(ledger, "challenged_findings"):
        return tuple(ledger.challenged_findings())
    raw = ledger.run(
        """
        SELECT COALESCE(json_agg(target_finding_id)::text, '[]') FROM (
            SELECT DISTINCT target_finding_id
            FROM private_challenge_request
            WHERE challenge_kind IN ('TAKEDOWN', 'CORRECTION')
            LIMIT 10001
        ) AS challenged;
        """,
        execution_timeout_seconds=5,
    )
    values = json.loads(raw or "[]")
    if not isinstance(values, list) or len(values) > 10_000 or any(
        not isinstance(item, str) or not 1 <= len(item) <= 200 for item in values
    ):
        raise ValueError("CHALLENGE_LEDGER_TARGETS_UNAVAILABLE")
    return tuple(values)
