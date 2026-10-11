"""DP-518: dry-run multi-consumer distributed withdrawal consistency checks."""

import json
import sqlite3
import unittest
from dataclasses import replace
from datetime import datetime, timezone

from dichiarazioni_pubbliche.revocation_epoch_fence import (
    IsolatedPublicationEpochStore,
    MaterialEpoch,
    PublicationEpochTicket,
    RevocationFenceHeld,
    _ticket_fingerprint,
)
from dichiarazioni_pubbliche.distributed_withdrawal_audit_v1 import (
    REQUIRED_PUBLIC_CONSUMERS,
    ReleaseArtifact,
    ReleaseReadback,
    ReleaseSnapshot,
    PublicReadback,
    audit_withdrawal_readback,
    release_inventory_sha256,
)

H = "a" * 64
HB = "b" * 64
J = "c" * 64


def fixture(*, withdrawn=True):
    deps = (MaterialEpoch("rights:1", 4, H), MaterialEpoch("source:1", 2, HB))
    ticket = PublicationEpochTicket(
        "release:1", deps, _ticket_fingerprint("release:1", deps)
    )
    artifacts = tuple(
        ReleaseArtifact(
            "person:1",
            surface,
            "ABSENT" if withdrawn else "PRESENT",
            None if withdrawn else J,
            ("rights:1", "source:1"),
        )
        for surface in sorted(REQUIRED_PUBLIC_CONSUMERS)
    )
    snapshot = ReleaseSnapshot(
        "release:1",
        "host:1",
        H,
        HB,
        J,
        H,
        J,
        ticket,
        artifacts,
    )
    probes = tuple(
        PublicReadback(
            "person:1",
            surface,
            "host:1",
            "generation:" + J,
            404 if withdrawn else 200,
            None if withdrawn else J,
        )
        for surface in sorted(REQUIRED_PUBLIC_CONSUMERS)
    )
    return snapshot, probes


def release_readback(snapshot):
    return ReleaseReadback(
        snapshot.release_id,
        snapshot.host_ref,
        snapshot.code_sha256,
        snapshot.mirror_sha256,
        snapshot.migration_sha256,
        snapshot.policy_sha256,
        snapshot.generation_sha256,
        snapshot.fence.fingerprint,
        release_inventory_sha256(snapshot.artifacts),
    )


