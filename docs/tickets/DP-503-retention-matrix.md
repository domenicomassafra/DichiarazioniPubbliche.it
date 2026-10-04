# DP-503 — Retention matrix

Status: IN PROGRESS
Milestone: M5
Depends on: DP-304, DP-305

## Outcome

Classify raw media, transcripts, evidence/cache, receipts, projection history, health data, and backups; make automated deletion fail closed and preserve durable provenance.

## Acceptance criteria

- Every artifact class has a data class, deletion trigger, mechanism, and implementation owner.
- Durable provenance, review/provider receipts, and public history are never bulk-purgeable.
- Only explicitly transient/cache artifacts are automatically purgeable absent a later qualified decision.
- Existing destructive-operation guards remain authoritative and fail closed on incomplete manifests or legal holds.
- No legal retention period, lawful basis, or rights outcome is invented.
- Focused retention tests pass; any runtime dry-run uses non-production/deletable material only.

## Implementation receipt — 2026-09-27

- Added machine-readable `poc/dichiarazioni_pubbliche/ops/retention_policy.py`.
- Added `tests/test_ops_retention_policy.py`.
- Added `docs/ops/retention-matrix.md`.
- Existing `retention.py` remains the destructive-operation authority; the new matrix references rather than bypasses its guards.

No legal retention period or lawful basis is asserted. DP-306/DP-307 legal/privacy decisions and a MiniPC retention/hold dry run remain launch blockers.
