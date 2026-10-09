"""Explicit, private, append-only Discovery triage annotations (DP-417).

This store is deliberately NOT wired to the read-only local Studio HTTP API.
It records an operator's non-authoritative triage annotation, not approval of
rights, identity, claims, capture, extraction, promotion, or publication.

Each write is one PostgreSQL transaction. A per-Hit transaction advisory lock
serializes cooperating writers before they read the current revision. Database
UNIQUE constraints provide a second fence against conflicting writers.
"""

from __future__ import annotations

import argparse
import json
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.studio_discovery_triage_contract import (
    StudioDiscoveryTriageRequest,
    make_triage_request,
    present_triage_receipt,
)


STUDIO_TRIAGE_STORE_VERSION = "studio-discovery-triage-ledger-v1"

_WRITE_SQL = """
BEGIN;
SET LOCAL lock_timeout = '1000ms';
SET LOCAL statement_timeout = '5000ms';
SELECT pg_advisory_xact_lock(hashtextextended('dp417:hit:' || :'hit_id', 0));
WITH scope AS (
    SELECT hit.id
    FROM research_discovery_hit hit
    JOIN research_discovery_run run ON run.id = hit.run_id
    JOIN research_discovery_manifest manifest ON manifest.id = run.manifest_id
    JOIN research_collection collection ON collection.id = manifest.collection_id
    JOIN research_discovery_attempt attempt
      ON attempt.id = hit.attempt_id
     AND attempt.run_id = run.id AND attempt.query_id = hit.query_id
    JOIN research_discovery_query discovery_query
      ON discovery_query.id = hit.query_id
     AND discovery_query.manifest_id = manifest.id
    WHERE hit.id = :'hit_id' AND collection.id = :'collection_id'
),
existing AS (
    SELECT collection_id, hit_id, request_key, revision,
           expected_revision, decision, payload_sha256, actor_ref,
           attestation_receipt_id
    FROM research_discovery_triage_decision
    WHERE request_key = :'request_key'
),
current_rev AS (
    -- No scope means no revision disclosure for a guessed cross-Collection Hit.
    SELECT coalesce(max(history.revision), 0)::bigint AS revision
    FROM scope
    LEFT JOIN research_discovery_triage_decision history
      ON history.hit_id = scope.id
    GROUP BY scope.id
),
inserted AS (
    INSERT INTO research_discovery_triage_decision
        (collection_id, hit_id, revision, expected_revision, request_key,
         decision, payload_sha256, actor_ref, attestation_receipt_id)
    SELECT :'collection_id', :'hit_id', current_rev.revision + 1,
           :'expected_revision'::bigint, :'request_key',
           :'decision', :'payload_sha256', :'actor_ref',
           NULLIF(:'attestation_receipt_id', '')
    FROM current_rev
    WHERE EXISTS (SELECT 1 FROM scope)
      AND NOT EXISTS (SELECT 1 FROM existing)
      AND current_rev.revision = :'expected_revision'::bigint
    ON CONFLICT DO NOTHING
    RETURNING revision, attestation_receipt_id
),
matched_replay AS (
    SELECT revision, attestation_receipt_id FROM existing
    WHERE collection_id = :'collection_id'
      AND hit_id = :'hit_id'
      AND request_key = :'request_key'
      AND expected_revision = :'expected_revision'::bigint
      AND decision = :'decision'
      AND actor_ref = :'actor_ref'
      AND payload_sha256 = :'payload_sha256'
      AND attestation_receipt_id IS NOT DISTINCT FROM
          NULLIF(:'attestation_receipt_id', '')
)
SELECT json_build_object(
    'result_code', CASE
        WHEN NOT EXISTS (SELECT 1 FROM scope) THEN 'SCOPE_NOT_FOUND'
        WHEN EXISTS (SELECT 1 FROM matched_replay) THEN 'REPLAY'
        WHEN EXISTS (SELECT 1 FROM existing) THEN 'IDEMPOTENCY_CONFLICT'
        WHEN EXISTS (SELECT 1 FROM inserted) THEN 'CREATED'
        ELSE 'REVISION_CONFLICT'
    END,
    'collection_id', :'collection_id',
    'hit_id', :'hit_id',
    'request_key', :'request_key',
    'decision', :'decision',
    'expected_revision', :'expected_revision'::bigint,
    'payload_sha256', :'payload_sha256',
    'signed_receipt_linked', COALESCE(
        (SELECT attestation_receipt_id IS NOT NULL FROM matched_replay),
        (SELECT attestation_receipt_id IS NOT NULL FROM inserted),
        false
    ),
    'revision', coalesce(
        (SELECT revision FROM matched_replay),
        (SELECT revision FROM inserted),
        (SELECT revision FROM current_rev)
    )
)::text;
COMMIT;
""".strip()


