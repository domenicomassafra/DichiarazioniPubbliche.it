# Dichiarazioni Pubbliche — consolidation baseline (2026-10-03)

Status: point-in-time engineering/product inventory; canonical contracts remain
`PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`, `PLAN.md`, ADRs and ticket files.

## Why this snapshot exists

The repository accumulated a large amount of backend, research-corpus, public-web and
design work in a short period. This snapshot records what is actually active now, what is
implemented but not yet wired into a user-facing workflow, what is intentionally blocked
or future work, and whether any Git WIP remains outside the canonical history.

## Git consolidation result

Authoritative checkout: `/Users/domenico/Code/DichiarazioniPubbliche.it`.

- `HEAD`: `1692d01df748c335bc7123f2f075a2c01bba02ae` on `main`;
- active local branches: `main` only;
- worktrees: one (the authoritative checkout);
- stash: empty;
- configured remotes / remote-tracking branches: none;
- tags: none;
- tracked or untracked source changes at audit start: none.

`git fsck --no-reflogs --unreachable` reports six historical commit objects. Reflog,
patch comparison and tree comparison show that each is an immediately superseded
amend/reset revision already represented by reachable history:

- `007d2c0` -> `c2cd1f7` (documentation cleanup/newline revision);
- `5a210e4` -> `80cf2f3` (benchmark commit amended to remove tracked cache artifacts and
  add the repository ignore cleanup);
- `599221e` -> `22ca8d4` (content-audit receipt replaced by the final validated provenance);
- `9eee311` -> `a215dd6` (canonical transcript/PostgreSQL queue commit amended for cleanup);
- `7fc221a` -> `778134b` (patch-equivalent provenance/UX hardening revision);
- `13bb5a9` -> `26c1d2e` (runtime unification recommit; later history separately handles
  the v0/v1 compatibility window).

There is therefore no lost branch/WIP to merge, cherry-pick or archive. The unreachable
objects are recovery history and should age out through normal reflog/GC rather than being
force-pruned merely to make `fsck` empty.

Because no remote is configured, this snapshot can prove local consolidation only; it
cannot assert parity with an external GitHub/origin repository.

### Secret-scanner review

A redacted `gitleaks --no-git` scan reports 15 `generic-api-key` candidates, all attached
to 64-character hexadecimal `receipt_key` / `lifeos_receipt_key` fields in the historical
Raffagiulians content-audit receipt set (14 tracked occurrences plus one ignored raw
receipt). The repository scan did not identify provider credential field names in those
findings. They are therefore recorded as receipt-identifier false-positive candidates,
not silently allowlisted and not claimed to be credentials. Before any public release,
DP-603/DP-702 should either prove their disclosure semantics or replace/redact them in the
release dataset; no scanner suppression is added by this consolidation pass.

## Validation baseline

Verified on the authoritative Mac checkout during this consolidation pass:

- Python test suite after the baseline export regression test was added: **969/969 PASS**,
  plus **276 subtests PASS**;
- deterministic benchmark: **5/5 PASS**;
- `python3 tools/check_contributor_acceptance.py`: PASS;
- `python3 -m compileall -q poc tests`: PASS;
- `git diff --check`: PASS before consolidation edits;
- Ruff semantic/export checks are clean; safe cleanup removed unused imports plus one
  duplicate dictionary key. The remaining 42 Ruff findings are formatting/style-only
  (`E402`, `E701`, `E702`, `E731`) and are not part of the current declared CI contract;
  they are intentionally not rewritten with unsafe fixes in this consolidation pass;
- Astro `npm run check`: **0 errors / 0 warnings / 0 hints**;
- `npm run check:design`: PASS;
- explicit fictional demo build (`DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build`):
  PASS, **10 static pages**.

The default web build failing when no public projection is supplied is intentional
fail-closed behavior, not a product defect. CI must opt into the fictional fixture
explicitly when it wants a credential/data-free static build.

## What is genuinely implemented

### Core ingestion, provenance and verification

The codebase contains real tested implementations for source polling/scheduling,
PostgreSQL job queue behavior, caption/transcript acquisition, canonical transcript
handling, claim windows/extraction contracts, official-evidence fetching and caching,
structured evidence observations, explicit review events, deterministic/time-aware
verification, finding persistence, non-biometric speaker provenance, relation/reanalysis
logic, fail-closed public projection, and append-only correction/right-of-reply records.

### Research Corpus / knowledge layer

