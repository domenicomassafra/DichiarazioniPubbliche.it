import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.provenance_quarantine import (  # noqa: E402
    ActorAuthorization,
    BoundedDependencyGraph,
    DependencyLink,
    HoldPermission,
    HoldScopeTarget,
    HoldState,
    InMemoryProvenanceHoldRegistry,
    ProvenanceQuarantineError,
    PublicDependencyRecord,
    RevalidationProof,
    publication_binding_sha256,
    verify_hold_event_chain,
)
from dichiarazioni_pubbliche.publication_safety import (  # noqa: E402
    ProofState,
    PublicationSafetyInput,
    WordingMode,
    evaluate_publication_safety,
)


def refs(name):
    return {
        "source_version": f"source:{name}:v1",
        "provenance_version": f"provenance:{name}:v1",
        "policy_version": "policy-v1",
        "review_version": f"review:{name}:v1",
    }


def graph_fixture():
    source_a = HoldScopeTarget.source(
        provider_id="provider-a",
        source_id="source-a",
        source_version="v1",
    )
    source_b = HoldScopeTarget.source(
        provider_id="provider-b",
        source_id="source-b",
        source_version="v7",
    )
    transcript_a = HoldScopeTarget.transcript("transcript-a", "tx-v3")
    transcript_b = HoldScopeTarget.transcript("transcript-b", "tx-v2")
    speaker_a = HoldScopeTarget.speaker_method("MANUAL_REVIEW", "speaker-v2")
    speaker_b = HoldScopeTarget.speaker_method("SOURCE_METADATA", "speaker-v1")
    person_a = HoldScopeTarget.person_mapping("person-map-a", "map-v4")
    person_b = HoldScopeTarget.person_mapping("person-map-b", "map-v1")
    finding_a = HoldScopeTarget.finding("finding:a")
    finding_b = HoldScopeTarget.finding("finding:b")
    finding_c = HoldScopeTarget.finding("finding:c")

    graph = BoundedDependencyGraph(
        records=(
            PublicDependencyRecord("public:a", (finding_a,), refs("a")),
            PublicDependencyRecord("public:b", (finding_b,), refs("b")),
            PublicDependencyRecord("public:c", (finding_c,), refs("c")),
        ),
        links=(
            DependencyLink(source_a, transcript_a),
            DependencyLink(transcript_a, speaker_a),
            DependencyLink(speaker_a, person_a),
            DependencyLink(person_a, finding_a),
            DependencyLink(source_b, transcript_b),
            DependencyLink(transcript_b, speaker_b),
            DependencyLink(speaker_b, person_b),
            DependencyLink(person_b, finding_b),
        ),
    )
    return graph, {
        "source_a": source_a,
        "source_b": source_b,
        "transcript_a": transcript_a,
        "speaker_a": speaker_a,
        "person_a": person_a,
        "finding_a": finding_a,
        "finding_c": finding_c,
    }


def registry():
    return InMemoryProvenanceHoldRegistry(
        actors=(
            ActorAuthorization("operator", frozenset({HoldPermission.ACTIVATE})),
            ActorAuthorization("reviewer", frozenset({HoldPermission.REVIEW_UNHOLD})),
            ActorAuthorization("revalidator", frozenset({HoldPermission.REVALIDATE})),
        )
    )


def proof(**overrides):
    values = {
        "source_version": "source:a:v2",
        "provenance_version": "provenance:a:v2",
        "policy_version": "policy-v2",
        "review_version": "review:a:v2",
    }
    values.update(overrides)
    return RevalidationProof(values)