class StudioDiscoveryTriageStore(PsqlRuntime):
    """Append-only annotation writer, usable only with explicit DB permission."""

    def record(
        self, *, collection_id: str, hit_id: str, request_key: str,
        decision: str, expected_revision: int, actor_ref: str,
    ) -> dict[str, object]:
        request = make_triage_request(
            collection_id=collection_id, hit_id=hit_id, request_key=request_key,
            decision=decision, expected_revision=expected_revision,
            actor_ref=actor_ref,
        )
        return self._record_request(request, attestation_receipt_id="")

    def _record_request(
        self, request: StudioDiscoveryTriageRequest, *, attestation_receipt_id: str,
    ) -> dict[str, object]:
        # This is a DB primitive, not a reviewer-credential verifier. The
        # signed path must verify the receipt separately before entering it.
        try:
            raw = self.run(
                _WRITE_SQL, collection_id=request.collection_id,
                hit_id=request.hit_id, request_key=request.request_key,
                decision=request.decision, expected_revision=request.expected_revision,
                payload_sha256=request.payload_sha256, actor_ref=request.actor_ref,
                attestation_receipt_id=attestation_receipt_id,
            )
        except Exception:
            # Never relay psql error output: it can include schema and private data.
            raise RuntimeError("STUDIO_TRIAGE_STORE_UNAVAILABLE") from None
        if not isinstance(raw, str) or len(raw) > 6000:
            raise ValueError("STUDIO_TRIAGE_RESULT_INVALID")
        try:
            # psql -qAt emits an empty row for the advisory-lock SELECT.
            lines = [line for line in raw.splitlines() if line.strip()]
            if len(lines) != 1:
                raise ValueError
            parsed = json.loads(lines[0])
        except (ValueError, TypeError, json.JSONDecodeError):
            raise ValueError("STUDIO_TRIAGE_RESULT_INVALID") from None
        if not isinstance(parsed, dict):
            raise ValueError("STUDIO_TRIAGE_RESULT_INVALID")
        allowed = {
            "result_code", "collection_id", "hit_id", "request_key",
            "decision", "expected_revision", "revision", "payload_sha256",
            "signed_receipt_linked",
        }
        if set(parsed) != allowed:
            raise ValueError("STUDIO_TRIAGE_RESULT_INVALID")
        code = parsed["result_code"]
        linked = parsed["signed_receipt_linked"]
        if type(linked) is not bool or (
            code in {"CREATED", "REPLAY"}
            and linked != bool(attestation_receipt_id)
        ):
            raise ValueError("STUDIO_TRIAGE_ATTESTATION_LINK_INVALID")
        try:
            receipt = present_triage_receipt(parsed, request=request)
        except (ValueError, TypeError):
            raise ValueError("STUDIO_TRIAGE_RESULT_INVALID") from None
        return {
            **receipt,
            "store_contract_version": STUDIO_TRIAGE_STORE_VERSION,
            "actor_attested": False,
            "capture_authorized": False,
        }

    def record_attested(
        self, *, authority: object, receipt_id: str,
        collection_id: str, hit_id: str, request_key: str,
        decision: str, expected_revision: int, actor_ref: str,
    ) -> dict[str, object]:
        """Require local, active, HMAC-bound actor proof before a private annotation.

        A credential-bound identity never grants rights clearance, rejection
        of source material, promotion, capture, or publication authority.
        """
        from dichiarazioni_pubbliche.studio_discovery_triage_authority import (
            verify_triage_attestation,
        )
        request = make_triage_request(
            collection_id=collection_id, hit_id=hit_id, request_key=request_key,
            decision=decision, expected_revision=expected_revision,
            actor_ref=actor_ref,
        )
        proof = verify_triage_attestation(authority, request, receipt_id)
        value = self._record_request(
            request, attestation_receipt_id=proof["receipt_id"],
        )
        successful = value["result_code"] in {"CREATED", "REPLAY"}
        return {
            **value,
            "actor_attested": successful,
            "identity_receipt_verified": True,
            "attestation_receipt_id": proof["receipt_id"] if successful else None,
            "triage_action_authorized": False,
            "publication_authority": False,
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Explicit private DB-only Discovery triage annotation. Not a publication decision."
    )
    parser.add_argument("--collection-id", required=True)
    parser.add_argument("--hit-id", required=True)
    parser.add_argument("--request-key", required=True)
    parser.add_argument("--decision", required=True, choices=("NEEDS_REVIEW", "DEFERRED", "REJECTED"))
    parser.add_argument("--expected-revision", required=True, type=int)
    parser.add_argument("--actor-ref", required=True)
    parser.add_argument("--authority-root", required=True,
                        help="Private local reviewer authority root (0700), never in Git.")
    parser.add_argument("--credential-id", required=True,
                        help="Local reviewer credential ID; no secret on the command line.")
    parser.add_argument("--confirm-private-annotation", action="store_true")
    args = parser.parse_args()
    if not args.confirm_private_annotation:
        parser.error("explicit --confirm-private-annotation is required")
    # Connections are inherited from the operator's PG* environment or psql
    # service file; no DSN or credentials are accepted in command arguments.
    from dichiarazioni_pubbliche.reviewer_identity_authority import (
        LocalFileReviewerIdentityAuthority,
    )
    from dichiarazioni_pubbliche.studio_discovery_triage_authority import (
        issue_triage_attestation,
    )
    request = make_triage_request(
        collection_id=args.collection_id, hit_id=args.hit_id,
        request_key=args.request_key, decision=args.decision,
        expected_revision=args.expected_revision, actor_ref=args.actor_ref,
    )
    authority = LocalFileReviewerIdentityAuthority(args.authority_root)
    proof = issue_triage_attestation(authority, request, args.credential_id)
    result = StudioDiscoveryTriageStore().record_attested(
        authority=authority, receipt_id=proof["receipt_id"],
        collection_id=args.collection_id, hit_id=args.hit_id,
        request_key=args.request_key, decision=args.decision,
        expected_revision=args.expected_revision, actor_ref=args.actor_ref,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
