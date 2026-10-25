"""Contract at the private DP-313 readback boundary (fictional HTML fixtures)."""

import hashlib
import unittest

from tools.dp313_curia_private_readback import evaluate_curia_private


TEXT = (
    "SENTENZA DELLA CORTE (Ottava Sezione) 25 giugno 2026 "
    "Con la sua impugnazione, VT chiede l’annullamento. "
    "Per questi motivi, la Corte (Ottava Sezione) dichiara e statuisce: "
    "1) La sentenza del Tribunale UE è annullata. "
    "2) La decisione di non iscrivere il nome di VT è annullata."
)


def specimen(text=TEXT):
    return (
        '<span class="outputEcli">ECLI:EU:C:2026:519</span>'
        '<div id="document_content"><p>' + text + "</p></div>"
    ).encode("utf-8")


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CuriaProceduralReadbackTests(unittest.TestCase):
    def test_realistic_legal_roles_and_negation_stay_private_held(self):
        receipt = evaluate_curia_private(specimen(), expected_sha256=digest(TEXT))
        self.assertEqual(receipt["state"], "PRIVATE_HOLD")
        self.assertEqual(receipt["source_sha256"], digest(TEXT))
        self.assertEqual(receipt["ecli"], "ECLI:EU:C:2026:519")
        self.assertEqual(receipt["span_roles"], [
            "PARTY_ALLEGATION", "COURT_DISPOSITION", "PRIOR_DECISION_QUOTATION",
        ])
        self.assertEqual(receipt["speakers"], [
            "person:vt-anonymized", "body:cjeu", "body:cjeu",
        ])
        self.assertEqual(receipt["underlying_fact_assessments"], [
            "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED",
        ])
        self.assertFalse(receipt["extraction_authorized"])
        self.assertFalse(receipt["publication_authorized"])
        self.assertTrue(all(s == "HOLD" for s in receipt["span_states"]))
        self.assertNotIn(TEXT, str(receipt))

    def test_source_mutation_fails_before_claim_parsing(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_DIGEST_CHANGED"):
            evaluate_curia_private(
                specimen(TEXT.replace("non iscrivere", "iscrivere")),
                expected_sha256=digest(TEXT),
            )

    def test_wrong_case_and_missing_content_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "ECLI_MISMATCH"):
            evaluate_curia_private(
                specimen().replace(b"2026:519", b"2026:520"),
                expected_sha256=digest(TEXT),
            )
        with self.assertRaisesRegex(ValueError, "DOCUMENT_CONTENT_MISSING"):
            evaluate_curia_private(
                specimen().replace(b'id="document_content"', b'id="unrelated_content"'),
                expected_sha256=digest(TEXT),
            )

    def test_missing_disposition_does_not_make_partial_case(self):
        incomplete = TEXT.split("Per questi motivi", 1)[0]
        with self.assertRaisesRegex(ValueError, "OFFICIAL_DOCUMENT_IDENTITY_UNVERIFIED"):
            evaluate_curia_private(
                specimen(incomplete), expected_sha256=digest(incomplete),
            )


if __name__ == "__main__":
    unittest.main()
