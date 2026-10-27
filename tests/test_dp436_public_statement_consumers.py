"""DP-436 pure opt-in v3 consumers; no new public HTTP route or publication."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.linked_data import (  # noqa: E402
    DP,
    RDF,
    SCHEMA,
    projection_ntriples,
    projection_statement_v3_jsonld,
    projection_statement_v3_ntriples,
    public_resource_uri,
)
from dichiarazioni_pubbliche.public_api import (  # noqa: E402
    ROUTES,
    PublicApiError,
    build_index,
    get_public_statement_v3,
    list_public_statements_v3,
    load_index,
)
from dichiarazioni_pubbliche.public_projection import build_public_projection  # noqa: E402
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    PUBLIC_SCHEMA_VERSION,
    PUBLIC_STATEMENT_SCHEMA_VERSION,
    PublicSchemaValidationError,
    projection_dataset_sha256,
    validate_public_bundle,
)
from test_dp435_public_statement_seam import (  # noqa: E402
    IsolatedStatementSource, QUOTE, SHA, SOURCE, STAMP, START,
)
from test_public_projection import FakeSource, valid_row  # noqa: E402


def v3_bundle(source: IsolatedStatementSource | None = None) -> dict:
    return build_public_projection(
        source or IsolatedStatementSource(),
        generated_at=STAMP,
        include_public_statements=True,
    )


def v2_bundle() -> dict:
    return build_public_projection(FakeSource([]), generated_at=STAMP)


def with_derived() -> dict:
    source = IsolatedStatementSource()
    source.row["summary"] = {"text": "Il costo dichiarato è dieci euro."}
    source.row["translation"] = {
        "text": "It costs ten euros, not twenty.",
        "language": "en",
        "source_language": "it",
    }
    for kind in ("summary", "translation"):
        source.gates[kind] = {
            "status": "APPROVED",
            "review_event_id": f"review:{kind}",
            "source_quote_sha256": SHA(QUOTE),
            "text_sha256": SHA(source.row[kind]["text"]),
        }
    return v3_bundle(source)


class PublicStatementV3ConsumerTests(unittest.TestCase):
    def setUp(self):
        # Synthetic distinct models exercise v3 export semantics in isolation.
        # The production subscription authorization remains unchanged.
        models = patch(
            "dichiarazioni_pubbliche.autonomous_publication.APPROVED_REVIEW_MODELS",
            frozenset({"model:1", "model:2"}),
        )
        models.start()
        self.addCleanup(models.stop)

    def test_api_requires_independent_current_release_after_withdrawal(self):
        bundle = v3_bundle()
        for reader in (
            lambda **kwargs: list_public_statements_v3(bundle, **kwargs),
            lambda **kwargs: get_public_statement_v3(bundle, "statement:1", **kwargs),
        ):
            with self.subTest(reader=reader):
                # The bundle's self-asserted SHA is not a live release authority.
                with self.assertRaises(PublicApiError) as missing:
                    reader(allow_statement_v3=True)
                self.assertEqual(missing.exception.status, 503)
                with self.assertRaises(PublicApiError) as withdrawn:
                    reader(
                        allow_statement_v3=True,
                        current_public_dataset_sha256="f" * 64,
                    )
                self.assertEqual(withdrawn.exception.status, 503)
                current = reader(
                    allow_statement_v3=True,
                    current_public_dataset_sha256=bundle["dataset_sha256"],
                )
                self.assertEqual(current["meta"]["dataset_sha256"], bundle["dataset_sha256"])

    def test_opt_in_required_and_v2_contract_not_reinterpreted(self):
        bundle = v3_bundle()
        with self.assertRaises(PublicApiError) as error:
            list_public_statements_v3(bundle)
        self.assertEqual(error.exception.status, 503)
        with self.assertRaises(PublicApiError):
            get_public_statement_v3(bundle, "statement:1")
        for serializer in (projection_statement_v3_ntriples, projection_statement_v3_jsonld):
            with self.assertRaises(PublicSchemaValidationError):
                serializer(bundle)
        with self.assertRaises(PublicApiError):
            list_public_statements_v3(v2_bundle(), allow_statement_v3=True)
        with self.assertRaises(PublicSchemaValidationError):
            projection_statement_v3_ntriples(v2_bundle(), allow_statement_v3=True)
        self.assertEqual(v2_bundle()["schema_version"], PUBLIC_SCHEMA_VERSION)
        self.assertIn("schema.org/Dataset", projection_ntriples(v2_bundle()))

    def test_v3_read_payload_preserves_exact_quote_and_provenance(self):
        bundle = v3_bundle()
        collection = list_public_statements_v3(bundle, allow_statement_v3=True,
            current_public_dataset_sha256=bundle["dataset_sha256"])
        detail = get_public_statement_v3(bundle, "statement:1", allow_statement_v3=True,
            current_public_dataset_sha256=bundle["dataset_sha256"])
        self.assertEqual(collection["data"], [detail["data"]])
        self.assertEqual(collection["meta"]["dataset_sha256"], bundle["dataset_sha256"])
        self.assertEqual(detail["meta"]["public_schema_version"], PUBLIC_STATEMENT_SCHEMA_VERSION)
        record = detail["data"]
        self.assertEqual(record["original"]["text"], QUOTE)
        self.assertEqual(record["original"]["quote_sha256"], SHA(QUOTE))
        self.assertEqual(record["original"]["wording_type"], "VERBATIM_ORIGINAL")
        self.assertEqual(record["source"]["sha256"], SHA(SOURCE))
        self.assertEqual(record["source"]["version_id"], "source-version:1")
        self.assertEqual(record["version_id"], "statement-version:1")
        self.assertEqual(record["person"]["id"], "person:1")
        self.assertIsNone(record["finding_id"])
        self.assertIsNone(record["summary"])
        self.assertIsNone(record["translation"])
        rendered = json.dumps(detail, ensure_ascii=False)
        self.assertNotIn(SOURCE, rendered)
        for hidden in ("review_provenance", "publication_review_ids", "raw_transcript", "normalized_claim"):
            self.assertNotIn(hidden, rendered)

    def test_v3_linked_data_and_jsonld_original_only_quote(self):
        bundle = with_derived()
        detail = get_public_statement_v3(bundle, "statement:1", allow_statement_v3=True,
            current_public_dataset_sha256=bundle["dataset_sha256"])
        serialized = projection_statement_v3_ntriples(bundle, allow_statement_v3=True)
        jsonld = projection_statement_v3_jsonld(bundle, allow_statement_v3=True)
        statement = jsonld["@graph"][1]
        statement_uri = public_resource_uri("statement", "statement:1")
        self.assertEqual(statement["@id"], statement_uri)
        self.assertEqual(statement["@type"], "Quotation")
        self.assertEqual(statement["text"], detail["data"]["original"]["text"])
        self.assertEqual(statement["dp:locator"], detail["data"]["original"]["locator"])
        self.assertEqual(statement["dp:sourceSha256"], detail["data"]["source"]["sha256"])
        self.assertEqual(statement["dp:quoteSha256"], detail["data"]["original"]["quote_sha256"])
        self.assertEqual(jsonld["@graph"][0]["dp:projectionFingerprint"], bundle["dataset_sha256"])
        self.assertEqual(len(statement["hasPart"]), 2)
        self.assertEqual(
            {part["dp:wordingType"] for part in statement["hasPart"]},
            {"SUMMARY", "TRANSLATION"},
        )
        self.assertTrue(all(part["@type"] == "CreativeWork" for part in statement["hasPart"]))
        self.assertTrue(all(part["isBasedOn"]["@id"] == statement_uri for part in statement["hasPart"]))
        self.assertNotIn(QUOTE, [part["text"] for part in statement["hasPart"]])
        self.assertIn(f"<{SCHEMA}Quotation>", serialized)
        self.assertIn(f"<{DP}wordingType> \"VERBATIM_ORIGINAL\"", serialized)
        self.assertIn(f"<{DP}wordingType> \"SUMMARY\"", serialized)
        self.assertIn(f"<{DP}wordingType> \"TRANSLATION\"", serialized)
        self.assertEqual(serialized, projection_statement_v3_ntriples(bundle, allow_statement_v3=True))
        for kind in ("summary", "translation"):
            self.assertEqual(detail["data"][kind]["wording_type"], kind.upper())
            self.assertNotEqual(detail["data"][kind]["text"], detail["data"]["original"]["text"])
        self.assertEqual(statement["hasPart"][1]["inLanguage"], "en")

    def test_legacy_finding_paraphrase_never_becomes_v3_quotation(self):
        source = IsolatedStatementSource()
        row = valid_row()
        source.projectable_findings = lambda: [row]
        bundle = v3_bundle(source)
        self.assertEqual(len(bundle["dossiers"]), 1)
        legacy_claim = bundle["dossiers"][0]["claim"]
        self.assertNotEqual(legacy_claim, QUOTE)
        api_json = json.dumps(
            list_public_statements_v3(bundle, allow_statement_v3=True,
                current_public_dataset_sha256=bundle["dataset_sha256"]), ensure_ascii=False
        )
        rdf = projection_statement_v3_ntriples(bundle, allow_statement_v3=True)
        jsonld = json.dumps(projection_statement_v3_jsonld(bundle, allow_statement_v3=True))
        for serialization in (api_json, rdf, jsonld):
            self.assertNotIn(legacy_claim, serialization)
            self.assertIn("statement", serialization)
        self.assertEqual(len(projection_statement_v3_jsonld(bundle, allow_statement_v3=True)["@graph"]), 2)

    def test_reported_quote_not_endorsed_or_misattributed_in_linked_data(self):
        source = IsolatedStatementSource()
        source.gates["context"]["speech_act"] = "REPORTED_QUOTE"
        source.gates["context"]["endorsed"] = False
        bundle = v3_bundle(source)
        document = projection_statement_v3_jsonld(bundle, allow_statement_v3=True)["@graph"][1]
        self.assertEqual(document["dp:speechAct"], "REPORTED_QUOTE")
        self.assertFalse(document["dp:endorsed"])
        self.assertNotIn("author", document)
        self.assertEqual(document["dp:recordedSpeaker"]["@id"], public_resource_uri("person", "person:1"))
        rdf = projection_statement_v3_ntriples(bundle, allow_statement_v3=True)
        self.assertNotIn(f"<{SCHEMA}author>", rdf)
        self.assertIn(f"<{DP}recordedSpeaker>", rdf)

    def test_optional_published_finding_has_distinct_reference_not_quote_body(self):
        source = IsolatedStatementSource()
        source.projectable_findings = lambda: [valid_row()]
        source.row["person_id"] = "person:a"
        source.row["content_id"] = "content:a"
        source.row["finding_id"] = "finding:a"
        source.get_statement_source_text = lambda content_id, version: (
            source.source_text if (content_id, version) == ("content:a", "source-version:1") else None
        )
        for proof in source.gates.values():
            proof["person_id"] = "person:a"
            proof["content_id"] = "content:a"
        bundle = v3_bundle(source)
        self.assertEqual(bundle["dossier_count"], 1)
        self.assertEqual(len(bundle["statements"]), 1)
        record = get_public_statement_v3(bundle, "statement:1", allow_statement_v3=True,
            current_public_dataset_sha256=bundle["dataset_sha256"])["data"]
        self.assertEqual(record["finding_id"], "finding:a")
        self.assertEqual(record["original"]["text"], QUOTE)
        jsonld = projection_statement_v3_jsonld(bundle, allow_statement_v3=True)["@graph"][1]
        finding_uri = public_resource_uri("finding", "finding:a")
        self.assertEqual(jsonld["subjectOf"]["@id"], finding_uri)
        rdf = projection_statement_v3_ntriples(bundle, allow_statement_v3=True)
        self.assertIn(f"<{SCHEMA}subjectOf> <{finding_uri}>", rdf)
        self.assertNotIn(bundle["dossiers"][0]["claim"], rdf)

    def test_timed_locator_and_source_version_roundtrip(self):
        bundle = v3_bundle(IsolatedStatementSource(source_kind="TIMED"))
        record = get_public_statement_v3(bundle, "statement:1", allow_statement_v3=True,
            current_public_dataset_sha256=bundle["dataset_sha256"])["data"]
        self.assertEqual(
            record["original"]["locator"],
            {"start_char": START, "end_char": START + len(QUOTE), "segment_id": "segment:1", "start_ms": 2000, "end_ms": 4000},
        )
        rdf = projection_statement_v3_ntriples(bundle, allow_statement_v3=True)
        self.assertIn(f"<{DP}startMs> \"2000\"", rdf)
        self.assertIn(f"<{DP}segmentId> \"segment:1\"", rdf)

    def test_missing_rights_revoked_or_changed_source_omit_from_fresh_snapshot(self):
        for gate, value in (("rights", "REVOKED"), ("rights", "UNKNOWN"), ("publication", "HELD")):
            with self.subTest(gate=gate, value=value):
                source = IsolatedStatementSource()
                source.gates[gate]["status"] = value
                bundle = v3_bundle(source)
                self.assertEqual(
                    list_public_statements_v3(bundle, allow_statement_v3=True,
                        current_public_dataset_sha256=bundle["dataset_sha256"])["data"], []
                )
                self.assertNotIn("statement:1", projection_statement_v3_ntriples(
                    bundle, allow_statement_v3=True
                ))
                with self.assertRaises(PublicApiError) as exc:
                    get_public_statement_v3(bundle, "statement:1", allow_statement_v3=True,
                        current_public_dataset_sha256=bundle["dataset_sha256"])
                self.assertEqual(exc.exception.status, 404)
        source = IsolatedStatementSource()
        source.source_text += " Addendum"
        self.assertEqual(v3_bundle(source)["statements"], [])

    def test_invalid_or_tampered_v3_never_serialized(self):
        pristine = v3_bundle()
        cases = {
            "changed quote": ("statements", "original_text", "FALSE"),
            "missing right": ("statements", "review_provenance", None),
            "private raw body": ("statements", "raw_transcript", "PRIVATE EVIDENCE"),
            "wrong dataset fingerprint": ("bundle", "dataset_sha256", "0" * 64),
        }
        for name, (area, field, value) in cases.items():
            with self.subTest(name=name):
                bundle = copy.deepcopy(pristine)
                if area == "bundle":
                    bundle[field] = value
                elif field == "review_provenance":
                    bundle["statements"][0][field].pop("rights")
                else:
                    bundle["statements"][0][field] = value
                if area != "bundle":
                    bundle["dataset_sha256"] = projection_dataset_sha256(bundle)
                for serialize in (
                    lambda b: list_public_statements_v3(b, allow_statement_v3=True,
                        current_public_dataset_sha256=b["dataset_sha256"]),
                    lambda b: projection_statement_v3_ntriples(b, allow_statement_v3=True),
                    lambda b: projection_statement_v3_jsonld(b, allow_statement_v3=True),
                ):
                    with self.assertRaises((PublicApiError, PublicSchemaValidationError)):
                        serialize(bundle)

    def test_unsafe_https_url_cannot_inject_into_jsonld_or_ntriples(self):
        bundle = v3_bundle()
        bundle["statements"][0]["source_url"] = "https://example.test/path>\n<https://evil.test"
        bundle["dataset_sha256"] = projection_dataset_sha256(bundle)
        for serialize in (
            lambda b: list_public_statements_v3(b, allow_statement_v3=True,
                current_public_dataset_sha256=b["dataset_sha256"]),
            lambda b: projection_statement_v3_ntriples(b, allow_statement_v3=True),
            lambda b: projection_statement_v3_jsonld(b, allow_statement_v3=True),
        ):
            with self.assertRaises((PublicApiError, PublicSchemaValidationError)):
                serialize(bundle)

    def test_special_original_characters_keep_exact_json_and_escaped_rdf_literal(self):
        source = IsolatedStatementSource()
        quoted = 'La cifra è "10"\tunità.'
        source.source_text = "Contesto: " + quoted + " Poi segue altro."
        offset = source.source_text.index(quoted)
        source.row["original_text"] = quoted
        source.row["source_sha256"] = SHA(source.source_text)
        source.row["locator"] = {"start_char": offset, "end_char": offset + len(quoted)}
        for proof in source.gates.values():
            proof["source_sha256"] = SHA(source.source_text)
            proof["quote_sha256"] = SHA(quoted)
            proof["span_start"] = offset
            proof["span_end"] = offset + len(quoted)
        bundle = v3_bundle(source)
        self.assertEqual(len(bundle["statements"]), 1)
        self.assertEqual(
            get_public_statement_v3(bundle, "statement:1", allow_statement_v3=True,
                current_public_dataset_sha256=bundle["dataset_sha256"])["data"]["original"]["text"],
            quoted,
        )
        self.assertEqual(
            projection_statement_v3_jsonld(bundle, allow_statement_v3=True)["@graph"][1]["text"],
            quoted,
        )
        rdf = projection_statement_v3_ntriples(bundle, allow_statement_v3=True)
        self.assertNotIn("\t", rdf)
        self.assertIn('\\\"10\\\"', rdf)
        self.assertIn("\\tunità", rdf)

    def test_unknown_and_nonpublic_id_have_same_404(self):
        bundle = v3_bundle()
        results = []
        for identifier in ("statement:private", "statement:unknown", "finding:legacy"):
            with self.assertRaises(PublicApiError) as err:
                get_public_statement_v3(bundle, identifier, allow_statement_v3=True,
                    current_public_dataset_sha256=bundle["dataset_sha256"])
            results.append((err.exception.status, err.exception.code, err.exception.message))
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(results[0][0], 404)

    def test_no_current_v1_endpoint_or_file_loader_v3_support(self):
        routes = {route.pattern for route in ROUTES}
        self.assertFalse(any("/statements" in route for route in routes))
        bundle = v3_bundle()
        with self.assertRaises(PublicApiError) as err:
            build_index(bundle)
        self.assertEqual(err.exception.status, 503)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "index.json"
            path.write_text(json.dumps(bundle), encoding="utf-8")
            with self.assertRaises(PublicApiError) as err:
                load_index(path, use_cache=False)
            self.assertEqual(err.exception.status, 503)
        self.assertEqual(validate_public_bundle(v2_bundle())["schema_version"], PUBLIC_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
