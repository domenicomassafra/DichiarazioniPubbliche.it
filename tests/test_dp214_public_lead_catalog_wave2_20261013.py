"""DP-214 second wave: bounded official metadata without rights, capture or ingest."""

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.garlasco_tracer import _safe_url  # noqa: E402
from dichiarazioni_pubbliche.research_pilot_readiness import load_unreviewed_public_leads  # noqa: E402
from tests.test_dp214_public_lead_catalog_20261013 import url_identity  # noqa: E402

CATALOG = ROOT / "config/garlasco-public-discovery-leads.v1.json"
WAVE26 = ROOT / "config/garlasco-source-governance-wave26.v1.json"
WAVE2_KEY = "metadata_only_official_probes_wave2"
EXPECTED = {
    "lead:garlasco:cassazione-26919-2024-defamation": (
        "https://www.cortedicassazione.it/it/penale_dettaglio.page?contentId=SZP32834",
        "2024-07-08", "JUDICIAL_DECISION_RELATED_DEFAMATION_NOT_HOMICIDE", "text/html",
        "cassazione:penale:26919-2024",
    ),
    "lead:garlasco:garanteprivacy-10149350-2025": (
        "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10149350",
        "2025-07-11", "DATA_PROTECTION_AUTHORITY_DECISION_NOT_COURT_JUDGMENT", "text/html",
        "garanteprivacy:docweb:10149350",
    ),
    "lead:garlasco:garanteprivacy-10273026-2026": (
        "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10273026",
        "2026-07-03", "DATA_PROTECTION_AUTHORITY_DECISION_NOT_COURT_JUDGMENT", "text/html",
        "garanteprivacy:docweb:10273026",
    ),
    "lead:garlasco:ministero-giustizia-bonetti-4-05562-2025": (
        "https://www.giustizia.it/cmsresources/cms/documents/interrogazione_bonetti_risposta_25ago2025.pdf",
        "2025-08-25", "FIRST_PARTY_MINISTERIAL_PARLIAMENTARY_REPLY_NOT_JUDGMENT", "application/pdf",
        "giustizia:written-reply:camera19:4-05562:2025-08-25",
    ),
}
# These per-document bindings were checked against the exact PR #12 registry.
# Same-host evidence is NOT enough: a real Ministry index is not evidence for a
# Cassation judgment, and a privacy ruling is not proof of homicide findings.
# Keep the source-specific authority limits in titles AND locator descriptions.
VERIFIED_SOURCE_METADATA = {'lead:garlasco:cassazione-26919-2024-defamation': {'document_title': 'Corte di cassazione, Quinta '
                                                                      'sezione penale, sentenza n. '
                                                                      '26919/2024',
                                                    'publisher': 'Corte Suprema di Cassazione',
                                                    'official_metadata_evidence_url': 'https://www.cortedicassazione.it/it/penale_dettaglio.page?contentId=SZP32834',
                                                    'record_locator': 'Giurisprudenza penale, '
                                                                      'scheda SZP32834; sentenza '
                                                                      '26919, deposito 8 luglio '
                                                                      '2024, udienza 15 marzo '
                                                                      '2024. Procedimento per '
                                                                      'diffamazione legato a '
                                                                      'servizio televisivo sul '
                                                                      'caso Garlasco; NON sentenza '
                                                                      'sul delitto di Chiara '
                                                                      'Poggi. Allegato PDF '
                                                                      'indicizzato ma endpoint PDF '
                                                                      'restituisce 404 alla '
                                                                      'verifica HEAD Mac: '
                                                                      'conservare scheda HTML come '
                                                                      'locator valido.',
                                                    'verification_scope': 'Official court indexed '
                                                                          'title, sentence number, '
                                                                          'hearing/deposit dates, '
                                                                          'and direct HTML HEAD '
                                                                          '200 only; no court PDF '
                                                                          'body acquired or '
                                                                          'licensed',
                                                    'identity_review_status': 'UNREVIEWED_SOURCE_USE_AND_SUBJECT_SCOPE',
                                                    'document_date_basis': 'OFFICIAL_INSTITUTIONAL_INDEX',
                                                    'discovery_type': 'OFFICIAL_CASSATION_DECISION_INDEX'},
 'lead:garlasco:garanteprivacy-10149350-2025': {'document_title': 'Garante per la protezione dei '
                                                                  'dati personali, provvedimento '
                                                                  "dell'11 luglio 2025, doc. web "
                                                                  '10149350',
                                                'publisher': 'Garante per la protezione dei dati '
                                                             'personali',
                                                'official_metadata_evidence_url': 'https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10149350',
                                                'record_locator': 'Docweb 10149350: decisione del '
                                                                  'Garante su diffusione illecita '
                                                                  "di immagini dell'esame "
                                                                  'autoptico di Chiara Poggi. '
                                                                  'Decisione di tutela dati, non '
                                                                  'giudizio su responsabilita '
                                                                  "penale nell'omicidio.",
                                                'verification_scope': 'Published first-party '
                                                                      'privacy decision '
                                                                      'heading/date/docweb and '
                                                                      'direct HTTPS HEAD 200; no '
                                                                      'personal images or document '
                                                                      'bodies copied',
                                                'identity_review_status': 'UNREVIEWED_SOURCE_USE_AND_SUBJECT_SCOPE',
                                                'document_date_basis': 'OFFICIAL_INSTITUTIONAL_INDEX',
                                                'discovery_type': 'FIRST_PARTY_PRIVACY_AUTHORITY_DECISION'},
 'lead:garlasco:garanteprivacy-10273026-2026': {'document_title': 'Garante per la protezione dei '
                                                                  'dati personali, provvedimento '
                                                                  'del 3 luglio 2026, doc. web '
                                                                  '10273026',
                                                'publisher': 'Garante per la protezione dei dati '
                                                             'personali',
                                                'official_metadata_evidence_url': 'https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10273026',
                                                'record_locator': 'Docweb 10273026: distinto '
                                                                  'provvedimento del Garante '
                                                                  'relativo alla divulgazione di '
                                                                  "immagini collegate all'omicidio "
                                                                  'di Chiara Poggi, con reclamanti '
                                                                  'familiari; non giudizio penale '
                                                                  "sull'omicidio.",
                                                'verification_scope': 'Published first-party '
                                                                      'privacy decision '
                                                                      'heading/date/docweb and '
                                                                      'direct HTTPS HEAD 200; no '
                                                                      'personal images or document '
                                                                      'bodies copied',
                                                'identity_review_status': 'UNREVIEWED_SOURCE_USE_AND_SUBJECT_SCOPE',
                                                'document_date_basis': 'OFFICIAL_INSTITUTIONAL_INDEX',
                                                'discovery_type': 'FIRST_PARTY_PRIVACY_AUTHORITY_DECISION',
                                                'related_document_identity_key': 'garanteprivacy:docweb:10149350',
                                                'relation': 'SAME_GARLASCO_PRIVACY_TOPIC_DISTINCT_PROCEEDING_NOT_HOMICIDE_EVIDENCE'},
 'lead:garlasco:ministero-giustizia-bonetti-4-05562-2025': {'document_title': 'Ministero della '
                                                                              'Giustizia, risposta '
                                                                              'scritta '
                                                                              "all'interrogazione "
                                                                              '4-05562 Bonetti',
                                                            'publisher': 'Ministero della '
                                                                         'Giustizia',
                                                            'official_metadata_evidence_url': 'https://www.giustizia.it/giustizia/en/contentview.page?contentId=ART1487250',
                                                            'record_locator': 'Risposta scritta '
                                                                              'ministeriale '
                                                                              "all'interrogazione "
                                                                              'n. 4-05562 '
                                                                              '(Bonetti), '
                                                                              'catalogata 25 '
                                                                              'agosto 2025 '
                                                                              "nell'indice "
                                                                              'ministeriale delle '
                                                                              'risposte 2025; '
                                                                              'domanda sui '
                                                                              'controlli relativi '
                                                                              'alla divulgazione '
                                                                              'di immagini '
                                                                              "dell'esame "
                                                                              'autoptico di Chiara '
                                                                              'Poggi. La risposta '
                                                                              "e' un atto "
                                                                              'ministeriale, non '
                                                                              'un provvedimento '
                                                                              'giudiziario.',
                                                            'verification_scope': 'Ministerial '
                                                                                  'index entry '
                                                                                  '4-05562 Bonetti '
                                                                                  '/ 25 August '
                                                                                  '2025 and direct '
                                                                                  'PDF HEAD 200, '
                                                                                  'application/pdf; '
                                                                                  'no document '
                                                                                  'body downloaded',
                                                            'identity_review_status': 'UNREVIEWED_SOURCE_USE_AND_SUBJECT_SCOPE',
                                                            'document_date_basis': 'OFFICIAL_INSTITUTIONAL_INDEX',
                                                            'discovery_type': 'FIRST_PARTY_MINISTRY_PARLIAMENTARY_REPLY'}}

