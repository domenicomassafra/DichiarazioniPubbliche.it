# DP-601 — Package and development-environment cleanup beyond POC naming

Status: IN PROGRESS
Milestone: M6 — open-source and release hardening
Depends on: DP-101..DP-106 and the existing deterministic backend/web baseline
Launch state: specification only; no rename, release, remote creation, or external publication is authorized

## Problem

The repository is intentionally pre-1.0 and its technical names are still provisional:
`poc/dichiarazioni_pubbliche` and `dichiarazioni-pubbliche`
configuration names. The current Python metadata is not yet a complete install contract,
the contributor workflow depends on `PYTHONPATH=poc`, and the frontend has a separate
Node setup. A new contributor can run the documented commands in the existing checkout,
but cannot yet prove that the package, CLI entry points, and development profiles install
and behave consistently from a clean clone.

The cleanup must improve the supported development path without pretending that the
POC/v0 names have already been renamed. Brand/domain clearance, schema migration,
and release decisions remain separate work.

## Outcome

Define and implement one boring, reproducible development environment that:

- installs the Python package from a clean checkout and preserves the existing
  `dichiarazioni_pubbliche` import and module-command compatibility;
- separates the no-provider deterministic profile from optional PostgreSQL and web
  profiles;
- makes supported Python, Node, package, and lockfile versions explicit;
- keeps the POC/v0 names as compatibility identifiers until their owning migration and
  release decisions are accepted; and
- hands a single version and dependency authority to DP-602 and DP-604.

This ticket is a specification contract. It does not itself perform the rename or publish
an artifact.

## Baseline and evidence limits

The checked-out baseline has:

- `pyproject.toml` with name `dichiarazioni-pubbliche`, version `0.0.1`, Python
  `>=3.11`, and no declared build backend, dependency groups, or console scripts;
- the package under `poc/dichiarazioni_pubbliche`, with existing `python -m` commands invoked
  through `PYTHONPATH=poc`;
- `web/package.json` with a private package, version `0.1.0`, and a committed npm lockfile;
- `.github/workflows/ci.yml` running Python 3.11/3.12 and Node 24 checks; and
- canonical source remote `https://github.com/domenicomassafra/DichiarazioniPubbliche.it`.

A separate file named as an DP-601 baseline and files named W0R/W0P were not present in
this checkout at specification time. Their absence is recorded as an evidence gap to
verify before implementation closure; no path, report, or result is invented here.

## Scope

### 1. Python package contract

The implementation must select a supported, pinned PEP 517 build backend and make the
package discoverable without changing the current import name. The minimum contract is:

- the distribution metadata truthfully states its provisional name, supported Python
  range, license, runtime dependencies, and development-only dependencies;
- package discovery includes `poc/dichiarazioni_pubbliche` without accidentally packaging
  `poc` as a second public top-level package;
- existing imports such as `dichiarazioni_pubbliche.public_projection` continue to work;
- the implementation may add wrappers or console entry points, but their names must be
  derived from the existing technical identity or explicitly approved by the owner;
- no new runtime dependency is added merely to hide the current `PYTHONPATH` setup;
- optional provider, PostgreSQL, and web tooling is not required by the deterministic
  contributor profile; and
- generated wheels, source distributions, virtual environments, caches, and credentials
  are ignored and are never required inputs to a clean-clone test.

If the physical package directory is moved during implementation, a compatibility
adapter must remain for the old import path and the migration must be documented. This
ticket does not authorize that move; the preferred implementation leaves the current
path intact and improves metadata and entry points.

### 2. Development profiles

Document and test these profiles as named contracts:

| Profile | Required tools | Required behavior | Explicitly not required |
|---|---|---|---|
| `backend-minimal` | Python 3.11 or 3.12 | package install/import, compile, deterministic unit/regression suite, benchmark, CLI help | paid model, ASR, PostgreSQL, remote services |
| `backend-postgres` | `backend-minimal` plus an isolated PostgreSQL instance | migration replay and explicitly database-backed tests | production data mutation or provider credentials |
| `web` | the Node version pinned by the web package/CI and npm | `npm ci`, type/Astro check, static build, explicit public-projection build | database, provider, or LLM access |
| `runtime-canary` | operator-selected MiniPC environment | ticket-specific runtime receipt and safe read-back | Mac-only evidence as a substitute |

A profile must name its setup command, test command, expected artifacts, cleanup rule,
and whether a missing external dependency is `SKIP`, `BLOCKED`, or a failure. Missing
provider credentials may block a live receipt, but they must never turn a deterministic
test green by silently selecting another provider.

### 3. Contributor entry points

The implementing change must update the relevant setup documentation so that a new
contributor can discover:

- the exact supported Python and Node versions;
- the minimal and optional profiles;
- the existing `PYTHONPATH=poc` compatibility path and the installed-package path;
- the deterministic commands that require no paid provider;
- how to run the web build from the default fictional fixture and from an explicit
  public projection;
- how to run migrations only in an isolated database; and
- where credentials, raw media, and private data must remain outside the repository.

