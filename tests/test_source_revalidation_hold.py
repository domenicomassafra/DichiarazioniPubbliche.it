import hashlib
import sys
import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.provenance_quarantine import (  # noqa: E402
    ActorAuthorization,
    BoundedDependencyGraph,
    HoldPermission,
    HoldScopeTarget,
    InMemoryProvenanceHoldRegistry,
    PublicDependencyRecord,
)
from dichiarazioni_pubbliche.source_revalidation import (  # noqa: E402
    RevalidationDisposition,
    SourceSnapshot,
    evaluate_reobservation,
)
from dichiarazioni_pubbliche.source_revalidation_hold import (  # noqa: E402
    SourceRevalidationHoldError,
    activate_source_revalidation_hold,
    build_source_revalidation_hold_request,
)


SHA_A = hashlib.sha256(b"source version a").hexdigest()
SHA_B = hashlib.sha256(b"source version b").hexdigest()
NOW = datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)
PROVIDER = "official-provider"


def snapshot(**overrides):
    values = dict(
        source_id="source:official:1",
        observed_at=NOW,
        availability="AVAILABLE",
        content_sha256=SHA_A,
        source_version="v1",
        etag='"etag-a"',
        canonical_url="https://example.test/official/1",
        rights_status="CLEARED",
    )
    values.update(overrides)
    return SourceSnapshot(**values)


def graph_for_previous(previous):
    scope = HoldScopeTarget.source(
        provider_id=PROVIDER,
        source_id=previous.source_id,
        source_version=previous.source_version,
    )
    graph = BoundedDependencyGraph(
        records=(
            PublicDependencyRecord(
                public_id="public:finding:1",
                dependencies=(scope,),
                load_bearing_refs={
                    "source_version": previous.source_version,
                    "provenance_version": "provenance-v1",
                    "policy_version": "policy-v1",
                    "review_version": "review-v1",
                },
            ),
        )
    )
    return graph, scope


def registry():
    return InMemoryProvenanceHoldRegistry(
        actors=(
            ActorAuthorization("operator", frozenset({HoldPermission.ACTIVATE})),
        )
    )


def apply(previous, current, *, quote=False, speaker=False, evidence=False):
    decision = evaluate_reobservation(
        previous,
        current,
        as_of=date(2026, 10, 5),
        load_bearing_for_quote=quote,
        load_bearing_for_speaker=speaker,
        load_bearing_for_evidence=evidence,
    )
    graph, scope = graph_for_previous(previous)
    holds = registry()
    receipt = activate_source_revalidation_hold(
        decision=decision,
        previous=previous,
        current=current,
        provider_id=PROVIDER,
        actor_id="operator",
        graph=graph,
        registry=holds,
    )
    return decision, receipt, holds, scope


class SourceRevalidationHoldTests(unittest.TestCase):
    def test_changed_source_creates_exactly_one_typed_hold_for_previous_version(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            content_sha256=SHA_B,
            source_version="v2",
            etag='"etag-b"',
        )
        decision, receipt, holds, expected_scope = apply(previous, current, quote=True)

        self.assertEqual(decision.disposition, RevalidationDisposition.HOLD_REQUIRED)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.request.scope, expected_scope)
        self.assertEqual(receipt.request.scope.version, "v1")
        self.assertEqual(receipt.decision_event_key, decision.event_key)
        self.assertEqual(receipt.hold.impact.affected_public_ids, ("public:finding:1",))
        self.assertEqual(len(holds.events), 1)

    def test_official_supersession_creates_one_replay_safe_targeted_hold(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            source_version="v2",
            supersedes_version="v1",
            content_sha256=SHA_B,
        )
        decision, receipt, holds, _ = apply(previous, current, evidence=True)

        self.assertIn("OFFICIAL_VERSION_SUPERSEDED", receipt.material_change_codes)
        replay = activate_source_revalidation_hold(
            decision=decision,
            previous=previous,
            current=current,
            provider_id=PROVIDER,
            actor_id="operator",
            graph=graph_for_previous(previous)[0],
            registry=holds,
        )
        self.assertEqual(replay, receipt)
        self.assertEqual(len(holds.events), 1)

    def test_rights_expiry_creates_targeted_hold_even_with_stable_bytes(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            rights_expires_on=date(2026, 10, 5),
        )
        decision, receipt, holds, _ = apply(previous, current, evidence=True)

        self.assertTrue(decision.needs_targeted_hold)
        self.assertIn("RIGHTS_EXPIRED", receipt.material_change_codes)
        self.assertEqual(len(holds.events), 1)

    def test_unchanged_source_does_not_activate_hold(self):
        previous = snapshot()
        current = replace(previous, observed_at=NOW.replace(hour=21))
        decision, receipt, holds, _ = apply(previous, current, quote=True)

        self.assertEqual(decision.disposition, RevalidationDisposition.UNCHANGED)
        self.assertIsNone(receipt)
        self.assertEqual(holds.events, ())

    def test_unavailable_source_retry_does_not_activate_hold(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            availability="UNAVAILABLE",
            content_sha256=None,
            etag=None,
        )
        decision, receipt, holds, _ = apply(previous, current, quote=True)

        self.assertEqual(decision.disposition, RevalidationDisposition.AVAILABILITY_RETRY)
        self.assertIsNone(receipt)
        self.assertEqual(holds.events, ())

    def test_review_required_without_targeted_hold_does_not_activate_hold(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            content_sha256=SHA_B,
            source_version="v2",
        )
        decision, receipt, holds, _ = apply(previous, current)

        self.assertEqual(decision.disposition, RevalidationDisposition.REVIEW_REQUIRED)
        self.assertFalse(decision.needs_targeted_hold)
        self.assertIsNone(receipt)
        self.assertEqual(holds.events, ())

    def test_tampered_event_key_is_rejected_before_hold_activation(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            content_sha256=SHA_B,
            source_version="v2",
        )
        decision = evaluate_reobservation(
            previous,
            current,
            as_of=date(2026, 10, 5),
            load_bearing_for_quote=True,
        )
        tampered = replace(decision, event_key="0" * 64)

        with self.assertRaisesRegex(
            SourceRevalidationHoldError,
            "EVENT_KEY_MISMATCH",
        ):
            build_source_revalidation_hold_request(
                decision=tampered,
                previous=previous,
                current=current,
                provider_id=PROVIDER,
            )


if __name__ == "__main__":
    unittest.main()
