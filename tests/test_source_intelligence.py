import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.domain_vocabulary import ClaimType  # noqa: E402
from dichiarazioni_pubbliche.source_intelligence import (  # noqa: E402
    EVIDENCE_ROLES,
    EvidenceItem,
    SourceIntelligenceContract,
    SourceIntelligenceError,
    SourceRelation,
    assess_evidence_set,
    evidence_item_from_row,
    load_source_intelligence_contract,
)


class SourceIntelligenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_source_intelligence_contract()

    def item(
        self,
        source_id,
        *,
        evidence_id="e:1",
        value=63.2,
        publication_date="2026-09-01",
        reference_period="2026-07",
        metric="employment_rate_pct",
        unit="percent",
        dimensions=None,
        independence_group=None,
        rights_status="UNKNOWN",
        valid_from=None,
        valid_until=None,
        record_status="ACTIVE",
    ):
        return evidence_item_from_row(
            {
                "evidence_id": evidence_id,
                "source_id": source_id,
                "publication_date": publication_date,
                "reference_period": reference_period,
                "metric": metric,
                "unit": unit,
                "dimensions": dimensions or {},
                "value_numeric": value if isinstance(value, (int, float)) else None,
                "value_text": value if isinstance(value, str) else None,
                "independence_group": independence_group or source_id,
                "rights_status": rights_status,
                "valid_from": valid_from,
                "valid_until": valid_until,
                "record_status": record_status,
                "status": "APPROVED",
                "metadata": {"evidence_source_id": source_id},
            },
            self.contract,
        )

    def assess(self, evidence, **overrides):
        values = {
            "target_type": "ATOMIC_CLAIM",
            "target_id": "claim:test",
            "claim_type": "NUMERIC_STATISTIC",
            "statement_date": "2026-09-04",
            "claim_requirements": {
                "metric": "employment_rate_pct",
                "unit": "percent",
                "reference_period": "2026-07",
            },
            "evidence": evidence,
            "contract": self.contract,
        }
        values.update(overrides)
        return assess_evidence_set(**values)

    def test_contract_covers_every_claim_type_and_registry_source(self):
        self.assertEqual(
            set(self.contract.requirements_by_claim_type),
            {item.value for item in ClaimType},
        )
        evidence_registry = __import__("json").loads(
            (ROOT / "config" / "evidence-sources.v1.json").read_text()
        )
        self.assertEqual(
            set(self.contract.evidence_profiles_by_registry_id),
            {row["id"] for row in evidence_registry["sources"]},
        )
        self.assertEqual(len(self.contract.profiles), 13)

    def test_same_source_can_have_multiple_roles_without_global_rating(self):
        profile = self.contract.evidence_profiles_by_registry_id["istat-sdmx"]
        self.assertEqual(set(profile.roles), {"PRIMARY_RECORD", "OFFICIAL_STATISTICS"})
        self.assertTrue(set(profile.roles) <= set(EVIDENCE_ROLES))
        self.assertFalse(hasattr(profile, "trust_score"))
        self.assertFalse(hasattr(profile, "reliability_score"))

    def test_istat_numeric_exact_period_is_sufficient(self):
        result = self.assess([self.item("istat-sdmx")])
        self.assertEqual(result.status, "SUFFICIENT_FOR_RULE")
        self.assertEqual(result.qualifying_evidence_ids, ("e:1",))
        self.assertFalse(result.coverage_need_candidates)

    def test_missing_evidence_review_status_does_not_become_approved(self):
        # A registry match and a plausible observed value do not prove human
        # approval. This adapter may also receive incomplete external rows.
        row = {
            "evidence_id": "e:istat-unreviewed",
            "source_id": "istat-sdmx",
            "publication_date": "2026-09-01",
            "reference_period": "2026-07",
            "metric": "employment_rate_pct",
            "unit": "percent",
            "value_numeric": 63.2,
            "rights_status": "UNKNOWN",
        }
        for review_state in ("missing", None, "", "PENDING"):
            with self.subTest(review_state=review_state):
                candidate = dict(row)
                if review_state != "missing":
                    candidate["status"] = review_state
                evidence = evidence_item_from_row(candidate, self.contract)
                result = self.assess([evidence])
                self.assertNotEqual(evidence.status, "APPROVED")
                self.assertEqual(result.status, "INSUFFICIENT_PRIMARY_SOURCE")
                self.assertEqual(result.qualifying_evidence_ids, ())
                self.assertIn(
                    {"evidence_id": "e:istat-unreviewed", "reason": "EVIDENCE_NOT_APPROVED"},
                    result.rejected_evidence,
                )
                self.assertTrue(result.coverage_need_candidates)

        # An explicit approved observation from the guarded store remains valid.
        reviewed = evidence_item_from_row({**row, "status": "APPROVED"}, self.contract)
        self.assertEqual(self.assess([reviewed]).status, "SUFFICIENT_FOR_RULE")

    def test_istat_wrong_period_is_temporal_mismatch(self):
        result = self.assess(
            [self.item("istat-sdmx", reference_period="2026-06")]
        )
        self.assertEqual(result.status, "TEMPORAL_MISMATCH")
        self.assertTrue(result.coverage_need_candidates)

    def test_future_evidence_is_temporal_mismatch(self):
        result = self.assess(
            [self.item("istat-sdmx", publication_date="2026-09-05")]
        )
        self.assertEqual(result.status, "TEMPORAL_MISMATCH")

    def test_missing_statement_date_cannot_bypass_required_temporal_cutoff(self):
        result = self.assess(
            [self.item("istat-sdmx", publication_date="2030-01-01")],
            statement_date=None,
        )
        self.assertEqual(result.status, "TEMPORAL_MISMATCH")
        self.assertIn("STATEMENT_DATE_REQUIRED",
                      {row["reason"] for row in result.rejected_evidence})

    def test_invalid_date_suffix_cannot_be_truncated_into_qualified_evidence(self):
        for value in (
            "2026-09-01NOT_A_DATE",
            "2026-09-01T99:99:99Z",
            "2026-09-01T12:00:00Zextra",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(SourceIntelligenceError, "SOURCE_INTELLIGENCE_DATE_INVALID"):
                    self.assess([self.item("istat-sdmx", publication_date=value)])

    def test_valid_timestamp_with_timezone_retains_date_level_cutoff_semantics(self):
        accepted = self.assess([
            self.item("istat-sdmx", publication_date="2026-09-04T20:45:15+02:00")
        ])
        self.assertEqual(accepted.status, "SUFFICIENT_FOR_RULE")
        future = self.assess([
            self.item("istat-sdmx", publication_date="2026-09-05T00:00:01Z")
        ])
        self.assertEqual(future.status, "TEMPORAL_MISMATCH")

    def test_version_not_yet_effective_is_temporal_mismatch(self):
        result = self.assess(
            [
                self.item(
                    "istat-sdmx",
                    valid_from="2026-09-05",
                )
            ]
        )
        self.assertEqual(result.status, "TEMPORAL_MISMATCH")
        self.assertIn(
            "VERSION_NOT_YET_EFFECTIVE",
            {row["reason"] for row in result.rejected_evidence},
        )

    def test_expired_version_is_temporal_mismatch_with_end_exclusive_semantics(self):
        result = self.assess(
            [
                self.item(
                    "istat-sdmx",
                    valid_from="2026-01-01",
                    valid_until="2026-09-04",
                )
            ]
        )
        self.assertEqual(result.status, "TEMPORAL_MISMATCH")
        self.assertIn(
            "VERSION_NO_LONGER_EFFECTIVE",
            {row["reason"] for row in result.rejected_evidence},
        )

    def test_superseded_version_without_valid_until_fails_closed(self):
        result = self.assess(
            [
                self.item(
                    "istat-sdmx",
                    record_status="SUPERSEDED",
                )
            ]
        )
        self.assertEqual(result.status, "TEMPORAL_MISMATCH")
        self.assertIn(
            "SUPERSEDED_VERSION_WITHOUT_VALID_UNTIL",
            {row["reason"] for row in result.rejected_evidence},
        )

    def test_expired_record_without_valid_until_fails_closed(self):
        result = self.assess(
            [
                self.item(
                    "istat-sdmx",
                    record_status="EXPIRED",
                )
            ]
        )
        self.assertEqual(result.status, "TEMPORAL_MISMATCH")
        self.assertIn(
            "SUPERSEDED_VERSION_WITHOUT_VALID_UNTIL",
            {row["reason"] for row in result.rejected_evidence},
        )

    def test_expired_record_with_valid_until_uses_normal_end_exclusive_semantics(self):
        result = self.assess(
            [
                self.item(
                    "istat-sdmx",
                    valid_from="2026-01-01",
                    valid_until="2026-09-04",
                    record_status="EXPIRED",
                )
            ]
        )
        self.assertEqual(result.status, "TEMPORAL_MISMATCH")
        self.assertIn(
            "VERSION_NO_LONGER_EFFECTIVE",
            {row["reason"] for row in result.rejected_evidence},
        )

    def test_superseded_version_with_historical_interval_can_prove_past_statement(self):
        result = self.assess(
            [
                self.item(
                    "istat-sdmx",
                    record_status="SUPERSEDED",
                    valid_from="2026-01-01",
                    valid_until="2026-10-01",
                )
            ]
        )
        self.assertEqual(result.status, "SUFFICIENT_FOR_RULE")

    def test_gazzetta_legal_scope_succeeds_normattiva_alone_does_not(self):
        legal_kwargs = dict(
            target_type="ATOMIC_CLAIM",
            target_id="claim:legal",
            claim_type="LEGAL_POLICY_STATUS",
            statement_date="2026-09-04",
            claim_requirements={"jurisdiction": "IT"},
            contract=self.contract,
        )
        gazzetta = self.item(
            "gazzetta-ufficiale",
            metric=None,
            unit=None,
            reference_period=None,
            value="vigente",
        )
        result = assess_evidence_set(evidence=[gazzetta], **legal_kwargs)
        self.assertEqual(result.status, "SUFFICIENT_FOR_RULE")
        informational = self.item(
            "normattiva-opendata",
            metric=None,
            unit=None,
            reference_period=None,
            value="vigente",
        )
        result = assess_evidence_set(evidence=[informational], **legal_kwargs)
        self.assertEqual(result.status, "INSUFFICIENT_PRIMARY_SOURCE")
        self.assertIn("AUTHENTIC_LEGAL_TEXT", result.coverage_need_candidates[0].required_roles)

    def test_gazzetta_wrong_jurisdiction_is_scope_mismatch(self):
        result = assess_evidence_set(
            target_type="ATOMIC_CLAIM",
            target_id="claim:legal-eu",
            claim_type="LEGAL_POLICY_STATUS",
            statement_date="2026-09-04",
            claim_requirements={"jurisdiction": "EU"},
            evidence=[
                self.item(
                    "gazzetta-ufficiale",
                    metric=None,
                    unit=None,
                    reference_period=None,
                    value="vigente",
                )
            ],
            contract=self.contract,
        )
        self.assertEqual(result.status, "SCOPE_MISMATCH")

    def test_missing_required_legal_jurisdiction_cannot_match_any_scope(self):
        legal = self.item("gazzetta-ufficiale", metric=None, unit=None,
                          reference_period=None, value="vigente")
        result = assess_evidence_set(
            target_type="ATOMIC_CLAIM", target_id="claim:missing-jurisdiction",
            claim_type="LEGAL_POLICY_STATUS", statement_date="2026-09-04",
            claim_requirements={}, evidence=[legal], contract=self.contract,
        )
        self.assertEqual(result.status, "SCOPE_MISMATCH")

    def test_legal_role_cannot_borrow_another_role_authority_scope(self):
        legal = self.item("gazzetta-ufficiale", metric=None, unit=None,
                          reference_period=None, value="vigente")
        borrowed_scope = replace(legal.authority_scopes[0], role="SECONDARY_REFERENCE")
        false_authority = replace(
            legal, roles=(*legal.roles, "SECONDARY_REFERENCE"),
            authority_scopes=(borrowed_scope,),
        )
        result = assess_evidence_set(
            target_type="ATOMIC_CLAIM", target_id="claim:borrowed-role",
            claim_type="LEGAL_POLICY_STATUS", statement_date="2026-09-04",
            claim_requirements={"jurisdiction": "IT"},
            evidence=[false_authority], contract=self.contract,
        )
        self.assertEqual(result.status, "SCOPE_MISMATCH")

    def test_multiple_required_role_groups_do_not_demand_one_scope_match_all(self):
        base = self.contract.requirements_by_claim_type["LEGAL_POLICY_STATUS"]
        extra_role = replace(
            base.rules[0], id=base.rules[0].id + ":primary-record",
            parameters={"roles": ["PRIMARY_RECORD"]},
        )
        expanded = replace(base, rules=(extra_role, *base.rules))
        contract = replace(
            self.contract,
            requirement_profiles=tuple(
                expanded if profile.claim_type == base.claim_type else profile
                for profile in self.contract.requirement_profiles
            ),
        )
        legal = self.item("gazzetta-ufficiale", metric=None, unit=None,
                          reference_period=None, value="vigente")
        result = assess_evidence_set(
            target_type="ATOMIC_CLAIM", target_id="claim:multiple-roles",
            claim_type="LEGAL_POLICY_STATUS", statement_date="2026-09-04",
            claim_requirements={"jurisdiction": "IT"},
            evidence=[legal], contract=contract,
        )
        self.assertEqual(result.status, "SUFFICIENT_FOR_RULE")

    def test_expired_authority_scope_cannot_prove_legal_status(self):
        legal = self.item("gazzetta-ufficiale", metric=None, unit=None,
                          reference_period=None, value="vigente")
        expired_scope = replace(legal.authority_scopes[0], valid_until="2026-09-01")
        result = assess_evidence_set(
            target_type="ATOMIC_CLAIM", target_id="claim:scope-expired",
            claim_type="LEGAL_POLICY_STATUS", statement_date="2026-09-04",
            claim_requirements={"jurisdiction": "IT"},
            evidence=[replace(legal, authority_scopes=(expired_scope,))],
            contract=self.contract,
        )
        self.assertEqual(result.status, "TEMPORAL_MISMATCH")
        self.assertIn("AUTHORITY_SCOPE_TEMPORAL_MISMATCH",
                      {row["reason"] for row in result.rejected_evidence})

    def test_first_party_statement_does_not_corroborate_numeric_content(self):
        first_party = EvidenceItem(
            evidence_id="e:first-party",
            registry_source_id="manual:first-party",
            source_profile_id="profile:first-party",
            roles=("FIRST_PARTY_STATEMENT",),
            authority_scopes=(),
            publication_date="2026-09-01",
            reference_period="2026-07",
            rights_status="UNKNOWN",
            access_status="AVAILABLE",
            independence_group="first-party",
            metric="employment_rate_pct",
            unit="percent",
            value_numeric=63.2,
            status="APPROVED",
        )
        result = self.assess([first_party])
        self.assertEqual(result.status, "INSUFFICIENT_PRIMARY_SOURCE")

    def test_conflicting_qualified_primary_records_hold(self):
        result = self.assess(
            [
                self.item("istat-sdmx", evidence_id="e:a", value=63.2),
                self.item(
                    "istat-publications",
                    evidence_id="e:b",
                    value=63.1,
                    independence_group="istat-release-b",
                ),
            ]
        )
        self.assertEqual(result.status, "CONFLICTING_EVIDENCE")
        self.assertEqual(len(result.conflict_groups), 1)

    def test_missing_primary_emits_coverage_need_candidate(self):
        result = self.assess([])
        self.assertEqual(result.status, "INSUFFICIENT_PRIMARY_SOURCE")
        self.assertTrue(
            any(need.requirement_kind == "ROLE_ANY" for need in result.coverage_need_candidates)
        )

    def test_two_syndicated_items_do_not_satisfy_two_independent_lineages(self):
        base = self.contract.requirements_by_claim_type["NUMERIC_STATISTIC"]
        rules = []
        for rule in base.rules:
            if rule.kind == "MIN_INDEPENDENT_LINEAGES":
                rules.append(replace(rule, parameters={"minimum": 2}))
            else:
                rules.append(rule)
        strict = replace(base, id=base.id + ":two", rules=tuple(rules))
        contract = SourceIntelligenceContract(
            source_version=self.contract.source_version,
            requirement_version=self.contract.requirement_version,
            profiles=self.contract.profiles,
            requirement_profiles=tuple(
                strict if item.claim_type == strict.claim_type else item
                for item in self.contract.requirement_profiles
            ),
        )
        first = self.item(
            "istat-sdmx", evidence_id="e:a", independence_group="agency-release"
        )
        second = self.item(
            "istat-publications", evidence_id="e:b", independence_group="copy-b"
        )
        relation = SourceRelation(
            from_profile_id=second.source_profile_id,
            to_profile_id=first.source_profile_id,
            relation_type="SYNDICATED_FROM",
            status="APPROVED",
            evidence_basis={"derivation_candidate_id": "derivation:test"},
        )
        result = self.assess(
            [first, second], contract=contract, relations=[relation]
        )
        self.assertEqual(result.status, "INSUFFICIENT_INDEPENDENCE")

    def test_syndicated_article_chain_counts_as_one_lineage_not_three(self):
        base = self.contract.requirements_by_claim_type["NUMERIC_STATISTIC"]
        rules = []
        for rule in base.rules:
            if rule.kind == "MIN_INDEPENDENT_LINEAGES":
                rules.append(replace(rule, parameters={"minimum": 2}))
            else:
                rules.append(rule)
        strict = replace(base, id=base.id + ":chain", rules=tuple(rules))
        contract = SourceIntelligenceContract(
            source_version=self.contract.source_version,
            requirement_version=self.contract.requirement_version,
            profiles=self.contract.profiles,
            requirement_profiles=tuple(
                strict if item.claim_type == strict.claim_type else item
                for item in self.contract.requirement_profiles
            ),
        )
        upstream = self.item(
            "istat-sdmx",
            evidence_id="e:upstream",
            independence_group="article:upstream",
        )
        copy_a = self.item(
            "istat-publications",
            evidence_id="e:copy-a",
            independence_group="article:copy-a",
        )
        copy_b = self.item(
            "eurostat-api",
            evidence_id="e:copy-b",
            independence_group="article:copy-b",
        )
        relations = (
            SourceRelation(
                from_profile_id=copy_a.source_profile_id,
                to_profile_id=upstream.source_profile_id,
                relation_type="SYNDICATED_FROM",
                status="APPROVED",
                evidence_basis={"derivation_candidate_id": "derivation:copy-a"},
            ),
            SourceRelation(
                from_profile_id=copy_b.source_profile_id,
                to_profile_id=copy_a.source_profile_id,
                relation_type="SYNDICATED_FROM",
                status="APPROVED",
                evidence_basis={"derivation_candidate_id": "derivation:copy-b"},
            ),
        )
        result = self.assess(
            [upstream, copy_a, copy_b],
            contract=contract,
            relations=relations,
        )
        self.assertEqual(result.status, "INSUFFICIENT_INDEPENDENCE")
        self.assertTrue(result.missing_rules)

    def test_rights_hold_fails_closed(self):
        result = self.assess(
            [self.item("istat-sdmx", rights_status="RIGHTS_HOLD")]
        )
        self.assertEqual(result.status, "ACCESS_OR_RIGHTS_BLOCKED")

    def test_unknown_source_identity_fails_closed(self):
        unknown = self.item("istat-sdmx")
        unknown = replace(
            unknown,
            registry_source_id="unknown",
            source_profile_id=None,
            roles=(),
            authority_scopes=(),
        )
        result = self.assess([unknown])
        self.assertEqual(result.status, "UNRESOLVED_SOURCE_IDENTITY")

    def test_high_context_inference_never_auto_suffices(self):
        evidence = EvidenceItem(
            evidence_id="e:expert",
            registry_source_id="manual:expert",
            source_profile_id="profile:expert",
            roles=("EXPERT_SYNTHESIS",),
            authority_scopes=(),
            publication_date="2026-09-01",
            reference_period=None,
            rights_status="UNKNOWN",
            access_status="AVAILABLE",
            independence_group="expert-a",
            status="APPROVED",
        )
        result = assess_evidence_set(
            target_type="ATOMIC_CLAIM",
            target_id="claim:causal",
            claim_type="CAUSAL_CLAIM",
            statement_date="2026-09-04",
            claim_requirements={},
            evidence=[evidence],
            contract=self.contract,
        )
        self.assertEqual(result.status, "NEEDS_REVIEW")


if __name__ == "__main__":
    unittest.main()
