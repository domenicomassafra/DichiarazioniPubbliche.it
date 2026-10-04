import json
import sys
import unittest
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.evidence_query import (  # noqa: E402
    compile_official_query,
)


class EvidenceQueryTests(unittest.TestCase):
    def test_normattiva_search_is_bounded_post_not_arbitrary_url(self):
        request = compile_official_query(
            "normattiva-opendata",
            "SIMPLE_SEARCH",
            {"text": "imposta automobilistica", "page_size": 20},
        )
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.content_type, "application/json")
        body = json.loads(request.body)
        self.assertEqual(body["testoRicerca"], "imposta automobilistica")
        self.assertEqual(body["paginazione"]["numeroElementiPerPagina"], 20)
        with self.assertRaisesRegex(ValueError, "PAGE_SIZE"):
            compile_official_query(
                "normattiva-opendata",
                "SIMPLE_SEARCH",
                {"text": "x", "page_size": 500},
            )

    def test_istat_path_components_reject_injection(self):
        request = compile_official_query(
            "istat-sdmx",
            "SDMX_DATA",
            {"flow_ref": "123_456", "key": "A.IT.*"},
        )
        self.assertTrue(request.url.startswith("https://esploradati.istat.it/SDMXWS/rest/data/"))
        with self.assertRaisesRegex(ValueError, "FLOW_REF_INVALID"):
            compile_official_query(
                "istat-sdmx",
                "SDMX_DATA",
                {"flow_ref": "../admin", "key": "A.IT"},
            )

    def test_eurostat_filters_are_sorted_and_bounded(self):
        request = compile_official_query(
            "eurostat-api",
            "STATISTICS_DATA",
            {
                "dataset": "une_rt_m",
                "filters": {"geo": "IT", "sex": ["F", "M"]},
            },
        )
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.url).query)
        self.assertEqual(query["geo"], ["IT"])
        self.assertEqual(query["sex"], ["F", "M"])
        with self.assertRaisesRegex(ValueError, "FILTER_VALUE"):
            compile_official_query(
                "eurostat-api",
                "STATISTICS_DATA",
                {"dataset": "x", "filters": {"geo": "IT&evil=1"}},
            )

    def test_parliament_query_is_template_only(self):
        request = compile_official_query(
            "senato-linked-data",
            "RESOURCE_PROPERTIES",
            {"resource_uri": "http://dati.senato.it/senatore/123", "limit": 50},
        )
        parsed = urllib.parse.parse_qs(urllib.parse.urlsplit(request.url).query)
        query = parsed["query"][0]
        self.assertTrue(query.startswith("SELECT ?predicate ?object WHERE"))
        self.assertIn("LIMIT 50", query)
        with self.assertRaisesRegex(ValueError, "RESOURCE_URI_INVALID"):
            compile_official_query(
                "senato-linked-data",
                "RESOURCE_PROPERTIES",
                {"resource_uri": "http://evil.test/x> } SERVICE <http://evil.test> {"},
            )

    def test_unknown_query_template_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "TEMPLATE_NOT_ALLOWED"):
            compile_official_query("istat-sdmx", "RAW_URL", {"url": "https://evil.test"})


if __name__ == "__main__":
    unittest.main()
