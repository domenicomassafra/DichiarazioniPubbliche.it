"""DP-304 real-case canary regressions: selection, rights hold, revocation, leaks."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tools"))

from dichiarazioni_pubbliche.dp304_case_fixture import (  # noqa: E402
    CASE_FIELDS,
    SENTINELS,
    case_row,
)
from dichiarazioni_pubbliche.policy.privacy_policy import (  # noqa: E402
    DataClass,
    ProjectionInput,
    decide_projection,
)
from dichiarazioni_pubbliche.public_projection import (  # noqa: E402
    build_public_projection,
    write_public_bundle,
)

import dp304_privacy_case_canary as canary  # noqa: E402


class PrivateFieldNameBoundaryTests(unittest.TestCase):
    """A private-named field stays private even when a caller mislabels it."""

    def test_private_named_fields_are_prohibited_even_when_mislabelled(self) -> None:
        for field in ("raw_transcript", "transcript_body", "reviewer_note",
                      "asr_text", "ocr_text", "raw_text", "evidence_excerpt"):
            with self.subTest(field=field):
                decision = decide_projection(
                    ProjectionInput(
                        field_name=field,
                        data_class=DataClass.PUBLIC_CORE,
                        relevance_reason="PUBLIC_ROLE",
                        explicitly_approved=True,
                        is_published_version=True,
                    )
                )
                self.assertFalse(
                    decision.allowed,
                    f"private field name {field!r} was published as {decision.decision.value}",
                )

    def test_case_selection_publishes_only_the_allowlisted_fields(self) -> None:
        published = []
        for field, data_class, reason, approved, _ in CASE_FIELDS:
            decision = decide_projection(
                ProjectionInput(
                    field_name=field,
                    data_class=data_class,
                    relevance_reason=reason,
                    explicitly_approved=approved,
                    is_published_version=True,
                )
            )
            if decision.allowed:
                published.append(field)
        self.assertEqual(
            published,
            ["finding_id", "person_name", "public_role_interval", "source_url",
             "normalized_claim"],
        )

    def test_public_figure_status_alone_is_not_relevance(self) -> None:
        decision = decide_projection(
            ProjectionInput(
                field_name="person_name",
                data_class=DataClass.PUBLIC_CORE,
                relevance_reason="IS_PUBLIC_FIGURE",
                is_published_version=True,
            )
        )
        self.assertFalse(decision.allowed)


class ReleaseLeakScanTests(unittest.TestCase):
    def test_leak_scan_rejects_a_sentinel_in_the_written_release(self) -> None:
        row = case_row()

        class Source:
            def projectable_findings(self):
                return [row]

        with tempfile.TemporaryDirectory(prefix="dp304-leak-") as temp:
            out = Path(temp) / "release"
            payload = build_public_projection(Source(), generated_at=canary.GENERATED_AT)
            self.assertEqual(payload["dossier_count"], 1)
            write_public_bundle(out, payload)
            self.assertEqual(canary.scan_release(out)["files"] != {}, True)
            (out / "claims").mkdir(exist_ok=True)
            (out / "claims" / "leak.txt").write_text(
                SENTINELS["raw_transcript"], encoding="utf-8"
            )
            with self.assertRaises(RuntimeError) as raised:
                canary.scan_release(out)
            self.assertIn("PRIVATE_SENTINEL_PUBLISHED", str(raised.exception))


class CaseCanaryTests(unittest.TestCase):
    def test_canary_runs_selection_rights_and_revocation(self) -> None:
        try:
            receipt = canary.run_canary()
        except RuntimeError as error:
            if "POSTGRES_UNAVAILABLE" in str(error):
                self.skipTest(str(error))
            raise
        self.assertEqual(receipt["publication"]["dossier_count"], 1)
        self.assertTrue(receipt["publication"]["private_sentinels_absent"])
        self.assertEqual(receipt["rights"]["outcome"], "REVIEWED_PUBLIC_HOLD")
        self.assertEqual(receipt["rights"]["event_count"], 2)
        self.assertTrue(receipt["rights"]["append_only_rejected"])
        self.assertEqual(receipt["revocation"]["dossier_count_after_revocation"], 0)
        self.assertEqual(receipt["revocation"]["stale_binding_dossier_count"], 0)
        self.assertFalse(receipt["access"]["audit_contains_body"])


if __name__ == "__main__":
    unittest.main()
