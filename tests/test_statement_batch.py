import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATEMENT = {
    "persona": "Sergio Mattarella",
    "data": "2025-12-31",
    "testo": "Ma nessun ostacolo è più forte della nostra democrazia.",
    "fonte_url": "https://www.quirinale.it/it/discorso/messaggio-fine-anno-presidente-repubblica-sergio-mattarella",
    "contesto": "Messaggio di fine anno al Quirinale.",
}


class StatementBatchTest(unittest.TestCase):
    def check_batch(self, *batches):
        with tempfile.TemporaryDirectory() as directory:
            for index, batch in enumerate(batches):
                Path(directory, f"{index}.json").write_text(json.dumps(batch), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "dichiarazioni_pubbliche.statement_batch", directory],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "poc")},
                capture_output=True,
                text=True,
                check=False,
            )
        return result.returncode, json.loads(result.stdout)

    def test_repeated_statement_is_counted_once_and_remains_private(self):
        code, report = self.check_batch([STATEMENT], [STATEMENT])
        self.assertEqual(code, 0)
        self.assertEqual(report["pending"], 1)
        self.assertEqual(report["duplicates"], 1)
        self.assertNotIn(STATEMENT["testo"], str(report))

    def test_rejects_bad_date_and_nonpublic_url_without_blocking_other_files(self):
        code, report = self.check_batch(
            [dict(STATEMENT, data="2025-02-31")],
            [dict(STATEMENT, fonte_url="https://127.0.0.1/test")],
            [STATEMENT],
        )
        self.assertEqual(code, 1)
        self.assertEqual(report["pending"], 1)
        self.assertEqual(report["errors"], [
            {"file": "0.json", "row": 1, "field": "data"},
            {"file": "1.json", "row": 1, "field": "fonte_url"},
        ])
