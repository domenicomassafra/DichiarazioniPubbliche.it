"""Actual Python linked-data/search fixtures behind optional 8-surface SQLite fence.

This is NOT an operational HTTP, edge cache, source approval or MiniPC proof.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / "poc"),
    str(Path(__file__).resolve().parent),
]

from dichiarazioni_pubbliche.linked_data import projection_ntriples  # noqa: E402
from dichiarazioni_pubbliche.public_projection import build_public_projection  # noqa: E402
from dichiarazioni_pubbliche.revocation_epoch_fence import (  # noqa: E402
    IsolatedPublicationEpochStore,
    RevocationFenceHeld,
)
from dichiarazioni_pubbliche.revocation_served_surfaces_v1 import (  # noqa: E402
    ALL_SURFACES,
    EXTENDED_SURFACES,
    IsolatedServedSurfaceFence,
    SurfaceArtifact,
    surface_manifest_sha256,
)
from dichiarazioni_pubbliche.correction_propagation import check_correction_propagation  # noqa: E402
from test_correction_propagation import (  # noqa: E402
    linked_data_receipt,
    route_manifest,
    search_index,
)
from test_public_projection import FakeSource, valid_row  # noqa: E402

NOW = datetime(2026, 10, 14, 1, tzinfo=timezone.utc)


def real_typescript_search_bytes(projection: dict) -> bytes:
    """Run actual production TS builder *and validator* on the Python fixture.

    No HTTP, source capture, installed global launcher or provider. Node reads
    only the repo's TS modules. The Python metadata guard below remains a
    separate parity assertion, not a substitute for the served search asset.
    """
    js = """
