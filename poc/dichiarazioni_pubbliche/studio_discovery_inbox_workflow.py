"""DP-417 persisted Collection-scoped Discovery Inbox: safe read/bulk preview.

Derives all rows, revision heads and blocker codes from PostgreSQL. It grants
no identity, rights, review, capture, merge, extraction or publication authority.
Bulk is intentionally a DRY RUN: non-atomic multiple writes cannot be claimed
reversible, and a preview is never a sufficient basis for a later DB mutation.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Any, Sequence

from dichiarazioni_pubbliche.studio_discovery_triage_contract import (
    TRIAGE_DECISIONS, _validated_ref, _validated_revision,
)

INBOX_VERSION = "studio-discovery-inbox-v2"
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_DISPOSITIONS = frozenset({
    "NEW_CONTENT", "EXISTING_CONTENT", "DUPLICATE_WITHIN_RUN",
    "HOST_LIMIT", "RESULT_LIMIT", "OUTSIDE_DATE_WINDOW",
    "REJECTED_POLICY", "AMBIGUOUS_CONTENT_IDENTITY",
})
_COLLECTION_STATES = frozenset({"ACTIVE", "PAUSED", "ARCHIVED"})
_MANIFEST_STATES = frozenset({"ACTIVE", "SUPERSEDED"})
_RUN_STATES = frozenset({"RUNNING", "COMPLETED", "PARTIAL", "BLOCKED", "FAILED"})
_ATTEMPT_STATES = frozenset({"RUNNING", "HEALTHY", "BLOCKED", "BUDGET_BLOCKED", "FAILED"})
_MEMBERSHIP_STATES = frozenset({"INCLUDED", "REJECTED", "REMOVED"})
_FAMILY = re.compile(r"[A-Za-z0-9_:-]{1,128}\Z")

_SCOPED_SQL = """
SELECT json_build_object(
    'hit_id', hit.id, 'run_id', run.id, 'attempt_id', attempt.id,
    'query_id', hit.query_id, 'manifest_id', manifest.id,
    'collection_id', manifest.collection_id, 'content_id', hit.content_id,
    'source_family', hit.source_family, 'adapter_id', attempt.adapter_id,
    'disposition', hit.disposition, 'reason_code', hit.reason_code,
    'collection_state', collection.status, 'manifest_state', manifest.status,
    'run_state', run.status, 'attempt_state', attempt.status,
    'rights_state', content.rights_status, 'membership_state', member.status,
    'lineage_ok', COALESCE(
       attempt.run_id=run.id AND attempt.query_id=hit.query_id
       AND query.manifest_id=manifest.id, false),
    'manifest_digest_ok', run.manifest_sha256=manifest.manifest_sha256,
    'family_scope_ok', COALESCE(
       manifest.source_families ? hit.source_family
       AND query.source_families ? hit.source_family, false),
    'adapter_scope_ok', COALESCE(query.adapter_ids ? attempt.adapter_id, false),
    'content_url_ok', COALESCE(content.canonical_url=hit.canonical_url, false),
    'head_revision', COALESCE(history.head_revision, 0),
    'ledger_count', COALESCE(history.ledger_count, 0),
    'latest_decision', CASE WHEN COALESCE(
       attempt.run_id=run.id AND attempt.query_id=hit.query_id
       AND query.manifest_id=manifest.id, false)
       THEN latest.decision ELSE NULL END
)::text
FROM research_discovery_hit hit
JOIN research_discovery_run run ON run.id=hit.run_id
JOIN research_discovery_manifest manifest ON manifest.id=run.manifest_id
JOIN research_collection collection ON collection.id=manifest.collection_id
LEFT JOIN research_discovery_attempt attempt ON attempt.id=hit.attempt_id
LEFT JOIN research_discovery_query query ON query.id=hit.query_id
LEFT JOIN content_item content ON content.id=hit.content_id
LEFT JOIN research_collection_content member
    ON member.collection_id=manifest.collection_id AND member.content_id=hit.content_id
LEFT JOIN LATERAL (
    SELECT COALESCE(MAX(revision),0) AS head_revision, COUNT(*) AS ledger_count
    FROM research_discovery_triage_decision decision
    WHERE decision.hit_id=hit.id AND decision.collection_id=manifest.collection_id
) history ON TRUE
LEFT JOIN LATERAL (
    SELECT decision FROM research_discovery_triage_decision
    WHERE hit_id=hit.id AND collection_id=manifest.collection_id
    ORDER BY revision DESC LIMIT 1
) latest ON TRUE
WHERE manifest.collection_id=:'collection_id'
  AND hit.id > :'after_id'
