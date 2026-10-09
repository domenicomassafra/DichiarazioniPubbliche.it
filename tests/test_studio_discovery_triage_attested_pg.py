"""DP-417 exact off-DB signed identity + real isolated PostgreSQL writer."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.reviewer_identity_authority import (  # noqa: E402
    LocalFileReviewerIdentityAuthority, initialize_authority_root,
    provision_reviewer_credential,
)
from dichiarazioni_pubbliche.studio_discovery_triage_authority import (  # noqa: E402
    issue_triage_attestation,
)
from dichiarazioni_pubbliche.studio_discovery_triage_contract import (  # noqa: E402
    make_triage_request,
)
from dichiarazioni_pubbliche.studio_discovery_triage_store import (  # noqa: E402
    StudioDiscoveryTriageStore,
)
from dichiarazioni_pubbliche.studio_operator_queues import StudioOperatorQueues  # noqa: E402


class AttestedMigratedPostgresTests(unittest.TestCase):
    def test_exact_signed_request_persists_once_and_revoke_denies_followup(self):
        # Import inside the method to avoid separately collecting the borrowed
        # test class from this module. Both data and credentials are isolated.
        from tests.test_studio_discovery_triage_schema import DiscoveryTriageSchemaTests

        cluster = DiscoveryTriageSchemaTests
        cluster.setUpClass()
        try:
            setup = cluster("test_append_only_history_preserves_disposition")
            setup.setUp()
            with tempfile.TemporaryDirectory(prefix="dp417-signed-triage-") as tmp:
                root = Path(tmp) / "authority"
                initialize_authority_root(root)
                provision_reviewer_credential(
                    root, credential_id="signed-operator",
                    actor_ref="operator:verified", key_version="k1",
                    secret_hex="55" * 32,
                )
                authority = LocalFileReviewerIdentityAuthority(root)
                store = StudioDiscoveryTriageStore(database_url=cluster.url)
                args = dict(
                    collection_id="collection:one", hit_id=setup.hit,
                    request_key="dp417:signed:first", decision="NEEDS_REVIEW",
                    expected_revision=0, actor_ref="operator:verified",
                )
                proof = issue_triage_attestation(
                    authority, make_triage_request(**args), "signed-operator",
                )
                first = store.record_attested(
                    authority=authority, receipt_id=proof["receipt_id"], **args,
                )
                replay = store.record_attested(
                    authority=authority, receipt_id=proof["receipt_id"], **args,
                )
                self.assertEqual((first["result_code"], replay["result_code"]),
                                 ("CREATED", "REPLAY"))
                self.assertTrue(first["actor_attested"])
                self.assertTrue(replay["identity_receipt_verified"])
                self.assertFalse(first["publication_authority"])
                self.assertFalse(first["triage_action_authorized"])
                self.assertEqual(
                    cluster.require_sql(
                        "SELECT count(*) FROM research_discovery_triage_decision "
                        f"WHERE hit_id='{setup.hit}'"
                    ), "1",
                )
                history = StudioOperatorQueues(database_url=cluster.url).inspect_discovery_triage(
                    collection_id="collection:one", hit_id=setup.hit,
                )
                self.assertEqual(history["results"], [
                    {"revision": 1, "decision": "NEEDS_REVIEW"},
                ])
                self.assertFalse(history["reviewer_identity_attested"])
                self.assertNotIn("operator:verified", json.dumps(history))
                forged = args | {"decision": "REJECTED", "request_key": "dp417:signed:second",
                                 "expected_revision": 1}
                with self.assertRaises(ValueError):
                    store.record_attested(
                        authority=authority, receipt_id=proof["receipt_id"], **forged,
                    )
                authority.revoke("signed-operator")
                with self.assertRaises(ValueError):
                    store.record_attested(
                        authority=authority, receipt_id=proof["receipt_id"], **args,
                    )
                self.assertEqual(
                    cluster.require_sql(
                        "SELECT count(*) FROM research_discovery_triage_decision "
                        f"WHERE hit_id='{setup.hit}'"
                    ), "1",
                )
        finally:
            cluster.tearDownClass()


if __name__ == "__main__":
    unittest.main()