Documentation must use the canonical technical names. The repository URL is now fixed at
`https://github.com/domenicomassafra/DichiarazioniPubbliche.it`; security contacts,
package registries and release/deployment destinations must still not be invented.

### 4. Version and dependency authority

DP-601 must identify, without choosing a release number, which files are authoritative
for:

- the Python distribution version;
- the web package version;
- supported interpreter and Node versions; and
- runtime versus development dependencies.

DP-604 owns the final release/versioning policy. DP-601 must make drift detectable and
must not independently bump a version in `pyproject.toml`, `web/package.json`, a lockfile,
or documentation. If the current versions intentionally differ by component, the
compatibility rule must be recorded rather than silently forced equal.

## Non-goals

- renaming the repository, Python package, CLI, database, or `*.v0` files;
- choosing the final brand/domain, package name, or public URL;
- creating a Git remote, tag, release, registry publication, or external package;
- changing the public projection, publication gates, provider routes, or MiniPC runtime;
- adding a dependency manager, service, database, queue, or container platform without a
  measured need;
- turning the POC benchmark into a public truth or publication contract; or
- removing historical receipts or fixtures to make a clean tree look simpler.

## Invariants

- `retrieved evidence != approved evidence != verification != publication` remains
  unchanged;
- provider failure, missing credentials, and missing dependencies remain explicit
  blocked states;
- no public request path gains a package, provider, or LLM dependency;
- no person-level score, political ranking, biometric identity, or raw private data is
  introduced by packaging work; and
- the MiniPC remains the authority for runtime claims.

## Acceptance criteria

- [ ] **AC-601.1 — Installable package:** From a clean checkout, a pinned supported
  Python build creates an installable artifact, and a fresh environment can import
  `dichiarazioni_pubbliche` and run the existing `python -m dichiarazioni_pubbliche.*` entry points
  without relying on an undeclared checkout path.
- [ ] **AC-601.2 — Compatibility:** Existing `PYTHONPATH=poc` commands continue to work
  during the compatibility window, or the migration provides a tested, documented
  replacement and an explicit deprecation window. No silent import break is allowed.
- [ ] **AC-601.3 — Truthful metadata:** Distribution metadata matches the supported
  interpreter range, actual runtime imports, Apache-2.0 code license, and development
  dependency set. A lock or install cannot silently add a provider or database client.
- [ ] **AC-601.4 — Profile separation:** `backend-minimal` passes with no paid provider,
  PostgreSQL, or network data source; `backend-postgres` and `web` are independently
  runnable and report missing prerequisites as `SKIP` or `BLOCKED` according to policy.
- [ ] **AC-601.5 — Name preservation:** The diff contains no repository/package rename,
  no `schema.v0` or `*.v0` migration, and no brand/domain decision. Any proposed rename
  is referred to DP-106 and the later owner-approved brand/domain decision rather than
  performed here.
- [ ] **AC-601.6 — Clean-clone acceptance:** A detached clean clone installs the package,
  runs compile/unit/benchmark and web checks, and produces a local demo without
  `node_modules`, virtual environments, caches, secrets, or raw media in the source
  tree. The proof records the exact commit and tool versions.
- [ ] **AC-601.7 — Migration compatibility:** If package layout changes, an additive
  filesystem/import compatibility check and the canonical `db/schema.v1.sql` plus ordered
  migration replay prove that no database migration is required. Production data is not
  touched.
- [ ] **AC-601.8 — CI contract:** DP-602 can run the same package-install and profile
  commands on Python 3.11 and 3.12, and a package/version drift check fails on an
  unreviewed metadata change.
- [ ] **AC-601.9 — License and data boundary:** `LICENSE`, `NOTICE`, dependency/license
  evidence, and the DP-603 fixture inventory are present or explicitly linked as the
  owning gate. The Apache code license is not represented as a grant for media,
  transcripts, evidence, or datasets.
- [ ] **AC-601.10 — Version handoff:** The implementation records the provisional version
  sources and defers the release number and SemVer decision to DP-604; no version is
  bumped as a side effect of environment cleanup.
- [ ] **AC-601.11 — No external side effect:** No remote, release, publication, provider
  call, or MiniPC deployment is part of the local proof.

## Validation / proof

The implementing receipt must run, from the exact candidate commit:

```text
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
cd web && npm ci && npm run check && npm run build
cd .. && git diff --check
```

It must additionally record the pinned build-backend and package-install command, the
fresh-environment import/CLI smoke output, interpreter and Node versions, and a clean-clone
receipt containing the commit, clone method, command exit codes, and artifact hashes.
A package build or test pass is not proof that a clean clone works; the clean-clone
command must be run independently.

Run a migration replay in an isolated database when the implementation changes package
paths or deployment commands. Use `ON_ERROR_STOP`, apply the existing ordered migrations,
replay them, and record the result. Do not connect to the MiniPC production database for
this documentation/specification acceptance.

Run a deterministic ticket completeness/collision audit covering DP-601..DP-607. The
audit must reject duplicate IDs, duplicate filename IDs, missing required sections,
unknown dependencies, and dependency cycles. It must also confirm that only the seven
owned ticket files were changed by this worker.

