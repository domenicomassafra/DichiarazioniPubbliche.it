# DP-414 — studio ia v3 corpus inbox collections verify

Status: DONE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-112, DP-113; supersedes only the private two-template constraint of DP-413

## Problem

The previous Verify Studio 2-template model assumes a source is already chosen. It has no coherent place for corpus search, new discovery triage, collection-level research or candidate promotion.

## Outcome

Ratify an implementable Studio IA with four operator jobs: Corpus Search, Discovery Inbox, Research Collection and Verify, all backed by persisted domain objects and one shared design language.

## Scope

- Define navigation, route/state contracts and screen responsibilities.
- Map every visible panel/counter/status to a persisted object/query; no fake AI activity.
- Specify desktop-first layout, keyboard model, loading/blocked/empty/error states.
- Preserve Verify three-pane source/claim/evidence workflow as one mode.
- Define mobile degradation without requiring full mobile operator parity.
- Update DESIGN/UX docs only where the new private IA supersedes old guidance.

## Non-goals

- No visual-polish bakeoff.
- No public IA rewrite.
- No enterprise sidebar/KPI wall by default.

## Dependencies and sequencing

DP-112, DP-113; supersedes only the private two-template constraint of DP-413

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [x] **AC-414.1:** An operator can describe where to search existing corpus, triage new hits, investigate a collection and verify a promoted claim without route ambiguity.
- [x] **AC-414.2:** No screen conflates analysis with publication.
- [x] **AC-414.3:** Every status displayed has a domain/query source.
- [x] **AC-414.4:** One dominant task remains visually clear per screen.

## Validation / proof

- `python3 -m compileall -q poc tests` when Python/runtime code changes;
- `PYTHONPATH=poc python3 -m unittest discover -s tests -v` when code/schema contracts change;
- `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark` when claim/evidence/publication semantics change;
- `cd web && npm run check && npm run build` when web/Studio code changes;
- `git diff --check` always;
- runtime-affecting completion additionally requires MiniPC read-back from `/home/udodo/src/DichiarazioniPubbliche.it` and PostgreSQL `dichiarazioni_pubbliche`.

Ticket-specific proof must include the exact acceptance fixtures/receipts named above,
not only a green unit-test summary.

## Documentation, data, and migration impact

Design/IA contract first; implementation follows DP-415..419.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

First local Studio IA v3 vertical slice implemented 2026-10-05. The private header now has
four unambiguous operator jobs and routes: `/studio/corpus/`, `/studio/inbox/`,
`/studio/collections/` and `/studio/verify/`. Each route shares one task-first workspace
frame whose single `h1` is the dominant task; Verify keeps exactly three panes for
source/transcript, claim queue, and evidence/review.

`studio-private-view-v1` is the typed private view-model contract. Every visible counter or
status requires `source_kind`, `source_ref`, `query_state` and `blocker_code`; blocked states
without a blocker code fail closed. Verify exposes only distinct `analysis` and `review`
action domains and no publication action. Fixture mutation actions are disabled because no
mutation backend is attached.

The local/demo dataset in `web/src/data/studio.ts` is explicitly `fixture_only`. Ordinary
public static builds do not materialize `/studio/**` at all: the gated
`src/pages/studio/[workspace]/index.astro` route returns no static paths unless
`DICHIARAZIONI_PUBBLICHE_STUDIO_FIXTURE_ONLY=1` is explicitly enabled. The opt-in Studio
fixture build emits all four workspaces and renders the source-binding metadata on every
visible status. The view-model still fails closed to `STUDIO_PRIVATE_SOURCE_REQUIRED` when
a fixture is resolved with `allow_fixture: false`; no persisted Studio backend is fabricated.

Local validation covers `astro check`, design-system checks, the 32-route public demo build
with zero `/studio/**` output/private fixture markers, the explicit 36-route Studio fixture
build, and `check-studio-v3.mjs` sabotage checks for missing source references/blocker codes,
legacy navigation ambiguity, fake AI/activity wording, publication controls, action-domain
separation and Verify three-pane. Public quality/route checks pass with Studio absent.
At the time of this first receipt, real persisted adapters for corpus/inbox/collection/
verification queries, mutation handlers, richer keyboard/loading/error acceptance, and the
ticket-specific MiniPC IA proof were still follow-up work. The MiniPC IA-contract proof is
superseded by the 2026-10-08 receipt below; persisted adapters and real operator workflows remain
owned by DP-415..DP-419 rather than DP-414.

### MiniPC IA-contract closure — 2026-10-08

The remaining DP-414-specific runtime acceptance was exercised without enabling private Studio in
production. On the authoritative MiniPC mirror at current main, `check-studio-v3.mjs` passes
against the live public build and confirms `/studio/**` is absent by default. A separate isolated
`/tmp` build from commit `9fa9074b02c9bf01b4570f19086e3302a04784b2`, using the real approved
public projection plus the explicit `DICHIARAZIONI_PUBBLICHE_STUDIO_FIXTURE_ONLY=1` opt-in,
materializes exactly four private fixture workspaces:

- `/studio/corpus/`
- `/studio/inbox/`
- `/studio/collections/`
- `/studio/verify/`

The same checker passes on that fixture build and proves source-bound status metadata, the single
dominant task/frame, Verify's three-pane analysis/review separation, disabled fixture mutations,
and absence of publication controls. The isolated build is removed afterward; the production
public dist remains Studio-free.

This closes DP-414's four IA/data-contract acceptance criteria. Persisted query adapters, mutation
handlers, richer keyboard/loading/error workflows, and private provenance inspection are not
silently absorbed here: they remain explicitly owned by DP-415..DP-419, whose acceptance criteria
are still open. DP-414 can therefore be `DONE` without claiming those downstream workspaces are
implemented or production-enabled.
