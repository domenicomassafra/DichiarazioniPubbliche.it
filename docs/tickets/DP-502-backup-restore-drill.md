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

### Local hardening advance — 2026-10-06

- The row-count manifest and restore verifier now cover every persistent table declared by
  `db/schema.v1.sql` or the ordered migrations, including identity/role, correction/reply,
  rights/privacy, challenge/high-risk review, source-health/polling, and fact-check mirror
  state added after the original DP-502 implementation.
- The current inventory covers all 92 durable public tables, including the source-span review
  ledgers and provenance hold/source-revalidation ledgers added by concurrent migrations.
- `ops/table_inventory.py` derives the expected inventory from `schema.v1.sql` plus all ordered
  migrations. `backup.sh` fails closed unless its checked-in inventory matches both that
  repository declaration and PostgreSQL's live permanent public-table catalog; the restore
  drill likewise requires the restored catalog to match the backed-up manifest before row-count
  comparison.
- `tests/test_ops_restore_drill.py` compares the checked-in backup inventory, the restore
  verifier inventory, and the repository-derived inventory without depending on shell-block
  layout. Local proof on 2026-10-06: 13/13 restore tests PASS, `compileall` PASS, and
  `git diff --check` PASS.
- The drill now refuses the canonical production database name and any restore target that
  already contains user relations before `pg_restore` runs. Cleanup resets only the
  disposable target's `public` schema.

These are local safety proofs only. The required MiniPC backup→restore round trip and
sanitized runtime receipt remain open, so DP-502 stays IN PROGRESS.
