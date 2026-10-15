"""DP-518 local generated-static-release readback, with no live host or cache."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.distributed_withdrawal_audit_v1 import (
    REQUIRED_PUBLIC_CONSUMERS,
    VERSION,
    LocalConsumerPath,
    ReleaseArtifact,
    ReleaseSnapshot,
    audit_local_static_withdrawal,
    release_inventory_sha256,
)
from dichiarazioni_pubbliche.revocation_epoch_fence import (
    MaterialEpoch,
    PublicationEpochTicket,
    _ticket_fingerprint,
)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fixture_body(entity: str, surface: str) -> bytes:
    if surface == "HTML":
        return f"<html><body><article>{entity}</article></body></html>".encode()
    if surface in {"API_JSON", "SEARCH", "JSON_LD"}:
        return json.dumps({"surface": surface, "entity": entity}).encode()
    if surface == "SITEMAP":
        return f"<urlset><url><loc>/person/{entity}</loc></url></urlset>".encode()
    if surface == "RDF":
        return f"<rdf:RDF><rdf:Description about='{entity}'/></rdf:RDF>".encode()
    return f"<consumer surface='{surface}' entity='{entity}'/>".encode()


class LocalWithdrawalNextTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / "public"
        self.root.mkdir()
        self.receipt = Path(self.folder.name) / "private" / "release-readback.json"
        self.receipt.parent.mkdir()
        self.surfaces = sorted(REQUIRED_PUBLIC_CONSUMERS)
        deps = (MaterialEpoch("rights:1", 4, sha(b"rights")),
                MaterialEpoch("source:other", 2, sha(b"source")))
        self.fence = PublicationEpochTicket(
            "release:withdrawn", deps, _ticket_fingerprint("release:withdrawn", deps)
        )
        self.paths = tuple(
            LocalConsumerPath(entity, surface, f"{entity}/{surface.lower()}.fixture")
            for entity in ("person:revoked", "person:safe")
            for surface in self.surfaces
        )
        self.safe_data = {
            (row.entity_id, row.surface): fixture_body(row.entity_id, row.surface)
            for row in self.paths if row.entity_id == "person:safe"
        }
        artifacts = tuple(
            ReleaseArtifact(
                path.entity_id,
                path.surface,
                "ABSENT" if path.entity_id == "person:revoked" else "PRESENT",
                None if path.entity_id == "person:revoked"
                else sha(self.safe_data[(path.entity_id, path.surface)]),
                ("rights:1",) if path.entity_id == "person:revoked"
                else ("source:other",),
            )
            for path in self.paths
        )
        self.manifest = ReleaseSnapshot(
            "release:withdrawn", "fixture:static", sha(b"code"),
            sha(b"mirror"), sha(b"migration"), sha(b"policy"),
            sha(b"generation:withdrawn"), self.fence, artifacts,
        )
        self.save_receipt()
        for path in self.paths:
            if path.entity_id == "person:safe":
                self.put(path, self.safe_data[(path.entity_id, path.surface)])

    def save_receipt(self, manifest=None):
        manifest = manifest or self.manifest
        body = {
            "version": VERSION,
            "release": {
                "release_id": manifest.release_id,
                "host_ref": manifest.host_ref,
                "code_sha256": manifest.code_sha256,
                "mirror_sha256": manifest.mirror_sha256,
                "migration_sha256": manifest.migration_sha256,
                "policy_sha256": manifest.policy_sha256,
                "generation_sha256": manifest.generation_sha256,
                "fence_fingerprint": manifest.fence.fingerprint,
                "inventory_sha256": release_inventory_sha256(manifest.artifacts),
            },
            "epochs": [asdict(x) for x in manifest.fence.dependencies],
        }
        self.receipt.write_text(json.dumps(body), encoding="utf-8")

    def put(self, path, body):
        target = self.root / path.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)

    def audit(self, **kwargs):
        return audit_local_static_withdrawal(
            self.root, self.receipt, self.manifest, self.paths,
            revoked_dependencies=("rights:1",),
            current_fence=kwargs.pop("current_fence", self.fence),
            **kwargs,
        )

    def test_actual_html_api_search_sitemap_rdf_and_all_other_files_must_be_absent(self):
        clean = self.audit()
        self.assertEqual(clean.status, "CONSISTENT_UNATTESTED")
        self.assertEqual(clean.surface_count, len(self.paths))
        self.assertFalse(clean.withdrawal_verified_on_live_host)

        for path in self.paths:
            if path.entity_id == "person:revoked":
                self.put(path, f"old revoked words in {path.surface}".encode())
        stale = self.audit()
        self.assertEqual(stale.status, "UNSAFE_PUBLIC_VISIBILITY")
        self.assertEqual(set(stale.unsafe_surfaces), set(self.surfaces))
        for path in self.paths:
            if path.entity_id == "person:revoked":
                (self.root / path.relative_path).unlink()
        self.assertEqual(self.audit().status, "CONSISTENT_UNATTESTED")

    def test_cache_edge_survives_withdrawal_until_denied_and_epoch_changes_hold(self):
        edge = next(
            path for path in self.paths
            if path.entity_id == "person:revoked" and path.surface == "CACHE_EDGE"
        )
        self.put(edge, b"old cached quote")
        cache = self.audit()
        self.assertEqual(cache.status, "UNSAFE_PUBLIC_VISIBILITY")
        self.assertEqual(cache.unsafe_surfaces, ("CACHE_EDGE",))
        self.assertFalse(cache.cache_purge_verified)

        (self.root / edge.relative_path).unlink()
        self.assertEqual(self.audit().status, "CONSISTENT_UNATTESTED")
        newer = (MaterialEpoch("rights:1", 5, sha(b"rights")),
                 MaterialEpoch("source:other", 2, sha(b"source")))
        current = PublicationEpochTicket(
            self.fence.release_id, newer, _ticket_fingerprint(self.fence.release_id, newer)
        )
        self.assertEqual(self.audit(current_fence=current).status, "STALE_REVOCATION_EPOCH")

    def test_restore_of_old_release_metadata_or_stale_file_fails_then_safe_restore_recovers(self):
        old = replace(self.manifest, release_id="release:older")
        old_deps = self.fence.dependencies
        old_fence = PublicationEpochTicket(
            old.release_id, old_deps, _ticket_fingerprint(old.release_id, old_deps)
        )
        self.save_receipt(replace(old, fence=old_fence))
        self.assertEqual(self.audit().status, "READBACK_UNTRUSTED_OR_DRIFT")

        self.save_receipt()
        html = next(
            path for path in self.paths
            if path.entity_id == "person:revoked" and path.surface == "HTML"
        )
        self.put(html, b"restored revoked statement")
        self.assertEqual(self.audit().status, "UNSAFE_PUBLIC_VISIBILITY")
        (self.root / html.relative_path).unlink()
        self.assertEqual(self.audit().status, "CONSISTENT_UNATTESTED")

    def test_unaffected_search_digest_drift_does_not_look_like_complete_release(self):
        search = next(
            path for path in self.paths
            if path.entity_id == "person:safe" and path.surface == "SEARCH"
        )
        self.put(search, b'{"hits": ["unreviewed, stale old result"]}')
        result = self.audit()
        self.assertEqual(result.status, "READBACK_UNTRUSTED_OR_DRIFT")
        self.assertEqual(result.sanitized_reason_codes, ("LOCAL_UNAFFECTED_ARTIFACT_DRIFT",))

    def test_uninventoried_legacy_route_blocks_clean_withdrawal(self):
        self.assertEqual(self.audit().status, "CONSISTENT_UNATTESTED")
        legacy = self.root / "person:revoked" / "statement-old.html"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_bytes(b"old quote still served by legacy static route")
        result = self.audit()
        self.assertEqual(result.status, "READBACK_UNTRUSTED_OR_DRIFT")
        self.assertEqual(result.sanitized_reason_codes, ("LOCAL_UNINVENTORIED_PUBLIC_FILE",))
        self.assertNotIn("statement-old.html", repr(result))
        legacy.unlink()
        self.assertEqual(self.audit().status, "CONSISTENT_UNATTESTED")

    def test_uninventoried_build_assets_cannot_clear_revocation_absence_audit(self):
        for name, body in (
            ("_astro/layout.abc123.js", b"export const view = 'ok';"),
            ("_astro/layout.abc123.css", b"body { display: block }"),
            ("assets/brand.webp", b"webp fixture"),
            ("static/fonts/body.woff2", b"font fixture"),
        ):
            asset = self.root / name
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(body)
        # JS/CSS/images can themselves contain withdrawn text, HTML snippets,
        # or embedded body data. A suffix/directory allowlist is not a proof
        # that the bytes belong to the attested generation.
        unverified = self.audit()
        self.assertEqual(unverified.status, "READBACK_UNTRUSTED_OR_DRIFT")
        self.assertEqual(
            unverified.sanitized_reason_codes,
            ("LOCAL_UNINVENTORIED_PUBLIC_FILE",),
        )
        legacy = self.root / "_astro" / "search-old.json"
        legacy.write_bytes(b'{"hits":["revoked quote"]}')
        result = self.audit()
        self.assertEqual(result.status, "READBACK_UNTRUSTED_OR_DRIFT")
        self.assertEqual(result.sanitized_reason_codes, ("LOCAL_UNINVENTORIED_PUBLIC_FILE",))

    def test_uninventoried_js_with_stale_revoked_quote_fails_closed(self):
        asset = self.root / "_astro" / "stale.abc123.js"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b'window.staleQuote="REVOKED SYNTHETIC WORDING";')
        status = self.audit()
        self.assertEqual(status.status, "READBACK_UNTRUSTED_OR_DRIFT")
        self.assertEqual(status.sanitized_reason_codes, ("LOCAL_UNINVENTORIED_PUBLIC_FILE",))

    def test_private_release_receipt_hardlinked_as_js_never_passes_audit(self):
        asset = self.root / "_astro" / "release.abc123.js"
        asset.parent.mkdir(parents=True)
        os.link(self.receipt, asset)
        status = self.audit()
        self.assertEqual(status.status, "READBACK_UNTRUSTED_OR_DRIFT")
        self.assertEqual(status.sanitized_reason_codes, ("LOCAL_UNINVENTORIED_PUBLIC_FILE",))
        self.assertFalse(status.withdrawal_verified_on_live_host)
        self.assertNotIn(self.receipt.read_text(), repr(status))

    def test_uninventoried_symlink_route_cannot_hide_old_public_bytes(self):
        legacy = self.root / "old-quote.html"
        legacy.symlink_to(self.receipt)
        with self.assertRaisesRegex(ValueError, "DP518_LOCAL_PATH_UNSAFE"):
            self.audit()

    def test_selected_release_root_enumeration_errors_fail_closed(self):
        with patch(
            "dichiarazioni_pubbliche.distributed_withdrawal_audit_v1.os.scandir",
            side_effect=PermissionError("restricted release root"),
        ):
            with self.assertRaisesRegex(ValueError, "DP518_LOCAL_PATH_UNSAFE"):
                self.audit()

    def test_selected_release_root_entry_limit_fails_closed(self):
        with patch(
            "dichiarazioni_pubbliche.distributed_withdrawal_audit_v1."
            "_MAX_LOCAL_RELEASE_ENTRIES", 2,
        ):
            with self.assertRaisesRegex(ValueError, "DP518_LOCAL_SCAN_LIMIT_EXCEEDED"):
                self.audit()

    def test_symlink_escape_and_unmapped_routes_cannot_pass_local_readback(self):
        outside = self.root.parent / (self.root.name + "-outside")
        outside.write_bytes(b"do not inspect me")
        self.addCleanup(outside.unlink)
        path = next(x for x in self.paths if x.entity_id == "person:revoked")
        (self.root / path.relative_path).parent.mkdir(parents=True, exist_ok=True)
        (self.root / path.relative_path).symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "DP518_LOCAL_PATH_UNSAFE"):
            self.audit()
        (self.root / path.relative_path).unlink()
        with self.assertRaisesRegex(ValueError, "DP518_LOCAL_ROUTE_COVERAGE_INVALID"):
            audit_local_static_withdrawal(
                self.root, self.receipt, self.manifest, self.paths[:-1],
                revoked_dependencies=("rights:1",), current_fence=self.fence,
            )

    def test_private_epoch_receipt_inside_public_document_root_is_refused(self):
        public_receipt = self.root / "epoch-receipt.json"
        public_receipt.write_bytes(self.receipt.read_bytes())
        with self.assertRaisesRegex(ValueError, "DP518_LOCAL_RELEASE_RECEIPT_INVALID"):
            audit_local_static_withdrawal(
                self.root, public_receipt, self.manifest, self.paths,
                revoked_dependencies=("rights:1",), current_fence=self.fence,
            )

    def test_local_receipt_epoch_tamper_and_missing_receipt_fail_closed(self):
        document = json.loads(self.receipt.read_text(encoding="utf-8"))
        document["epochs"][0]["epoch"] -= 1
        self.receipt.write_text(json.dumps(document), encoding="utf-8")
        tampered = self.audit()
        self.assertEqual(tampered.status, "READBACK_UNTRUSTED_OR_DRIFT")
        self.assertEqual(tampered.sanitized_reason_codes, ("LOCAL_EPOCH_READBACK_DRIFT",))

        self.receipt.unlink()
        with self.assertRaisesRegex(ValueError, "DP518_LOCAL_RELEASE_RECEIPT_INVALID"):
            self.audit()


if __name__ == "__main__":
    unittest.main()
