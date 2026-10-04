"""DP-601 — distribution metadata is a truthful, enforced contract.

These tests read the real `pyproject.toml` from the repository. They do not import
`tomllib` shims or cached state: the assertions are about the file a contributor
actually clones.
"""

from __future__ import annotations

import re
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _load() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


class DistributionMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = _load()
        self.project = self.data["project"]

    def test_build_backend_is_declared_and_pinned(self) -> None:
        build_system = self.data["build-system"]
        self.assertEqual(build_system["build-backend"], "setuptools.build_meta")
        self.assertEqual(build_system["requires"], ["setuptools>=68.0,<81.0"])

    def test_supported_python_range_is_declared(self) -> None:
        # An unbounded upper range is the drift that silently drops or adds a
        # supported minor version; DP-601 requires explicit bounds.
        self.assertEqual(self.project["requires-python"], ">=3.11,<4.0")
        for minor in ("3.11", "3.12", "3.13", "3.14"):
            self.assertIn(
                f"Programming Language :: Python :: {minor}",
                self.project["classifiers"],
            )

    def test_runtime_profile_declares_no_third_party_dependency(self) -> None:
        # AC-601.3: an install must never silently add a provider or database
        # client. The runtime is stdlib-only and reaches PostgreSQL through `psql`.
        self.assertEqual(self.project["dependencies"], [])

    def test_optional_dependency_groups_all_have_bounded_versions(self) -> None:
        groups = self.project["optional-dependencies"]
        self.assertIn("dev", groups)
        self.assertIn("postgres", groups)
        for group, requirements in groups.items():
            for requirement in requirements:
                with self.subTest(group=group, requirement=requirement):
                    self.assertRegex(
                        requirement,
                        r"^[A-Za-z0-9._-]+(?:==|>=)\d[\w.]*,\s*<\s*\d",
                        f"{group} requirement lacks lower+upper bounds: {requirement}",
                    )

    def test_only_the_import_compatible_package_is_shipped(self) -> None:
        tool = self.data["tool"]["setuptools"]
        self.assertEqual(
            tool["packages"],
            [
                "dichiarazioni_pubbliche",
                "dichiarazioni_pubbliche.ops",
                "dichiarazioni_pubbliche.policy",
            ],
        )
        self.assertEqual(
            tool["package-dir"],
            {
                "dichiarazioni_pubbliche": "poc/dichiarazioni_pubbliche",
                "dichiarazioni_pubbliche.ops": "poc/dichiarazioni_pubbliche/ops",
                "dichiarazioni_pubbliche.policy": "poc/dichiarazioni_pubbliche/policy",
            },
        )

    def test_console_scripts_resolve_to_real_callables(self) -> None:
        # A console script that names a missing `main` is a broken install.
        sys.path.insert(0, str(ROOT / "poc"))
        self.addCleanup(lambda: sys.path.remove(str(ROOT / "poc")))
        import importlib

        for name, target in self.project["scripts"].items():
            module_name, _, attribute = target.partition(":")
            with self.subTest(script=name):
                module = importlib.import_module(module_name)
                self.assertTrue(
                    callable(getattr(module, attribute, None)),
                    f"{name} points at {target}, which is not callable",
                )

    def test_repository_module_public_exports_resolve(self) -> None:
        sys.path.insert(0, str(ROOT / "poc"))
        self.addCleanup(lambda: sys.path.remove(str(ROOT / "poc")))
        import importlib

        for module_name in (
            "claim_repository",
            "finding_repository",
            "relation_repository",
            "verification_repository",
        ):
            with self.subTest(module=module_name):
                module = importlib.import_module(f"dichiarazioni_pubbliche.{module_name}")
                missing = [name for name in module.__all__ if not hasattr(module, name)]
                self.assertEqual(missing, [], f"{module_name} has broken __all__ exports")

    def test_license_metadata_matches_the_repository_license(self) -> None:
        self.assertEqual(self.project["license"], "Apache-2.0")
        self.assertIn(
            "Apache License",
            (ROOT / "LICENSE").read_text(encoding="utf-8").splitlines()[0].strip(),
        )
        self.assertIn("NOTICE", self.project["license-files"])

    def test_version_matches_the_canonical_version_source(self) -> None:
        # DP-604 owns the policy; this test only enforces the mapping so drift is
        # detectable rather than silent.
        version_file = ROOT / "VERSION"
        self.assertTrue(version_file.is_file(), "canonical VERSION file is missing")
        canonical = version_file.read_text(encoding="utf-8").strip()
        self.assertEqual(self.project["version"], canonical)


class ProvisionalNameTests(unittest.TestCase):
    """DP-601/DP-106 — stable baselines with a bounded config fallback window."""

    COMPATIBILITY_IDENTITY = {
        "distribution": "dichiarazioni-pubbliche",
        "python_package": "dichiarazioni_pubbliche",
        "python_source_root": "poc",
        "database_baseline": "db/schema.v1.sql",
        "queue_baseline": "db/job_queue.v1.sql",
    }

    def test_distribution_name_is_unchanged(self) -> None:
        self.assertEqual(_load()["project"]["name"], "dichiarazioni-pubbliche")

    def test_python_import_name_still_resolves(self) -> None:
        sys.path.insert(0, str(ROOT / "poc"))
        self.addCleanup(lambda: sys.path.remove(str(ROOT / "poc")))
        import dichiarazioni_pubbliche

        self.assertEqual(dichiarazioni_pubbliche.__name__, "dichiarazioni_pubbliche")

    def test_v1_baseline_files_are_present(self) -> None:
        for path in ("db/schema.v1.sql", "db/job_queue.v1.sql"):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), f"{path} is missing")

    def test_v0_config_files_are_present_during_compatibility_window(self) -> None:
        for path in (
            "config/source-registry.v0.json",
            "config/transcription-policy.v0.json",
        ):
            with self.subTest(path=path):
                self.assertTrue(
                    (ROOT / path).is_file(),
                    f"{path} must remain during the DP-106 compatibility window",
                )
        for path in (
            "config/source-registry.v1.json",
            "config/transcription-policy.v1.json",
        ):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), f"{path} is missing")

    def test_no_deprecated_alias_was_silently_introduced(self) -> None:
        # A new distribution name, package dir, or console script carrying a
        # post-rename brand would pre-empt DP-106/DP-701.
        data = _load()
        forbidden = re.compile(r"\bagli[-_]atti\b", re.IGNORECASE)
        self.assertIsNone(forbidden.search(data["project"]["name"]))
        for name in data["project"]["scripts"]:
            self.assertIsNone(
                forbidden.search(name),
                f"console script {name} pre-empts the DP-106/DP-701 name decision",
            )


if __name__ == "__main__":
    unittest.main()
