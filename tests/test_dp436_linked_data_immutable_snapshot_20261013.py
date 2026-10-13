"""DP-436: linked-data v3 must not serialize caller mutations after validation.

Synthetic-only post-validation mutation; no source rights, HTTP or publication.
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche import linked_data  # noqa: E402
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    projection_dataset_sha256,
    validate_public_bundle,
)
from test_dp435_public_statement_seam import QUOTE, SHA, SOURCE  # noqa: E402
from test_dp436_public_statement_consumers import with_derived  # noqa: E402


PRIVATE = "PRIVATE RAW SOURCE BODY NOT AUTHORIZED"
PRIVATE_PERSON = "PRIVATE UNREVIEWED SPEAKER"
PRIVATE_SOURCE = "PRIVATE UNREVIEWED SOURCE"


def mutation_after_validation(incoming, calls):
    def validate_then_mutate(snapshot, *, allow_statement_v3):
        # Run the actual validator first, rather than bypassing publication
        # gates; the adversarial caller changes its input only afterward.
        result = validate_public_bundle(snapshot, allow_statement_v3=allow_statement_v3)
        calls.append(True)
        row = incoming["statements"][0]
        row["original_text"] = PRIVATE
        row["quote_sha256"] = SHA(PRIVATE)
        row["speaker_name"] = PRIVATE_PERSON
        row["source_title"] = PRIVATE_SOURCE
        row["source_sha256"] = "f" * 64
        row["source_url"] = "https://example.test/private-unapproved"
        row["locator"]["start_char"] = 0
        row["summary"]["text"] = PRIVATE
        return result

    return validate_then_mutate


class PublicV3LinkedDataSnapshotTests(unittest.TestCase):
    def test_jsonld_uses_prevalidation_detached_public_snapshot(self):
        incoming = with_derived()
        digest = incoming["dataset_sha256"]
        calls = []
        with patch.object(
            linked_data,
            "validate_public_bundle",
            side_effect=mutation_after_validation(incoming, calls),
        ):
            result = linked_data.projection_statement_v3_jsonld(
                incoming, allow_statement_v3=True
            )

        self.assertEqual(calls, [True])
        self.assertNotEqual(projection_dataset_sha256(incoming), digest)
        self.assertEqual(result["@graph"][0]["dp:projectionFingerprint"], digest)
        quote = result["@graph"][1]
        self.assertEqual(quote["text"], QUOTE)
        self.assertEqual(quote["dp:quoteSha256"], SHA(QUOTE))
        self.assertEqual(quote["dp:sourceSha256"], SHA(SOURCE))
        self.assertEqual(quote["dp:locator"]["start_char"], SOURCE.index(QUOTE))
        self.assertEqual(quote["isPartOf"]["name"], "Documento dimostrativo")
        self.assertEqual(quote["isPartOf"]["url"], "https://example.test/documento")
        self.assertEqual(
            quote["hasPart"][0]["text"], "Il costo dichiarato è dieci euro."
        )
        self.assertEqual(
            hashlib.sha256(quote["text"].encode()).hexdigest(),
            quote["dp:quoteSha256"],
        )
        for marker in (PRIVATE, PRIVATE_PERSON, PRIVATE_SOURCE):
            self.assertNotIn(marker, str(result))

    def test_ntriples_uses_prevalidation_detached_public_snapshot(self):
        incoming = with_derived()
        digest = incoming["dataset_sha256"]
        calls = []
        with patch.object(
            linked_data,
            "validate_public_bundle",
            side_effect=mutation_after_validation(incoming, calls),
        ):
            result = linked_data.projection_statement_v3_ntriples(
                incoming, allow_statement_v3=True
            )

        self.assertEqual(calls, [True])
        self.assertNotEqual(projection_dataset_sha256(incoming), digest)
        self.assertIn(f'"{QUOTE}"', result)
        self.assertIn(f'"{SHA(QUOTE)}"', result)
        self.assertIn(f'"{SHA(SOURCE)}"', result)
        self.assertIn(f'"{digest}"', result)
        self.assertIn('"Documento dimostrativo"', result)
        self.assertIn('"Il costo dichiarato è dieci euro."', result)
        self.assertIn(
            "<https://schema.org/url> <https://example.test/documento>", result
        )
        for marker in (PRIVATE, PRIVATE_PERSON, PRIVATE_SOURCE, "f" * 64):
            self.assertNotIn(marker, result)


if __name__ == "__main__":
    unittest.main()
