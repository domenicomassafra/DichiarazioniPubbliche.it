"""Atomic, intentionally paused DP-214 collection scaffold from existing claims.

This writes *only* a Research Collection plus links to the 18 previously
persisted, uniquely linked historical Content records. It never fetches a URL,
sets rights, creates a Capture/Passage/Claim, or changes public data.

The live database must match the exact read-only inventory. In particular
30 distinct claim IDs, 18 distinct Content IDs, UNKNOWN rights and zero
preexisting capture/passages are required. Concurrent drift fails closed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass

from dichiarazioni_pubbliche.garlasco_pilot_inventory import build_live_inventory
from dichiarazioni_pubbliche.studio_local_api import _StudioReadOnlyDb

GARLASCO_SEED_CONTRACT_VERSION = "garlasco-existing-claim-collection-seed-v1"
GARLASCO_SEED_COLLECTION = "research:garlasco"
_SHA = re.compile(r"^[0-9a-f]{64}$")

# Every statement runs inside one atomic transaction. A paused, baseline-only
# collection must never be mistaken for the accepted 100-item pilot.
_SEED_SQL = r"""
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL statement_timeout = '8s';
SET LOCAL lock_timeout = '1s';
SELECT pg_advisory_xact_lock(hashtext('DP214:paused:garlasco:existing-claim-seed'));
LOCK TABLE atomic_claim, content_item IN SHARE MODE NOWAIT;
SELECT set_config('dp.garlasco.expected_items', :'expected_items', true);
SELECT set_config('dp.garlasco.expected_claims', :'expected_claims', true);
SELECT set_config('dp.garlasco.pre_public_findings', :'pre_public_findings', true);

DO $seed_preflight$
DECLARE
    supplied_items jsonb := current_setting('dp.garlasco.expected_items')::jsonb;
    supplied_claims jsonb := current_setting('dp.garlasco.expected_claims')::jsonb;
BEGIN
    IF jsonb_typeof(supplied_items) <> 'array'
        OR jsonb_typeof(supplied_claims) <> 'array'
        OR jsonb_array_length(supplied_items) <> 18
        OR jsonb_array_length(supplied_claims) <> 30
    THEN
        RAISE EXCEPTION 'DP214_BASELINE_SHAPE_MISMATCH';
    END IF;
    IF (SELECT count(*) FROM atomic_claim WHERE id LIKE 'claim:garlasco:%') <> 30
       OR (SELECT count(DISTINCT id) FROM atomic_claim WHERE id LIKE 'claim:garlasco:%') <> 30
       OR (SELECT count(DISTINCT content_id) FROM atomic_claim WHERE id LIKE 'claim:garlasco:%') <> 18
       OR (SELECT count(*) FROM (
           SELECT DISTINCT id FROM atomic_claim WHERE id LIKE 'claim:garlasco:%'
           EXCEPT
           SELECT value #>> '{}' FROM jsonb_array_elements(supplied_claims)
       ) missing) <> 0
       OR (SELECT count(*) FROM (
           SELECT value #>> '{}' AS claim_id FROM jsonb_array_elements(supplied_claims)
           EXCEPT
           SELECT id FROM atomic_claim WHERE id LIKE 'claim:garlasco:%'
       ) extra) <> 0
    THEN
        RAISE EXCEPTION 'DP214_BASELINE_CLAIM_SET_DRIFT';
    END IF;
    IF EXISTS (
        SELECT 1 FROM (
          SELECT DISTINCT c.id, c.canonical_url, c.source_id, c.rights_status
          FROM atomic_claim ac JOIN content_item c ON c.id=ac.content_id
          WHERE ac.id LIKE 'claim:garlasco:%'
        ) live FULL OUTER JOIN jsonb_to_recordset(supplied_items)
          AS requested(id text, canonical_url text, source_id text, rights_status text)
          ON live.id=requested.id
          AND live.canonical_url=requested.canonical_url
          AND live.source_id=requested.source_id
          AND live.rights_status=requested.rights_status
        WHERE live.id IS NULL OR requested.id IS NULL
           OR live.rights_status <> 'UNKNOWN'
    ) THEN
        RAISE EXCEPTION 'DP214_BASELINE_CONTENT_IDENTITY_OR_RIGHTS_DRIFT';
    END IF;
    IF (SELECT count(*) FROM content_capture cc
        WHERE cc.content_id IN (SELECT content_id FROM atomic_claim WHERE id LIKE 'claim:garlasco:%')) <> 0
       OR (SELECT count(*) FROM passage p
        WHERE p.content_id IN (SELECT content_id FROM atomic_claim WHERE id LIKE 'claim:garlasco:%')) <> 0
    THEN
        RAISE EXCEPTION 'DP214_BASELINE_ALREADY_PROCESSED';
    END IF;
    IF EXISTS (SELECT 1 FROM research_collection WHERE slug='garlasco' AND id<>'research:garlasco')
    THEN
        RAISE EXCEPTION 'DP214_COLLECTION_SLUG_CONFLICT';
    END IF;
    IF EXISTS (SELECT 1 FROM research_collection WHERE id='research:garlasco'
        AND (slug <> 'garlasco' OR name <> 'Garlasco — corpus privato'
            OR scope_text <> 'Baseline storica: 30 claim, 18 contenuti. Raccolta sospesa, diritti e discovery da verificare.'
            OR status <> 'PAUSED'
            OR policy_version <> 'garlasco-existing-claim-collection-seed-v1'
            OR metadata <> '{"pilot_ready":false,"review_required":true,"source":"historical-claim-content-only","rights_clearance":false,"capture_authorized":false}'::jsonb))
    THEN
        RAISE EXCEPTION 'DP214_COLLECTION_AUTHORITY_CONFLICT';
    END IF;
    IF EXISTS (
        SELECT 1 FROM research_collection_content existing
        WHERE existing.collection_id='research:garlasco'
          AND (
            existing.status <> 'INCLUDED' OR
            existing.inclusion_method <> 'EXISTING_CLAIM_BASELINE' OR
            existing.inclusion_version <> 'garlasco-existing-claim-collection-seed-v1' OR
            existing.metadata <> '{"capture_authorized":false,"research_only":true,"rights_clearance":false}'::jsonb OR
            existing.content_id NOT IN (
                SELECT content_id FROM atomic_claim WHERE id LIKE 'claim:garlasco:%'
            )
          )
    ) THEN
        RAISE EXCEPTION 'DP214_COLLECTION_MEMBERSHIP_AUTHORITY_CONFLICT';
    END IF;
