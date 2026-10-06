"""Machine-readable threat register for the Dichiarazioni Pubbliche pipeline (DP-501).

This module is the single canonical inventory of STRIDE-style threats over the
real ingestion-to-publication pipeline:

    source ingest -> transcript -> claim -> evidence -> finding
                 -> public projection -> public API

It is *pure*: it holds data plus pure predicates over that data. It performs no
I/O, opens no sockets, and imports nothing from the runtime daemons. Its job is
to make the security posture of the system auditable by code rather than by
prose, and to make "a mitigation exists" and "the mitigation is machine-checked"
two separately verifiable claims.

The companion regression matrix in ``tests/test_ops_threat_matrix.py`` binds
each ``enforced_by`` entry to a real, runnable check (a test, a SQL assertion,
a config file, or a fail-closed helper). A threat that claims machine-checkable
enforcement but has no live check is a defect, not a documentation gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


# --- Enumerations -----------------------------------------------------------
# Deliberately closed vocabularies: an unknown value is a bug, and the pure
# `validate_register` predicate below turns an unknown value into a hard
# failure rather than a silently-unreviewed threat.

STRIDE = (
    "SPOOFING",
    "TAMPERING",
    "REPUDIATION",
    "INFORMATION_DISCLOSURE",
    "DENIAL_OF_SERVICE",
    "ELEVATION_OF_PRIVILEGE",
)

PIPELINE_STAGES = (
    "SOURCE_INGEST",
    "TRANSCRIPT",
    "CLAIM",
    "EVIDENCE",
    "FINDING",
    "PUBLIC_PROJECTION",
    "PUBLIC_API",
)

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

# Status vocabulary. `DOCUMENTED_ONLY` is explicitly a weaker state and the
# regression matrix fails if a CRITICAL/HIGH threat regresses to it.
STATUSES = (
    "MITIGATED",
    "MITIGATED_IN_CODE",
    "DOCUMENTED_ONLY",
    "ACCEPTED_RISK",
    "FUTURE",
)

# Enforcement mechanisms we are willing to claim. Each one must be resolvable
# to something a machine can check.
ENFORCEMENT = (
    "PYTEST",
    "SCHEMA_SQL",
    "MIGRATION_SQL",
    "RUNTIME_CODE",
    "CONFIG_FILE",
    "UNIT_FILE",
    "OPERATIONAL_PROCEDURE",
)

# Only these are permitted to be non-code enforcement for a high-severity
# threat; everything else must be machine-checked.
_PROCEDURAL_ONLY_ALLOWED = {"T-NOT-EDITION", "T-COST-BUDGET-EXHAUSTED"}


@dataclass(frozen=True)
class Threat:
    """One row of the threat model."""

    id: str
    stride: str
    stage: str
    title: str
    asset: str
    attack: str
    impact: str
    likelihood: str
    severity: str
    status: str
    mitigations: tuple[str, ...]
    enforced_by: tuple[str, ...]
    invariant: str = ""
    evidence: str = ""
    notes: str = ""

    @property
    def machine_checked(self) -> bool:
        """True when at least one enforcement is a machine-checkable artifact."""
        return any(m != "OPERATIONAL_PROCEDURE" for m in self.enforced_by)

    @property
    def regression_checked(self) -> bool:
        """True when a check would actually fail if the mitigation regressed."""
        return any(
            m in {"PYTEST", "SCHEMA_SQL", "MIGRATION_SQL", "CONFIG_FILE", "UNIT_FILE"}
            for m in self.enforced_by
        )


# --- The register -----------------------------------------------------------
#
# Each entry is written against the *real* implementation, not an aspiration.
# `invariant` names the product invariant that the mitigation defends, so a
# future change that removes the invariant is visibly out of contract with the
# mitigation that was supposed to protect it.

THREATS: tuple[Threat, ...] = (
    Threat(
        id="T-SRC-SPOOF",
        stride="SPOOFING",
        stage="SOURCE_INGEST",
        title="Unverified source identity is laundered into attribution",
        asset="source.canonical_url / content_item.source_id",
        attack=(
            "An operator (or a tampered registry file) registers a look-alike "
            "host as a legitimate outlet; discovered content is then attributed "
            "to the real outlet's canonical name."
        ),
        impact="False provenance for every claim derived from that content.",
        likelihood="MEDIUM",
        severity="HIGH",
        status="MITIGATED",
        mitigations=(
            "Source Registry is an explicit, reviewable config/registry file; "
            "sources not present in the registry are refused "
            "(worker SOURCE_NOT_IN_REGISTRY, scheduler SKIPPED_UNSUPPORTED).",
            "Content identity is derived from platform + external id, not from "
            "a display name supplied by the remote host.",
        ),
        enforced_by=("CONFIG_FILE", "PYTEST"),
        invariant="Public claim attribution requires approved provenance.",
        evidence="config/source-registry.v1.json; tests/test_source_watcher.py",
    ),
    Threat(
        id="T-SRC-SSRF",
        stride="INFORMATION_DISCLOSURE",
        stage="SOURCE_INGEST",
        title="Discovery/evidence fetch reaches internal network (SSRF)",
        asset="MiniPC network position, internal services",
        attack=(
            "A feed entry or evidence candidate points at 169.254.169.254, "
            "localhost, or an RFC1918 host to reach cloud metadata or internal "
            "admin services."
        ),
        impact="Credential/metadata disclosure, internal service reachability.",
        likelihood="MEDIUM",
        severity="CRITICAL",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "HTTPS-only, userinfo/port rejection, DNS-resolved non-public "
            "address refusal, redirect re-validation at every hop.",
            "Host + path prefix + method allowlist per evidence source.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST", "CONFIG_FILE"),
        invariant="External content is validated at the acquisition boundary.",
        evidence=(
            "poc/dichiarazioni_pubbliche/evidence_runtime.py; "
            "poc/dichiarazioni_pubbliche/source_adapters.py; "
            "config/evidence-sources.v1.json; tests/test_evidence_runtime.py"
        ),
    ),
    Threat(
        id="T-SRC-SIZE",
        stride="DENIAL_OF_SERVICE",
        stage="SOURCE_INGEST",
        title="Unbounded response body exhausts worker memory/disk",
        asset="Worker process, private artifact store",
        attack="A remote endpoint streams an enormous or truncated body.",
        impact="Worker OOM, disk pressure, lost lease, dead-letter storm.",
        likelihood="MEDIUM",
        severity="HIGH",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "max_response_bytes cap on every fetch/discovery response; "
            "known Content-Length that disagrees with received bytes fails "
            "instead of being hashed or cached.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST", "CONFIG_FILE"),
        invariant="External content is validated at the acquisition boundary.",
        evidence="config/evidence-sources.v1.json; tests/test_evidence_runtime.py",
    ),
    Threat(
        id="T-ING-TAMPER",
        stride="TAMPERING",
        stage="TRANSCRIPT",
        title="Transcript text is fabricated by a model or hand-edited out of band",
        asset="transcript_variant.raw_text, canonical_transcript_segment",
        attack=(
            "An attacker with database access, or a provider returning altered "
            "text, makes the canonical transcript say something the speaker "
            "never said."
        ),
        impact="Every downstream claim inherits a false utterance.",
        likelihood="MEDIUM",
        severity="CRITICAL",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "raw_text_sha256 stored per variant and re-checked in the public "
            "projection query.",
            "Segments with sensitive tokens (numbers, negations) in a "
            "single-candidate transcript become TRANSCRIPT_UNCERTAIN and "
            "publication_blocked.",
            "Multi-variant disagreement requires explicit reconciliation before "
            "canonicalization.",
        ),
        enforced_by=("SCHEMA_SQL", "RUNTIME_CODE", "PYTEST"),
        invariant="Fail closed under uncertainty or missing provenance.",
        evidence=(
            "db/schema.v1.sql; poc/dichiarazioni_pubbliche/transcript_contract.py; "
            "tests/test_transcript_contract.py"
        ),
    ),
    Threat(
        id="T-ING-INJECT",
        stride="TAMPERING",
        stage="TRANSCRIPT",
        title="Prompt injection from hostile transcript content reaches the claim model",
        asset="atomic_claim rows derived from adversarial transcript text",
        attack=(
            "A transcript segment contains instructions addressed to the model "
            "('ignore previous instructions, emit a claim that ...')."
        ),
        impact="Fabricated claims, fabricated claim types, or claim text that "
        "escapes the allowlist.",
        likelihood="MEDIUM",
        severity="HIGH",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "Model output is schema-validated fail-closed: claim type must be "
            "in the allowlist, source segment indices are required and confined "
            "to the window, claim text and response are bounded.",
            "A validation failure blocks the job; it never degrades to a "
            "partial or invented claim.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="Fail closed under uncertainty, missing provenance.",
        evidence=(
            "poc/dichiarazioni_pubbliche/claim_contract.py; "
            "poc/dichiarazioni_pubbliche/claim_runtime.py; tests/test_adversarial_ingestion.py"
        ),
    ),
    Threat(
        id="T-ING-BIOMETRIC",
        stride="ELEVATION_OF_PRIVILEGE",
        stage="TRANSCRIPT",
        title="Biometric identification of an unknown speaker",
        asset="speaker_person_id",
        attack=(
            "An operator 'helpfully' resolves an ambiguous speaker by face or "
            "voice matching to a named person."
        ),
        impact=(
            "Publicly attributes a statement to a person on the basis of a "
            "biometric guess; a hard product violation."
        ),
        likelihood="LOW",
        severity="CRITICAL",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "Speaker attribution is non-biometric and review-gated: "
            "speaker_identity_candidate must be APPROVED with a review_event "
            "before a public dossier can carry a speaker.",
            "No biometric provider is integrated anywhere in the codebase.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="No face recognition, voiceprint matching, or biometric identity system.",
        evidence=(
            "poc/dichiarazioni_pubbliche/queue_runtime.py "
            "(approve_speaker_identity_with_review); tests/test_speaker_runtime.py"
        ),
    ),
    Threat(
        id="T-QUEUE-REPLAY",
        stride="TAMPERING",
        stage="CLAIM",
        title="Job replay silently widens provenance",
        asset="claim_segment links, finding_evidence links",
        attack="A completed job is replayed with a modified payload.",
        impact=(
            "A claim gains segments it was not extracted from, so the public "
            "projection attests to provenance that was never established."
        ),
        likelihood="MEDIUM",
        severity="HIGH",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "Replaying a claim may add its claim_segments; replaying an "
            "existing claim may not append further segments.",
            "A finding is created only when claim, assessment, and the "
            "verified evidence set coincide with the verification run, and its "
            "finding_evidence links are written in the same insert.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="Replays are idempotent and must not silently widen provenance.",
        evidence=(
            "poc/dichiarazioni_pubbliche/queue_runtime.py; tests/test_claim_repository.py"
        ),
    ),
    Threat(
        id="T-QUEUE-LEASES",
        stride="REPUDIATION",
        stage="CLAIM",
        title="Concurrent workers double-execute or zombie a job",
        asset="processing_job state machine",
        attack="A worker dies mid-job; a second worker picks the same job.",
        impact=(
            "Unreproducible provenance, or a job stuck in RUNNING forever "
            "hiding a real failure."
        ),
        likelihood="HIGH",
        severity="MEDIUM",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "SKIP LOCKED claim with a lease; lease expiry reaper returns jobs "
            "to the queue; local 0600 lock file prevents timer/manual overlap.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="Each stage persists enough provenance to reproduce its output.",
        evidence="db/job_queue.v1.sql; tests/test_queue_runtime.py; tests/test_worker_daemon.py",
    ),
    Threat(
        id="T-EV-EVAP",
        stride="INFORMATION_DISCLOSURE",
        stage="EVIDENCE",
        title="Raw transcript or evidence excerpt reaches the public projection",
        asset="public projection bundle, static site",
        attack=(
            "A private raw_text or evidence body is added to the projection "
            "payload, or a projection file is left behind after a correction."
        ),
        impact=(
            "Publication of private operational data; a superseded dossier stays "
            "publicly reachable."
        ),
        likelihood="MEDIUM",
        severity="CRITICAL",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "The projection query exposes provenance identifiers only; the "
            "dossier contract is validated and a contract-violating row is "
            "omitted rather than sanitized into something publishable.",
            "write_public_bundle removes projection-owned claim files that the "
            "next bundle does not contain.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="Public projection must fail closed and not expose raw bodies.",
        evidence="poc/dichiarazioni_pubbliche/public_projection.py; tests/test_public_projection.py",
    ),
    Threat(
        id="T-EV-SELFREPORT",
        stride="SPOOFING",
        stage="EVIDENCE",
        title="Invented evidence URL or model-invented query",
        asset="evidence.url, evidence.content_sha256",
        attack=(
            "A model 'suggests' a plausible official URL, or a fetch is recorded "
            "as successful without the content actually being observed."
        ),
        impact="Fabricated citations, which is a truthfulness failure of the "
        "highest order for this product.",
        likelihood="MEDIUM",
        severity="CRITICAL",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "Evidence is content-addressed by hash of the actually fetched "
            "bytes; a Content-Length/body mismatch fails the fetch instead of "
            "caching a partial body.",
            "Queries are compiled deterministically by evidence_query, not "
            "generated as free-text URLs by a model.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="Evidence URLs must be validated by code, not invented.",
        evidence=(
            "poc/dichiarazioni_pubbliche/evidence_runtime.py; "
            "poc/dichiarazioni_pubbliche/evidence_query.py; tests/test_evidence_query.py"
        ),
    ),
    Threat(
        id="T-AUTO-PUB",
        stride="ELEVATION_OF_PRIVILEGE",
        stage="FINDING",
        title="Auto-publication of a model-produced finding",
        asset="finding.publication_status",
        attack=(
            "Any code path sets publication_status to a published value without "
            "an APPROVED review_event tied to the current provenance."
        ),
        impact=(
            "Unreviewed output becomes public record. This is the product's "
            "primary invariant and the most damaging single failure."
        ),
        likelihood="LOW",
        severity="CRITICAL",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "Publication requires publish_finding_with_review, which writes the "
            "review_event in the same transaction; generic status helpers "
            "reject APPROVED for evidence/observations.",
            "A successful model run produces at most a finding *draft*.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="No automatic publication merely because a model produced an answer.",
        evidence="poc/dichiarazioni_pubbliche/queue_runtime.py; tests/test_review_admin.py",
    ),
    Threat(
        id="T-FUTURE-EVIDENCE",
        stride="TAMPERING",
        stage="FINDING",
        title="Future evidence used to judge an earlier statement",
        asset="verification_run.assessment",
        attack=(
            "A counterexample published after the statement date is used to "
            "label the original statement false as of the time it was made."
        ),
        impact="A time-travel verdict; historically false record.",
        likelihood="MEDIUM",
        severity="HIGH",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "Verification is bounded to the statement date; later information "
            "yields OUTDATED_DATA, not FACTUALLY_FALSE.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="No future evidence to judge an earlier claim.",
        evidence=(
            "poc/dichiarazioni_pubbliche/domain_vocabulary.py; "
            "poc/dichiarazioni_pubbliche/verification_runtime.py; "
            "tests/test_verification_runtime.py"
        ),
    ),
    Threat(
        id="T-PERSON-SCORE",
        stride="ELEVATION_OF_PRIVILEGE",
        stage="FINDING",
        title="Person-level trust/reliability score leaks into the public model",
        asset="public schema, JSON-LD",
        attack="An aggregate or numeric per-person field is added to a dossier.",
        impact=(
            "The product becomes a person ranking, violating political-neutrality "
            "invariants regardless of how well-intentioned the aggregation is."
        ),
        likelihood="LOW",
        severity="CRITICAL",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "Dossier contract and JSON-LD builder reject unknown fields; "
            "claim-level only, aggregate_person_score is asserted False.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="No person-level truth/trust/reliability score or ranking.",
        evidence="poc/dichiarazioni_pubbliche/public_schema.py; tests/test_public_schema.py",
    ),
    Threat(
        id="T-ROR-LEAK",
        stride="INFORMATION_DISCLOSURE",
        stage="FINDING",
        title="Right of reply or correction becomes public without processing",
        asset="right_of_reply, correction, projection",
        attack=(
            "A right-of-reply body is written to the public projection while "
            "its reanalysis trigger is still PENDING."
        ),
        impact=(
            "An allegation-response is published without review, and against a "
            "finding version the system has not re-examined."
        ),
        likelihood="LOW",
        severity="HIGH",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "Projection requires a PROCESSED trigger of the matching type plus "
            "review events on both finding versions.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="Corrections and rights of reply are append-only and private by default.",
        evidence=(
            "poc/dichiarazioni_pubbliche/queue_runtime.py; "
            "poc/dichiarazioni_pubbliche/correction_runtime.py; tests/test_correction_runtime.py"
        ),
    ),
    Threat(
        id="T-PROJ-TAMPER",
        stride="TAMPERING",
        stage="PUBLIC_PROJECTION",
        title="Public bundle is edited in place or served stale",
        asset="index.json, index.jsonld, claims/*.{json,html,jsonld}",
        attack=(
            "An operator hand-edits the generated bundle, or a crash leaves an "
            "old dossier publicly reachable after its gate stopped holding."
        ),
        impact="Public record that the pipeline never produced.",
        likelihood="MEDIUM",
        severity="HIGH",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "dataset_sha256 over the canonical dossier list; atomic writes; "
            "stale projection-owned claim files removed on every rebuild.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST", "OPERATIONAL_PROCEDURE"),
        invariant="Public output is a projection, never an operational database dump.",
        evidence=(
            "poc/dichiarazioni_pubbliche/public_projection.py; "
            "tests/test_public_projection.py; docs/ops/restore-drill.md; "
            "deploy/ops/verify_projection_bundle.py"
        ),
    ),
    Threat(
        id="T-API-UNAUTH",
        stride="ELEVATION_OF_PRIVILEGE",
        stage="PUBLIC_API",
        title="Administrative surface exposed over HTTP",
        asset="Review/approval CLI, future admin endpoints",
        attack=(
            "A future HTTP surface ships without AuthN/AuthZ/CSRF and lets an "
            "anonymous caller approve a finding or unblock a job."
        ),
        impact="Total loss of the review gate; arbitrary publication.",
        likelihood="LOW",
        severity="HIGH",
        status="FUTURE",
        mitigations=(
            "No authenticated admin surface exists today; review is "
            "CLI/local-operator only and is therefore not a runtime-exposed "
            "attack surface.",
            "Design work is tracked as DP-507 and must land *before* any such "
            "surface exists, not after.",
        ),
        enforced_by=("PYTEST", "OPERATIONAL_PROCEDURE"),
        invariant="Administrative review is local/operator-only until a "
        "dedicated authenticated service is designed.",
        evidence=(
            "tests/test_review_admin.py; docs/tickets/DP-507-admin-auth-surface.md; "
            "docs/ops/threat-model.md"
        ),
    ),
    Threat(
        id="T-API-SECRET",
        stride="INFORMATION_DISCLOSURE",
        stage="PUBLIC_API",
        title="Provider credential or database URL leaks into a public artifact",
        asset="Repository, public projection, logs",
        attack="A credential is committed or written into a public bundle.",
        impact="Provider spend abuse; operational database compromise.",
        likelihood="LOW",
        severity="CRITICAL",
        status="MITIGATED",
        mitigations=(
            "Runtime secrets live only in ~/.config/dichiarazioni-pubbliche/*.env, never in "
            "the repository; the health digest asserts it carries no secrets, "
            "no raw errors, and no transcript text.",
        ),
        enforced_by=("PYTEST", "UNIT_FILE"),
        invariant="No public database credentials or provider secrets in the repository.",
        evidence=(
            "tests/test_health_digest.py; "
            "deploy/systemd/dichiarazioni-pubbliche-worker.service; "
            "deploy/systemd/dichiarazioni-pubbliche-health.service"
        ),
    ),
    Threat(
        id="T-DO-COST",
        stride="DENIAL_OF_SERVICE",
        stage="SOURCE_INGEST",
        title="Provider spend explosion from a runaway or hostile source",
        asset="Provider account budget",
        attack=(
            "A source floods content; a retry storm; a canary regression "
            "re-enables paid fan-out at scale."
        ),
        impact="Unbounded financial loss on the maintainer's provider account.",
        likelihood="MEDIUM",
        severity="HIGH",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "Hard per-job / per-source-per-day / global-per-day caps enforced "
            "as a preflight before any paid lane; the queue holds only "
            "executable work, so a blocked provider does not accumulate "
            "materialized cost-bearing children.",
            "The cost model is a pure function (ops/cost_policy.py) that "
            "fails closed on unknown input.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="Budget caps fail closed.",
        evidence=(
            "poc/dichiarazioni_pubbliche/ops/cost_policy.py; "
            "poc/dichiarazioni_pubbliche/worker_daemon.py; tests/test_ops_cost_policy.py"
        ),
    ),
    Threat(
        id="T-QUEUE-FLOOD",
        stride="DENIAL_OF_SERVICE",
        stage="CLAIM",
        title="Write amplification from materializing non-executable work",
        asset="processing_job table",
        attack=(
            "A canary creates thousands of CLAIM_EXTRACT_WINDOW children while "
            "the provider is unavailable."
        ),
        impact=(
            "Queue noise that hides real blockers, wasted storage, and an "
            "operator digest dominated by one non-actionable cause."
        ),
        likelihood="MEDIUM",
        severity="MEDIUM",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "Windows are materialized only when capability + cost gates pass; "
            "1,467 blocked children were collapsed back to 11 blocked parents "
            "by migration 20260922-collapse-disabled-claim-fanout.sql.",
        ),
        enforced_by=("MIGRATION_SQL", "RUNTIME_CODE", "PYTEST"),
        invariant="Do not materialize downstream child jobs when the downstream "
        "capability is unavailable.",
        evidence=(
            "db/migrations/20260922-collapse-disabled-claim-fanout.sql; "
            "poc/dichiarazioni_pubbliche/worker_daemon.py; tests/test_worker_daemon.py"
        ),
    ),
    Threat(
        id="T-PROVIDER-DOWNGRADE",
        stride="TAMPERING",
        stage="CLAIM",
        title="Provider outage is 'handled' by degrading quality",
        asset="claim/ASR/evidence outputs",
        attack=(
            "Pressure to keep the pipeline 'green' leads to switching provider or "
            "model, lowering validation thresholds, or accepting a partial "
            "response when the real provider is down."
        ),
        impact=(
            "The public record silently becomes lower quality than the system "
            "claims. The operator cannot tell a degraded record from a sound one."
        ),
        likelihood="MEDIUM",
        severity="CRITICAL",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "Provider failure raises a BlockedJob, which is a terminal "
            "observable state, never a fallback. The claim client is built only "
            "when a credential exists; without one the lane is blocked with "
            "zero network calls and zero cost.",
            "The outage drill asserts: no provider receipt with a SUCCESS "
            "status is created, no claim is inserted, and no finding changes "
            "publication state.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="Provider failure is an explicit blocked state.",
        evidence=(
            "poc/dichiarazioni_pubbliche/worker_handlers_claim_evidence.py; "
            "deploy/ops/provider_outage_drill.sh; tests/test_ops_provider_outage.py"
        ),
    ),
    Threat(
        id="T-DELETE-DATA",
        stride="DENIAL_OF_SERVICE",
        stage="TRANSCRIPT",
        title="Retention purge destroys irreplaceable provenance",
        asset="transcripts/, receipts/, media/",
        attack=(
            "A manifest is truncated, a symlink is placed in the media tree, or "
            "a directory is empty, and the purge runs anyway."
        ),
        impact=(
            "Raw media deleted while no durable transcript/provenance exists: "
            "the source can no longer be re-derived."
        ),
        likelihood="LOW",
        severity="HIGH",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "purge_transient_media authorizes deletion only when the manifest "
            "is a real file, valid JSON, <= 1 MiB, transcript/content_hash/"
            "provenance are all complete, transcripts and receipts each hold at "
            "least one non-symlink file, and the media tree contains no symlink.",
        ),
        enforced_by=("RUNTIME_CODE", "PYTEST"),
        invariant="Deletion/retention operations fail closed when manifests or "
        "durable receipts are incomplete.",
        evidence="poc/dichiarazioni_pubbliche/retention.py; tests/test_retention.py",
    ),
    Threat(
        id="T-BACKUP",
        stride="INFORMATION_DISCLOSURE",
        stage="FINDING",
        title="Backup artifact leaks private operational data",
        asset="pg_dump files, projection bundles in backup storage",
        attack=(
            "A database dump containing raw transcript text and provider "
            "receipts lands in a world-readable location, or in the repository."
        ),
        impact=(
            "Bulk disclosure of unpublished transcript/evidence content, which "
            "the public projection deliberately withholds."
        ),
        likelihood="MEDIUM",
        severity="HIGH",
        status="MITIGATED",
        mitigations=(
            "Backup artifacts are written 0600 into a private backup root, are "
            "excluded from the repository, and the drill verifies the dump is "
            "never committed.",
        ),
        enforced_by=("PYTEST", "OPERATIONAL_PROCEDURE"),
        invariant="Private/raw operational data is not exposed merely because a "
        "public projection exists.",
        evidence=(
            "deploy/ops/backup.sh; deploy/ops/restore_drill.sh; "
            "tests/test_ops_restore_drill.py; docs/ops/backup-and-restore.md"
        ),
    ),
    Threat(
        id="T-RESTORE-SILENT",
        stride="REPUDIATION",
        stage="FINDING",
        title="Partial or fabricated restore is reported as success",
        asset="restored database, restored projection bundle",
        attack=(
            "A restore is declared done when psql exited zero but tables are "
            "missing, or when the bundle is 'recreated' by regenerating an empty "
            "projection over an empty database."
        ),
        impact=(
            "The team believes it has recovered when it has not, and publishes "
            "from an empty record. A silent loss of the public history is worse "
            "than a loud outage."
        ),
        likelihood="MEDIUM",
        severity="CRITICAL",
        status="MITIGATED_IN_CODE",
        mitigations=(
            "The drill compares source and restored row counts per table and "
            "compares dataset_sha256 of the projection bundle; any mismatch is "
            "a non-zero exit, and the drill never regenerates a projection as a "
            "substitute for a restored one.",
        ),
        enforced_by=("PYTEST", "OPERATIONAL_PROCEDURE"),
        invariant="Restore must never fabricate data; a failed restore fails loudly.",
        evidence="deploy/ops/restore_drill.sh; tests/test_ops_restore_drill.py",
    ),
    Threat(
        id="T-RETENTION-UNBOUNDED",
        stride="DENIAL_OF_SERVICE",
        stage="TRANSCRIPT",
        title="Private store grows without bound",
        asset="~/.local/share/dichiarazioni-pubbliche private artifact store",
        attack="Raw media, caption responses, and evidence cache never expire.",
        impact="Disk exhaustion on the single-host runtime authority.",
        likelihood="HIGH",
        severity="MEDIUM",
        status="MITIGATED",
        mitigations=(
            "Explicit retention matrix with per-artifact class and trigger; the "
            "digest reports private_runtime_storage so growth is visible before "
            "it becomes an outage.",
        ),
        enforced_by=("PYTEST", "OPERATIONAL_PROCEDURE"),
        invariant="Prefer deterministic logic and cheap stages before expensive ones.",
        evidence=(
            "docs/ops/retention-matrix.md; poc/dichiarazioni_pubbliche/ops/retention_policy.py; "
            "tests/test_ops_retention_policy.py"
        ),
    ),
    Threat(
        id="T-NOT-EDITION",
        stride="INFORMATION_DISCLOSURE",
        stage="PUBLIC_API",
        title="Private record surfaces through a mirrored or proxied artifact",
        asset="public site, CDN, archival snapshot",
        attack=(
            "An operator publishes a private runtime directory, or a snapshot "
            "service archives a pre-publication URL."
        ),
        impact="Private transcript/evidence content becomes retrievable.",
        likelihood="LOW",
        severity="MEDIUM",
        status="DOCUMENTED_ONLY",
        mitigations=(
            "Deployment rule: only the generated public bundle directory is "
            "ever served; private roots stay under ~/.local and are not bound "
            "to any listener.",
        ),
        enforced_by=("UNIT_FILE", "OPERATIONAL_PROCEDURE"),
        invariant="Private/raw operational data is not exposed merely because a "
        "public projection exists.",
        evidence="deploy/systemd/dichiarazioni-pubbliche-web.service; docs/ops/runbook.md",
    ),
)


# --- Pure predicates --------------------------------------------------------


def _ids(rows: Iterable[Threat]) -> set[str]:
    return {row.id for row in rows}


def by_stage(stage: str) -> tuple[Threat, ...]:
    """Threats affecting one pipeline stage, in register order."""
    return tuple(row for row in THREATS if row.stage == stage)


def by_severity(severity: str) -> tuple[Threat, ...]:
    """Threats at exactly one severity."""
    return tuple(row for row in THREATS if row.severity == severity)


def critical_threats() -> tuple[Threat, ...]:
    return by_severity("CRITICAL")


def coverage_gaps() -> tuple[str, ...]:
    """Machine-detectable holes in the register.

    A gap is any threat that is HIGH or CRITICAL and is not at least
    regression-checked, or whose mitigations/evidence are empty. This function
    is what keeps the model from quietly decaying into prose.
    """
    gaps: list[str] = []
    for row in THREATS:
        if row.severity in {"HIGH", "CRITICAL"} and not row.regression_checked:
            gaps.append(f"{row.id}:high_severity_without_machine_check")
        if not row.mitigations:
            gaps.append(f"{row.id}:no_mitigation")
        if not row.evidence:
            gaps.append(f"{row.id}:no_evidence_pointer")
    return tuple(gaps)


def procedural_only_high_severity() -> tuple[str, ...]:
    """HIGH/CRITICAL threats whose only enforcement is a written procedure."""
    return tuple(
        row.id
        for row in THREATS
        if row.severity in {"HIGH", "CRITICAL"}
        and set(row.enforced_by) == {"OPERATIONAL_PROCEDURE"}
    )


def validate_register(
    rows: tuple[Threat, ...] = THREATS,
) -> tuple[str, ...]:
    """Return a list of structural defects; empty means the register is sound.

    Pure, total, and independent of any file: it validates the data itself.
    """
    defects: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row.id in seen:
            defects.append(f"duplicate_id:{row.id}")
        seen.add(row.id)
        if row.stride not in STRIDE:
            defects.append(f"{row.id}:unknown_stride:{row.stride}")
        if row.stage not in PIPELINE_STAGES:
            defects.append(f"{row.id}:unknown_stage:{row.stage}")
        if row.severity not in SEVERITIES:
            defects.append(f"{row.id}:unknown_severity:{row.severity}")
        if row.status not in STATUSES:
            defects.append(f"{row.id}:unknown_status:{row.status}")
        if row.likelihood not in SEVERITIES:
            defects.append(f"{row.id}:unknown_likelihood:{row.likelihood}")
        for mechanism in row.enforced_by:
            if mechanism not in ENFORCEMENT:
                defects.append(f"{row.id}:unknown_enforcement:{mechanism}")
        if not row.enforced_by:
            defects.append(f"{row.id}:no_enforcement")
        if row.status in {"MITIGATED", "MITIGATED_IN_CODE"} and not row.regression_checked:
            defects.append(f"{row.id}:claims_mitigation_without_machine_check")
        if (
            row.severity in {"HIGH", "CRITICAL"}
            and set(row.enforced_by) == {"OPERATIONAL_PROCEDURE"}
            and row.id not in _PROCEDURAL_ONLY_ALLOWED
        ):
            defects.append(f"{row.id}:high_severity_procedural_only")
    return tuple(defects)


def trust_boundaries() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """The stage-to-stage trust boundaries and the threats that sit on them.

    Used by the regression matrix to assert that no boundary between an
    untrusted input stage and a trusted output stage is unguarded.
    """
    return (
        ("SOURCE_INGEST", by_stage("SOURCE_INGEST")),
        ("TRANSCRIPT", by_stage("TRANSCRIPT")),
        ("CLAIM", by_stage("CLAIM")),
        ("EVIDENCE", by_stage("EVIDENCE")),
        ("FINDING", by_stage("FINDING")),
        ("PUBLIC_PROJECTION", by_stage("PUBLIC_PROJECTION")),
        ("PUBLIC_API", by_stage("PUBLIC_API")),
    )
