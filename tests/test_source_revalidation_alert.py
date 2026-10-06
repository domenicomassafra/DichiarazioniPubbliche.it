import hashlib
import json
import sys
import unittest
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ops.taxonomy import actionable  # noqa: E402
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
from dichiarazioni_pubbliche.source_revalidation_alert import (  # noqa: E402
    SourceRevalidationAlertError,
    bounded_revalidation_alert_digest,
    build_source_revalidation_operator_alert,
)
from dichiarazioni_pubbliche.source_revalidation_hold import (  # noqa: E402
    activate_source_revalidation_hold,
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
        canonical_url="https://secret.example.test/official/1",
        rights_status="CLEARED",
        metadata={"private_note": "do not emit me"},
    )
    values.update(overrides)
    return SourceSnapshot(**values)


def graph(previous, *, count=1):
    scope = HoldScopeTarget.source(
        provider_id=PROVIDER,
        source_id=previous.source_id,
        source_version=previous.source_version,
    )
    return BoundedDependencyGraph(
        records=tuple(
            PublicDependencyRecord(
                public_id=f"public:finding:{index:03d}",
                dependencies=(scope,),
                load_bearing_refs={
                    "source_version": previous.source_version,
                    "provenance_version": f"provenance:{index}",
                    "policy_version": "policy-v1",
                    "review_version": f"review:{index}",
                },
            )
            for index in range(count)
        )
    )


def hold_registry():
    return InMemoryProvenanceHoldRegistry(
        actors=(
            ActorAuthorization("operator", frozenset({HoldPermission.ACTIVATE})),
        )
    )


def decision(previous, current, **load_bearing):
    return evaluate_reobservation(
        previous,
        current,
        as_of=date(2026, 10, 5),
        **load_bearing,
    )


