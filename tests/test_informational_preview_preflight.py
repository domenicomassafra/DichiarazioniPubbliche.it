"""Negative acceptance for the independent six-page informational preview fence."""

from __future__ import annotations

import hashlib
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from check_informational_preview import (  # noqa: E402
    PreviewPreflightError,
    check_preview_bundle,
    check_preview_projection,
    inspect_preview_governance,
    main,
)


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class InformationalPreviewPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        self.material = {"dossiers": [], "topics": [], "contents": []}
        self.sha = hashlib.sha256(canonical(self.material).encode()).hexdigest()
        self.projection = {
            **self.material,
            "schema_version": "dichiarazioni-pubbliche-public-v2",
            "dataset_sha256": self.sha,
            "dossier_count": 0,
            "generated_at": "2026-10-10T00:00:00Z",
            "methodology": {"aggregate_person_score": False},
        }
        self.projection_path = self.root / "index.json"
        self.write_projection()
        self.index = {
            "schema_version": "dichiarazioni-pubbliche-search-index-v1",
            "projection_schema_version": self.projection["schema_version"],
            "projection_sha256": self.sha,
            "generated_at": self.projection["generated_at"],
            "records": [],
        }
        self.write_index()
        self.create_site()

    def write_projection(self) -> None:
        self.projection_path.write_text(canonical(self.projection), encoding="utf-8")

    def write_index(self) -> None:
        index = dict(self.index)
        index["index_sha256"] = hashlib.sha256(canonical(self.index).encode()).hexdigest()
        (self.dist / "search-index.v1.json").write_text(canonical(index), encoding="utf-8")

    def create_site(self) -> None:
        routes = ["/", "/esplora/", "/metodo/", "/correzioni/", "/dati/", "/progetto/"]
        for route in [*routes, "/accedi/", "/account/"]:
            filename = self.dist / route.lstrip("/") / "index.html"
            filename.parent.mkdir(parents=True, exist_ok=True)
            policy = "noindex,nofollow" if route in ("/accedi/", "/account/") else "index,follow"
            filename.write_text(
                f'<html lang="it"><head><link rel="canonical" href="{route}">'
                f'<meta name="robots" content="{policy}"></head>'
                '<body><main id="main"><h1>Progetto pubblico</h1></main></body></html>',
                encoding="utf-8",
            )
        (self.dist / "robots.txt").write_text(
            "User-agent: *\nAllow: /\nSitemap: https://dichiarazionipubbliche.it/sitemap.xml\n",
            encoding="utf-8",
        )
        sitemap = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        sitemap += "".join(f"<url><loc>https://dichiarazionipubbliche.it{route}</loc></url>" for route in routes)
        (self.dist / "sitemap.xml").write_text(sitemap + "</urlset>", encoding="utf-8")

    def check(self, **kwargs: object) -> object:
        return check_preview_bundle(self.dist, self.sha, environment={}, **kwargs)

    def test_safe_empty_bundle_stays_mechanical_only(self):
        result = self.check(projection_path=self.projection_path)
        self.assertEqual(result["outcome"], "BUNDLE-PASS-NO-LAUNCH-AUTHORITY")
        self.assertEqual(result["public_routes"], 6)
        self.assertTrue(result["source_projection_checked"])

    def test_missing_source_is_explicitly_less_complete(self):
        result = self.check()
        self.assertFalse(result["source_projection_checked"])

    def test_missing_independent_fingerprint_and_demo_override_refused(self):
        with self.assertRaisesRegex(PreviewPreflightError, "EXPECTED_FINGERPRINT_REQUIRED"):
            check_preview_bundle(self.dist, self.sha[:4], environment={})
        with self.assertRaisesRegex(PreviewPreflightError, "DEMO_OVERRIDE_SET"):
            check_preview_bundle(
                self.dist,
                self.sha,
                environment={"DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION": ""},
            )

    def test_index_drift_or_self_consistent_poisoned_index_refused(self):
        self.index["records"] = [{"id": "finding:demo:1", "kind": "finding"}]
        self.write_index()
        with self.assertRaisesRegex(PreviewPreflightError, "NONEMPTY_SEARCH_INDEX"):
            self.check()
        self.index["records"] = []
        self.index["projection_sha256"] = "0" * 64
        self.write_index()
        with self.assertRaisesRegex(PreviewPreflightError, "SEARCH_FINGERPRINT_DRIFT"):
            self.check()

    def test_index_hash_tamper_refused(self):
        path = self.dist / "search-index.v1.json"
        indexed = json.loads(path.read_text(encoding="utf-8"))
        indexed["index_sha256"] = "0" * 64
        path.write_text(canonical(indexed), encoding="utf-8")
        with self.assertRaisesRegex(PreviewPreflightError, "SEARCH_INDEX_TAMPERED"):
            self.check()

    def test_private_studio_and_demo_assets_refused(self):
        path = self.dist / "studio" / "corpus" / "index.html"
        path.parent.mkdir(parents=True)
        path.write_text("private", encoding="utf-8")
        with self.assertRaisesRegex(PreviewPreflightError, "UNEXPECTED_HTML_ROUTE"):
            self.check()
        path.unlink()
        (self.dist / "demo-projection.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(PreviewPreflightError, "UNEXPECTED_PUBLIC_ARTIFACT"):
            self.check()

    def test_sensitive_body_marker_refused(self):
        filename = self.dist / "progetto" / "index.html"
        filename.write_text(filename.read_text() + "provider_receipt", encoding="utf-8")
        with self.assertRaisesRegex(PreviewPreflightError, "PRIVATE_OR_DEMO_MARKER"):
            self.check()

    def test_public_robots_sitemap_and_account_noindex_refused_on_drift(self):
        filename = self.dist / "account" / "index.html"
        filename.write_text(filename.read_text().replace("noindex,nofollow", "index,follow"), encoding="utf-8")
        with self.assertRaisesRegex(PreviewPreflightError, "PRIVATE_ROUTE_INDEXABLE"):
            self.check()
        self.create_site()
        (self.dist / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        with self.assertRaisesRegex(PreviewPreflightError, "ROBOTS_DRIFT"):
            self.check()
        self.create_site()
        (self.dist / "sitemap.xml").write_text("<urlset/>", encoding="utf-8")
        with self.assertRaisesRegex(PreviewPreflightError, "SITEMAP_.*DRIFT"):
            self.check()

    def test_projection_fingerprint_and_privacy_hold(self):
        self.assertEqual(check_preview_projection(self.projection_path, self.sha)["dataset_sha256"], self.sha)
        self.projection["dataset_sha256"] = "0" * 64
        self.write_projection()
        with self.assertRaisesRegex(PreviewPreflightError, "PROJECTION_FINGERPRINT_DRIFT"):
            self.check(projection_path=self.projection_path)
        self.projection["dataset_sha256"] = self.sha
        self.projection["rights_case"] = {"submitter_contact": "private@example.invalid"}
        self.write_projection()
        with self.assertRaisesRegex(PreviewPreflightError, "PRIVATE_OR_DEMO_MARKER"):
            self.check(projection_path=self.projection_path)

    def test_orphaned_studio_bundle_is_still_a_public_leak(self):
        # Even when Studio has no HTML route, its emitted JS is publicly fetchable.
        folder = self.dist / "_astro"
        folder.mkdir()
        (folder / "StudioReadOnlyWorkspace.js").write_text(
            'const sample={fixture_only:true};', encoding="utf-8"
        )
        with self.assertRaisesRegex(PreviewPreflightError, "PRIVATE_STUDIO_OR_DEMO_ASSET"):
            self.check()
        (folder / "StudioReadOnlyWorkspace.js").unlink()
        (folder / "StudioWorkspaceClient.js").write_text("export const ready=true;", encoding="utf-8")
        with self.assertRaisesRegex(PreviewPreflightError, "PRIVATE_STUDIO_OR_DEMO_ASSET"):
            self.check()

    def test_original_ticket_and_qualified_register_still_gate_preview(self):
        review_root = self.root / "governance"
        ticket_dir = review_root / "docs" / "tickets"
        ticket_dir.mkdir(parents=True)
        for item in ("DP-304", "DP-307", "DP-410", "DP-701", "DP-702"):
            (ticket_dir / f"{item}-fixture.md").write_text(
                f"# {item}\nStatus: DONE\n", encoding="utf-8"
            )
        plan_rows = "".join(
            f"| {item} | DONE | fixture | x |\n"
            for item in ("DP-304", "DP-307", "DP-410", "DP-701", "DP-702")
        )
        (review_root / "PLAN.md").write_text(plan_rows, encoding="utf-8")
        (review_root / "docs" / "policy").mkdir()
        legal_rows = "".join(
            f"| Q-306-{i:02d} (DP-301) | x | source | `DECIDED` | owner | surface | default | `CLOSED` |\n"
            for i in range(1, 17)
        )
        register = review_root / "docs" / "policy" / "legal-closure-register.md"
        register.write_text(legal_rows, encoding="utf-8")
        green_rows = inspect_preview_governance(review_root)
        self.assertEqual(green_rows["mechanical_policy_blockers"], [])
        self.assertEqual(green_rows["unresolved_qualified_review_rows"], [])
        self.assertFalse(green_rows["qualified_preview_scope_signed_off"])
        register.write_text(legal_rows.replace("`DECIDED`", "`OPEN`", 1), encoding="utf-8")
        (ticket_dir / "DP-304-fixture.md").write_text("# DP-304\nStatus: IN PROGRESS\n", encoding="utf-8")
        blocked_rows = inspect_preview_governance(review_root)
        self.assertIn("Q-306-01:OPEN", blocked_rows["unresolved_qualified_review_rows"])
        self.assertTrue(any("DP-304" in row for row in blocked_rows["mechanical_policy_blockers"]))

    def test_cli_bundle_mode_distinguished_from_required_human_review(self):
        args = ["--dist", str(self.dist), "--expected-fingerprint", self.sha,
                "--projection", str(self.projection_path), "--repository-root", str(ROOT)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 2)
            self.assertEqual(main(args + ["--bundle-only"]), 0)
            self.assertEqual(main([a for a in args if a not in
                                   ("--projection", str(self.projection_path))] + ["--bundle-only"]), 1)


if __name__ == "__main__":
    unittest.main()
