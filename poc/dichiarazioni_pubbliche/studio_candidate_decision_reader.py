"""Private historical candidate-decision readback; no publication authority."""
from __future__ import annotations

import json
import re

from dichiarazioni_pubbliche.studio_readonly_db import StudioReadOnlyDb as _StudioReadOnlyDb

_STUDIO_REF = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_CAPTURE_SHA = re.compile(r"^[0-9a-f]{64}$")


class _StudioDecisionReader(_StudioReadOnlyDb):
    """DP418: optional historical PG receipt, never reviewer authorization.

    No schema bootstrap here. Missing additive isolated decision table fails
    503; actual writes require separate signed DP310 reviewer credentials.
    """

    def read_decision(self, *, candidate_id: str, run_id: str, passage_id: str,
                      capture_id: str, request_key: str) -> dict[str, object]:
        for value in (candidate_id, run_id, passage_id, capture_id, request_key):
            if not isinstance(value, str) or not _STUDIO_REF.fullmatch(value) or ".." in value:
                raise ValueError("STUDIO_DECISION_REF_INVALID")
        from dichiarazioni_pubbliche.studio_candidate_decision_sql import READBACK_SQL

        raw = self.run(
            READBACK_SQL, candidate_id=candidate_id, run_id=run_id,
            passage_id=passage_id, capture_id=capture_id, request_key=request_key,
        )
        if not raw:
            raise ValueError("STUDIO_DECISION_NOT_FOUND")
        try:
            row = json.loads(raw)
            expected = {"candidate_id", "run_id", "passage_id", "capture_id",
                        "request_key", "decision", "revision", "receipt_sha256",
                        "source_current"}
            if not isinstance(row, dict) or set(row) != expected:
                raise ValueError
            if any(row[key] != value for key, value in {
                    "candidate_id": candidate_id, "run_id": run_id,
                    "passage_id": passage_id, "capture_id": capture_id,
                    "request_key": request_key}.items()):
                raise ValueError
            if (row["decision"] not in {"HOLD", "REJECT", "REVIEW_CREATE", "REVIEW_LINK"}
                    or type(row["revision"]) is not int or row["revision"] < 1
                    or not isinstance(row["receipt_sha256"], str)
                    or not _CAPTURE_SHA.fullmatch(row["receipt_sha256"])
                    or type(row["source_current"]) is not bool):
                raise ValueError
        except (TypeError, KeyError, ValueError):
            raise ValueError("STUDIO_DECISION_ROW_INVALID") from None
        return {
            "contract_version": "studio-candidate-decision-receipt-v1",
            "private_only": True, "historical_only": True,
            "candidate_id": candidate_id, "run_id": run_id,
            "passage_id": passage_id, "capture_id": capture_id,
            "request_key": request_key,
            "decision": row["decision"], "revision": row["revision"],
            "receipt_sha256": row["receipt_sha256"],
            "status": ("HISTORICAL_SOURCE_CURRENT" if row["source_current"]
                       else "HISTORICAL_SOURCE_WITHDRAWN"),
            "review_authority": False, "promotion_authority": False,
            "publication_authority": False, "rights_clearance": False,
        }
