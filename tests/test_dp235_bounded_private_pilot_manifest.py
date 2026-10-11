import unittest
from dataclasses import replace

from dichiarazioni_pubbliche.bounded_private_pilot_manifest_v1 import (
    PrivatePilotSample,
    freeze_private_pilot_manifest,
    validate_private_pilot_manifest,
)


HASH_A = "a" * 64
HASH_B = "b" * 64


class TestDP235(unittest.TestCase):
    def sample(self, n="a", **updates):
        fields = dict(
            sample_id=n,
            content_id="content-" + n,
            source_family="official-parliament",
            language="it",
            medium="written",
            rights_reference="rights:receipt-" + n,
            capture_permission="APPROVED_EXTERNAL_REQUIRED",
            source_locator="https://www.example.org/source/" + n,
            source_version="revision-1",
            source_version_sha256=HASH_A if n == "a" else HASH_B,
            person_id="person-" + n,
            attribution_role="AUTHOR",
            media_type="text/html",
            rights_source_family="official-parliament",
            rights_content_id="content-" + n,
            rights_version_sha256=HASH_A if n == "a" else HASH_B,
            rights_source_locator="https://www.example.org/source/" + n,
        )
        fields.update(updates)
        return PrivatePilotSample(**fields)

    def test_freeze_is_deterministic_bounded_and_never_authorizes(self):
        first = freeze_private_pilot_manifest([self.sample("b"), self.sample("a")])
        second = freeze_private_pilot_manifest([self.sample("a"), self.sample("b")])
        self.assertEqual(first, second)
        self.assertEqual([s.sample_id for s in first.samples], ["a", "b"])
        self.assertEqual(first.review_status, "PROPOSED")
        self.assertEqual(first.hold_reasons, ())
        self.assertFalse(first.dispatch_authorized)
        self.assertEqual(first.estimated_cost_eur_cents, 0)
        validate_private_pilot_manifest(first)

    def test_legacy_seven_field_sample_is_constructible_but_not_freezable(self):
        # Previous prototype incorrectly accepted this insufficient descriptor.
        legacy = PrivatePilotSample(
            "a",
            "content-a",
            "source",
            "it",
            "written",
            "rights-ref",
            "APPROVED_EXTERNAL_REQUIRED",
        )
        with self.assertRaises(ValueError):
            freeze_private_pilot_manifest([legacy])

    def test_missing_rights_and_unknown_attribution_are_held_not_approved(self):
        unresolved = self.sample(
            "a",
            rights_reference=None,
            rights_source_family=None,
            rights_content_id=None,
            rights_version_sha256=None,
            rights_source_locator=None,
            person_id=None,
            attribution_role="UNKNOWN",
        )
        m = freeze_private_pilot_manifest([unresolved])
        self.assertEqual(m.review_status, "HELD")
        self.assertEqual(
            m.hold_reasons,
            (
                "a:PILOT_ATTRIBUTION_UNRESOLVED",
                "a:PILOT_RIGHTS_REFERENCE_MISSING",
            ),
        )
        validate_private_pilot_manifest(m)

    def test_reported_attribution_stays_held_even_with_rights_pointer(self):
        m = freeze_private_pilot_manifest([self.sample(attribution_role="REPORTED")])
        self.assertEqual(m.review_status, "HELD")
        self.assertIn("a:PILOT_ATTRIBUTION_UNRESOLVED", m.hold_reasons)

    def test_rights_reference_requires_matching_subject_scope(self):
        for override in (
            {"rights_source_family": None},
            {"rights_content_id": "another-content"},
            {"rights_version_sha256": HASH_B},
            {"rights_source_locator": "https://www.example.org/unrelated"},
            {"rights_reference": "APPROVED"},
            {"rights_reference": None},
        ):
            with self.subTest(override=override):
                bad = self.sample(**override)
                with self.assertRaisesRegex(ValueError, "PILOT_RIGHTS_SCOPE"):
                    freeze_private_pilot_manifest([bad])

    def test_non_approved_permission_marker_is_not_accepted(self):
        with self.assertRaisesRegex(ValueError, "PILOT_NEVER_INVENTS_PERMISSION"):
            self.sample(capture_permission="CLEARED")

    def test_missing_or_invalid_source_version_locator_hash_rejected(self):
        bad_cases = (
            {"source_locator": "http://www.example.org/item"},
            {"source_locator": "https://www.example.org/item#mutable"},
            {"source_locator": "https://user:pass@example.org/item"},
            {"source_locator": "https://localhost/item"},
            {"source_locator": "https://www.example.org\\@another.example/item"},
            {"source_locator": "https://www.example.org/é"},
            {"source_version": " "},
            {"source_version_sha256": "a" * 63},
            {"source_version_sha256": "A" * 64},
            {"content_id": ""},
            {"source_family": "*"},
        )
        for override in bad_cases:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    freeze_private_pilot_manifest([self.sample(**override)])

    def test_person_role_format_language_matrix_rejected(self):
        bad_cases = (
            {"person_id": None},
            {"attribution_role": "VERIFIED"},
            {"attribution_role": "SPEAKER", "person_id": ""},
            {"medium": "video", "media_type": "text/plain"},
            {"medium": "audio", "media_type": "video/mp4"},
            {"medium": "written", "media_type": "image/jpeg"},
            {"medium": []},
            {"media_type": "application/x-unknown"},
            {"language": "unknown"},
            {"language": " "},
        )
        for override in bad_cases:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    freeze_private_pilot_manifest([self.sample(**override)])

    def test_media_original_speaker_is_only_a_proposal(self):
        clip = self.sample(
            medium="video",
            media_type="video/mp4",
            language="en",
            attribution_role="SPEAKER",
        )
        manifest = freeze_private_pilot_manifest([clip])
        self.assertEqual(manifest.review_status, "PROPOSED")
        self.assertFalse(manifest.dispatch_authorized)
        validate_private_pilot_manifest(manifest)

    def test_duplicate_ids_content_versions_and_bytes_rejected(self):
        original = self.sample()
        conflicts = (
            self.sample(),
            self.sample(
                "b",
                content_id=original.content_id,
                rights_content_id=original.content_id,
            ),
            self.sample(
                "b",
                source_locator=original.source_locator,
                rights_source_locator=original.source_locator,
            ),
            self.sample(
                "b", source_version_sha256=HASH_A, rights_version_sha256=HASH_A
            ),
        )
        for conflict in conflicts:
            with self.subTest(conflict=conflict):
                with self.assertRaisesRegex(ValueError, "PILOT_DUPLICATE"):
                    freeze_private_pilot_manifest([original, conflict])

    def test_bounded_sample_cap_and_source_families(self):
        with self.assertRaisesRegex(ValueError, "PILOT_SAMPLE_CAP"):
            freeze_private_pilot_manifest([self.sample()], max_samples=0)
        with self.assertRaisesRegex(ValueError, "PILOT_SAMPLE_CAP"):
            freeze_private_pilot_manifest([self.sample()], max_samples=9)
        with self.assertRaisesRegex(ValueError, "PILOT_SAMPLE_CAP"):
            freeze_private_pilot_manifest(
                [self.sample("a"), self.sample("b")], max_samples=1
            )
        families = [
            self.sample(
                str(i),
                source_family=f"official-{i}",
                rights_source_family=f"official-{i}",
                source_version_sha256=hex(i + 1)[2:].zfill(64),
                rights_version_sha256=hex(i + 1)[2:].zfill(64),
            )
            for i in range(5)
        ]
        with self.assertRaisesRegex(ValueError, "PILOT_SOURCE_FAMILY_CAP"):
            freeze_private_pilot_manifest(families)

    def test_declared_cost_budget_is_bounded_and_tamper_protected(self):
        funded = self.sample(estimated_cost_eur_cents=35)
        with self.assertRaisesRegex(ValueError, "PILOT_BUDGET_EXCEEDED"):
            freeze_private_pilot_manifest([funded], budget_eur_cents=34)
        with self.assertRaisesRegex(ValueError, "PILOT_BUDGET"):
            freeze_private_pilot_manifest([funded], budget_eur_cents=10001)
        with self.assertRaises(ValueError):
            freeze_private_pilot_manifest([self.sample(estimated_cost_eur_cents=True)])
        m = freeze_private_pilot_manifest([funded], budget_eur_cents=35)
        self.assertEqual(m.estimated_cost_eur_cents, 35)
        validate_private_pilot_manifest(m)
        for forged in (
            replace(m, budget_eur_cents=0),
            replace(m, estimated_cost_eur_cents=0),
            replace(m, max_samples=0),
        ):
            with self.subTest(forged=forged):
                with self.assertRaises(ValueError):
                    validate_private_pilot_manifest(forged)

    def test_tampering_or_forged_manifest_invariants_fail_validation(self):
        m = freeze_private_pilot_manifest([self.sample()])
        bad_forms = (
            replace(m, manifest_sha256="bad"),
            replace(m, dispatch_authorized=True),
            replace(m, review_status="APPROVED"),
            replace(m, review_status="HELD"),
            replace(m, hold_reasons=("a:FAKE",)),
            replace(m, samples=(replace(self.sample(), language="de"),)),
            replace(m, samples=(self.sample(), self.sample())),
            replace(m, samples=[self.sample()]),
            replace(m, samples=(object(),)),
        )
        for forged in bad_forms:
            with self.subTest(forged=forged):
                with self.assertRaises(ValueError):
                    validate_private_pilot_manifest(forged)
        with self.assertRaises(ValueError):
            validate_private_pilot_manifest(object())


if __name__ == "__main__":
    unittest.main()
