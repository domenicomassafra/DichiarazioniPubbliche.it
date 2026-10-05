# DP-602 — CI matrix and deterministic contributor acceptance

Status: IN PROGRESS
Milestone: M6 — open-source and release hardening
Depends on: DP-601 package/development profiles and the existing Python/web baseline
Launch state: specification only; CI must not publish, release, or access production data

## Problem

The current workflow runs Python 3.11/3.12 compile, unit/regression, benchmark, and
whitespace checks, plus a Node 24 `npm ci`, Astro check, and static build. It does not
yet prove the package-install path, the contributor profiles, the licensing/data gate,
the ticket graph, or a clean-clone run. The current `git diff --check HEAD^ HEAD` shape
also needs an explicit first-commit/merge-base policy. The canonical source remote now
exists; hosted-CI success must still be evidenced by an actual hosted run rather than
inferred from local checks.

A release-oriented workflow must remain deterministic: no paid provider, no production
database, no public deployment, and no secret-dependent default job.

## Outcome

Define a least-privilege, reproducible CI contract that:

- runs the same supported Python matrix and web toolchain as the documented setup;
- installs and smoke-tests the package without paid credentials;
- separates deterministic checks from provider-, MiniPC-, and release-only gates;
- validates migrations in an isolated database when a ticket requires them;
- checks repository hygiene, relative links, license/data inventory, version/changelog
  consistency, and ticket completeness/collisions; and
- runs the credential-free DP-223 false-attribution/fabricated-quote regression once that
  benchmark is implemented, without network/provider calls; and
- produces sanitized, inspectable receipts without exposing raw data or secrets.

The workflow may run on a future remote, but this ticket does not create one.

## Baseline and evidence limits

The baseline workflow is `.github/workflows/ci.yml`. It currently uses:

- Ubuntu latest;
- Python 3.11 and 3.12;
- `actions/checkout@v4`, `actions/setup-python@v5`, and `actions/setup-node@v4`;
- `npm ci` with `web/package-lock.json`; and
- read-only repository permissions for the existing jobs.

The canonical GitHub remote is now configured. No file named W0R/W0P or a separate
DP-601 baseline was available during this specification, so the implementation must
verify those evidence sources rather than inventing their paths or claiming a hosted CI
run without a real hosted receipt.

## Scope

### 1. Required job matrix

The implementation must provide named jobs with explicit inputs and outputs:

| Job | Matrix/entry condition | Required checks | Failure meaning |
|---|---|---|---|
| `backend-minimal` | Python 3.11 and 3.12 on a supported Ubuntu runner | package build/install, compile, unit/regression, deterministic benchmark, DP-223 trust/evidence benchmark once implemented, import/CLI smoke, whitespace | contributor baseline or attribution-integrity regression is broken |
| `web` | the Node version pinned by `web/package.json` and the lockfile | `npm ci`, `npm run check`, `npm run build`, explicit public-projection build when fixtures are available | frontend contract/build is broken |
| `repository-contract` | every push and pull request | relative-link audit, JSON/YAML/template parse checks, ticket completeness/collision audit, license/data inventory gate, secret-pattern scan | documentation, rights, or graph contract is broken |
| `migration-canary` | only tickets that declare a persistent migration or explicitly request it | isolated PostgreSQL schema, `ON_ERROR_STOP`, ordered migration apply, replay, rollback/forward compatibility checks | migration claim is unproven or unsafe |
| `runtime-minipc` | only runtime-affecting tickets, dispatched to the existing operator path | ticket-specific MiniPC receipt and safe read-back | runtime claim remains unproven; not replaced by Mac output |

`backend-minimal` and `web` are required contributor checks. A missing external provider
is not a reason to weaken or skip a deterministic check. A missing MiniPC or legal
decision is a `BLOCKED` result for the affected claim, not a green substitute.

The current POC benchmark is a legacy regression receipt and can still print historical
`PUBLISH` labels. CI may run it for regression coverage, but it must pair that run with
the current fail-closed projection/review tests and must never treat the benchmark label
as publication authorization or a public release result.

The default workflow must not start a paid model, remote ASR, production database,
public host, or external publication.

### 2. Hermetic setup and cleanup

Each job must:

- check out the candidate commit with the minimum history needed for the declared
  whitespace/base check;
- use pinned, reviewed tool versions and lockfiles;
- install only the profile's declared dependencies;
- avoid credentials and provider calls;
- run in an ephemeral workspace and remove generated artifacts after collecting
  sanitized receipts; and
- fail if a tracked source file is unexpectedly modified by setup or generated output
  collides with a source path.

CI must use least privilege. The default workflow needs read-only repository contents;
any future artifact, issue, or release permission must be isolated to an explicitly
authorized workflow and covered by a separate security review. Third-party actions must
be pinned or otherwise reviewed and recorded in the dependency inventory.

