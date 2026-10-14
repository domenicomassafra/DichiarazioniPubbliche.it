"""DP440 private multi-synopsis cohort reconciliation on real public fixtures."""

from __future__ import annotations

import copy
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / "poc"),
    str(Path(__file__).resolve().parent),
]

from dichiarazioni_pubbliche.private_synopsis_refresh_cohort_v1 import (  # noqa: E402
    CohortRead,
    CohortRelease,
    plan_synopsis_refresh_cohort,
    pinned_release_digest,
    pinned_membership_digest,
)
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    projection_dataset_sha256,
    validate_public_bundle,
)
from dichiarazioni_pubbliche.public_synopsis_refresh_plan_v1 import (  # noqa: E402
    synopsis_read_sha256,
)
from test_dp440_public_synopsis import (  # noqa: E402
    bundle,
    intersection,
    prepare,
    sentence,
)

NOW = datetime(2026, 10, 11, 16, tzinfo=timezone.utc)
OPAQUE_SECRET = b"owner-independent-private-key-32bytes!"
ONE = ("person:1", "topic:official-test")
TWO = ("person:2", "topic:second-test")
THREE = ("person:1", "topic:second-test")


def two_person_bundle():
    value = bundle()
    first = copy.deepcopy(value["statements"][0])
    second = copy.deepcopy(first)
    for row, num, source_hash in ((first, 3, "b"), (second, 4, "c")):
        row.update(
            {
                "person_id": "person:2",
                "statement_id": f"statement:{num}",
                "version_id": f"statement-version:{num}",
                "content_id": f"content:{num}",
                "source_url": f"https://example.test/source-{num}",
                "source_version": f"source-version:{num}",
                "source_sha256": source_hash * 64,
                "review_provenance": {
                    name: f"review:{name}:{num}" for name in row["review_provenance"]
                },
            }
        )
    value["statements"].extend((first, second))
    value["dataset_sha256"] = projection_dataset_sha256(value)
    return value


def three_source_shared_lineage_fixture():
    """Three real public v3 Statements, two in one reviewed source lineage.

    The canonical synopsis contract needs two *independent* lineages, not
    three distinct labels. No statement/version identity is duplicated.
    """
    value = bundle()
    third = copy.deepcopy(value["statements"][0])
    third.update(
        {
            "statement_id": "statement:third",
            "version_id": "statement-version:third",
            "content_id": "content:third",
            "source_url": "https://example.test/third",
            "source_title": "Terza fonte sintetica",
            "source_version": "source-version:third",
            "source_sha256": "b" * 64,
            "statement_date": "2026-10-09",
            "review_provenance": {
                name: f"review:{name}:third" for name in third["review_provenance"]
            },
        }
    )
    value["statements"].append(third)
    value["dataset_sha256"] = projection_dataset_sha256(value)
    validate_public_bundle(value, allow_statement_v3=True)
    pairs = tuple(
        (row["statement_id"], row["version_id"]) for row in value["statements"]
    )
    proof = intersection(
        value,
        statement_versions=pairs,
        statement_lineages=(
            (*pairs[0], "reviewed:shared-original"),
            (*pairs[1], "reviewed:shared-original"),
            (*pairs[2], "reviewed:independent-original"),
        ),
    )
    reviewed = prepare(
        value,
        proof=proof,
        sentences=tuple(
            sentence(value, index, review_event_id=f"review:approved:{index}")
            for index in range(3)
        ),
    )
    assert reviewed.status == "READY_READ_MODEL", reviewed.reason_code
    return value, proof, reviewed


def membership(value, key):
    eligible = [row for row in value["statements"] if row["person_id"] == key[0]]
    return intersection(
        value,
        person_id=key[0],
        topic_id=key[1],
        statement_versions=tuple(
            (row["statement_id"], row["version_id"]) for row in eligible
        ),
        statement_lineages=tuple(
            (row["statement_id"], row["version_id"], f"independent:lineage:{idx}")
            for idx, row in enumerate(eligible)
        ),
    )


