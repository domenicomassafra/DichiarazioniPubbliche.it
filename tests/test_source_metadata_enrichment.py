import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import extract_source_metadata  # noqa: E402
from dichiarazioni_pubbliche.source_metadata_enrichment import (  # noqa: E402
    MAX_CANDIDATES_PER_FIELD,
    MAX_VALUE_CHARS,
    MetadataEnrichmentError,
    build_metadata_enrichment,
)


class SourceMetadataEnrichmentTests(unittest.TestCase):
    def test_existing_capture_parser_output_roundtrips_into_contract(self):
        parsed = extract_source_metadata(
            """
            <html><head>
              <link rel="canonical" href="https://example.test/article">
              <link rel="alternate" type="application/json+oembed"
                    href="https://embed.example.test/oembed">
              <meta property="og:title" content="Page title">
              <meta name="description" content="Page description">
              <meta name="author" content="Mario Rossi">
              <meta property="og:site_name" content="Example News">
              <script type="application/ld+json">
                {"@type":"NewsArticle","headline":"Page title",
                 "publisher":{"@type":"Organization","name":"Example News"}}
              </script>
            </head><body>Visible body.</body></html>
            """,
            base_url="https://example.test/article",
        )
        enrichment = build_metadata_enrichment(
            content_id="content:parser-seam",
            parsed_metadata=parsed,
            content_identity={
                "canonical_url": "https://example.test/article",
                "title": "Page title",
            },
            source_registry_identity={"publisher": "Example News"},
        )

        self.assertFalse(enrichment.conflicts)
        self.assertIn(
            "Page description",
            {row.value for row in enrichment.candidates if row.field == "description"},
        )
        self.assertEqual(
            enrichment.oembed_endpoint_candidates,
            ("https://embed.example.test/oembed",),
        )

    def test_maps_bounded_metadata_into_explicit_non_authoritative_contract(self):
        enrichment = build_metadata_enrichment(
            content_id="content:1",
            parsed_metadata={
                "meta": {
                    "og:title": "Page title",
                    "description": "Page description",
                    "author": "Mario Rossi",
                    "og:site_name": "Example News",
                    "raw_body": "must never be copied",
                },
                "jsonld_identity": [
                    {
                        "headline": "JSON-LD title",
                        "author": {"name": "Mario Rossi"},
                        "publisher": {"name": "Example News"},
                        "articleBody": "must never be copied",
                    }
                ],
                "canonical_url_candidates": ["https://example.test/article"],
                "oembed_candidates": [
                    {"url": "https://embed.example.test/oembed", "type": "application/json+oembed"}
                ],
            },
            content_identity={
                "canonical_url": "https://example.test/article",
                "title": "Page title",
            },
            source_registry_identity={"publisher": "Example News"},
        )

        by_field = {}
        for candidate in enrichment.candidates:
            by_field.setdefault(candidate.field, []).append(candidate)
            self.assertFalse(candidate.publication_authority)
        self.assertEqual(by_field["description"][0].value, "Page description")
        self.assertEqual({row.value for row in by_field["author"]}, {"Mario Rossi"})
        self.assertIn("Example News", {row.value for row in by_field["publisher"]})
        self.assertEqual(enrichment.canonical_url_candidates, ("https://example.test/article",))
        self.assertEqual(
            enrichment.oembed_endpoint_candidates,
            ("https://embed.example.test/oembed",),
        )
        self.assertFalse(enrichment.publication_authority)
        self.assertFalse(enrichment.identity_mutation_allowed)
        encoded = json.dumps(enrichment.to_dict(), sort_keys=True)
        self.assertNotIn("raw_body", encoded)
        self.assertNotIn("articleBody", encoded)
        self.assertNotIn("must never be copied", encoded)

    def test_conflicts_are_explicit_and_never_rewrite_content_or_registry_identity(self):
        enrichment = build_metadata_enrichment(
            content_id="content:conflict",
            parsed_metadata={
                "meta": {
                    "og:title": "Different page title",
                    "author": "Different Author",
                    "og:site_name": "Different Publisher",
                },
                "canonical_url_candidates": ["https://other.example/article"],
            },
            content_identity={
                "canonical_url": "https://content.example/article",
                "title": "Stored title",
                "author": "Stored Author",
            },
            source_registry_identity={
                "canonical_url": "https://registry.example/source",
                "publisher": "Registry Publisher",
            },
        )

        codes = {conflict.code for conflict in enrichment.conflicts}
        self.assertIn("CONTENT_TITLE_CONFLICT", codes)
        self.assertIn("CONTENT_AUTHOR_CONFLICT", codes)
        self.assertIn("SOURCE_REGISTRY_PUBLISHER_CONFLICT", codes)
        self.assertIn("CONTENT_CANONICAL_URL_CONFLICT", codes)
        self.assertIn("SOURCE_REGISTRY_CANONICAL_URL_CONFLICT", codes)
        self.assertIn("CONTENT_SOURCE_REGISTRY_CANONICAL_CONFLICT", codes)
        self.assertFalse(enrichment.identity_mutation_allowed)
        content_conflict = next(
            row for row in enrichment.conflicts if row.code == "CONTENT_CANONICAL_URL_CONFLICT"
        )
        self.assertEqual(content_conflict.expected_value, "https://content.example/article")
        self.assertEqual(content_conflict.observed_values, ("https://other.example/article",))

    def test_unsafe_private_or_credentialed_urls_are_rejected_without_raw_url_retention(self):
        unsafe_values = [
            "https://127.0.0.1/private",
            "https://10.0.0.1/private",
            "https://service.internal/private",
            "https://user:pass@example.test/private",
            "http://example.test/insecure",
        ]
        enrichment = build_metadata_enrichment(
            content_id="content:unsafe",
            parsed_metadata={
                "canonical_url_candidates": unsafe_values,
                "oembed_candidates": [{"url": value} for value in unsafe_values],
            },
            content_identity={"canonical_url": "https://example.test/article"},
        )

        self.assertEqual(enrichment.canonical_url_candidates, ())
        self.assertEqual(enrichment.oembed_endpoint_candidates, ())
        codes = [conflict.code for conflict in enrichment.conflicts]
        self.assertEqual(codes.count("UNSAFE_CANONICAL_CANDIDATE"), len(unsafe_values))
        self.assertEqual(codes.count("UNSAFE_OEMBED_ENDPOINT"), len(unsafe_values))
        encoded = json.dumps(enrichment.to_dict(), sort_keys=True)
        for unsafe in unsafe_values:
            self.assertNotIn(unsafe, encoded)
        self.assertIn("sha256:", encoded)

    def test_reference_identity_with_unsafe_canonical_url_fails_closed(self):
        with self.assertRaisesRegex(MetadataEnrichmentError, "CONTENT_CANONICAL_URL_UNSAFE"):
            build_metadata_enrichment(
                content_id="content:unsafe-reference",
                parsed_metadata={},
                content_identity={"canonical_url": "https://192.168.1.2/private"},
            )
        with self.assertRaisesRegex(
            MetadataEnrichmentError,
            "SOURCE_REGISTRY_CANONICAL_URL_UNSAFE",
        ):
            build_metadata_enrichment(
                content_id="content:unsafe-registry",
                parsed_metadata={},
                content_identity={"canonical_url": "https://example.test/article"},
                source_registry_identity={"canonical_url": "https://localhost/source"},
            )

    def test_candidate_count_and_values_are_bounded(self):
        enrichment = build_metadata_enrichment(
            content_id="content:bounded",
            parsed_metadata={
                "meta": {
                    "og:title": "A" * (MAX_VALUE_CHARS + 500),
                    "twitter:title": "second",
                    "title": "third",
                },
                "jsonld_identity": [
                    {"headline": f"headline-{index}"}
                    for index in range(MAX_CANDIDATES_PER_FIELD + 10)
                ],
            },
            content_identity={},
        )
        titles = [row for row in enrichment.candidates if row.field == "title" and row.origin.startswith(("page_meta", "jsonld"))]
        self.assertLessEqual(len(titles), MAX_CANDIDATES_PER_FIELD)
        self.assertTrue(all(len(row.value) <= MAX_VALUE_CHARS for row in titles))


if __name__ == "__main__":
    unittest.main()
