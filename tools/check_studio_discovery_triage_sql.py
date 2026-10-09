#!/usr/bin/env python3
"""DP-417: exercise actual append-only CAS SQL using pg_temp and ROLLBACK only.

No migration is applied and no real Discovery, Content or review rows change.
The script emits SQL with synthetic, private-safe IDs; run it through psql on
the operator DB or use --sql to inspect the exact test transaction.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime  # noqa: E402
from dichiarazioni_pubbliche.studio_discovery_triage_contract import (  # noqa: E402
    make_triage_request,
)
from dichiarazioni_pubbliche.studio_discovery_triage_store import _WRITE_SQL  # noqa: E402

_FIXTURE = """
BEGIN;
SET LOCAL search_path TO pg_temp, public;
SET LOCAL statement_timeout = '5000ms';
CREATE TEMP TABLE research_collection (id text PRIMARY KEY);
CREATE TEMP TABLE research_discovery_manifest (
    id text PRIMARY KEY, collection_id text NOT NULL REFERENCES research_collection(id));
CREATE TEMP TABLE research_discovery_run (
    id text PRIMARY KEY, manifest_id text NOT NULL REFERENCES research_discovery_manifest(id));
CREATE TEMP TABLE research_discovery_query (
    id text PRIMARY KEY, manifest_id text NOT NULL REFERENCES research_discovery_manifest(id));
CREATE TEMP TABLE research_discovery_attempt (
    id text PRIMARY KEY, run_id text NOT NULL REFERENCES research_discovery_run(id),
    query_id text NOT NULL REFERENCES research_discovery_query(id));
CREATE TEMP TABLE research_discovery_hit (
    id text PRIMARY KEY, run_id text NOT NULL REFERENCES research_discovery_run(id),
    attempt_id text NOT NULL REFERENCES research_discovery_attempt(id),
    query_id text NOT NULL REFERENCES research_discovery_query(id));
CREATE TEMP TABLE research_discovery_triage_decision (
    collection_id text NOT NULL,
    hit_id text NOT NULL REFERENCES research_discovery_hit(id),
    revision bigint NOT NULL CHECK (revision > 0),
    expected_revision bigint NOT NULL CHECK (expected_revision >= 0),
    request_key text NOT NULL UNIQUE,
    decision text NOT NULL CHECK (decision IN ('NEEDS_REVIEW','DEFERRED','REJECTED')),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    actor_ref text NOT NULL,
    attestation_receipt_id text UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (hit_id, revision)
);
INSERT INTO research_collection VALUES ('research:fixture');
INSERT INTO research_discovery_manifest VALUES ('manifest:fixture','research:fixture');
INSERT INTO research_discovery_run VALUES ('run:fixture','manifest:fixture');
INSERT INTO research_discovery_query VALUES ('query:fixture','manifest:fixture');
INSERT INTO research_discovery_attempt VALUES ('attempt:fixture','run:fixture','query:fixture');
INSERT INTO research_discovery_hit VALUES
    ('hit:fixture','run:fixture','attempt:fixture','query:fixture');
""".strip()


def _scenario(*, request_key: str, decision: str, expected_revision: int,
              collection_id: str = "research:fixture") -> str:
    request = make_triage_request(
        collection_id=collection_id, hit_id="hit:fixture",
        request_key=request_key, decision=decision, expected_revision=expected_revision,
        actor_ref="operator:fixture-unattested",
    )
    # All interpolation happens through psql's :'name' safely quoted bind
    # values. The fixture IDs are strictly allowlisted by make_triage_request.
    vars_sql = "\n".join(
        f"\\set {key} {getattr(request, key)}"
        for key in ("collection_id", "hit_id", "request_key", "decision",
                    "expected_revision", "payload_sha256", "actor_ref")
    )
    vars_sql += "\n\\set attestation_receipt_id ''"
    body = _WRITE_SQL.removeprefix("BEGIN;").removesuffix("COMMIT;").strip()
    return vars_sql + "\n" + body


def synthetic_triage_sql() -> str:
    scenarios = (
        ("request:one", "NEEDS_REVIEW", 0, "research:fixture"),
        ("request:one", "NEEDS_REVIEW", 0, "research:fixture"),
        ("request:one", "DEFERRED", 0, "research:fixture"),
        ("request:two", "DEFERRED", 0, "research:fixture"),
        ("request:two", "DEFERRED", 1, "research:fixture"),
        ("request:three", "REJECTED", 1, "research:fixture"),
        ("request:four", "NEEDS_REVIEW", 2, "research:absent"),
    )
    statements = [_FIXTURE]
    statements.extend(_scenario(
        request_key=key, decision=decision, expected_revision=revision,
        collection_id=collection,
    ) for key, decision, revision, collection in scenarios)
    statements.append("SELECT 'DP417_TEMP_COUNT=' || count(*)::text FROM research_discovery_triage_decision;")
    statements.append("ROLLBACK;")
    return "\n".join(statements) + "\n"


def evaluate_triage_canary(output: str) -> dict[str, object]:
    results = []
    count = None
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("DP417_TEMP_COUNT="):
            count = int(line.split("=", 1)[1])
            continue
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            raise RuntimeError("STUDIO_TRIAGE_CANARY_UNEXPECTED_OUTPUT") from None
        if not isinstance(result, dict):
            raise RuntimeError("STUDIO_TRIAGE_CANARY_UNEXPECTED_OUTPUT")
        results.append(result)
    expected = (
        ("CREATED", 1), ("REPLAY", 1), ("IDEMPOTENCY_CONFLICT", 1),
        ("REVISION_CONFLICT", 1), ("CREATED", 2),
        ("REVISION_CONFLICT", 2), ("SCOPE_NOT_FOUND", None),
    )
    actual = tuple((result.get("result_code"), result.get("revision"))
                   for result in results)
    if actual != expected or count != 2:
        raise RuntimeError("STUDIO_TRIAGE_CANARY_CAS_OR_REPLAY_FAILED")
    if any(result.get("collection_id") not in {"research:fixture", "research:absent"}
           or result.get("hit_id") != "hit:fixture" for result in results):
        raise RuntimeError("STUDIO_TRIAGE_CANARY_SCOPE_INVALID")
    return {
        "status": "PASS_PG_TEMP_ROLLBACK",
        "scenarios": len(results),
        "expected_results": [r[0] for r in expected],
        "temporary_rows_at_rollback": count,
        "production_rows_modified": 0,
        "publication_authority": False,
    }


def main() -> int:
    if "--sql" in sys.argv:
        print(synthetic_triage_sql(), end="")
        return 0
    try:
        output = PsqlRuntime().run(synthetic_triage_sql())
        print(json.dumps(evaluate_triage_canary(output), sort_keys=True))
    except Exception:
        # Do not print potentially sensitive psql errors or connection details.
        raise SystemExit("STUDIO_TRIAGE_PG_TEMP_CANARY_FAILED") from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
