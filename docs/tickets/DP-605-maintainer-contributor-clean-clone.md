# DP-605 — Maintainer and contributor documentation dry-run from a clean clone

Status: DONE
Milestone: M6 — open-source and release hardening
Depends on: DP-001, DP-601, and the documented DP-602/DP-603/DP-604 gates
Launch state: documentation and clean-clone proof only; no release or public publication

## Problem

The repository has useful README, contribution, security, architecture, and ticket
contracts, but the original contributor path required readers to infer which commands
were mandatory, which were optional, where PostgreSQL/provider credentials belonged, and
how to run a local demo. The original setup text also contained a generic clone
placeholder. A documentation page that only works in the original working directory is
not an onboarding proof.

The required proof must be performed by a fresh clean clone of the exact candidate commit
and must preserve the current POC/v0 names. Hosted CI may create that detached proof from
its checked-out commit without implying release authorization. It must not turn a Mac-only
check into a runtime or release claim.

## Outcome

Deliver a role-specific onboarding and operations guide that lets a new contributor or
maintainer:

1. clone or obtain the exact candidate source safely;
2. create an isolated Python/Node environment;
3. run deterministic backend and web checks without paid credentials;
4. run a clearly labeled fictional local demo;
5. run optional PostgreSQL migration tests only in a disposable database;
6. understand provider-blocked states and private-data boundaries;
7. find the correct ticket, security, license, and release handoff; and
8. leave the source tree clean.

The guide must include a recorded dry-run receipt from an independent clean clone. It
must not invent a public repository URL, security contact, or release destination.

## Baseline and evidence limits

Current baseline:

- `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `SECURITY.md`, `GOVERNANCE.md`, and
  `web/README.md` are the contributor-facing entry points;
- backend commands currently require Python 3.11+ and `PYTHONPATH=poc` where applicable;
- the web frontend uses `npm ci`, `npm run check`, and `npm run build`;
- the public frontend has a fictional fallback projection and a fail-closed explicit
  projection path;
- PostgreSQL is required only for explicitly database-backed tests/migrations; and
- the canonical remote is `https://github.com/domenicomassafra/DichiarazioniPubbliche.it`.

No separate DP-601 baseline or W0R/W0P file was present during this specification. The
missing artifacts must be checked before closure; no report path is fabricated.

## Scope

### 1. Reader paths

The documentation must provide three explicit paths without mixing their authority:

| Reader | Required outcome | May skip |
|---|---|---|
| New contributor | install, deterministic tests, web check/build, ticket reading, safe local demo | PostgreSQL, providers, MiniPC |
| Maintainer | run migration canaries, inspect private health/receipts, review public projection, prepare release evidence | paid provider only when not required by the ticket |
| Operator/integrator | use approved public projection/API, respect no-publication and no-raw-data boundaries, record runtime proof | local contributor setup not relevant to the read path |

Each path must state prerequisites, exact commands, expected result, cleanup, and the
owner of a failure. A command that needs a credential must be marked `BLOCKED` when the
credential is absent; it must not be presented as a passing default.

### 2. Source acquisition and clean-clone proof

The canonical repository now has a GitHub remote. Clean-clone proof should therefore use
that hosted remote for current candidates; historical receipts that predate the remote
may retain their exact local-clone method as evidence of what was run at the time.

The guide must distinguish:

- `git clone` instructions for a future confirmed remote, using a placeholder that is
  visibly a placeholder until the owner supplies the URL;
- the local dry-run method used for this repository; and
- the prohibition on copying credentials, browser profiles, raw media, private
  transcripts, or local databases into a clone.

The clean-clone proof must start from a directory with no inherited virtualenv,
`node_modules`, `.astro`, build output, provider environment, or untracked source files.
After the documented commands, the source tree must have no generated source artifact or
uncommitted change. Ignored caches may exist only if the documented cleanup removes them
or the receipt records their exact location.

### 3. Minimal contributor walkthrough

The walkthrough must reach a useful result quickly and use deterministic fixtures:

1. verify Python and Node prerequisites;
2. create isolated environments using the commands selected by DP-601;
3. install the Python package or use the documented compatibility path;
4. run compile, unit/regression, and benchmark commands;
5. install web dependencies from `web/package-lock.json`, then run `npm run check` and
   `npm run build`;
6. run the local demo using the clearly labeled fictional projection;
7. optionally run the explicit public-projection build with a generated, approved
   projection file; and
8. inspect the resulting public/development output for demo labeling and absence of
   private fields.

The walkthrough must not require a paid model, live ASR, remote evidence provider, or
production PostgreSQL. It must not claim that a demo fixture is a real public finding.

### 4. Optional database/runtime path

The maintainer path must document the isolated PostgreSQL setup and ordered migration
procedure with `ON_ERROR_STOP`. It must state that production data is never a test
fixture, that replay is required where migrations claim idempotence, and that a failed
migration leaves the ticket blocked.

