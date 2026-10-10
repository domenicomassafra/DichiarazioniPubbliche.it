# Dichiarazioni Pubbliche

> **Memoria verificabile delle dichiarazioni pubbliche.**

Dichiarazioni Pubbliche is an open-source, Italy-first system for preserving and examining public
statements with source provenance, evidence, review history, corrections, and machine-
readable public records.

The project is deliberately **not** a politician ranking engine and **not** an LLM that
publishes a verdict after one prompt. Retrieval, evidence approval, verification,
publication, reply, and correction are separate auditable stages.

> **Brand decision:** **Dichiarazioni Pubbliche** is the owner-approved product name as of 2026-10-03.
> Canonical domain label: `dichiarazionipubbliche.it`. Trademark clearance, registrar ownership,
> and public-launch readiness remain separate pre-launch gates.

Canonical source repository: `domenicomassafra/DichiarazioniPubbliche.it`.

**Current status / next-agent entry point (2026-10-10):** [`HANDOFF.md`](HANDOFF.md),
[`FINAL-PENDING-GRILLING-2026-10-10.md`](FINAL-PENDING-GRILLING-2026-10-10.md),
[`MEGA-HANDOFF-2026-10-10.md`](MEGA-HANDOFF-2026-10-10.md), and
[`LAUNCH.md`](LAUNCH.md). The repository being merged and CI passing does **not**
mean the editorial product or latest website build has been released; the
current 125-ticket ledger is in [`PLAN.md`](PLAN.md).

## Why this exists

Public statements are easy to publish and hard to remember accurately over time.
Dichiarazioni Pubbliche aims to build a durable public record that can answer:

- what was said, when, where, and in what wording;
- which public source supports the attribution;
- what checkable atomic claim was extracted;
- which evidence was actually fetched and reviewed;
- which verification rule produced a finding;
- whether the finding was corrected, disputed, or answered later;
- how statements on the same topic changed over time.

The public product is statement-centered: canonical Statement pages connect to Person
archives, Topic dossiers, original Content pages, reviewed longitudinal Traces, Method,
and a stable public JSON/JSON-LD/API surface. The canonical page architecture is
[`docs/35-public-product-architecture-v3.md`](docs/35-public-product-architecture-v3.md).

## Core guarantees

- **Fail closed.** Missing or stale provenance means hold/omit, not a weaker verdict.
- **No auto-publication.** Model output is never publication authorization.
- **No person scores.** No global truthfulness, reliability, competence, or political
  ranking.
- **No biometric identification.** Speaker provenance is non-biometric.
- **Time-aware verification.** Future evidence is not silently used to judge an earlier
  statement.
- **Append-only review history.** Corrections and rights of reply do not rewrite history
  invisibly.
- **Static-first public reads.** The public request path does not depend on a live LLM.
- **Minimal infrastructure.** PostgreSQL and simple workers first; new infrastructure
  needs evidence.

The complete product constitution is in [`PRODUCT.md`](PRODUCT.md).

## Architecture in one minute

```text
sources
  -> discovery/acquisition
  -> transcript variants + canonical transcript
  -> non-biometric speaker provenance
  -> atomic claims
  -> evidence retrieval + structured observations
  -> deterministic/versioned verification
  -> finding + explicit review
  -> fail-closed public projection
  -> JSON / JSON-LD / HTML / future read-only API
  -> correction / reply / re-analysis
```

