"""DP-243 purely synthetic historical manifest negatives; no historical evidence asserted."""

import sys
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.historical_corpus_preflight_v1 import (  # noqa: E402
    HistoricalEntry,
    HistoricalManifest,
    preflight_historical_corpus,
)
from dichiarazioni_pubbliche.original_source_resolver import (
    ExactSourceLocatorResolution,
)  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PRIVATE_RIGHTS_RECORD_VERSION,
    PrivateRightsRecord,
    RightsSubject,
    rights_subject_fingerprint,
)

NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)
EVENT = datetime(1934, 1, 2, tzinfo=timezone.utc)
A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64
USES = (
    "DISCOVER_METADATA",
    "FETCH",
    "STORE_BODY",
    "PARSE_TEXT",
    "TRANSLATE",
    "ARCHIVE",
)


def entry(
    *,
    subject="MUSSOLINI",
    content_id="source:synthetic:it",
    sha=A,
    kind="PRIMARY_ORIGINAL",
    language="it",
    origin_content_id=None,
    origin_sha256=None,
    role="AUTHOR",
    uses=USES,
    rights=True,
    collection_id="collection:it",
    **changes,
):
    url = f"https://example.invalid/{content_id}"
    source_family = "SYNTHETIC_TEST_FAMILY"
    rights_subject = RightsSubject(source_family, "URL", url, content_id=content_id)
    record = (
        PrivateRightsRecord(
            id=f"rights:{content_id}:{sha[:4]}",
            subject_fingerprint=rights_subject_fingerprint(rights_subject),
            source_family=source_family,
            locator_kind="URL",
            locator_value=url,
            content_id=content_id,
            evidence_id=None,
            transcript_segment_id=None,
            canonical_segment_id=None,
            passage_id=None,
            rights_status="CLEARED",
            rights_receipt_ref="synthetic:untrusted:receipt",
            permitted_uses=tuple(uses),
            attribution_requirements=(),
            reviewed_at="2026-10-10T00:00:00+00:00",
            expires_at="2026-10-12T00:00:00+00:00",
            reviewer_ref="synthetic:untrusted:reviewer",
            policy_version="synthetic:rights-v1",
            record_visibility="PRIVATE",
            supersedes_id=None,
            version_state="CURRENT",
            record_version=PRIVATE_RIGHTS_RECORD_VERSION,
        )
        if rights
        else None
    )
    locator = ExactSourceLocatorResolution(
        "LOCATED",
        (),
        content_id,
        f"passage:{content_id}",
        "TEXT_POSITION",
        sha,
        D,
    )
    return replace(
        HistoricalEntry(
            entry_id=f"entry:{content_id}:{sha[:4]}",
            subject=subject,
            collection_id=collection_id,
            content_id=content_id,
            source_family=source_family,
            locator_url=url,
            source_kind=kind,
            original_language=language,
            media_type="text/plain",
            source_version_sha256=sha,
            selector_fingerprint=D,
            observed_at=NOW,
            event_at=EVENT,
            event_timezone="Europe/Rome",
            attribution_role=role,
            role_review_ref="synthetic:role:untrusted",
            origin_content_id=origin_content_id,
            origin_sha256=origin_sha256,
            rights_subject=rights_subject,
            rights_record=record,
            rights_record_id=record.id if record else "rights:missing",
            rights_policy_version="synthetic:rights-v1",
            exact_locator=locator,
        ),
        **changes,
    )


def manifest(subject, entries, *, collection_id=None, **changes):
    collection_id = collection_id or (
        "collection:it" if subject == "MUSSOLINI" else "collection:de"
    )
    return replace(
        HistoricalManifest(
            subject=subject,
            person_id=f"synthetic:person:{subject}",
            collection_id=collection_id,
            coverage_start=datetime(1930, 1, 1, tzinfo=timezone.utc),
            coverage_horizon=NOW,
            coverage_scope_ref="synthetic:scope:untrusted",
            entries=tuple(entries),
        ),
        **changes,
    )


def two(it=None, de=None):
    it = it or entry()
    de = de or entry(
        subject="HITLER",
        content_id="source:synthetic:de",
        sha=B,
        language="de",
        collection_id="collection:de",
    )
    return (manifest("MUSSOLINI", (it,)), manifest("HITLER", (de,)))


