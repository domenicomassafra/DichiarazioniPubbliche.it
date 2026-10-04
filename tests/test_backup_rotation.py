import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "ops" / "backup.sh"


class BackupRotationTests(unittest.TestCase):
    def _write_tool(self, root: Path, name: str, body: str) -> None:
        path = root / name
        path.write_text("#!/bin/sh\nset -eu\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _fake_env(self, fakebin: Path, *, keep: str = "10") -> dict[str, str]:
        self._write_tool(fakebin, "date", "echo 20260929T120000Z\n")
        self._write_tool(
            fakebin,
            "pg_dump",
            "file=''\nfor arg in \"$@\"; do\n  case \"$arg\" in --file=*) file=${arg#--file=} ;; esac\ndone\n[ -n \"$file\" ]\nprintf 'fake-dump-bytes' > \"$file\"\n",
        )
        self._write_tool(fakebin, "psql", "echo 0\n")
        self._write_tool(fakebin, "pg_restore", "exit 0\n")
        self._write_tool(
            fakebin,
            "sha256sum",
            "printf 'deadbeef  %s\\n' \"$1\"\n",
        )
        env = os.environ.copy()
        env["PATH"] = str(fakebin) + os.pathsep + env.get("PATH", "")
        env["DICHIARAZIONI_PUBBLICHE_BACKUP_KEEP"] = keep
        env.pop("DICHIARAZIONI_PUBBLICHE_PUBLIC_BUNDLE", None)
        return env

    def _run(self, backup_root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SCRIPT), str(backup_root), "postgresql:///fake"],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_same_second_backups_get_unique_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fakebin = root / "bin"
            fakebin.mkdir()
            backup_root = root / "backups"
            env = self._fake_env(fakebin)

            first = self._run(backup_root, env)
            second = self._run(backup_root, env)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertTrue((backup_root / "20260929T120000Z" / "dichiarazioni_pubbliche.dump").is_file())
            self.assertTrue((backup_root / "20260929T120000Z-001" / "dichiarazioni_pubbliche.dump").is_file())
            self.assertIn("BACKUP OK set=20260929T120000Z", first.stdout)
            self.assertIn("BACKUP OK set=20260929T120000Z-001", second.stdout)

    def test_rotation_removes_oldest_valid_sets_not_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fakebin = root / "bin"
            fakebin.mkdir()
            backup_root = root / "backups"
            backup_root.mkdir()
            for stamp in (
                "20260929T110000Z",
                "20260929T113000Z",
                "20260929T114500Z",
            ):
                d = backup_root / stamp
                d.mkdir()
                (d / "dichiarazioni_pubbliche.dump").write_bytes(b"old")
            env = self._fake_env(fakebin, keep="2")

            proc = self._run(backup_root, env)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            remaining = sorted(
                p.name
                for p in backup_root.iterdir()
                if p.is_dir() and (p / "dichiarazioni_pubbliche.dump").is_file()
            )
            self.assertEqual(remaining, ["20260929T114500Z", "20260929T120000Z"])
            self.assertTrue((backup_root / "20260929T120000Z" / "dichiarazioni_pubbliche.dump").is_file())
            self.assertIn("sets_kept=2", proc.stdout)
            self.assertIn("BACKUP rotate removing", proc.stdout)

    def test_invalid_keep_fails_before_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fakebin = root / "bin"
            fakebin.mkdir()
            env = self._fake_env(fakebin, keep="0")
            proc = self._run(root / "backups", env)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("must be an integer >= 1", proc.stderr)

    def test_script_has_post_rotation_fail_closed_guard(self):
        text = SCRIPT.read_text()
        self.assertIn("current dump missing after rotation", text)
        self.assertIn("current dump unreadable after rotation", text)
        self.assertIn('if [ "$dir" = "$SET_DIR" ]', text)


if __name__ == "__main__":
    unittest.main()
