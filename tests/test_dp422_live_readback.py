"""DP-422 negative tests: a green empty MiniPC is never proof of live data."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_dp422_live_readback import (
    CANONICAL_ROUTES,
    PRIVATE_OR_UNAPPROVED,
    ReadbackError,
    check_readback,
)

FINGERPRINT = "a" * 64


def _body(payload):
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def valid_response_map():
    responses = {
        "/search-index.v1.json": (200, _body({
            "schema_version": "dichiarazioni-pubbliche-search-index-v1",
            "projection_sha256": FINGERPRINT, "records": [],
        })),
        "/api/v1/index.json": (200, _body({
            "schema_version": "dichiarazioni-pubbliche-public-v2",
            "dataset_sha256": FINGERPRINT,
            "dossiers": [], "contents": [], "topics": [],
            "methodology": {"aggregate_person_score": False},
        })),
        "/api/v1/health": (200, _body({
            "data": {"dataset_fingerprint": FINGERPRINT, "dossier_count": 0},
        })),
        "/robots.txt": (200, b"User-agent: *\nAllow: /\nSitemap: https://dichiarazionipubbliche.it/sitemap.xml\n"),
        "/sitemap.xml": (200, (
            "<urlset>" + "".join(
                "<url><loc>https://dichiarazionipubbliche.it" + route + "</loc></url>"
                for route in CANONICAL_ROUTES
            ) + "</urlset>"
        ).encode()),
        "/_astro/main.css": (200, b"body {margin: 0}"),
    }
    for name in ("findings", "people", "topics", "records"):
        responses["/api/v1/" + name] = (200, _body({
            "data": [], "meta": {"dataset_fingerprint": FINGERPRINT},
        }))
    for route in CANONICAL_ROUTES:
        responses[route] = (200, (
            '<html lang="it"><head><meta name="robots" content="index,follow">'
            '<link rel="canonical" href="' + route + '">'
            '<link rel="stylesheet" href="/_astro/main.css">'
            '</head><body><main id="main"><h1>Archivio pubblico</h1>'
            '<a href="/esplora/">Esplora</a><a href="/metodo/">Metodo</a>'
            '</main></body></html>'
        ).encode())
    for route in PRIVATE_OR_UNAPPROVED:
        responses[route] = (404, b"not found")
    return responses


class DP422LiveReadbackTests(unittest.TestCase):
    def test_approved_empty_honest_result_does_not_mark_dp422_done(self):
        responses = valid_response_map()
        result = check_readback(responses.__getitem__, FINGERPRINT)
        self.assertEqual(result["result"], "PASS_APPROVED_EMPTY_ONLY")
        self.assertEqual(result["static_canonical_routes_http_200"], 6)
        self.assertFalse(result["production_dynamic_route_approval"])
        self.assertFalse(result["dp422_done"])

    def test_pinned_external_expected_fingerprint_is_mandatory(self):
        with self.assertRaisesRegex(ReadbackError, "SEARCH_PROJECTION_DRIFT"):
            check_readback(valid_response_map().__getitem__, "b" * 64)
        with self.assertRaisesRegex(ReadbackError, "INVALID_EXPECTED_FINGERPRINT"):
            check_readback(valid_response_map().__getitem__, "invalid")

    def test_rejects_disagreement_between_live_index_api_and_health(self):
        modifications = (
            ("/search-index.v1.json", lambda value: value.update(projection_sha256="b" * 64), "SEARCH_PROJECTION_DRIFT"),
            ("/api/v1/index.json", lambda value: value.update(dataset_sha256="b" * 64), "API_PROJECTION_DRIFT"),
            ("/api/v1/health", lambda value: value["data"].update(dataset_fingerprint="b" * 64), "HEALTH_PROJECTION_DRIFT"),
            ("/api/v1/topics", lambda value: value["meta"].update(dataset_fingerprint="b" * 64), "FINGERPRINT_DRIFT"),
            ("/search-index.v1.json", lambda value: value.update(records=[{"kind": "person"}]), "NOT_APPROVED_EMPTY"),
            ("/api/v1/index.json", lambda value: value.update(topics=[{"slug": "fake"}]), "NOT_APPROVED_EMPTY"),
        )
        for path, modify, reason in modifications:
            with self.subTest(path=path, reason=reason):
                responses = valid_response_map()
                value = json.loads(responses[path][1])
                modify(value)
                responses[path] = (200, _body(value))
                with self.assertRaisesRegex(ReadbackError, reason):
                    check_readback(responses.__getitem__, FINGERPRINT)

    def test_rejects_alias_production_leak_or_broken_static_page(self):
        modifications = (
            ("/tracce/relation-demo-public-services-update/", (200, b"demo"), "HTTP_STATUS"),
            ("/studio/corpus/", (200, b"private"), "HTTP_STATUS"),
            ("/", (200, b"<main>missing canonical</main>"), "CANONICAL_DRIFT"),
            ("/_astro/main.css", (404, b""), "HTTP_STATUS"),
        )
        for path, response, reason in modifications:
            with self.subTest(path=path):
                responses = valid_response_map()
                responses[path] = response
                with self.assertRaisesRegex(ReadbackError, reason):
                    check_readback(responses.__getitem__, FINGERPRINT)

    def test_rejects_sitemap_leaked_route_and_demo_html(self):
        responses = valid_response_map()
        old = responses["/sitemap.xml"][1]
        responses["/sitemap.xml"] = (200, old.replace(
            b"</urlset>",
            b"<url><loc>https://dichiarazionipubbliche.it/studio/corpus/</loc></url></urlset>",
        ))
        with self.assertRaisesRegex(ReadbackError, "SITEMAP_CANONICAL_SET_DRIFT"):
            check_readback(responses.__getitem__, FINGERPRINT)
        responses = valid_response_map()
        responses["/metodo/"] = (
            200,
            responses["/metodo/"][1].replace(b"Archivio pubblico", b"Ambiente dimostrativo"),
        )
        with self.assertRaisesRegex(ReadbackError, "DEMO_OR_PRIVATE_LEAK"):
            check_readback(responses.__getitem__, FINGERPRINT)


if __name__ == "__main__":
    unittest.main()