class DistributedWithdrawalAuditTests(unittest.TestCase):
    def audit(self, manifest=None, probes=None, **changes):
        source, readback = fixture()
        snapshot = manifest or source
        return audit_withdrawal_readback(
            snapshot,
            readback if probes is None else probes,
            revoked_dependencies=("rights:1",),
            observed_release=changes.pop("observed_release", release_readback(snapshot)),
            **changes,
        )

    def test_exact_release_readback_rejects_rollback_and_inventory_tamper(self):
        manifest, probes = fixture()
        observed = release_readback(manifest)
        for changed in (
            replace(manifest, code_sha256=HB),
            replace(manifest, mirror_sha256=H),
            replace(manifest, migration_sha256=H),
            replace(manifest, policy_sha256=HB),
            replace(manifest, generation_sha256=H),
            replace(
                manifest,
                artifacts=(
                    replace(manifest.artifacts[0], dependency_refs=("rights:1",)),
                    *manifest.artifacts[1:],
                ),
            ),
        ):
            with self.subTest(changed=changed):
                audit = self.audit(changed, probes, observed_release=observed)
                self.assertEqual(audit.status, "READBACK_UNTRUSTED_OR_DRIFT")
                self.assertIn("RELEASE_IDENTITY_READBACK_DRIFT", audit.sanitized_reason_codes)
                self.assertFalse(audit.release_authorized)
        for observed_wrong in (
            replace(observed, release_id="release:rollback"),
            replace(observed, host_ref="host:rollback"),
            replace(observed, fence_fingerprint=H),
            replace(observed, inventory_sha256=H),
        ):
            with self.subTest(observed_wrong=observed_wrong):
                outcome = self.audit(manifest, probes, observed_release=observed_wrong)
                self.assertEqual(outcome.status, "READBACK_UNTRUSTED_OR_DRIFT")

    def test_missing_or_malformed_release_readback_refuses(self):
        manifest, probes = fixture()
        with self.assertRaisesRegex(ValueError, "DP518_RELEASE_READBACK_INVALID"):
            self.audit(manifest, probes, observed_release=None)
        with self.assertRaisesRegex(ValueError, "DP518_RELEASE_READBACK_INVALID"):
            self.audit(
                manifest,
                probes,
                observed_release=replace(release_readback(manifest), code_sha256="invalid"),
            )

    def test_disjoint_revoked_dependencies_do_not_cross_contaminate_entities(self):
        manifest, probes = fixture()

        def entity_rows(entity, dependency):
            return tuple(
                replace(row, entity_id=entity, dependency_refs=(dependency,))
                for row in manifest.artifacts
            )

        def entity_probes(entity):
            return tuple(replace(row, entity_id=entity) for row in probes)

        split = replace(
            manifest,
            artifacts=entity_rows("person:1", "rights:1") + entity_rows("person:2", "source:1"),
        )
        outcome = audit_withdrawal_readback(
            split,
            entity_probes("person:1") + entity_probes("person:2"),
            revoked_dependencies=("rights:1", "source:1"),
            observed_release=release_readback(split),
        )
        self.assertEqual(outcome.status, "CONSISTENT_UNATTESTED")
        self.assertEqual(outcome.surface_count, len(REQUIRED_PUBLIC_CONSUMERS) * 2)

        # The relaxed disjoint check must not hide a source:1 dependency omitted
        # by one public surface of person:2 while others still link source:1.
        wrong = replace(
            split,
            artifacts=(
                *split.artifacts[:len(REQUIRED_PUBLIC_CONSUMERS)],
                replace(split.artifacts[len(REQUIRED_PUBLIC_CONSUMERS)], dependency_refs=("rights:1",)),
                *split.artifacts[len(REQUIRED_PUBLIC_CONSUMERS) + 1:],
            ),
        )
        drift = audit_withdrawal_readback(
            wrong,
            entity_probes("person:1") + entity_probes("person:2"),
            revoked_dependencies=("rights:1", "source:1"),
            observed_release=release_readback(wrong),
        )
        self.assertEqual(drift.status, "READBACK_UNTRUSTED_OR_DRIFT")
        self.assertIn("PUBLIC_CONSUMER_DEPENDENCY_INCOMPLETE", drift.sanitized_reason_codes)

    def test_multi_revocation_cannot_claim_consistency_when_one_dependency_is_unmapped(self):
        """Every requested revoked dependency needs a public dependency-graph readback."""
        manifest, probes = fixture()
        # The release has both rights:1 and source:1 in its valid epoch
        # ticket, but all twelve artifact rows accidentally omit source:1.
        # 404 responses and self-consistent release hashes cannot conceal
        # that missing coverage in a multi-dependency withdrawal.
        incomplete = replace(
            manifest,
            artifacts=tuple(
                replace(row, dependency_refs=("rights:1",))
                for row in manifest.artifacts
            ),
        )
        result = audit_withdrawal_readback(
            incomplete,
            probes,
            revoked_dependencies=("rights:1", "source:1"),
            observed_release=release_readback(incomplete),
        )
        self.assertEqual(result.status, "INCOMPLETE_PUBLIC_COVERAGE")
        self.assertIn(
            "REVOCATION_NOT_LINKED_TO_PUBLIC_ENTITY", result.sanitized_reason_codes
        )
        self.assertFalse(result.release_authorized)
        self.assertFalse(result.withdrawal_verified_on_live_host)

    def test_cached_old_200_on_edge_is_unsafe_even_with_clean_origin_generation(self):
        manifest, probes = fixture()
        edge = next(row for row in probes if row.surface == "CACHE_EDGE")
        stale_edge = replace(edge, status_code=200, body_sha256=J)
        other_probes = tuple(stale_edge if row.surface == "CACHE_EDGE" else row for row in probes)
        outcome = self.audit(manifest, other_probes)
        self.assertEqual(outcome.status, "UNSAFE_PUBLIC_VISIBILITY")
        self.assertIn("CACHE_EDGE", outcome.unsafe_surfaces)
        self.assertFalse(outcome.cache_purge_verified)

    def test_complete_withdrawal_remains_contract_only_without_real_authority(self):
        outcome = self.audit()
        self.assertEqual(outcome.status, "CONSISTENT_UNATTESTED")
        self.assertEqual(outcome.surface_count, len(REQUIRED_PUBLIC_CONSUMERS))
        self.assertFalse(outcome.release_authorized)
        self.assertFalse(outcome.publication_authority)
        self.assertFalse(outcome.withdrawal_verified_on_live_host)
        self.assertFalse(outcome.cache_purge_verified)
        self.assertEqual(outcome.unsafe_surfaces, ())
        self.assertNotIn(
            "host:1",
            json.dumps(outcome.__dict__)
            if hasattr(outcome, "__dict__")
            else str(outcome),
        )

    def test_revoked_old_200_quote_refuses_even_if_hash_matches(self):
        manifest, probes = fixture()
        probe = replace(probes[0], status_code=200, body_sha256=J)
        result = self.audit(manifest, (probe, *probes[1:]))
        self.assertEqual(result.status, "UNSAFE_PUBLIC_VISIBILITY")
        self.assertIn(probes[0].surface, result.unsafe_surfaces)
        self.assertFalse(result.release_authorized)

    def test_no_cache_or_search_probe_is_incomplete_not_success(self):
        manifest, probes = fixture()
        result = self.audit(manifest, probes[:-1])
        self.assertEqual(result.status, "INCOMPLETE_PUBLIC_COVERAGE")
        self.assertFalse(result.withdrawal_verified_on_live_host)

    def test_wrong_release_generation_or_host_rejected(self):
        manifest, probes = fixture()
        for mutated in (
            replace(probes[0], host_ref="host:other"),
            replace(probes[0], generation_ref="generation:old"),
        ):
            with self.subTest(mutated=mutated):
                result = self.audit(manifest, (mutated, *probes[1:]))
                self.assertNotEqual(result.status, "CONSISTENT_UNATTESTED")

    def test_duplicate_or_unknown_consumer_refuses(self):
        manifest, probes = fixture()
        for edited in (
            (probes[0], *probes),
            (replace(probes[0], surface="UNKNOWN"), *probes[1:]),
        ):
            with self.subTest(edit=edited[0].surface), self.assertRaises(ValueError):
                self.audit(manifest, edited)

    def test_manifest_missing_surface_or_material_dependency_blocks(self):
        manifest, probes = fixture()
        with self.assertRaisesRegex(ValueError, "READBACK_UNSCOPED"):
            self.audit(replace(manifest, artifacts=manifest.artifacts[:-1]), probes)
        cases = (
            replace(
                manifest,
                artifacts=(
                    replace(manifest.artifacts[0], dependency_refs=("source:1",)),
                    *manifest.artifacts[1:],
                ),
            ),
            replace(
                manifest,
                artifacts=(
                    replace(manifest.artifacts[0], state="PRESENT", artifact_sha256=J),
                    *manifest.artifacts[1:],
                ),
            ),
        )
        for changed in cases:
            with self.subTest(changed=changed.artifacts[0].surface):
                result = self.audit(changed, probes)
                self.assertNotEqual(result.status, "CONSISTENT_UNATTESTED")

    def test_fence_tamper_or_epoch_conflict_denied(self):
        manifest, probes = fixture()
        with self.assertRaises(ValueError):
            self.audit(
                replace(manifest, fence=replace(manifest.fence, fingerprint=J)), probes
            )
        actual = (MaterialEpoch("rights:1", 5, H), MaterialEpoch("source:1", 2, HB))
        new_fence = PublicationEpochTicket(
            "release:1", actual, _ticket_fingerprint("release:1", actual)
        )
        outcome = self.audit(manifest, probes, current_fence=new_fence)
        self.assertEqual(outcome.status, "STALE_REVOCATION_EPOCH")

    def test_missing_external_cdn_cache_proof_always_stays_unattested(self):
        manifest, probes = fixture()
        self.assertEqual(self.audit(manifest, probes).status, "CONSISTENT_UNATTESTED")

    def test_redirect_and_provider_outage_never_look_like_absence(self):
        manifest, probes = fixture()
        for status in (200, 302, 503):
            altered = replace(
                probes[0], status_code=status, body_sha256=J if status == 200 else None
            )
            with self.subTest(status=status):
                self.assertNotEqual(
                    self.audit(manifest, (altered, *probes[1:])).status,
                    "CONSISTENT_UNATTESTED",
                )

    def test_public_body_and_privacy_fields_never_in_audit_receipt(self):
        result = self.audit()
        self.assertFalse(hasattr(result, "body"))
        self.assertFalse(hasattr(result, "source_text"))
        self.assertEqual(result.sanitized_reason_codes, ())

    def test_dp320_isolated_revocation_refuses_stale_reader_despite_old_metadata(self):
        # A correct offline report never replaces the real transactional read fence.
        connection = sqlite3.connect(":memory:")
        try:
            store = IsolatedPublicationEpochStore(connection)
            store.init_fixture_schema()
            store.register_fixture_source("rights:1", H)
            store.register_fixture_source("source:1", HB)
            ticket = store.mint(
                release_id="release:1", dependency_ids=("rights:1", "source:1")
            )
            store.publish_reference(ticket=ticket, artifact_sha256=J)
            self.assertTrue(store.check_served(ticket, J))
            manifest, probes = fixture()
            manifest = replace(manifest, fence=ticket)
            self.assertEqual(
                self.audit(manifest, probes).status, "CONSISTENT_UNATTESTED"
            )
            store.revoke(
                source_id="rights:1",
                event_id="revoke:1",
                reason="RIGHTS_WITHDRAWN",
                now=datetime(2026, 10, 11, tzinfo=timezone.utc),
            )
            with self.assertRaises(RevocationFenceHeld):
                store.check_served(ticket, J)
            # The supplied probe is unchanged: real CDN withdrawal remains unproved.
            self.assertEqual(
                self.audit(manifest, probes).status, "CONSISTENT_UNATTESTED"
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
