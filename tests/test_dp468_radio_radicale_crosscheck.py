"""A separate video publisher's index is evidence, never a publication grant."""

import json
import unittest

from tools.dp468_radio_radicale_crosscheck import URL, PROFILES, crosscheck
from tools.dp468_senato_profile_crosscheck import MANIFEST, read_batch


class RadioRadicaleCrosscheckTests(unittest.TestCase):
    def setUp(self):
        self.source, self.batch = read_batch(MANIFEST.read_text(encoding="utf-8"))
        self.profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
        items = []
        for number, p in enumerate(self.profiles["observations"], 1):
            name = p["title"].split(" di ", 2)[-1].split(" - XIX", 1)[0]
            items.append(
                f'<li class="views-row intervento int{number}">'
                f'<span class="date-display-single" content="2025-05-29T10:01:00+02:00"></span>'
                f'<span class="subject"><a href="{URL}#i={number}">{name}</a></span></li>'
            )
        self.items = items

    def page(self, items=None):
        return (
            '<h1>Seduta 310ª (XIX legislatura)</h1>'
            '<script>"uploadDate":"2025-05-29"</script>'
            "<div id='vp-index-list'><ul>" + "".join(self.items if items is None else items)
            + "</ul></div>"
        ).encode("utf-8")

    def test_matches_all_16_but_never_grants_publication(self):
        result = crosscheck(self.source, self.batch, self.profiles, URL, self.page())
        self.assertEqual(result["matched"], 16)
        self.assertEqual(result["observations"][0]["speaker"], "Manfredi POTENTI")
        self.assertFalse(result["identity_approved"])
        self.assertTrue(all(not x["publication_authorized"] for x in result["observations"]))

    def test_wrong_publisher_session_or_speaker_order_fails_closed(self):
        cases = (
            (URL.replace("radioradicale.it", "example.org"), self.page(), "SOURCE_UNVERIFIED"),
            (URL, self.page().replace(b"Seduta 310", b"Seduta 309"), "SESSION_MISMATCH"),
            (URL, self.page(self.items[::-1]), "SPEAKER_INDEX_MISMATCH"),
            (URL, self.page(self.items[:-1]), "SPEAKER_INDEX_MISMATCH"),
            (URL, self.page().replace(b"2025-05-29T", b"2025-05-30T"), "SPEAKER_INDEX_MISMATCH"),
        )
        for url, body, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                crosscheck(self.source, self.batch, self.profiles, url, body)

    def test_profile_not_authorized_or_different_source_fails(self):
        for key, value in (("identity_approved", True), ("original_source_sha256", "0" * 64)):
            profiles = {**self.profiles, key: value}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "PROFILE_RECEIPT_INVALID"):
                crosscheck(self.source, self.batch, profiles, URL, self.page())


if __name__ == "__main__":
    unittest.main()