The operator path must distinguish Mac development evidence from MiniPC runtime proof.
A runtime ticket must record the MiniPC mirror hash, migration result, service/command
exit codes, and actual read-back state. No remote deployment is part of onboarding.

### 5. Safety, licensing, and versioning handoff

The guide must link to the canonical contracts rather than restating them:

- `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`, and `AGENTS.md` for invariants;
- `SECURITY.md` for private vulnerability reporting and the fact that a final public
  security contact remains an owner decision until explicitly approved;
- ADR 0005 and DP-603 for code/content licensing and fixture inventory;
- DP-602 for CI and clean-clone checks; and
- DP-604 for the provisional version source, changelog, and release checklist.

It must use the current `dichiarazioni_pubbliche`, `schema.v0`, and `*.v0` names until their
owners authorize a migration. It must not promise stable API, SDK, MCP, or release
availability.

## Non-goals

- creating or guessing a Git remote, public URL, issue tracker, or security contact;
- renaming the repository, package, schema, or POC/v0 files;
- publishing a website, package, dataset, release, or API;
- requiring paid providers or live credentials for the default path;
- adding a container, VM, service, or infrastructure solely for onboarding;
- treating a local demo as public data or a release acceptance; or
- replacing canonical docs with a second architecture or handoff.

## Acceptance criteria

- [ ] **AC-605.1 — Role-specific guide:** The documentation has separate, navigable
  contributor, maintainer, and operator paths with prerequisites, commands, expected
  results, cleanup, and failure ownership.
- [ ] **AC-605.2 — Clean-clone execution:** An independent clone of the exact candidate
  commit completes the documented minimal path with no local-only file, credential,
  virtualenv, `node_modules`, raw media, or provider state.
- [ ] **AC-605.3 — Backend result:** The clean clone passes the documented compile,
  full unit/regression, deterministic benchmark, and package/CLI smoke checks with no
  paid provider.
- [ ] **AC-605.4 — Web/demo result:** `npm ci`, `npm run check`, and `npm run build` pass;
  the fictional demo is visibly labeled and the explicit public-projection build fails
  closed for an incompatible or missing projection.
- [ ] **AC-605.5 — Optional database boundary:** The documented PostgreSQL path uses an
  isolated database/schema, applies ordered migrations with `ON_ERROR_STOP`, and never
  instructs a contributor to mutate production data.
- [ ] **AC-605.6 — Provider/blocker honesty:** Missing provider credentials or MiniPC
  access are recorded as `BLOCKED`/`PENDING-OWNER`, with no substitute provider,
  fabricated receipt, or Mac-only runtime claim.
- [ ] **AC-605.7 — Safety links:** The guide points to the canonical product, provenance,
  privacy, security, license, and ticket gates and does not expose raw/private content or
  credentials in examples.
- [ ] **AC-605.8 — Licensing evidence:** A clean clone can locate `LICENSE`, `NOTICE`, and
  the DP-603 inventory, and the guide tells contributors not to add a fixture or donor
  artifact without evidence/attribution.
- [ ] **AC-605.9 — Versioning handoff:** The guide identifies the provisional version
  sources and directs release/version decisions to DP-604; it does not hard-code a fake
  release number or claim stable v1.
- [ ] **AC-605.10 — Tree hygiene:** After the dry-run, `git status --short` and an
  artifact-path audit show no uncommitted source change or generated output in the
  repository. Cleanup instructions remove only generated/local artifacts.
- [ ] **AC-605.11 — No external side effect:** The proof creates no remote, release,
  issue, PR, public site, provider call, or external publication.
- [ ] **AC-605.12 — M6 audit:** The DP-601..DP-607 ticket completeness/collision audit
  passes, and the documentation links resolve from the clean clone.

## Validation / proof

The implementation must produce a dry-run receipt with:

- exact commit and local-clone method;
- operating system, Python, Node, npm, and package-manager versions;
- command-by-command exit codes and sanitized output references;
- package/build artifact hashes where applicable;
- the fictional-demo marker and public-projection build result;
- `git status --short`, generated-artifact audit, and cleanup result;
- optional isolated migration receipt, if run; and
- explicit `PENDING-REMOTE`, `PENDING-OWNER`, or `BLOCKED` classifications.

Run the standard checks from the clean clone:

```text
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
cd web && npm ci && npm run check && npm run build
cd .. && git diff --check
```

Then run the relative-link audit, DP-603 inventory check, version/changelog check, and
DP-601..DP-607 completeness/collision audit. The receipt must not include raw transcript,
provider, credential, or private database contents.

## Documentation, data, and migration impact

- Update the existing contributor and web documentation in the implementing change; do
  not create a competing architecture or handoff document.
- Add no code or database migration for documentation-only work. If the documented
  command path changes, DP-601 owns package compatibility and DP-602 owns CI.
- Do not copy private fixtures or raw media into the clean-clone proof. The DP-603
  inventory records any data used by the demo.
