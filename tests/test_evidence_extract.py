import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.evidence_extract import (  # noqa: E402
    exact_phrase_excerpt,
    extract_jsonstat_observations,
    extract_normattiva_hits,
    extract_visible_html_text,
)


class EvidenceExtractTests(unittest.TestCase):
    def test_jsonstat_decodes_dimensions_and_selectors(self):
        payload = {
            "class": "dataset",
            "id": ["geo", "time"],
            "size": [2, 2],
            "dimension": {
                "geo": {
                    "category": {
                        "index": {"IT": 0, "FR": 1},
                        "label": {"IT": "Italy", "FR": "France"},
                    }
                },
                "time": {
                    "category": {
                        "index": {"2026-01": 0, "2026-02": 1}
                    }
                },
            },
            "value": {"0": 1.5, "1": 1.7, "2": 2.0, "3": 2.1},
            "status": {"1": "p"},
        }
        rows = extract_jsonstat_observations(
            payload,
            selectors={"geo": "IT", "time": ["2026-02"]},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].value, 1.7)
        self.assertEqual(rows[0].reference_period, "2026-02")
        self.assertEqual(rows[0].labels["geo"], "Italy")
        self.assertEqual(rows[0].status, "p")

    def test_normattiva_returns_only_structured_metadata(self):
        rows = extract_normattiva_hits(
            {
                "listaAtti": [
                    {
                        "codiceRedazionale": "26G00001",
                        "denominazioneAtto": "LEGGE",
                        "numeroAtto": 1,
                        "dataGUStr": "01-01-2026",
                        "numeroGU": "1",
                        "dataEmanazione": "2026-01-01",
                        "titoloAtto": "Titolo",
                        "descrizioneAtto": "Descrizione",
                    }
                ]
            }
        )
        self.assertEqual(rows[0].codice_redazionale, "26G00001")
        self.assertEqual(rows[0].numero_atto, "1")

    def test_html_text_drops_script_and_exact_excerpt_is_deterministic(self):
        text = extract_visible_html_text(
            b"<html><script>secret()</script><body><p>Articolo 1. Il valore e' 10.</p></body></html>"
        )
        self.assertNotIn("secret", text)
        excerpt = exact_phrase_excerpt(text, "Il valore e' 10", context_characters=5)
        self.assertIsNotNone(excerpt)
        self.assertIn("Il valore e' 10", excerpt)

    def test_unknown_jsonstat_selector_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_DIMENSION"):
            extract_jsonstat_observations(
                {
                    "class": "dataset",
                    "id": ["geo"],
                    "size": [1],
                    "dimension": {
                        "geo": {"category": {"index": {"IT": 0}}}
                    },
                    "value": {"0": 1},
                },
                selectors={"evil": "x"},
            )


if __name__ == "__main__":
    unittest.main()