import {buildSearchIndexMaterial,finalizeSearchIndex,validateSearchIndex,canonicalJson} from './src/lib/searchIndex.ts';
let input='';for await(const chunk of process.stdin) input+=chunk;
const projection=JSON.parse(input);
const index=await finalizeSearchIndex(buildSearchIndexMaterial(projection));
await validateSearchIndex(index,projection.dataset_sha256);
process.stdout.write(canonicalJson(index));
"""
    root = Path(__file__).resolve().parents[1] / "web"
    completed = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", js],
        cwd=root,
        input=json.dumps(projection, ensure_ascii=False),
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
        env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    if completed.returncode:
        raise AssertionError(
            "DP320_REAL_TS_SEARCH_ASSET_INVALID:" + completed.stderr[-500:]
        )
    return completed.stdout.encode("utf-8")


def real_artifacts():
    # Both actual Python materializers read the SAME approved-shaped synthetic
    # projection; do not disguise two unrelated fixture corpora as one release.
    shared_projection = build_public_projection(
        FakeSource([valid_row()]),
        generated_at="2026-10-13T12:00:00Z",
    )
    actual_index = search_index(shared_projection)
    checked = check_correction_propagation(
        old_projection=shared_projection,
        new_projection=shared_projection,
        search_index=actual_index,
        linked_data_receipt=linked_data_receipt(shared_projection),
        route_static_manifest=route_manifest(shared_projection, shared_projection),
    )
    assert checked.consistent, checked.blockers
    # DP-431's corrected Python contract, like the actual TS consumer, treats
    # an explicit empty first-class Content catalog as no searchable Content.
    # Two records (Finding and Person) are correct for this synthetic release;
    # expecting a third fallback Content was a stale cross-lane test premise.
    assert shared_projection.get("contents") == []
    assert {row["kind"] for row in actual_index["records"]} == {"finding", "person"}
    assert actual_index["projection_sha256"] == shared_projection["dataset_sha256"]
    real_search = real_typescript_search_bytes(shared_projection)
    served = json.loads(real_search)
    actual = {(row["kind"], row["id"]): row for row in served["records"]}
    # DP431's *Python guard* checks metadata only, whereas the actual TS
    # asset has the full public record schema. Compare overlapping fields,
    # never equate the partial receipt with the full served search material.
    assert len(served["records"]) == len(actual)
    assert len(served["records"]) == len(actual_index["records"])
    assert {(row["kind"], row["id"]) for row in actual_index["records"]} == set(actual)
    for public_receipt in actual_index["records"]:
        canonical_record = actual[(public_receipt["kind"], public_receipt["id"])]
        assert all(
            canonical_record[key] == value for key, value in public_receipt.items()
        )
    real_rdf = projection_ntriples(shared_projection).encode()
    assert real_search and real_rdf.startswith(
        b"<https://dichiarazionipubbliche.it/id/"
    )
    return {"SEARCH": real_search, "RDF": real_rdf}


class ExtendedRdfAndSearchFenceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.base = IsolatedPublicationEpochStore(self.conn)
        self.base.init_fixture_schema()
        self.base.register_fixture_source("rights:public", "d" * 64)
        self.base.register_fixture_source("source:public", "a" * 64)
        self.ticket = self.base.mint(
            release_id="release:public:8",
            dependency_ids=("rights:public", "source:public"),
        )
        self.fence = IsolatedServedSurfaceFence(self.conn, include_rdf=True)
        self.fence.init_fixture_schema()
        self.items = self.artifacts()
        self.manifest = surface_manifest_sha256(
            self.ticket, self.items, include_rdf=True
        )

    def artifacts(self):
        verified = real_artifacts()
        return tuple(
            SurfaceArtifact(
                surface=name,
                release_id=self.ticket.release_id,
                source_id="source:public",
                source_epoch=0,
                ticket_fingerprint=self.ticket.fingerprint,
                material_sha256=hashlib.sha256(
                    verified.get(name, b"synthetic public approved:" + name.encode())
                ).hexdigest(),
                content=verified.get(
                    name, b"synthetic public approved:" + name.encode()
                ),
            )
            for name in EXTENDED_SURFACES
        )

    def seal(self):
        self.assertTrue(self.fence.seal(self.ticket, self.items, self.manifest))

    def test_search_asset_has_real_typescript_consumer_required_fields(self):
        # This must be the actual TS search asset shape, not the smaller
        # DP431 *metadata guard* fixture, which cannot be served to Explore.
        index = json.loads(real_artifacts()["SEARCH"])
        self.assertEqual(
            index["schema_version"], "dichiarazioni-pubbliche-search-index-v1"
        )
        self.assertEqual(
            index["projection_schema_version"], "dichiarazioni-pubbliche-public-v2"
        )
        self.assertEqual(len(index["index_sha256"]), 64)
        self.assertTrue(index["generated_at"])
        self.assertTrue(index["records"])
        self.assertIn("route", index["records"][0])
        self.assertIn("direct_quote_eligible", index["records"][0])
        self.assertIn("primary_terms", index["records"][0])
        self.assertIn("secondary_terms", index["records"][0])

    def test_corrected_dp431_guard_and_real_ts_index_have_exact_empty_content_parity(
        self,
    ):
        # This fixture originally failed on the combined published DP-431 and
        # DP-320 files: eight DP-320 tests assumed a fabricated third Content
        # row with contents=[]. Require exact metadata-to-consumer identity,
        # not an exception for stale Python legacy rows.
        shared_projection = build_public_projection(
            FakeSource([valid_row()]), generated_at="2026-10-13T12:00:00Z"
        )
        self.assertEqual(shared_projection["contents"], [])
        index = search_index(shared_projection)
        served = json.loads(
            next(item.content for item in self.items if item.surface == "SEARCH")
        )
        metadata = {(row["kind"], row["id"]) for row in index["records"]}
        actual = {(row["kind"], row["id"]) for row in served["records"]}
        self.assertEqual(metadata, actual)
        self.assertEqual({kind for kind, _ in actual}, {"finding", "person"})
        self.assertEqual(len(actual), 2)

    def test_eighth_rdf_optional_and_entire_real_search_cohort_pinned(self):
        self.assertEqual(len(ALL_SURFACES), 7)
        self.assertEqual(EXTENDED_SURFACES, (*ALL_SURFACES, "RDF"))
        self.assertEqual(len(self.items), 8)
        self.assertNotEqual(
            self.items[2].material_sha256, self.items[-1].material_sha256
        )
        self.assertIn(b"dichiarazioni-pubbliche-search-index-v1", self.items[2].content)
        self.assertIn(b"<https://dichiarazionipubbliche.it/id/", self.items[-1].content)
        with self.assertRaisesRegex(RevocationFenceHeld, "SCOPE"):
            surface_manifest_sha256(self.ticket, self.items)
        self.seal()
        self.assertTrue(self.fence.check_all(self.ticket, self.items, self.manifest))
        for item in self.items:
            self.assertTrue(self.fence.check_one(self.ticket, item, self.manifest))
        with self.assertRaisesRegex(RevocationFenceHeld, "SCOPE"):
            IsolatedServedSurfaceFence(self.conn).check_all(
                self.ticket, self.items, self.manifest
            )

    def test_seven_surface_release_does_not_implicitly_become_eight(self):
        other = IsolatedServedSurfaceFence(self.conn)
        limited = self.items[:-1]
        seven_pin = surface_manifest_sha256(self.ticket, limited)
        self.assertTrue(other.seal(self.ticket, limited, seven_pin))
        with self.assertRaisesRegex(RevocationFenceHeld, "CONFLICT|PUBLICATION|SCOPE"):
            self.fence.seal(self.ticket, self.items, self.manifest)
        with self.assertRaisesRegex(RevocationFenceHeld, "SCOPE"):
            self.fence.check_one(self.ticket, limited[0], seven_pin)

    def test_malformed_rdf_and_cross_surface_missing_denied(self):
        self.seal()
        with self.assertRaisesRegex(RevocationFenceHeld, "MATERIAL"):
            self.fence.check_one(
                self.ticket,
                replace(self.items[-1], content=b"FORGED RDF"),
                self.manifest,
            )
        with self.assertRaisesRegex(RevocationFenceHeld, "SCOPE"):
            self.fence.check_all(self.ticket, self.items[:-1], self.manifest)
        self.conn.execute("DELETE FROM dp320_surface_reference WHERE surface='RDF'")
        self.conn.commit()
        with self.assertRaisesRegex(RevocationFenceHeld, "SCOPE"):
            self.fence.check_one(self.ticket, self.items[2], self.manifest)

    def test_rehashed_rdf_then_repin_cannot_override_sealed_manifest(self):
        self.seal()
        rogue = replace(
            self.items[-1],
            content=b"corrected-but-unreviewed-rdf",
            material_sha256=hashlib.sha256(b"corrected-but-unreviewed-rdf").hexdigest(),
        )
        forged = self.items[:-1] + (rogue,)
        rehash = surface_manifest_sha256(self.ticket, forged, include_rdf=True)
        with self.assertRaisesRegex(RevocationFenceHeld, "PUBLICATION"):
            self.fence.check_one(self.ticket, rogue, rehash)
        with self.assertRaisesRegex(RevocationFenceHeld, "CONFLICT"):
            self.fence.seal(self.ticket, forged, rehash)
        self.assertTrue(
            self.fence.check_one(self.ticket, self.items[-1], self.manifest)
        )

    def test_four_revoke_reasons_block_search_rdf_and_every_other_surface(self):
        for reason in (
            "RIGHTS_WITHDRAWN",
            "PRIVACY_HOLD",
            "CORRECTION",
            "SOURCE_SUPERSEDED",
        ):
            with self.subTest(reason=reason):
                # Test isolated SQLite state and full original public-search/RDF
                # fixtures for every independent revocation reason.
                conn = sqlite3.connect(":memory:")
                try:
                    base = IsolatedPublicationEpochStore(conn)
                    base.init_fixture_schema()
                    for dependency in self.ticket.dependencies:
                        base.register_fixture_source(
                            dependency.dependency_id, dependency.material_sha256
                        )
                    ticket = base.mint(
                        release_id=self.ticket.release_id,
                        dependency_ids=tuple(
                            d.dependency_id for d in self.ticket.dependencies
                        ),
                    )
                    fence = IsolatedServedSurfaceFence(conn, include_rdf=True)
                    fence.init_fixture_schema()
                    self.assertTrue(fence.seal(ticket, self.items, self.manifest))
                    base.revoke(
                        source_id="rights:public",
                        event_id="event:revoked",
                        reason=reason,
                        now=NOW,
                    )
                    for item in self.items:
                        with self.assertRaisesRegex(
                            RevocationFenceHeld, "STALE_OR_HELD"
                        ):
                            fence.check_one(ticket, item, self.manifest)
                    with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
                        fence.check_all(ticket, self.items, self.manifest)
                    self.assertEqual(len(base.pending_invalidations()), 1)
                finally:
                    conn.close()

    def test_ticket_with_malformed_nested_dependency_held_without_private_leak(self):
        self.seal()
        malformed = replace(self.ticket, dependencies=(None,))
        with self.assertRaisesRegex(RevocationFenceHeld, "TICKET_INVALID"):
            self.fence.check_one(malformed, self.items[0], self.manifest)
        with self.assertRaisesRegex(RevocationFenceHeld, "TICKET_INVALID"):
            surface_manifest_sha256(malformed, self.items, include_rdf=True)

    def test_rdf_reference_read_serializes_with_revoker_on_two_real_connections(self):
        with tempfile.TemporaryDirectory(prefix="dp320-rdf-transaction-") as directory:
            file = Path(directory) / "sqlite-reference.db"
            first = sqlite3.connect(file, timeout=2)
            try:
                core = IsolatedPublicationEpochStore(first)
                core.init_fixture_schema()
                for dependency in self.ticket.dependencies:
                    core.register_fixture_source(
                        dependency.dependency_id, dependency.material_sha256
                    )
                release = core.mint(
                    release_id=self.ticket.release_id,
                    dependency_ids=tuple(
                        dep.dependency_id for dep in self.ticket.dependencies
                    ),
                )
                serving = IsolatedServedSurfaceFence(first, include_rdf=True)
                serving.init_fixture_schema()
                self.assertTrue(serving.seal(release, self.items, self.manifest))
                inside = threading.Event()
                proceed = threading.Event()
                accepted: list[bool] = []

                def read_eighth():
                    conn = sqlite3.connect(file, timeout=2)
                    try:

                        def pause(sql):
                            if sql.startswith("SELECT surface,release_id,source_id"):
                                inside.set()
                                self.assertTrue(proceed.wait(timeout=3))

                        conn.set_trace_callback(pause)
                        accepted.append(
                            IsolatedServedSurfaceFence(
                                conn, include_rdf=True
                            ).check_one(release, self.items[-1], self.manifest)
                        )
                    finally:
                        conn.close()

                thread = threading.Thread(target=read_eighth, daemon=True)
                thread.start()
                try:
                    self.assertTrue(inside.wait(timeout=2))
                    contender = sqlite3.connect(file, timeout=0)
                    try:
                        with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                            IsolatedPublicationEpochStore(contender).revoke(
                                source_id="rights:public",
                                event_id="event:rdf:race",
                                reason="RIGHTS_WITHDRAWN",
                                now=NOW,
                            )
                    finally:
                        contender.close()
                finally:
                    proceed.set()
                    thread.join(timeout=4)
                self.assertFalse(thread.is_alive())
                self.assertEqual(accepted, [True])
                core.revoke(
                    source_id="rights:public",
                    event_id="event:rdf:race",
                    reason="RIGHTS_WITHDRAWN",
                    now=NOW,
                )
                with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
                    serving.check_one(release, self.items[-1], self.manifest)
            finally:
                first.close()


if __name__ == "__main__":
    unittest.main()
