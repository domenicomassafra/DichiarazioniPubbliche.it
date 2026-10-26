#!/usr/bin/env python3
"""One bounded DP-319 investigation of an already captured official Senato XML.

Read-only against the operational PostgreSQL corpus; writes only the explicitly
selected opt-in private SQLite attempt ledger. No provider, review or publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import (  # noqa: E402
    CaptureBodyStore,
    CapturePipelineStore,
)
from dichiarazioni_pubbliche.investigation_attempts_store_v1 import (  # noqa: E402
    InvestigationSQLiteStore,
    InvestigationSourceRecord,
)
from dichiarazioni_pubbliche.investigation_attempts_v1 import (  # noqa: E402
    InvestigationObservation,
    InvestigationSpec,
)
from dichiarazioni_pubbliche.private_capture_rights import (  # noqa: E402
    SourceFamilyUseGuard,
    SourceUseBlocked,
)
from dichiarazioni_pubbliche.private_investigation_d_receipt import (  # noqa: E402
    PrivateDReceiptLedger,
)
from dichiarazioni_pubbliche.research_plan import ResearchAssignment  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PrivateRightsRegistryStore,
    RightsSubject,
)
from dp326_senato_private_discovery import (  # noqa: E402
    CONTENT_BLOB_SHA1,
    CURRENT_COMMIT,
    COLLECTION_ID,
    REVIEWER_REF,
    RIGHTS_RECEIPT,
    official_verified_hit,
)
from dp330_senato_private_capture import (  # noqa: E402
    BODY_SHA256,
    POLICY,
    SOURCE_FAMILY,
    SOURCE_ID,
    SOURCE_URL,
    _context,
)

NEED_ID = "need:dp319-334-senato-history"
CANDIDATE_ID = "candidate:dp319-334-senato-history"
ATTEMPT_KEY = "dp319-334-senato-history-v1"
AKN_ROOT = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03}akomaNtoso"
MAX_XML_BYTES = 1_000_000


def _document_date(raw: bytes) -> str:
    if hashlib.sha256(raw).hexdigest() != BODY_SHA256:
        raise ValueError("DP319_PINNED_BODY_HASH_MISMATCH")
    try:
        root = ElementTree.fromstring(raw)
        if root.tag != AKN_ROOT:
            raise ValueError("DP319_PINNED_XML_INVALID")
        dates = {
            element.get("date")
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1] == "FRBRdate"
            and element.get("name") == "presentazione"
        }
        if len(dates) != 1:
            raise ValueError("DP319_PINNED_DATE_UNRESOLVED")
        observed = date.fromisoformat(next(iter(dates)))
    except ElementTree.ParseError as exc:
        raise ValueError("DP319_PINNED_XML_INVALID") from exc
    if observed >= date.today():
        raise ValueError("DP319_PINNED_DATE_NOT_HISTORICAL")
    return observed.isoformat()


def run(database_url: str, ledger_path: Path, storage_root: Path) -> dict[str, object]:
    """Check rights and real capture before one append-only, zero-provider attempt."""
    official = official_verified_hit()
    if (
        official.canonical_url != SOURCE_URL
        or official.metadata.get("commit") != CURRENT_COMMIT
        or official.metadata.get("blob_sha1") != CONTENT_BLOB_SHA1
    ):
        raise ValueError("DP319_OFFICIAL_SOURCE_IDENTITY_MISMATCH")

    captures = CapturePipelineStore(database_url=database_url)
    context = _context(captures)  # Reuse DP-330's exact Collection/Hit guard.
    content_id = context["id"]
    subject = RightsSubject(
        source_family=SOURCE_FAMILY,
        locator_kind="URL",
        locator_value=SOURCE_URL,
        content_id=content_id,
    )
    rights = PrivateRightsRegistryStore(database_url=database_url)
    current = rights.read_current(subject)
    if current is None:
        raise ValueError("DP319_RIGHTS_RECORD_MISSING")
    if (
        current.rights_receipt_ref != RIGHTS_RECEIPT
        or current.reviewer_ref != REVIEWER_REF
        or "ATTRIBUTION_REQUIRED" not in current.attribution_requirements
    ):
        raise ValueError("DP319_SOURCE_LICENSE_RECEIPT_MISMATCH")
    use = SourceFamilyUseGuard(
        read_current=rights.read_current,
        subject=subject,
        rights_record_id=current.id,
        policy_version=POLICY,
        expected_sha256=BODY_SHA256,
    )
    use.require("PARSE_TEXT", content_sha256=BODY_SHA256)

    capture = captures.find_capture(content_id, BODY_SHA256)
    if (
        not capture
        or capture.get("status") != "CAPTURED"
        or capture.get("rights_status") != "CLEARED"
        or capture.get("hold_status") != "NONE"
        or capture.get("content_id") != content_id
        or capture.get("content_sha256") != BODY_SHA256
        or capture.get("final_url") != SOURCE_URL
        or not capture.get("body_ref")
    ):
        raise ValueError("DP319_APPROVED_CAPTURE_UNAVAILABLE")

    raw = CaptureBodyStore(storage_root).read(
        capture["body_ref"],
        expected_sha256=BODY_SHA256,
        max_bytes=MAX_XML_BYTES,
    )
    use.require(
        "PARSE_TEXT",
        content_sha256=hashlib.sha256(raw).hexdigest(),
        media_type=capture.get("media_type"),
    )
    historical_date = _document_date(raw)

    # These identifiers are local to the isolated canary; no Coverage Need or
    # completed exception is asserted to exist in operational PostgreSQL.
    source = InvestigationSourceRecord(
        need_id=NEED_ID,
        source_id=SOURCE_ID,
        candidate_id=CANDIDATE_ID,
        material_fingerprint="sha256:" + BODY_SHA256,
        source_version="capture:" + capture["id"],
        source_sha256=BODY_SHA256,
        rights_status="CLEARED",
        policy_status="ALLOWED",
        revision=1,
    )
    spec = InvestigationSpec(
        need_id=NEED_ID,
        material_fingerprint=source.material_fingerprint,
        question_kind="SOURCE_VERSION",
        question="Does the pinned historical Senato record prove present status?",
        source_family=SOURCE_FAMILY,
        max_attempts=1,
        cost_cap_usd=Decimal("0"),
        rights_status="CLEARED",
    )
    assignments = (
        ResearchAssignment(
            assignment_id="assignment:dp319-334-senato-history",
            coverage_need_id=NEED_ID,
            lane="OFFICIAL_STRUCTURED",
            question=spec.question,
            adapter_ids=("senato_official_pinned_metadata",),
            max_queries=1,
            max_results=1,
            max_results_per_host=1,
            cost_cap_usd=Decimal("0"),
            temporal_constraints={"record_date": historical_date},
            authority_scope={
                "source_commit": CURRENT_COMMIT,
                "rights_record": current.id,
            },
            stop_conditions=("ONE_PINNED_OFFICIAL_RECORD_OR_HOLD",),
        ),
    )
    store = InvestigationSQLiteStore(ledger_path)
    try:
        store.record_source(source, expected_revision=0)
    except ValueError as exc:
        if str(exc) != "INVESTIGATION_STORE_SOURCE_REVISION_CONFLICT":
            raise
        # Registration below verifies exact persisted source+rights identity.
    state = store.register(spec, assignments, source)
    replay = state.revision != 0
    d_receipt_id = None
    d_blocker = None
    if state.revision == 0:
        use.require("PARSE_TEXT", content_sha256=BODY_SHA256)
        state = store.reserve(
            spec,
            assignments,
            source,
            key=ATTEMPT_KEY,
            expected_revision=state.revision,
        )
    # Only this script's zero-provider inspection is eligible for this exact D
    # receipt. A pending prior reservation can have unknown effects and is never
    # automatically completed or dispatched on process restart.
    if state.revision in (1, 2) and (not replay or state.revision == 2):
        attempt = state.reservations[0]
        try:
            use.require("PARSE_TEXT", content_sha256=BODY_SHA256)
            d_receipt_id = PrivateDReceiptLedger(database_url).record_zero_attempt(
                attempt=attempt,
                source=source,
                content_id=content_id,
                rights_record_id=current.id,
            )
        except SourceUseBlocked:
            d_blocker = "DP319_RIGHTS_REVOKED_DURING_RESERVATION"
        except ValueError as exc:
            d_blocker = (
                str(exc)
                if str(exc).startswith("DP319_D_")
                else "DP319_D_LEDGER_UNAVAILABLE"
            )
        except (RuntimeError, OSError):
            d_blocker = "DP319_D_LEDGER_UNAVAILABLE"
        if not replay and d_receipt_id:
            try:
                use.require("PARSE_TEXT", content_sha256=BODY_SHA256)
            except SourceUseBlocked:
                d_blocker = "DP319_RIGHTS_REVOKED_DURING_RESERVATION"
            else:
                state = store.complete(
                    spec,
                    assignments,
                    source,
                    observation=InvestigationObservation(
                        attempt_id=attempt.attempt_id,
                        material_fingerprint=source.material_fingerprint,
                        assignment_id=attempt.assignment_id,
                        lane=attempt.lane,
                        result="SOURCE_INCONCLUSIVE",
                        lineage_id=None,
                        source_version=None,
                        source_sha256=None,
                        review_event_id=None,
                        spent_usd=Decimal("0"),
                    ),
                    key=ATTEMPT_KEY,
                    expected_revision=state.revision,
                )
    state = store.resume(state.decision.plan_fingerprint, source_revision=1)
    receipt = state.reservations[0] if state.reservations else None
    coverage = [
        {
            "lane": lane.lane,
            "status": lane.status,
            "reason_code": lane.reason_code,
            "assignment_ids": list(lane.assignment_ids),
            "completed_attempt_ids": list(lane.completed_attempt_ids),
            "max_queries": lane.max_queries,
            "max_results": lane.max_results,
            "max_results_per_host": lane.max_results_per_host,
            "cost_cap_usd": str(lane.cost_cap_usd),
            "stop_conditions": list(lane.stop_conditions),
            "source_lineages": list(lane.source_lineages),
            "independent_lineages": lane.independent_lineages,
        }
        for lane in state.decision.coverage
    ]
    missing_coverage = [
        lane["lane"] for lane in coverage
        if lane["status"] not in {"CHECKED_INSUFFICIENT", "SOURCE_CANDIDATE", "INDEPENDENT_CANDIDATE"}
    ]
    status = (
        ("PRIVATE_PARTIAL_HOLD" if missing_coverage else "PRIVATE_INSUFFICIENT_EVIDENCE")
        if d_receipt_id is not None
        and state.decision.status == "EXHAUSTED"
        and len(state.observations) == 1
        and state.observations[0].result == "SOURCE_INCONCLUSIVE"
        else "WAIT_EXTERNAL"
    )
    return {
        "status": status,
        "decision": state.decision.status,
        "reason_code": d_blocker or state.decision.reason_code,
        "residual_reason": "HISTORICAL_OFFICIAL_RECORD_DOES_NOT_PROVE_CURRENT_STATUS",
        "coverage": coverage,
        "missing_coverage": missing_coverage,
        "source_permissions_for_other_lanes": "NOT_EVALUATED",
        "collection_id": COLLECTION_ID,
        "content_id": content_id,
        "source_id": SOURCE_ID,
        "source_commit": CURRENT_COMMIT,
        "source_sha256": BODY_SHA256,
        "source_document_date": historical_date,
        "capture_id": capture["id"],
        "rights_record_id": current.id,
        "rights_use": "PARSE_TEXT",
        "license": "CC-BY-4.0",
        "attribution": "Senato della Repubblica",
        "plan_fingerprint": state.decision.plan_fingerprint,
        "attempt_id": receipt.attempt_id if receipt else None,
        "ledger_revision": state.revision,
        "reservation_count": len(state.reservations),
        "completion_count": len(state.observations),
        "observation": state.observations[0].result if state.observations else None,
        "spent_usd": str(state.decision.spent_usd),
        "d_receipt_id": d_receipt_id,
        "d_quota_units_consumed": 0 if d_receipt_id else None,
        "d_request_count": 0 if d_receipt_id else None,
        "d_usage_reconciled": d_receipt_id is not None,
        "provider_billing_reconciled": False,
        "replay_same_receipt": replay and state.revision == 2,
        "dispatch_authorized": state.dispatch_authorized,
        "publication_authority": state.publication_authority,
        "new_child_task_count": 0,
        "downstream_queue_closed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url", default=os.getenv("DICHIARAZIONI_PUBBLICHE_DATABASE_URL")
    )
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=Path("~/.local/share/dichiarazioni-pubbliche-captures").expanduser(),
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url is required")
    try:
        result = run(args.database_url, args.ledger, args.storage_root)
    except (SourceUseBlocked, ValueError) as exc:
        code = str(exc)
        if not code.startswith(
            (
                "SOURCE_USE_",
                "DP319_RIGHTS_",
                "DP319_SOURCE_LICENSE_",
                "DP319_APPROVED_CAPTURE_",
            )
        ):
            raise
        result = {
            "status": "WAIT_EXTERNAL",
            "reason_code": code,
            "dispatch_authorized": False,
            "publication_authority": False,
            "new_child_task_count": 0,
            "d_usage_reconciled": False,
            "provider_billing_reconciled": False,
        }
    except (RuntimeError, OSError):
        result = {
            "status": "WAIT_EXTERNAL",
            "reason_code": "DP319_OPERATIONAL_STORE_UNAVAILABLE",
            "dispatch_authorized": False,
            "publication_authority": False,
            "new_child_task_count": 0,
            "d_usage_reconciled": False,
            "provider_billing_reconciled": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
