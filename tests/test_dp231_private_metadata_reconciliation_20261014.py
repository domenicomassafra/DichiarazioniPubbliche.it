"""Real Python capture/public-projection fixtures; private metadata only."""

from __future__ import annotations

import sys
import copy
import unittest
from dataclasses import replace
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / "poc"),
    str(Path(__file__).resolve().parent),
]

from dichiarazioni_pubbliche.capture_pipeline import extract_source_metadata  # noqa: E402
from dichiarazioni_pubbliche.public_projection import build_public_projection  # noqa: E402
from dichiarazioni_pubbliche.source_metadata_enrichment import (  # noqa: E402
    MetadataCandidate,
    build_metadata_enrichment,
)
from test_public_projection import FakeSource, valid_row  # noqa: E402
from test_public_schema import valid_content  # noqa: E402


def real_public():
    return build_public_projection(
        FakeSource([valid_row()]),
        generated_at="2026-10-13T12:00:00Z",
    )


def captured(
    *,
    title="Source",
    publisher="Public organization",
    canonical="https://example.test/source",
    content_id="content:a",
):
    # Real capture HTML metadata parser, not a mocked metadata DTO.
    html = f'''<html><head><title>{title}</title>
    <link rel="canonical" href="{canonical}">
    <meta property="og:title" content="{title}">
    <meta property="og:site_name" content="{publisher}">
    <link rel="alternate" type="application/json+oembed" href="https://embed.example.test/oembed">
    <script type="application/ld+json">{{"@type":"NewsArticle","headline":"{title}"}}</script>
    </head><body>Synthetic text only.</body></html>'''
    parsed = extract_source_metadata(html, base_url="https://example.test/source")
    return build_metadata_enrichment(
        content_id=content_id,
        parsed_metadata=parsed,
        content_identity={
            "canonical_url": "https://example.test/source",
            "title": "Source",
        },
        source_registry_identity={"publisher": "Public organization"},
    )


