# GOAL INFINITO — Wave 10: Candidate operator continuation

Date: 2026-10-09. Published baseline commit:
`90a154c8813bfe86ddf5f462cbc8a06ffc63b482`.
Wave 9 full suite: 2069/2069 PASS; benchmark 5/5; restored fixture
PASS; 41 release blockers. GitHub CI run `37972323989` was
**SUCCESS** after the sole PRIME publisher's fast-forward push.

## Reproducible independent operator defects

1. **Candidate manifest memory bound**: `load_candidate_batch` previously
   read arbitrary file contents before validating the 16-item shape.
   RED test used a 1.1-MB oversized JSON input. The loader now consumes
   no more than 1,048,577 bytes and rejects files over 1 MiB with
   `CANDIDATE_BATCH_FILE_TOO_LARGE` before JSON parsing.
2. **Capture availability authority**: `require_private_passage_state`
   accepted arbitrary truthy JSON fields as proof that the Capture body
   reference existed (`"false"` and `1` were accepted). It now requires
   the exact PostgreSQL JSON boolean `true`. RED→GREEN tests include
   absent, boolean false, numeric, string, list and dictionary values.

Focused local suite `test_private_candidate_batch`,
`test_private_candidate_commit_fence`, `test_private_capture_batch`,
`test_capture_authorization` and operator Candidate CLI:
**55/55 PASS**; `compileall` and `git diff --check` PASS.

These are fail-closed processing bounds, not proof of actual Capture
body readability, source license, approved provider use, or accepted
Discovery lineage; none may advance a Candidate for `research:garlasco`
while its real Collection remains PAUSED. No production writes/migration
or release were performed.

## Independent DP-417 triage-history confidentiality

Before a RED→GREEN patch, the read-only SQL history inspector for a
Collection-scoped Hit leaked existing decisions and the head revision
when Attempt/Query lineage had become inconsistent. The independent
worker reproduced the bug on isolated ephemeral PostgreSQL, then
changed the Hit's Query link after creating two annotations.
The corrected SQL gates selected rows, head revision and count on
`lineage_ok`; the presenter rejects untrusted false-lineage rows
carrying revision counts or decisions. The invalid Hit returns zero
decisions and zero head revision with a safe provenance blocker.
SQL+adversarial tests: **17/17 PASS** covering triage reader,
store and attested PostgreSQL fixtures. Source-only proof; no
production migration, no live queue, no reviewer authority.

No canonical ticket status or legal question disposition was changed:
**86 DONE, 24 IN PROGRESS, 6 BLOCKED, 9 FUTURE / 39 open**;
**NO-GO / 41 release blockers**. The independent DP-417 correction
was reviewed and included for the next integrated full-suite gate;
no approval is inferred.

Read-only MiniPC SQL follow-up, inside `BEGIN READ ONLY` / `ROLLBACK`:
`to_regclass('public.research_discovery_triage_decision')` returned
`NULL` (uninstalled DP-417 ledger). The Garlasco Collection remains
`PAUSED`, has 18 INCLUDED Content, **zero** INCLUDED Content with
`rights_status=CLEARED`, and zero live Discovery Hits, Content
Captures, Passages, Statement Candidates and Claim Candidates.
No operation in this wave changed these production values.

## Integrated Wave 10 test gate

- `PYTHONPATH=poc python3 -m unittest discover -s tests -q`:
  **2072/2072 PASS** (128.430 seconds); the expected fixture-only
  HTTP/socket resource warnings did not fail the run.
- Fixture restore drill: **PASS** (100 tables, 1,248 declared fields).
- Deterministic verification benchmark: **5/5 PASS**.
- Repository ticket contract: **PASS**.
- Preflight: **NO-GO/41**, receipt SHA-256 unchanged:
  `890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`.
- `compileall` and `git diff --check`: **PASS**.

No new ticket or acceptance criterion was marked DONE based on these
fixture tests. The live DP-417 migration and all launch authority
remain outside this source-only wave.
