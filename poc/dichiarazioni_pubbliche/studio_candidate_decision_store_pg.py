"""DP-418: operator-private PostgreSQL CAS for explicitly attested review intent.

Only a real DP-310 off-database review-event receipt can authorize an append.
The current Candidate/MatchRun/Statement/Passage/Capture/right rows are locked
and checked in one transaction. These receipts NEVER promote a Claim or cluster,
grant rights, approve equivalence, or issue publication authority.

The additive private table must be explicitly initialized on an isolated DB;
no production migration or Studio endpoint is introduced by this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass

from dichiarazioni_pubbliche.publication_review_control import (
    PublicationReviewEvent,
    review_event_integrity_valid,
)
from dichiarazioni_pubbliche.publication_review_persistence import (
    identity_attestation_blockers,
)
from dichiarazioni_pubbliche.reviewer_identity_authority import (
    LocalFileReviewerIdentityAuthority,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime, _clean
from dichiarazioni_pubbliche.candidate_matching import deterministic_match_run_id

DECISION_STORE_VERSION = "dp418-private-decision-v1"
_REF = re.compile(r"[A-Za-z0-9_:./-]{1,180}\Z", re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_DECISIONS = frozenset({"HOLD", "REJECT", "REVIEW_CREATE", "REVIEW_LINK"})
_ACTIONS = {
    "HOLD": "SUPERSEDED",
    "REJECT": "REJECTED",
    "REVIEW_CREATE": "APPROVED",
    "REVIEW_LINK": "APPROVED",
}


def _reference(value: object) -> str:
    if not isinstance(value, str) or not _REF.fullmatch(value):
        raise ValueError("DP418_DECISION_REFERENCE_INVALID")
    return value


def _hash(value: object) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError("DP418_DECISION_SHA256_INVALID")
    return value


def _digest(value: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode("ascii")
    ).hexdigest()


@dataclass(frozen=True)
class CandidateDecisionRequest:
    candidate_id: str
    run_id: str
    input_fingerprint: str
    passage_id: str
    capture_id: str
    capture_sha256: str
    request_key: str
    decision: str
    expected_revision: int
    actor_ref: str
    target_type: str = ""
    target_id: str = ""

    @property
    def record_version(self) -> str:
        return DECISION_STORE_VERSION + ":" + self.payload_sha256

    @property
    def payload_sha256(self) -> str:
        return _digest(
            {name: getattr(self, name) for name in self.__dataclass_fields__}
            | {"contract_version": DECISION_STORE_VERSION}
        )


def candidate_decision_request(
    *,
    candidate_id: str,
    run_id: str,
    input_fingerprint: str,
    passage_id: str,
    capture_id: str,
    capture_sha256: str,
    request_key: str,
    decision: str,
    expected_revision: int,
    actor_ref: str,
    target_type: str = "",
    target_id: str = "",
) -> CandidateDecisionRequest:
    for value in (candidate_id, run_id, passage_id, capture_id, request_key, actor_ref):
        _reference(value)
    _hash(input_fingerprint)
    _hash(capture_sha256)
    if (
        decision not in _DECISIONS
        or type(expected_revision) is not int
        or not 0 <= expected_revision < 2**31
    ):
        raise ValueError("DP418_DECISION_REQUEST_INVALID")
    if run_id != deterministic_match_run_id(candidate_id, input_fingerprint):
        raise ValueError("DP418_DECISION_MATCH_RUN_INVALID")
    if decision == "REVIEW_LINK":
        if (
            target_type != "CLAIM_CANDIDATE"
            or not target_id
            or target_id == candidate_id
        ):
            raise ValueError("DP418_DECISION_TARGET_INVALID")
        _reference(target_id)
    elif target_type or target_id:
        raise ValueError("DP418_DECISION_TARGET_INVALID")
    return CandidateDecisionRequest(
        candidate_id,
        run_id,
        input_fingerprint,
        passage_id,
        capture_id,
        capture_sha256,
        request_key,
        decision,
        expected_revision,
        actor_ref,
        target_type,
        target_id,
    )


_INITIALIZE = """
CREATE TABLE IF NOT EXISTS dp418_candidate_decision (
    receipt_id text PRIMARY KEY,
    candidate_id text NOT NULL REFERENCES claim_candidate(id),
    run_id text NOT NULL REFERENCES candidate_match_run(id),
    passage_id text NOT NULL REFERENCES passage(id),
    capture_id text NOT NULL REFERENCES content_capture(id),
    capture_sha256 text NOT NULL CHECK (capture_sha256 ~ '^[0-9a-f]{64}$'),
    input_fingerprint text NOT NULL CHECK (input_fingerprint ~ '^[0-9a-f]{64}$'),
    request_key text NOT NULL UNIQUE,
    revision bigint NOT NULL CHECK (revision > 0),
    expected_revision bigint NOT NULL CHECK (expected_revision >= 0),
    decision text NOT NULL CHECK (decision IN ('HOLD','REJECT','REVIEW_CREATE','REVIEW_LINK')),
    actor_ref text NOT NULL,
    target_type text NOT NULL DEFAULT '',
    target_id text NOT NULL DEFAULT '',
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    authority_receipt_id text NOT NULL,
    authority_event_sha256 text NOT NULL CHECK (authority_event_sha256 ~ '^[0-9a-f]{64}$'),
    receipt_sha256 text NOT NULL CHECK (receipt_sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(candidate_id, revision)
);
CREATE OR REPLACE FUNCTION dp418_decision_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$BEGIN
    RAISE EXCEPTION 'DP418_DECISION_APPEND_ONLY';
END$$;
DROP TRIGGER IF EXISTS dp418_decision_no_change ON dp418_candidate_decision;
CREATE TRIGGER dp418_decision_no_change BEFORE UPDATE OR DELETE ON dp418_candidate_decision
FOR EACH ROW EXECUTE FUNCTION dp418_decision_immutable();
"""

_WRITE_SQL = """
BEGIN;
SET LOCAL lock_timeout = '2000ms';
SET LOCAL statement_timeout = '5000ms';
SELECT pg_advisory_xact_lock(hashtextextended(:'candidate_id', 418));
-- Lock all mutable source/run rows. A second SQL statement observes the
-- committed state after any concurrent rights writer holding these locks.
WITH locked AS (
    SELECT c.id FROM claim_candidate c
    JOIN statement_candidate s ON s.id=c.statement_candidate_id AND s.content_id=c.content_id
    JOIN statement_candidate_passage edge ON edge.statement_candidate_id=s.id
        AND edge.content_id=s.content_id
    JOIN passage p ON p.id=edge.passage_id AND p.content_id=edge.content_id
    JOIN content_capture cap ON cap.id=p.capture_id AND cap.content_id=p.content_id
    JOIN content_item content ON content.id=c.content_id
    JOIN candidate_match_run run ON run.claim_candidate_id=c.id
    WHERE c.id=:'candidate_id' AND run.id=:'run_id'
      AND p.id=:'passage_id' AND cap.id=:'capture_id'
    FOR UPDATE OF c, s, edge, p, cap, content, run
) SELECT count(*) FROM locked;
-- Match results are mutable independent rows; freeze their dispositions and
-- targets until this transaction completes. The Run row lock also blocks a
-- new result FK insert while this decision is evaluated.
WITH locked_results AS (
    SELECT id FROM candidate_match_result WHERE run_id=:'run_id' FOR UPDATE
) SELECT count(*) FROM locked_results;
WITH lineage AS (
    SELECT c.id
    FROM claim_candidate c
    JOIN statement_candidate s ON s.id=c.statement_candidate_id AND s.content_id=c.content_id
    JOIN statement_candidate_passage edge ON edge.statement_candidate_id=s.id
        AND edge.content_id=s.content_id
    JOIN passage p ON p.id=edge.passage_id AND p.content_id=edge.content_id
    JOIN content_capture cap ON cap.id=p.capture_id AND cap.content_id=p.content_id
    JOIN content_item content ON content.id=c.content_id
    JOIN candidate_match_run run ON run.claim_candidate_id=c.id
    WHERE c.id=:'candidate_id' AND c.status='CANDIDATE'
      AND s.status IN ('CANDIDATE','APPROVED')
      AND c.metadata->>'parent_passage_id'=p.id
      AND p.selector_type IN ('TEXT_POSITION','PAGE_RANGE')
      AND p.id=:'passage_id' AND cap.id=:'capture_id'
      AND cap.content_sha256=:'capture_sha256'
      AND content.rights_status='CLEARED' AND cap.rights_status='CLEARED'
      AND cap.hold_status='NONE' AND cap.status='CAPTURED'
      AND run.id=:'run_id' AND run.status='COMPLETED'
      AND run.input_fingerprint=:'input_fingerprint'
      AND run.matching_version='candidate-matching-v1'
      AND run.result_count=(SELECT count(*) FROM candidate_match_result r
                            WHERE r.run_id=run.id)
      AND NOT EXISTS(SELECT 1 FROM candidate_match_result invalid
                     WHERE invalid.run_id=run.id AND (
                         invalid.status <> 'CANDIDATE' OR
                         invalid.matching_version <> run.matching_version))
      AND (:'decision' <> 'REVIEW_CREATE' OR NOT EXISTS(
            SELECT 1 FROM candidate_match_result duplicate
            WHERE duplicate.run_id=run.id AND duplicate.status='CANDIDATE'
              AND duplicate.match_class IN ('DUPLICATE_EXTRACTION','SAME_PROPOSITION')))
      AND (:'decision' <> 'REVIEW_LINK' OR EXISTS(
            SELECT 1 FROM candidate_match_result reviewed
            WHERE reviewed.run_id=run.id AND reviewed.status='CANDIDATE'
              AND reviewed.target_type='CLAIM_CANDIDATE'
              AND reviewed.target_claim_candidate_id=:'target_id'
              AND reviewed.match_class='DUPLICATE_EXTRACTION'
              AND reviewed.matching_version=run.matching_version))
      AND NOT EXISTS (
          SELECT 1 FROM content_capture newer WHERE newer.content_id=c.content_id
            AND (newer.observed_at, newer.id) > (cap.observed_at, cap.id))
), latest AS (
    SELECT COALESCE(MAX(revision),0) AS revision FROM dp418_candidate_decision
    WHERE candidate_id=:'candidate_id'
), previous AS (
    SELECT * FROM dp418_candidate_decision WHERE request_key=:'request_key'
), inserted AS (
    INSERT INTO dp418_candidate_decision (
      receipt_id,candidate_id,run_id,passage_id,capture_id,capture_sha256,
      input_fingerprint,request_key,revision,expected_revision,decision,actor_ref,
      payload_sha256,authority_receipt_id,authority_event_sha256,receipt_sha256,
      target_type,target_id)
    SELECT :'receipt_id', :'candidate_id', :'run_id', :'passage_id', :'capture_id',
      :'capture_sha256', :'input_fingerprint', :'request_key', latest.revision+1,
      :'expected_revision'::bigint, :'decision', :'actor_ref', :'payload_sha256',
      :'authority_receipt_id', :'authority_event_sha256', :'receipt_sha256',
      :'target_type', :'target_id'
    FROM lineage, latest WHERE latest.revision=:'expected_revision'::bigint
      AND NOT EXISTS(SELECT 1 FROM previous)
    ON CONFLICT DO NOTHING RETURNING revision, receipt_sha256
)
SELECT json_build_object(
  'result_code', CASE
    WHEN NOT EXISTS (SELECT 1 FROM lineage) THEN 'HELD_SOURCE'
    WHEN EXISTS(SELECT 1 FROM previous WHERE payload_sha256=:'payload_sha256'
        AND authority_receipt_id=:'authority_receipt_id'
        AND authority_event_sha256=:'authority_event_sha256'
        AND receipt_sha256=:'receipt_sha256') THEN 'REPLAY'
    WHEN EXISTS(SELECT 1 FROM previous) THEN 'IDEMPOTENCY_CONFLICT'
    WHEN EXISTS(SELECT 1 FROM inserted) THEN 'CREATED'
    ELSE 'REVISION_CONFLICT'
  END,
  'revision', COALESCE((SELECT revision FROM inserted),
       (SELECT revision FROM previous), (SELECT revision FROM latest)),
  'receipt_sha256', COALESCE((SELECT receipt_sha256 FROM inserted),
       (SELECT receipt_sha256 FROM previous))
)::text;
COMMIT;
"""

_READ_SQL = """
SELECT json_build_object(
  'candidate_id',candidate_id,'run_id',run_id,'passage_id',passage_id,
  'capture_id',capture_id,'decision',decision,'revision',revision,
  'receipt_sha256',receipt_sha256,'authority_receipt_id',authority_receipt_id,
  'request_key',request_key,'target_type',target_type,'target_id',target_id
)::text FROM dp418_candidate_decision
WHERE candidate_id=:'candidate_id' AND request_key=:'request_key';
"""


class StudioCandidateDecisionStorePg(PsqlRuntime):
    def run(self, sql: str, **variables: object) -> str:
        args = self._args()
        for key, value in variables.items():
            args.extend(["-v", f"{key}={_clean(value)}"])
        env = os.environ.copy()
        env["PGCONNECT_TIMEOUT"] = "3"
        try:
            process = subprocess.run(
                args,
                input=sql,
                text=True,
                capture_output=True,
                timeout=10,
                env=env,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("DP418_DECISION_STORE_UNAVAILABLE") from None
        if process.returncode or len(process.stdout) > 8192:
            raise RuntimeError("DP418_DECISION_STORE_UNAVAILABLE") from None
        return process.stdout.strip()

    def initialize(self) -> None:
        """Opt-in local schema provision; caller controls isolated PG DB."""
        self.run(_INITIALIZE)

    def record(
        self,
        request: CandidateDecisionRequest,
        *,
        authority: LocalFileReviewerIdentityAuthority | None,
        review_event: PublicationReviewEvent | None,
        authority_receipt_id: str | None,
        credential_id: str | None = None,
    ) -> dict[str, object]:
        if type(request) is not CandidateDecisionRequest:
            raise ValueError("DP418_DECISION_REQUEST_INVALID")
        checked = candidate_decision_request(
            **{name: getattr(request, name) for name in request.__dataclass_fields__}
        )
        if (
            type(authority) is not LocalFileReviewerIdentityAuthority
            or not isinstance(review_event, PublicationReviewEvent)
            or not isinstance(authority_receipt_id, str)
            or not isinstance(credential_id, str)
        ):
            return {"result_code": "HELD_AUTHORITY", "promotion_authority": False}
        try:
            credential = authority.identity(credential_id, require_active=True)
            attestation = authority.resolve(authority_receipt_id)
            if (
                not review_event_integrity_valid(review_event)
                or identity_attestation_blockers(review_event, attestation)
                or attestation is None
                or attestation.receipt_id != authority_receipt_id
                or review_event.actor_ref != credential.actor_ref
                or review_event.credential_fingerprint
                != credential.credential_fingerprint
                or review_event.record_id != "dp418:" + checked.candidate_id
                or review_event.record_version != checked.record_version
                or review_event.role != "DECISION_REVIEWER"
                or review_event.stage != "PRIMARY"
                or review_event.action != _ACTIONS[checked.decision]
            ):
                return {"result_code": "HELD_AUTHORITY", "promotion_authority": False}
        except (ValueError, OSError, TypeError):
            return {"result_code": "HELD_AUTHORITY", "promotion_authority": False}
        receipt_sha256 = _digest(
            {
                "payload": checked.payload_sha256,
                "authority_receipt": authority_receipt_id,
                "authority_event": review_event.integrity_sha256,
                "contract": DECISION_STORE_VERSION,
            }
        )
        raw = self.run(
            _WRITE_SQL,
            **{name: getattr(checked, name) for name in checked.__dataclass_fields__},
            receipt_id="dp418-decision:" + receipt_sha256,
            payload_sha256=checked.payload_sha256,
            authority_receipt_id=authority_receipt_id,
            authority_event_sha256=review_event.integrity_sha256,
            receipt_sha256=receipt_sha256,
        )
        try:
            lines = [
                json.loads(line) for line in raw.splitlines() if line.startswith("{")
            ]
            if len(lines) != 1 or set(lines[0]) != {
                "result_code",
                "revision",
                "receipt_sha256",
            }:
                raise ValueError
            result = lines[0]
            if result["result_code"] not in {
                "CREATED",
                "REPLAY",
                "HELD_SOURCE",
                "REVISION_CONFLICT",
                "IDEMPOTENCY_CONFLICT",
            }:
                raise ValueError
            if (
                result["result_code"] in {"CREATED", "REPLAY"}
                and result["receipt_sha256"] != receipt_sha256
            ):
                raise ValueError
            if type(result["revision"]) is not int:
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise ValueError("DP418_DECISION_RESULT_INVALID") from None
        return {
            **result,
            "promotion_authority": False,
            "publication_authority": False,
            "equivalence_approved": False,
        }

    def read(self, candidate_id: str, request_key: str) -> dict[str, object] | None:
        """Read historical decision, never a current source or authority permit."""
        raw = self.run(
            _READ_SQL,
            candidate_id=_reference(candidate_id),
            request_key=_reference(request_key),
        )
        if not raw:
            return None
        try:
            row = json.loads(raw)
            if (
                not isinstance(row, dict)
                or set(row)
                != {
                    "candidate_id",
                    "run_id",
                    "passage_id",
                    "capture_id",
                    "decision",
                    "revision",
                    "receipt_sha256",
                    "authority_receipt_id",
                    "request_key",
                    "target_type",
                    "target_id",
                }
                or row["candidate_id"] != candidate_id
                or row["request_key"] != request_key
                or row["decision"] not in _DECISIONS
                or type(row["revision"]) is not int
                or row["revision"] < 1
            ):
                raise ValueError
            _hash(row["receipt_sha256"])
            for key in ("run_id", "passage_id", "capture_id", "authority_receipt_id"):
                _reference(row[key])
            if row["decision"] == "REVIEW_LINK":
                if row["target_type"] != "CLAIM_CANDIDATE":
                    raise ValueError
                _reference(row["target_id"])
            elif row["target_type"] or row["target_id"]:
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise ValueError("DP418_DECISION_READ_INVALID") from None
        return {
            **row,
            "historical_only": True,
            "promotion_authority": False,
            "publication_authority": False,
            "equivalence_approved": False,
        }


__all__ = [
    "CandidateDecisionRequest",
    "StudioCandidateDecisionStorePg",
    "candidate_decision_request",
    "DECISION_STORE_VERSION",
]
