"""Offline DP-320 cross-release change planning; all data is synthetic."""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.private_surface_release_transition_v1 import (  # noqa: E402
    plan_private_surface_release_transition,
)
from dichiarazioni_pubbliche.revocation_epoch_fence import (  # noqa: E402
    IsolatedPublicationEpochStore,
    RevocationFenceHeld,
)
from dichiarazioni_pubbliche.revocation_served_surfaces_v1 import (  # noqa: E402
    ALL_SURFACES,
    EXTENDED_SURFACES,
    SurfaceArtifact,
    surface_manifest_sha256,
)

NOW = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)


def source_fixture(*, rdf: bool = True):
    conn = sqlite3.connect(":memory:")
    try:
        store = IsolatedPublicationEpochStore(conn)
        store.init_fixture_schema()
        store.register_fixture_source("rights:public", "a" * 64)
        store.register_fixture_source("source:public", "b" * 64)
        ids = ("rights:public", "source:public")
        old = store.mint(release_id="release:old", dependency_ids=ids)
        new = store.mint(release_id="release:new", dependency_ids=ids)

        def artifacts(ticket, *, edit=None, include_rdf=rdf):
            names = EXTENDED_SURFACES if include_rdf else ALL_SURFACES
            result = []
            for name in names:
                body = (
                    "synthetic-reviewed-public-v2:"
                    + name
                    + (":changed" if name == edit else "")
                ).encode()
                result.append(
                    SurfaceArtifact(
                        surface=name,
                        release_id=ticket.release_id,
                        source_id="source:public",
                        source_epoch=0,
                        ticket_fingerprint=ticket.fingerprint,
                        material_sha256=hashlib.sha256(body).hexdigest(),
                        content=body,
                    )
                )
            return tuple(result)

        return old, new, artifacts(old), artifacts(new), conn, artifacts
    except BaseException:
        conn.close()
        raise


