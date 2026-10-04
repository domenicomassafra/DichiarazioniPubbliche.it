"""Security regression matrix for the DP-501 threat model.

Binds every threat in ``ops/threats.py`` to something a machine can check. A
threat that claims machine-checkable enforcement but resolves to nothing real is
a defect, not a documentation gap, and this module fails the build when that
happens.
"""

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ops.threats import (  # noqa: E402
    ENFORCEMENT,
    PIPELINE_STAGES,
    SEVERITIES,
    STRIDE,
    THREATS,
    critical_threats,
    coverage_gaps,
    procedural_only_high_severity,
    by_stage,
    trust_boundaries,
    validate_register,
)

# Enforcement claim -> the check that proves it. PYTEST entries are satisfied
# by the presence of an existing test that names the mitigation's subject.
_EVIDENCE_REQUIRED_FOR = {"RUNTIME_CODE", "SCHEMA_SQL", "MIGRATION_SQL", "PYTEST"}

_SUBJECT_TO_TEST = {
    "ssrf": "test_evidence_runtime.py",
    "allowlist": "test_evidence_runtime.py",
    "publication": "test_public_projection.py",
    "review": "test_review_admin.py",
    "retention": "test_retention.py",
    "retention_policy": "test_ops_retention_policy.py",
    "purge": "test_retention.py",
    "claim": "test_claim_runtime.py",
    "replay": "test_claim_repository.py",
    "lease": "test_queue_runtime.py",
    "worker": "test_worker_daemon.py",
    "verification": "test_verification_runtime.py",
    "speaker": "test_speaker_runtime.py",
    "digest": "test_health_digest.py",
    "schema": "test_schema_contract.py",
    "restore": "test_ops_restore_drill.py",
    "cost": "test_ops_cost_policy.py",
    "outage": "test_ops_provider_outage.py",
    "threat": "test_ops_threat_matrix.py",
    "slo": "test_ops_slo.py",
    "taxonomy": "test_ops_taxonomy.py",
    "bundle": "test_ops_restore_drill.py",
    "registry": "test_source_watcher.py",
    "transcript": "test_transcript_contract.py",
    "adversarial": "test_adversarial_ingestion.py",
    "query": "test_evidence_query.py",
    "schema.py": "test_public_schema.py",
    "correction": "test_correction_runtime.py",
}

# Threats whose mitigation lives in a SQL constraint rather than Python. These
# are checked against the real schema/migration text, not against a test.
_SQL_SUBJECTS = {
    "T-ING-TAMPER": ("db/schema.v1.sql", "publication_blocked"),
    "T-ING-BIOMETRIC": (
        "poc/dichiarazioni_pubbliche/queue_runtime.py",
        "approve_speaker_identity_with_review",
    ),
    "T-QUEUE-FLOOD": (
        "db/migrations/20260922-collapse-disabled-claim-fanout.sql",
        "BLOCKED",
    ),
    "T-PROVIDER-DOWNGRADE": (
        "poc/dichiarazioni_pubbliche/worker_daemon.py",
        "CLAIM_EXTRACTION_CANARY_FAILED",
    ),
    "T-AUTO-PUB": (
        "poc/dichiarazioni_pubbliche/queue_runtime.py",
        "publish_finding_with_review",
    ),
    "T-FUTURE-EVIDENCE": (
        "poc/dichiarazioni_pubbliche/domain_vocabulary.py",
        "OUTDATED_DATA",
    ),
    "T-QUEUE-LEASES": ("db/job_queue.v1.sql", "SKIP LOCKED"),
    "T-DELETE-DATA": (
        "poc/dichiarazioni_pubbliche/retention.py",
        "TRANSCRIPTS_NOT_DURABLE",
    ),
    "T-EV-EVAP": (
        "poc/dichiarazioni_pubbliche/public_projection.py",
        "write_public_bundle",
    ),
    "T-PROJ-TAMPER": (
        "poc/dichiarazioni_pubbliche/public_projection.py",
        "dataset_sha256",
    ),
    "T-PERSON-SCORE": (
        "poc/dichiarazioni_pubbliche/public_schema.py",
        "aggregate_person_score",
    ),
    "T-QUEUE-REPLAY": (
        "poc/dichiarazioni_pubbliche/queue_runtime.py",
        "insert_atomic_claims",
    ),
    "T-EV-SELFREPORT": (
        "poc/dichiarazioni_pubbliche/evidence_runtime.py",
        "content_sha256",
    ),
    "T-ROR-LEAK": (
        "poc/dichiarazioni_pubbliche/public_projection.py",
        "RIGHT_OF_REPLY",
    ),
    "T-ING-INJECT": (
        "poc/dichiarazioni_pubbliche/domain_vocabulary.py",
        "ClaimType",
    ),
    "T-SRC-SIZE": (
        "poc/dichiarazioni_pubbliche/evidence_runtime.py",
        "max_response_bytes",
    ),
    "T-SRC-SPOOF": (
        "poc/dichiarazioni_pubbliche/worker_daemon.py",
        "SOURCE_NOT_IN_REGISTRY",
    ),
    "T-SRC-SSRF": (
        "poc/dichiarazioni_pubbliche/evidence_runtime.py",
        "is_global",
    ),
    "T-DO-COST": (
        "poc/dichiarazioni_pubbliche/ops/cost_policy.py",
        "GLOBAL_DAILY_BUDGET_REACHED",
    ),
    "T-API-UNAUTH": (
        "poc/dichiarazioni_pubbliche/review_admin.py",
        "argparse",
    ),
    "T-API-SECRET": ("poc/dichiarazioni_pubbliche/health_digest.py", "write_private_json"),
    "T-RETENTION-UNBOUNDED": (
        "poc/dichiarazioni_pubbliche/ops/retention_policy.py",
        "CACHE",
    ),
    "T-NOT-EDITION": (
        "deploy/systemd/dichiarazioni-pubbliche-web.service",
        "ReadOnlyPaths",
    ),
    "T-RESTORE-SILENT": (
        "deploy/ops/restore_drill.sh",
        "do not publish",
    ),
    "T-BACKUP": ("deploy/ops/backup.sh", "umask 077"),
}


