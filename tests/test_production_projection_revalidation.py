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
    RevalidationProof,
)
from dichiarazioni_pubbliche.production_projection_revalidation import (  # noqa: E402
    ProductionProjectionRevalidator,
    local_provenance_hold_allows_publication,
)
from dichiarazioni_pubbliche.source_revalidation import (  # noqa: E402
    SourceSnapshot,
    evaluate_reobservation,
)
from dichiarazioni_pubbliche.source_revalidation_hold import (  # noqa: E402
    activate_source_revalidation_hold,
)


FINDING_ID = "finding:projection-hold"
SOURCE_SHA_A = hashlib.sha256(b"source-a").hexdigest()
SOURCE_SHA_B = hashlib.sha256(b"source-b").hexdigest()
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def refs(*, source_version: str = "source:v1") -> dict[str, str]:
    return {
        "source_version": source_version,
        "provenance_version": "provenance:v1",
        "policy_version": "policy:v1",
        "review_version": "review:v1",
    }


def graph_for(scope: HoldScopeTarget, load_refs: dict[str, str]) -> BoundedDependencyGraph:
    return BoundedDependencyGraph(
        records=(
            PublicDependencyRecord(
                public_id=FINDING_ID,
                dependencies=(scope,),
                load_bearing_refs=load_refs,
            ),
        )
    )


def registry() -> InMemoryProvenanceHoldRegistry:
    return InMemoryProvenanceHoldRegistry(
        actors=(
            ActorAuthorization("operator", frozenset({HoldPermission.ACTIVATE})),
            ActorAuthorization("reviewer", frozenset({HoldPermission.REVIEW_UNHOLD})),
            ActorAuthorization("revalidator", frozenset({HoldPermission.REVALIDATE})),
        )
    )


class ProductionProjectionLocalHoldTests(unittest.TestCase):
    def test_active_and_pending_hold_block_until_exact_current_revalidation(self):
        scope = HoldScopeTarget.finding(FINDING_ID)
        load_refs = refs()
        graph = graph_for(scope, load_refs)
        holds = registry()
        binding = RevalidationProof(load_refs).binding_sha256

        holds.activate(
            request_id="hold:activate",
            hold_id="hold:projection",
            actor_id="operator",
            reason_code="SOURCE_VERSION_DEFECT",
            scope=scope,
            graph=graph,
        )
        self.assertFalse(
            local_provenance_hold_allows_publication(
                finding_id=FINDING_ID,
                current_safety_binding_sha256=binding,
                registry=holds,
                graph=graph,
            )
        )
        holds.reviewed_unhold(
            request_id="hold:review",
            hold_id="hold:projection",
            actor_id="reviewer",
            review_code="FIX_REVIEWED",
            graph=graph,
        )
        self.assertFalse(
            local_provenance_hold_allows_publication(
                finding_id=FINDING_ID,
                current_safety_binding_sha256=binding,
                registry=holds,
                graph=graph,
            )
        )
        holds.revalidate(
            request_id="hold:revalidate",
            hold_id="hold:projection",
            actor_id="revalidator",
            proof=RevalidationProof(load_refs),
            graph=graph,
        )
        self.assertTrue(
            local_provenance_hold_allows_publication(
                finding_id=FINDING_ID,
                current_safety_binding_sha256=binding,
                registry=holds,
                graph=graph,
            )
        )

        changed_binding = RevalidationProof(refs(source_version="source:v2")).binding_sha256
        self.assertFalse(
            local_provenance_hold_allows_publication(
                finding_id=FINDING_ID,
                current_safety_binding_sha256=changed_binding,
                registry=holds,
                graph=graph,
            )
        )

    def test_tampered_local_hold_chain_fails_closed(self):
        scope = HoldScopeTarget.finding(FINDING_ID)
        load_refs = refs()
        graph = graph_for(scope, load_refs)
        holds = registry()
        binding = RevalidationProof(load_refs).binding_sha256
        holds.activate(
            request_id="hold:tamper",
            hold_id="hold:tamper",
            actor_id="operator",
            reason_code="SOURCE_VERSION_DEFECT",
            scope=scope,
            graph=graph,
        )
        holds._events[0] = replace(holds.events[0], reason_code="CHANGED_AFTER_APPEND")
        self.assertFalse(
            local_provenance_hold_allows_publication(
                finding_id=FINDING_ID,
                current_safety_binding_sha256=binding,
                registry=holds,
                graph=graph,
            )
        )

    def test_source_drift_hold_prevents_silent_version_swap_until_revalidated(self):
        previous = SourceSnapshot(
            source_id="source:official:projection",
            observed_at=NOW,
            availability="AVAILABLE",
            content_sha256=SOURCE_SHA_A,
            source_version="v1",
            etag='"a"',
            canonical_url="https://example.test/source",
            rights_status="CLEARED",
        )
        current = replace(
            previous,
            observed_at=NOW.replace(hour=13),
            content_sha256=SOURCE_SHA_B,
            source_version="v2",
            etag='"b"',
        )
        decision = evaluate_reobservation(
            previous,
            current,
            as_of=date(2026, 10, 6),
            load_bearing_for_evidence=True,
        )
        source_scope = HoldScopeTarget.source(
            provider_id="official-provider",
            source_id=previous.source_id,
            source_version="v1",
        )
        load_refs = refs(source_version="source-snapshot:v2")
        graph = graph_for(source_scope, load_refs)
        holds = registry()
        receipt = activate_source_revalidation_hold(
            decision=decision,
            previous=previous,
            current=current,
            provider_id="official-provider",
            actor_id="operator",
            graph=graph,
            registry=holds,
        )
        self.assertIsNotNone(receipt)
        binding = RevalidationProof(load_refs).binding_sha256
        self.assertFalse(
            local_provenance_hold_allows_publication(
                finding_id=FINDING_ID,
                current_safety_binding_sha256=binding,
                registry=holds,
                graph=graph,
            )
        )

        holds.reviewed_unhold(
            request_id="source:reviewed-unhold",
            hold_id=receipt.hold.hold_id,
            actor_id="reviewer",
            review_code="SOURCE_V2_REVIEWED",
            graph=graph,
        )
        holds.revalidate(
            request_id="source:revalidated",
            hold_id=receipt.hold.hold_id,
            actor_id="revalidator",
            proof=RevalidationProof(load_refs),
            graph=graph,
        )
        self.assertTrue(
            local_provenance_hold_allows_publication(
                finding_id=FINDING_ID,
                current_safety_binding_sha256=binding,
                registry=holds,
                graph=graph,
            )
        )

    def test_partial_local_hold_configuration_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "PRODUCTION_REVALIDATION_LOCAL_HOLD_INPUT_INCOMPLETE",
        ):
            ProductionProjectionRevalidator(
                None,
                reviewer_authority_root=None,
                local_hold_registry=registry(),
            )


