"""Independent RDFLib audit of approved public export bytes (DP-176).

This optional developer/CI suite never changes the stdlib public serializers.
The dedicated rdf-contract job installs and version-checks RDFLib; minimal
backend unittest discovery can still run without any third-party package.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from rdflib import Graph, Literal, Namespace, URIRef
    from rdflib.compare import isomorphic
    from rdflib.namespace import RDF, XSD
except ImportError:
    Graph = None

from dichiarazioni_pubbliche.linked_data import (  # noqa: E402
    projection_linked_data_receipt,
    projection_ntriples,
    projection_statement_v3_jsonld,
    projection_statement_v3_ntriples,
    public_resource_uri,
)
from dichiarazioni_pubbliche.public_projection import build_public_projection  # noqa: E402
from test_dp435_public_statement_seam import IsolatedStatementSource, SHA  # noqa: E402
from test_dp436_public_statement_consumers import with_derived  # noqa: E402
from test_public_projection import FakeSource, valid_row  # noqa: E402


@unittest.skipUnless(Graph is not None, "RDFLib is an optional dev dependency")
class RDFLibPublicExportTests(unittest.TestCase):
    def parse_nt(self, encoded):
        graph = Graph().parse(data=encoded, format="nt")
        self.assertEqual(len(graph), len(encoded.splitlines()), "duplicate RDF triples")
        return graph

    def assert_roundtrip(self, graph, fmt):
        encoded = graph.serialize(format=fmt)
        reparsed = Graph().parse(data=encoded, format=fmt)
        self.assertTrue(isomorphic(graph, reparsed), f"{fmt} graph roundtrip changed")

    def test_v2_public_index_nt_is_valid_stable_and_fingerprinted(self):
        bundle = build_public_projection(
            FakeSource([valid_row()]), generated_at="2026-10-19T00:00:00Z"
        )
        encoded = projection_ntriples(bundle)
        receipt = projection_linked_data_receipt(bundle)
        self.assertEqual(bundle["dataset_sha256"], "fa890e20533d851edac58b1498c960c636edb1a0d34f9cfeebc7434805123f2b")
        self.assertEqual(hashlib.sha256(encoded.encode()).hexdigest(), "4042d614bba09c7db4172ce8caf03d18334990122cecaeac308eeb318bd1d9a1")
        self.assertEqual(receipt["ntriples_sha256"], hashlib.sha256(encoded.encode()).hexdigest())
        self.assertEqual(receipt["byte_count"], len(encoded.encode()))
        graph = self.parse_nt(encoded)
        self.assertEqual(len(graph), receipt["triple_count"])
        dataset = URIRef(public_resource_uri("dataset", bundle["dataset_sha256"]))
        dp = Namespace("https://dichiarazionipubbliche.it/vocab#")
        schema = Namespace("https://schema.org/")
        self.assertIn((dataset, dp.projectionFingerprint, Literal(bundle["dataset_sha256"])), graph)
        self.assertIn((dataset, schema.version, Literal(bundle["schema_version"])), graph)
        self.assert_roundtrip(graph, "nt")

    def test_v3_jsonld_and_nt_share_approved_semantic_triples(self):
        bundle = with_derived()
        nt = projection_statement_v3_ntriples(bundle, allow_statement_v3=True)
        document = projection_statement_v3_jsonld(bundle, allow_statement_v3=True)
        self.assertEqual(bundle["dataset_sha256"], "c850689cde27d5ef4b583b38796dbe50c82a1a522d463d166857883aea82d131")
        self.assertEqual(hashlib.sha256(nt.encode()).hexdigest(), "db72d72f4344820cac05b543d96f371dbca128c29fafbb585396261abe851dd3")
        nt_graph = self.parse_nt(nt)
        jsonld_graph = Graph().parse(data=json.dumps(document, ensure_ascii=False), format="json-ld")
        self.assert_roundtrip(nt_graph, "nt")
        self.assert_roundtrip(jsonld_graph, "json-ld")

        record = bundle["statements"][0]
        subjects = {
            URIRef(public_resource_uri("dataset", bundle["dataset_sha256"])),
            URIRef(public_resource_uri("statement", record["statement_id"])),
            *(URIRef(public_resource_uri("representation", f'{record["version_id"]}:{kind}'))
              for kind in ("summary", "translation") if record[kind] is not None),
        }
        dp = Namespace("https://dichiarazionipubbliche.it/vocab#")
        schema = Namespace("https://schema.org/")
        common = {
            RDF.type, schema.hasPart, schema.identifier, schema.version,
            schema.text, schema.inLanguage, schema.dateCreated,
            schema.dateModified, schema.isPartOf, schema.author, schema.subjectOf,
            dp.projectionFingerprint, dp.wordingType, dp.quoteSha256,
            dp.sourceSha256, dp.sourceVersion, dp.sourceKind,
            dp.speechAct, dp.recordedSpeaker, dp.sourceQuoteSha256,
            dp.sourceLanguage,
        }
        shared = lambda graph: {
            (subject, predicate, obj)
            for subject, predicate, obj in graph
            if subject in subjects and predicate in common
            and not (subject == URIRef(public_resource_uri("dataset", bundle["dataset_sha256"]))
                     and predicate == schema.hasPart)
        }
        self.assertEqual(shared(nt_graph), shared(jsonld_graph))
        quote = URIRef(public_resource_uri("statement", record["statement_id"]))
        dataset = URIRef(public_resource_uri("dataset", bundle["dataset_sha256"]))
        self.assertIn((dataset, schema.hasPart, quote), nt_graph)
        self.assertIn(quote, jsonld_graph.subjects(RDF.type, schema.Quotation))
        self.assertIn((quote, schema.text, Literal(record["original_text"])), nt_graph)
        self.assertIn((quote, schema.text, Literal(record["original_text"])), jsonld_graph)
        # The opt-in JSON-LD deliberately types booleans; the v3 NT contract
        # emits legacy plain strings. Both describe the same endorsed value.
        self.assertIn((quote, dp.endorsed, Literal(str(record["endorsed"]).lower())), nt_graph)
        self.assertIn((quote, dp.endorsed, Literal(record["endorsed"], datatype=XSD.boolean)), jsonld_graph)

    def test_invalid_nt_and_well_formed_forged_triples_are_rejected(self):
        bundle = with_derived()
        original = projection_statement_v3_ntriples(bundle, allow_statement_v3=True)
        original_graph = self.parse_nt(original)
        with self.assertRaises(Exception):
            Graph().parse(data='<https://example.test/s> <https://example.test/p> <unterminated .', format="nt")
        tampered = original.replace(f'"{bundle["dataset_sha256"]}"', '"' + '0' * 64 + '"', 1)
        self.assertNotEqual(tampered, original)
        changed = self.parse_nt(tampered)
        self.assertFalse(isomorphic(original_graph, changed), "forged fingerprint accepted")

    def test_special_escaped_source_wording_survives_rdf_parse(self):
        source = IsolatedStatementSource()
        quoted = 'La cifra è "10" \\ unità\tcon\nnuova riga 💡'
        source.source_text = "Prima: " + quoted + " Dopo."
        offset = source.source_text.index(quoted)
        source.row["original_text"] = quoted
        source.row["source_sha256"] = SHA(source.source_text)
        source.row["locator"] = {"start_char": offset, "end_char": offset + len(quoted)}
        for proof in source.gates.values():
            proof["source_sha256"] = SHA(source.source_text)
            proof["quote_sha256"] = SHA(quoted)
            proof["span_start"] = offset
            proof["span_end"] = offset + len(quoted)
        bundle = build_public_projection(source, include_public_statements=True)
        self.assertEqual(len(bundle["statements"]), 1)
        nt = projection_statement_v3_ntriples(bundle, allow_statement_v3=True)
        graph = self.parse_nt(nt)
        quote = URIRef(public_resource_uri("statement", source.row["statement_id"]))
        self.assertIn((quote, Namespace("https://schema.org/").text, Literal(quoted)), graph)
        self.assertIn('\\\\', nt)
        self.assertIn('\\t', nt)
        self.assertIn('\\n', nt)
        self.assertNotIn('\t', nt)

    def test_revocation_and_nonendorsement_stay_nonpublic(self):
        schema = Namespace("https://schema.org/")
        for gate, value in (("rights", "REVOKED"), ("rights", "UNKNOWN"), ("publication", "HELD")):
            with self.subTest(gate=gate, value=value):
                source = IsolatedStatementSource()
                source.gates[gate]["status"] = value
                bundle = build_public_projection(source, include_public_statements=True)
                self.assertEqual(bundle["statements"], [])
                nt = self.parse_nt(projection_statement_v3_ntriples(bundle, allow_statement_v3=True))
                document = projection_statement_v3_jsonld(bundle, allow_statement_v3=True)
                jsonld = Graph().parse(data=json.dumps(document), format="json-ld")
                self.assertEqual(list(nt.triples((None, RDF.type, schema.Quotation))), [])
                self.assertEqual(list(jsonld.triples((None, RDF.type, schema.Quotation))), [])

        source = IsolatedStatementSource()
        source.gates["context"]["speech_act"] = "REPORTED_QUOTE"
        source.gates["context"]["endorsed"] = False
        bundle = build_public_projection(source, include_public_statements=True)
        nt = self.parse_nt(projection_statement_v3_ntriples(bundle, allow_statement_v3=True))
        document = projection_statement_v3_jsonld(bundle, allow_statement_v3=True)
        jsonld = Graph().parse(data=json.dumps(document), format="json-ld")
        quote = URIRef(public_resource_uri("statement", source.row["statement_id"]))
        self.assertEqual(list(nt.objects(quote, schema.author)), [])
        self.assertEqual(list(jsonld.objects(quote, schema.author)), [])


if __name__ == "__main__":
    unittest.main()
