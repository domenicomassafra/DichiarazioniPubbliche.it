import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class PublicWebBoundaryTests(unittest.TestCase):
    def test_private_studio_routes_are_explicitly_non_public(self):
        studio_root = WEB / "src" / "pages" / "studio"
        self.assertTrue(studio_root.is_dir())
        routes = tuple(sorted(studio_root.glob("*/index.astro")))
        self.assertEqual({path.parent.name for path in routes}, {"[workspace]"})
        source = routes[0].read_text()
        self.assertIn("BaseLayout", source)
        self.assertRegex(source, r"<BaseLayout\b[^>]*\bstudio(?:\s|>)")
        self.assertIn('DICHIARAZIONI_PUBBLICHE_STUDIO_FIXTURE_ONLY', source)
        self.assertIn("if (!allowFixture) return [];", source)
        for workspace in ("corpus", "inbox", "collections", "verify"):
            self.assertIn(f'"{workspace}"', source)

        layout = (WEB / "src" / "layouts" / "BaseLayout.astro").read_text()
        self.assertIn(
            'const robotsPolicy = studio || usingDemoProjection ? "noindex,nofollow" : "index,follow";',
            layout,
        )
        self.assertIn('<meta name="robots" content={robotsPolicy}', layout)

        prototype = WEB / "prototypes" / "verify-studio" / "README.md"
        self.assertTrue(prototype.is_file())
        self.assertIn("private", prototype.read_text().lower())

    def test_public_projection_fails_closed_without_explicit_input(self):
        source = (WEB / "src" / "lib" / "projection.ts").read_text()
        self.assertIn("DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH is required", source)
        self.assertIn('DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION === "1"', source)
        self.assertNotIn("if (!configuredPath) {\n    assertProjection(demoProjection)", source)

    def test_public_home_and_footer_do_not_link_private_studio(self):
        home = (WEB / "src" / "pages" / "index.astro").read_text()
        layout = (WEB / "src" / "layouts" / "BaseLayout.astro").read_text()
        self.assertNotIn("/studio/", home)
        self.assertNotIn("/studio/", layout)
        self.assertNotIn("demoContentAudit", home)

    def test_canonical_content_route_is_projection_backed_not_demo_only(self):
        source = (WEB / "src" / "pages" / "contenuti" / "[slug].astro").read_text()
        self.assertIn("loadPublicProjection", source)
        self.assertIn("contentSlug", source)
        self.assertIn("projection.dossiers", source)
        self.assertNotIn("demoContentAudit", source)
        self.assertNotIn("ContentAuditClient", source)
        self.assertNotIn("DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION", source)


if __name__ == "__main__":
    unittest.main()
