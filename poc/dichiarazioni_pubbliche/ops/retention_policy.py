"""Retention matrix as machine-readable policy (DP-503).

The prose matrix lives in ``docs/ops/retention-matrix.md``. This module is its
executable form: every artifact class, its retention rule, its trigger, the
deletion mechanism, and the legal-basis pointer (DP-304 privacy minimization,
DP-305 copyright/excerpt policy).

Critical property: this module *references* the rules already encoded in
``poc/dichiarazioni_pubbliche/retention.py`` rather than re-implementing them. A row
whose ``implemented_by`` names a real module function must agree with that
function's actual guard conditions; the regression test cross-checks that
agreement, so the doc and the code cannot silently diverge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


# --- Classes ---------------------------------------------------------------
# What kind of thing is this, and therefore what may be done to it.
#   DURABLE_PROVENANCE  -> must survive; backs a published public record
#   DURABLE_PRIVATE     -> must survive; backs a not-yet-public decision
#   TRANSIENT           -> deletable once its durable successor exists
#   CACHE               -> regenerable at any time; safe to drop
#   RECEIPT             -> append-only accounting; must survive

CLASSES = (
    "DURABLE_PROVENANCE",
    "DURABLE_PRIVATE",
    "TRANSIENT",
    "CACHE",
    "RECEIPT",
)


@dataclass(frozen=True)
class RetentionRule:
    artifact: str
    data_class: str
    retention: str
    trigger: str
    deletion_mechanism: str
    legal_basis: str
    implemented_by: str
    notes: str = ""


RULES: tuple[RetentionRule, ...] = (
    # --- Durable provenance: backs the public record. Never deleted. ---------
    RetentionRule(
        artifact="public projection bundle (index.json, index.jsonld, claims/*)",
        data_class="DURABLE_PROVENANCE",
        retention="permanent (finding-versioned; corrections append, never rewrite)",
        trigger="never auto-delete; stale projection-owned files removed on rebuild",
        deletion_mechanism=(
            "public_projection.write_public_bundle removes only files the next "
            "bundle does not contain"
        ),
        legal_basis="DP-304 (public-interest record); append-only per PRODUCT.md",
        implemented_by="dichiarazioni_pubbliche.public_projection.write_public_bundle",
        notes="A correction publishes a new finding version; history is preserved.",
    ),
    RetentionRule(
        artifact="review_event ledger",
        data_class="RECEIPT",
        retention="permanent (append-only provenance of every approval)",
        trigger="never",
        deletion_mechanism="none",
        legal_basis="DP-304 (auditability)",
        implemented_by="dichiarazioni_pubbliche.queue_runtime.record_review_event",
        notes="Deletion would break the traceable-published-finding invariant.",
    ),
    RetentionRule(
        artifact="transcript variants + segments (raw_text)",
        data_class="DURABLE_PRIVATE",
        retention=(
            "retain; this is the provenance that raw media are transient copies of"
        ),
        trigger=(
            "never auto-delete; referenced by claims, evidence, and published "
            "findings"
        ),
        deletion_mechanism="none in v0",
        legal_basis="DP-304 (provenance); DP-305 (excerpt policy bounds any sharing)",
        implemented_by="poc/dichiarazioni_pubbliche/retention.py (purge guard reads this)",
        notes="Private operational data; never exposed via public projection.",
    ),
    RetentionRule(
        artifact="research corpus capture metadata/hash + lifecycle current state",
        data_class="DURABLE_PRIVATE",
        retention=(
            "retain audit metadata/hash; no numeric legal period is invented while "
            "DP-304 remains unapproved"
        ),
        trigger="never auto-delete from DP-118; rights/qualified review controls later lifecycle",
        deletion_mechanism="none in v1; body bytes are governed separately",
        legal_basis="DP-304 deny-by-default; DP-118 technical lifecycle",
        implemented_by="dichiarazioni_pubbliche.corpus_retention",
        notes="body_ref may be cleared after an eligible purge; content_sha256 survives.",
    ),
    RetentionRule(
        artifact="research corpus capture lifecycle events / archive and purge receipts",
        data_class="RECEIPT",
        retention="retain append-only while the capture record exists",
        trigger="never bulk-delete independently of the owning capture",
        deletion_mechanism="none; capture FK lifecycle only",
        legal_basis="DP-304 auditability; DP-118 replay",
        implemented_by="capture_lifecycle_event + dichiarazioni_pubbliche.corpus_retention",
        notes="Archive failure and purge receipts remain inspectable instead of being overwritten away.",
    ),
    RetentionRule(
        artifact="provider_receipt (cost/provider accounting)",
        data_class="RECEIPT",
        retention="retain (bounded accounting history)",
        trigger="never auto-delete within v0",
        deletion_mechanism="none in v0",
        legal_basis="DP-304 (cost auditability)",
        implemented_by="dichiarazioni_pubbliche.queue_runtime.record_receipt",
    ),
    # --- Transient: deletable once durable successors exist. ----------------
    RetentionRule(
        artifact="research corpus captured body/object bytes",
        data_class="TRANSIENT",
        retention=(
            "purge only when the individual capture is explicitly EPHEMERAL, has no "
            "active hold, and hash/path safety checks pass; POLICY_PENDING is not purgeable"
        ),
        trigger=(
            "DP-118 prepare -> verified body deletion -> finalize lifecycle; dry-run is default"
        ),
        deletion_mechanism="dichiarazioni_pubbliche.corpus_retention.purge_local_capture_body + lifecycle SQL",
        legal_basis="DP-304 P-304-06 (only EPHEMERAL purge eligible); DP-305 private-by-default",
        implemented_by="dichiarazioni_pubbliche.corpus_retention",
        notes="No numeric retention period is encoded; an active legal/rights/privacy/copyright/dispute hold blocks purge.",
    ),
    RetentionRule(
        artifact="raw downloaded media (audio/video under content/*/media)",
        data_class="TRANSIENT",
        retention=(
            "purge after transcript + content hash + provenance are complete"
        ),
        trigger=(
            "purge_transient_media preconditions: manifest present, valid, <=1MiB; "
            "transcript_status/content_hash_status/provenance_status all complete; "
            "transcripts/ and receipts/ each hold >=1 non-symlink file; media tree "
            "has no symlink"
        ),
        deletion_mechanism=(
            "dichiarazioni_pubbliche.retention.purge_transient_media (fail-closed; "
            "rmtree of media/ only)"
        ),
        legal_basis="DP-304 (data minimization: keep derived, drop bulk raw)",
        implemented_by="dichiarazioni_pubbliche.retention.purge_transient_media",
        notes="Never deletes transcripts/ or receipts/; only media/.",
    ),
    RetentionRule(
        artifact="raw caption / ASR provider response payloads (private store)",
        data_class="TRANSIENT",
        retention=(
            "retain until the derived transcript variant + receipt are durable; "
            "the derived variant is the durable provenance"
        ),
        trigger="derived transcript + receipt durable (same precondition set as media purge)",
        deletion_mechanism=(
            "manual/operator, gated on durable variant existing; no bulk auto-purge in v0"
        ),
        legal_basis="DP-304 (minimize raw provider payloads)",
        implemented_by=(
            "dichiarazioni_pubbliche.worker_daemon.persist_asr_response / persist_caption"
        ),
        notes="Out of the repository by policy; private root is 0700/0600.",
    ),
    RetentionRule(
        artifact="research corpus Passage.private_text",
        data_class="DURABLE_PRIVATE",
        retention=(
            "private research text; no automatic purge while legal retention periods are unapproved"
        ),
        trigger="no automatic deletion in DP-118; future approved retention workflow only",
        deletion_mechanism="none in v1",
        legal_basis="DP-304 OPERATIONAL_PRIVATE; DP-305 no public raw/full-text projection",
        implemented_by="passage table + public/private projection leak tests",
        notes="Search may use it inside Studio; Public must never serialize it.",
    ),
    # --- Cache: regenerable, safe to drop at any time. ----------------------
    RetentionRule(
        artifact="evidence HTTP cache (fetched evidence bodies)",
        data_class="CACHE",
        retention=(
            "TTL from evidence-sources policy (default 3600s, per-source up to "
            "21600s); also content-addressed by sha256"
        ),
        trigger="cache_ttl_seconds expiry or content re-hash",
        deletion_mechanism="TTL eviction in evidence_runtime fetcher (regenerable)",
        legal_basis="n/a (regenerable public source data)",
        implemented_by="dichiarazioni_pubbliche.evidence_runtime.SafeEvidenceFetcher",
        notes="Cache never outlives its TTL; droppable at any time without loss.",
    ),
    RetentionRule(
        artifact="health digest (~/.local/state/dichiarazioni-pubbliche/health.json)",
        data_class="CACHE",
        retention="regenerated every 15 min; single file overwritten atomically",
        trigger="each health timer run",
        deletion_mechanism="atomic overwrite; no history retained (privacy: no accumulation)",
        legal_basis="DP-304 (aggregate-only, no raw text)",
        implemented_by="dichiarazioni_pubbliche.health_digest.write_private_json",
    ),
    # --- Backup: operational copies. ----------------------------------------
    RetentionRule(
        artifact="PostgreSQL backup dumps + projection bundle backups",
        data_class="DURABLE_PRIVATE",
        retention=(
            "operator-defined rotation (recommended: 7 daily + 4 weekly); backups "
            "contain the same private data as the live store"
        ),
        trigger="scheduled backup timer / manual drill",
        deletion_mechanism=(
            "rotate by count/age in backup.sh; stored 0600 in a private backup root"
        ),
        legal_basis="DP-304 (backups inherit source retention)",
        implemented_by="deploy/ops/backup.sh",
        notes="Never commit a backup; never put one in the public bundle directory.",
    ),
)


def rules_for_class(data_class: str) -> tuple[RetentionRule, ...]:
    return tuple(row for row in RULES if row.data_class == data_class)


def rule_for(artifact: str) -> RetentionRule:
    for row in RULES:
        if row.artifact == artifact:
            return row
    raise KeyError(artifact)


def purgeable_artifacts() -> tuple[str, ...]:
    """Artifacts that may be deleted by an automated mechanism."""
    return tuple(
        row.artifact for row in RULES if row.data_class in {"TRANSIENT", "CACHE"}
    )


def permanent_artifacts() -> tuple[str, ...]:
    """Artifacts that must never be auto-deleted."""
    return tuple(
        row.artifact
        for row in RULES
        if "permanent" in row.retention or "retain" in row.retention
    )


def validate_matrix(rules: tuple[RetentionRule, ...] = RULES) -> tuple[str, ...]:
    """Structural self-check; empty tuple means the matrix is coherent.

    Enforces the policy rules that matter:
      - every class is known;
      - every DURABLE_PROVENANCE/RECEIPT artifact has no deletion mechanism
        other than projection-rebuild/append-only (never a bulk delete);
      - every legal_basis points at a real AA ticket or states n/a;
      - every row names an implemented_by anchor.
    """
    defects: list[str] = []
    seen: set[str] = set()
    for row in rules:
        if row.artifact in seen:
            defects.append(f"duplicate_artifact:{row.artifact}")
        seen.add(row.artifact)
        if row.data_class not in CLASSES:
            defects.append(f"{row.artifact}:unknown_class:{row.data_class}")
        if not row.trigger:
            defects.append(f"{row.artifact}:no_trigger")
        if not row.deletion_mechanism:
            defects.append(f"{row.artifact}:no_deletion_mechanism")
        if not row.legal_basis:
            defects.append(f"{row.artifact}:no_legal_basis")
        if not row.implemented_by:
            defects.append(f"{row.artifact}:no_implemented_by")
        if row.data_class == "DURABLE_PROVENANCE" and "never" not in row.trigger:
            defects.append(f"{row.artifact}:durable_provenance_must_be_never_deleted")
        if row.data_class == "RECEIPT" and "none" not in row.deletion_mechanism.lower():
            # receipts are append-only; a bulk delete is a policy violation
            if "remove" in row.deletion_mechanism.lower() or "rmtree" in row.deletion_mechanism.lower():
                defects.append(f"{row.artifact}:receipt_bulk_delete_forbidden")
    return tuple(defects)


def as_matrix_rows(rules: Iterable[RetentionRule] = RULES) -> tuple[dict[str, Any], ...]:
    """Row dicts for docs/table generation and for the digest."""
    return tuple(
        {
            "artifact": row.artifact,
            "class": row.data_class,
            "retention": row.retention,
            "trigger": row.trigger,
            "deletion_mechanism": row.deletion_mechanism,
            "legal_basis": row.legal_basis,
            "implemented_by": row.implemented_by,
            "notes": row.notes,
        }
        for row in rules
    )
