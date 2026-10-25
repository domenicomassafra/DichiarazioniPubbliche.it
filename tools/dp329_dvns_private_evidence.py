#!/usr/bin/env python3
"""One public DVNS/OpenCoesione MCP aggregate → private candidate Evidence.

--apply-private-evidence registers a bounded machine review of the current
official OpenCoesione licence, then persists a single typed candidate through
the existing private rights and Evidence stores. Never approves or publishes.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.dvns_mcp_private_evidence import (
    LICENSE_URL, METRIC, POLICY_VERSION, SOURCE_URL, DATASET, SOURCE_FAMILY,
    DvnsMcpError, fetch_public_mcp_snapshot, import_opencoesione_snapshot,
    official_licence_receipt, observe_official_reference,
    persist_private_candidate, rights_subject,
)
from dichiarazioni_pubbliche.private_capture_rights import evaluate_source_use
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore


def run(*, database_url: str, apply: bool) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    observed = now.isoformat(timespec="seconds")
    notice_receipt = official_licence_receipt()
    rights = PrivateRightsRegistryStore(database_url=database_url)
    subject = rights_subject()
    current = rights.read_current(subject)
    if apply and current is None:
        current = rights.record_rights(
            subject=subject, policy_version=POLICY_VERSION, rights_status="CLEARED",
            rights_receipt_ref=notice_receipt,
            permitted_uses=("FETCH", "STORE_BODY"),
            attribution_requirements=("ATTRIBUTION_REQUIRED", "LICENSE_LINK_REQUIRED"),
            reviewed_at=observed,
            expires_at=(now + timedelta(days=30)).isoformat(timespec="seconds"),
            reviewer_ref="machine:dp329-official-opencoesione-licence-review",
        )
    if current is None or current.rights_receipt_ref != notice_receipt:
        return {"status": "HOLD", "reason": "DVNS_MCP_CURRENT_LICENCE_RIGHTS_REQUIRED",
                "source_url": SOURCE_URL, "licence_url": LICENSE_URL,
                "licence_sha256": notice_receipt, "written": False}
    for use in ("FETCH", "STORE_BODY"):
        decision = evaluate_source_use(
            rights.read_current(subject), subject=subject,
            rights_record_id=current.id, policy_version=POLICY_VERSION,
            use=use, now=now,
        )
        if not decision.permitted:
            return {"status": "HOLD", "reason": decision.reason_code,
                    "rights_record_id": current.id, "written": False}
    if not apply:
        return {"status": "READY_FOR_ONE_PRIVATE_CANDIDATE", "source_url": SOURCE_URL,
                "rights_record_id": current.id, "written": False}
    payload = fetch_public_mcp_snapshot()
    official_reference = observe_official_reference()
    # The source receipt is timed after the network read, not at preflight.
    observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
    imported = import_opencoesione_snapshot(payload, observed_at=observed)
    store = QueueRuntimeStore(database_url=database_url)
    receipt = persist_private_candidate(imported, store=store, rights=rights,
                                        licence_receipt=notice_receipt, observed_at=observed,
                                        official_reference=official_reference)
    record = store.run(
        """SELECT json_build_object(
           'id', e.id, 'url', e.canonical_url, 'rights_status', e.rights_status,
           'record_status', e.record_status,
           'content_sha256', e.content_sha256,
           'source_version', e.metadata->>'source_version',
           'official_current_source_version', e.metadata->>'official_current_source_version',
           'official_current_reference_period', e.metadata->>'official_current_reference_period',
           'dvns_snapshot_superseded', e.metadata->'dvns_snapshot_superseded',
           'source_record_id', e.metadata->>'external_id',
           'observation_id', o.id, 'metric', o.metric,
           'numeric_value', o.value_numeric, 'unit', o.unit,
           'reference_period', o.reference_period, 'status', o.status,
           'rights_record_id', o.metadata->>'rights_record_id',
           'selector', o.source_pointer->'field_provenance'->>'value_numeric'
         )::text FROM evidence e JOIN evidence_observation o ON o.evidence_id=e.id
         WHERE e.id=:'evidence' AND o.id=:'observation';""",
        evidence=receipt.evidence_id, observation=receipt.observation_id,
    )
    if not record:
        raise DvnsMcpError("DVNS_MCP_AUTHENTICATED_CONSUMER_READBACK_MISSING")
    readback = json.loads(record)
    if (readback["id"] != receipt.evidence_id or readback["status"] != "CANDIDATE"
            or readback["rights_status"] != "CLEARED"
            or readback["content_sha256"] != official_reference.source_version[7:]
            or readback["source_version"] != receipt.source_version
            or readback["rights_record_id"] != receipt.rights_record_id
            or readback["url"] != SOURCE_URL
            or readback["metric"] != METRIC
            or readback["numeric_value"] != int(imported.normalized_batch.values[0].value_numeric)
            or readback["reference_period"] != imported.normalized_batch.values[0].reference_period
            or readback["source_record_id"] != receipt.source_record_id
            or readback["official_current_source_version"] != official_reference.source_version
            or readback["official_current_reference_period"] != official_reference.reference_period
            or readback["record_status"] != (
                "SUPERSEDED" if readback["dvns_snapshot_superseded"] else "ACTIVE")
            or readback["dvns_snapshot_superseded"] != (
                official_reference.reference_period > imported.normalized_batch.values[0].reference_period)
            or readback["selector"] != dict(imported.provenance[0].fields)["value_numeric"]):
        raise DvnsMcpError("DVNS_MCP_AUTHENTICATED_CONSUMER_READBACK_MISMATCH")
    return {"status": "PRIVATE_CANDIDATE_PERSISTED", "dataset": DATASET,
            "source_family": SOURCE_FAMILY, "source_url": SOURCE_URL,
            "licence_url": LICENSE_URL, "licence_sha256": notice_receipt,
            "attribution": "Dipartimento per le Politiche di Coesione / OpenCoesione",
            "rights_record_id": current.id, "policy_version": POLICY_VERSION,
            "official_current_projects": official_reference.projects,
            "rights_expires_at": current.expires_at, "provider": imported.provider_id,
            "schema_version": imported.source_schema_version,
            "adapter_version": imported.adapter_version,
            "dvns_replay_id": imported.replay_id,
            "readback": readback, "written": True, "publication_authorized": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="dichiarazioni_pubbliche")
    parser.add_argument("--apply-private-evidence", action="store_true")
    args = parser.parse_args()
    try:
        receipt = run(database_url=args.database_url, apply=args.apply_private_evidence)
    except DvnsMcpError as exc:
        receipt = {"status": "HOLD", "reason": str(exc)}
    print(json.dumps(receipt, sort_keys=True, ensure_ascii=False))
    return 2 if receipt["status"] == "HOLD" else 0


if __name__ == "__main__":
    raise SystemExit(main())
