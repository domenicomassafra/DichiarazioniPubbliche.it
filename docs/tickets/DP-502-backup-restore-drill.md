# DP-502 — Backup/restore drill

Status: IN PROGRESS
Milestone: M5
Depends on: DP-501

## Outcome

Back up PostgreSQL and, when present, the public projection; restore into a disposable database; prove load-bearing row counts and public dataset fingerprint match without regenerating missing data.

## Acceptance criteria

- Backup output contains a readable PostgreSQL dump and source row-count manifest.
- A configured public projection is copied verbatim with its dataset fingerprint.
- Restore runs only against a disposable target, never the production database.
- Every load-bearing restored table count matches the source manifest.
- Projection fingerprints match when a public bundle is included.
- Missing/mismatched evidence fails closed; regeneration or hand-edited counts cannot manufacture PASS.
- A complete MiniPC round trip is recorded without credentials or private payloads.

## Implementation receipt — 2026-09-27

- Added `deploy/ops/backup.sh` and `deploy/ops/restore_drill.sh`.
- Added pure verifier/CLI `ops/restore_verify.py` and `ops/restore_drill.py`.
- Added deterministic `tests/test_ops_restore_drill.py`.
- Added `docs/ops/backup-and-restore.md` and `docs/ops/restore-drill.md`.

Development tests prove fail-closed comparison behavior. Remaining acceptance is the real backup→restore round trip on a throwaway MiniPC database with a sanitized receipt. Production data must not be modified.