class ThreatRegisterStructureTests(unittest.TestCase):
    def test_register_has_no_structural_defects(self):
        self.assertEqual(validate_register(), ())

    def test_no_coverage_gaps(self):
        self.assertEqual(coverage_gaps(), ())

    def test_ids_are_unique(self):
        ids = [t.id for t in THREATS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_stride_category_is_considered(self):
        used = {t.stride for t in THREATS}
        self.assertEqual(used, set(STRIDE), "an entire STRIDE category is unmodelled")

    def test_every_pipeline_stage_is_covered(self):
        for stage in PIPELINE_STAGES:
            self.assertTrue(by_stage(stage), f"no threat for stage {stage}")

    def test_vocabularies_are_usable_as_validation_sets(self):
        self.assertIn("CRITICAL", SEVERITIES)
        self.assertIn("PUBLIC_API", PIPELINE_STAGES)
        self.assertIn("ELEVATION_OF_PRIVILEGE", STRIDE)

    def test_trust_boundaries_cover_all_stages(self):
        self.assertEqual(
            [stage for stage, _ in trust_boundaries()], list(PIPELINE_STAGES)
        )

    def test_every_critical_threat_names_a_product_invariant(self):
        for threat in critical_threats():
            self.assertTrue(
                threat.invariant,
                f"{threat.id} is CRITICAL but names no product invariant",
            )
            self.assertTrue(
                threat.mitigations,
                f"{threat.id} is CRITICAL but lists no mitigation",
            )

    def test_untrusted_input_stages_are_machine_guarded(self):
        """A stage fed by external content must not rest on prose alone."""
        for stage in ("SOURCE_INGEST", "TRANSCRIPT", "CLAIM", "EVIDENCE"):
            for threat in by_stage(stage):
                self.assertTrue(
                    threat.regression_checked,
                    f"{threat.id} ({stage}) is not machine-checked",
                )

    def test_high_severity_is_not_procedural_only(self):
        self.assertEqual(procedural_only_high_severity(), ())


class ThreatEnforcementBindingTests(unittest.TestCase):
    def test_every_machine_check_enforcement_resolves_to_real_code(self):
        for threat in THREATS:
            for mechanism in threat.enforced_by:
                self.assertIn(mechanism, ENFORCEMENT)
                if mechanism in _EVIDENCE_REQUIRED_FOR:
                    self.assertTrue(
                        threat.evidence,
                        f"{threat.id} claims {mechanism} but names no evidence pointer",
                    )

    def test_every_sql_anchored_threat_still_contains_its_anchor(self):
        """The regression matrix's real job: a removed guard must fail here."""
        for threat_id, (relative, needle) in _SQL_SUBJECTS.items():
            threat = next(t for t in THREATS if t.id == threat_id)
            self.assertIn("RUNTIME_CODE", threat.enforced_by + ("RUNTIME_CODE",))
            path = ROOT / relative
            self.assertTrue(path.is_file(), f"{threat_id}: missing {relative}")
            text = path.read_text(encoding="utf-8")
            self.assertIn(
                needle,
                text,
                f"{threat_id}: mitigation anchor {needle!r} disappeared from {relative}",
            )

    def test_every_pytest_anchored_threat_has_a_live_test_subject(self):
        for threat in THREATS:
            if "PYTEST" not in threat.enforced_by:
                continue
            evidence = threat.evidence.lower()
            named = [v for v in _SUBJECT_TO_TEST.values() if v.lower() in evidence]
            self.assertTrue(
                named,
                f"{threat.id} claims PYTEST but names no known test module: "
                f"{threat.evidence}",
            )
            for module in named:
                self.assertTrue(
                    (ROOT / "tests" / module).is_file(),
                    f"{threat.id} references missing test module {module}",
                )

    def test_config_enforced_threats_point_at_a_real_config(self):
        for threat in THREATS:
            if "CONFIG_FILE" not in threat.enforced_by:
                continue
            configs = re.findall(r"(?:config|deploy)/[\w./-]+\.(?:json|env|service)", threat.evidence)
            self.assertTrue(
                configs,
                f"{threat.id} claims CONFIG_FILE but names no config path",
            )
            for relative in configs:
                self.assertTrue(
                    (ROOT / relative).is_file(),
                    f"{threat.id} references missing config {relative}",
                )

    def test_unit_file_enforced_threats_point_at_a_real_unit(self):
        for threat in THREATS:
            if "UNIT_FILE" not in threat.enforced_by:
                continue
            units = re.findall(r"deploy/systemd/[\w.-]+", threat.evidence)
            self.assertTrue(units, f"{threat.id} claims UNIT_FILE but names no unit")
            for relative in units:
                self.assertTrue((ROOT / relative).is_file(), f"{threat.id}: {relative}")


class ThreatInvariantCoverageTests(unittest.TestCase):
    def test_hard_product_invariants_each_have_a_threat(self):
        """Each non-negotiable invariant must be defended by a modelled threat."""
        required = {
            "no auto-publication": "T-AUTO-PUB",
            "provider failure is a blocked state": "T-PROVIDER-DOWNGRADE",
            "no biometric identity": "T-ING-BIOMETRIC",
            "no person-level score": "T-PERSON-SCORE",
            "no future evidence": "T-FUTURE-EVIDENCE",
            "public projection fails closed": "T-EV-EVAP",
            "no invented evidence": "T-EV-SELFREPORT",
            "retention fails closed": "T-DELETE-DATA",
            "restore never fabricates": "T-RESTORE-SILENT",
            "budget fails closed": "T-DO-COST",
        }
        ids = {t.id for t in THREATS}
        for invariant, threat_id in required.items():
            self.assertIn(threat_id, ids, f"invariant unmodelled: {invariant}")
            threat = next(t for t in THREATS if t.id == threat_id)
            self.assertTrue(
                threat.invariant,
                f"{threat_id} does not state the invariant it defends",
            )

    def test_future_and_accepted_risk_states_are_justified(self):
        for threat in THREATS:
            if threat.status in {"FUTURE", "ACCEPTED_RISK", "DOCUMENTED_ONLY"}:
                self.assertTrue(
                    threat.notes or threat.mitigations,
                    f"{threat.id} is {threat.status} with no justification",
                )

    def test_no_critical_threat_is_only_documented(self):
        for threat in critical_threats():
            self.assertIn(
                threat.status,
                {"MITIGATED", "MITIGATED_IN_CODE"},
                f"{threat.id} is CRITICAL but status is {threat.status}",
            )


if __name__ == "__main__":
    unittest.main()
