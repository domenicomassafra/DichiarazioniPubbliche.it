"""DP-436: opt-in cross-format parity checks against a single approved projection.

Only synthetic, locally generated statement source/rights fixtures are used here.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.linked_data import (  # noqa: E402
    projection_statement_v3_jsonld,
    projection_statement_v3_ntriples,
)
from dichiarazioni_pubbliche.public_api import list_public_statements_v3  # noqa: E402
from dichiarazioni_pubbliche.public_projection import build_public_projection  # noqa: E402
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    projection_dataset_sha256,
)
from dichiarazioni_pubbliche.public_v3_consumer_parity import (  # noqa: E402
    PublicV3ConsumerParityError,
    verify_public_v3_consumer_parity,
)
from test_dp435_public_statement_seam import (  # noqa: E402
    IsolatedStatementSource,
    QUOTE,
    SHA,
    STAMP,
)
from test_dp436_public_statement_consumers import with_derived  # noqa: E402


def bundle(source=None):
    return build_public_projection(
        source or IsolatedStatementSource(),
        generated_at=STAMP,
        include_public_statements=True,
    )


def formats(payload):
    return {
        "api_payload": list_public_statements_v3(payload, allow_statement_v3=True,
            current_public_dataset_sha256=payload["dataset_sha256"]),
        "jsonld_payload": projection_statement_v3_jsonld(
            payload, allow_statement_v3=True
        ),
        "ntriples_payload": projection_statement_v3_ntriples(
            payload, allow_statement_v3=True
        ),
    }


class PublicV3ConsumerParityTests(unittest.TestCase):
    def test_no_implicit_v3_or_legacy_admission(self):
        projection = bundle()
        with self.assertRaises(PublicV3ConsumerParityError):
            verify_public_v3_consumer_parity(projection)
        legacy = copy.deepcopy(projection)
        legacy["schema_version"] = "dichiarazioni-pubbliche-public-v2"
        with self.assertRaises(PublicV3ConsumerParityError):
            verify_public_v3_consumer_parity(legacy, allow_statement_v3=True)

    def test_clean_typed_derived_artifacts_agree_and_replay(self):
        projection = with_derived()
        outputs = formats(projection)
        receipt = verify_public_v3_consumer_parity(
            projection,
            allow_statement_v3=True,
            **outputs,
        )
        self.assertEqual(receipt["dataset_sha256"], projection["dataset_sha256"])
        self.assertEqual(receipt["statement_count"], 1)
        self.assertEqual(
            receipt["statement_versions"],
            [
                {
                    "statement_id": "statement:1",
                    "version_id": "statement-version:1",
                    "quote_sha256": SHA(QUOTE),
                    "source_sha256": projection["statements"][0]["source_sha256"],
                }
            ],
        )
        self.assertEqual(
            receipt,
            verify_public_v3_consumer_parity(projection, allow_statement_v3=True),
        )
        self.assertNotIn("review_provenance", str(receipt))
        self.assertNotIn("PRIVATE", str(receipt))

    def test_api_mutations_fail_closed_even_if_other_formats_unchanged(self):
        projection = with_derived()
        for path, wrong in (
            (("meta", "dataset_sha256"), "f" * 64),
            (("meta", "public_schema_version"), "legacy"),
            (("data", 0, "statement_id"), "statement:another"),
            (("data", 0, "version_id"), "statement-version:stale"),
            (("data", 0, "original", "text"), "costa 20 euro"),
            (("data", 0, "original", "quote_sha256"), "0" * 64),
            (("data", 0, "original", "locator", "end_char"), 999),
            (("data", 0, "source", "version_id"), "source-version:obsolete"),
            (("data", 0, "source", "sha256"), "0" * 64),
            (("data", 0, "person", "id"), "person:someone-else"),
            (("data", 0, "summary", "wording_type"), "VERBATIM_ORIGINAL"),
            (("data", 0, "translation", "text"), QUOTE),
            (("data", 0, "translation", "source_quote_sha256"), "0" * 64),
            (("data", 0, "translation", "source_language"), "fr"),
        ):
            with self.subTest(path=path):
                outputs = formats(projection)
                target = outputs["api_payload"]
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = wrong
                with self.assertRaises(PublicV3ConsumerParityError):
                    verify_public_v3_consumer_parity(
                        projection,
                        allow_statement_v3=True,
                        **outputs,
                    )

    def test_jsonld_mutations_fail_closed_including_derived_as_quote(self):
        projection = with_derived()
        for path, wrong in (
            (("@graph", 0, "dp:projectionFingerprint"), "0" * 64),
            (("@graph", 1, "@type"), "CreativeWork"),
            (("@graph", 1, "identifier"), "statement:wrong"),
            (("@graph", 1, "text"), "sintesi, non parole originali"),
            (("@graph", 1, "dp:quoteSha256"), "0" * 64),
            (("@graph", 1, "dp:sourceSha256"), "0" * 64),
            (("@graph", 1, "dp:sourceVersion"), "source-version:stale"),
            (("@graph", 1, "dp:locator", "start_char"), 999),
            (("@graph", 1, "isPartOf", "@id"), "https://example.test/private"),
            (("@graph", 1, "hasPart", 0, "@type"), "Quotation"),
            (("@graph", 1, "hasPart", 1, "dp:wordingType"), "VERBATIM_ORIGINAL"),
            (("@graph", 1, "hasPart", 1, "dp:sourceQuoteSha256"), "0" * 64),
            (("@graph", 1, "hasPart", 1, "inLanguage"), "it"),
        ):
            with self.subTest(path=path):
                outputs = formats(projection)
                target = outputs["jsonld_payload"]
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = wrong
                with self.assertRaises(PublicV3ConsumerParityError):
                    verify_public_v3_consumer_parity(
                        projection,
                        allow_statement_v3=True,
                        **outputs,
                    )

    def test_rdf_tamper_and_injected_private_triples_rejected(self):
        projection = with_derived()
        original = formats(projection)
        for rdf in (
            original["ntriples_payload"].replace('"VERBATIM_ORIGINAL"', '"PARAPHRASE"'),
            original["ntriples_payload"].replace(
                '"' + SHA(QUOTE) + '"', '"' + "0" * 64 + '"'
            ),
            original["ntriples_payload"].replace(
                '"source-version:1"', '"source-version:old"'
            ),
            original["ntriples_payload"]
            + '<https://example.test/private> <https://schema.org/text> "RAW CAPTURE" .\n',
            original["ntriples_payload"].replace('"SUMMARY"', '"VERBATIM_ORIGINAL"'),
            original["ntriples_payload"].replace(
                '"TRANSLATION"', '"VERBATIM_ORIGINAL"'
            ),
        ):
            with self.subTest(rdf=rdf[-100:]):
                outputs = formats(projection)
                outputs["ntriples_payload"] = rdf
                with self.assertRaises(PublicV3ConsumerParityError):
                    verify_public_v3_consumer_parity(
                        projection,
                        allow_statement_v3=True,
                        **outputs,
                    )

    def test_multiple_statements_sort_parity_and_no_silent_omission(self):
        projection = with_derived()
        earlier = copy.deepcopy(projection["statements"][0])
        earlier.update(
            {
                "statement_id": "statement:0",
                "version_id": "statement-version:0",
                "person_id": "person:0",
                "content_id": "content:0",
                "speaker_name": "Altra persona dimostrativa",
                "speech_act": "REPORTED_QUOTE",
                "endorsed": False,
                "summary": None,
                "translation": None,
            }
        )
        projection["statements"].append(earlier)
        projection["dataset_sha256"] = projection_dataset_sha256(projection)
        outputs = formats(projection)
        self.assertEqual(
            [item["statement_id"] for item in outputs["api_payload"]["data"]],
            ["statement:0", "statement:1"],
        )
        self.assertEqual(
            verify_public_v3_consumer_parity(
                projection,
                allow_statement_v3=True,
                **outputs,
            )["statement_count"],
            2,
        )
        for surface in ("api_payload", "jsonld_payload"):
            with self.subTest(surface=surface):
                modified = copy.deepcopy(outputs)
                key = "data" if surface == "api_payload" else "@graph"
                modified[surface][key].pop()
                if surface == "api_payload":
                    modified[surface]["meta"]["count"] = 1
                with self.assertRaises(PublicV3ConsumerParityError):
                    verify_public_v3_consumer_parity(
                        projection,
                        allow_statement_v3=True,
                        **modified,
                    )
        first = outputs["jsonld_payload"]["@graph"][1]
        self.assertEqual(first["dp:speechAct"], "REPORTED_QUOTE")
        self.assertFalse(first["dp:endorsed"])
        self.assertNotIn("author", first)

    def test_stale_projection_revocation_rejects_all_old_artifacts(self):
        source = IsolatedStatementSource()
        old = bundle(source)
        old_artifacts = formats(old)
        source.gates["rights"]["status"] = "REVOKED"
        current = bundle(source)
        self.assertEqual(current["statements"], [])
        report = verify_public_v3_consumer_parity(current, allow_statement_v3=True)
        self.assertEqual(report["statement_count"], 0)
        self.assertEqual(report["statement_versions"], [])
        with self.assertRaises(PublicV3ConsumerParityError):
            verify_public_v3_consumer_parity(
                current,
                allow_statement_v3=True,
                **old_artifacts,
            )
        self.assertNotEqual(old["dataset_sha256"], current["dataset_sha256"])

    def test_timed_original_escapes_and_shifts_preserve_span_and_text(self):
        source = IsolatedStatementSource(source_kind="TIMED")
        original = 'La cifra è "10"\tunità.\nNon 20.'
        source.source_text = f"Contesto: {original} Poi segue altro."
        start = source.source_text.index(original)
        source.row.update(
            {
                "original_text": original,
                "source_sha256": SHA(source.source_text),
                "locator": {
                    "start_char": start,
                    "end_char": start + len(original),
                    "segment_id": "segment:1",
                    "start_ms": 2000,
                    "end_ms": 4000,
                },
            }
        )
        for attestation in source.gates.values():
            attestation.update(
                {
                    "source_sha256": SHA(source.source_text),
                    "quote_sha256": SHA(original),
                    "span_start": start,
                    "span_end": start + len(original),
                }
            )
        projection = bundle(source)
        self.assertEqual(len(projection["statements"]), 1)
        self.assertEqual(
            verify_public_v3_consumer_parity(projection, allow_statement_v3=True)[
                "statement_versions"
            ][0]["quote_sha256"],
            SHA(original),
        )

    def test_rehashed_bundle_with_forged_quote_and_invalid_derived_cannot_pass(self):
        projection = with_derived()
        projection["statements"][0]["translation"]["source_quote_sha256"] = "0" * 64
        projection["dataset_sha256"] = projection_dataset_sha256(projection)
        with self.assertRaises(PublicV3ConsumerParityError):
            verify_public_v3_consumer_parity(projection, allow_statement_v3=True)


if __name__ == "__main__":
    unittest.main()
