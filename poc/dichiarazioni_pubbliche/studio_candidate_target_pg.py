"""DP-418 independently persisted, metadata-only target source readback.

This private adapter never copies the matcher suggestion into source evidence.
Only an explicit Claim Candidate parent_passage_id backed by its Statement's
real Passage edge can be resolved to an immutable written Content Capture.

Canonical atomic_claim lacks a direct Passage FK: its DP-212 provenance_key
is a canonical segment ID, claim_text_provenance ID, or bare Claim ID rather
than a Passage ID. Returning None is safer than inventing an Atomic source.
No review, source-rights or publication authority is granted here.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime, _clean

_REF = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_HARD_DENY = frozenset({"DENIED", "REVOKED", "EXPIRED"})
_CAPTURE_STATUS = frozenset({"CAPTURED", "PURGED_BODY", "QUARANTINED"})
_CAPTURE_HOLD = frozenset(
    {
        "NONE",
        "RIGHTS_HOLD",
        "PRIVACY_HOLD",
        "COPYRIGHT_HOLD",
        "LEGAL_HOLD",
        "DISPUTE_HOLD",
    }
)

_TARGET_SOURCE_SQL = """
SELECT json_build_object(
    'member_type', 'CLAIM_CANDIDATE',
    'member_id', candidate.id,
    'content_id', content.id,
    'passage_id', passage.id,
    'capture_id', capture.id,
    'capture_sha256', capture.content_sha256,
    'content_rights', content.rights_status,
    'capture_rights', capture.rights_status,
    'capture_status', capture.status,
    'capture_hold_status', capture.hold_status
)::text
FROM claim_candidate candidate
JOIN statement_candidate statement
  ON statement.id=candidate.statement_candidate_id
 AND statement.content_id=candidate.content_id
JOIN statement_candidate_passage edge
  ON edge.statement_candidate_id=statement.id
 AND edge.content_id=statement.content_id
JOIN passage passage
  ON passage.id=edge.passage_id AND passage.content_id=edge.content_id
JOIN content_item content ON content.id=candidate.content_id
JOIN content_capture capture
  ON capture.id=passage.capture_id AND capture.content_id=passage.content_id
WHERE candidate.id=:'member_id'
  AND candidate.metadata->>'parent_passage_id'=passage.id
  AND candidate.status IN ('CANDIDATE', 'PROMOTED')
  AND statement.status IN ('CANDIDATE', 'APPROVED')
  AND passage.selector_type IN ('TEXT_POSITION', 'PAGE_RANGE')
ORDER BY passage.id
LIMIT 2;
""".strip()


def _reference(value: object) -> str:
    if not isinstance(value, str) or not _REF.fullmatch(value):
        raise ValueError("DP418_TARGET_REFERENCE_INVALID")
    return value


class StudioCandidateTargetPg(PsqlRuntime):
    """PostgreSQL reader with a read-only transaction even under a privileged DSN.

    The public method requires no credential or new schema. `run()` also has
    read-only PostgreSQL session settings, preventing writes through this store.
    Instantiate only in an existing authenticated private operator context.
    """

    def run(self, sql: str, **variables: object) -> str:
        args = self._args()
        try:
            for key, value in variables.items():
                args.extend(["-v", f"{key}={_clean(value)}"])
            env = os.environ.copy()
            env["PGOPTIONS"] = (
                env.get("PGOPTIONS", "")
                + " -c default_transaction_read_only=on"
                + " -c statement_timeout=3000"
                + " -c lock_timeout=1000"
            ).strip()
            env["PGCONNECT_TIMEOUT"] = "3"
            process = subprocess.run(
                args,
                input=sql,
                capture_output=True,
                text=True,
                timeout=8,
                env=env,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired, ValueError):
            raise RuntimeError("DP418_TARGET_STORE_UNAVAILABLE") from None
        if process.returncode != 0 or len(process.stdout) > 8_192:
            raise RuntimeError("DP418_TARGET_STORE_UNAVAILABLE") from None
        return process.stdout.strip()

    def source_context(self, member_type: str, member_id: str) -> dict[str, str] | None:
        """Independently re-read one target; absent/ambiguous sources hold.

        A legacy content-rights APPROVED flag is *not* converted into CLEARED.
        Only explicit CLEARED on both current Content and exact Capture may
        expose the state CLEARED; downstream reviewer/publication flags stay
        false regardless. Returns no text, URLs, arbitrary metadata or scores.
        """
        if member_type not in {"CLAIM_CANDIDATE", "ATOMIC_CLAIM"}:
            raise ValueError("DP418_TARGET_TYPE_INVALID")
        member_id = _reference(member_id)
        if member_type == "ATOMIC_CLAIM":
            # Schema has no atomic_claim->passage FK. Even a promotion edge
            # alone cannot establish the DP-212 provenance_key as Passage ID.
            return None
        raw = self.run(_TARGET_SOURCE_SQL, member_id=member_id)
        if not raw:
            return None
        if len(raw) > 6_000:
            raise ValueError("DP418_TARGET_SOURCE_INVALID")
        try:
            rows = [json.loads(line) for line in raw.splitlines()]
        except (ValueError, TypeError):
            raise ValueError("DP418_TARGET_SOURCE_INVALID") from None
        if len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValueError("DP418_TARGET_SOURCE_AMBIGUOUS")
        row: dict[str, Any] = rows[0]
        required = {
            "member_type",
            "member_id",
            "content_id",
            "passage_id",
            "capture_id",
            "capture_sha256",
            "content_rights",
            "capture_rights",
            "capture_status",
            "capture_hold_status",
        }
        if (
            set(row) != required
            or row["member_type"] != member_type
            or row["member_id"] != member_id
        ):
            raise ValueError("DP418_TARGET_SOURCE_INVALID")
        for field in ("content_id", "passage_id", "capture_id"):
            _reference(row[field])
        if not isinstance(row["capture_sha256"], str) or not _SHA.fullmatch(
            row["capture_sha256"]
        ):
            raise ValueError("DP418_TARGET_SOURCE_INVALID")
        if (
            row["capture_status"] not in _CAPTURE_STATUS
            or row["capture_hold_status"] not in _CAPTURE_HOLD
            or not isinstance(row["content_rights"], str)
            or not isinstance(row["capture_rights"], str)
        ):
            # PURGE_PENDING/unknown are unsupported in the consumer contract;
            # never remap into a falsely current `CAPTURED` row.
            return None
        content_rights = row["content_rights"]
        capture_rights = row["capture_rights"]
        if content_rights in _HARD_DENY or capture_rights in _HARD_DENY:
            rights = next(
                state
                for state in ("DENIED", "REVOKED", "EXPIRED")
                if state in {content_rights, capture_rights}
            )
        elif content_rights == capture_rights == "CLEARED":
            rights = "CLEARED"
        else:
            rights = "UNKNOWN"
        return {
            "member_type": member_type,
            "member_id": member_id,
            "content_id": row["content_id"],
            "passage_id": row["passage_id"],
            "capture_id": row["capture_id"],
            "capture_sha256": row["capture_sha256"],
            "rights_status": rights,
            "capture_status": row["capture_status"],
            "capture_hold_status": row["capture_hold_status"],
        }


__all__ = ["StudioCandidateTargetPg"]