FORBIDDEN_KEYS = {
    "body", "text", "full_text", "transcript", "extracted_text", "pdf_bytes",
    "body_sha256", "capture_id", "passage_id", "content_id", "discovery_ref",
    "publisher_approved", "speaker_approved", "publication_authorized", "PUBLISH",
}
ALLOWED_KEYS = {
    "id", "url", "document_identity_key", "document_title", "document_date",
    "document_date_basis", "publisher", "document_kind", "record_locator",
    "proposed_family", "discovery_type", "status", "identity_review_status",
    "checked_on", "http_head_status", "http_reachability", "http_content_type",
    "official_metadata_evidence_url", "verification_scope", "related_document_identity_key",
    "relation", "rights_status", "provenance_status", "candidate_only",
    "capture_authorized", "capture_performed", "count_as_logical_item",
}


def _lineage_url_set(wave26):
    """Compare actual upstream locators; multiple refs to one URL are one identity."""
    urls = set()
    for row in wave26["source_reviews"]:
        for key in ("original_url", "identity_evidence_url", "rights_evidence_url"):
            value = row.get(key)
            if isinstance(value, str) and value.startswith("https://"):
                urls.add(url_identity(value))
    for row in wave26["parliamentary_probes"]:
        for key in ("transcript_url", "video_index_url"):
            value = row.get(key)
            if isinstance(value, str) and value.startswith("https://"):
                urls.add(url_identity(value))
    return urls