The post-September research-corpus work is not merely documentation. The repository has
real schema/runtime/tests for Research Corpus persistence, immutable captures/passages,
rights/retention/replay, PostgreSQL corpus search, entity/topic/event resolution,
proposition/source-derivation clustering, candidate promotion, bounded research discovery,
capture parsing, passage candidate extraction, candidate matching, Coverage Needs and
contextual Source Intelligence.

Several of those capabilities are currently invoked through bounded operator tools rather
than one continuous Studio workflow. That distinction matters: persisted/backend-complete
does not mean a finished operator product.

### Public read surface

The public projection and read-only HTTP API are real. The API implementation exposes
health/schema/index plus bounded finding/record/topic/person reads and OpenAPI material;
the public request path is read-only and does not call an LLM. Its implementation ticket
is complete, while the served API/OpenAPI contract still truthfully identifies itself as
pre-release/draft until release ratification.

The Astro frontend currently builds these public/demo routes:

- `/`;
- `/esplora/`;
- `/fact-check/<finding>/`;
- `/record/<person>/`;
- `/contenuti/intervista-servizi-pubblici/` (demo ContentAudit fixture);
- `/metodo/`.

## What is partial, operator-only or not wired yet

- Research discovery/capture/candidate extraction/matching have real bounded operator
  tools, but not one completed continuous worker/Studio interaction loop.
- Corpus search exists at the PostgreSQL/runtime layer but is not yet exposed as a real
  Studio search workspace.
- Review/admin is a local/operator CLI surface; there is no production admin HTTP auth UI.
- Public right-of-reply/correction intake is intentionally not exposed; the append-only
  lifecycle exists behind operator controls while abuse/auth policy remains future work.
- The social-creator source adapter is approved-metadata/fixture-oriented and refuses live
  fetching; live source families currently include YouTube feed and podcast RSS paths.
- Studio React/data files exist as prototype material, but no `/studio/*` page is routed in
  the live Astro page tree.

## Public frontend / UX state

The visible product brand is already **Dichiarazioni Pubbliche**. `DichiarazioniPubbliche.it` and
`dichiarazioni_pubbliche` are technical compatibility identifiers, not the public-facing name.
A repository/package rename should therefore be treated as a migration/release task, not
as a visual rebrand shortcut.

The live frontend is structurally healthy but not yet equal to the accepted UX v2/v3
design material. Confirmed gaps include:

- Home does not yet surface the signature ContentAudit/media example described by the
  current UX architecture;
- Explore still lacks the accepted content-type modes; during this consolidation its
  existing query/esito/order state was made shareable in the URL;
- record-local filtering/search is not implemented yet; misleading no-op filter buttons
  were removed and the search label now truthfully describes the global public record;
- the public header now preserves navigation on mobile and distinguishes the Fact-check
  Explore mode from the general Explore route;
- duplicate arrow links in result rows were reduced to one keyboard destination per
  fact-check, and ContentAudit selection now exposes its selected state to assistive tech;
- the newer design-system primitives exist, but current public pages still rely heavily on
  the transitional `legacy.css` layer;
- private Studio IA/routes are not implemented even though prototype components remain in
  the tree.

This means the next UI/UX work should be consolidation of the accepted architecture, not
another disconnected visual concept pass.

## Backlog shape at this snapshot

Ticket-file statuses at audit time:

- **35 DONE**;
- **18 IN PROGRESS**;
- **6 READY**;
- **4 BLOCKED**;
- **24 FUTURE**.

The four explicit external blockers are DP-201..DP-204 (official OmniRoute governed
claim-extraction path and live remote-ASR credential/canary chain). They must remain
blocked rather than be hidden with a fallback.

The immediate research-corpus closure dependency is DP-214: the Garlasco tracer bullet is
also the remaining acceptance path for DP-215.9. The broader Studio IA/workspace sequence
DP-414..420 remains downstream of that tracer. Public person/topic/ContentAudit/comparison
UI tickets DP-405..408 are READY, not DONE.

## Branding decision for the next phase

No additional public rename is required to start UI/UX consolidation: **Dichiarazioni Pubbliche is
already the canonical visible brand**. Until DP-701 (brand/domain/handle clearance),
DP-106 (technical v0/v1 migration) and DP-601 (package/development contract) deliberately
resolve their own scopes, keep the repository/package compatibility names stable.

The useful next design phase is therefore: make the implemented public surfaces behave
like the accepted Dichiarazioni Pubbliche UX, retire transitional styling incrementally, then build the
real Studio IA after the tracer contract is proven.