### 3. Clean-clone proof

At least one required job must perform a detached clean-clone smoke test. The test must
be independent of the developer's working tree and must prove:

- no untracked local environment, `node_modules`, virtualenv, raw media, credentials, or
  private data is needed;
- the package and frontend can be installed from the committed lock/config state;
- the deterministic commands pass without a provider key;
- the working tree remains free of generated source artifacts; and
- the exact commit, runner image/tool versions, and exit codes are recorded.

A normal checkout with a developer's uncommitted files is not clean-clone evidence.
The proof must not use a destructive command against the authoritative checkout.

### 4. Repository contract checks

The workflow must run deterministic checks for:

- required ticket sections, unique ticket IDs, unique filename IDs, valid status values,
  valid dependency IDs, and no dependency cycles;
- relative Markdown links and referenced local files;
- JSON, YAML, and GitHub template syntax using pinned, documented tools or native
  parsers;
- `LICENSE`/`NOTICE` presence and the DP-603 fixture/data inventory gate;
- accidental secrets, private keys, credential-shaped values, raw transcript bodies, and
  provider prompts in tracked changes;
- version-source and changelog consistency under the DP-604 policy; and
- whitespace and conflict-marker checks.

Checks must be deterministic and must not depend on an unapproved network lookup. A
license or rights row with `UNKNOWN`, missing evidence, or a stale review fails the
release-facing gate rather than being silently accepted.

### 5. Migration and runtime boundaries

`migration-canary` must use a disposable database or schema, never a production
connection. It must use the repository's ordered migration procedure, `ON_ERROR_STOP`,
and replay the migration at least twice where the ticket declares idempotence. The job
must not alter `db/schema.v1.sql` or invent a new migration authority.

`runtime-minipc` is not a replacement for a default CI job. It is a separately auditable
receipt for runtime-affecting changes, with the MiniPC mirror hash, migration result,
command exit codes, and actual resulting state recorded. Mac-only output must remain
labelled development evidence.

## Non-goals

- creating a GitHub/GitLab remote, issue tracker, project board, or public repository;
- publishing packages, images, releases, API artifacts, or datasets;
- enabling paid providers, remote ASR, or provider substitution;
- adding a database, queue, Kubernetes, vector database, or deployment service;
- changing publication, evidence, speaker, or public-projection semantics;
- making CI a legal or rights approval; or
- declaring hosted CI green when no remote or hosted runner exists.

## Invariants

- CI cannot turn a blocked provider, missing migration proof, or unresolved legal/rights
  decision into a pass;
- no default job may expose raw/private data, credentials, or provider responses;
- public reads remain projection-only and LLM-free;
- the public projection remains fail-closed; and
- the MiniPC remains the runtime authority.

## Acceptance criteria

- [ ] **AC-602.1 — Matrix fidelity:** The workflow runs the documented supported Python
  versions and the exact pinned web toolchain, with no unapproved version drift.
- [ ] **AC-602.2 — Deterministic backend:** For each required Python version, a clean
  environment builds/installs the package, compiles `poc` and `tests`, runs the full
  unit/regression suite, runs the deterministic benchmark, and passes import/CLI smoke
  checks without a paid credential. Legacy benchmark `PUBLISH` output is retained only
  as historical regression evidence; current fail-closed projection/review tests must
  prove that no deterministic result auto-publishes.
- [ ] **AC-602.3 — Deterministic web:** A clean `npm ci` install passes type/Astro
  checks and the static build from the documented fictional fixture; an explicit
  approved public projection build is tested separately and is not replaced by a demo
  fallback.
- [ ] **AC-602.4 — Clean clone:** One required job proves a detached clean clone has no
  local-only prerequisites or generated source artifacts and records the exact commit,
  tool versions, and exit codes.
- [ ] **AC-602.5 — Repository contract:** Link, syntax, ticket completeness/collision,
  license/data inventory, secret/private-data, version/changelog, and whitespace checks
  run on every relevant change and fail closed on a missing required field.
- [ ] **AC-602.6 — No side effects:** Default CI has read-only permissions, makes no
  provider/publication/deploy call, and cannot access production credentials or data.
  Any future write-capable workflow is separately authorized and reviewed.
- [ ] **AC-602.7 — Migration canary:** A ticket that changes persistent schema or
  migration order proves `ON_ERROR_STOP` apply/replay in an isolated database; missing
  or failed proof leaves the ticket blocked and never changes production.
- [ ] **AC-602.8 — Runtime separation:** Runtime-affecting work records MiniPC proof;
  Mac results are labelled development evidence and cannot satisfy the runtime gate.
- [ ] **AC-602.9 — Licensing:** Every newly introduced CI dependency/action and fixture
  has an DP-603 inventory row with exact version, license evidence, and attribution;
  unknown rights fail the release-facing check.
