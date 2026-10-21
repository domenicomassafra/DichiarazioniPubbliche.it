#!/usr/bin/env python3
"""DP-304 real-case rehearsal: selection, rights case, revocation (fictional data).

Disposable PostgreSQL, isolated release directory, loopback public surfaces.
A passing rehearsal proves the deny-by-default gates behave as specified on one
case. It is not a lawful basis, a retention period, a rights outcome for a real
person, or a publication authorization.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.dp304_case_fixture import (  # noqa: E402
    CASE_FIELDS,
    CASE_RECORD,
    CASE_SUBJECT,
    SENTINELS,
    case_row,
)
from dichiarazioni_pubbliche.dp304_case_postgres import (  # noqa: E402
    disposable_postgres,
    file_hashes,
)
from dichiarazioni_pubbliche.policy.privacy_policy import (  # noqa: E402
    PRIVACY_POLICY_VERSION,
    RETENTION_PERIODS_APPROVED,
    DataClass,
    PrivateAccessMode,
    PrivateAccessPurpose,
    PrivateAccessRequest,
    PrivateAccessRole,
    ProjectionInput,
    RetentionDecision,
    RightsRequestKind,
    RightsRequestOutcome,
    assert_no_trait_inference,
    decide_projection,
    minimize_public_fieldset,
    retention_decision,
    rights_request_outcome,
)
from dichiarazioni_pubbliche.privacy_decision_persistence import (  # noqa: E402
    PrivacyPublicationDecisionStore,
)
from dichiarazioni_pubbliche.privacy_runtime import (  # noqa: E402
    PrivacyRightsAccessStore,
    RightsCaseEventType,
)
from dichiarazioni_pubbliche.public_api import build_server  # noqa: E402
from dichiarazioni_pubbliche.public_projection import (  # noqa: E402
    build_public_projection,
    write_public_bundle,
)

GENERATED_AT = "2026-10-21T00:00:00+00:00"
REVIEWER = "reviewer:dp304-canary"
AUDIT = "audit:dp304-canary"
ACTOR = "operator:dp304-canary"
PUBLISHED_TEXT = "normalized_claim"
PUBLIC_PATHS = (
    "/api/v1/health",
    "/api/v1/index.json",
    "/api/v1/findings",
    f"/api/v1/findings/{CASE_RECORD}",
    "/index.nt",
)
# After revocation the record route must disappear while the collection stays up.
STABLE_PATHS = ("/api/v1/health", "/api/v1/index.json", "/api/v1/findings", "/index.nt")
RECORD_PATH = f"/api/v1/findings/{CASE_RECORD}"
# Real published values for the five allowlisted fields of this case.
PUBLIC_VALUES = {
    "finding_id": CASE_RECORD,
    "person_name": "Persona Pubblica Fittizia",
    "public_role_interval": "Consiglio comunale Fittizio, mandato in corso",
    "source_url": "https://example.test/dp304-canary",
    "normalized_claim": "Il consiglio comunale ha approvato il bilancio con dodici voti favorevoli.",
}


def require(condition: object, code: str) -> None:
    if not condition:
        raise RuntimeError("DP304_CANARY_" + code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selection_receipt() -> dict[str, Any]:
    """Deny-by-default classification of the case field matrix plus retention."""
    decisions: dict[str, str] = {}
    for field, data_class, reason, approved, expect_public in CASE_FIELDS:
        decision = decide_projection(
            ProjectionInput(
                field_name=field,
                data_class=data_class,
                text_value=PUBLIC_VALUES.get(field) or SENTINELS.get(field),
                relevance_reason=reason,
                explicitly_approved=approved,
                is_published_version=True,
            )
        )
        require(
            decision.allowed == expect_public,
            f"SELECTION_MISMATCH_{field}_{decision.decision.value}",
        )
        decisions[field] = decision.decision.value
    public_figure_only = decide_projection(
        ProjectionInput(
            field_name="person_name",
            data_class=DataClass.PUBLIC_CORE,
            relevance_reason="IS_PUBLIC_FIGURE",
            is_published_version=True,
        )
    )
    require(not public_figure_only.allowed, "PUBLIC_FIGURE_ONLY_ALLOWED")
    mislabelled = decide_projection(
        ProjectionInput(
            field_name="raw_transcript",
            data_class=DataClass.PUBLIC_CORE,
            relevance_reason="PUBLIC_ROLE",
            is_published_version=True,
        )
    )
    require(not mislabelled.allowed, "MISLABELLED_PRIVATE_FIELD_ALLOWED")
    assert_no_trait_inference()
    minimized = minimize_public_fieldset([field for field, *_ in CASE_FIELDS])
    require("raw_transcript" not in minimized, "MINIMIZATION_KEPT_RAW_TRANSCRIPT")
    require("normalized_claim" in minimized, "MINIMIZATION_DROPPED_PUBLIC_FIELD")
    retention = retention_decision(DataClass.OPERATIONAL_PRIVATE)
    require(RETENTION_PERIODS_APPROVED is False, "RETENTION_PERIOD_INVENTED")
    require(retention is RetentionDecision.AWAITING_APPROVED_PERIOD, "RETENTION_NOT_HELD")
    require(
        retention_decision(DataClass.OPERATIONAL_PRIVATE, legal_hold_active=True)
        is RetentionDecision.LEGAL_HOLD,
        "RETENTION_HOLD_NOT_PRIOR",
    )
    return {
        "policy_version": PRIVACY_POLICY_VERSION,
        "field_matrix": decisions,
        "published_field_count": sum(
            1 for value in decisions.values() if value.startswith("ALLOW")
        ),
        "refused_or_held_field_count": sum(
            1 for value in decisions.values() if not value.startswith("ALLOW")
        ),
        "public_figure_only_relevance": public_figure_only.decision.value,
        "mislabelled_private_field": mislabelled.decision.value,
        "minimized_public_fieldset": list(minimized),
        "retention_behavior": retention.value,
        "retention_periods_approved": RETENTION_PERIODS_APPROVED,
    }


class DecisionBoundSource:
    """Projection source whose publication revalidation replays the private review."""

    def __init__(self, row: dict[str, Any], store: PrivacyPublicationDecisionStore) -> None:
        self.row = row
        self.store = store
        self.record_version = "v1"

    def projectable_findings(self) -> list[dict[str, Any]]:
        return [self.row]

    def revalidate_publication_candidate(
        self, row: dict[str, Any], dossier: dict[str, Any]
    ) -> bool:
        replay = self.store.replay_current_text_field(
            subject_ref=CASE_SUBJECT,
            record_ref=CASE_RECORD,
            current_record_version=self.record_version,
            field_name=PUBLISHED_TEXT,
            current_text_value=str(row[PUBLISHED_TEXT]),
        )
        return replay.allowed


def scan_release(out: Path, paths: tuple[str, ...]) -> dict[str, Any]:
    """Every written file plus every loopback response, scanned for sentinels."""
    leaks: list[str] = []
    files: dict[str, str] = {}
    for path in sorted(out.rglob("*")):
        if path.is_file():
            body = path.read_bytes()
            files[path.relative_to(out).as_posix()] = digest(body)
            leaks.extend(
                f"FILE:{path.name}:{name}"
                for name, sentinel in SENTINELS.items()
                if sentinel.encode() in body
            )
    responses: dict[str, dict[str, Any]] = {}
    with build_server(out / "index.json", host="127.0.0.1", port=0, static_dir=out) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for route in paths:
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    conn.request("GET", route, headers={"Accept-Encoding": "identity"})
                    response = conn.getresponse()
                    body = response.read(1_000_001)
                finally:
                    conn.close()
                responses[route] = {"status": response.status, "sha256": digest(body)}
                leaks.extend(
                    f"HTTP:{route}:{name}"
                    for name, sentinel in SENTINELS.items()
                    if sentinel.encode() in body
                )
        finally:
            server.shutdown()
            worker.join(timeout=5)
    require(not leaks, "PRIVATE_SENTINEL_PUBLISHED_" + (leaks[0] if leaks else ""))
    return {"files": files, "http": responses}


def persist_review(
    store: PrivacyPublicationDecisionStore,
    *,
    record_version: str,
    relevance_reason: str | None,
    supersedes: str | None,
) -> str:
    record = store.append_review(
        subject_ref=CASE_SUBJECT,
        record_ref=CASE_RECORD,
        record_version=record_version,
        inputs=ProjectionInput(
            field_name=PUBLISHED_TEXT,
            data_class=DataClass.PUBLIC_SAFE_TEXT,
            text_value=case_row()[PUBLISHED_TEXT],
            relevance_reason=relevance_reason,
            explicitly_approved=True,
            is_published_version=True,
        ),
        reviewer_ref=REVIEWER,
        audit_ref=AUDIT,
        reviewed_at="2026-10-21T07:00:00+00:00",
        supersedes_decision_id=supersedes,
    )
    return record.decision_id


def rights_receipt(url: str, out: Path, before_files: dict[str, str]) -> dict[str, Any]:
    """Private append-only rights case; published artifacts must not change."""
    store = PrivacyRightsAccessStore(url)
    require(
        rights_request_outcome(
            RightsRequestKind.DELETION,
            affects_published_version=True,
            reviewed=True,
        )
        is RightsRequestOutcome.REVIEWED_PUBLIC_HOLD,
        "RIGHTS_OUTCOME_NOT_HOLD",
    )
    case = store.open_rights_case(
        subject_ref=CASE_SUBJECT,
        target_record_ref=CASE_RECORD,
        request_kind=RightsRequestKind.DELETION,
        affects_published_version=True,
        opened_at="2026-10-21T08:00:00+00:00",
        requester_ref="requester:dp304-canary",
        actor_ref=ACTOR,
    )
    require(case.latest_event_type == RightsCaseEventType.OPEN_PRIVATE.value, "RIGHTS_CASE_OPEN")
    held = store.append_rights_review_hold(
        case_id=case.case_id, actor_ref=ACTOR, occurred_at="2026-10-21T08:05:00+00:00"
    )
    require(
        held.latest_event_type == RightsCaseEventType.PUBLIC_HISTORY_HOLD_REQUIRED.value,
        "RIGHTS_HOLD_EVENT_MISSING",
    )
    require(file_hashes(out) == before_files, "RIGHTS_REQUEST_MUTATED_PUBLIC_ARTIFACTS")
    mutation_error = ""
    try:
        store.run("UPDATE privacy_rights_case SET request_kind = 'CORRECTION';")
    except RuntimeError as error:
        mutation_error = str(error)
    require("append-only" in mutation_error, "RIGHTS_LEDGER_MUTABLE")
    event_count = store.run(
        "SELECT count(*) FROM privacy_rights_case_event WHERE case_id = :'case_id';",
        case_id=case.case_id,
    )
    require("2" in str(event_count), "RIGHTS_EVENT_COUNT")
    return {
        "case_id": case.case_id,
        "outcome": RightsRequestOutcome.REVIEWED_PUBLIC_HOLD.value,
        "latest_event_type": held.latest_event_type,
        "event_count": 2,
        "public_artifacts_unchanged": True,
        "append_only_rejected": True,
    }


def access_receipt(url: str) -> dict[str, Any]:
    """Authorized read of a private excerpt with a content-free audit."""
    store = PrivacyRightsAccessStore(url)
    store.run(
        "INSERT INTO evidence (id, canonical_url, source_type, excerpt, rights_status) "
        "VALUES (:'id', 'https://example.test/dp304-canary-verbale', "
        "'PRIMARY_OFFICIAL', :'excerpt', 'UNKNOWN') ON CONFLICT (id) DO NOTHING;",
        id="evidence:dp304-canary",
        excerpt=SENTINELS["evidence_excerpt"],
    )

    def request(
        role: PrivateAccessRole,
        purpose: PrivateAccessPurpose,
        mode: PrivateAccessMode = PrivateAccessMode.READ,
    ) -> PrivateAccessRequest:
        return PrivateAccessRequest(
            actor_ref=ACTOR,
            role=role,
            purpose=purpose,
            data_class=DataClass.OPERATIONAL_PRIVATE,
            requested_fields=("excerpt",),
            mode=mode,
        )

    allowed = store.inspect_private_field(
        table_name="evidence",
        field_name="excerpt",
        record_ref="evidence:dp304-canary",
        request=request(PrivateAccessRole.TRIAGE_REVIEWER, PrivateAccessPurpose.EDITORIAL_REVIEW),
        occurred_at="2026-10-21T08:10:00+00:00",
    )
    require(allowed.allowed, "ACCESS_DENIED")
    require(allowed.value == SENTINELS["evidence_excerpt"], "ACCESS_WRONG_VALUE")
    wrong_purpose = store.inspect_private_field(
        table_name="evidence",
        field_name="excerpt",
        record_ref="evidence:dp304-canary",
        request=request(PrivateAccessRole.OPERATOR, PrivateAccessPurpose.EDITORIAL_REVIEW),
        occurred_at="2026-10-21T08:11:00+00:00",
    )
    require(not wrong_purpose.allowed, "ACCESS_NOT_BOUNDED_BY_ROLE")
    destructive = store.inspect_private_field(
        table_name="evidence",
        field_name="excerpt",
        record_ref="evidence:dp304-canary",
        request=request(
            PrivateAccessRole.TRIAGE_REVIEWER,
            PrivateAccessPurpose.EDITORIAL_REVIEW,
            PrivateAccessMode.DELETE,
        ),
        occurred_at="2026-10-21T08:12:00+00:00",
    )
    require(not destructive.allowed, "ACCESS_MODE_NOT_READ_ONLY")

    # Scan the complete persisted audit rows, not a projected subset: a column
    # that later starts carrying a value must fail this rehearsal.
    rows = store.run(
        "SELECT COALESCE(json_agg(row_to_json(audit))::text, '[]') FROM ("
        "SELECT * FROM private_access_audit_event ORDER BY occurred_at_text, event_id"
        ") audit;"
    )
    for name, sentinel in SENTINELS.items():
        require(sentinel not in rows, f"ACCESS_AUDIT_COPIED_BODY_{name}")
    require("excerpt" not in rows, "ACCESS_AUDIT_COPIED_FIELD_NAME")
    count = store.run("SELECT count(*) FROM private_access_audit_event;")
    require(int(str(count).strip()) == 3, "ACCESS_AUDIT_EVENT_COUNT_MISMATCH")
    outcomes = sorted(str(json.loads(rows)[index]["outcome"]) for index in range(3))
    require(outcomes.count("ALLOW_READ_ONLY") == 1, "ACCESS_AUDIT_OUTCOME_MISSING")
    return {
        "authorized_read": allowed.allowed,
        "wrong_purpose_denied": not wrong_purpose.allowed,
        "destructive_mode_denied": not destructive.allowed,
        "audit_event_count": 3,
        "audit_outcomes": outcomes,
        "audit_contains_body": False,
        "audit_contains_field_name": False,
    }


def revoke_and_replay(
    store: PrivacyPublicationDecisionStore,
    source: DecisionBoundSource,
    out: Path,
    first_decision: str,
) -> dict[str, Any]:
    """Relevance revoked: nothing republishes and stale artifacts are purged."""
    claim_paths = tuple(
        "/" + name for name in file_hashes(out) if name.startswith("claims/")
    )
    require(bool(claim_paths), "CLAIM_ARTIFACTS_MISSING")
    revoked = persist_review(
        store, record_version="v2", relevance_reason=None, supersedes=first_decision
    )
    source.record_version = "v2"
    payload = build_public_projection(source, generated_at=GENERATED_AT)
    require(payload["dossier_count"] == 0, "REVOKED_RECORD_STILL_PUBLIC")
    require(payload["omitted_count"] >= 1, "REVOCATION_NOT_RECORDED_AS_OMISSION")
    write_public_bundle(out, payload)
    surfaces = scan_release(out, PUBLIC_PATHS + claim_paths)
    for route in STABLE_PATHS:
        require(surfaces["http"][route]["status"] == 200, "REVOKED_SURFACE_NOT_200")
    require(surfaces["http"][RECORD_PATH]["status"] == 404, "REVOKED_RECORD_ROUTE_SERVED")
    for route in claim_paths:
        require(surfaces["http"][route]["status"] == 404, "REVOKED_CLAIM_FILE_STILL_SERVED")
    served = json.loads((out / "index.json").read_text(encoding="utf-8"))
    require(served["dossier_count"] == 0, "REVOKED_INDEX_STILL_PUBLISHES")
    require(not any(name.startswith("claims/") for name in file_hashes(out)),
            "REVOKED_CLAIM_ARTIFACT_REMAINS")

    # The private append-only history survives the revocation.
    lineage = store.run(
        "SELECT count(*) || ':' || string_agg(decision_action, ',' ORDER BY review_sequence) "
        "FROM privacy_publication_decision "
        "WHERE subject_ref = :'subject' AND record_ref = :'record';",
        subject=CASE_SUBJECT,
        record=CASE_RECORD,
    ).strip()
    require(lineage.startswith("2:") and "ALLOW" in lineage, "DECISION_HISTORY_LOST")
    original = store.run(
        "SELECT row_to_json(decision_row)::text FROM (SELECT * FROM "
        "privacy_publication_decision WHERE decision_action = 'ALLOW' "
        "ORDER BY review_sequence LIMIT 1) decision_row;"
    )
    require(first_decision in original, "ORIGINAL_DECISION_NOT_READABLE")
    source.record_version = "v1"
    stale = build_public_projection(source, generated_at=GENERATED_AT)["dossier_count"]
    require(stale == 0, "STALE_BINDING_REPUBLISHED")
    return {
        "revocation_decision_id": revoked,
        "dossier_count_after_revocation": payload["dossier_count"],
        "omitted_count": payload["omitted_count"],
        "removed_claim_paths": len(claim_paths),
        "claim_paths_http_404": True,
        "surfaces_after_revocation": surfaces["http"],
        "decision_lineage": lineage,
        "original_decision_readable": True,
        "stale_binding_dossier_count": stale,
    }


def run_canary() -> dict[str, Any]:
    selection = selection_receipt()
    with disposable_postgres() as url:
        store = PrivacyPublicationDecisionStore(url)
        first = persist_review(
            store, record_version="v1", relevance_reason="PUBLIC_ROLE", supersedes=None
        )
        source = DecisionBoundSource(case_row(), store)
        with tempfile.TemporaryDirectory(prefix="dp304-canary-release-") as temp:
            out = Path(temp) / "release"
            payload = build_public_projection(source, generated_at=GENERATED_AT)
            require(payload["dossier_count"] == 1, "APPROVED_RECORD_NOT_PUBLISHED")
            write_public_bundle(out, payload)
            before_files = file_hashes(out)
            surfaces = scan_release(out, PUBLIC_PATHS)
            require(
                all(response["status"] == 200 for response in surfaces["http"].values()),
                "PUBLISHED_SURFACE_UNEXPECTED_STATUS",
            )
            served = json.loads((out / "index.json").read_text(encoding="utf-8"))
            require(served["dossier_count"] == 1, "PUBLISHED_INDEX_NOT_SERVING")
            rights = rights_receipt(url, out, before_files)
            revocation = revoke_and_replay(store, source, out, first)
        access = access_receipt(url)
    return {
        "case": {
            "subject_ref": CASE_SUBJECT,
            "record_ref": CASE_RECORD,
            "data": "fictional",
            "policy_version": PRIVACY_POLICY_VERSION,
        },
        "selection": selection,
        "publication": {
            "dossier_count": payload["dossier_count"],
            "dataset_sha256": payload["dataset_sha256"],
            "files_written": len(before_files),
            "private_sentinels_absent": True,
            "surfaces": surfaces["http"],
        },
        "rights": rights,
        "access": access,
        "revocation": revocation,
        "limits": [
            "fictional case, disposable database, isolated release directory",
            "no lawful basis, retention period, real-person rights outcome or launch approval",
            "field matrix covers 14 classified fields of this case, not the whole projection allowlist",
        ],
    }


def main() -> int:
    try:
        receipt = run_canary()
    except RuntimeError as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASSED", "receipt": receipt}, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
