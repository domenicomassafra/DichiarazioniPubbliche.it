"""DP231 offline source coverage against real captured metadata and public-v2 bundles."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "poc"), str(ROOT / "tests")]

from dichiarazioni_pubbliche.private_source_metadata_review_v1 import (  # noqa: E402
    metadata_snapshot_sha256,
)
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256  # noqa: E402
from dichiarazioni_pubbliche.source_metadata_enrichment import (  # noqa: E402
    build_metadata_enrichment,
)
from test_dp231_metadata_release_cohort_20261014 import (  # noqa: E402
    release_with_standalone,
)
from test_dp231_private_metadata_reconciliation_20261014 import (  # noqa: E402
    captured,
    real_public,
)


AT = datetime(2026, 10, 14, 18, tzinfo=timezone.utc)


def audit(projection=None, inventories=None, policies=None, **overrides):
    from dichiarazioni_pubbliche.private_source_coverage_v1 import (
        coverage_inventory_manifest_sha256,
        coverage_policy_manifest_sha256,
        plan_private_source_coverage,
    )

    projection = projection if projection is not None else release_with_standalone()
    inventories = (
        inventories
        if inventories is not None
        else {
            "capture": {
                "content:a": captured(),
                "content:standalone": captured(content_id="content:standalone"),
            },
            "registry": {
                "content:a": captured(),
                "content:standalone": captured(content_id="content:standalone"),
            },
        }
    )
    policies = (
        policies
        if policies is not None
        else {
            "content:a": ("APPROVED", "APPROVED"),
            "content:standalone": ("APPROVED", "APPROVED"),
        }
    )
    observed = {name: "2026-10-14T13:00:00Z" for name in inventories}
    pins = {
        name: {key: metadata_snapshot_sha256(record) for key, record in records.items()}
        for name, records in inventories.items()
    }
    arguments = {
        "public_projection": projection,
        "expected_public_sha256": projection["dataset_sha256"],
        "expected_public_generated_at": projection["generated_at"],
        "metadata_inventories": inventories,
        "expected_metadata_pins": pins,
        "inventory_observed_at": observed,
        "expected_inventory_manifest_sha256": coverage_inventory_manifest_sha256(
            pins, observed
        ),
        "source_policies": policies,
        "expected_source_policy_sha256": coverage_policy_manifest_sha256(policies),
        "source_role_claims": {},
        "as_of": AT,
        "max_inventory_age_days": 15,
        "private_opt_in": True,
    }
    arguments.update(overrides)
    return plan_private_source_coverage(**arguments)


class SourceCoverageTests(unittest.TestCase):
    def test_real_linked_dossier_and_standalone_public_content_in_both_inventories(
        self,
    ):
        plan = audit()
        self.assertEqual(plan.content_count, 2)
        self.assertEqual(plan.linked_content_count, 1)
        self.assertEqual(plan.standalone_content_count, 1)
        self.assertEqual(plan.status, "PRIVATE_REVIEW_ONLY")
        self.assertEqual(plan.missing_count, 0)
        self.assertEqual(plan.held_count, 0)
        self.assertEqual(len(plan.items), 2)
        self.assertTrue(
            all(
                item.reason_codes == ("MANUAL_SOURCE_COVERAGE_REVIEW",)
                for item in plan.items
            )
        )
        self.assertFalse(plan.source_approval_authority)
        self.assertFalse(plan.publication_authority)
        self.assertEqual(plan.provider_calls, 0)
        self.assertEqual(plan.capture_calls, 0)
        self.assertEqual(audit(), plan)
        for sentinel in (
            "content:a",
            "content:standalone",
            "https://",
            "Public organization",
        ):
            self.assertNotIn(sentinel, repr(plan))

    def test_unscoped_standalone_and_dossier_missing_metadata_never_return_clean(self):
        entirely_absent = audit(inventories={"capture": {}, "registry": {}})
        self.assertEqual(entirely_absent.content_count, 2)
        self.assertEqual(entirely_absent.missing_count, 2)
        self.assertEqual(entirely_absent.held_count, 2)
        self.assertTrue(
            all(
                "METADATA_ABSENT_ALL_INVENTORIES" in x.reason_codes
                for x in entirely_absent.items
            )
        )
        one_missing = audit(
            inventories={
                "capture": {"content:a": captured()},
                "registry": {"content:a": captured()},
            }
        )
        self.assertEqual(one_missing.missing_count, 1)
        self.assertFalse(one_missing.source_approval_authority)

    def test_partially_missing_and_stale_inventory_includes_dossier_and_standalone(
        self,
    ):
        from dichiarazioni_pubbliche.private_source_coverage_v1 import (
            coverage_inventory_manifest_sha256,
        )

        records = {
            "content:a": captured(),
            "content:standalone": captured(content_id="content:standalone"),
        }
        inventories = {"capture": records, "registry": {"content:a": captured()}}
        observed = {
            "capture": "2026-09-01T13:00:00Z",
            "registry": "2026-10-14T13:00:00Z",
        }
        pins = {
            name: {
                identifier: metadata_snapshot_sha256(item)
                for identifier, item in group.items()
            }
            for name, group in inventories.items()
        }
        args = dict(inventories=inventories, inventory_observed_at=observed)
        with self.assertRaisesRegex(ValueError, "COVERAGE_INVENTORY_PIN_MISMATCH"):
            audit(**args)
        view = audit(
            **args,
            expected_inventory_manifest_sha256=coverage_inventory_manifest_sha256(
                pins, observed
            ),
        )
        self.assertEqual(view.missing_count, 1)
        self.assertEqual(view.stale_count, 2)
        self.assertEqual(view.held_count, 2)
        self.assertTrue(
            any("STALE_METADATA_INVENTORY" in item.reason_codes for item in view.items)
        )

    def test_distinct_canonical_candidate_discordance_between_private_inventories_held(
        self,
    ):
        different = build_metadata_enrichment(
            content_id="content:a",
            parsed_metadata={
                "canonical_url_candidates": [
                    "https://other.example.test/SECRET_PRIVATE_PATH"
                ]
            },
            content_identity={"canonical_url": "https://example.test/source"},
        )
        view = audit(
            inventories={
                "capture": {"content:a": captured()},
                "registry": {"content:a": different},
            }
        )
        self.assertEqual(
            view.held_count, 2
        )  # standalone has no metadata in this fixture
        by_reason = [
            x for x in view.items if "PRIVATE_CANONICAL_DISCORDANCE" in x.reason_codes
        ]
        self.assertEqual(len(by_reason), 1)
        self.assertNotIn("SECRET_PRIVATE_PATH", repr(view))
        self.assertNotIn("other.example", repr(view))

    def test_two_public_canonical_urls_same_content_fail_closed_even_if_rehashed(self):
        from test_public_schema import valid_content

        projection = real_public()
        same_id = valid_content()
        same_id.update(
            content_id="content:a",
            slug="duplicate",
            finding_ids=[],
            url="https://second.example.test/private",
        )
        projection["contents"].append(same_id)
        projection["dataset_sha256"] = projection_dataset_sha256(projection)
        with self.assertRaisesRegex(
            ValueError, "COVERAGE_PUBLIC_CANONICAL_DISCORDANCE"
        ):
            audit(
                projection=projection,
                inventories={"capture": {"content:a": captured()}},
            )

    def test_different_content_ids_sharing_url_remain_distinct_opaque_subjects(self):
        from test_public_schema import valid_content

        projection = real_public()
        conflict = valid_content()
        conflict.update(
            content_id="content:shadow",
            slug="shadow",
            finding_ids=[],
            url=projection["dossiers"][0]["source"]["url"],
        )
        projection["contents"].append(conflict)
        projection["dataset_sha256"] = projection_dataset_sha256(projection)
        result = audit(
            projection=projection,
            inventories={"capture": {"content:a": captured()}},
            policies={"content:a": ("APPROVED", "APPROVED")},
        )
        self.assertEqual(result.content_count, 2)
        self.assertEqual(result.missing_count, 1)
        self.assertEqual(len({item.opaque_content_ref for item in result.items}), 2)

    def test_rights_review_hold_and_self_attested_official_role_cannot_authorize(self):
        records = {"content:a": captured()}
        rights = {"content:a": ("REVOKED", "APPROVED")}
        result = audit(
            projection=real_public(),
            inventories={"capture": records, "registry": records},
            policies=rights,
            source_role_claims={"content:a": "OFFICIAL_SOURCE"},
        )
        self.assertEqual(result.held_count, 1)
        self.assertEqual(result.status, "PRIVATE_COVERAGE_HOLDS")
        self.assertIn("SOURCE_RIGHTS_OR_REVIEW_HOLD", result.items[0].reason_codes)
        self.assertIn(
            "SELF_ATTESTED_SOURCE_ROLE_NO_AUTHORITY", result.items[0].reason_codes
        )
        self.assertFalse(result.source_approval_authority)

    def test_expected_independent_sha_and_mutation_after_preflight_fail_closed(self):
        for invalid in (
            {"expected_public_sha256": "f" * 64},
            {"expected_source_policy_sha256": "f" * 64},
            {"expected_inventory_manifest_sha256": "f" * 64},
            {"private_opt_in": False},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                audit(**invalid)
        swapped = {"capture": {"content:a": captured()}, "registry": {}}
        pins = {"capture": {"content:a": "0" * 64}, "registry": {}}
        with self.assertRaises(ValueError):
            audit(inventories=swapped, expected_metadata_pins=pins)

        # A dict subclass can redirect lookup after its digest is computed.
        class LateSwap(dict):
            def __getitem__(self, key):
                if key == "content:a":
                    return captured(title="UNAUTHORIZED_SECRET_AFTER_DIGEST")
                return super().__getitem__(key)

        with self.assertRaises(ValueError):
            audit(
                inventories={
                    "capture": LateSwap({"content:a": captured()}),
                    "registry": {},
                }
            )

    def test_snapshot_isolation_under_postvalidation_inventory_and_rights_swap(self):
        from dichiarazioni_pubbliche import private_source_coverage_v1 as coverage

        private = {"content:a": captured()}
        inventories = {"capture": private}
        policies = {"content:a": ("REVOKED", "PENDING")}
        original_canonical = coverage._safe_https_url
        calls = 0

        def mutate_late(url):
            nonlocal calls
            calls += 1
            policies["content:a"] = ("APPROVED", "APPROVED")
            private["content:a"] = captured(
                canonical="https://tampered.example.test/PRIVATE_NEVER_ECHO"
            )
            return original_canonical(url)

        with patch.object(coverage, "_safe_https_url", side_effect=mutate_late):
            result = audit(
                projection=real_public(), inventories=inventories, policies=policies
            )
        self.assertGreater(calls, 0)
        self.assertEqual(result.held_count, 1)
        self.assertEqual(
            result.items[0].reason_codes, ("SOURCE_RIGHTS_OR_REVIEW_HOLD",)
        )
        self.assertNotIn("PRIVATE_NEVER_ECHO", repr(result))

    def test_stale_empty_inventory_cannot_hide_staleness_or_missing_metadata(self):
        from dichiarazioni_pubbliche.private_source_coverage_v1 import (
            coverage_inventory_manifest_sha256,
        )

        old = {"capture": "2026-09-01T13:00:00Z"}
        view = audit(
            inventories={"capture": {}},
            inventory_observed_at=old,
            expected_inventory_manifest_sha256=coverage_inventory_manifest_sha256(
                {"capture": {}}, old
            ),
        )
        self.assertEqual(view.content_count, 2)
        self.assertEqual(view.stale_count, 2)
        self.assertEqual(view.missing_count, 2)
        self.assertEqual(view.held_count, 2)

    def test_unpublished_private_inventory_id_is_held_without_its_identifier(self):
        unrelated = {
            "content:PRIVATE_NEVER_ECHO": captured(
                content_id="content:PRIVATE_NEVER_ECHO"
            )
        }
        plan = audit(
            projection=real_public(),
            inventories={"capture": unrelated, "registry": {}},
            policies={},
        )
        self.assertEqual(plan.content_count, 2)
        self.assertEqual(plan.held_count, 2)
        self.assertNotIn("PRIVATE_NEVER_ECHO", repr(plan))
        self.assertNotIn("https://", json.dumps([item.__dict__ for item in plan.items]))

    def test_inventory_order_no_input_mutation_and_no_implicit_provider_effect(self):
        before = {
            "content:a": captured(),
            "content:standalone": captured(content_id="content:standalone"),
        }
        original = copy.deepcopy(before)
        a = audit(
            inventories={
                "registry": before,
                "capture": dict(reversed(list(before.items()))),
            }
        )
        b = audit(inventories={"capture": before, "registry": before})
        self.assertEqual(a, b)
        self.assertEqual(before, original)
        self.assertEqual(a.provider_calls, 0)
        self.assertEqual(a.capture_calls, 0)


if __name__ == "__main__":
    unittest.main()
