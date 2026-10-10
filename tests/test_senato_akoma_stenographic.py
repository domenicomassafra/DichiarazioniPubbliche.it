"""Offline smoke/regression for an independently implemented official AKN reader."""

from __future__ import annotations

import hashlib
import unittest

from dichiarazioni_pubbliche.senato_akoma_stenographic import (
    SenatoAkomaError,
    import_senato_akoma_stenographic,
)


URL = (
    "https://raw.githubusercontent.com/SenatoDellaRepubblica/"
    "AkomaNtosoBulkData/" + "a" * 40
    + "/Leg19/Atto00055187/resaula/01457617-ra.akn.xml"
)
NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03"


def fixture() -> bytes:
    return f'''<akomaNtoso xmlns="{NS}">
      <debate contains="originalVersion">
        <meta>
          <identification><FRBRWork>
            <FRBRuri value="http://dati.senato.it/osr/RESAULA/2025-05-29/310" />
            <FRBRdate date="2025-05-29" name="presentazione" />
          </FRBRWork></identification>
          <references>
            <TLCPerson id="p32600" href="http://dati.senato.it/osr/Persona/32600" showAs="Castellone" />
            <TLCPerson id="p33022" href="http://dati.senato.it/osr/Persona/33022" showAs="Potenti" />
          </references>
        </meta>
        <debateBody title="Resoconto n.310 della legislatura 19">
          <debateSection>
            <speech by="#p32600"><from refersTo="#p32600">PRESIDENTE</from>
              <p>La seduta <b>inizia</b>.</p></speech>
            <speech by="#p33022"><from refersTo="#p33022">POTENTI</from>
              <p>Un dato: <i>zero</i>.</p></speech>
            <speech by="#p"><from refersTo="#p">PRESIDENTE</from>
              <p>Attribuzione sconosciuta.</p></speech>
          </debateSection>
        </debateBody>
      </debate>
    </akomaNtoso>'''.encode("utf-8")


def blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()


def imported(raw: bytes, *, url: str = URL, digest: str | None = None):
    return import_senato_akoma_stenographic(
        raw, source_raw_url=url, expected_blob_sha1=digest or blob_sha(raw)
    )


class SenatoAkomaTests(unittest.TestCase):
    def test_two_distinct_official_speakers_and_unknown_held(self):
        result = imported(fixture())
        self.assertEqual((result.sitting_date, result.sitting_number), ("2025-05-29", 310))
        self.assertEqual(result.source_license_id, "CC-BY-4.0")
        self.assertEqual(len(result.speeches), 2)
        self.assertEqual(len(result.held_speeches), 1)
        self.assertEqual(result.held_speeches[0].ordinal, 2)
        self.assertEqual(result.held_speeches[0].reason, "OFFICIAL_SPEAKER_REFERENCE_UNRESOLVED")
        self.assertEqual([s.official_display_name for s in result.speeches], ["Castellone", "Potenti"])
        self.assertNotEqual(result.speeches[0].official_person_uri, result.speeches[1].official_person_uri)
        self.assertEqual(result.speeches[0].presentation_label, "PRESIDENTE")
        self.assertTrue(result.speeches[0].review_text.endswith("inizia."))
        self.assertFalse(result.speeches[0].quote_or_person_approved)
        self.assertFalse(result.publication_authorized)
        self.assertEqual(result.source_rights_decision, "PENDING_OPERATOR_SCOPE_REVIEW")

    def test_same_bytes_are_stable_and_content_hashes_change_on_revision(self):
        first = imported(fixture())
        second = imported(fixture())
        self.assertEqual(first, second)
        changed = fixture().replace(b"Un dato", b"Due dati")
        amended = imported(changed)
        self.assertNotEqual(first.source_sha256, amended.source_sha256)
        self.assertNotEqual(first.speeches[1].review_text_sha256, amended.speeches[1].review_text_sha256)

    def test_commit_pin_and_blob_bytes_mandatory(self):
        raw = fixture()
        with self.assertRaisesRegex(SenatoAkomaError, "BLOB_MISMATCH"):
            imported(raw, digest="0" * 40)
        for url in (URL.replace("a" * 40, "master"),
                    URL.replace("SenatoDellaRepubblica", "Impersonator"),
                    URL.replace("resaula", "sommcomm"),
                    URL.replace("raw.githubusercontent.com", "evil.githubusercontent.com")):
            with self.subTest(url=url), self.assertRaisesRegex(SenatoAkomaError, "PINNED"):
                imported(raw, url=url)

    def test_document_type_sitting_identity_and_person_mapping_guard(self):
        raw = fixture()
        variants = (
            (b"/2025-05-29/310", b"/2025-05-29/311", "SITTING_MISMATCH"),
            (b"Persona/33022", b"Persona/33023", "PERSON_REFERENCE_INVALID"),
            (b"<speech by=\"#p33022\">", b"<speech by=\"#p32600\">", None),
            (b"<speech by=\"#p32600\">", b"<act by=\"#p32600\">", "XML_INVALID"),
        )
        for before, after, code in variants:
            with self.subTest(code=code):
                mutated = raw.replace(before, after)
                if code is None:
                    result = imported(mutated)
                    self.assertEqual(len(result.held_speeches), 2)  # speaker and from disagree
                else:
                    with self.assertRaisesRegex(SenatoAkomaError, code):
                        imported(mutated)

    def test_invalid_xml_dtd_and_unsupported_namespace_refused(self):
        for data, reason in (
            (b"<!DOCTYPE x [<!ENTITY x SYSTEM 'file:///etc/passwd'>]>" + fixture(), "DTD_FORBIDDEN"),
            (fixture().replace(b"CSD03", b"other"), "DOCUMENT_UNSUPPORTED"),
            (b"<broken", "XML_INVALID"),
            (b"X" * 3000001, "XML_SIZE_INVALID"),
        ):
            with self.subTest(reason=reason), self.assertRaisesRegex(SenatoAkomaError, reason):
                imported(data)


if __name__ == "__main__":
    unittest.main()
