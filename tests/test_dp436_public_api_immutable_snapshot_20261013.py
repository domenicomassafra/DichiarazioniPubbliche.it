"""DP-436: v3 API quote must not change after bundle validation.

All values are synthetic. No real source, publication, HTTP or provider access.
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

from dichiarazioni_pubbliche import public_api  # noqa: E402
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    projection_dataset_sha256,
    validate_public_bundle,
)
from test_dp435_public_statement_seam import QUOTE, SHA  # noqa: E402
from test_dp436_public_statement_consumers import v3_bundle  # noqa: E402


PRIVATE = "PRIVATE RAW UNAPPROVED TRANSCRIPT"
PRIVATE_NAME = "PRIVATE UNAPPROVED IDENTITY"


class PublicStatementV3ApiSnapshotTests(unittest.TestCase):
    def test_list_and_detail_freeze_approved_public_bundle_before_validating(self):
        for mode in ("list", "detail"):
            with self.subTest(mode=mode):
                incoming = v3_bundle()
                original_digest = incoming["dataset_sha256"]
                original_source_url = incoming["statements"][0]["source_url"]
                original_locator = dict(incoming["statements"][0]["locator"])
                calls = []

                def mutate_incoming_after_real_validation(snapshot, *, allow_statement_v3):
                    result = validate_public_bundle(
                        snapshot, allow_statement_v3=allow_statement_v3
                    )
                    calls.append(True)
                    # A second thread/caller replaces mutable input immediately
                    # after validation, before the API assembles a response.
                    incoming["statements"][0]["original_text"] = PRIVATE
                    incoming["statements"][0]["speaker_name"] = PRIVATE_NAME
                    incoming["statements"][0]["source_url"] = (
                        "https://example.test/private-unapproved"
                    )
                    incoming["statements"][0]["locator"]["start_char"] = 0
                    return result

                with patch.object(
                    public_api, "validate_public_bundle",
                    side_effect=mutate_incoming_after_real_validation,
                ):
                    if mode == "list":
                        result = public_api.list_public_statements_v3(
                            incoming, allow_statement_v3=True,
                            current_public_dataset_sha256=original_digest,
                        )
                        quote = result["data"][0]
                    else:
                        result = public_api.get_public_statement_v3(
                            incoming, "statement:1", allow_statement_v3=True,
                            current_public_dataset_sha256=original_digest,
                        )
                        quote = result["data"]

                self.assertEqual(calls, [True], "real schema validation is required")
                self.assertNotEqual(
                    projection_dataset_sha256(incoming), original_digest,
                    "the original mutable input really changed after validation",
                )
                self.assertEqual(result["meta"]["dataset_sha256"], original_digest)
                self.assertEqual(quote["original"]["text"], QUOTE)
                self.assertEqual(quote["original"]["quote_sha256"], SHA(QUOTE))
                self.assertEqual(quote["original"]["locator"], original_locator)
                self.assertEqual(quote["person"]["name"], "Persona dimostrativa")
                self.assertEqual(quote["source"]["url"], original_source_url)
                self.assertEqual(
                    hashlib.sha256(quote["original"]["text"].encode()).hexdigest(),
                    quote["original"]["quote_sha256"],
                )
                self.assertNotIn(PRIVATE, str(result))
                self.assertNotIn(PRIVATE_NAME, str(result))


if __name__ == "__main__":
    unittest.main()
