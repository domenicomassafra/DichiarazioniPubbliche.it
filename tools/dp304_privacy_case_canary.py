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
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.dp304_case_fixture import (  # noqa: E402
    CASE_FIELDS,
    CASE_RECORD,
    CASE_SUBJECT,
    SENTINELS,
    case_row,
)
from dichiarazioni_pubbliche.policy.privacy_policy import (  # noqa: E402
    PRIVACY_POLICY_VERSION,
    DataClass,
    PrivateAccessMode,
    PrivateAccessPurpose,
    PrivateAccessRequest,
    PrivateAccessRole,
    ProjectionInput,
    RightsRequestKind,
    RightsRequestOutcome,
    assert_no_trait_inference,
    decide_projection,
    minimize_public_fieldset,
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


def require(condition: object, code: str) -> None:
    if not condition:
        raise RuntimeError("DP304_CANARY_" + code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bin(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for candidate in sorted(Path("/usr/lib/postgresql").glob(f"*/bin/{name}")):
        return str(candidate)
    raise RuntimeError("DP304_CANARY_POSTGRES_UNAVAILABLE_" + name)


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise RuntimeError(
            "DP304_CANARY_COMMAND_FAILED_" + (detail[-1] if detail else "unknown")
        )
    return proc.stdout


@contextmanager
def disposable_postgres() -> Iterator[str]:
    """Fresh schema plus replay-safe additive privacy migrations."""
    with tempfile.TemporaryDirectory(prefix="dp304-case-canary-") as temp:
        base = Path(temp)
        data_dir = base / "data"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        _run([_bin("initdb"), "-D", str(data_dir), "--username=postgres",
              "--auth=trust", "--encoding=UTF8", "--no-locale"])
        started = False
        try:
            _run([_bin("pg_ctl"), "-D", str(data_dir), "-l", str(base / "server.log"),
                  "-o", f"-F -p {port} -h 127.0.0.1 -k {base}", "-w", "start"])
            started = True
            admin = f"postgresql://postgres@127.0.0.1:{port}/postgres"
            _run([_bin("psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1", "--dbname", admin,
                  "-c", "CREATE DATABASE dp304_case_canary;"])
            url = f"postgresql://postgres@127.0.0.1:{port}/dp304_case_canary"
            _run([_bin("psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1", "--dbname", url,
                  "-f", str(ROOT / "db/schema.v1.sql")])
            for _ in range(2):
                _run([_bin("psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1", "--dbname", url,
                      "-f", str(ROOT / "db/migrations/"
                               "20261007-add-privacy-rights-access-ledgers.sql")])
            yield url
        finally:
            if started:
                subprocess.run([_bin("pg_ctl"), "-D", str(data_dir), "-m", "immediate",
                                "-w", "stop"], capture_output=True, text=True, check=False)


def selection_receipt() -> dict[str, Any]:
    """Deny-by-default classification of every field in the fictional case."""
    decisions: dict[str, str] = {}
    for field, data_class, reason, approved, expect_public in CASE_FIELDS:
        decision = decide_projection(
            ProjectionInput(
                field_name=field,
                data_class=data_class,
                text_value=SENTINELS.get(field),
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
    return {
        "policy_version": PRIVACY_POLICY_VERSION,
        "field_decisions": decisions,
        "published_field_count": sum(1 for value in decisions.values() if value.startswith("ALLOW")),
        "refused_or_held_field_count": sum(
            1 for value in decisions.values() if not value.startswith("ALLOW")
        ),
        "public_figure_only_relevance": public_figure_only.decision.value,
        "mislabelled_private_field": mislabelled.decision.value,
        "minimized_public_fieldset": list(minimized),
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
        self.last_reasons = replay.blockers
        return replay.allowed


def materialize(out: Path, source: DecisionBoundSource) -> dict[str, Any]:
    payload = build_public_projection(source, generated_at=GENERATED_AT)
    write_public_bundle(out, payload)
    return payload


def scan_release(out: Path) -> dict[str, Any]:
    """Every written public file plus every loopback response, scanned for sentinels."""
    leaks: list[str] = []
    files: dict[str, str] = {}
    for path in sorted(out.rglob("*")):
        if path.is_file():
            body = path.read_bytes()
            files[path.relative_to(out).as_posix()] = digest(body)
            for name, sentinel in SENTINELS.items():
                if sentinel.encode() in body:
                    leaks.append(f"FILE:{path.name}:{name}")
    responses: dict[str, dict[str, Any]] = {}
    with build_server(out / "index.json", host="127.0.0.1", port=0, static_dir=out) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for route in PUBLIC_PATHS:
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    conn.request("GET", route, headers={"Accept-Encoding": "identity"})
                    response = conn.getresponse()
                    body = response.read(1_000_001)
                finally:
                    conn.close()
                responses[route] = {"status": response.status, "sha256": digest(body)}
                for name, sentinel in SENTINELS.items():
                    if sentinel.encode() in body:
                        leaks.append(f"HTTP:{route}:{name}")
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


def rights_receipt(url: str, before: dict[str, Any], out: Path) -> dict[str, Any]:
    """Private append-only rights case; published history must not change."""
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
    require(case.latest_event_type == RightsCaseEventType.OPEN_PRIVATE.value, "RIGHT_CASE_OPEN")
    held = store.append_rights_review_hold(
        case_id=case.case_id, actor_ref=ACTOR, occurred_at="2026-10-21T08:05:00+00:00"
    )
    require(
        held.latest_event_type == RightsCaseEventType.PUBLIC_HISTORY_HOLD_REQUIRED.value,
        "RIGHTS_HOLD_EVENT_MISSING",
    )
    after_bundle = json.loads((out / "index.json").read_text(encoding="utf-8"))
    require(
        after_bundle["dataset_sha256"] == before["dataset_sha256"],
        "RIGHTS_REQUEST_MUTATED_PUBLIC_HISTORY",
    )
    append_only_rejected = False
    try:
        store.run("UPDATE privacy_rights_case SET request_kind = 'CORRECTION';")
    except RuntimeError:
        append_only_rejected = True
    require(append_only_rejected, "RIGHTS_LEDGER_MUTABLE")

    columns = store.run(
        "SELECT count(*) FROM privacy_rights_case_event WHERE case_id = :'case_id';",
        case_id=case.case_id,
    )
    return {
        "case_id": case.case_id,
        "outcome": RightsRequestOutcome.REVIEWED_PUBLIC_HOLD.value,
        "latest_event_type": held.latest_event_type,
        "event_count": int(columns.strip()),
        "public_dataset_unchanged": True,
        "append_only_rejected": append_only_rejected,
    }


def access_receipt(url: str) -> dict[str, Any]:
    """Authorized read of a private excerpt with a content-free audit row."""
    store = PrivacyRightsAccessStore(url)
    store.run(
        "INSERT INTO evidence (id, canonical_url, source_type, excerpt, rights_status) "
        "VALUES (:'id', 'https://example.test/dp304-canary-verbale', "
        "'PRIMARY_OFFICIAL', :'excerpt', 'UNKNOWN');",
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
        request=request(
            PrivateAccessRole.TRIAGE_REVIEWER, PrivateAccessPurpose.EDITORIAL_REVIEW
        ),
        occurred_at="2026-10-21T08:10:00+00:00",
    )
    require(allowed.allowed, "ACCESS_DENIED")
    require(allowed.value == SENTINELS["evidence_excerpt"], "ACCESS_WRONG_VALUE")
    wrong_purpose = store.inspect_private_field(
        table_name="evidence",
        field_name="excerpt",
        record_ref="evidence:dp304-canary",
        request=request(
            PrivateAccessRole.OPERATOR, PrivateAccessPurpose.EDITORIAL_REVIEW
        ),
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
    audit_rows = store.run(
        "SELECT COALESCE(json_agg(json_build_object('purpose', purpose_ref, "
        "'outcome', outcome, 'field_count', requested_field_count))::text, '[]') "
        "FROM private_access_audit_event;"
    )
    audit_text = str(audit_rows)
    for name, sentinel in SENTINELS.items():
        require(sentinel not in audit_text, f"ACCESS_AUDIT_COPIED_BODY_{name}")
    require("excerpt" not in audit_text, "ACCESS_AUDIT_COPIED_FIELD_NAME")
    return {
        "authorized_read": allowed.allowed,
        "wrong_purpose_denied": not wrong_purpose.allowed,
        "destructive_mode_denied": not destructive.allowed,
        "audit_event_count": 3,
        "audit_contains_body": False,
        "audit_contains_field_name": False,
    }


def revoke_and_replay(
    store: PrivacyPublicationDecisionStore,
    source: DecisionBoundSource,
    out: Path,
    first_decision: str,
) -> dict[str, Any]:
    """Relevance revoked: the published binding is stale, so nothing republishes."""
    revoked = persist_review(
        store, record_version="v2", relevance_reason=None, supersedes=first_decision
    )
    source.record_version = "v2"
    payload = build_public_projection(source, generated_at=GENERATED_AT)
    require(payload["dossier_count"] == 0, "REVOKED_RECORD_STILL_PUBLIC")
    require(payload["omitted_count"] >= 1, "REVOCATION_NOT_RECORDED_AS_OMISSION")
    lineage = store.run(
        "SELECT count(*) || ':' || "
        "string_agg(decision_action, ',' ORDER BY review_sequence) "
        "FROM privacy_publication_decision "
        "WHERE subject_ref = :'subject' AND record_ref = :'record';",
        subject=CASE_SUBJECT,
        record=CASE_RECORD,
    ).strip()
    require(lineage.startswith("2:") and "ALLOW" in lineage, "DECISION_HISTORY_LOST")
    source.record_version = "v1"
    stale = build_public_projection(source, generated_at=GENERATED_AT)["dossier_count"]
    require(stale == 0, "STALE_BINDING_REPUBLISHED")
    return {
        "revocation_decision_id": revoked,
        "dossier_count_after_revocation": payload["dossier_count"],
        "omitted_count": payload["omitted_count"],
        "decision_lineage": lineage,
        "stale_binding_dossier_count": stale,
    }


def run_canary() -> dict[str, Any]:
    require(SENTINELS["raw_transcript"] not in json.dumps(case_row()["normalized_claim"]),
            "FIXTURE_CONTAMINATED_CLAIM")
    selection = selection_receipt()
    with disposable_postgres() as url:
        store = PrivacyPublicationDecisionStore(url)
        first = persist_review(
            store, record_version="v1", relevance_reason="PUBLIC_ROLE", supersedes=None
        )
        source = DecisionBoundSource(case_row(), store)
        with tempfile.TemporaryDirectory(prefix="dp304-canary-release-") as temp:
            out = Path(temp) / "release"
            payload = materialize(out, source)
            require(payload["dossier_count"] == 1, "APPROVED_RECORD_NOT_PUBLISHED")
            surfaces = scan_release(out)
            rights = rights_receipt(url, payload, out)
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
            "private_sentinels_absent": True,
            "surfaces": surfaces,
        },
        "rights": rights,
        "access": access,
        "revocation": revocation,
        "limits": [
            "fictional case, disposable database, isolated release directory",
            "no lawful basis, retention period, real-person rights outcome or launch approval",
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