The authoritative Git checkout is developed on Mac. Long-running backend runtime proof is
performed on the MiniPC. See [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Project status

The repository contains production-shaped backend/runtime code, a live MiniPC runtime,
and a read-only public API/web foundation, but it is **pre-1.0** and does not yet ship the
final public product release.

Already implemented and tested:

- source registry, polling, scheduler, PostgreSQL queue, retries, leases, blocked states;
- caption/transcript ingestion and canonical transcript handling;
- claim extraction contracts and provider/cost gates;
- private Research Corpus persistence, immutable captures/passages, retention and replay;
- corpus search, explainable entity/topic/event resolution and proposition clustering;
- bounded research discovery and capture/parser tooling;
- passage candidate extraction, claim-candidate promotion, matching and coverage-needs planning;
- contextual source intelligence with scoped evidentiary roles and fail-closed suitability checks;
- safe official-evidence fetching, caching, queries, and observation extraction;
- deterministic verification with temporal cutoff;
- explicit evidence/speaker/finding review events;
- non-biometric speaker provenance;
- longitudinal relation candidates and re-analysis triggers;
- fail-closed JSON/JSON-LD/HTML public projection;
- append-only correction/right-of-reply lifecycle;
- adversarial replay/provenance/fetch/retention hardening.

Known external live blockers are tracked as tickets rather than hidden by fallbacks:

- `DP-201` — official OmniRoute tiered claim-extraction path;
- `DP-204` — live remote-ASR receipt requires configured provider credential.

At the verified 2026-10-10 checkpoint, `main` and `origin/main` matched,
GitHub CI passed, and no other local branch, worktree or stash existed.
**90/125 tickets were DONE**; a full editorial release remained **NO-GO** and a
production website deployment was not implied by the GitHub push. Read
[`HANDOFF.md`](HANDOFF.md) for the exact current verification steps; the
[`2026-10-03 consolidation`](docs/reviews/consolidation-baseline-2026-10-03.md)
remains historical evidence, not a current runtime report.

See [`PLAN.md`](PLAN.md) for the complete path to stable v1.

## Repository map

```text
.
├── PRODUCT.md          product constitution and invariants
├── CONTEXT.md          canonical domain vocabulary
├── ARCHITECTURE.md     system boundaries and runtime topology
├── PLAN.md             milestone + ticket graph to v1
├── AGENTS.md           execution rules for humans and coding agents
├── CONTRIBUTING.md     contribution workflow
├── GOVERNANCE.md       decision hierarchy
├── SECURITY.md         vulnerability policy
├── db/                 PostgreSQL schema, queue contract, migrations
├── config/             versioned runtime policies/registries
├── poc/dichiarazioni_pubbliche/
│   └──                current Python runtime modules
├── tests/              deterministic/regression/adversarial tests
├── web/                static-first Astro public/Studio frontend
├── tools/               deterministic contributor/repository/licensing checks
├── docs/adr/            architecture decisions
├── docs/tickets/        implementation specs
├── docs/release/        versioning, changelog, release checklist, onboarding
├── docs/licensing/      fixture/data rights inventory and attribution
├── docs/                historical research and implementation receipts
└── research/            source/reference inventory
```

[`docs/README.md`](docs/README.md) explains which documents are canonical and which are
historical evidence.

## Quick start

Requirements: Python 3.11, 3.12, 3.13, or 3.14 (see
[`docs/release/development-environment.md`](docs/release/development-environment.md)
for the supported matrix and the `backend-minimal` / `backend-postgres` / `web`
profiles).

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
```

No paid model/provider credential is required for the deterministic contributor suite.

One command runs the full deterministic acceptance set (repository contract,
fixture/data licensing inventory, version/changelog consistency) with no network,
no credentials, and no PostgreSQL:

```bash
python3 tools/check_contributor_acceptance.py
```

To work against an installed package instead of the checkout:

```bash
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"
```

Frontend development:

```bash
cd web
npm install
npm run check
npm run build
```

`web/README.md` documents how to build from an explicitly supplied, fail-closed
public projection. Missing/invalid public projection paths **fail the build**;
the fictional demo is enabled only by setting
`DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1` for local tests, and may never be
deployed publicly.

Useful entry points:

```bash
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.source_watcher --help
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.worker_daemon --help
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.review_admin --help
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.public_projection --help
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.claim_extraction_benchmark --help
```

## Data and safety

Raw media, private transcripts, evidence bodies, provider credentials, and production
database dumps do not belong in Git. Public output is produced through an explicit
projection and is not an operational DB export.

This project works with public-interest and potentially reputationally sensitive
material. Read [`PRODUCT.md`](PRODUCT.md) and [`SECURITY.md`](SECURITY.md) before changing
review/publication logic.

## Contributing

Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`AGENTS.md`](AGENTS.md). Significant
work should map to a ticket in [`PLAN.md`](PLAN.md) / [`docs/tickets/`](docs/tickets/),
with tests and MiniPC runtime proof where required.

Security issues should not be filed publicly; follow [`SECURITY.md`](SECURITY.md).

## License

Repository code is licensed under the [Apache License 2.0](LICENSE). Third-party source
material, media, datasets, evidence, trademarks, and service terms retain their own
rights and are not relicensed by the code license.

Every tracked fixture, dataset, and visual reference has a row in the versioned
[fixture/data licensing inventory](docs/licensing/README.md), recording provenance,
license evidence, attribution, personal-data class, and redistribution status. Rows with
unresolved rights are held at `pending-review`/`blocked` and must not ship in a release
artifact or public projection.

## Important legal note

The legal/safety documents in this repository are product research, not legal advice.
A qualified Italy/EU legal review remains a pre-launch ticket.