class HistoricalPreflightTests(unittest.TestCase):
    def test_corpus_is_private_review_only_without_dispatch_or_public_authority(self):
        decision = preflight_historical_corpus(two(), now=NOW)
        self.assertEqual(len(decision.rows), 2)
        self.assertTrue(
            all(row.state == "PRIVATE_REVIEW_ONLY" for row in decision.rows)
        )
        self.assertFalse(decision.dispatch_authorized)
        self.assertFalse(decision.public_eligible)
        self.assertEqual(decision.coverage_state, "SCOPED_UNVERIFIED")
        self.assertEqual(
            decision, preflight_historical_corpus(tuple(reversed(two())), now=NOW)
        )

    def test_required_two_distinct_persons_and_language_scope(self):
        with self.assertRaisesRegex(ValueError, "TWO_SUBJECTS"):
            preflight_historical_corpus((two()[0],), now=NOW)
        with self.assertRaisesRegex(ValueError, "LANGUAGE"):
            preflight_historical_corpus(
                two(
                    de=entry(
                        subject="HITLER",
                        language="it",
                        content_id="source:synthetic:de",
                        collection_id="collection:de",
                    )
                ),
                now=NOW,
            )
        with self.assertRaisesRegex(ValueError, "PERSON"):
            preflight_historical_corpus(
                (two()[0], replace(two()[1], person_id=two()[0].person_id)), now=NOW
            )

    def test_discovery_only_never_becomes_body_permission(self):
        it = entry(uses=("DISCOVER_METADATA",))
        decision = preflight_historical_corpus(two(it=it), now=NOW)
        row = next(row for row in decision.rows if row.entry_id == it.entry_id)
        self.assertEqual(row.state, "HELD")
        self.assertIn("SOURCE_USE_NOT_PERMITTED", row.holds)

    def test_unknown_expired_revoked_and_rights_subject_mismatch_hold(self):
        base = entry()
        versions = (
            replace(base, rights_record=None),
            replace(
                base, rights_record=replace(base.rights_record, rights_status="REVOKED")
            ),
            replace(
                base,
                rights_record=replace(
                    base.rights_record, expires_at="2026-10-10T00:00:00+00:00"
                ),
            ),
            replace(
                base,
                rights_subject=replace(
                    base.rights_subject, locator_value="https://example.invalid/other"
                ),
            ),
        )
        for variant in versions:
            with self.subTest(variant=variant):
                decision = preflight_historical_corpus(two(it=variant), now=NOW)
                self.assertEqual(
                    next(r for r in decision.rows if r.entry_id == base.entry_id).state,
                    "HELD",
                )

    def test_reported_speech_actor_and_narrator_cannot_be_original_speaker(self):
        for role in ("NARRATOR", "ACTOR", "REPORTED", "UNKNOWN"):
            with self.subTest(role=role):
                row = preflight_historical_corpus(
                    two(it=entry(attribution_role=role)), now=NOW
                ).rows[0]
                self.assertEqual(row.state, "HELD")
                self.assertIn("SPEECH_ACT_UNVERIFIED", row.holds)

    def test_wrong_source_version_or_missing_exact_locator_is_held(self):
        for changes in (
            {"exact_locator": None},
            {"exact_locator": replace(entry().exact_locator, source_version_sha256=B)},
            {"exact_locator": replace(entry().exact_locator, status="STALE")},
        ):
            decision = preflight_historical_corpus(two(it=entry(**changes)), now=NOW)
            self.assertEqual(decision.rows[0].state, "HELD")
            self.assertIn("EXACT_SOURCE_UNVERIFIED", decision.rows[0].holds)

    def test_repost_retains_independent_provenance_and_never_becomes_original(self):
        parent = entry()
        copy = entry(
            content_id="source:synthetic:copy",
            sha=C,
            kind="ARCHIVE_COPY",
            origin_content_id=parent.content_id,
            origin_sha256=A,
            attribution_role="REPORTED",
            collection_id="collection:it",
        )
        ms = (manifest("MUSSOLINI", (parent, copy)), two()[1])
        result = preflight_historical_corpus(ms, now=NOW)
        row = next(row for row in result.rows if row.content_id == copy.content_id)
        self.assertEqual(row.state, "HELD")
        self.assertIn("SPEECH_ACT_UNVERIFIED", row.holds)
        self.assertEqual(row.root_content_id, parent.content_id)
        self.assertEqual(len(result.logical_content_ids), 3)

    def test_copy_missing_or_wrong_original_fingerprint_fails_closed(self):
        base = entry(
            content_id="source:synthetic:copy",
            sha=C,
            kind="ARCHIVE_COPY",
            origin_content_id="source:synthetic:it",
            origin_sha256=A,
        )
        for variant in (
            replace(base, origin_sha256=B),
            replace(base, origin_content_id="source:missing"),
            replace(base, origin_content_id=base.content_id),
        ):
            result = preflight_historical_corpus(
                (manifest("MUSSOLINI", (entry(), variant)), two()[1]), now=NOW
            )
            row = next(row for row in result.rows if row.content_id == base.content_id)
            self.assertEqual(row.state, "HELD")
            self.assertIn("ORIGIN_UNVERIFIED", row.holds)

    def test_german_translation_has_distinct_hash_and_parent_translation_rights(self):
        parent = two()[1].entries[0]
        translated = entry(
            subject="HITLER",
            content_id="source:synthetic:translation",
            sha=C,
            kind="EDITORIAL_TRANSLATION",
            language="it",
            origin_content_id=parent.content_id,
            origin_sha256=B,
            collection_id="collection:de",
            edition_method="HUMAN_TRANSLATION",
            edition_date=NOW,
        )
        manifests = (two()[0], manifest("HITLER", (parent, translated)))
        decision = preflight_historical_corpus(manifests, now=NOW)
        self.assertEqual(
            next(r for r in decision.rows if r.entry_id == translated.entry_id).state,
            "PRIVATE_REVIEW_ONLY",
        )
        no_translation = replace(
            parent,
            rights_record=replace(
                parent.rights_record,
                permitted_uses=(
                    "FETCH",
                    "STORE_BODY",
                    "PARSE_TEXT",
                ),
            ),
        )
        decision = preflight_historical_corpus(
            (two()[0], manifest("HITLER", (no_translation, translated))), now=NOW
        )
        row = next(r for r in decision.rows if r.entry_id == translated.entry_id)
        self.assertIn("PARENT_TRANSLATION_RIGHTS_UNVERIFIED", row.holds)
        self.assertEqual(row.state, "HELD")

    def test_shared_content_dedupes_membership_without_cross_person_attribution(self):
        src = entry()
        src = replace(src, additional_collection_ids=("collection:alternate",))
        duplicate = replace(src, additional_collection_ids=("collection:alternate",))
        manifests = (
            manifest("MUSSOLINI", (src,)),
            manifest("HITLER", (two()[1].entries[0],)),
        )
        result = preflight_historical_corpus(
            (replace(manifests[0], entries=(src, duplicate)), manifests[1]), now=NOW
        )
        self.assertEqual(len(result.logical_content_ids), 2)
        self.assertEqual(
            result.rows[0].collections, ("collection:alternate", "collection:it")
        )
        other = replace(src, additional_collection_ids=("collection:another",))
        left = (manifest("MUSSOLINI", (src, other)), two()[1])
        right = (manifest("MUSSOLINI", (other, src)), two()[1])
        a = preflight_historical_corpus(left, now=NOW)
        b = preflight_historical_corpus(right, now=NOW)
        self.assertEqual(
            a.rows[0].collections,
            ("collection:alternate", "collection:another", "collection:it"),
        )
        self.assertEqual(a.manifest_fingerprint, b.manifest_fingerprint)
        # Explicitly separate manifests of the same person is never a way to bypass caps.
        with self.assertRaisesRegex(ValueError, "TWO_SUBJECTS"):
            preflight_historical_corpus(
                (manifests[0], replace(manifests[0], collection_id="other")), now=NOW
            )

    def test_changed_capture_requires_explicit_supersession_and_fresh_review(self):
        original = entry(observed_at=NOW - timedelta(days=1))
        update = entry(sha=C)
        for variant in (update, replace(update, supersedes_sha256=B)):
            with self.subTest(variant=variant):
                decision = preflight_historical_corpus(
                    two(it=variant), now=NOW, previous=(original,)
                )
                self.assertIn("REVISION_UNVERIFIED", decision.rows[0].holds)
        next_record = replace(update, supersedes_sha256=A)
        decision = preflight_historical_corpus(
            two(it=next_record), now=NOW, previous=(original,)
        )
        self.assertEqual(decision.rows[0].state, "HELD")
        self.assertIn("REVISION_REVALIDATION_REQUIRED", decision.rows[0].holds)
        self.assertEqual(decision.revalidation_content_ids, (original.content_id,))

    def test_mass_input_future_horizon_duplicate_conflict_denied(self):
        all_it = tuple(entry(content_id=f"synthetic:{i}", sha=A) for i in range(9))
        with self.assertRaisesRegex(ValueError, "ITEM_CAP"):
            preflight_historical_corpus(
                (manifest("MUSSOLINI", all_it), two()[1]), now=NOW
            )
        with self.assertRaisesRegex(ValueError, "HORIZON"):
            preflight_historical_corpus(
                (
                    replace(
                        two()[0],
                        coverage_horizon=datetime(2027, 1, 1, tzinfo=timezone.utc),
                    ),
                    two()[1],
                ),
                now=NOW,
            )
        with self.assertRaisesRegex(ValueError, "CONTENT_CONFLICT"):
            preflight_historical_corpus(
                (manifest("MUSSOLINI", (entry(), entry(sha=C))), two()[1]), now=NOW
            )

    def test_fingerprint_changes_for_edition_metadata_and_rights_receipt(self):
        original = two()[1].entries[0]
        translated = entry(
            subject="HITLER",
            content_id="synthetic:translation",
            sha=C,
            kind="EDITORIAL_TRANSLATION",
            language="it",
            collection_id="collection:de",
            origin_content_id=original.content_id,
            origin_sha256=B,
            edition_method="HUMAN_TRANSLATION",
            edition_date=NOW,
        )
        before = preflight_historical_corpus(
            (two()[0], manifest("HITLER", (original, translated))), now=NOW
        )
        other_edition = replace(translated, edition_method="OCR_REVIEWED_TRANSLATION")
        after = preflight_historical_corpus(
            (two()[0], manifest("HITLER", (original, other_edition))), now=NOW
        )
        self.assertNotEqual(before.manifest_fingerprint, after.manifest_fingerprint)
        changed_receipt = replace(
            translated,
            rights_record=replace(
                translated.rights_record, rights_receipt_ref="synthetic:second"
            ),
        )
        after_rights = preflight_historical_corpus(
            (two()[0], manifest("HITLER", (original, changed_receipt))), now=NOW
        )
        self.assertNotEqual(
            before.manifest_fingerprint, after_rights.manifest_fingerprint
        )

    def test_unobserved_initial_primary_is_explicit_gap(self):
        result = preflight_historical_corpus(
            (manifest("MUSSOLINI", ()), manifest("HITLER", ())), now=NOW
        )
        self.assertEqual(result.missing_primary_subjects, ("MUSSOLINI", "HITLER"))
        self.assertFalse(result.dispatch_authorized)
        self.assertFalse(result.public_eligible)

    def test_secondary_scholarship_not_original_or_primary_attribution(self):
        academic = entry(source_kind="SECONDARY_SCHOLARSHIP", attribution_role="AUTHOR")
        result = preflight_historical_corpus(two(it=academic), now=NOW)
        self.assertIsNone(result.rows[0].root_content_id)
        self.assertEqual(result.rows[0].state, "PRIVATE_REVIEW_ONLY")
        self.assertEqual(result.missing_primary_subjects, ("MUSSOLINI",))

    def test_identical_archived_bytes_still_need_independent_source_lineage(self):
        original = entry()
        copy = entry(
            content_id="synthetic:archived-copy",
            kind="ARCHIVE_COPY",
            origin_content_id=original.content_id,
            origin_sha256=A,
            attribution_role="NARRATOR",
        )
        result = preflight_historical_corpus(
            (manifest("MUSSOLINI", (original, copy)), two()[1]), now=NOW
        )
        mirror = next(row for row in result.rows if row.content_id == copy.content_id)
        self.assertNotIn("ORIGIN_UNVERIFIED", mirror.holds)
        self.assertIn("SPEECH_ACT_UNVERIFIED", mirror.holds)
        self.assertEqual(mirror.root_content_id, original.content_id)

    def test_audio_requires_distinct_media_use_and_https(self):
        it = entry(media_type="video/mp4", uses=("FETCH", "STORE_BODY", "PARSE_TEXT"))
        result = preflight_historical_corpus(two(it=it), now=NOW)
        self.assertIn("SOURCE_USE_NOT_PERMITTED", result.rows[0].holds)
        with self.assertRaisesRegex(ValueError, "SOURCE_URL"):
            preflight_historical_corpus(
                two(it=entry(locator_url="http://example.invalid/item")), now=NOW
            )
        with self.assertRaisesRegex(ValueError, "SOURCE_URL"):
            preflight_historical_corpus(
                two(it=entry(locator_url="https://user:pass@example.invalid/item")),
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main()
