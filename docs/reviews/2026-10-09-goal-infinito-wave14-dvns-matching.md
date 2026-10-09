# GOAL INFINITO — Wave 14: strict temporal sources and matching provenance

Date: 2026-10-09. Published baseline: `ee754fb16cd6caf746bc8254c27593141fc14dd8`.
GitHub Actions `37979721801`: SUCCESS, 11/11 jobs. No production deployment.

## DP-234 strict ISO input (offline candidate-only bridge)

The Source Intelligence DVNS suitability adapter used
`date.fromisoformat(raw[:10])`, silently accepting malformed suffixes,
impossible clocks/time zones and altered source validity intervals as if
they were authoritative dates. The actual configured synthetic ISTAT
profile/source scope could therefore report `READY_FOR_DP215_ASSESSMENT`
for malformed `statement_date`, `effective_at`, `AuthorityScope.valid_from`
or `valid_until`. Three new focused tests reproduced fifteen RED subcases.

The replacement requires a full-string ISO calendar date or ISO timestamp,
parses valid clock/zone fields and preserves field-specific
`DVNS_DP215_*_INVALID` codes. Valid dates/timestamps, explicit status,
rights, approved roles and temporal validity still use existing guards.
This does **not** approve an official DVNS schema, licensed source, rights
scope or real provider/MiniPC canary.

## DP-418 persisted matching authority (private read-only Studio)

The previous Studio matching reader returned a constant current algorithm
version but failed to read stored `candidate_match_run.matching_version`,
`candidate_match_result.matching_version` and each result's lifecycle
`status`. Six adversarial RED subcases proved stale/missing version and
non-candidate results still reached Studio as apparently current matches.
The SQL reader now fetches the actual persisted fields; the private
inspector requires current `candidate-matching-v1` on the run and each
result, plus `status=CANDIDATE` for each result, before presenting safe
summary features. PostgreSQL schema and migration define these exact
columns. Existing output remains `currentness=UNVERIFIED` with no
review/publication/promotion authority and no private raw text.

## Local proof, boundaries

- `test_dvns_source_suitability`, `test_dvns_structured_evidence`,
  `test_studio_candidate_review`, `test_studio_local_api`,
  `test_candidate_matching`: **56/56 PASS**.
- Independent DVNS importer, structured evidence and Source Intelligence
  adjacent tests: **65/65 PASS** (worker report).
- `python3 -m compileall -q poc tests` and `git diff --check`: PASS.
- Full-suite, restore drill, deterministic benchmark, launch preflight,
  the coherent selective commit and matching GitHub Actions CI are
  recorded separately after their results, not inferred here.

## Frozen full-suite evidence (source only)

- `PYTHONPATH=poc python3 -m unittest discover -s tests -q`:
  **2097/2097 PASS**, 382.986 seconds (fixture HTTP/socket warnings only).
- Restore drill: **PASS**, all 100 tables (1,248 schema fields), exact
  backup/restore state comparison.
- Deterministic verification benchmark: **5/5 PASS**.
- `python3 tools/check_repository_contract.py --only tickets`:
  **PASS**; `python3 -m compileall -q poc tests`, `git diff --check`:
  **PASS**.
- `PYTHONPATH=poc python3 tools/check_launch_preflight.py --expect-no-go`:
  **NO-GO/41** with unchanged receipt SHA-256
  `890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`.

The full suite is deterministic/test fixtures, not source licensing,
human-reviewed attribution, production PostgreSQL validation or MiniPC
runtime deployment. A matching commit SHA/CI is a distinct final gate.

DP-234 and DP-418 remain IN PROGRESS. No licensed DVNS rights, authentic
Garlasco Capture/Passage rows, signed reviewer action, production migration
or real DP-418 acceptance is claimed. Canonical release preflight remains
NO-GO/41 with 39 open tickets until independently changed by real evidence.
The unrelated local ContentAuditClient prototype and owner handoff are
intentionally excluded from publication.