## Documentation, data, and migration impact

- Update package/setup documentation in the implementing change; do not edit
  `PLAN.md` from this specification.
- Add or update a dependency/version manifest only through DP-601's implementation;
  DP-604 owns the release policy.
- Add no database migration for a package-name decision. If a future migration is needed,
  use the ordered, replay-safe procedure in `AGENTS.md` and obtain MiniPC proof.
- Do not move or delete fixtures, raw media, historical receipts, or third-party
  material. DP-603 owns licensing and redistribution status.
- Keep `LICENSE`, `NOTICE`, and the distinction between code and content intact.

## Blocked conditions

Keep the ticket `BLOCKED` or classify the implementation incomplete if:

- DP-101..DP-106 compatibility decisions are not available for a proposed layout change;
- the package cannot be installed without a new unapproved dependency or paid service;
- the current import/CLI contract cannot be preserved during the compatibility window;
- a clean clone cannot run the deterministic profile without credentials or local files;
- license, fixture, or third-party rights evidence is missing for a packaged artifact;
- a version owner has not accepted the version-source decision needed by DP-604;
- a runtime-affecting change lacks MiniPC proof; or
- the requested work would require a remote, release, external publication, or rename
  that the owner has not authorized.

## Completion receipt — implementation 2026-09-26

Implemented. Evidence (Mac + Python 3.14.7 + 3.11.15; all commands run from an
independent clean clone, commit 1aa0e86):

- `pyproject.toml` now declares a pinned PEP 517 backend (`setuptools>=68.0,<81.0`),
  `requires-python = ">=3.11,<4.0"`, an empty runtime `dependencies` list, bounded
  `dev`/`postgres` optional-dependency groups, and explicit package mappings for
  `dichiarazioni_pubbliche`, `dichiarazioni_pubbliche.ops`, and
  `dichiarazioni_pubbliche.policy` (so `poc` is not shipped as a second top-level package),
  SPDX `license = "Apache-2.0"` with `license-files = ["LICENSE", "NOTICE"]`, and seven
  `dichiarazioni-pubbliche-*` console scripts derived from the existing module names.
- Wheel and sdist build: `dichiarazioni_pubbliche-0.0.1-py3-none-any.whl` /
  `.tar.gz` (sdist ships `poc/dichiarazioni_pubbliche/`, `LICENSE`, `NOTICE`, `pyproject.toml`).
- Fresh-env install, run from `/tmp` with **no repo on `sys.path`**:
  `import dichiarazioni_pubbliche` ok; canonical modules and subpackages import from the wheel;
  `dichiarazioni-pubbliche-review-admin --help` ok; benchmark
  `python -m dichiarazioni_pubbliche.benchmark --fixtures <repo>/poc/fixtures/italian_cases.json`
  -> `Benchmark: 5/5 passed (100%)`.
- `tests/test_packaging_metadata.py` (13 tests) enforces the metadata contract, asserts
  console scripts resolve to real callables, and **fails if any `.v0`/POC identifier is
  renamed** (the Python package/distribution identifiers; the two `config/*.v0.json`
  files remain temporary fallbacks during the DP-106 observation window, while
  `db/schema.v1.sql`, `db/job_queue.v1.sql`, and `config/*.v1.json` are canonical; the
  `dichiarazioni-pubbliche` name, and the `dichiarazioni_pubbliche` import). This is the
  documented deprecation surface; the runtime rename itself is **not** performed (DP-106
  owns it). No brand/domain decision is made (DP-701).
- Profiles `backend-minimal` / `backend-postgres` / `web` / `runtime-canary` are
  documented in `docs/release/development-environment.md` with setup/test/cleanup and a
  SKIP-vs-BLOCKED policy.
- Version/dependency authority handed to DP-604: canonical `VERSION`, web version
  independent (recorded, not forced equal), runtime vs dev deps separated.

Honest limitation (documented, not hidden): several modules resolve repo-relative
defaults as `Path(__file__).parents[2]`, which is the repo root. Under a non-editable
wheel those `config/` and `poc/fixtures/` paths do not exist, so the data-backed
commands need an explicit path flag (`--fixtures`, `--registry`, `--audit`,
`--transcript`). Every one of those flags exists; all modules still import from the
install. This is the DP-106 compatibility-window reason the checkout path remains
primary.

**AC status.** AC-601.1 PASS, AC-601.2 PASS (no import break; compat path intact),
AC-601.3 PASS, AC-601.4 PASS for the isolated profiles, AC-601.5 PASS (no rename),
AC-601.6 PASS (clean clone; no venv/node_modules/secrets needed),
AC-601.7 N/A (no DB/package-path change), AC-601.8 PASS, AC-601.9 PASS (LICENSE, NOTICE,
DP-603 inventory present), AC-601.10 PASS (no version bumped; DP-604 owns the number),
AC-601.11 PASS (no remote/release/provider/MiniPC side effect).

Not claimed: the package was **not released**, no remote or registry artifact was
created, and the POC/v0 names were **not** renamed.