def make_read(value, key, proof):
    eligible = [
        idx for idx, row in enumerate(value["statements"]) if row["person_id"] == key[0]
    ]
    return prepare(
        value,
        proof=proof,
        sentences=tuple(
            sentence(value, index, review_event_id=f"review:cohort:{index}")
            for index in eligible
        ),
    )


def release(value=None, keys=(ONE, TWO), epoch=10, withheld=()):
    value = two_person_bundle() if value is None else value
    proofs = {key: membership(value, key) for key in keys}
    reads = {
        key: CohortRead(
            read=make_read(value, key, proof),
            issuer_epoch=epoch,
        )
        for key, proof in proofs.items()
    }
    for key in withheld:
        reads[key] = replace(
            reads[key],
            read=replace(
                reads[key].read,
                status="WITHHELD",
                reason_code="SYNOPSIS_STALE_OR_UNAPPROVED_SNAPSHOT",
                fingerprint=None,
                coverage_note=None,
                snapshot_at=None,
                sentences=(),
            ),
        )
    return CohortRelease(
        issuer_ref="issuer:owned:private",
        issuer_epoch=epoch,
        public_bundle=value,
        reads=reads,
        memberships=proofs,
    )


def pins(value):
    return {
        "release": pinned_release_digest(value),
        "reads": {
            key: synopsis_read_sha256(envelope.read)
            for key, envelope in value.reads.items()
        },
        "memberships": {
            key: pinned_membership_digest(proof)
            for key, proof in value.memberships.items()
        },
    }


