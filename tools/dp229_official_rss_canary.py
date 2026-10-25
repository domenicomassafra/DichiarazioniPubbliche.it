#!/usr/bin/env python3
"""Private, zero-cost DP-228/DP-209 real RSS canary in a disposable local PostgreSQL.

The run never connects to the production database, ingests article bodies,
approves evidence, or creates publication authority. The PostgreSQL directory
is retained (with mode 0700) for a later deterministic receipt readback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.challenger_research import compile_challenger_research_request
from dichiarazioni_pubbliche.claim_research_plan import compile_claim_research_plan
from dichiarazioni_pubbliche.domain_vocabulary import ClaimType
from dichiarazioni_pubbliche.research_discovery import (
    ConfiguredRegistryDiscoveryAdapter,
    ResearchDiscoveryStore,
    run_discovery_manifest,
)
from dichiarazioni_pubbliche.research_plan import discovery_manifest_from_assignments


COLLECTION_ID = "collection:dp229:senato-s1-official-rss"
RUN_ID = "run:dp229:senato-s1:official-camera:20261022"
SOURCE_ID = "official-camera-temi"
QUERY = (
    "Quali fonti istituzionali della Camera chiariscono i limiti e gli sviluppi "
    "della proposta legislativa del Senato S.1 rispetto a una legge vigente?"
)


def binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for path in sorted(Path("/usr/lib/postgresql").glob(f"*/bin/{name}"), reverse=True):
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise RuntimeError(f"DP229_CANARY_MISSING_BINARY:{name}")


def checked(*args: str, stdin: str | None = None) -> str:
    result = subprocess.run(args, text=True, input=stdin, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"DP229_CANARY_COMMAND_FAILED:{args[0]}:{result.returncode}:{result.stderr[:500]}")
    return result.stdout.strip()


def run_case(state: Path) -> dict[str, object]:
    if state.is_symlink():
        raise ValueError("DP229_CANARY_STATE_SYMLINK")
    state.mkdir(parents=True, mode=0o700, exist_ok=True)
    state.chmod(0o700)
    data = state / "pgdata"
    if not data.exists():
        checked(binary("initdb"), "-D", str(data), "--username=postgres",
                "--auth=trust", "--encoding=UTF8", "--no-locale")
    pgctl = binary("pg_ctl")
    # No TCP listener: only the Unix socket inside the private 0700 directory.
    checked(pgctl, "-D", str(data), "-l", str(state / "postgres.log"),
            "-o", f"-F -h '' -k {state}", "-w", "start")
    try:
        database = f"host={state} dbname=postgres user=postgres"
        store = ResearchDiscoveryStore(database)
        schema = ROOT / "db" / "schema.v1.sql"
        schema_hash = hashlib.sha256(schema.read_bytes()).hexdigest()
        schema_marker = state / "schema-applied"
        if not schema_marker.exists():
            checked(binary("psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1",
                    "--dbname", database, "-f", str(schema))
            schema_marker.write_text(schema_hash + "\n")
        else:
            marker = schema_marker.read_text().strip()
            if marker not in {schema_hash, "schema.v1.sql"}:
                raise RuntimeError("DP229_CANARY_SCHEMA_CHANGED")
            if marker != schema_hash:
                schema_marker.write_text(schema_hash + "\n")
        store.run(
            """
            INSERT INTO research_collection (id, slug, name, scope_text, policy_version)
            VALUES (:'collection_id', 'dp229-s1-official-rss', 'DP229 private canary',
                    'Official RSS metadata only; no publication', 'dp229-private-canary-v1')
            ON CONFLICT (id) DO NOTHING;
            """,
            collection_id=COLLECTION_ID,
        )
        # DP-209 requires the exact Coverage Need to be durable and in scope
        # before saving the manifest. Keep this synthetic *assignment* distinct
        # from the real external RSS execution and from canonical fact findings.
        need_id = "coverage:dp229:senato-s1-limitations"
        requirement_fingerprint = hashlib.sha256(
            ("dp229-private-limitations:" + QUERY).encode("utf-8")
        ).hexdigest()
        authority_scope = {"country": "IT", "purpose": "PRIVATE_COUNTERCASE"}
        store.run(
            """
            INSERT INTO coverage_need (
                id, collection_id, need_type, requirement_kind,
                requirement_fingerprint, question, required_roles,
                authority_scope, max_attempts, created_by
            ) VALUES (
                :'need_id', :'collection_id', 'OTHER', 'OTHER',
                :'fingerprint', :'question', '[]'::jsonb,
                :'authority_scope'::jsonb, 1, 'DP229_PRIVATE_CANARY'
            ) ON CONFLICT (id) DO NOTHING;
            """,
            need_id=need_id, collection_id=COLLECTION_ID,
            fingerprint=requirement_fingerprint, question=QUERY,
            authority_scope=json.dumps(authority_scope, sort_keys=True),
        )
        plan = compile_claim_research_plan(
            claim_id="claim:dp229:senato-s1-research-canary",
            claim_type=ClaimType.HISTORICAL_CLAIM,
            coverage_needs=({
                "id": need_id, "collection_id": COLLECTION_ID,
                "need_type": "OTHER", "requirement_kind": "OTHER",
                "requirement_fingerprint": requirement_fingerprint,
                "question": QUERY, "required_roles": [],
                "max_attempts": 1, "attempt_count": 0,
                "authority_scope": authority_scope,
            },),
            lane_adapters={"CHALLENGER": ("configured_registry",)},
            include_challenger=True, max_assignments=1, max_unique_lanes=1,
            max_total_results=2, max_total_cost_usd=Decimal("0"),
            per_assignment_max_results=2, per_assignment_max_results_per_host=1,
            per_assignment_cost_cap_usd=Decimal("0"),
        )
        request = compile_challenger_research_request(
            plan, max_assignments=1, max_total_queries=1,
            max_total_results=2, max_total_cost_usd=Decimal("0"),
        )
        if plan.status != "READY" or request.status != "READY":
            raise RuntimeError(f"DP229_CANARY_REQUEST_BLOCKED:{plan.blockers}:{request.blockers}")
        challenger_rows = tuple(a for a in plan.assignments if a.lane == "CHALLENGER")
        manifest = discovery_manifest_from_assignments(
            challenger_rows, collection_id=COLLECTION_ID,
            lane_source_families={"CHALLENGER": ("public_rss",)},
            seeds=({"kind": "source_id", "value": SOURCE_ID},),
        )
        adapter = ConfiguredRegistryDiscoveryAdapter(ROOT / "config" / "source-registry.v1.json")
        if (len(manifest.queries), request.max_queries, manifest.max_results,
                manifest.max_results_per_host, manifest.cost_cap_usd) != (1, 1, 2, 1, Decimal("0")):
            raise RuntimeError("DP229_CANARY_CAP_WIDENED")
        # Re-running this canary with the same state directory replays a durable
        # attempt. A new observation timestamp must not be mistaken for a new
        # live discovery or a fresh source-rights decision.
        previous_attempts = int(store.run(
            "SELECT count(*)::text FROM research_discovery_attempt WHERE run_id=:'run_id';",
            run_id=RUN_ID,
        ))
        receipt = run_discovery_manifest(
            manifest, store, {"configured_registry": adapter}, run_id=RUN_ID,
        )
        replay = run_discovery_manifest(
            manifest, store, {"configured_registry": adapter}, run_id=RUN_ID,
        )
        if asdict(receipt) != asdict(replay):
            raise RuntimeError("DP229_CANARY_REPLAY_MISMATCH")
        attempts = json.loads(store.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'adapter_id', adapter_id, 'adapter_version', adapter_version,
                'started_at_utc', to_char(started_at AT TIME ZONE 'UTC',
                    'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
                'status', status, 'error_category', error_category,
                'cost_usd', cost_usd, 'cost_upper_bound_usd', cost_upper_bound_usd,
                'raw_hits', raw_hits, 'accepted_hits', accepted_hits
            ) ORDER BY started_at)::text, '[]')
            FROM research_discovery_attempt WHERE run_id=:'run_id';
            """,
            run_id=RUN_ID,
        ))
        if len(attempts) != 1 or attempts[0]["adapter_id"] != adapter.adapter_id:
            raise RuntimeError("DP229_CANARY_ATTEMPT_NOT_PERSISTED")
        return {
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "attempt_started_at_utc": attempts[0]["started_at_utc"],
            "new_healthy_attempt_this_invocation": (
                previous_attempts == 0 and attempts[0]["status"] == "HEALTHY"
            ),
            "run_id": RUN_ID, "plan_id": plan.plan_id,
            "request_id": request.request_id, "manifest_sha256": manifest.manifest_sha256,
            "source_id": SOURCE_ID, "source_family": "public_rss",
            "query_count": len(manifest.queries), "result_cap": 2,
            "host_cap": 1, "cost_cap_usd": "0",
            "run_status": receipt.status, "attempt_count": receipt.attempt_count,
            "healthy_attempts": receipt.healthy_attempts,
            "blocked_attempts": receipt.blocked_attempts,
            "failed_attempts": receipt.failed_attempts,
            "raw_hits": receipt.raw_hits, "accepted_hits": receipt.accepted_hits,
            "observed_cost_usd": str(receipt.cost_usd),
            "attempts": attempts, "readback_replay_equal": True,
            "publication_authority": False, "disposition": "HOLD",
            "privacy": "ONLY_SOURCE_METADATA_IN_LOCAL_PRIVATE_LEDGER",
        }
    finally:
        checked(pgctl, "-D", str(data), "-m", "fast", "-w", "stop")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.state_dir.is_symlink():
        raise ValueError("DP229_CANARY_STATE_SYMLINK")
    receipt = run_case(args.state_dir.resolve())
    text = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2)
    (args.state_dir / "receipt.json").write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