class ProvenanceQuarantineTests(unittest.TestCase):
    def test_source_provider_version_scope_is_deterministic_and_unrelated_records_survive(self):
        graph, target = graph_fixture()
        first = graph.dry_run(target["source_a"])
        second = graph.dry_run(target["source_a"])

        self.assertEqual(first, second)
        self.assertEqual(first.affected_public_ids, ("public:a",))
        self.assertNotIn("public:b", first.affected_public_ids)
        self.assertNotIn("public:c", first.affected_public_ids)
        self.assertEqual(
            graph.dry_run(
                HoldScopeTarget.source(
                    provider_id="provider-other",
                    source_id="source-a",
                    source_version="v1",
                )
            ).affected_count,
            0,
        )
        self.assertEqual(
            graph.dry_run(
                HoldScopeTarget.source(
                    provider_id="provider-a",
                    source_id="source-a",
                    source_version="v2",
                )
            ).affected_count,
            0,
        )

    def test_transcript_speaker_person_and_single_finding_scopes(self):
        graph, target = graph_fixture()

        for name in ("transcript_a", "speaker_a", "person_a", "finding_a"):
            with self.subTest(scope=name):
                receipt = graph.dry_run(target[name])
                self.assertEqual(receipt.affected_public_ids, ("public:a",))
        self.assertEqual(
            graph.dry_run(target["finding_c"]).affected_public_ids,
            ("public:c",),
        )

    def test_activate_reviewed_unhold_revalidation_is_explicit_and_append_only(self):
        graph, target = graph_fixture()
        holds = registry()
        before_records = tuple(
            (
                record.public_id,
                record.dependencies,
                tuple(sorted(record.load_bearing_refs.items())),
            )
            for record in graph.records
        )

        activated = holds.activate(
            request_id="request:activate:1",
            hold_id="hold:1",
            actor_id="operator",
            reason_code="TRANSCRIPT_PROVIDER_INCIDENT",
            incident_id="incident:42",
            scope=target["source_a"],
            graph=graph,
            private_note="private incident body",
        )
        self.assertEqual(activated.state, HoldState.ACTIVE)
        self.assertEqual(holds.held_public_ids(graph), ("public:a",))

        reviewed = holds.reviewed_unhold(
            request_id="request:review:1",
            hold_id="hold:1",
            actor_id="reviewer",
            review_code="FIX_REVIEWED",
            graph=graph,
        )
        self.assertEqual(reviewed.state, HoldState.PENDING_REVALIDATION)
        self.assertEqual(holds.held_public_ids(graph), ("public:a",))

        released = holds.revalidate(
            request_id="request:revalidate:1",
            hold_id="hold:1",
            actor_id="revalidator",
            proof=proof(),
            graph=graph,
        )
        self.assertEqual(released.state, HoldState.RELEASED)
        self.assertEqual(holds.held_public_ids(graph), ())
        self.assertEqual(
            tuple(
                (
                    record.public_id,
                    record.dependencies,
                    tuple(sorted(record.load_bearing_refs.items())),
                )
                for record in graph.records
            ),
            before_records,
        )
        self.assertEqual(len(holds.events), 3)
        self.assertTrue(verify_hold_event_chain(holds.events))

    def test_reviewed_unhold_without_revalidation_remains_held(self):
        graph, target = graph_fixture()
        holds = registry()
        holds.activate(
            request_id="request:activate:2",
            hold_id="hold:2",
            actor_id="operator",
            reason_code="SOURCE_VERSION_DEFECT",
            scope=target["source_a"],
            graph=graph,
        )
        holds.reviewed_unhold(
            request_id="request:review:2",
            hold_id="hold:2",
            actor_id="reviewer",
            review_code="PATCH_REVIEWED",
            graph=graph,
        )

        self.assertEqual(holds.state("hold:2"), HoldState.PENDING_REVALIDATION)
        self.assertEqual(holds.held_public_ids(graph), ("public:a",))

    def test_status_cannot_be_directly_edited_around_append_only_events(self):
        graph, target = graph_fixture()
        holds = registry()
        holds.activate(
            request_id="request:status-edit",
            hold_id="hold:status-edit",
            actor_id="operator",
            reason_code="SOURCE_VERSION_DEFECT",
            scope=target["source_a"],
            graph=graph,
        )

        with self.assertRaises(AttributeError):
            holds.status = HoldState.RELEASED
        self.assertEqual(holds.state("hold:status-edit"), HoldState.ACTIVE)

    def test_revalidation_cannot_skip_reviewed_unhold(self):
        graph, target = graph_fixture()
        holds = registry()
        holds.activate(
            request_id="request:activate:3",
            hold_id="hold:3",
            actor_id="operator",
            reason_code="PERSON_MAPPING_DEFECT",
            scope=target["person_a"],
            graph=graph,
        )

        with self.assertRaisesRegex(
            ProvenanceQuarantineError,
            "HOLD_REVALIDATION_SEQUENCE_INVALID",
        ):
            holds.revalidate(
                request_id="request:revalidate:3",
                hold_id="hold:3",
                actor_id="revalidator",
                proof=proof(),
                graph=graph,
            )

    def test_revalidation_binding_matches_dp308_load_bearing_binding_shape(self):
        revalidation = proof()
        publication = evaluate_publication_safety(
            PublicationSafetyInput(
                wording_mode=WordingMode.PARAPHRASE,
                media_quote=False,
                source_identity=ProofState.PASSED,
                exact_wording=ProofState.NOT_APPLICABLE,
                transcript_verbatim=ProofState.NOT_APPLICABLE,
                speaker_span=ProofState.PASSED,
                speech_origin=ProofState.PASSED,
                context_integrity=ProofState.PASSED,
                wording_integrity=ProofState.PASSED,
                identity_integrity=ProofState.PASSED,
                translation_review=ProofState.NOT_APPLICABLE,
                evidence_suitability=ProofState.PASSED,
                citation_assurance=ProofState.PASSED,
                privacy=ProofState.PASSED,
                rights=ProofState.PASSED,
                verification_review=ProofState.PASSED,
                finding_review=ProofState.PASSED,
                challenge_hold=ProofState.PASSED,
                load_bearing_refs=revalidation.load_bearing_refs,
            )
        )
        self.assertEqual(revalidation.binding_sha256, publication.binding_sha256)
        self.assertEqual(
            revalidation.binding_sha256,
            publication_binding_sha256(revalidation.load_bearing_refs),
        )

    def test_replay_is_idempotent_but_request_id_reuse_with_changed_scope_is_rejected(self):
        graph, target = graph_fixture()
        holds = registry()
        kwargs = dict(
            request_id="request:replay",
            hold_id="hold:replay",
            actor_id="operator",
            reason_code="SOURCE_VERSION_DEFECT",
            scope=target["source_a"],
            graph=graph,
        )
        first = holds.activate(**kwargs)
        replay = holds.activate(**kwargs)
        self.assertEqual(first, replay)
        self.assertEqual(len(holds.events), 1)

        changed = dict(kwargs)
        changed["scope"] = target["source_b"]
        with self.assertRaisesRegex(ProvenanceQuarantineError, "HOLD_REPLAY_CONFLICT"):
            holds.activate(**changed)

    def test_review_and_revalidation_request_replay_remains_idempotent_after_release(self):
        graph, target = graph_fixture()
        holds = registry()
        holds.activate(
            request_id="request:progressed:activate",
            hold_id="hold:progressed",
            actor_id="operator",
            reason_code="SOURCE_VERSION_DEFECT",
            scope=target["source_a"],
            graph=graph,
        )
        review_kwargs = dict(
            request_id="request:progressed:review",
            hold_id="hold:progressed",
            actor_id="reviewer",
            review_code="PATCH_REVIEWED",
            graph=graph,
        )
        review = holds.reviewed_unhold(**review_kwargs)
        revalidation_kwargs = dict(
            request_id="request:progressed:revalidate",
            hold_id="hold:progressed",
            actor_id="revalidator",
            proof=proof(),
            graph=graph,
        )
        revalidated = holds.revalidate(**revalidation_kwargs)

        self.assertEqual(holds.reviewed_unhold(**review_kwargs), review)
        self.assertEqual(holds.revalidate(**revalidation_kwargs), revalidated)
        self.assertEqual(len(holds.events), 3)

    def test_tampered_event_chain_is_detected_and_blocks_followup(self):
        graph, target = graph_fixture()
        holds = registry()
        holds.activate(
            request_id="request:tamper",
            hold_id="hold:tamper",
            actor_id="operator",
            reason_code="SPEAKER_METHOD_DEFECT",
            scope=target["speaker_a"],
            graph=graph,
        )
        tampered = replace(holds.events[0], reason_code="CHANGED_AFTER_APPEND")
        self.assertFalse(verify_hold_event_chain((tampered,)))

        holds._events[0] = tampered
        with self.assertRaisesRegex(ProvenanceQuarantineError, "HOLD_EVENT_CHAIN_TAMPERED"):
            holds.reviewed_unhold(
                request_id="request:tamper:review",
                hold_id="hold:tamper",
                actor_id="reviewer",
                review_code="FIX_REVIEWED",
                graph=graph,
            )

    def test_unauthorized_actor_cannot_create_review_or_clear_hold(self):
        graph, target = graph_fixture()
        holds = registry()
        with self.assertRaisesRegex(ProvenanceQuarantineError, "HOLD_ACTOR_UNAUTHORIZED"):
            holds.activate(
                request_id="request:nope",
                hold_id="hold:nope",
                actor_id="public-caller",
                reason_code="SOURCE_DEFECT",
                scope=target["source_a"],
                graph=graph,
            )

        holds.activate(
            request_id="request:auth",
            hold_id="hold:auth",
            actor_id="operator",
            reason_code="SOURCE_DEFECT",
            scope=target["source_a"],
            graph=graph,
        )
        with self.assertRaisesRegex(ProvenanceQuarantineError, "HOLD_ACTOR_UNAUTHORIZED"):
            holds.reviewed_unhold(
                request_id="request:auth:review",
                hold_id="hold:auth",
                actor_id="operator",
                review_code="FIX_REVIEWED",
                graph=graph,
            )

    def test_receipt_is_bounded_and_redacts_private_note_and_actor_identity(self):
        graph, target = graph_fixture()
        holds = registry()
        receipt = holds.activate(
            request_id="request:redaction",
            hold_id="hold:redaction",
            actor_id="operator",
            reason_code="SOURCE_DEFECT",
            scope=target["source_a"],
            graph=graph,
            private_note="secret contact alice@example.test",
        )

        self.assertTrue(receipt.private_note_redacted)
        self.assertNotEqual(receipt.actor_ref, "operator")
        self.assertNotIn("operator", receipt.actor_ref)
        self.assertLessEqual(len(receipt.impact.affected_public_ids), 50)
        self.assertNotIn("secret contact", repr(receipt))
        self.assertNotIn("alice@example.test", repr(receipt))
        self.assertEqual(len(holds.events[0].private_note_sha256), 64)

    def test_impact_receipt_truncates_ids_but_preserves_total_and_binding(self):
        finding = HoldScopeTarget.finding("finding:bulk")
        graph = BoundedDependencyGraph(
            records=tuple(
                PublicDependencyRecord(
                    f"public:{index:03d}",
                    (finding,),
                    refs(f"bulk:{index:03d}"),
                )
                for index in range(60)
            )
        )

        impact = graph.dry_run(finding)
        self.assertEqual(impact.affected_count, 60)
        self.assertEqual(len(impact.affected_public_ids), 50)
        self.assertTrue(impact.ids_truncated)
        self.assertEqual(len(impact.impact_binding_sha256), 64)

    def test_dependency_traversal_fails_closed_when_requested_depth_is_too_small(self):
        graph, target = graph_fixture()
        with self.assertRaisesRegex(
            ProvenanceQuarantineError,
            "HOLD_GRAPH_TRAVERSAL_BOUND_EXCEEDED",
        ):
            graph.dry_run(target["source_a"], max_depth=2)

    def test_domain_contract_exposes_no_delete_or_record_mutation_operation(self):
        graph, _ = graph_fixture()
        holds = registry()
        self.assertFalse(hasattr(holds, "delete"))
        self.assertFalse(hasattr(holds, "delete_hold"))
        self.assertFalse(hasattr(holds, "mutate_record"))
        with self.assertRaises(TypeError):
            graph.records[0].load_bearing_refs["source_version"] = "tampered"


if __name__ == "__main__":
    unittest.main()
