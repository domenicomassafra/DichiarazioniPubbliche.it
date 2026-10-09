"""DP-417: scoped, bounded, read-only inspection of private triage annotations.

Annotations are not review authority and MUST NOT authorize downstream actions.
This reader returns no operator identity, free text, URL, query or source body.
"""

from __future__ import annotations

import json
from typing import Any

from dichiarazioni_pubbliche.studio_discovery_triage_contract import (
    TRIAGE_DECISIONS,
    _validated_ref,
    _validated_revision,
)

TRIAGE_HISTORY_VERSION = "studio-discovery-triage-history-v1"

_TRIAGE_HISTORY_SQL = """
WITH scoped_hit AS (
    SELECT hit.id, COALESCE(
        attempt.run_id=run.id AND attempt.query_id=hit.query_id
        AND discovery_query.manifest_id=manifest.id, false
    ) AS lineage_ok
    FROM research_discovery_hit hit
    JOIN research_discovery_run run ON run.id=hit.run_id
    JOIN research_discovery_manifest manifest ON manifest.id=run.manifest_id
    LEFT JOIN research_discovery_attempt attempt ON attempt.id=hit.attempt_id
    LEFT JOIN research_discovery_query discovery_query ON discovery_query.id=hit.query_id
    WHERE hit.id=:'hit_id' AND manifest.collection_id=:'collection_id'
),
selected AS (
    SELECT history.revision, history.expected_revision, history.decision
    FROM research_discovery_triage_decision history
    JOIN scoped_hit hit ON hit.id=history.hit_id AND hit.lineage_ok
    WHERE history.collection_id=:'collection_id'
      AND history.revision > :'after_revision'::bigint
    ORDER BY history.revision ASC
    LIMIT :'limit'::integer
)
SELECT json_build_object(
    'collection_id', :'collection_id',
    'hit_id', hit.id, 'lineage_ok', hit.lineage_ok,
    'head_revision', (
        SELECT coalesce(max(history.revision),0)
        FROM research_discovery_triage_decision history
        WHERE history.hit_id=hit.id AND history.collection_id=:'collection_id'
          AND hit.lineage_ok
    ),
    'ledger_count', (
        SELECT count(*)
        FROM research_discovery_triage_decision history
        WHERE history.hit_id=hit.id AND history.collection_id=:'collection_id'
          AND hit.lineage_ok
    ),
    'decisions', (
        SELECT coalesce(
            json_agg(json_build_object(
                'revision', selected.revision,
                'expected_revision', selected.expected_revision,
                'decision', selected.decision
            ) ORDER BY selected.revision ASC),
            '[]'::json
        )
        FROM selected
    )
)::text
FROM scoped_hit hit;
""".strip()


def _present(row: dict[str, Any], *, collection_id: str, hit_id: str,
             limit: int, after_revision: int) -> dict[str, object]:
    if row.get("collection_id") != collection_id or row.get("hit_id") != hit_id:
        raise ValueError("STUDIO_TRIAGE_HISTORY_SCOPE_MISMATCH")
    lineage_ok = row.get("lineage_ok")
    if type(lineage_ok) is not bool:
        raise ValueError("STUDIO_TRIAGE_HISTORY_LINEAGE_INVALID")
    head_revision = _validated_revision(row.get("head_revision"))
    ledger_count = _validated_revision(row.get("ledger_count"))
    # Revisions start at one and each insertion must increment by one. MAX()
    # alone hides deleted or missing rows outside the requested page.
    if ledger_count != head_revision:
        raise ValueError("STUDIO_TRIAGE_HISTORY_LEDGER_INCOMPLETE")
    decisions = row.get("decisions")
    # Failed Hit -> Attempt -> Query lineage must not disclose old annotations,
    # including their count/head, even if the ledger's Collection ID matches.
    if not lineage_ok and (head_revision != 0 or ledger_count != 0 or decisions != []):
        raise ValueError("STUDIO_TRIAGE_HISTORY_LINEAGE_DISCLOSURE")
    visible_count = min(limit, max(head_revision - after_revision, 0))
    if not isinstance(decisions, list) or len(decisions) != visible_count:
        raise ValueError("STUDIO_TRIAGE_HISTORY_LIMIT_INVALID")
    output: list[dict[str, object]] = []
    last_revision = after_revision
    for record in decisions:
        if not isinstance(record, dict):
            raise ValueError("STUDIO_TRIAGE_HISTORY_RECORD_INVALID")
        revision = _validated_revision(record.get("revision"))
        expected = _validated_revision(record.get("expected_revision"), expected=True)
        decision = record.get("decision")
        if (
            revision != last_revision + 1 or revision > head_revision
            or revision != expected + 1
            or decision not in TRIAGE_DECISIONS
        ):
            raise ValueError("STUDIO_TRIAGE_HISTORY_RECORD_INVALID")
        output.append({"revision": revision, "decision": decision})
        last_revision = revision
    if head_revision < after_revision and output:
        raise ValueError("STUDIO_TRIAGE_HISTORY_HEAD_INVALID")
    return {
        "contract_version": TRIAGE_HISTORY_VERSION,
        "collection_id": collection_id, "hit_id": hit_id,
        "private_only": True, "read_only": True,
        "publication_authority": False, "triage_action_authorized": False,
        "reviewer_identity_attested": False, "rights_clearance": False,
        "lineage_ok": lineage_ok, "head_revision": head_revision,
        "results": output,
        "next_after_revision": last_revision if len(output) == limit else None,
        "blockers": (
            ([] if lineage_ok else ["DISCOVERY_LINEAGE_MISMATCH"])
            + ["TRIAGE_REVIEWER_AUTHORITY_NOT_REEVALUATED",
               "PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED"]
        ),
    }


def read_triage_history(store: Any, *, collection_id: str, hit_id: str,
                        limit: int = 20, after_revision: int = 0) -> dict[str, object]:
    collection_id = _validated_ref(collection_id)
    hit_id = _validated_ref(hit_id)
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError("STUDIO_TRIAGE_HISTORY_LIMIT_INVALID")
    after_revision = _validated_revision(after_revision)
    try:
        raw = store.run(
            _TRIAGE_HISTORY_SQL, collection_id=collection_id, hit_id=hit_id,
            limit=limit, after_revision=after_revision,
        )
    except Exception:
        raise RuntimeError("STUDIO_TRIAGE_HISTORY_STORE_UNAVAILABLE") from None
    if not isinstance(raw, str) or len(raw) > 30_000:
        raise ValueError("STUDIO_TRIAGE_HISTORY_RESULT_INVALID")
    if not raw.strip():
        raise ValueError("STUDIO_TRIAGE_HISTORY_NOT_FOUND")
    if len(raw.splitlines()) != 1:
        raise ValueError("STUDIO_TRIAGE_HISTORY_RESULT_INVALID")
    try:
        row = json.loads(raw)
    except (ValueError, TypeError, json.JSONDecodeError):
        raise ValueError("STUDIO_TRIAGE_HISTORY_RESULT_INVALID") from None
    if not isinstance(row, dict):
        raise ValueError("STUDIO_TRIAGE_HISTORY_RESULT_INVALID")
    try:
        return _present(
            row, collection_id=collection_id, hit_id=hit_id,
            limit=limit, after_revision=after_revision,
        )
    except (ValueError, TypeError):
        raise ValueError("STUDIO_TRIAGE_HISTORY_RESULT_INVALID") from None


__all__ = ["TRIAGE_HISTORY_VERSION", "read_triage_history"]