END
$seed_preflight$;

INSERT INTO research_collection
    (id, slug, name, scope_text, status, policy_version, metadata)
VALUES (
    'research:garlasco', 'garlasco', 'Garlasco — corpus privato',
    'Baseline storica: 30 claim, 18 contenuti. Raccolta sospesa, diritti e discovery da verificare.',
    'PAUSED', 'garlasco-existing-claim-collection-seed-v1',
    '{"pilot_ready":false,"review_required":true,"source":"historical-claim-content-only","rights_clearance":false,"capture_authorized":false}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO research_collection_content
    (collection_id, content_id, inclusion_method, inclusion_version, status, rationale, metadata)
SELECT
    'research:garlasco', historical.content_id,
    'EXISTING_CLAIM_BASELINE', 'garlasco-existing-claim-collection-seed-v1',
    'INCLUDED', 'Historical link only. Acquisition, rights, extraction and publication NOT approved.',
    '{"capture_authorized":false,"research_only":true,"rights_clearance":false}'::jsonb
FROM (SELECT DISTINCT content_id FROM atomic_claim WHERE id LIKE 'claim:garlasco:%') historical
ON CONFLICT (collection_id,content_id) DO NOTHING;

DO $seed_postflight$
BEGIN
    IF (SELECT count(*) FROM research_collection WHERE id='research:garlasco' AND status='PAUSED') <> 1
       OR (SELECT count(*) FROM research_collection_content WHERE collection_id='research:garlasco') <> 18
       OR (SELECT count(*) FROM research_collection_content WHERE collection_id='research:garlasco' AND status='INCLUDED') <> 18
       OR (SELECT count(*) FROM atomic_claim WHERE id LIKE 'claim:garlasco:%') <> 30
       OR (SELECT count(*) FROM finding WHERE publication_status='PUBLISH')
          <> current_setting('dp.garlasco.pre_public_findings')::integer
    THEN
        RAISE EXCEPTION 'DP214_SEED_POSTFLIGHT_MISMATCH';
    END IF;
END
$seed_postflight$;

SELECT json_build_object(
    'collection_id','research:garlasco',
    'status',(SELECT status FROM research_collection WHERE id='research:garlasco'),
    'linked_historical_content',(SELECT count(*) FROM research_collection_content WHERE collection_id='research:garlasco' AND status='INCLUDED'),
    'baseline_claims',(SELECT count(*) FROM atomic_claim WHERE id LIKE 'claim:garlasco:%'),
    'publication_authority',false,
    'capture_authorized',false,
    'pilot_complete',false
)::text;
COMMIT;
""".strip()


@dataclass(frozen=True)
class SeedResult:
    status: str
    receipt: dict[str, object]


def prepare_seed_variables(inventory: object, *, expected_sha: str) -> dict[str, str]:
    """Validate exact immutable expected baseline before opening a write TX."""
    if not isinstance(expected_sha, str) or not _SHA.fullmatch(expected_sha):
        raise ValueError("DP214_SEED_SHA_INVALID")
    receipt = inventory.receipt()
    if receipt["seed_sha256"] != expected_sha:
        raise ValueError("DP214_SEED_SHA_MISMATCH")
    if (
        receipt["baseline_claims"] != 30 or receipt["seed_items"] != 18
        or receipt["counts"]["claims"] != 30
        or receipt["counts"]["linked_claims"] != 30
        or receipt["counts"]["collection_rows"] not in {0, 1}
        or receipt["counts"]["collection_members"] not in {0, 18}
        or receipt["counts"]["captures"] != 0
        or receipt["counts"]["passages"] != 0
        or any(item.rights_status != "UNKNOWN" for item in inventory.seed_manifest.items)
    ):
        raise ValueError("DP214_SEED_PRECONDITIONS_NOT_MET")
    sources = dict(inventory.source_bindings)
    if len(sources) != 18:
        raise ValueError("DP214_SEED_SOURCE_BINDINGS_MISSING")
    items = [
        {
            "id": item.item_id, "canonical_url": item.canonical_url,
            "source_id": sources[item.item_id],
            "rights_status": item.rights_status,
        }
        for item in inventory.seed_manifest.items
    ]
    return {
        "expected_items": json.dumps(items, ensure_ascii=False, separators=(",", ":")),
        "expected_claims": json.dumps(list(inventory.seed_manifest.baseline_claim_ids), separators=(",", ":")),
        "pre_public_findings": str(receipt["counts"]["public_findings"]),
    }


def apply_paused_seed(
    reader: _StudioReadOnlyDb, *, expected_sha: str, rollback_test: bool = False
) -> SeedResult:
    inventory = build_live_inventory(reader)
    variables = prepare_seed_variables(inventory, expected_sha=expected_sha)
    cmd = ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1"]
    for key, value in variables.items():
        cmd.extend(["-v", f"{key}={value}"])
    env = os.environ.copy()
    env["PGCONNECT_TIMEOUT"] = "3"
    env["PGOPTIONS"] = (
        env.get("PGOPTIONS", "")
        + " -c statement_timeout=8000 -c lock_timeout=1000"
    ).strip()
    script = _SEED_SQL
    if rollback_test:
        if not script.endswith("COMMIT;"):
            raise RuntimeError("DP214_SEED_TRANSACTION_SCRIPT_INVALID")
        script = script[:-len("COMMIT;")] + "ROLLBACK;"
    try:
        run = subprocess.run(
            cmd, input=script, text=True, capture_output=True,
            env=env, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("DP214_SEED_DB_UNAVAILABLE") from None
    if run.returncode != 0:
        raise RuntimeError("DP214_SEED_TRANSACTION_REJECTED") from None
    lines = [line for line in run.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("DP214_SEED_RECEIPT_MISSING")
    try:
        payload = next(json.loads(line) for line in lines if line.strip().startswith("{"))
    except (ValueError, StopIteration):
        raise RuntimeError("DP214_SEED_RECEIPT_INVALID") from None
    if (
        payload.get("collection_id") != GARLASCO_SEED_COLLECTION
        or payload.get("status") != "PAUSED"
        or payload.get("linked_historical_content") != 18
        or payload.get("baseline_claims") != 30
        or payload.get("publication_authority") is not False
        or payload.get("capture_authorized") is not False
        or payload.get("pilot_complete") is not False
    ):
        raise RuntimeError("DP214_SEED_RECEIPT_CONFLICT")
    return SeedResult(
        "ROLLBACK_TEST_PASSED" if rollback_test else "PAUSED_PRIVATE_BASELINE_ONLY", payload
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-time private, paused Garlasco baseline seed")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true", help="Allow exact controlled DB transaction")
    group.add_argument("--rollback-test", action="store_true", help="Exercise real DB transaction and ROLLBACK")
    parser.add_argument("--expected-seed-sha", required=True)
    args = parser.parse_args(argv)
    try:
        reader = _StudioReadOnlyDb()
        inventory = build_live_inventory(reader)
        prepare_seed_variables(inventory, expected_sha=args.expected_seed_sha)
        if not args.apply and not args.rollback_test:
            print(json.dumps({
                "status": "DRY_RUN_PAUSED_SEED_ELIGIBLE",
                "seed_sha256": inventory.receipt()["seed_sha256"],
                "collection_status_if_applied": "PAUSED",
                "linked_historical_content_if_applied": 18,
                "publication_authority": False,
                "capture_authorized": False,
                "pilot_complete": False,
            }, sort_keys=True))
            return 0
        result = apply_paused_seed(
            reader, expected_sha=args.expected_seed_sha, rollback_test=args.rollback_test
        )
    except (ValueError, RuntimeError):
        print(json.dumps({"status": "BLOCKED", "reason_code": "DP214_SEED_PRECONDITION_OR_TRANSACTION_REFUSED"}))
        return 2
    print(json.dumps({"execution_status": result.status, **result.receipt}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
