# DP-503 — Retention matrix

Status: DONE
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

## Final runtime receipt — 2026-10-06

- Candidate commit: `5a86666bf3bb955f18e036c010e53613425a6cf6`; the MiniPC tracked-file Git blob manifest matched that commit exactly.
- An independent detached Mac clone passed the focused threat/retention command and the full deterministic suite (**1720 tests OK**).
- On the MiniPC mirror, the retention-policy/destructive-guard command passed as part of the **29/29** focused threat/retention set, and the full deterministic suite passed **1620/1620** with 12 skips. The focused tests use test/temporary material and did not purge production data.
- Durable provenance and history remain non-bulk-purgeable; incomplete manifests and legal holds continue to fail closed.

No legal retention period, lawful basis, or rights outcome is asserted. DP-306/DP-307 remain explicit legal/privacy launch dependencies, but they do not substitute for or invalidate the now-complete technical retention matrix and MiniPC proof.
