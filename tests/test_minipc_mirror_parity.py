from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


TOOL = Path(__file__).resolve().parent.parent / "tools" / "check_minipc_mirror_parity.py"
spec = importlib.util.spec_from_file_location("check_minipc_mirror_parity", TOOL)
assert spec is not None and spec.loader is not None
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)


class MiniPCMirrorParityTests(unittest.TestCase):
    def test_match_missing_drift_and_stale_remote_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "match.py").write_text("v1", encoding="utf-8")
            (repo / "drift.py").write_text("v2", encoding="utf-8")
            (repo / "missing.py").write_text("new", encoding="utf-8")
            paths = ["drift.py", "match.py", "missing.py", "deleted.py"]
            rows = parity.compare_paths(repo, paths, {
                "match.py": {"status": "FILE", "sha256": parity.sha256_path(repo / "match.py")},
                "drift.py": {"status": "FILE", "sha256": "1" * 64},
                "missing.py": {"status": "ABSENT"},
                "deleted.py": {"status": "FILE", "sha256": "2" * 64},
            })
            self.assertEqual(
                {row["path"]: row["status"] for row in rows},
                {"drift.py": "DRIFT", "match.py": "MATCH", "missing.py": "MISSING", "deleted.py": "STALE_REMOTE"},
            )

    def test_remote_mismatch_and_unsafe_paths_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            with self.assertRaisesRegex(ValueError, "does not match"):
                parity.compare_paths(repo, ["safe.py"], {})
            with self.assertRaisesRegex(ValueError, "Unsafe tracked path"):
                parity.compare_paths(repo, ["../outside"], {"../outside": {"status": "ABSENT"}})
            with self.assertRaisesRegex(ValueError, "malformed remote digest"):
                parity.compare_paths(repo, ["safe.py"], {"safe.py": {"status": "FILE", "sha256": "broken"}})

    def test_source_symlink_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "real.txt").write_text("private", encoding="utf-8")
            (repo / "alias.txt").symlink_to(repo / "real.txt")
            with self.assertRaisesRegex(ValueError, "Symlink"):
                parity.compare_paths(repo, ["alias.txt"], {"alias.txt": {"status": "ABSENT"}})


if __name__ == "__main__":
    unittest.main()
