import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.retention import purge_transient_media


class RetentionTests(unittest.TestCase):
    def _make_content(self, root: Path, complete: bool = True) -> Path:
        content = root / "content-1"
        (content / "media").mkdir(parents=True)
        (content / "transcripts").mkdir()
        (content / "receipts").mkdir()
        (content / "media" / "video.mp4").write_bytes(b"x" * 1024)
        (content / "media" / "audio.m4a").write_bytes(b"y" * 512)
        (content / "transcripts" / "canonical.json").write_text('{"text":"ok"}')
        (content / "receipts" / "capture.json").write_text('{"sha256":"abc"}')
        status = "complete" if complete else "pending"
        (content / "manifest.json").write_text(
            json.dumps(
                {
                    "transcript_status": status,
                    "content_hash_status": "complete",
                    "provenance_status": "complete",
                }
            )
        )
        return content

    def test_purge_after_transcript_hash_and_provenance_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = self._make_content(Path(tmp))
            result = purge_transient_media(content)
            self.assertTrue(result.purged)
            self.assertEqual(result.bytes_freed, 1536)
            self.assertFalse((content / "media").exists())
            self.assertTrue((content / "transcripts" / "canonical.json").exists())
            self.assertTrue((content / "receipts" / "capture.json").exists())

    def test_fail_closed_while_transcript_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = self._make_content(Path(tmp), complete=False)
            result = purge_transient_media(content)
            self.assertFalse(result.purged)
            self.assertTrue((content / "media" / "video.mp4").exists())

    def test_fail_closed_when_durable_artifacts_are_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = self._make_content(Path(tmp))
            (content / "transcripts" / "canonical.json").unlink()
            result = purge_transient_media(content)
            self.assertFalse(result.purged)
            self.assertEqual(result.reason, "TRANSCRIPTS_NOT_DURABLE")
            self.assertTrue((content / "media" / "video.mp4").exists())

    def test_fail_closed_when_durable_artifact_dir_is_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = self._make_content(root)
            external = root / "external-transcripts"
            external.mkdir()
            (external / "canonical.json").write_text('{"text":"outside"}')
            shutil.rmtree(content / "transcripts")
            (content / "transcripts").symlink_to(external, target_is_directory=True)
            result = purge_transient_media(content)
            self.assertFalse(result.purged)
            self.assertEqual(result.reason, "TRANSCRIPTS_NOT_DURABLE")
            self.assertTrue((content / "media" / "video.mp4").exists())

    def test_invalid_manifest_never_authorizes_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = self._make_content(Path(tmp))
            (content / "manifest.json").write_text("{not-json")
            result = purge_transient_media(content)
            self.assertFalse(result.purged)
            self.assertEqual(result.reason, "MANIFEST_INVALID")
            self.assertTrue((content / "media" / "video.mp4").exists())

    def test_symlink_inside_media_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = self._make_content(root)
            outside = root / "outside.bin"
            outside.write_bytes(b"do-not-touch")
            (content / "media" / "outside-link").symlink_to(outside)
            result = purge_transient_media(content)
            self.assertFalse(result.purged)
            self.assertEqual(result.reason, "MEDIA_TREE_SYMLINK_REFUSED")
            self.assertEqual(outside.read_bytes(), b"do-not-touch")
