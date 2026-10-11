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
    ReleaseSnapshot,
    PublicReadback,
    audit_withdrawal_readback,
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


class DistributedWithdrawalAuditTests(unittest.TestCase):
    def audit(self, manifest=None, probes=None, **changes):
        source, readback = fixture()
        return audit_withdrawal_readback(
            manifest or source,
            readback if probes is None else probes,
            revoked_dependencies=("rights:1",),
            **changes,
        )

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
