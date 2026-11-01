"""DP-468 private authority store contracts and migration constraints."""

from datetime import timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dp468_authority_support import AuthorityFixture, disposition


class PublicStatementAuthorityTests(AuthorityFixture):
    def test_all_seven_current_authorities_require_two_reviews_and_third_audit(self):
        self.append_all()
        result = self.store.current_attestations(
            binding=self.binding, review_packet=self.packet,
            authority_review_packets=self.authority_packets,
            verify_authority_review=self.verify, now=self.now,
        )
        self.assertEqual(
            set(result),
            {"rights", "privacy", "retention", "attribution", "context", "wording", "publication"},
        )
        self.assertEqual(result["publication"]["release_pin_id"], "release-pin:dp468:first-batch")
        self.assertEqual(result["context"]["speech_act"], "DIRECT_ASSERTION")

    def test_missing_or_unverified_external_authority_never_projects(self):
        with self.assertRaisesRegex(ValueError, "DP468_EXTERNAL_AUTHORITY_REVIEW_INVALID"):
            self.append("RIGHTS", {
                "use_scope": "PUBLIC_EXACT_EXCERPT",
                "policy_version": "dp468-public-quote-rights-v1",
                "jurisdiction": "IT", "license_id": "CC-BY-4.0",
                "terms_url": "https://creativecommons.org/licenses/by/4.0/legalcode",
                "terms_sha256": "e" * 64, "attribution_required": True,
                "attribution_text": "Fonte: Senato.", "source_rights_ref": "rights:exact",
            }, evidence={"evidence_refs": ["evidence:rights"]},
               review_event_id="review:rights", verify=lambda _row: False)
        self.assertEqual(len(self.db.authority_events), 0)

    def test_publication_requires_three_distinct_authorized_model_dispositions(self):
        repeated = [
            disposition("PRIMARY_REVIEW", self.packet.primary),
            disposition("INDEPENDENT_REVIEW", self.packet.independent),
            disposition("THIRD_AUDIT", self.packet.primary),
        ]
        with self.assertRaisesRegex(ValueError, "DP468_RELEASE_DISPOSITIONS_NOT_INDEPENDENT"):
            self.append_all(release_dispositions=repeated)
        self.assertFalse(any(
            row["authority_kind"] == "PUBLICATION" for row in self.db.authority_events
        ))

    def test_expiry_and_current_source_binding_are_rechecked_on_every_read(self):
        self.append_all()
        expired = self.now + timedelta(days=8)
        self.assertIsNone(self.store.current_attestations(
            binding=self.binding, review_packet=self.packet,
            authority_review_packets=self.authority_packets,
            verify_authority_review=self.verify, now=expired,
        ))
        changed = {**self.binding, "quote_sha256": "f" * 64}
        self.assertIsNone(self.store.current_attestations(
            binding=changed, review_packet=self.packet,
            authority_review_packets=self.authority_packets,
            verify_authority_review=self.verify, now=self.now,
        ))

    def test_later_rights_revocation_invalidates_the_public_version(self):
        self.append_all()
        self.append("RIGHTS", {"reason_code": "SOURCE_RIGHTS_REVOKED"}, status="REVOKED")
        self.assertIsNone(self.store.current_attestations(
            binding=self.binding, review_packet=self.packet,
            authority_review_packets=self.authority_packets,
            verify_authority_review=self.verify, now=self.now,
        ))

    def test_tampered_authority_event_hash_fails_closed(self):
        self.append_all()
        self.db.authority_events[0]["payload"]["license_id"] = "OTHER"
        self.assertIsNone(self.store.current_attestations(
            binding=self.binding, review_packet=self.packet,
            authority_review_packets=self.authority_packets,
            verify_authority_review=self.verify, now=self.now,
        ))

    def test_authority_insert_requires_exact_database_readback(self):
        self.db.wrong_return = True
        with self.assertRaisesRegex(ValueError, "DP468_AUTHORITY_EVENT_NOT_PERSISTED"):
            self.append("RIGHTS", {
                "use_scope": "PUBLIC_EXACT_EXCERPT",
                "policy_version": "dp468-public-quote-rights-v1",
                "jurisdiction": "IT", "license_id": "CC-BY-4.0",
                "terms_url": "https://creativecommons.org/licenses/by/4.0/legalcode",
                "terms_sha256": "e" * 64, "attribution_required": True,
                "attribution_text": "Fonte: Senato.", "source_rights_ref": "rights:exact",
            }, evidence={"evidence_refs": ["evidence:rights"]},
               review_event_id="review:rights")


class PublicStatementAuthorityMigrationTests(unittest.TestCase):
    def test_private_append_only_migration_has_required_constraints(self):
        root = Path(__file__).resolve().parents[1]
        migration = (root / "db/migrations/20261101-add-public-statement-authority-ledgers.sql").read_text()
        self.assertIn("CHECK (status <> 'APPROVED' OR expires_at IS NOT NULL)", migration)
        self.assertGreaterEqual(migration.count("previous_integrity_sha256 IS NOT NULL"), 2)
        self.assertIn("record_visibility text NOT NULL DEFAULT 'PRIVATE' CHECK (record_visibility = 'PRIVATE')", migration)
        self.assertIn("BEFORE UPDATE OR DELETE ON", migration)
        self.assertIn("BEFORE TRUNCATE ON", migration)
        self.assertIn("CHECK (event_sequence <> 1 OR status = 'OPEN')", migration)
        for table in (
            "public_statement_authority_event",
            "public_statement_challenge_request",
            "public_statement_challenge_event",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", migration)


if __name__ == "__main__":
    unittest.main()
