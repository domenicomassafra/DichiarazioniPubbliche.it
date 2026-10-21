"""DP-319: source epoch labels cannot mint a second paid attempt."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tests.test_dp319_durable_investigation_next import observed, source
from tests.test_dp319_investigation_attempts import assignment, spec
from dichiarazioni_pubbliche.investigation_attempts_store_v1 import InvestigationSQLiteStore


class SameSourceHashDedupeTests(unittest.TestCase):
    def test_relabelled_same_bytes_never_reopens_reserved_or_completed_cost(self):
        for finished in (False, True):
            with self.subTest(finished=finished), tempfile.TemporaryDirectory() as work:
                db = InvestigationSQLiteStore(Path(work) / "ledger.sqlite")
                first = source()
                scope = spec()
                plan = (assignment(),)
                db.record_source(first, expected_revision=0)
                db.register(scope, plan, first)
                reserved = db.reserve(
                    scope, plan, first, key="first", expected_revision=0
                )
                if finished:
                    db.complete(
                        scope, plan, first,
                        observation=observed(reserved.reservations[0]),
                        key="first", expected_revision=reserved.revision,
                    )
                # A new metadata/material epoch claims novelty, but the
                # immutable original bytes, source and Content are unchanged.
                relabelled = source(
                    revision=2, version="capture:v2",
                    fingerprint="material:relabelled",
                    sha=first.source_sha256,
                )
                db.record_source(relabelled, expected_revision=1)
                newer = spec(material_fingerprint=relabelled.material_fingerprint)
                with self.assertRaisesRegex(
                    ValueError, "SOURCE_SCOPE_ALREADY_RESERVED"
                ):
                    db.register(newer, plan, relabelled)
                self.assertEqual(
                    len(db.history(scope, plan).reservations), 1
                )

    def test_changed_source_bytes_reopen_new_version(self):
        with tempfile.TemporaryDirectory() as work:
            db = InvestigationSQLiteStore(Path(work) / "ledger.sqlite")
            first = source()
            scope = spec()
            plan = (assignment(),)
            db.record_source(first, expected_revision=0)
            db.register(scope, plan, first)
            db.reserve(scope, plan, first, key="first", expected_revision=0)
            second = source(
                revision=2, version="capture:v2",
                fingerprint="material:changed-bytes", sha="b" * 64,
            )
            db.record_source(second, expected_revision=1)
            newer = spec(material_fingerprint=second.material_fingerprint)
            db.register(newer, plan, second)
            fresh = db.reserve(newer, plan, second, key="second", expected_revision=0)
            self.assertEqual(len(fresh.reservations), 1)


if __name__ == "__main__":
    unittest.main()