class PrivateSurfaceReleaseTransitionTests(unittest.TestCase):
    def setUp(self):
        self.old, self.new, self.before, self.after, self.conn, self.build = (
            source_fixture()
        )
        self.addCleanup(self.conn.close)

    def plan(self, **overrides):
        params = {
            "previous_ticket": self.old,
            "previous_artifacts": self.before,
            "expected_previous_manifest_sha256": surface_manifest_sha256(
                self.old, self.before, include_rdf=True
            ),
            "current_ticket": self.new,
            "current_artifacts": self.after,
            "expected_current_manifest_sha256": surface_manifest_sha256(
                self.new, self.after, include_rdf=True
            ),
            "previous_created_at": "2026-10-13T08:00:00Z",
            "current_created_at": "2026-10-14T09:00:00Z",
            "as_of": NOW,
            "current_source_policies": {
                "rights:public": ("APPROVED", "APPROVED"),
                "source:public": ("APPROVED", "APPROVED"),
            },
            "previous_include_rdf": True,
            "current_include_rdf": True,
            "private_opt_in": True,
        }
        params.update(overrides)
        return plan_private_surface_release_transition(**params)

    def test_complete_unchanged_eight_surface_cohort_is_never_authority(self):
        result = self.plan()
        self.assertEqual(result.status, "UNCHANGED_REVIEW_PENDING")
        self.assertEqual(result.surface_count, 8)
        self.assertEqual(result.changed_surface_count, 0)
        self.assertEqual(result.added_surface_count, 0)
        self.assertEqual(result.held_dependency_count, 0)
        self.assertEqual(len(result.surfaces), 8)
        self.assertFalse(result.publication_authority)
        self.assertFalse(result.source_approval_authority)
        self.assertFalse(result.rights_authority)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(result, self.plan())
        for forbidden in (
            "rights:public",
            "source:public",
            "release:old",
            "release:new",
            "synthetic-reviewed",
        ):
            self.assertNotIn(forbidden, repr(result))

    def test_changed_one_surface_finds_exact_material_without_copying_body(self):
        changed = self.build(self.new, edit="SEARCH")
        result = self.plan(
            current_artifacts=changed,
            expected_current_manifest_sha256=surface_manifest_sha256(
                self.new, changed, include_rdf=True
            ),
        )
        self.assertEqual(result.status, "MANUAL_RECHECK_REQUIRED")
        self.assertEqual(result.changed_surface_count, 1)
        self.assertEqual(
            [item.surface for item in result.surfaces if item.changed], ["SEARCH"]
        )
        self.assertIn("SURFACE_MATERIAL_CHANGED", result.reason_codes)
        self.assertNotIn("synthetic-reviewed", repr(result))

    def test_rights_and_review_hold_never_self_approve(self):
        for bad in (
            ("REVOKED", "APPROVED"),
            ("APPROVED", "PENDING"),
            ("EXPIRED", "DENIED"),
        ):
            with self.subTest(bad=bad):
                result = self.plan(
                    current_source_policies={
                        "rights:public": bad,
                        "source:public": ("APPROVED", "APPROVED"),
                    }
                )
                self.assertEqual(result.status, "WITHHELD_SOURCE_POLICY")
                self.assertEqual(result.held_dependency_count, 1)
                self.assertIn("SOURCE_POLICY_NOT_APPROVED", result.reason_codes)
                self.assertFalse(result.rights_authority)

    def test_manifest_body_tamper_and_self_repin_require_owner_sha(self):
        bad = list(self.after)
        bad[2] = replace(bad[2], content=b"injected SECRET")
        with self.assertRaisesRegex(ValueError, "TRANSITION_RELEASE_INVALID"):
            self.plan(current_artifacts=tuple(bad))
        bad[2] = replace(
            bad[2], material_sha256=hashlib.sha256(b"injected SECRET").hexdigest()
        )
        with self.assertRaisesRegex(ValueError, "TRANSITION_MANIFEST_PIN_MISMATCH"):
            self.plan(current_artifacts=tuple(bad))

    def test_timestamp_rollback_future_and_naive_receipt_denied(self):
        for changed in (
            {"current_created_at": "2026-10-12T08:00:00Z"},
            {"current_created_at": "2026-10-15T08:00:00Z"},
            {"current_created_at": "2026-10-14T08:00:00"},
            {"as_of": datetime(2026, 10, 14, 9)},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.plan(**changed)

    def test_seven_to_eight_surface_upgrade_requires_scope_review(self):
        old, new, before, after, conn, build = source_fixture(rdf=False)
        self.addCleanup(conn.close)
        current = build(new, include_rdf=True)
        result = self.plan(
            previous_ticket=old,
            current_ticket=new,
            previous_artifacts=before,
            current_artifacts=current,
            expected_previous_manifest_sha256=surface_manifest_sha256(old, before),
            expected_current_manifest_sha256=surface_manifest_sha256(
                new, current, include_rdf=True
            ),
            previous_include_rdf=False,
            current_include_rdf=True,
        )
        self.assertEqual(result.status, "MANUAL_RECHECK_REQUIRED")
        self.assertEqual(result.added_surface_count, 1)
        self.assertIn("SURFACE_SCOPE_CHANGED", result.reason_codes)

    def test_revoked_dependency_epoch_or_source_material_requires_recheck(self):
        self.conn.execute(
            "UPDATE epoch_source SET material_sha256=? WHERE source_id=?",
            ("c" * 64, "source:public"),
        )
        self.conn.commit()
        # Same release ticket bytes cannot prove currently active source; the
        # planner has no DB. An explicit dependency change must still be held.
        new = replace(
            self.new,
            dependencies=tuple(
                replace(d, material_sha256="c" * 64)
                if d.dependency_id == "source:public"
                else d
                for d in self.new.dependencies
            ),
        )
        from dichiarazioni_pubbliche.revocation_epoch_fence import _ticket_fingerprint

        new = replace(
            new, fingerprint=_ticket_fingerprint(new.release_id, new.dependencies)
        )
        changed = tuple(
            replace(a, ticket_fingerprint=new.fingerprint) for a in self.after
        )
        result = self.plan(
            current_ticket=new,
            current_artifacts=changed,
            expected_current_manifest_sha256=surface_manifest_sha256(
                new, changed, include_rdf=True
            ),
        )
        self.assertEqual(result.status, "MANUAL_RECHECK_REQUIRED")
        self.assertIn("SOURCE_DEPENDENCY_DRIFT", result.reason_codes)

    def test_caller_mutation_after_snapshot_cannot_inject_approval(self):
        policies = {
            "rights:public": ("REVOKED", "PENDING"),
            "source:public": ("APPROVED", "APPROVED"),
        }
        result = self.plan(current_source_policies=policies)
        policies["rights:public"] = ("APPROVED", "APPROVED")
        self.assertEqual(result.status, "WITHHELD_SOURCE_POLICY")

    def test_bad_inputs_fail_closed_and_no_private_echo(self):
        cases = (
            {"private_opt_in": False},
            {"expected_previous_manifest_sha256": "0" * 64},
            {"previous_artifacts": list(self.before)},
            {"current_source_policies": {"rights:public": ("APPROVED", "APPROVED")}},
            {
                "current_source_policies": {
                    "rights:public": ("SECRET_PRIVATE", "APPROVED"),
                    "source:public": ("APPROVED", "APPROVED"),
                }
            },
            {"current_include_rdf": "true"},
        )
        for item in cases:
            with (
                self.subTest(item=item),
                self.assertRaises((ValueError, RevocationFenceHeld)) as caught,
            ):
                self.plan(**item)
            self.assertNotIn("SECRET_PRIVATE", str(caught.exception))

    def test_forged_dependency_duplicates_and_wrong_epoch_version_denied(self):
        # An untrusted caller may recompute all apparent hashes; that does
        # not make duplicate dependencies or a future incompatible epoch
        # contract a valid source ticket.
        from dichiarazioni_pubbliche.revocation_epoch_fence import _ticket_fingerprint

        changed = (
            replace(self.new, version="not-the-epoch-contract"),
            replace(
                self.new, dependencies=self.new.dependencies + self.new.dependencies[:1]
            ),
            replace(self.new, dependencies=tuple(reversed(self.new.dependencies))),
            replace(
                self.new,
                dependencies=tuple(
                    replace(dep, material_sha256="bad-sha") if i == 0 else dep
                    for i, dep in enumerate(self.new.dependencies)
                ),
            ),
        )
        for new in changed:
            with self.subTest(new=new):
                recomputed = replace(
                    new,
                    fingerprint=_ticket_fingerprint(new.release_id, new.dependencies),
                )
                artifacts = tuple(
                    replace(row, ticket_fingerprint=recomputed.fingerprint)
                    for row in self.after
                )
                with self.assertRaisesRegex(
                    ValueError, "TRANSITION_(RELEASE|DEPENDENCY_SCOPE)_INVALID"
                ):
                    self.plan(current_ticket=recomputed, current_artifacts=artifacts)


if __name__ == "__main__":
    unittest.main()
