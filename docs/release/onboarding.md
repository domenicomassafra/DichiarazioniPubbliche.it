# Onboarding and contributor guide

Implements DP-605. Owner: DP-605. This is the role-based, navigable onboarding path
for contributors, maintainers, and operators/integrators. It points to the canonical
contracts (`PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`, `AGENTS.md`, `SECURITY.md`,
ADRs, tickets) rather than restating them.

> **Canonical source remote:**
> `https://github.com/domenicomassafra/DichiarazioniPubbliche.it`. A source remote does
> not imply that a package, release, production dataset or public deployment has been
> approved.

## Pick your path

| Reader | Go to | Required outcome | May skip |
|---|---|---|---|
| **New contributor** | [Contributor path](#1-contributor-path) | install, deterministic tests, web check/build, read a ticket, run the labeled local demo | PostgreSQL, providers, MiniPC |
| **Maintainer** | [Maintainer path](#2-maintainer-path) | run migration canaries in an isolated DB, inspect receipts, review projection, prepare release evidence | paid provider unless a ticket requires it |
| **Operator / integrator** | [Operator path](#3-operator--integrator-path) | consume the approved public projection/API, respect no-publication and no-raw-data boundaries, record runtime proof | local contributor setup |

Supported versions and the four named profiles (`backend-minimal`,
`backend-postgres`, `web`, `runtime-canary`) are defined once, in
[`development-environment.md`](development-environment.md).

---

## 0. Prerequisites

All paths assume:

- **Python 3.11, 3.12, 3.13, or 3.14** (`python3 -V`),
- **Node 24 + npm** for the web path (`node -v`, `npm -v`),
- **Git**,
- **PostgreSQL client (`psql`)** only for the maintainer DB path,
- **no** API keys, database dumps, or media on your machine for any path below.

Check your toolchain:

```bash
python3 -V && node -v && npm -v && git --version && (command -v psql || echo "psql: not installed (only needed for the maintainer DB path)")
```

---

## 1. Contributor path

Goal: from a clean source copy, reach a **passing deterministic test suite** and a
**visible local demo**, with no credentials, no PostgreSQL, and no paid provider.

### 1.1 Obtain the source

Clone the canonical repository and check out the exact candidate commit:

```bash
COMMIT=<candidate-commit>
SCRATCH="$(mktemp -d)/dichiarazioni-pubbliche"
git clone https://github.com/domenicomassafra/DichiarazioniPubbliche.it.git "$SCRATCH"
cd "$SCRATCH" && git checkout --detach "$COMMIT"
git status --short          # must be empty
```

`origin` must resolve to the canonical repository above. A clean clone proves the source
tree is reproducible; release/deployment authority remains a separate gate.

Never copy credentials, browser profiles, raw media, private transcripts, or local
databases into the clone. Those are ignored in Git (`.gitignore`) and must stay that
way.

### 1.2 Run the deterministic backend checks

From the clone root (the canonical commands from `AGENTS.md`):

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
```

Expected: compile is silent; the suite ends `OK`; the benchmark prints
`Benchmark: N/N passed (100%)`. None of these need a credential, a network, or a
database.

### 1.3 Run the repository acceptance check

One command that also runs the licensing and version gates:

```bash
python3 tools/check_contributor_acceptance.py
```

Expected: `OK: contributor acceptance satisfied.`

### 1.4 (Optional) Run the installed package

```bash
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"
python -c "import dichiarazioni_pubbliche; print(dichiarazioni_pubbliche.__file__)"
PYTHONPATH=poc python -m dichiarazioni_pubbliche.benchmark   # or: --fixtures "$PWD/poc/fixtures/italian_cases.json"
```

See [`docs/release/development-environment.md`](development-environment.md)
for the honest limitation: repo-relative config/content paths (`--fixtures`,
`--registry`, `--audit`) must be passed explicitly under a non-editable wheel
install. All modules still import from the install.

### 1.5 Frontend check and build

```bash
cd web
npm ci          # from the committed lockfile; do not edit package-lock.json by hand
npm run check   # astro check
npm run build   # static build from the fictional demo projection
cd ..
```

Expected: `astro check` reports 0 errors; the build completes and lists the static
routes. Without any configuration the build uses the **fictional** demo projection
(`web/src/data/demo-projection.json`) and the UI shows a visible `Ambiente
dimostrativo` banner. That is a UX fixture, **not** a real public finding.

### 1.6 Local demo

```bash
cd web && npm run dev
```

Browse the local dev server. The demo banner makes the fictional state visible. If
you instead have an **approved** public projection file, build from it explicitly:

```bash
DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH=/abs/path/to/index.json npm run build
```

The build **fails closed** if the projection is missing or its `schema_version` is not
`dichiarazioni-pubbliche-public-v2` (or `methodology.aggregate_person_score` is not `false`). It
never silently falls back to the demo when an explicit path is set.

### 1.7 Cleanup

```bash
rm -rf .venv web/node_modules web/dist web/.astro
rm -rf *.egg-info build dist          # left by `pip install -e .` / `python -m build`
find . -name __pycache__ -type d -prune -exec rm -rf {} +
git status --short          # must be empty
```

`pip install -e .` writes `dichiarazioni_pubbliche.egg-info/` into the checkout and

**Failure ownership:** if a deterministic backend/web check fails, that is a real
contributor bug — open an issue with a reproducible input. If a check is `BLOCKED`
because a provider/PostgreSQL/MiniPC credential is absent, that is expected and
correct; see the operator path.

---

## 2. Maintainer path

Adds the **isolated PostgreSQL** migration canary and release-evidence preparation on
top of the contributor path.

### 2.1 Isolated database + ordered migrations (never production)

PostgreSQL is required **only** for the `backend-postgres` profile. Use a disposable
database/schema you created for this purpose. **Production data is never a test
fixture and must never be mutated to obtain a pass.**

```bash
# a throwaway cluster/database you created for this purpose
export ISOLATED_DSN="postgresql:///dichiarazioni_pubbliche_canary"   # your local disposable DB

# apply the baseline + ordered migrations, failing on the first error
psql "$ISOLATED_DSN" -v ON_ERROR_STOP=1 -f db/schema.v1.sql
for m in db/migrations/*.sql; do
  echo "== applying $m"
  psql "$ISOLATED_DSN" -v ON_ERROR_STOP=1 -f "$m" || { echo "MIGRATION FAILED: $m"; exit 1; }
done

# where a migration claims idempotence, replay it once to prove it
for m in db/migrations/*.sql; do
  psql "$ISOLATED_DSN" -v ON_ERROR_STOP=1 -f "$m" || { echo "REPLAY FAILED: $m"; exit 1; }
done
echo "migration apply + replay OK in isolated DB"
```

A failed migration leaves the ticket `BLOCKED`; it is never "fixed" by weakening a
constraint or by editing production.

### 2.2 Database-backed tests

Only tests that explicitly require PostgreSQL need the isolated DSN. The
deterministic contributor suite does **not**. Provide the DSN via the environment (not
in the repo) for the DB-backed tests only.

### 2.3 Review the public projection and receipts

Review the fail-closed public projection and any receipts before a release. Keep
Mac development evidence and MiniPC runtime proof distinct (see the operator path and
`docs/release/checklist.md`).

### 2.4 Prepare release evidence

Follow [`docs/release/checklist.md`](checklist.md) end to end. It records
the commit, version, tool versions, artifact hashes, and each gate's PASS/BLOCKED. The
version/changelog gate is:

```bash
python3 tools/check_version_consistency.py
```

**Release authority remains blocked** until the owner approves the release and legal,
registry/signing, dataset and deployment gates are complete. The canonical source remote
already exists; that fact alone does not authorize a tag, package publication or public
deployment.

**Failure ownership:** an isolated-DB migration failure is a maintainer/database
issue; an unresolved licensing row is a rights issue (DP-603, `docs/licensing/`); a
missing MiniPC receipt is a runtime issue (operator path).

---

## 3. Operator / integrator path

Goal: consume the approved public projection/API safely and record runtime proof.

### 3.1 Read path

The public read path depends only on the approved, fail-closed public projection
(`dichiarazioni-pubbliche-public-v2`). There are **no LLM calls, provider calls, database
credentials, or operational-table reads** in the public request path. Static public
HTML is pre-rendered from the approved projection.

### 3.2 Boundaries you must respect

- **No auto-publication.** Operator/model output is never publication authorization.
- **No raw data.** Never expose raw transcripts, evidence bodies, credentials, or
  operational DB exports through a public surface. Public output is a sanitized
  projection only.
- **No scores.** No person-level truthfulness/reliability/political ranking or
  biometric identity matching.
- **Right of reply / corrections** are append-only and private by default.

### 3.3 Runtime proof (MiniPC is the runtime authority)

Long-running backend runtime is proven on the **MiniPC**, not on a Mac. A runtime
claim records: the MiniPC mirror hash, migration result, service/command exit codes,
and the actual read-back state. **Mac-only evidence is explicitly insufficient** and
does not substitute for a MiniPC receipt; without it, the runtime claim stays
`BLOCKED`.

A live provider/ASR/evidence step without a configured credential is `BLOCKED` — never
swap in a different provider or fabricate a receipt to make it green.

### 3.4 Known external blockers (tracked, not hidden)

- `DP-201` — official OmniRoute tiered claim-extraction path;
- `DP-204` — live remote-ASR receipt requires a configured provider credential.

**Failure ownership:** a projection that fails closed, or a provider that returns
`BLOCKED`, is working as designed. Do not "fix" it by weakening a gate.

---

## 4. Safety, licensing, and versioning handoff

This guide links to the canonical contracts and does not duplicate them:

- [`PRODUCT.md`](../../PRODUCT.md), [`CONTEXT.md`](../../CONTEXT.md), [`ARCHITECTURE.md`](../../ARCHITECTURE.md), [`AGENTS.md`](../../AGENTS.md) — invariants and authority;
- [`SECURITY.md`](../../SECURITY.md) — private vulnerability reporting (a final public
  security contact remains an owner decision while no remote exists);
- [`docs/adr/0005-apache-2-core-license.md`](../adr/0005-apache-2-core-license.md) and [`docs/licensing/`](../licensing/) — the Apache-2.0 **code** boundary and the separate **data/fixture** rights inventory (DP-603);
- `docs/release/development-environment.md` — profiles, supported versions, and the
  `.v0`/POC compatibility surface (DP-601, migration owned by DP-106);
- [`docs/release/versioning-policy.md`](versioning-policy.md) and
  [`docs/release/changelog-policy.md`](changelog-policy.md) — version
  and changelog contract (DP-604);
- [`tools/check_repository_contract.py`](../../tools/check_repository_contract.py) and
  `.github/workflows/ci.yml` — CI and clean-clone checks (DP-602).

**Do not add a fixture or donor artifact** without recording its provenance, license,
attribution, and redistribution status in the DP-603 inventory (see
[`docs/licensing/README.md`](../licensing/README.md)). Do not add third-party code
whose license is incompatible with the Apache-2.0 core. Do not rename the
`dichiarazioni_pubbliche` / `schema.v0` / `*.v0` identifiers — DP-106 owns that migration —
and do not claim stable API/SDK/MCP/release availability, which this pre-1.0
repository does not provide.

## 5. Clean-clone dry-run receipt

The DP-605 proof — a real dry run of this guide from an independent clean clone — is
recorded in the DP-605 ticket's completion receipt. The recipe is:

1. `git clone --no-hardlinks <local-source> "$SCRATCH"` and `git checkout --detach <commit>`;
2. run §1.2, §1.3, §1.5 in order, capturing each exit code;
3. run the clean-clone job from `.github/workflows/ci.yml` (`clean-clone`) for the
   package-install smoke;
4. record tool versions, `git status --short`, and the §1.7 cleanup result;
5. classify anything remote-dependent as `PENDING-REMOTE` / `PENDING-OWNER` /
   `BLOCKED`.

The proof creates no remote, release, issue, PR, public site, provider call, or
external publication.
