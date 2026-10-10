"""DP-234: official Senato OpenData RDF field contract, metadata only.

The two assembly sitting IDs/dates/numbers are from the observed 2026-10-10
Senato OpenData Leg19 dump-sedute-19.zip (CC BY 3.0, Senato attribution).
No transcript, third-party media or legal authorization is reproduced here.
"""

import io
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.senato_open_data_sedute import (
    ZIP_MEMBER,
    SenatoOpenDataError,
    import_senato_open_data_sittings,
)
from dichiarazioni_pubbliche.dvns_source_suitability import derive_dvns_candidate_suitability, HELD
from dichiarazioni_pubbliche.source_intelligence import load_source_intelligence_contract

SOURCE_ROWS = '''<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:osr="http://dati.senato.it/osr/">
<rdf:Description rdf:about="http://dati.senato.it/sedutaassemblea/23908">
  <osr:legislatura rdf:datatype="http://www.w3.org/2001/XMLSchema#integer">19</osr:legislatura>
  <osr:dataSeduta rdf:datatype="http://www.w3.org/2001/XMLSchema#date">2022-10-13</osr:dataSeduta>
  <osr:numeroSeduta rdf:datatype="http://www.w3.org/2001/XMLSchema#integer">1</osr:numeroSeduta>
  <rdf:type rdf:resource="http://dati.senato.it/osr/SedutaAssemblea" />
</rdf:Description>
<rdf:Description rdf:about="http://dati.senato.it/sedutaassemblea/23909">
  <osr:legislatura rdf:datatype="http://www.w3.org/2001/XMLSchema#integer">19</osr:legislatura>
  <osr:dataSeduta rdf:datatype="http://www.w3.org/2001/XMLSchema#date">2022-10-19</osr:dataSeduta>
  <osr:numeroSeduta rdf:datatype="http://www.w3.org/2001/XMLSchema#integer">2</osr:numeroSeduta>
  <rdf:type rdf:resource="http://dati.senato.it/osr/SedutaAssemblea" />
</rdf:Description>
<rdf:Description rdf:about="http://dati.senato.it/sedutacommissione/19-0-1-0-10">
  <osr:tipoSeduta rdf:datatype="http://www.w3.org/2001/XMLSchema#string">antimeridiana</osr:tipoSeduta>
  <osr:legislatura rdf:datatype="http://www.w3.org/2001/XMLSchema#integer">19</osr:legislatura>
  <osr:dataSeduta rdf:datatype="http://www.w3.org/2001/XMLSchema#date">2022-12-07</osr:dataSeduta>
  <osr:commissione rdf:resource="http://dati.senato.it/commissione/0-1" />
  <rdf:type rdf:resource="http://dati.senato.it/osr/SedutaCommissione" />
</rdf:Description>
</rdf:RDF>'''


def archive(xml=SOURCE_ROWS, name=ZIP_MEMBER):
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED) as writer:
        writer.writestr(name, xml)
    return content.getvalue()


class SenatoOpenDataSittingsTests(unittest.TestCase):
    def test_real_rdf_schema_maps_to_candidate_only_dp234_without_speech_rights(self):
        blob = archive()
        imported = import_senato_open_data_sittings(blob, observed_at_utc="2026-10-10T10:30:00Z")
        self.assertEqual(imported.rows_imported, 2)  # Ignore commission meetings (no assembly number).
        self.assertEqual(imported.source_dataset_url.split("/OpenData/")[-1], "main/Leg19/dump-sedute-19.zip")
        self.assertEqual(imported.observed_license_scope, "CC-BY-3.0 (official OpenData datasets only)")
        self.assertEqual(imported.rights_gate, "BLOCKED_PENDING_PROJECT_SOURCE_PROFILE_REVIEW")
        self.assertEqual(imported.imported.rights_status, "BLOCKED")
        self.assertEqual(imported.imported.authority_scope, "STRUCTURED_EVIDENCE_CANDIDATE_ONLY")
        self.assertEqual(imported.imported.normalized_batch.fetch_state, "SUCCEEDED")
        rows = imported.imported.normalized_batch.values
        self.assertEqual([row.value_numeric for row in rows], [1, 2])
        self.assertEqual([row.reference_period for row in rows], ["2022-10-13", "2022-10-19"])
        self.assertEqual([row.publication_date for row in rows], [None, None])
        self.assertEqual([row.source_roles for row in rows], [(), ()])
        self.assertEqual(rows[0].source_record_id, "http://dati.senato.it/sedutaassemblea/23908")
        self.assertIn("osr:numeroSeduta", dict(imported.imported.provenance[0].fields)["value_numeric"])
        self.assertNotIn("transcript", str(imported).lower())
        self.assertNotIn("approved", str(imported).lower())
        same = import_senato_open_data_sittings(blob, observed_at_utc="2026-10-10T10:30:00Z")
        self.assertEqual(imported.imported.replay_id, same.imported.replay_id)

    def test_fail_closed_for_missing_number_wrong_legislature_or_unknown_predicate(self):
        mutations = (
            SOURCE_ROWS.replace("<osr:numeroSeduta rdf:datatype=", "<osr:other rdf:datatype=", 1),
            SOURCE_ROWS.replace(">19</osr:legislatura>", ">20</osr:legislatura>", 1),
            SOURCE_ROWS.replace("</osr:numeroSeduta>", "</osr:numeroSeduta><osr:unknown>1</osr:unknown>", 1),
            SOURCE_ROWS.replace("2022-10-13", "2022-02-30", 1),
            SOURCE_ROWS.replace('http://dati.senato.it/sedutaassemblea/23909', 'http://dati.senato.it/sedutaassemblea/23908'),
        )
        for xml in mutations:
            with self.subTest(xml=xml[:30]), self.assertRaises(SenatoOpenDataError):
                import_senato_open_data_sittings(archive(xml), observed_at_utc="2026-10-10T10:30:00Z")

    def test_rejects_wrong_archive_malicious_xml_or_invalid_observation(self):
        for blob in (b"not zip", archive(name="../../other.xml"), archive('<!DOCTYPE foo [<!ENTITY x "b">]>' + SOURCE_ROWS)):
            with self.assertRaises(SenatoOpenDataError):
                import_senato_open_data_sittings(blob, observed_at_utc="2026-10-10T10:30:00Z")
        for observed in ("2026-10-10", "2026-02-30T00:00:00Z", "2026-10-10T10:30:00+02:00"):
            with self.assertRaises(SenatoOpenDataError):
                import_senato_open_data_sittings(archive(), observed_at_utc=observed)

    def test_real_dp215_senato_profile_cannot_launder_unapproved_dataset_rights(self):
        contract = load_source_intelligence_contract()
        profile = contract.evidence_profiles_by_registry_id["senato-linked-data"]
        scope = profile.authority_scopes[0]
        imported = import_senato_open_data_sittings(
            archive(), observed_at_utc="2026-10-10T10:30:00Z"
        )
        result = derive_dvns_candidate_suitability(
            imported.imported,
            target_id="claim-candidate:senato-seduta-offline-test",
            statement_date="2022-10-20",
            claim_requirements={"metric": "senato_assemblea_numero_seduta"},
            source_profile=profile,
            evidence_role="OFFICIAL_PROCEDURAL_RECORD",
            authority_scope=scope,
        )
        self.assertEqual(result.candidate_state, HELD)
        self.assertIn("DVNS_RIGHTS_BLOCKED", result.blocking_reasons)
        self.assertTrue(all(row.candidate_state == HELD for row in result.records))


if __name__ == "__main__":
    unittest.main()