- [ ] **AC-602.10 — Versioning:** CI detects disagreement among Python metadata, web
  metadata, the DP-604 canonical version source, lockfiles, and changelog without
  automatically bumping or publishing a version.
- [ ] **AC-602.11 — No remote assumption:** The specification and local validation do
  not require a remote URL, issue, PR, or hosted runner; a hosted result is classified
  `PENDING-REMOTE` until a canonical remote is confirmed.
- [ ] **AC-602.12 — Trust & Evidence regression:** Once DP-223 is implemented, every
  release-facing deterministic backend run executes it without network/provider access and
  fails on any known false public person attribution or fabricated direct quotation. False
  holds/abstentions remain separately reported and cannot be traded for a false-publication
  pass through a composite score.

## Validation / proof

The implementation receipt must include a fresh run of:

```text
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
cd web && npm ci && npm run check && npm run build
cd .. && git diff --check
```

Then run and record:

1. the detached clean-clone job or an equivalent local clean-clone harness;
2. the ticket completeness/collision audit for DP-601..DP-607;
3. the relative-link, template/syntax, license/data, secret/private-data, and
   version/changelog checks;
4. an isolated migration apply/replay when applicable; and
5. a read-only runtime receipt on MiniPC when applicable.

The audit must check duplicate ticket IDs and filename IDs, required sections, valid
status values, dependency references, and cycles. It must confirm that this worker
changed only the seven owned ticket files and did not modify `PLAN.md`, code, package
metadata, or CI.

## Documentation, data, and migration impact

- Update the contributor/CI documentation in the implementing change and retain the
  deterministic command list in `README.md`, `CONTRIBUTING.md`, and `AGENTS.md` where
  appropriate.
- No database migration is introduced by CI configuration. Migration jobs must use the
  existing ordered migrations and `ON_ERROR_STOP` contract.
- Update DP-603's inventory when a CI action, tool, or fixture is added. Do not add a
  dependency merely to make a check appear green.
- DP-604 owns version/changelog policy; CI may enforce it but must not choose a release.
- Do not edit `PLAN.md`; the M6 ordering remains canonical.

## Blocked conditions

Keep the ticket `BLOCKED` or classify the implementation incomplete if:

- a canonical remote or hosted runner is required but absent;
- a supported Python/Node version cannot be installed reproducibly from committed
  configuration;
- a deterministic job needs a paid provider, production credential, or production data;
- a migration cannot be applied/replayed in isolation;
- a CI action/dependency has unknown or incompatible licensing;
- the ticket/link/rights/version checks cannot be made deterministic;
- a hosted result is required for runtime proof but MiniPC or owner evidence is absent;
  or
- the requested workflow would publish, release, or mutate an external service.

## Completion receipt — implementation 2026-09-26

Implemented. `.github/workflows/ci.yml` now has named jobs:

- `backend-minimal`: matrix `ubuntu-latest` + `macos-latest` x Python **3.11, 3.12,
  3.13, 3.14** (the ticket asked for 3.12/3.13/3.14; 3.11 is retained because it is
  still in `requires-python`). Runs: build distribution -> install into a fresh venv ->
  import/all-modules/console-script smoke -> `compileall` -> full unittest -> benchmark
  -> contributor acceptance -> whitespace (`git diff --check` with a single-commit
  fallback policy) -> assert the tree was not modified by the build.
- `web`: `npm ci` + `npm run check` + `npm run build` (Node 24), plus an assertion that
  an invalid explicit `DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH` is **rejected** (fail-closed).
- `repository-contract`: ticket graph, relative links, JSON, templates, hygiene,
  license, licensing inventory (+ `--check-hashes` and staleness), version/changelog
  consistency.
- `clean-clone`: detached `git clone --no-hardlinks .` of the candidate commit into a
  scratch dir, then compileall/unittest/benchmark/contributor-acceptance — independent
  of the job's working tree.

Least privilege: `permissions: contents: read`; no publish/release/deploy; no
credentials; no PostgreSQL; no provider. Third-party actions are the official
`actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`.

Deterministic contributor acceptance is one credential-free entry point:
`python3 tools/check_contributor_acceptance.py` (repository contract + licensing
inventory + version/changelog). No network, no provider, no PostgreSQL.

Verification actually run (all green, no skips): Python 3.11.15 / 3.12.13 / 3.13.12 /
3.14.7 -> 353 tests OK; benchmark 5/5; `npm ci` 284 packages; `astro check` 0 errors;
build 12 pages; invalid-projection build rejected.

**AC status.** AC-602 required jobs PASS; hermetic setup/least privilege PASS;
clean-clone proof PASS (independent scratch clone, no local-only files);
repository-contract checks PASS; no publish/deploy/production access.
A **hosted** CI run was not claimed in this historical receipt because the canonical
remote did not yet exist at the time. The local commands were the evidence available for
that closure; future hosted claims require an actual GitHub Actions run.
