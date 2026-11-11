"""The Senato profile cross-check never grants speech identity/publication."""

import unittest
from unittest.mock import Mock, patch

from tools.dp468_senato_profile_crosscheck import MANIFEST, crosscheck, fetch_profile, read_batch


class ProfileReadbackTests(unittest.TestCase):
    def test_manifest_selects_16_pinned_records(self):
        digest, rows = read_batch(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(len(digest), 64)
        self.assertEqual(len(rows), 16)
        self.assertEqual(rows[0], (3, "Potenti", 33022))

    def test_profile_card_is_a_document_check_not_public_identity_approval(self):
        body = (
            b"<html><title>Scheda di attivita di Manfredi POTENTI - "
            b"XIX Legislatura | Senato della Repubblica</title></html>"
        )
        fetch = Mock(return_value=(
            "https://www.senato.it/composizione/senatori/elenco-alfabetico/"
            "scheda-attivita?did=00033022", body,
        ))
        result = crosscheck(33022, "Potenti", fetch=fetch)
        self.assertEqual(result["status"], "PROFILE_DOCUMENT_MATCH_ONLY")
        self.assertFalse(result["speaker_attribution_approved"])
        self.assertFalse(result["publication_authorized"])
        self.assertEqual(len(result["html_sha256"]), 64)

    def test_wrong_person_or_redirect_keeps_hold(self):
        url = (
            "https://www.senato.it/composizione/senatori/elenco-alfabetico/"
            "scheda-attivita?did=00033022"
        )
        correct = b"<title>Mario Potenti - XIX Legislatura | Senato della Repubblica</title>"
        for final_url, body, reason in (
            (url.replace("00033022", "00033023"), correct, "DP468_PROFILE_DID_MISMATCH"),
            (url.replace("www.senato.it", "example.org"), correct, "DP468_PROFILE_DID_MISMATCH"),
            (url, correct.replace(b"Potenti", b"Altrui"), "DP468_PROFILE_IDENTITY_MISMATCH"),
            (url, correct.replace(b"XIX Legislatura", b"XVIII Legislatura"), "DP468_PROFILE_IDENTITY_MISMATCH"),
        ):
            with self.subTest(reason=reason, final_url=final_url), self.assertRaisesRegex(ValueError, reason):
                crosscheck(33022, "Potenti", fetch=lambda _did: (final_url, body))

    def test_duplicate_manifest_identity_fails(self):
        original = MANIFEST.read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "DP468_MANIFEST_SELECTION_INVALID"):
            read_batch(original.replace("| 6 | Pucciarelli | 32697 |", "| 6 | Pucciarelli | 33022 |"))

    def test_missing_manifest_candidate_fails(self):
        original = MANIFEST.read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "DP468_MANIFEST_SELECTION_INVALID"):
            read_batch(original.replace(
                "| 6 | Pucciarelli | 32697 | 417:540 | `33dfddb7fad615bf6d06359410e43028af6d20ab6fdc59bdfed76465d0545826` |",
                "",
            ))

    def test_curl_transport_fails_closed_on_empty_response_or_non_html(self):
        valid = (
            b"<title>Manfredi POTENTI - XIX Legislatura | Senato della Repubblica</title>"
        )
        final = b"https://www.senato.it/composizione/senatori/elenco-alfabetico/scheda-attivita?did=00033022"
        with patch("tools.dp468_senato_profile_crosscheck.subprocess.run") as execute:
            execute.return_value.stdout = valid + b"\n__DP468_FINAL__:" + final + b"\ntext/html; charset=utf-8"
            url, body = fetch_profile(33022)
            self.assertEqual(url.encode(), final)
            self.assertEqual(body, valid)
            execute.return_value.stdout = b"\n__DP468_FINAL__:" + final + b"\ntext/html"
            with self.assertRaisesRegex(ValueError, "DP468_PROFILE_HTTP_UNVERIFIED"):
                fetch_profile(33022)
            execute.return_value.stdout = valid + b"\n__DP468_FINAL__:" + final + b"\napplication/json"
            with self.assertRaisesRegex(ValueError, "DP468_PROFILE_HTTP_UNVERIFIED"):
                fetch_profile(33022)


if __name__ == "__main__":
    unittest.main()