ORDER BY hit.id ASC
LIMIT :'limit'::integer;
""".strip()

# The selection is re-read from the authoritative database in ONE statement.
# IDs cannot contain commas, and are passed as a psql variable, never SQL source.
_SELECTED_SQL = _SCOPED_SQL.replace(
    "  AND hit.id > :'after_id'",
    "  AND hit.id = ANY(string_to_array(:'selected_ids', ','))",
)
assert _SELECTED_SQL != _SCOPED_SQL


def _state(value: object, allowed: frozenset[str], *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or value not in allowed:
        raise ValueError("STUDIO_INBOX_STATE_INVALID")
    return value


def _reason(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _CODE.fullmatch(value):
        raise ValueError("STUDIO_INBOX_REASON_INVALID")
    return value


def _id(value: object, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    return _validated_ref(value)


def _bool(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("STUDIO_INBOX_CHECK_INVALID")
    return value


def _present(row: dict[str, Any], *, collection_id: str) -> dict[str, object]:
    path = {k: _id(row.get(k), optional=(k == "attempt_id")) for k in (
        "hit_id", "run_id", "attempt_id", "query_id", "manifest_id", "collection_id",
    )}
    if path["collection_id"] != collection_id:
        raise ValueError("STUDIO_INBOX_COLLECTION_MISMATCH")
    content_id = _id(row.get("content_id"), optional=True)
    source_family = row.get("source_family")
    adapter_id = _id(row.get("adapter_id"), optional=True)
    if not isinstance(source_family, str) or not _FAMILY.fullmatch(source_family):
        raise ValueError("STUDIO_INBOX_FAMILY_INVALID")
    disposition = _state(row.get("disposition"), _DISPOSITIONS)
    collection_state = _state(row.get("collection_state"), _COLLECTION_STATES)
    manifest_state = _state(row.get("manifest_state"), _MANIFEST_STATES)
    run_state = _state(row.get("run_state"), _RUN_STATES)
    attempt_state = _state(row.get("attempt_state"), _ATTEMPT_STATES, nullable=True)
    member_state = _state(row.get("membership_state"), _MEMBERSHIP_STATES, nullable=True)
    # The full rights vocabulary may grow; no unknown value can confer rights.
    rights_state = _reason(row.get("rights_state"))
    reason = _reason(row.get("reason_code"))
    lineage = _bool(row.get("lineage_ok"))
    digest = _bool(row.get("manifest_digest_ok"))
    family = _bool(row.get("family_scope_ok"))
    adapter = _bool(row.get("adapter_scope_ok"))
    url_ok = _bool(row.get("content_url_ok"))
    head = _validated_revision(row.get("head_revision"))
    count = _validated_revision(row.get("ledger_count"))
    latest = row.get("latest_decision")
    if head != count or (head == 0 and latest is not None) or (
        head > 0 and lineage and latest not in TRIAGE_DECISIONS
    ):
        raise ValueError("STUDIO_INBOX_LEDGER_INCOMPLETE")
    if not lineage:
        latest = None  # No historical review information under broken lineage.
    elif latest is not None:
        latest = _state(latest, TRIAGE_DECISIONS)

    blockers: list[tuple[str, str]] = []

    def block(flag: bool, code: str, condition: str) -> None:
        if flag:
            blockers.append((code, condition))

    block(collection_state != "ACTIVE", "COLLECTION_NOT_ACTIVE", "REACTIVATE_OR_REVIEW_COLLECTION")
    block(manifest_state != "ACTIVE", "DISCOVERY_MANIFEST_SUPERSEDED", "CREATE_CURRENT_MANIFEST_AND_RERUN")
    block(run_state not in {"COMPLETED", "PARTIAL"}, "DISCOVERY_RUN_NOT_COMPLETE", "COMPLETE_OR_RETRY_RUN")
    if attempt_state != "HEALTHY":
        attempt_blocker = (
            "DISCOVERY_ATTEMPT_BUDGET_BLOCKED" if attempt_state == "BUDGET_BLOCKED"
            else "DISCOVERY_ATTEMPT_NOT_HEALTHY"
        )
        attempt_recovery = (
            "REAUTHORIZE_BUDGET_AND_RETRY_ATTEMPT" if attempt_state == "BUDGET_BLOCKED"
            else "REVIEW_AND_RETRY_ATTEMPT"
        )
        blockers.append((attempt_blocker, attempt_recovery))
    block(not lineage, "DISCOVERY_LINEAGE_MISMATCH", "REPAIR_OR_REPLAY_DISCOVERY_LINEAGE")
    block(not digest, "DISCOVERY_MANIFEST_DIGEST_MISMATCH", "REPLAY_CURRENT_MANIFEST")
    block(not family, "DISCOVERY_FAMILY_NOT_ALLOWED", "REVIEW_SOURCE_FAMILY_SCOPE")
    block(not adapter, "DISCOVERY_ADAPTER_NOT_ALLOWED", "REVIEW_ADAPTER_SCOPE")
    block(disposition not in {"NEW_CONTENT", "EXISTING_CONTENT"},
          "DISCOVERY_DISPOSITION_NOT_ACTIONABLE", "REVIEW_OR_RERUN_DISCOVERY")
    block(content_id is None, "DISCOVERY_CONTENT_UNRESOLVED", "RESOLVE_CONTENT_IDENTITY")
    block(not url_ok, "DISCOVERY_URL_BINDING_MISMATCH", "REVIEW_CONTENT_IDENTITY")
    block(member_state != "INCLUDED", "DISCOVERY_MEMBERSHIP_NOT_INCLUDED", "REVIEW_COLLECTION_MEMBERSHIP")
    block(rights_state != "CLEARED", "DISCOVERY_CONTENT_RIGHTS_UNCLEARED", "REVIEW_CONTENT_RIGHTS")
    # The local metadata never supplies proof of CURRENT private source rights
    # or signed review authorization. No ready row may imply either.
    blockers.extend([
        ("PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED", "VERIFY_CURRENT_PRIVATE_SOURCE_RIGHTS_RECORD"),
        ("DISCOVERY_TRIAGE_REVIEW_AUTHORITY_UNAVAILABLE", "VERIFY_REVIEWER_AUTHORITY_AND_CURRENT_POLICY"),
    ])
    current = (collection_state == "ACTIVE" and manifest_state == "ACTIVE" and
               run_state in {"COMPLETED", "PARTIAL"} and attempt_state == "HEALTHY" and
               lineage and digest and family and adapter)
    # Currentness is transport/lineage currentness, NOT rights or action authority.
    snapshot = json.dumps({"path": path, "disposition": disposition, "content_id": content_id,
                           "source_family": source_family, "adapter_id": adapter_id,
                           "reason_code": reason, "blockers": [code for code, _ in blockers],
                           "current": current, "head": head if lineage else None,
                           "latest": latest, "statuses": [collection_state, manifest_state,
                                                           run_state, attempt_state]},
                          sort_keys=True, separators=(",", ":"))
    return {
        "queue": disposition, "hit_id": path["hit_id"], "collection_id": collection_id,
        "content_id": content_id, "provenance_path": path, "reason_code": reason,
        "source_family": source_family, "adapter_id": adapter_id,
        "collection_state": collection_state, "manifest_state": manifest_state,
        "run_state": run_state, "attempt_state": attempt_state,
        "current": current,
        "annotation_revision": head if lineage else None,
        "latest_annotation": latest,
        "snapshot_sha256": hashlib.sha256(snapshot.encode()).hexdigest(),
        "blockers": [code for code, _ in blockers],
        "unblock_conditions": [
            {"blocker": code, "unblock_condition": condition} for code, condition in blockers
        ],
        "private_only": True, "read_only": True,
        "action_authorized": False, "rights_clearance": False,
        "publication_authority": False,
    }


class DiscoveryInboxWorkflow:
    def __init__(self, store: Any) -> None:
        self.store = store

    def list_rows(self, *, collection_id: str, limit: int = 20,
                  after_id: str | None = None) -> dict[str, object]:
        collection_id = _validated_ref(collection_id)
        if type(limit) is not int or not 1 <= limit <= 30:
            raise ValueError("STUDIO_INBOX_LIMIT_INVALID")
        cursor = _validated_ref(after_id) if after_id is not None else ""
        try:
            raw = self.store.run(_SCOPED_SQL, collection_id=collection_id,
                                 after_id=cursor, limit=limit)
        except Exception:
            raise RuntimeError("STUDIO_INBOX_STORE_UNAVAILABLE") from None
        if not isinstance(raw, str) or len(raw) > 110000:
            raise ValueError("STUDIO_INBOX_ROWS_INVALID")
        lines = [line for line in raw.splitlines() if line.strip()]
        if len(lines) > limit:
            raise ValueError("STUDIO_INBOX_LIMIT_EXCEEDED")
        rows = []
        last = cursor
        for line in lines:
            try:
                parsed = json.loads(line)
            except (ValueError, TypeError):
                raise ValueError("STUDIO_INBOX_ROW_INVALID") from None
            if not isinstance(parsed, dict):
                raise ValueError("STUDIO_INBOX_ROW_INVALID")
            item = _present(parsed, collection_id=collection_id)
            if item["hit_id"] <= last:
                raise ValueError("STUDIO_INBOX_ORDER_INVALID")
            rows.append(item)
            last = item["hit_id"]
        return {
            "contract_version": INBOX_VERSION,
            "collection_id": collection_id,
            "private_only": True, "read_only": True,
            "action_authorized": False, "publication_authority": False,
            "rows": rows, "next_after_id": last if len(rows) == limit else None,
        }

    def preview_bulk(self, *, collection_id: str, hit_ids: list[str],
                     decision: str) -> dict[str, object]:
        """Atomically re-read a bounded selection, refusing missing/mixed rows.

        A dry run grants no authority and never produces a reusable write
        command; an actual reviewer action must independently revalidate.
        """
        collection_id = _validated_ref(collection_id)
        if not isinstance(hit_ids, list) or not 1 <= len(hit_ids) <= 10:
            raise ValueError("BULK_SIZE_INVALID")
        ids = [_validated_ref(value) for value in hit_ids]
        if len(set(ids)) != len(ids):
            raise ValueError("BULK_DUPLICATE_SELECTION")
        if decision not in {"NEEDS_REVIEW", "DEFERRED"}:
            raise ValueError("BULK_ACTION_NOT_ALLOWED")
        try:
            raw = self.store.run(
                _SELECTED_SQL, collection_id=collection_id,
                selected_ids=",".join(ids), limit=len(ids),
            )
        except Exception:
            raise RuntimeError("STUDIO_INBOX_STORE_UNAVAILABLE") from None
        if not isinstance(raw, str) or len(raw) > 48000:
            raise ValueError("BULK_ROWS_INVALID")
        lines = [line for line in raw.splitlines() if line.strip()]
        if len(lines) != len(ids):
            raise ValueError("BULK_SELECTION_CHANGED_OR_MISSING")
        rows = []
        seen: set[str] = set()
        for line in lines:
            try:
                item = _present(json.loads(line), collection_id=collection_id)
            except (ValueError, TypeError, json.JSONDecodeError):
                raise ValueError("BULK_ROWS_INVALID") from None
            if item["hit_id"] not in ids or item["hit_id"] in seen:
                raise ValueError("BULK_SELECTION_CHANGED_OR_MISSING")
            rows.append(item)
            seen.add(item["hit_id"])
        if seen != set(ids):
            raise ValueError("BULK_SELECTION_CHANGED_OR_MISSING")
        return plan_bulk_annotation(rows, decision=decision,
                                    expected_collection_id=collection_id)


def plan_bulk_annotation(rows: Sequence[dict[str, object]], *, decision: str,
                         expected_collection_id: str) -> dict[str, object]:
    """Allow only homogeneous, supersedable annotation previews (never writes)."""
    collection_id = _validated_ref(expected_collection_id)
    if decision not in {"NEEDS_REVIEW", "DEFERRED"}:
        raise ValueError("BULK_ACTION_NOT_ALLOWED")
    if not isinstance(rows, (tuple, list)) or not 1 <= len(rows) <= 10:
        raise ValueError("BULK_SIZE_INVALID")
    ids = [r.get("hit_id") for r in rows if isinstance(r, dict)]
    if len(ids) != len(rows):
        raise ValueError("BULK_ROW_INVALID")
    if len(set(ids)) != len(ids):
        raise ValueError("BULK_DUPLICATE_SELECTION")
    fingerprint: tuple[object, ...] | None = None
    items = []
    for row in rows:
        if row.get("collection_id") != collection_id:
            raise ValueError("BULK_COLLECTION_MISMATCH")
        hit_id = _validated_ref(row.get("hit_id"))
        if row.get("current") is not True:
            raise ValueError("BULK_ROW_NOT_CURRENT")
        rev = _validated_revision(row.get("annotation_revision"), expected=True)
        latest = row.get("latest_annotation")
        if latest is not None and latest not in TRIAGE_DECISIONS:
            raise ValueError("BULK_REVIEW_STATES_INCOMPATIBLE")
        if latest == "REJECTED":
            raise ValueError("BULK_REVIEW_STATES_INCOMPATIBLE")
        if row.get("queue") not in {"NEW_CONTENT", "EXISTING_CONTENT"}:
            raise ValueError("BULK_QUEUE_NOT_ANNOTATABLE")
        path = row.get("provenance_path")
        if not isinstance(path, dict) or path.get("hit_id") != hit_id:
            raise ValueError("BULK_PROVENANCE_INVALID")
        # A bulk group must have the same source run/manifest, same exact
        # queue type and review state. Different snapshots cannot be grouped.
        state = (row["queue"], latest, rev, path.get("run_id"), path.get("manifest_id"),
                 row.get("source_family"), row.get("adapter_id"),
                 row.get("reason_code"), tuple(row.get("blockers") or ()),
                 row.get("collection_state"), row.get("manifest_state"),
                 row.get("attempt_state"))
        if fingerprint is None:
            fingerprint = state
        elif fingerprint != state:
            raise ValueError("BULK_REVIEW_STATES_INCOMPATIBLE")
        items.append({"hit_id": hit_id, "expected_revision": rev,
                      "snapshot_sha256": row.get("snapshot_sha256")})
    if any(not isinstance(i["snapshot_sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", i["snapshot_sha256"]
    ) for i in items):
        raise ValueError("BULK_SNAPSHOT_INVALID")
    return {
        "contract_version": INBOX_VERSION,
        "result_code": "DRY_RUN_ONLY", "collection_id": collection_id,
        "annotation": decision, "items": items,
        "requires_fresh_database_compare_and_swap": True,
        "mutation_authorized": False, "publication_authority": False,
        "private_only": True,
    }


def render_private_inbox_fragment(page: dict[str, object]) -> str:
    """Bounded accessible *read-only* HTML for the private Studio owner to embed.

    This is not wired to the public frontend or to the Studio HTTP endpoint.
    Only accepted output from list_rows is rendered; every value is escaped.
    No buttons, mutation links, human decisions or sensitive source bodies.
    """
    if not isinstance(page, dict) or page.get("contract_version") != INBOX_VERSION:
        raise ValueError("STUDIO_INBOX_FRAGMENT_CONTRACT_INVALID")
    collection = _validated_ref(page.get("collection_id"))
    rows = page.get("rows")
    if not isinstance(rows, list) or len(rows) > 30:
        raise ValueError("STUDIO_INBOX_FRAGMENT_ROWS_INVALID")

    def safe(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("STUDIO_INBOX_FRAGMENT_FIELD_INVALID")
        return html.escape(value, quote=True)

    result = [
        '<section class="studio-discovery-inbox" aria-labelledby="dp417-inbox-heading">',
        '<h2 id="dp417-inbox-heading">Discovery Inbox · sola lettura</h2>',
        f'<p>Raccolta: <code>{safe(collection)}</code>. '
        'Le annotazioni non autorizzano acquisizione, verifica o pubblicazione.</p>',
        '<ol class="studio-discovery-inbox__rows">',
    ]
    for row in rows:
        if not isinstance(row, dict) or row.get("collection_id") != collection:
            raise ValueError("STUDIO_INBOX_FRAGMENT_SCOPE_INVALID")
        hit_id = _validated_ref(row.get("hit_id"))
        queue = _state(row.get("queue"), _DISPOSITIONS)
        path = row.get("provenance_path")
        if not isinstance(path, dict) or path.get("hit_id") != hit_id or path.get("collection_id") != collection:
            raise ValueError("STUDIO_INBOX_FRAGMENT_PATH_INVALID")
        blocks = row.get("unblock_conditions")
        if not isinstance(blocks, list) or len(blocks) > 24:
            raise ValueError("STUDIO_INBOX_FRAGMENT_BLOCKERS_INVALID")
        result.append('<li class="studio-discovery-inbox__row">')
        result.append(f'<h3><code>{safe(hit_id)}</code> · {safe(queue)}</h3>')
        result.append('<details><summary>Provenienza e motivi del blocco</summary>')
        result.append('<dl>')
        for key, label in (("run_id", "Run"), ("attempt_id", "Tentativo"),
                           ("query_id", "Query ID"), ("manifest_id", "Manifest")):
            value = path.get(key)
            value = _id(value, optional=(key == "attempt_id"))
            result.append(f'<dt>{label}</dt><dd><code>{safe(value or "non disponibile")}</code></dd>')
        result.append('</dl><ul>')
        for block in blocks:
            if not isinstance(block, dict):
                raise ValueError("STUDIO_INBOX_FRAGMENT_BLOCKERS_INVALID")
            code = _reason(block.get("blocker"))
            condition = _reason(block.get("unblock_condition"))
            if code is None or condition is None:
                raise ValueError("STUDIO_INBOX_FRAGMENT_BLOCKERS_INVALID")
            result.append(f'<li><code>{safe(code)}</code> · {safe(condition)}</li>')
        result.append('</ul></details></li>')
    result.extend(['</ol>', '</section>'])
    return "".join(result)


__all__ = ["DiscoveryInboxWorkflow", "plan_bulk_annotation",
           "render_private_inbox_fragment", "INBOX_VERSION"]
