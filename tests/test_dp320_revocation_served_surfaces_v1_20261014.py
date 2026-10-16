"""DP320 opt-in offline surface snapshot; no HTTP, live DB, or private data."""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.revocation_epoch_fence import (  # noqa: E402
    IsolatedPublicationEpochStore,
    MaterialEpoch,
    RevocationFenceHeld,
    _ticket_fingerprint,
)
from dichiarazioni_pubbliche.revocation_served_surfaces_v1 import (  # noqa: E402
    ALL_SURFACES,
    IsolatedServedSurfaceFence,
    SurfaceArtifact,
    surface_manifest_sha256,
)

NOW = datetime(2026, 10, 14, 0, tzinfo=timezone.utc)
SAFE = b"synthetic:public:approved:immutable"
LEAK = b"PRIVATE COMPLAINT BODY: never leave a private store"


class RevocationServedSurfaceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="dp320-surfaces-")
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / "private.sqlite"
        self.conn = sqlite3.connect(self.database, timeout=2)
        self.addCleanup(self.conn.close)
        self.core = IsolatedPublicationEpochStore(self.conn)
        self.core.init_fixture_schema()
        self.core.register_fixture_source(
            "source:one", hashlib.sha256(b"approved source").hexdigest()
        )
        self.core.register_fixture_source(
            "rights:one", hashlib.sha256(b"approved rights").hexdigest()
        )
        self.fence = IsolatedServedSurfaceFence(self.conn)
        self.fence.init_fixture_schema()
        self.ticket = self.core.mint(
            release_id="release:approved:1", dependency_ids=("rights:one", "source:one")
        )
        self.epoch = next(
            v.epoch for v in self.ticket.dependencies if v.dependency_id == "source:one"
        )
        self.items = self.artifacts()
        self.manifest = surface_manifest_sha256(self.ticket, self.items)

    def artifacts(
        self,
        payload=SAFE,
        *,
        release_id=None,
        source_id="source:one",
        ticket_fingerprint=None,
        epoch=None,
    ):
        return tuple(
            SurfaceArtifact(
                surface=surface,
                release_id=release_id or self.ticket.release_id,
                source_id=source_id,
                source_epoch=self.epoch if epoch is None else epoch,
                ticket_fingerprint=ticket_fingerprint or self.ticket.fingerprint,
                material_sha256=hashlib.sha256(payload + surface.encode()).hexdigest(),
                content=payload + surface.encode(),
            )
            for surface in ALL_SURFACES
        )

    def seal(self):
        self.assertTrue(self.fence.seal(self.ticket, self.items, self.manifest))

    def test_all_seven_atomic_surfaces_sha_and_single_read(self):
        self.assertEqual(len(ALL_SURFACES), 7)
        self.seal()
        self.assertTrue(self.fence.check_all(self.ticket, self.items, self.manifest))
        for surface, observation in zip(ALL_SURFACES, self.items):
            self.assertEqual(observation.surface, surface)
            self.assertTrue(
                self.fence.check_one(self.ticket, observation, self.manifest)
            )
        self.assertTrue(self.fence.seal(self.ticket, self.items, self.manifest))

    def test_forged_large_self_consistent_ticket_cannot_bypass_mint_dependency_cap(self):
        # mint() caps a dependency cohort at 128. A caller must not bypass
        # that cap by constructing an otherwise correctly hashed ticket.
        for i in range(127):
            self.core.register_fixture_source(
                f"source:extra:{i:03d}", hashlib.sha256(f"extra:{i}".encode()).hexdigest()
            )
        deps = [*self.ticket.dependencies]
        deps.extend(
            MaterialEpoch(f"source:extra:{i:03d}", 0, hashlib.sha256(f"extra:{i}".encode()).hexdigest())
            for i in range(127)
        )
        deps = tuple(sorted(deps, key=lambda d: d.dependency_id))
        self.assertEqual(len(deps), 129)
        forged = replace(self.ticket, dependencies=deps, fingerprint=_ticket_fingerprint(self.ticket.release_id, deps))
        observations = self.artifacts(ticket_fingerprint=forged.fingerprint)
        manifest = surface_manifest_sha256(forged, observations)
        with self.assertRaisesRegex(RevocationFenceHeld, "DEPENDENCY_SCOPE"):
            self.fence.seal(forged, observations, manifest)
        legitimate_deps = tuple(
            dependency for dependency in deps
            if dependency.dependency_id != "source:extra:126"
        )
        self.assertEqual(len(legitimate_deps), 128)
        legitimate = replace(
            forged, dependencies=legitimate_deps,
            fingerprint=_ticket_fingerprint(forged.release_id, legitimate_deps),
        )
        valid_observations = self.artifacts(ticket_fingerprint=legitimate.fingerprint)
        valid_manifest = surface_manifest_sha256(legitimate, valid_observations)
        self.assertTrue(self.fence.seal(legitimate, valid_observations, valid_manifest))

    def test_surface_corruption_absence_cross_epoch_and_source_denied(self):
        self.seal()
        mutations = (
            (replace(self.items[0], content=b"FORGED HTML"), "MATERIAL"),
            (replace(self.items[0], material_sha256="a" * 64), "MATERIAL"),
            (replace(self.items[0], release_id="release:other"), "RELEASE"),
            (replace(self.items[0], ticket_fingerprint="b" * 64), "TICKET"),
            (replace(self.items[0], source_epoch=1), "EPOCH"),
            (replace(self.items[0], source_id="source:arbitrary"), "SOURCE"),
            (replace(self.items[0], surface="UNKNOWN"), "SURFACE"),
        )
        for changed, expected in mutations:
            with (
                self.subTest(expected=expected),
                self.assertRaisesRegex(RevocationFenceHeld, expected),
            ):
                self.fence.check_one(self.ticket, changed, self.manifest)
        with self.assertRaisesRegex(RevocationFenceHeld, "SCOPE"):
            self.fence.check_all(self.ticket, self.items[:-1], self.manifest)
        with self.assertRaisesRegex(RevocationFenceHeld, "PUBLICATION|TICKET"):
            self.fence.check_all(self.ticket, self.items, "f" * 64)
        with self.assertRaisesRegex(RevocationFenceHeld, "SURFACE"):
            self.fence.seal(self.ticket, self.items + (self.items[0],), self.manifest)
        with self.assertRaisesRegex(RevocationFenceHeld, "SOURCE"):
            self.fence.seal(
                self.ticket, self.artifacts(source_id="source:phantom"), self.manifest
            )

    def test_stale_mixed_surface_or_single_missing_database_reference(self):
        self.seal()
        self.conn.execute(
            "UPDATE dp320_surface_reference SET material_sha256=? WHERE surface='JSON_LD'",
            ("0" * 64,),
        )
        self.conn.commit()
        with self.assertRaisesRegex(RevocationFenceHeld, "MATERIAL|MANIFEST"):
            self.fence.check_one(self.ticket, self.items[0], self.manifest)
        self.conn.execute("DELETE FROM dp320_surface_reference WHERE surface='JSON_LD'")
        self.conn.commit()
        with self.assertRaisesRegex(RevocationFenceHeld, "SCOPE"):
            self.fence.check_one(self.ticket, self.items[0], self.manifest)

    def test_revocation_privacy_correction_replay_and_no_auto_restore(self):
        for reason in (
            "RIGHTS_WITHDRAWN",
            "CORRECTION",
            "PRIVACY_HOLD",
            "SOURCE_SUPERSEDED",
        ):
            with self.subTest(reason=reason):
                with tempfile.TemporaryDirectory() as directory:
                    db = Path(directory) / "sealed.sqlite"
                    conn = sqlite3.connect(db)
                    try:
                        core = IsolatedPublicationEpochStore(conn)
                        core.init_fixture_schema()
                        for dep in self.ticket.dependencies:
                            core.register_fixture_source(
                                dep.dependency_id, dep.material_sha256
                            )
                        ticket = core.mint(
                            release_id=self.ticket.release_id,
                            dependency_ids=tuple(
                                d.dependency_id for d in self.ticket.dependencies
                            ),
                        )
                        fence = IsolatedServedSurfaceFence(conn)
                        fence.init_fixture_schema()
                        fence.seal(ticket, self.items, self.manifest)
                        self.assertEqual(
                            core.revoke(
                                source_id="rights:one",
                                event_id="event:one",
                                reason=reason,
                                now=NOW,
                            ),
                            1,
                        )
                        self.assertEqual(
                            core.revoke(
                                source_id="rights:one",
                                event_id="event:one",
                                reason=reason,
                                now=NOW,
                            ),
                            1,
                        )
                        with self.assertRaisesRegex(
                            RevocationFenceHeld, "STALE_OR_HELD"
                        ):
                            fence.check_all(ticket, self.items, self.manifest)
                        with self.assertRaisesRegex(
                            RevocationFenceHeld, "STALE_OR_HELD"
                        ):
                            fence.seal(ticket, self.items, self.manifest)
                        core.acknowledge(event_id="event:one", epoch=1)
                        with self.assertRaisesRegex(
                            RevocationFenceHeld, "STALE_OR_HELD"
                        ):
                            fence.check_one(ticket, self.items[0], self.manifest)
                        with self.assertRaisesRegex(
                            RevocationFenceHeld, "REPLAY_CONFLICT"
                        ):
                            core.revoke(
                                source_id="source:one",
                                event_id="event:one",
                                reason=reason,
                                now=NOW,
                            )
                        core.register_fixture_source("rights:one", "e" * 64)
                        with self.assertRaisesRegex(
                            RevocationFenceHeld, "STALE_OR_HELD"
                        ):
                            core.mint(
                                release_id="release:restored",
                                dependency_ids=("rights:one", "source:one"),
                            )
                    finally:
                        conn.close()

    def test_malicious_metadata_bodies_and_partial_batch_failclosed(self):
        self.seal()
        for value in (
            {"surface": "HTML", "rights_authority": LEAK},
            replace(self.items[0], content=LEAK),
            replace(self.items[0], material_sha256="fake"),
            replace(self.items[0], surface="../private"),
        ):
            with self.subTest(kind=type(value).__name__):
                try:
                    self.fence.check_one(self.ticket, value, self.manifest)
                except RevocationFenceHeld as exc:
                    self.assertNotIn(LEAK.decode(), str(exc))
                    self.assertTrue(
                        str(exc).startswith("SURFACE_") or str(exc).startswith("FENCE_")
                    )
                else:
                    self.fail("untrusted material allowed")
        with self.assertRaisesRegex(RevocationFenceHeld, "SURFACE"):
            self.fence.check_all(self.ticket, (self.items[0],) * 7, self.manifest)

    def test_sealed_ticket_immutable_conflict_and_root_publication_guard(self):
        self.seal()
        changes = self.artifacts(payload=b"alternate approved-looking body")
        second_manifest = surface_manifest_sha256(self.ticket, changes)
        with self.assertRaisesRegex(RevocationFenceHeld, "CONFLICT"):
            self.fence.seal(self.ticket, changes, second_manifest)
        self.conn.execute("UPDATE epoch_publication SET artifact_sha256=?", ("a" * 64,))
        self.conn.commit()
        with self.assertRaisesRegex(RevocationFenceHeld, "PUBLICATION|MANIFEST"):
            self.fence.check_all(self.ticket, self.items, self.manifest)

    def test_correspondence_and_actual_digest_not_just_self_hashed_metadata(self):
        with self.assertRaisesRegex(RevocationFenceHeld, "MATERIAL"):
            self.fence.seal(
                self.ticket,
                (replace(self.items[0], content=b"secret"),) + self.items[1:],
                self.manifest,
            )
        with self.assertRaisesRegex(RevocationFenceHeld, "TICKET"):
            self.fence.seal(self.ticket, self.items, "f" * 64)
        with self.assertRaisesRegex(RevocationFenceHeld, "SURFACE"):
            self.fence.seal(self.ticket, tuple(reversed(self.items)), self.manifest)

    def test_read_revoke_transaction_serialization_two_connections(self):
        self.seal()
        inside = threading.Event()
        release = threading.Event()
        outcome = []
        errors = []

        def read():
            db = sqlite3.connect(self.database, timeout=2)

            def hook(sql):
                if sql.startswith("SELECT surface,release_id,source_id"):
                    inside.set()
                    release.wait(timeout=3)

            db.set_trace_callback(hook)
            try:
                outcome.append(
                    IsolatedServedSurfaceFence(db).check_all(
                        self.ticket, self.items, self.manifest
                    )
                )
            except BaseException as exc:
                errors.append(type(exc).__name__)
            finally:
                db.close()

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        try:
            self.assertTrue(inside.wait(timeout=2))
            racer = sqlite3.connect(self.database, timeout=0)
            try:
                with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                    IsolatedPublicationEpochStore(racer).revoke(
                        source_id="rights:one",
                        event_id="race:revoked",
                        reason="RIGHTS_WITHDRAWN",
                        now=NOW,
                    )
            finally:
                racer.close()
        finally:
            release.set()
            reader.join(timeout=4)
        self.assertFalse(reader.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(outcome, [True])
        self.core.revoke(
            source_id="rights:one",
            event_id="race:revoked",
            reason="RIGHTS_WITHDRAWN",
            now=NOW,
        )
        with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
            self.fence.check_one(self.ticket, self.items[0], self.manifest)

    def test_competing_surface_seals_cas_and_correction(self):
        self.seal()
        first = threading.Event()
        proceed = threading.Event()
        errors = []

        def conflict():
            other = sqlite3.connect(self.database, timeout=2)
            try:
                first.set()
                proceed.wait(timeout=2)
                alternative = self.artifacts(payload=b"fake correction")
                with self.assertRaisesRegex(RevocationFenceHeld, "CONFLICT"):
                    IsolatedServedSurfaceFence(other).seal(
                        self.ticket,
                        alternative,
                        surface_manifest_sha256(self.ticket, alternative),
                    )
            except BaseException as exc:
                errors.append(type(exc).__name__)
            finally:
                other.close()

        worker = threading.Thread(target=conflict, daemon=True)
        worker.start()
        self.assertTrue(first.wait(timeout=2))
        proceed.set()
        worker.join(timeout=4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(self.fence.check_all(self.ticket, self.items, self.manifest))

    def test_inflight_seal_precedes_revoke_and_then_all_surfaces_hold(self):
        """A revoker cannot commit between the epoch check and surface writes."""
        inside = threading.Event()
        resume = threading.Event()
        outcomes = []

        def seal_in_worker():
            conn = sqlite3.connect(self.database, timeout=2)

            def before_write(sql):
                if sql.startswith("INSERT INTO epoch_publication"):
                    inside.set()
                    resume.wait(timeout=3)

            conn.set_trace_callback(before_write)
            try:
                outcomes.append(
                    IsolatedServedSurfaceFence(conn).seal(
                        self.ticket, self.items, self.manifest
                    )
                )
            except BaseException as exc:
                outcomes.append(type(exc).__name__)
            finally:
                conn.close()

        worker = threading.Thread(target=seal_in_worker, daemon=True)
        worker.start()
        try:
            self.assertTrue(inside.wait(timeout=2))
            racing_connection = sqlite3.connect(self.database, timeout=0)
            try:
                with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                    IsolatedPublicationEpochStore(racing_connection).revoke(
                        source_id="source:one",
                        event_id="event:late-correction",
                        reason="CORRECTION",
                        now=NOW,
                    )
            finally:
                racing_connection.close()
        finally:
            resume.set()
            worker.join(timeout=4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(outcomes, [True])
        self.core.revoke(
            source_id="source:one",
            event_id="event:late-correction",
            reason="CORRECTION",
            now=NOW,
        )
        with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
            self.fence.check_all(self.ticket, self.items, self.manifest)
        self.assertEqual(
            self.core.pending_invalidations(),
            (("event:late-correction", "source:one", 1),),
        )

    def test_sqlite_restart_rechecks_root_manifest_and_held_epoch(self):
        self.seal()
        self.assertTrue(self.fence.check_all(self.ticket, self.items, self.manifest))
        reopened_connection = sqlite3.connect(self.database, timeout=2)
        try:
            reopened = IsolatedServedSurfaceFence(reopened_connection)
            self.assertTrue(
                reopened.check_one(self.ticket, self.items[0], self.manifest)
            )
            self.core.revoke(
                source_id="rights:one",
                event_id="event:durable-withdrawal",
                reason="RIGHTS_WITHDRAWN",
                now=NOW,
            )
            with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
                reopened.check_all(self.ticket, self.items, self.manifest)
            with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
                reopened.seal(self.ticket, self.items, self.manifest)
        finally:
            reopened_connection.close()

    def test_tampered_ticket_fingerprint_and_surface_epoch_metadata(self):
        from dataclasses import replace as cloned

        self.seal()
        modified = cloned(self.ticket, fingerprint="a" * 64)
        with self.assertRaisesRegex(RevocationFenceHeld, "TAMPERED"):
            self.fence.check_one(
                modified,
                cloned(self.items[0], ticket_fingerprint=modified.fingerprint),
                self.manifest,
            )
        self.conn.execute(
            "UPDATE dp320_surface_reference SET source_epoch=99 WHERE surface='HTML'"
        )
        self.conn.commit()
        with self.assertRaisesRegex(RevocationFenceHeld, "EPOCH|MANIFEST"):
            self.fence.check_one(self.ticket, self.items[0], self.manifest)

    def test_bounded_reference_only_benchmark(self):
        self.seal()
        start = time.perf_counter()
        for _ in range(100):
            self.assertTrue(
                self.fence.check_all(self.ticket, self.items, self.manifest)
            )
        elapsed = time.perf_counter() - start
        self.assertGreater(elapsed, 0)
        self.assertLess(
            elapsed, 8, "100 local SQLite checks exceeded bounded smoke budget"
        )


if __name__ == "__main__":
    unittest.main()
