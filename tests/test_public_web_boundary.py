import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class PublicWebBoundaryTests(unittest.TestCase):
    def test_private_studio_is_not_a_public_static_route(self):
        self.assertFalse((WEB / "src" / "pages" / "studio").exists())
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
