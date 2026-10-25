"""DP-367: file identity must remain protected during secret loading."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.public_account import read_secret_file


class AccountSecretFileTests(unittest.TestCase):
    def test_secret_file_replacement_with_symlink_is_refused_at_open(self):
        # Emulate a file swap between the path check and the actual open.
        # Both files have owner-only permissions: stat cannot distinguish them.
        with tempfile.TemporaryDirectory() as directory:
            keyfile = Path(directory) / "key"
            redirect = Path(directory) / "another-key"
            saved = Path(directory) / "saved-key"
            keyfile.write_text("initial-secret-123")
            redirect.write_text("swapped-secret-456")
            os.chmod(keyfile, 0o600)
            os.chmod(redirect, 0o600)
            real_read_bytes = Path.read_bytes
            real_open = os.open

            def swap():
                if not keyfile.is_symlink():
                    keyfile.rename(saved)
                    keyfile.symlink_to(redirect)

            def raced_read_bytes(file):
                if file == keyfile:
                    swap()
                return real_read_bytes(file)

            def raced_open(file, flags, *args, **kwargs):
                if Path(file) == keyfile:
                    swap()
                return real_open(file, flags, *args, **kwargs)

            with patch.object(Path, "read_bytes", raced_read_bytes), patch(
                "os.open", raced_open
            ), self.assertRaisesRegex(ValueError, "ACCOUNT_SECRET_SYMLINK"):
                read_secret_file(keyfile)


if __name__ == "__main__":
    unittest.main()
