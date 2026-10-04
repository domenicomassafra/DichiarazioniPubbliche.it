# Restore drill runbook

1. Create or select an isolated PostgreSQL database on the MiniPC. Never point the drill at the production database.
2. Produce a fresh backup with `deploy/ops/backup.sh`, using the same database and projection inputs as the candidate runtime.
3. Run `deploy/ops/restore_drill.sh --backup-root <private-root> --restore-url <throwaway-libpq-url>`.
4. Treat exit code `0` as a pass, `1` as a real mismatch/failure, and `2` as blocked because required input/tooling is unavailable.
5. Preserve a sanitized receipt with the backup set name, table results, dataset fingerprint result, and exit code. Do not record credentials or raw transcript/evidence content.
6. If any load-bearing table or public-bundle fingerprint is missing or mismatched, do not publish and do not repair the restored copy merely to obtain green output.

The pure verification rules and deterministic tests are in `poc/dichiarazioni_pubbliche/ops/restore_verify.py` and `tests/test_ops_restore_drill.py`.
