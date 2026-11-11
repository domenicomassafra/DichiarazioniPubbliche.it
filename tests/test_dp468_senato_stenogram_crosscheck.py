"""DP-468 official stenogram cross-check is evidence, never publication authority."""

import unittest

from tools.dp468_senato_stenogram_crosscheck import (
    TOC_URL, _OfficialSpeech, _TocLinks, _candidate_links, validate_intervention,
)


URL = (
    "https://www.senato.it/show-doc?id=1457617&leg=19&"
    "part=doc_dc-ressten_rs-ddltit_intervento_potentirelatore&tipodoc=Resaula"
)
BODY = (
    b'<div class="bgt"><p><a href="https://www.senato.it/loc/link.asp?'
    b'leg=19&amp;tipodoc=sanasen&amp;id=33022">POTENTI</a>'
    b'Sono le parole <i>esatte</i> pronunciate.</p></div>'
)


class OfficialStenogramTests(unittest.TestCase):
    def test_article_binds_exact_wording_and_senate_person_id(self):
        self.assertEqual(len(validate_intervention(
            URL, BODY, 33022, "Sono le parole esatte pronunciate.",
        )), 64)

    def test_quote_in_navigation_or_script_cannot_pass(self):
        navigation_only = (
            b'<script>Sono le parole esatte pronunciate.</script>'
            b'<div class="bgt"><p><a href="https://www.senato.it/loc/link.asp?'
            b'leg=19&amp;tipodoc=sanasen&amp;id=33022">POTENTI</a>'
            b'Testo diverso.</p></div>'
        )
        with self.assertRaisesRegex(ValueError, "WORDING_OR_SPEAKER_MISMATCH"):
            validate_intervention(URL, navigation_only, 33022, "Sono le parole esatte pronunciate.")

    def test_script_embedded_in_article_cannot_supply_missing_quote(self):
        embedded = (
            b'<div class="bgt"><p><a href="https://www.senato.it/loc/link.asp?'
            b'leg=19&amp;tipodoc=sanasen&amp;id=33022">POTENTI</a>'
            b'Testo diverso.</p><script>Sono le parole esatte pronunciate.</script></div>'
        )
        with self.assertRaisesRegex(ValueError, "WORDING_OR_SPEAKER_MISMATCH"):
            validate_intervention(URL, embedded, 33022, "Sono le parole esatte pronunciate.")

    def test_wrong_speaker_quote_and_source_are_held(self):
        for url, body, did, quote, error in (
            (URL, BODY, 33023, "Sono le parole esatte pronunciate.", "WORDING_OR_SPEAKER_MISMATCH"),
            (URL, BODY, 33022, "Sono altre parole pronunciate.", "WORDING_OR_SPEAKER_MISMATCH"),
            (URL.replace("www.senato.it", "example.com"), BODY, 33022,
             "Sono le parole esatte pronunciate.", "LINK_INVALID"),
            (URL.replace("www.senato.it", "www.senato.it:8443"), BODY, 33022,
             "Sono le parole esatte pronunciate.", "LINK_INVALID"),
            (URL.replace("id=1457617", "id=1457618"), BODY, 33022,
             "Sono le parole esatte pronunciate.", "LINK_INVALID"),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                validate_intervention(url, body, did, quote)

    def test_toc_filters_by_visible_person_label(self):
        p = _TocLinks()
        p.feed(
            '<a class="toc-link" href="/show-doc?id=1457617&amp;leg=19&amp;'
            'part=doc_dc-ressten_rs-potenti&amp;tipodoc=Resaula">POTENTI, relatore</a>'
            '<a class="toc-link" href="/show-doc?id=1457617&amp;leg=19&amp;'
            'part=doc_dc-ressten_rs-verini&amp;tipodoc=Resaula">VERINI</a>'
        )
        self.assertEqual(len(_candidate_links(p.links, "Potenti")), 1)
        self.assertIn("id=1457617", _candidate_links(p.links, "Potenti")[0])
        with self.assertRaisesRegex(ValueError, "TOC_SPEAKER_MISSING"):
            _candidate_links(p.links, "Maiorino")
        with self.assertRaisesRegex(ValueError, "LINK_INVALID"):
            _candidate_links([("POTENTI", "https://example.net/show-doc")], "Potenti")

    def test_html_parser_excludes_outer_content(self):
        p = _OfficialSpeech()
        p.feed((b'<div>Injected words</div>' + BODY + b'<p>More injected words</p>').decode())
        self.assertNotIn("Injected words", p.text)
        self.assertIn(33022, p.person_dids)


if __name__ == "__main__":
    unittest.main()
