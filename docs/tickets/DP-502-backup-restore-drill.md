# DP-502 — Backup/restore drill

Status: DONE
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

## MiniPC completion receipt — 2026-10-06

The production MiniPC created backup set `20261006T185552Z` with a readable PostgreSQL dump
(10,892,638 bytes) and the configured public bundle. The dump was restored into disposable
DB `dp_restore_accept_20261006_1856`; the drill verified **92/92** table-data entries and
reported `RESULT: PASS (restored state matches backup exactly)` plus `DRILL PASS`. The
disposable DB was then dropped. The canonical production database was never used as a
restore target and no credential/private payload was copied into the sanitized receipt.

### Post-migration release-candidate drill — 2026-10-06

After the final 2026-10-06 additive migrations, backup set `20261006T214721Z` was restored
again into a separately created disposable MiniPC database. The source dump contained **94**
table-data entries; every manifest count matched the restored database, including the two new
private reply-governance ledgers. The verifier reported `RESULT: PASS` and `DRILL PASS`, and the
temporary database was removed immediately afterwards. This confirms the final integrated
94-table runtime state remains recoverable without touching the production database.

### Effective-time migration drill — 2026-10-07

After promoting main `2db8ca1100c5a1efd99ce38ffe50b1593646ed83`, the MiniPC applied
`20261007-add-evidence-effective-time-state.sql` twice successfully, then created backup set
`20261007T143042Z`. The dump again contained **94** table-data entries. A fresh disposable
database restored every manifest count exactly, including the updated `evidence` table with
`valid_from`, `valid_until`, and `record_status`; the verifier reported
`RESULT: PASS (restored state matches backup exactly)` and `DRILL PASS`. The disposable
database was removed immediately after verification.

### Privacy rights/access migration drill — 2026-10-07

Candidate `dbca6035148873ce740a4abf6140b14bfa9a2854` passed GitHub Actions run
`37647821230` before promotion. The MiniPC pre-migration state was internally consistent at
**94 repository-declared / 94 live tables** and was backed up as set `20261007T155743Z`
(dump bytes `10908926`). Only
`20261007-add-privacy-rights-access-ledgers.sql` was then applied, twice with
`ON_ERROR_STOP`; no historical migration replay was attempted. Repository and live inventory
converged at **97/97** tables, while the three new private ledgers were intentionally empty
(`0/0/0`) immediately after migration.

The post-migration backup set `20261007T160049Z` contains **97 table-data entries** and a
10,926,017-byte dump. Sanitized integrity identifiers are dump SHA-256
`9168371b3f549a7d58f9a43822073f64a4d3c94b0db3ed6e68a330f3c745b0c2` and manifest
SHA-256 `8d8c329378652df29a2f0cedfbab2b9c5161eae585632368e2ef2c38868a2f8b`.
A fresh disposable database `dp_restore_dbca603_20261007` restored all **97/97** durable
tables with exact source/restored row-count parity, including the three new zero-row privacy
ledgers. The verifier reported `RESULT: PASS (restored state matches backup exactly)` and
`DRILL PASS set=20261007T160049Z`; the disposable database was removed afterward.
