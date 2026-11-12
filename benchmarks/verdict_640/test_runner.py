"""One end-to-end behavior test of three rows, command adapter and printed metrics."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


RUNNER = Path(__file__).with_name("runner.py")


class VerdictRunnerTest(unittest.TestCase):
    def test_three_rows_command_contract_and_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            data = folder / "sample.jsonl"
            output = folder / "report.json"
            adapter = folder / "adapter.py"
            rows = [
                {"id": "ok", "quote": "corretto", "label": "vero"},
                {"id": "wrong", "quote": "sbagliato", "label": "falso"},
                {"id": "invalid", "quote": "non valido", "label": "opinione"},
            ]
            for row in rows:
                row.update({"person": "Autore", "date": "2026-11-01", "source_url": "https://example.org/source", "evidence": [{"url": "https://example.org/one", "note": "Fonte uno"}, {"url": "https://example.org/two", "note": "Fonte due"}]})
            data.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
            adapter.write_text(
                "import json, sys\n"
                "request = json.load(sys.stdin)\n"
                "assert 'label' not in request and 'evidence' not in request\n"
                "response = {'label': 'unknown' if request['statement'] == 'non valido' else 'vero', 'evidence': [], 'model_calls': 2}\n"
                "print(json.dumps(response))\n", encoding="utf-8"
            )
            done = subprocess.run([sys.executable, str(RUNNER), "--data", str(data), "--command", f"{sys.executable} {adapter}", "--report-json", str(output)], text=True, capture_output=True, timeout=10)
            self.assertEqual(done.returncode, 1, done.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual((report["total"], report["correct"], report["model_calls_total"]), (3, 1, 5))
            self.assertEqual([case["actual"] for case in report["cases"]], ["vero", "vero", "ERRORE"])
            self.assertIn("accuracy: 33.3%", done.stdout)
            self.assertIn("wrong: atteso=falso, ottenuto=vero", done.stdout)
            self.assertIn("invalid: atteso=opinione, ottenuto=ERRORE", done.stdout)
            self.assertIn("Chiamate per dichiarazione: ok=2, wrong=2, invalid=1", done.stdout)
            self.assertIn("mediana=", done.stdout)


if __name__ == "__main__":
    unittest.main()