def validate_wave2(catalog, wave26):
    if catalog["version"] != "garlasco-public-discovery-leads-v1" or catalog["state"] != "UNREVIEWED_CANDIDATES_ONLY":
        raise ValueError("CATALOG_STATE_CHANGED")
    rows = catalog[WAVE2_KEY]
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("WAVE2_BOUNDS_MISMATCH")
    if set(row["id"] for row in rows) != set(EXPECTED):
        raise ValueError("UNVERIFIED_WAVE2_ITEM")
    prior = catalog["candidates"] + catalog["source_locator_only"] + catalog["metadata_only_official_probes"]
    if len(prior) != 11:
        raise ValueError("ORIGINAL_LEADS_CHANGED")
    ids = [row["id"] for row in prior + rows]
    urls = [url_identity(row["url"]) for row in prior + rows]
    if len(ids) != len(set(ids)) or len(urls) != len(set(urls)):
        raise ValueError("DUPLICATE_SOURCE_ID_OR_URL")
    if set(urls[-4:]) & _lineage_url_set(wave26):
        raise ValueError("DUPLICATE_OF_WAVE26")
    document_keys = [row["document_identity_key"] for row in catalog["metadata_only_official_probes"] + rows]
    if len(set(document_keys)) != len(document_keys):
        raise ValueError("DUPLICATE_DOCUMENT_IDENTITY")
    for row in rows:
        expected_url, date, kind, mime, identity = EXPECTED[row["id"]]
        if row["url"] != expected_url or not _safe_url(row["url"]):
            raise ValueError("UNVERIFIED_WAVE2_URL")
        if set(row) - ALLOWED_KEYS or set(row) & FORBIDDEN_KEYS:
            raise ValueError("FORBIDDEN_SOURCE_CONTENT_OR_AUTHORITY")
        if row["document_date"] != date or row["document_identity_key"] != identity or row["document_kind"] != kind:
            raise ValueError("UNVERIFIED_WAVE2_IDENTITY")
        if not row.get("document_title") or not row.get("record_locator") or not row.get("publisher"):
            raise ValueError("MISSING_OFFICIAL_METADATA")
        # Bind all authority-bearing labels and their issuer evidence to the
        # exact record identity, not merely a valid government HTTPS hostname.
        verified = VERIFIED_SOURCE_METADATA[row["id"]]
        for field in ("document_title", "publisher", "official_metadata_evidence_url",
                      "record_locator", "verification_scope", "identity_review_status",
                      "document_date_basis", "discovery_type"):
            if row.get(field) != verified[field]:
                raise ValueError(f"SOURCE_METADATA_IDENTITY_MISMATCH:{field}")
        if row["document_date_basis"] not in {"OFFICIAL_INSTITUTIONAL_INDEX", "OFFICIAL_DOCUMENT_NUMBER_AND_DATE"}:
            raise ValueError("DATE_AUTHORITY_MISSING")
        if row["proposed_family"] != "OFFICIAL_PROCEDURAL" or row["status"] != "UNREVIEWED" or row["rights_status"] != "UNKNOWN":
            raise ValueError("RIGHTS_OR_SOURCE_STATE_ESCALATED")
        if row["provenance_status"] != "UNVERIFIED_IN_DATABASE":
            raise ValueError("PERSISTED_PROVENANCE_FABRICATED")
        for key, expected_flag in (("candidate_only", True), ("capture_authorized", False),
                                   ("capture_performed", False), ("count_as_logical_item", False)):
            if row.get(key) is not expected_flag:
                raise ValueError("UNAUTHORIZED_INGEST_OR_CAPTURE")
        if row["http_head_status"] != 200 or row["http_reachability"] != "HEAD_200" or row["checked_on"] != "2026-10-13":
            raise ValueError("HTTP_OBSERVATION_UNVERIFIED")
        if not row["http_content_type"].startswith(mime):
            raise ValueError("MIME_TYPE_MISREPRESENTED")
        evidence_url = row["official_metadata_evidence_url"]
        if not _safe_url(evidence_url):
            raise ValueError("INVALID_INSTITUTIONAL_EVIDENCE")
        if urlsplit(evidence_url).hostname not in {
            "www.cortedicassazione.it", "www.garanteprivacy.it", "www.giustizia.it",
        }:
            raise ValueError("NON_INSTITUTIONAL_EVIDENCE")
        if row.get("related_document_identity_key"):
            if row["related_document_identity_key"] not in {r["document_identity_key"] for r in rows if r is not row}:
                raise ValueError("INVENTED_RELATED_DOCUMENT")
            if row.get("relation") != "SAME_GARLASCO_PRIVACY_TOPIC_DISTINCT_PROCEEDING_NOT_HOMICIDE_EVIDENCE":
                raise ValueError("RELATED_DECISION_OVERCLAIM")
        for field in ("related_document_identity_key", "relation"):
            if row.get(field) != verified.get(field):
                raise ValueError(f"SOURCE_METADATA_IDENTITY_MISMATCH:{field}")
    serialized = json.dumps(sorted((r["id"], r["url"], r["document_identity_key"]) for r in rows),
                            separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()


class DP214PublicLeadsWave2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.wave26 = json.loads(WAVE26.read_text(encoding="utf-8"))

    def test_four_new_official_records_replay_and_not_accepted(self):
        self.assertEqual(validate_wave2(self.catalog, self.wave26),
                         validate_wave2(copy.deepcopy(self.catalog), self.wave26))
        unchanged = load_unreviewed_public_leads(CATALOG)
        self.assertEqual((unchanged["unreviewed_file_candidates"], unchanged["source_locator_only"],
                          unchanged["file_leads_counted_in_pilot"]), (6, 1, 0))

    def test_reject_duplicate_url_or_prior_wave26_alias(self):
        changed = copy.deepcopy(self.catalog)
        changed[WAVE2_KEY][1]["url"] = changed[WAVE2_KEY][0]["url"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SOURCE_ID_OR_URL"):
            validate_wave2(changed, self.wave26)
        changed = copy.deepcopy(self.catalog)
        changed[WAVE2_KEY][0]["url"] = self.wave26["parliamentary_probes"][0]["transcript_url"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SOURCE_ID_OR_URL|DUPLICATE_OF_WAVE26"):
            validate_wave2(changed, self.wave26)

    def test_no_rights_capture_body_publication_or_fabricated_relation(self):
        for key, value in (("rights_status", "CLEARED"), ("capture_authorized", True),
                           ("capture_performed", True), ("count_as_logical_item", True),
                           ("body", "copied judicial body"), ("discovery_ref", "invented"),
                           ("http_head_status", 404), ("document_date", "2024-07-07")):
            with self.subTest(field=key):
                changed = copy.deepcopy(self.catalog)
                changed[WAVE2_KEY][0][key] = value
                with self.assertRaises(ValueError):
                    validate_wave2(changed, self.wave26)
        changed = copy.deepcopy(self.catalog)
        changed[WAVE2_KEY][2]["related_document_identity_key"] = "invented:judgment"
        with self.assertRaisesRegex(ValueError, "INVENTED_RELATED_DOCUMENT"):
            validate_wave2(changed, self.wave26)



    def test_every_title_issuer_evidence_and_locator_is_bound_to_its_document(self):
        # Swapping in another REAL official page must not establish provenance
        # for the original lead. This used to pass when the host was on-list.
        rows = self.catalog[WAVE2_KEY]
        for i, row in enumerate(rows):
            for field in ("document_title", "publisher",
                          "official_metadata_evidence_url", "record_locator"):
                # Two Garante records legitimately share one issuer label.
                # Pick a DIFFERENT legitimate institutional value for each swap.
                unrelated = next(other[field] for other in rows
                                 if other["id"] != row["id"] and other[field] != row[field])
                with self.subTest(id=row["id"], field=field):
                    changed = copy.deepcopy(self.catalog)
                    changed[WAVE2_KEY][i][field] = unrelated
                    with self.assertRaisesRegex(
                        ValueError, "SOURCE_METADATA_IDENTITY_MISMATCH"
                    ):
                        validate_wave2(changed, self.wave26)

    def test_cassation_homicide_fiction_and_real_unrelated_ministry_index_fail(self):
        for field, value in (
            ("document_title", "Cassazione sentenza definitiva su omicidio"),
            ("record_locator", "Cassazione ha definitivamente deciso chi ha ucciso Chiara Poggi"),
            ("publisher", "Ministero della Giustizia"),
            ("official_metadata_evidence_url",
             "https://www.giustizia.it/giustizia/en/contentview.page?contentId=ART1487250"),
            ("verification_scope", "Court judgment establishes murder guilt"),
            ("identity_review_status", "APPROVED"),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.catalog)
                changed[WAVE2_KEY][0][field] = value
                with self.assertRaisesRegex(
                    ValueError, f"SOURCE_METADATA_IDENTITY_MISMATCH:{field}"
                ):
                    validate_wave2(changed, self.wave26)

    def test_unreviewed_privacy_documents_cannot_gain_fabricated_lineage(self):
        changed = copy.deepcopy(self.catalog)
        # The linked Garante record is distinct, and cannot silently become
        # unrelated or be presented as a judiciary verdict.
        changed[WAVE2_KEY][2].pop("related_document_identity_key")
        changed[WAVE2_KEY][2].pop("relation")
        with self.assertRaisesRegex(ValueError, "SOURCE_METADATA_IDENTITY_MISMATCH"):
            validate_wave2(changed, self.wave26)
        changed = copy.deepcopy(self.catalog)
        changed[WAVE2_KEY][0]["related_document_identity_key"] = (
            changed[WAVE2_KEY][1]["document_identity_key"]
        )
        changed[WAVE2_KEY][0]["relation"] = (
            "SAME_GARLASCO_PRIVACY_TOPIC_DISTINCT_PROCEEDING_NOT_HOMICIDE_EVIDENCE"
        )
        with self.assertRaisesRegex(ValueError, "SOURCE_METADATA_IDENTITY_MISMATCH"):
            validate_wave2(changed, self.wave26)


if __name__ == "__main__":
    unittest.main()