class ProductionProjectionRightsScopeTests(unittest.TestCase):
    """A reviewed private fetch grant must not become public-link authority."""

    def test_clearance_without_explicit_public_link_permission_stays_held(self):
        current = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        record = {
            "record_visibility": "PRIVATE",
            "rights_status": "CLEARED",
            "rights_receipt_ref": "rights:reviewed",
            "reviewer_ref": "reviewer:authorized",
            "reviewed_at": "2026-10-09T12:00:00+00:00",
            "permitted_uses": ["PRIVATE_FETCH", "PRIVATE_MODEL_PROCESSING"],
            "expires_at": None,
        }
        passed = ProductionProjectionRevalidator._rights_pass
        self.assertFalse(passed((record,), now=current))
        self.assertFalse(passed(({**record, "permitted_uses": []},), now=current))
        self.assertFalse(passed(({**record, "permitted_uses": "LINK_PUBLIC"},), now=current))
        self.assertTrue(passed(({**record, "permitted_uses": ["LINK_PUBLIC"]},), now=current))

    def test_public_link_permission_requires_current_reviewed_clearance(self):
        current = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        record = {
            "record_visibility": "PRIVATE",
            "rights_status": "CLEARED",
            "rights_receipt_ref": "rights:reviewed",
            "reviewer_ref": "reviewer:authorized",
            "reviewed_at": "2026-10-09T12:00:00+00:00",
            "permitted_uses": ["LINK_PUBLIC"],
            "expires_at": "2026-10-11T00:00:00+00:00",
        }
        passed = ProductionProjectionRevalidator._rights_pass
        for field, value in (
            ("rights_status", "UNKNOWN"),
            ("record_visibility", "PUBLIC"),
            ("rights_receipt_ref", None),
            ("reviewer_ref", None),
            ("reviewed_at", None),
            ("reviewed_at", "2026-10-12T00:00:00+00:00"),
            ("reviewed_at", "2026-10-09T12:00:00"),
            ("expires_at", "2026-10-09T00:00:00+00:00"),
        ):
            with self.subTest(field=field, value=value):
                self.assertFalse(passed(({**record, field: value},), now=current))
        self.assertTrue(passed((record,), now=current))


if __name__ == "__main__":
    unittest.main()