class PrivateMetadataReviewTests(unittest.TestCase):
    def plan(self, before=None, after=None, **overrides):
        from dichiarazioni_pubbliche.private_source_metadata_review_v1 import (
            plan_private_metadata_recheck,
            metadata_snapshot_sha256,
        )

        before = before or captured()
        after = after or before
        projection = real_public()
        values = dict(
            previous=before,
            current=after,
            expected_previous_sha256=metadata_snapshot_sha256(before),
            expected_current_sha256=metadata_snapshot_sha256(after),
            public_projection=projection,
            expected_public_projection_sha256=projection["dataset_sha256"],
            expected_public_generated_at=projection["generated_at"],
            content_id="content:a",
            source_use_status="APPROVED",
            source_review_status="APPROVED",
            allow_private_preview=True,
        )
        values.update(overrides)
        return plan_private_metadata_recheck(**values)

    def test_actual_capture_and_public_projection_join_no_authority(self):
        result = self.plan()
        self.assertEqual(result.status, "UNCHANGED_REVIEW_PENDING")
        self.assertEqual(result.changed_fields, ())
        self.assertFalse(result.publication_authority)
        self.assertFalse(result.source_approval_authority)
        self.assertFalse(result.factual_verification)
        self.assertFalse(result.identity_mutation_allowed)
        self.assertFalse(result.approved_official_source)
        self.assertTrue(result.private_only)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(result.capture_calls, 0)
        self.assertEqual(result, self.plan())
        self.assertNotIn("https://", repr(result))

    def test_canonical_url_and_title_drift_cannot_rebind_public_content(self):
        before = captured()
        after = captured(
            title="UNAPPROVED_PRIVATE_TITLE",
            canonical="https://other.example.test/source",
        )
        result = self.plan(before, after)
        self.assertEqual(result.status, "WITHHELD_IDENTITY_REVIEW")
        self.assertIn("canonical_url", result.changed_fields)
        self.assertIn("title", result.changed_fields)
        self.assertIn("PUBLIC_CONTENT_LOCATOR_MISMATCH", result.reason_codes)
        self.assertIn("CONTENT_CANONICAL_URL_CONFLICT", result.new_conflict_codes)
        self.assertNotIn("UNAPPROVED_PRIVATE_TITLE", repr(result))
        self.assertNotIn("other.example", repr(result))

    def test_altered_publisher_or_oembed_metadata_never_promotes_provider(self):
        before, after = captured(), captured(publisher="Unreviewed publisher")
        result = self.plan(before, after)
        self.assertEqual(result.status, "REVIEW_REQUIRED")
        self.assertIn("publisher", result.changed_fields)
        self.assertIn("SOURCE_REGISTRY_PUBLISHER_CONFLICT", result.new_conflict_codes)
        self.assertFalse(result.approved_official_source)

    def test_rights_hold_revocation_or_no_review_refuses_unchanged(self):
        for policy in ("REVOKED", "PENDING", "EXPIRED", "DENIED"):
            with self.subTest(policy=policy):
                result = self.plan(source_use_status=policy)
                self.assertEqual(result.status, "WITHHELD_SOURCE_POLICY")
                self.assertEqual(result.reason_codes, ("SOURCE_USE_NOT_APPROVED",))
                self.assertFalse(result.publication_authority)
        result = self.plan(source_review_status="PENDING")
        self.assertEqual(result.status, "WITHHELD_SOURCE_POLICY")
        self.assertIn("SOURCE_REVIEW_NOT_APPROVED", result.reason_codes)

    def test_unapproved_private_and_credentialed_url_does_not_echo(self):
        before = captured()
        # HTML parser already filters many unsafe locators. The lower-level
        # metadata parser can still receive an unsafe candidate through an
        # alternate approved adapter; it must remain a digest-only conflict.
        after = build_metadata_enrichment(
            content_id="content:a",
            parsed_metadata={
                "canonical_url_candidates": ["https://user:secret@localhost/private"]
            },
            content_identity={"canonical_url": "https://example.test/source"},
        )
        result = self.plan(before, after)
        self.assertEqual(result.status, "REVIEW_REQUIRED")
        self.assertIn("UNSAFE_CANONICAL_CANDIDATE", result.new_conflict_codes)
        self.assertNotIn("secret", repr(result))
        self.assertNotIn("localhost", repr(result))

    def test_pins_bad_public_release_content_identity_and_optin_fail_closed(self):
        for kw, error in (
            ({"expected_previous_sha256": "0" * 64}, "METADATA_PIN_MISMATCH"),
            (
                {"expected_public_projection_sha256": "0" * 64},
                "PUBLIC_PROJECTION_PIN_MISMATCH",
            ),
            (
                {"expected_public_generated_at": "2026-09-01T00:00:00Z"},
                "PUBLIC_PROJECTION_PIN_MISMATCH",
            ),
            ({"allow_private_preview": False}, "PRIVATE_OPT_IN_REQUIRED"),
        ):
            with self.subTest(kw=kw), self.assertRaisesRegex(ValueError, error):
                self.plan(**kw)
        with self.assertRaisesRegex(ValueError, "METADATA_CONTENT_ID_MISMATCH"):
            self.plan(after=captured(content_id="content:other"))
        missing = captured(content_id="content:unpublished")
        with self.assertRaisesRegex(ValueError, "PUBLIC_CONTENT_NOT_FOUND"):
            self.plan(before=missing, after=missing, content_id="content:unpublished")

    def test_forged_rehashed_candidate_authority_or_unsafe_url_refuses(self):
        from dichiarazioni_pubbliche.private_source_metadata_review_v1 import (
            metadata_snapshot_sha256,
        )

        safe = captured()
        rogue = replace(
            safe, candidates=(replace(safe.candidates[0], publication_authority=True),)
        )
        with self.assertRaisesRegex(ValueError, "METADATA_SNAPSHOT_INVALID"):
            metadata_snapshot_sha256(rogue)
        rogue_url = replace(
            safe, canonical_url_candidates=("https://127.0.0.1/PRIVATE",)
        )
        with self.assertRaisesRegex(ValueError, "METADATA_SNAPSHOT_INVALID"):
            metadata_snapshot_sha256(rogue_url)
        rogue_type = replace(
            safe,
            candidates=(
                MetadataCandidate(
                    field="PRIVATE_BODY", value="PRIVATE_RAW", origin="hacked"
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, "METADATA_SNAPSHOT_INVALID"):
            metadata_snapshot_sha256(rogue_type)

    def test_missing_metadata_does_not_prove_absence_of_source(self):
        before = captured()
        empty = build_metadata_enrichment(
            content_id="content:a",
            parsed_metadata={},
            content_identity={},
        )
        result = self.plan(before, empty)
        self.assertEqual(result.status, "REVIEW_REQUIRED")
        self.assertIn("metadata_removed", result.changed_fields)
        self.assertFalse(result.absence_of_original_established)

    def test_reordering_approved_shaped_metadata_never_creates_false_drift(self):
        from dichiarazioni_pubbliche.private_source_metadata_review_v1 import (
            metadata_snapshot_sha256,
        )

        older = captured()
        reversed_rows = replace(older, candidates=tuple(reversed(older.candidates)))
        self.assertEqual(
            metadata_snapshot_sha256(older), metadata_snapshot_sha256(reversed_rows)
        )
        self.assertEqual(
            self.plan(older, reversed_rows).status, "UNCHANGED_REVIEW_PENDING"
        )

    def test_pinned_public_source_url_drift_fails_closed_and_then_requires_review(self):
        from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256

        original = real_public()
        tampered = copy.deepcopy(original)
        tampered["dossiers"][0]["source"]["url"] = (
            "https://unreviewed.example.test/other"
        )
        with self.assertRaisesRegex(ValueError, "PUBLIC_PROJECTION_INVALID"):
            self.plan(public_projection=tampered)
        # This is NOT accepted by recomputing a hash from attacker input;
        # caller must separately obtain the new owner-held projection pin.
        tampered["dataset_sha256"] = projection_dataset_sha256(tampered)
        result = self.plan(
            public_projection=tampered,
            expected_public_projection_sha256=tampered["dataset_sha256"],
        )
        self.assertEqual(result.status, "WITHHELD_IDENTITY_REVIEW")
        self.assertEqual(result.reason_codes, ("PUBLIC_CONTENT_LOCATOR_MISMATCH",))

    def test_dynamic_public_projection_mapping_cannot_change_after_validation(self):
        class AlteringPublicBundle(dict):
            def __getitem__(self, key):
                if key == "dossiers":
                    self.setdefault("private_raw_body", "MUST_NOT_COPY")
                return super().__getitem__(key)

        with self.assertRaisesRegex(ValueError, "PUBLIC_PROJECTION_INVALID"):
            self.plan(public_projection=AlteringPublicBundle(real_public()))

    def test_standalone_public_content_without_finding_is_reconcilable(self):
        from dichiarazioni_pubbliche.public_schema import (
            projection_dataset_sha256,
            validate_public_bundle,
        )

        current = real_public()
        content = valid_content()
        content.update(
            content_id="content:standalone", slug="standalone", finding_ids=[]
        )
        current["contents"].append(content)
        current["dataset_sha256"] = projection_dataset_sha256(current)
        validate_public_bundle(current)
        metadata = captured(content_id="content:standalone")
        result = self.plan(
            before=metadata,
            after=metadata,
            content_id="content:standalone",
            public_projection=current,
            expected_public_projection_sha256=current["dataset_sha256"],
        )
        self.assertEqual(result.status, "UNCHANGED_REVIEW_PENDING")
        self.assertFalse(result.source_approval_authority)

    def test_canonical_content_and_dossier_locator_disagreement_refused(self):
        from dichiarazioni_pubbliche.public_schema import (
            projection_dataset_sha256,
            validate_public_bundle,
        )

        current = real_public()
        content = valid_content()
        content.update(
            content_id="content:a",
            slug="content-a",
            finding_ids=[],
            url="https://different.example.test/unreviewed",
        )
        current["contents"].append(content)
        current["dataset_sha256"] = projection_dataset_sha256(current)
        validate_public_bundle(current)
        with self.assertRaisesRegex(ValueError, "PUBLIC_CONTENT_IDENTITY_AMBIGUOUS"):
            self.plan(
                public_projection=current,
                expected_public_projection_sha256=current["dataset_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