- Do not edit `PLAN.md`; the M6 sequence remains canonical.
- DP-604 consumes the dry-run receipt as release-readiness evidence, not as a release.

## Blocked conditions

Keep the ticket `BLOCKED` or classify the dry-run incomplete if:

- a canonical remote is required for the proof but the owner has not supplied one;
- a documented command needs a local file, credential, provider, or service not declared
  in the guide;
- the clean clone cannot run the deterministic profile;
- the demo can be mistaken for a real/public finding or contains private data;
- a database instruction could touch production data;
- the final security contact, legal/rights decision, or public URL is needed but remains
  undecided;
- runtime behavior is claimed without MiniPC proof; or
- the guide would require a rename, release, remote, or external publication.

## Completion receipt — implementation + real dry run 2026-09-26

The dry run was **actually performed** from an independent clean clone, and it found
and fixed four real documentation defects — the doc was corrected, not the report.

**Receipt.**

- commit: `1aa0e8627875a1c61cb3b5bb2118af21c4bddb87`
- clone method at the time of this historical receipt: `git clone --no-hardlinks <local
  authoritative checkout>` into a fresh `mktemp -d`; this predates creation of the
  canonical GitHub remote and is preserved only as execution evidence for that run.
- host: Darwin 25.6.0 arm64; Python 3.14.7; Node v24.18.0; npm 11.16.0; git 2.54.0.
- `git status --short` after clone: empty.

**Defects the dry run found (all fixed, then re-verified from a fresh commit):**

1. every relative link in `docs/release/onboarding.md` was repo-root-relative and
   therefore **broken** outside the working directory (18 findings) — rewritten
   relative to `docs/release/`;
2. `docs/release/README.md` and the checklist pointed at a `.yaml` inventory while the
   generated artifact is `.json`;
3. the guide claimed `git status`/remotes showed "no remote" — a local clone *does* set
   an `origin` to the local path; the historical claim was corrected, and the guide now
   points directly at the canonical GitHub source remote;
4. `pip install -e .` leaves `dichiarazioni_pubbliche.egg-info/` in the tree, so the
   documented cleanup did not reach an empty `git status` — `*.egg-info/`, `build/`,
   `dist/` are now ignored and removed by the documented cleanup.

**Final run, all green from the clean clone:** `compileall` exit 0; **353 tests OK**;
`benchmark 5/5 passed (100%)`; contributor acceptance OK (repository contract,
licensing inventory 36 rows / 340 tracked files, inventory freshness, version
consistency); wheel+sdist build; fresh-env install with **no repo on `sys.path`** — all
**42 modules** import, console script ok, benchmark 5/5; `npm ci` (284 packages),
`astro check` **0 errors / 0 warnings**, build **12 pages**; `Ambiente dimostrativo`
banner present in the built demo; an invalid explicit projection is **rejected**
(fail-closed); `git diff --check` exit 0; post-cleanup `git status --short` empty and
no generated artifact remains. No tracked raw media, credential, or db dump; the
`raw/` transcript dir is ignored and untracked.

**Guide.** `docs/release/onboarding.md` provides separate contributor, maintainer, and
operator/integrator paths, each with prerequisites, exact commands, expected results,
cleanup, and failure ownership. It links (never restates) `PRODUCT.md`, `CONTEXT.md`,
`ARCHITECTURE.md`, `AGENTS.md`, `SECURITY.md`, ADR 0005, the DP-603 inventory, DP-602 CI,
and DP-604 versioning. It keeps the `dichiarazioni_pubbliche` / `schema.v0` / `*.v0` names,
promises no stable API/SDK/MCP/release, invents no public URL or security contact, and
shows the isolated-PostgreSQL migration path with `ON_ERROR_STOP` and a required replay.

**AC status.** AC-605.1 PASS, AC-605.2 PASS, AC-605.3 PASS, AC-605.4 PASS,
AC-605.5 PASS (documented; no migration was run in this candidate because it changes no
persistence), AC-605.6 PASS, AC-605.7 PASS, AC-605.8 PASS, AC-605.9 PASS, AC-605.10
PASS, AC-605.11 PASS (no remote, release, issue, PR, site, provider call, or external
publication), AC-605.12 PASS (link/collision/inventory/version audits green).

**Follow-up 2026-10-05.** The canonical GitHub repository and issue tracker now exist, so
the historical `PENDING-REMOTE` classification is closed. The guide and release policy
were corrected anywhere they still said otherwise. The hosted DP-602 matrix has a real
successful Actions receipt, and the `clean-clone` job now performs the package-install
smoke the guide already promised plus the DP-604 reproducible-artifact check.

Remaining external decisions are `PENDING-OWNER`: final public security contact,
qualified legal/privacy review (DP-307/DP-702), registry/signing/hosting choices, and
release authorization. They are release/launch gates rather than missing contributor or
maintainer setup, so the DP-605 documentation/dry-run ticket is complete without
inventing them.
