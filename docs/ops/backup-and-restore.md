# Backup and restore

Status: implementation complete on the development checkout; runtime drill still required on an isolated MiniPC database.

`deploy/ops/backup.sh` creates a PostgreSQL custom-format dump plus an observed row-count manifest. If a public projection bundle is configured, it copies the bundle verbatim and records its `dataset_sha256`. Backup directories are private and the dump is checked with `pg_restore --list` before the backup is called usable.

`deploy/ops/restore_drill.sh` restores a selected backup into a throwaway database. It compares the source manifest with live restored row counts and delegates fail-closed verdicts to `dichiarazioni_pubbliche.ops.restore_verify`. A missing count, mismatched count, missing bundle hash, or changed bundle hash fails the drill. The verifier never regenerates data to manufacture a pass.

Production data must not be altered for acceptance. The restore target must be disposable. The public bundle is evidence to compare, not a substitute for restoring the operational database.

## Required runtime receipt

The DP-502 receipt must record the backup set identifier, dump readability, restored row-count comparison, projection fingerprint comparison when a bundle exists, command exit status, and proof the target was isolated. A failed or incomplete restore is a failed/blocked drill, not a reason to edit counts or rebuild missing records.