class SynopsisCohortTests(unittest.TestCase):
    def run_plan(self, previous=None, current=None, **overrides):
        previous = release(epoch=10) if previous is None else previous
        current = (
            release(copy.deepcopy(previous.public_bundle), epoch=11)
            if current is None
            else current
        )
        older, newer = pins(previous), pins(current)
        args = {
            "previous": previous,
            "current": current,
            "expected_previous_release_sha256": older["release"],
            "expected_current_release_sha256": newer["release"],
            "expected_previous_read_sha256": older["reads"],
            "expected_current_read_sha256": newer["reads"],
            "expected_previous_membership_sha256": older["memberships"],
            "expected_current_membership_sha256": newer["memberships"],
            "opaque_key": OPAQUE_SECRET,
            "now": NOW,
        }
        args.update(overrides)
        return plan_synopsis_refresh_cohort(**args)

    def test_real_two_person_two_topic_cohort_repeat_no_automatic_authority(self):
        old = release()
        current = release(copy.deepcopy(old.public_bundle), epoch=11)
        first = self.run_plan(old, current)
        self.assertEqual(first.status, "IDLE_NO_AUTHORITY")
        self.assertEqual(first.items, ())
        self.assertEqual(first, self.run_plan(old, current))
        self.assertEqual(first.review_item_count, 0)
        self.assertIsNone(first.verdict)
        self.assertFalse(first.publication_authority)
        self.assertFalse(first.source_rights_authority)
        self.assertFalse(first.semantic_entailment_verified)
        self.assertTrue(first.private_only)
        self.assertEqual(first.provider_calls, 0)
        self.assertEqual(first.source_body_count, 0)

    def test_canonical_three_source_shared_lineage_labels_are_not_duplicate_keys(self):
        # Reviewer11 false-deny: same externally reviewed source lineage
        # can support distinct Statement/version keys; only duplicate keys
        # and missing one-to-one coverage are malformed.
        public, proof, canonical = three_source_shared_lineage_fixture()
        self.assertEqual(canonical.status, "READY_READ_MODEL")
        self.assertEqual(len(proof.statement_versions), 3)
        self.assertEqual(len({row[2] for row in proof.statement_lineages}), 2)
        before = release(copy.deepcopy(public), keys=(ONE,), epoch=10)
        after = release(copy.deepcopy(public), keys=(ONE,), epoch=11)
        for issued in (before, after):
            issued.memberships[ONE] = proof
            issued.reads[ONE] = replace(
                issued.reads[ONE], read=copy.deepcopy(canonical)
            )
        result = self.run_plan(before, after)
        self.assertEqual(result.status, "IDLE_NO_AUTHORITY")
        self.assertEqual(result.review_item_count, 0)
        self.assertEqual(result.items, ())
        self.assertFalse(result.publication_authority)
        self.assertFalse(result.source_rights_authority)

    def test_simultaneous_added_retired_changed_and_held_opaque_items(self):
        old = release(keys=(ONE, TWO), epoch=10)
        value = copy.deepcopy(old.public_bundle)
        value["statements"][0]["source_sha256"] = "d" * 64
        value["statements"][0]["review_provenance"]["rights"] = (
            "review:rights:withdrawn"
        )
        value["dataset_sha256"] = projection_dataset_sha256(value)
        current = release(value, keys=(ONE, THREE), epoch=11, withheld=(THREE,))
        result = self.run_plan(old, current)
        self.assertEqual(result.status, "MANUAL_RECHECK_REQUIRED")
        self.assertEqual(
            {i.transition for i in result.items}, {"CHANGED", "RETIRED", "HELD"}
        )
        self.assertTrue(all(i.manual_only for i in result.items))
        self.assertTrue(all(len(i.opaque_ref) == 64 for i in result.items))
        self.assertEqual(
            tuple(i.opaque_ref for i in result.items),
            tuple(sorted(i.opaque_ref for i in result.items)),
        )
        self.assertIn(
            "CITED_SOURCE_MATERIAL_CHANGED",
            {reason for i in result.items for reason in i.reason_codes},
        )
        self.assertIn(
            "SOURCE_RIGHTS_EXTERNAL_REVIEW_REQUIRED",
            {action for i in result.items for action in i.manual_actions},
        )
        self.assertNotIn("original_text", repr(result))
        self.assertNotIn("https://", repr(result))
        for identifier in ("person:1", "person:2", "statement:1", "topic:second-test"):
            self.assertNotIn(identifier, repr(result))

    def test_addition_is_manual_even_when_new_read_is_approved_shaped(self):
        a = release(keys=(ONE,), epoch=10)
        b = release(copy.deepcopy(a.public_bundle), keys=(ONE, TWO), epoch=11)
        result = self.run_plan(a, b)
        self.assertEqual([i.transition for i in result.items], ["ADDED"])
        self.assertIn("NEW_SYNOPSIS_REVIEW_REQUIRED", result.items[0].manual_actions)
        self.assertFalse(result.items[0].source_rights_authority)

    def test_expired_topic_membership_and_revocation_withhold(self):
        old = release(epoch=10)
        current = release(copy.deepcopy(old.public_bundle), epoch=11)
        current.memberships[ONE] = replace(current.memberships[ONE], status="REVOKED")
        plan = self.run_plan(old, current)
        self.assertEqual([i.transition for i in plan.items], ["HELD"])
        self.assertIn("TOPIC_MEMBERSHIP_NOT_CURRENT", plan.items[0].reason_codes)
        expired = release(copy.deepcopy(old.public_bundle), epoch=11)
        expired.memberships[TWO] = replace(
            expired.memberships[TWO],
            currentness_valid_until="2026-10-11T15:00:00+00:00",
        )
        self.assertIn("HELD", [i.transition for i in self.run_plan(old, expired).items])

    def test_new_ready_read_outside_current_topic_membership_is_held(self):
        previous = release(epoch=10)
        current = release(copy.deepcopy(previous.public_bundle), epoch=11)
        proof = current.memberships[ONE]
        # Real READY read still cites two Statements; a reduced externally
        # reviewed current intersection cannot silently keep either one.
        current.memberships[ONE] = replace(
            proof,
            statement_versions=proof.statement_versions[1:],
            statement_lineages=proof.statement_lineages[1:],
        )
        result = self.run_plan(previous, current)
        self.assertEqual([item.transition for item in result.items], ["HELD"])
        self.assertIn(
            "CURRENT_READY_READ_DEPENDENCY_NOT_VALID", result.items[0].reason_codes
        )
        self.assertIn(
            "CITED_STATEMENT_REMOVED_OR_TOPIC_REVOKED", result.items[0].reason_codes
        )

    def test_changed_membership_review_receipt_requires_refresh_even_when_read_is_identical(
        self,
    ):
        previous = release(epoch=10)
        current = release(copy.deepcopy(previous.public_bundle), epoch=11)
        current.memberships[TWO] = replace(
            current.memberships[TWO], review_event_id="review:topic:reconsidered"
        )
        plan = self.run_plan(previous, current)
        self.assertEqual([item.transition for item in plan.items], ["CHANGED"])
        self.assertIn("TOPIC_REVIEW_RECEIPT_CHANGED", plan.items[0].reason_codes)

    def test_p2_malformed_current_membership_is_not_a_usable_review_proof(self):
        """Independently pinned current member cannot forge source lineage/attestation."""
        previous = release(epoch=10)
        current = release(copy.deepcopy(previous.public_bundle), epoch=11)
        proof = current.memberships[ONE]
        compromised = (
            replace(proof, statement_lineages=()),
            replace(proof, currentness_attestation_id=""),
            replace(proof, review_event_id=""),
            replace(
                proof,
                statement_lineages=(
                    proof.statement_lineages[0],
                    proof.statement_lineages[0],
                ),
            ),
        )
        for forged in compromised:
            with self.subTest(forged=forged):
                replica = copy.deepcopy(current)
                replica.memberships[ONE] = forged
                # Both release and individual membership pins are freshly
                # obtained, i.e. ordinary self-hashing cannot prove approval.
                with self.assertRaisesRegex(ValueError, "COHORT_MEMBERSHIP_INVALID"):
                    self.run_plan(previous, replica)
                # The same forged proof persisted unchanged over BOTH
                # releases previously yielded IDLE_NO_AUTHORITY / zero tasks.
                stale_previous = copy.deepcopy(previous)
                stale_previous.memberships[ONE] = replace(
                    forged,
                    dataset_sha256=stale_previous.public_bundle["dataset_sha256"],
                )
                with self.assertRaisesRegex(ValueError, "COHORT_MEMBERSHIP_INVALID"):
                    self.run_plan(stale_previous, replica)

    def test_p2_new_current_topic_membership_without_any_read_is_not_idle(self):
        """A new reviewed intersection with no read needs manual production/hold."""
        previous = release(keys=(ONE,), epoch=10)
        current = release(copy.deepcopy(previous.public_bundle), keys=(ONE,), epoch=11)
        current.memberships[TWO] = membership(current.public_bundle, TWO)
        # The second topic/person combination is not present in either
        # synopsis read inventory; it must never silently disappear.
        result = self.run_plan(previous, current)
        self.assertEqual(result.status, "MANUAL_RECHECK_REQUIRED")
        self.assertEqual(result.review_item_count, 1)
        self.assertEqual(result.items[0].transition, "HELD")
        self.assertIn("CURRENT_MEMBERSHIP_READ_MISSING", result.items[0].reason_codes)
        self.assertIn("NEW_SYNOPSIS_REVIEW_REQUIRED", result.items[0].manual_actions)
        self.assertEqual(len(result.items[0].opaque_ref), 64)
        for secret in ("person:2", "topic:second-test", "https://", "original_text"):
            self.assertNotIn(secret, repr(result))

    def test_canonical_sort_is_independent_of_mapping_insertion_order(self):
        old = release(epoch=10)
        current = release(
            copy.deepcopy(old.public_bundle), keys=(ONE, TWO, THREE), epoch=11
        )
        normal = self.run_plan(old, current)
        reversed_current = replace(
            current,
            reads=dict(reversed(tuple(current.reads.items()))),
            memberships=dict(reversed(tuple(current.memberships.items()))),
        )
        self.assertEqual(pins(current), pins(reversed_current))
        self.assertEqual(normal, self.run_plan(old, reversed_current))

    def test_stale_external_release_read_and_membership_pins_refuse(self):
        old = release(epoch=10)
        current = release(copy.deepcopy(old.public_bundle), epoch=11)
        oldpins, newpins = pins(old), pins(current)
        with self.assertRaisesRegex(ValueError, "COHORT_RELEASE_PIN_MISMATCH"):
            self.run_plan(old, current, expected_current_release_sha256="0" * 64)
        badreads = dict(newpins["reads"])
        badreads[ONE] = "0" * 64
        with self.assertRaisesRegex(ValueError, "COHORT_READ_PIN_MISMATCH"):
            self.run_plan(old, current, expected_current_read_sha256=badreads)
        badproofs = dict(oldpins["memberships"])
        badproofs[TWO] = "0" * 64
        with self.assertRaisesRegex(ValueError, "COHORT_MEMBERSHIP_PIN_MISMATCH"):
            self.run_plan(old, current, expected_previous_membership_sha256=badproofs)

    def test_replayed_issuer_or_old_read_in_new_release_refused(self):
        old = release(epoch=10)
        with self.assertRaisesRegex(ValueError, "COHORT_ISSUER_REPLAY"):
            self.run_plan(old, copy.deepcopy(old))
        current = release(copy.deepcopy(old.public_bundle), epoch=11)
        current.reads[ONE] = copy.deepcopy(old.reads[ONE])
        with self.assertRaisesRegex(ValueError, "COHORT_ISSUER_REPLAY"):
            self.run_plan(old, current)
        changed = release(copy.deepcopy(old.public_bundle), epoch=11)
        changed.public_bundle["generated_at"] = "2026-10-11T12:30:00+00:00"
        with self.assertRaisesRegex(ValueError, "COHORT_.*INVALID"):
            self.run_plan(old, changed)

    def test_deep_snapshot_survives_mutation_after_pin_and_refuses_subclasses(self):
        old = release(epoch=10)
        current = release(copy.deepcopy(old.public_bundle), epoch=11)
        initial = pins(old)
        current_pins = pins(current)
        original = copy.deepcopy(current)
        current.reads[ONE].read.sentences[0]["text"] = (
            "PRIVATE_SENTINEL_FROM_UNREVIEWED_BYTES"
        )
        with self.assertRaisesRegex(ValueError, "COHORT_.*PIN_MISMATCH"):
            self.run_plan(
                old,
                current,
                expected_current_release_sha256=current_pins["release"],
                expected_current_read_sha256=current_pins["reads"],
            )
        self.assertEqual(self.run_plan(old, original).items, ())

        class EvilRead(type(old.reads[ONE].read)):
            pass

        current = release(copy.deepcopy(old.public_bundle), epoch=11)
        current.reads[ONE] = replace(
            current.reads[ONE], read=EvilRead(**vars(current.reads[ONE].read))
        )
        with self.assertRaisesRegex(ValueError, "COHORT_INPUT_INVALID"):
            self.run_plan(old, current)

        class EvilDict(dict):
            pass

        current = release(copy.deepcopy(old.public_bundle), epoch=11)
        current.public_bundle["statements"][0] = EvilDict(
            current.public_bundle["statements"][0]
        )
        with self.assertRaisesRegex(ValueError, "COHORT_INPUT_INVALID"):
            self.run_plan(old, current)
        self.assertEqual(initial["release"], pins(old)["release"])

    def test_external_pins_cannot_be_self_issued_and_output_no_url_or_original(self):
        old = release(epoch=10)
        new = release(copy.deepcopy(old.public_bundle), epoch=11)
        changed = copy.deepcopy(new)
        changed.public_bundle["statements"][0]["source_url"] = (
            "https://example.test/CHANGED"
        )
        changed.public_bundle["dataset_sha256"] = projection_dataset_sha256(
            changed.public_bundle
        )
        with self.assertRaisesRegex(
            ValueError, "COHORT_.*INVALID|COHORT_.*PIN_MISMATCH"
        ):
            self.run_plan(old, changed)
        result = self.run_plan(old, new)
        for sensitive in (
            "example.test",
            "Persona dimostrativa",
            "Documento dimostrativo",
        ):
            self.assertNotIn(sensitive, repr(result))


if __name__ == "__main__":
    unittest.main()
