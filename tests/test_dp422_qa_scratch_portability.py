"""DP-422 QA scripts must keep Astro scratch dirs on the checkout filesystem.

The SSR checks build an isolated Astro output with `--outDir` and Astro moves
the prerendered assets there with `fs.rename`. When the scratch directory is
created under `os.tmpdir()` (a tmpfs on Linux) while `web/.astro/` lives on
disk, that rename fails with `EXDEV: cross-device link not permitted` and the
QA script aborts before asserting anything. This guard keeps every
Astro-driven check on `web/scripts/lib/scratch.mjs`.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "web" / "scripts" / "lib" / "scratch.mjs"


def _astro_build_scripts():
    """Scripts that drive `astro build --outDir` into an isolated scratch directory."""
    paths = sorted((ROOT / "web" / "scripts").glob("*.mjs")) + sorted((ROOT / "tests").glob("*.mjs"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if "--outDir" in text:
            yield path, text


class QaScratchPortabilityTest(unittest.TestCase):
    def test_helper_defaults_inside_the_web_package(self):
        text = HELPER.read_text(encoding="utf-8")
        self.assertIn("DP_SCRATCH_ROOT", text)
        self.assertIn('new URL("../../", import.meta.url)', text)

    def test_astro_build_scripts_are_covered(self):
        covered = [str(path.relative_to(ROOT)) for path, _ in _astro_build_scripts()]
        self.assertIn("web/scripts/check-public-topic-v3.mjs", covered)
        self.assertIn("tests/dp429_explore_accessibility_regression.mjs", covered)

    def test_astro_builds_do_not_use_the_system_tmpdir(self):
        offenders = [
            str(path.relative_to(ROOT))
            for path, text in _astro_build_scripts()
            if "tmpdir(" in text
        ]
        self.assertEqual(offenders, [], "Astro scratch dirs must not use os.tmpdir()")


if __name__ == "__main__":
    unittest.main()
