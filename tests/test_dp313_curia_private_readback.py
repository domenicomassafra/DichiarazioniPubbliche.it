"""Contract at the private DP-313 readback boundary (fictional HTML fixtures)."""

import hashlib
import unittest

from tools.dp313_curia_private_readback import evaluate_curia_private


TEXT = (
    "SENTENZA DELLA CORTE (Ottava Sezione) 25 giugno 2026 "
    "Con la sua impugnazione, VT chiede l’annullamento. "
    "Con decisione del 15 luglio 2022 inviata al ricorrente, la commissione "
    "giudicatrice ha respinto la sua domanda di riesame della decisione di non "
    "iscrivere il suo nome nell’elenco di riserva. "
    "Per questi motivi, la Corte (Ottava Sezione) dichiara e statuisce: "
    "1) La sentenza del Tribunale UE è annullata. "
    "2) La decisione del 15 luglio 2022, con la quale la commissione giudicatrice "
    "del concorso generale EPSO/AD/380/19 ha deciso, in seguito a riesame, "
    "di non iscrivere il nome di VT nell’elenco di riserva per l’assunzione di "
    "amministratori di grado AD 7 nel settore della cooperazione internazionale "
    "e della gestione degli aiuti a paesi terzi, è annullata."
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
            "PARTY_ALLEGATION", "PRIOR_DECISION_REPORTED_BY_COURT",
            "COURT_DISPOSITION", "COURT_ANNULMENT_OF_REPORTED_DECISION",
        ])
        self.assertEqual(receipt["speakers"], [
            "person:vt-anonymized", "body:cjeu", "body:cjeu", "body:cjeu",
        ])
        self.assertEqual(receipt["underlying_fact_assessments"], [
            "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED",
        ])
        self.assertFalse(receipt["extraction_authorized"])
        self.assertFalse(receipt["publication_authorized"])
        self.assertTrue(all(s == "HOLD" for s in receipt["span_states"]))
        self.assertNotIn(TEXT, str(receipt))

    def test_officially_reported_2022_decision_is_not_a_direct_quote_or_2026_status(self):
        """Curia C-622/24 P paras. 8 and operative 2: two acts, two dates."""
        receipt = evaluate_curia_private(specimen(), expected_sha256=digest(TEXT))
        self.assertEqual(receipt["assertion_kinds"], [
            "ALLEGATION", "ALLEGATION", "FINDING_ORDER", "FINDING_ORDER",
        ])
        self.assertEqual(receipt["quoted_authors"], [None] * 4)
        self.assertEqual(receipt["span_status_effective_dates"], [
            "2026-06-25", "2022-07-15", "2026-06-25", "2026-06-25",
        ])
        report = receipt["reported_prior_decision"]
        self.assertEqual(report["date_as_reported"], "2022-07-15")
        self.assertEqual(report["reported_by_ref"], "body:cjeu")
        self.assertIsNone(report["original_record_ref"])
        self.assertFalse(report["verbatim_original_quote_verified"])
        self.assertFalse(report["original_author_verified"])
        self.assertFalse(report["effective_date_verified"])
        report_locator = receipt["span_locators"][1]
        self.assertIn("Con decisione del 15 luglio 2022", TEXT[
            report_locator["start_char"]:report_locator["end_char"]
        ])
        annulment_locator = receipt["span_locators"][3]
        self.assertIn("è annullata.", TEXT[
            annulment_locator["start_char"]:annulment_locator["end_char"]
        ])

    def test_source_mutation_fails_before_claim_parsing(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_DIGEST_CHANGED"):
            evaluate_curia_private(
                specimen(TEXT.replace("non iscrivere", "iscrivere")),
                expected_sha256=digest(TEXT),
            )

    def test_prior_date_and_court_annulment_must_be_located_separately(self):
        changed_date = TEXT.replace(
            "Con decisione del 15 luglio 2022", "Con decisione del 15 luglio 2023",
        )
        with self.assertRaisesRegex(ValueError, "OFFICIAL_SPAN_MISSING"):
            evaluate_curia_private(specimen(changed_date), expected_sha256=digest(changed_date))

        no_second_order = TEXT.replace(
            "a paesi terzi, è annullata.", "a paesi terzi, resta pendente.",
        )
        with self.assertRaisesRegex(ValueError, "OFFICIAL_SPAN_MISSING"):
            evaluate_curia_private(specimen(no_second_order), expected_sha256=digest(no_second_order))

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
                specimen(incomplete), expected_sha256=digest(incomplete.strip()),
            )


if __name__ == "__main__":
    unittest.main()
