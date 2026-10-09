"""DP-417: private operator triage annotations never become approval authority."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_discovery_triage_store import (  # noqa: E402
    StudioDiscoveryTriageStore,
    _WRITE_SQL,
)
from dichiarazioni_pubbliche.studio_discovery_triage_contract import (  # noqa: E402
    make_triage_request,
)
from dichiarazioni_pubbliche.studio_local_api import (  # noqa: E402
    _ALLOWED_PATHS, _dispatch, StudioLocalReaders,
)
from tools.check_studio_discovery_triage_sql import (  # noqa: E402
    synthetic_triage_sql, evaluate_triage_canary,
)
from dichiarazioni_pubbliche.reviewer_identity_authority import (  # noqa: E402
    LocalFileReviewerIdentityAuthority, initialize_authority_root,
    provision_reviewer_credential,
)
from dichiarazioni_pubbliche.studio_discovery_triage_authority import (  # noqa: E402
    issue_triage_attestation,
)

ARGS = {
    "collection_id": "research:1",
    "hit_id": "hit:1",
    "request_key": "request:one",
    "decision": "NEEDS_REVIEW",
    "expected_revision": 0,
    "actor_ref": "operator:unattested",
}


class FakeStore(StudioDiscoveryTriageStore):
    def __init__(self, result="CREATED", *, error=None, mutate=None):
        self.result = result
        self.error = error
        self.mutate = mutate
        self.calls = []

    def run(self, sql, **kwargs):
        self.calls.append((sql, kwargs))
        if self.error is not None:
            raise self.error
        row = {
            "result_code": self.result,
            "collection_id": kwargs["collection_id"],
            "hit_id": kwargs["hit_id"],
            "request_key": kwargs["request_key"],
            "decision": kwargs["decision"],
            "expected_revision": kwargs["expected_revision"],
            "payload_sha256": kwargs["payload_sha256"],
            "revision": None if self.result == "SCOPE_NOT_FOUND" else 1,
        }
        if self.mutate:
            row.update(self.mutate)
        return json.dumps(row)


class StudioTriageStoreTests(unittest.TestCase):
    def test_transaction_scope_cas_advisory_and_no_side_effect(self):
        sql = _WRITE_SQL
        self.assertIn("BEGIN;", sql)
        self.assertIn("COMMIT;", sql)
        self.assertIn("pg_advisory_xact_lock(", sql)
        self.assertIn("run.id = hit.run_id", sql)
        self.assertIn("manifest.id = run.manifest_id", sql)
        self.assertIn("collection.id = :'collection_id'", sql)
        self.assertIn("hit.id = :'hit_id'", sql)
        self.assertIn("WHERE request_key = :'request_key'", sql)
        self.assertIn("current_rev.revision = :'expected_revision'::bigint", sql)
        self.assertIn("ON CONFLICT DO NOTHING", sql)
        self.assertIn("matched_replay", sql)
        self.assertNotIn("UPDATE research_discovery_hit", sql)
        self.assertNotIn("DELETE FROM research_discovery_hit", sql)
        self.assertNotIn("INSERT INTO content_item", sql)
        self.assertNotIn("PUBLICATION_APPROVED", sql)

    def test_created_and_replay_are_safe_annotations_only(self):
        for code in ("CREATED", "REPLAY"):
            with self.subTest(code=code):
                store = FakeStore(code)
                value = store.record(**ARGS)
                self.assertEqual(value["result_code"], code)
                self.assertEqual(value["revision"], 1)
                self.assertFalse(value["publication_authority"])
                self.assertFalse(value["triage_action_authorized"])
                self.assertFalse(value["capture_authorized"])
                self.assertFalse(value["actor_attested"])
                self.assertTrue(value["private_only"])
                query, params = store.calls[0]
                self.assertEqual(query, _WRITE_SQL)
                self.assertEqual(params["request_key"], ARGS["request_key"])
                self.assertEqual(
                    params["payload_sha256"],
                    make_triage_request(**ARGS).payload_sha256,
                )
                self.assertNotIn("url", json.dumps(value).lower())

    def test_explicit_safe_conflicts_no_private_data(self):
        for code in ("SCOPE_NOT_FOUND", "REVISION_CONFLICT", "IDEMPOTENCY_CONFLICT"):
            with self.subTest(code=code):
                value = FakeStore(code).record(**ARGS)
                self.assertEqual(value["result_code"], code)
                self.assertEqual(value["revision"], None if code == "SCOPE_NOT_FOUND" else 1)
                self.assertFalse(value["publication_authority"])
        with self.assertRaisesRegex(RuntimeError, "STUDIO_TRIAGE_STORE_UNAVAILABLE") as raised:
            FakeStore(error=RuntimeError("DATABASE_URL=PASSWORDSECRET")).record(**ARGS)
        self.assertNotIn("PASSWORDSECRET", str(raised.exception))

    def test_invalid_unsafe_input_or_storage_response_fails_closed(self):
        for invalid in (
            {"decision": "APPROVED"},
            {"decision": "PUBLISH"},
            {"expected_revision": -1},
            {"expected_revision": True},
            {"request_key": "x'\nDROP TABLE content_item;"},
            {"actor_ref": "evil@example.org\n"},
            {"hit_id": "other; SELECT password"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                FakeStore().record(**(ARGS | invalid))
        for bad in (
            {"result_code": "APPROVED"},
            {"collection_id": "research:2"},
            {"revision": True},
            {"payload_sha256": "b" * 64},
            {"revision": -1},
        ):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "RESULT_INVALID"):
                FakeStore(mutate=bad).record(**ARGS)

    def test_real_sql_fixture_generator_covers_all_collision_states(self):
        sql = synthetic_triage_sql()
        self.assertIn("CREATE TEMP TABLE research_discovery_triage_decision", sql)
        self.assertIn("SET LOCAL search_path TO pg_temp, public", sql)
        self.assertEqual(sql.count("ROLLBACK;"), 1)
        self.assertNotIn("CREATE TABLE research_discovery_triage_decision", sql)
        rows = [
            {"result_code": status, "revision": revision,
             "hit_id": "hit:fixture", "collection_id": "research:fixture"}
            for status, revision in (
                ("CREATED", 1), ("REPLAY", 1), ("IDEMPOTENCY_CONFLICT", 1),
                ("REVISION_CONFLICT", 1), ("CREATED", 2),
                ("REVISION_CONFLICT", 2), ("SCOPE_NOT_FOUND", None),
            )
        ]
        rows[-1]["collection_id"] = "research:absent"
        output = "\n".join(json.dumps(row) for row in rows) + "\nDP417_TEMP_COUNT=2"
        self.assertEqual(evaluate_triage_canary(output)["status"], "PASS_PG_TEMP_ROLLBACK")
        with self.assertRaisesRegex(RuntimeError, "CAS_OR_REPLAY_FAILED"):
            evaluate_triage_canary(output.replace('"REPLAY"', '"CREATED"'))

    def test_attested_record_requires_exact_active_credential_bound_to_request(self):
        with tempfile.TemporaryDirectory() as root:
            private = Path(root) / "authority"
            initialize_authority_root(private)
            provision_reviewer_credential(
                private, credential_id="reviewer-1",
                actor_ref=ARGS["actor_ref"], key_version="k1",
                secret_hex="33" * 32,
            )
            authority = LocalFileReviewerIdentityAuthority(private)
            request = make_triage_request(**ARGS)
            attestation = issue_triage_attestation(authority, request, "reviewer-1")
            store = FakeStore()
            created = store.record_attested(
                authority=authority,
                receipt_id=attestation["receipt_id"], **ARGS,
            )
            self.assertEqual(created["result_code"], "CREATED")
            self.assertTrue(created["actor_attested"])
            self.assertTrue(created["identity_receipt_verified"])
            self.assertEqual(created["attestation_receipt_id"], attestation["receipt_id"])
            self.assertFalse(created["triage_action_authorized"])
            self.assertFalse(created["publication_authority"])
            self.assertFalse(created["capture_authorized"])
            self.assertEqual(len(store.calls), 1)
            for changed in (
                {"decision": "REJECTED"},
                {"actor_ref": "reviewer:impostor"},
                {"expected_revision": 1},
                {"request_key": "request:other"},
            ):
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    store.record_attested(
                        authority=authority, receipt_id=attestation["receipt_id"],
                        **(ARGS | changed),
                    )
                self.assertEqual(len(store.calls), 1)
            authority.revoke("reviewer-1")
            with self.assertRaises(ValueError):
                store.record_attested(
                    authority=authority, receipt_id=attestation["receipt_id"],
                    **ARGS,
                )
            self.assertEqual(len(store.calls), 1)

    def test_attested_record_conflict_never_reports_action_authority(self):
        with tempfile.TemporaryDirectory() as root:
            private = Path(root) / "authority"
            initialize_authority_root(private)
            provision_reviewer_credential(
                private, credential_id="operator-1",
                actor_ref=ARGS["actor_ref"], key_version="k1",
                secret_hex="44" * 32,
            )
            authority = LocalFileReviewerIdentityAuthority(private)
            req = make_triage_request(**ARGS)
            proof = issue_triage_attestation(authority, req, "operator-1")
            store = FakeStore("IDEMPOTENCY_CONFLICT")
            response = store.record_attested(
                authority=authority, receipt_id=proof["receipt_id"], **ARGS,
            )
            self.assertEqual(response["result_code"], "IDEMPOTENCY_CONFLICT")
            self.assertFalse(response["actor_attested"])
            self.assertTrue(response["identity_receipt_verified"])
            self.assertIsNone(response["attestation_receipt_id"])
            self.assertFalse(response["publication_authority"])
            self.assertFalse(response["triage_action_authorized"])

    def test_local_http_remains_strictly_read_only(self):
        self.assertNotIn("/v1/discovery/triage", _ALLOWED_PATHS)
        self.assertNotIn("/v1/discovery/review", _ALLOWED_PATHS)
        with self.assertRaisesRegex(ValueError, "STUDIO_LOCAL_PATH_NOT_ALLOWED"):
            _dispatch(
                StudioLocalReaders(corpus=None, captures=None, candidates=None),
                "/v1/discovery/triage", ARGS,
            )


if __name__ == "__main__":
    unittest.main()