class SourceRevalidationAlertTests(unittest.TestCase):
    def test_hold_alert_reuses_dp505_source_taxonomy_and_dp510_ids(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            content_sha256=SHA_B,
            source_version="v2",
            etag='"etag-b"',
        )
        result = decision(previous, current, load_bearing_for_quote=True)
        dependency_graph = graph(previous)
        registry = hold_registry()
        hold = activate_source_revalidation_hold(
            decision=result,
            previous=previous,
            current=current,
            provider_id=PROVIDER,
            actor_id="operator",
            graph=dependency_graph,
            registry=registry,
        )
        alert = build_source_revalidation_operator_alert(
            decision=result,
            source_id=previous.source_id,
            provider_id=PROVIDER,
            source_version=previous.source_version,
            graph=dependency_graph,
            hold_receipt=hold,
        )

        expected = actionable(({"category": "SOURCE", "count": 1},))[0]
        self.assertEqual(alert.category, "SOURCE")
        self.assertEqual(alert.severity, expected["severity"])
        self.assertEqual(alert.page, expected["page"])
        self.assertTrue(expected["operator_action"])
        self.assertEqual(alert.hold_id, hold.hold.hold_id)
        self.assertEqual(alert.hold_event_id, hold.hold.event_id)
        self.assertEqual(alert.affected_public_ids, ("public:finding:000",))

    def test_review_required_maps_to_existing_source_warning_without_hold(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            content_sha256=SHA_B,
            source_version="v2",
        )
        result = decision(previous, current)
        alert = build_source_revalidation_operator_alert(
            decision=result,
            source_id=previous.source_id,
            provider_id=PROVIDER,
            source_version=previous.source_version,
            graph=graph(previous),
        )

        self.assertEqual(result.disposition, RevalidationDisposition.REVIEW_REQUIRED)
        self.assertEqual(alert.category, "SOURCE")
        self.assertEqual(alert.severity, "WARNING")
        self.assertFalse(alert.page)
        self.assertIsNone(alert.hold_id)

    def test_rights_expiry_maps_to_existing_evidence_taxonomy(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            rights_expires_on=date(2026, 10, 5),
        )
        result = decision(previous, current, load_bearing_for_evidence=True)
        dependency_graph = graph(previous)
        registry = hold_registry()
        hold = activate_source_revalidation_hold(
            decision=result,
            previous=previous,
            current=current,
            provider_id=PROVIDER,
            actor_id="operator",
            graph=dependency_graph,
            registry=registry,
        )
        alert = build_source_revalidation_operator_alert(
            decision=result,
            source_id=previous.source_id,
            provider_id=PROVIDER,
            source_version=previous.source_version,
            graph=dependency_graph,
            hold_receipt=hold,
        )

        expected = actionable(({"category": "EVIDENCE", "count": 1},))[0]
        self.assertEqual(alert.category, "EVIDENCE")
        self.assertEqual(alert.severity, expected["severity"])
        self.assertEqual(alert.page, expected["page"])
        self.assertIn("RIGHTS_EXPIRED", alert.change_codes)

    def test_official_supersession_maps_deterministically_to_source(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            source_version="v2",
            supersedes_version="v1",
            content_sha256=SHA_B,
        )
        result = decision(previous, current, load_bearing_for_evidence=True)
        dependency_graph = graph(previous)
        registry = hold_registry()
        hold = activate_source_revalidation_hold(
            decision=result,
            previous=previous,
            current=current,
            provider_id=PROVIDER,
            actor_id="operator",
            graph=dependency_graph,
            registry=registry,
        )
        alert = build_source_revalidation_operator_alert(
            decision=result,
            source_id=previous.source_id,
            provider_id=PROVIDER,
            source_version=previous.source_version,
            graph=dependency_graph,
            hold_receipt=hold,
        )
        self.assertEqual(alert.category, "SOURCE")
        self.assertIn("OFFICIAL_VERSION_SUPERSEDED", alert.change_codes)

    def test_unchanged_emits_no_alert_and_retry_is_never_critical(self):
        previous = snapshot()
        unchanged = replace(previous, observed_at=NOW.replace(hour=21))
        unchanged_decision = decision(previous, unchanged)
        self.assertIsNone(
            build_source_revalidation_operator_alert(
                decision=unchanged_decision,
                source_id=previous.source_id,
                provider_id=PROVIDER,
                source_version=previous.source_version,
                graph=graph(previous),
            )
        )

        unavailable = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            availability="UNAVAILABLE",
            content_sha256=None,
            etag=None,
        )
        retry_decision = decision(previous, unavailable)
        retry_alert = build_source_revalidation_operator_alert(
            decision=retry_decision,
            source_id=previous.source_id,
            provider_id=PROVIDER,
            source_version=previous.source_version,
            graph=graph(previous),
        )
        self.assertEqual(retry_decision.disposition, RevalidationDisposition.AVAILABILITY_RETRY)
        self.assertNotIn(retry_alert.severity, {"CRITICAL", "OUTAGE"})
        self.assertFalse(retry_alert.page)

    def test_alert_payload_contains_only_bounded_ids_codes_and_taxonomy_fields(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            content_sha256=SHA_B,
            source_version="v2",
        )
        result = decision(previous, current)
        alert = build_source_revalidation_operator_alert(
            decision=result,
            source_id=previous.source_id,
            provider_id=PROVIDER,
            source_version=previous.source_version,
            graph=graph(previous, count=60),
        )
        payload = asdict(alert)
        serialized = json.dumps(payload, sort_keys=True)

        self.assertEqual(len(alert.affected_public_ids), 50)
        self.assertTrue(alert.affected_ids_truncated)
        self.assertNotIn("https://", serialized)
        self.assertNotIn(SHA_A, serialized)
        self.assertNotIn(SHA_B, serialized)
        self.assertNotIn("do not emit me", serialized)
        self.assertNotIn("metadata", payload)
        self.assertNotIn("canonical_url", payload)
        self.assertNotIn("snapshot_ref", serialized)

    def test_digest_deduplicates_exact_event_replay_and_rejects_conflict(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            content_sha256=SHA_B,
            source_version="v2",
        )
        result = decision(previous, current)
        first = build_source_revalidation_operator_alert(
            decision=result,
            source_id=previous.source_id,
            provider_id=PROVIDER,
            source_version=previous.source_version,
            graph=graph(previous),
        )
        self.assertEqual(bounded_revalidation_alert_digest((first, first)), (first,))

        conflicting = replace(first, severity="CRITICAL")
        with self.assertRaisesRegex(
            SourceRevalidationAlertError,
            "SOURCE_REVALIDATION_ALERT_REPLAY_CONFLICT",
        ):
            bounded_revalidation_alert_digest((first, conflicting))

    def test_hold_alert_requires_matching_dp510_event(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            content_sha256=SHA_B,
            source_version="v2",
        )
        result = decision(previous, current, load_bearing_for_quote=True)
        with self.assertRaisesRegex(
            SourceRevalidationAlertError,
            "SOURCE_REVALIDATION_ALERT_HOLD_RECEIPT_REQUIRED",
        ):
            build_source_revalidation_operator_alert(
                decision=result,
                source_id=previous.source_id,
                provider_id=PROVIDER,
                source_version=previous.source_version,
                graph=graph(previous),
            )


if __name__ == "__main__":
    unittest.main()
