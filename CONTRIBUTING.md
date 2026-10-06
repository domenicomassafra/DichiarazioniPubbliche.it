# Contributing to Dichiarazioni Pubbliche

Thank you for helping improve Dichiarazioni Pubbliche. This project handles public-interest statements
and reputationally sensitive records, so correctness, provenance, and restraint matter
more than feature velocity.

## Before contributing

Read `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`, `AGENTS.md`, and the relevant ADRs.
Contributions that bypass the publication/provenance rules will not be accepted even if
they make the demo look better.

## Ways to contribute

- bug reports with reproducible inputs;
- source adapters and deterministic extractors;
- tests and adversarial fixtures;
- evidence/query adapters for authoritative public sources;
- public-data/API/frontend work over the approved public projection;
- documentation, accessibility, internationalization, and developer experience;
- security reports through the private process in `SECURITY.md`;
- research/design proposals as an issue or ADR candidate.

## Development setup

Requirements:

- Python 3.11, 3.12, 3.13, or 3.14;
- Git;
- Node 24 + npm, only for the frontend;
- PostgreSQL only for tests/features that explicitly require it.

The deterministic suite has no paid-provider requirement:

```bash
# No public remote is configured yet; clone from the authoritative checkout.
git clone --no-hardlinks <path-to-authoritative-checkout> DichiarazioniPubbliche.it
cd DichiarazioniPubbliche.it
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
```

The full deterministic acceptance set — repository contract, fixture/data licensing
inventory, and version/changelog consistency — is one command, and needs no network,
no credentials, and no PostgreSQL:

```bash
python3 tools/check_contributor_acceptance.py
```

New contributors should follow
[`docs/release/onboarding.md`](docs/release/onboarding.md) (contributor,
maintainer, and operator paths). Supported versions, the named profiles
(`backend-minimal`, `backend-postgres`, `web`, `runtime-canary`), and the
`poc`/`dichiarazioni_pubbliche`/`*.v0` compatibility surface are documented in
[`docs/release/development-environment.md`](docs/release/development-environment.md).

Do not put API keys, raw private transcripts, downloaded media, or production database
dumps in the repository.

## Issue-first work

Substantial changes should have a ticket or issue describing:

- user/problem statement;
- domain terms involved;
- invariants that must remain true;
- acceptance criteria;
- tests and runtime proof;
- explicit non-goals;
- data/schema/public-output impact.

The repo-local ticket format is documented in `docs/tickets/README.md`. It exists because
the project may be worked on before a public GitHub remote is configured; public issues
can later link to or replace these specs.

## Pull requests

Keep PRs reviewable and coherent. A PR should:

- implement one ticket or tightly related set of tickets;
- include tests for behavior changes;
- update canonical docs or ADRs when it changes a contract;
- state whether it changes public projection/schema;
- state whether MiniPC acceptance is required and provide the receipt when available;
- avoid drive-by refactors unrelated to the spec.

## Code review

Review along two independent axes:

1. **Spec:** does the change implement the ticket/ADR/product requirement?
2. **Standards:** is the code safe, local, testable, comprehensible, and consistent with
   the repository architecture?

A change can pass one axis and fail the other.

## Tests

Run focused tests while working, then before completion:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
python3 tools/check_contributor_acceptance.py
git diff --check
```

Tests must be deterministic by default. Live provider tests should be separately gated,
bounded by cost, and must never be necessary for basic contributor CI.

## Database and migrations

- prefer additive, replay-safe migrations;
- preserve append-only review/correction history;
- do not weaken foreign keys or provenance checks merely to simplify fixtures;
- never run destructive experiments against production;
- document rollout order when code depends on a new schema capability.

## Evidence and external code

Respect source terms, copyright, privacy, and licenses. Do not paste or port code from a
repository whose license is incompatible with this project's Apache-2.0 core. When a
restrictive project inspires behavior, write a clean functional specification and
implement from that specification rather than translating its source.

Do not add a fixture, dataset, screenshot, or donor artifact without adding a row to
the fixture/data licensing inventory
([`docs/licensing/README.md`](docs/licensing/README.md)) recording provenance,
license evidence, attribution, modifications, personal-data class, and redistribution
status. If the rights evidence is unknown, leave the row `pending-review`/`blocked`
with a concrete owner and blocker — never guess a license and never use the Apache-2.0
code license as a data permission.

## Naming during the pre-1.0 compatibility window

The repository still carries provisional package identifiers (`poc/`,
`dichiarazioni_pubbliche`). Stable database/config baselines use `db/schema.v1.sql`,
`db/job_queue.v1.sql`, and `config/*.v1.json`; the DP-106 `config/*.v0.json` fallback
window has closed in the source tree. Do not rename the remaining package identifiers in
a pull request; DP-601 owns that packaging transition. Use the current names in
documentation and new code until that rename is accepted.

## Commit style

Use concise imperative/conventional-style subjects where practical, for example:

`feat: add role interval provenance`

`fix: fail closed on stale speaker review`

`docs: establish public API contract`

## Community conduct

Participation is governed by `CODE_OF_CONDUCT.md`. Security issues belong in the private
path described by `SECURITY.md`, not a public issue.
