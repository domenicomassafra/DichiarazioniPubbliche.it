"""Contract for the independently licensed Italian WikiNER model builder."""

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from dp158_train_wikiner_ner import parse_wikiner_sentence, verify_archive  # noqa: E402


class WikiNERTrainingTests(unittest.TestCase):
    def test_entity_boundaries_from_wikiner_iob1(self):
        record = ("Mario|NPR|I-PER Rossi|NPR|I-PER e|CON|O "
                  "Luca|NPR|I-PER Bianchi|NPR|I-PER a|PRE|O "
                  "Roma|NPR|I-LOC .|PON|O")
        text, entities = parse_wikiner_sentence(record)
        self.assertEqual(text, "Mario Rossi e Luca Bianchi a Roma .")
        self.assertEqual([(text[a:b], kind) for a, b, kind in entities], [
            ("Mario Rossi", "PER"), ("Luca Bianchi", "PER"), ("Roma", "LOC")
        ])

    def test_adjacent_distinct_entities_and_unsupported_labels(self):
        record = ("Eni|NPR|I-ORG Roma|NPR|B-LOC evento|NOM|I-MISC "
                  "diverso|ADJ|O")
        text, entities = parse_wikiner_sentence(record)
        self.assertEqual([(text[a:b], kind) for a, b, kind in entities], [
            ("Eni", "ORG"), ("Roma", "LOC")
        ])

    def test_archive_digest_is_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "WIKINER_ARCHIVE_DIGEST_MISMATCH"):
            verify_archive(Path(__file__), hashlib.sha256(b"other").hexdigest())


if __name__ == "__main__":
    unittest.main()
