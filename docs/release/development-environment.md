# Development environment (DP-601)

Implements DP-601. Owner: DP-601. This is the authoritative package/development
contract. It records the supported versions, the named profiles, the install path, and
the compatibility surface of the `.v0` names. It does **not** perform the runtime
rename — that is DP-106 — and it does not choose a brand/domain (DP-701).

## Supported versions

| Component | Supported | Authority |
|---|---|---|
| Python | 3.11, 3.12, 3.13, 3.14 (`>=3.11,<4.0`) | `pyproject.toml` `requires-python` + classifiers |
| Node | pinned by the web lockfile and CI matrix (Node 24 in CI) | `web/package.json`, DP-602 |
| Build backend | `setuptools>=68.0,<81.0` (PEP 517) | `pyproject.toml` `[build-system]` |

The Python runtime is **stdlib-only**. `pyproject.toml` `dependencies` is empty on
purpose: an install must never silently add a provider client, an HTTP stack, or a
database driver. PostgreSQL is reached through the `psql` CLI, not a Python driver.

## The two ways to run the backend

Both work. Use the first for a newcomer and CI; the second is what an installed
distribution looks like.

### 1. Checkout path (compatibility, works with zero install)

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
```

`PYTHONPATH=poc` puts `poc/` on the path so the import name `dichiarazioni_pubbliche`
resolves. This is the canonical contributor path and the one AGENTS.md and CI use.

### 2. Installed package

```bash
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"          # or: python -m pip install .
python -c "import dichiarazioni_pubbliche; print(dichiarazioni_pubbliche.__file__)"
dichiarazioni-pubbliche-review-admin --help
```

The install exposes the import name `dichiarazioni_pubbliche` and console scripts
`dichiarazioni-pubbliche-{benchmark,public-projection,source-watcher,worker-daemon,review-admin,
scheduler-daemon,health-digest}`.

**One honest limitation.** Several runtime modules resolve repository-relative config
and content paths as `Path(__file__).parents[2]` (i.e. the *repo root*). Under a
non-editable wheel install the package lives in `site-packages/`, so those repo-relative
defaults (`config/*.json`, `poc/fixtures/`, `poc/content/`) do not exist. Every such
command accepts an explicit path override and works:

- `--fixtures` (benchmark)
- `--registry` (source_watcher)
- `--audit` / `--transcript` (claim_extraction_benchmark)
- `--output` (public_projection, requires a database DSN)

All 42 `dichiarazioni_pubbliche` modules import cleanly from an installed wheel; only these
*repo-relative default* arguments need an explicit path. This is the compatibility
window behavior DP-106 owns, and it is why the checkout path remains the primary
contributor path.

## Named profiles

| Profile | Required tools | Required behavior | Explicitly NOT required |
|---|---|---|---|
| `backend-minimal` | Python 3.11–3.14 | package import, compile, deterministic unit/regression suite, benchmark, CLI help | paid model, ASR, PostgreSQL, network, any credential |
| `backend-postgres` | `backend-minimal` + an isolated PostgreSQL | ordered migration apply/replay in an isolated DB, explicitly DB-backed tests | production data mutation, provider credentials |
| `web` | Node 24 + npm, `web/package-lock.json` | `npm ci`, `npm run check`, `npm run build`, explicit public-projection build | database, provider, LLM |
| `runtime-canary` | operator-selected MiniPC environment | ticket-specific runtime receipt + safe read-back | Mac-only evidence as a substitute |

A missing external dependency is an explicit `SKIP` (feature genuinely out of scope),
`BLOCKED` (required but unavailable), or a **failure** (deterministic, and should be
fixed) — never a silent pass. A missing provider credential may block a live receipt but
must never make a deterministic test green by selecting a different provider.

## Local demo (no provider, no database)

The frontend has a **fictional** demo projection
(`web/src/data/demo-projection.json`) used only when no explicit projection path is
configured. The UI renders a visible `Ambiente dimostrativo` banner in that state. The
demo is a UX fixture, not a real public finding.

```bash
cd web && npm ci && npm run dev
```

To build from an **explicit, approved** public projection (fails closed on the wrong
schema version or if `methodology.aggregate_person_score` is not `false`):

```bash
DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH=/abs/path/to/index.json npm run build
```

## Where credentials and private data must live

- Provider credentials, `DICHIARAZIONI_PUBBLICHE_OMNIROUTE_BASE_URL`, `DICHIARAZIONI_PUBBLICHE_DATABASE_URL`, and
  similar secrets belong in the environment or an operator-local ignored file — never in
  the repository.
- Raw media, full private transcripts, browser profiles, cookies, and production
  database dumps are ignored (`*.mp4`, `*.wav`, `data/private/`, `poc/content/*/raw/`)
  and must not be committed or copied into a clone.
- Public output comes only from the fail-closed projection, not an operational export.

## The `.v0` / POC compatibility surface (DP-106 owns the migration)

These names are **deprecated compatibility identifiers**, retained on purpose:

| Identifier | Status | Migration owner |
|---|---|---|
| `poc/` (source root) | retained | DP-106 |
| `dichiarazioni_pubbliche` (import + distribution identity) | retained | DP-106 |
| `dichiarazioni-pubbliche` (distribution name) | retained | DP-106 |
| `db/schema.v1.sql`, `db/job_queue.v1.sql` | canonical stable baselines | DP-106 |
| `config/source-registry.v1.json`, `config/transcription-policy.v1.json` | canonical runtime configs | DP-106 |
| `config/source-registry.v0.json`, `config/transcription-policy.v0.json` | temporary fallback only | DP-106 compatibility window |

**Deprecation path.** DP-106 defines a two-phase dual-resolution window: loaders prefer
the new `*.v1.json` path and fall back to the `*.v0.json` path with a diagnostic,
keeping the internal `"name": "transcription-policy-v0"` key stable, and closing the
window only after a full error-free release cycle on the MiniPC. Until DP-106 executes,
packaging work must **not** rename any of the identifiers above. The packaging tests
(`tests/test_packaging_metadata.py`) fail if a rename happens as a side effect of
environment cleanup, so the deprecation is explicit and detected — never silent.

## Version and dependency authority

- Product/package version: root `VERSION` (see
  [`versioning-policy.md`](versioning-policy.md)); mirrored in `pyproject.toml`.
- Web package version: `web/package.json`, intentionally independent.
- Runtime dependencies: `pyproject.toml` `[project]` (empty).
- Development dependencies: `pyproject.toml` `[project.optional-dependencies].dev`,
  each with lower+upper bounds.

Drift is detected by `tools/check_version_consistency.py` and
`tests/test_packaging_metadata.py`. A packaging change must not bump a version as a side
effect; DP-604 owns version/release decisions.

## Generated and ignored artifacts

Wheels, sdists, virtual environments, `node_modules/`, `.astro/`, `web/dist/`,
`__pycache__/`, and pip caches are ignored and are never required inputs to a clean-clone
test. The clean-clone procedure and its cleanup rule are in
[`../tickets/DP-605-maintainer-contributor-clean-clone.md`](../tickets/DP-605-maintainer-contributor-clean-clone.md)
and [`checklist.md`](checklist.md).
