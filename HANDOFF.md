# Dichiarazioni Pubbliche — Current Operational Handoff

Last updated: 2026-10-03

This file is intentionally short. It is an operational continuation note, not the
project constitution, architecture, or backlog.

## Read first

1. `PRODUCT.md`
2. `CONTEXT.md`
3. `ARCHITECTURE.md`
4. `PLAN.md`
5. `AGENTS.md`
6. relevant ADR/ticket

## Authorities

- Git/source authority: `/Users/domenico/Code/DichiarazioniPubbliche.it`
- Branch policy: keep `main` clean; avoid unnecessary branches/worktrees.
- Runtime authority: MiniPC.
- MiniPC deployment mirror: `/home/udodo/src/DichiarazioniPubbliche.it` (not a Git checkout).
- Production PostgreSQL DB: `dichiarazioni_pubbliche` on MiniPC.
- Production contract registry: `dichiarazioni-pubbliche-public-v2` ACTIVE.
- Current canonical backup set: `~/.local/share/dichiarazioni-pubbliche-backups/20261004T014945Z/`.

## Current code/runtime baseline

The 2026-10-04 consolidation closes the previously uncommitted 2026-10-03
rename/cutover and owner WIP on `main`. The canonical Git remote is
`https://github.com/domenicomassafra/DichiarazioniPubbliche.it.git`. Use
`git log -1 --oneline` for the exact current commit rather than copying a stale hash into
this handoff.

The preserved pre-rebrand WIP in `queue_runtime.py`, `tests/test_queue_runtime.py`,
`poc/dichiarazioni_pubbliche/timestamp_acceptance.py` and
`tests/test_timestamp_acceptance.py` is now validated as part of the canonical tree.

Latest validation after the consolidation:

- Mac full Python suite: **977/977 PASS**;
- MiniPC pre-cutover full Python suite: **977/977 PASS**;
- deterministic benchmark: **5/5 PASS**;
- compileall: PASS;
- timestamp acceptance fixture: 84 segments / 36 claims / 0 provider calls;
- Astro check: 47 files, 0 diagnostics;
- design-system check: PASS;
- explicit demo static build: **16 routes PASS**;
- normal static build without a public projection remains fail-closed as designed;
- git diff --check: PASS;
- MiniPC worker/source-poll/health post-cutover oneshots: exit 0;
- five renamed MiniPC timer/web surfaces: active;
- loopback web read-back: HTTP 200;
- production projection: dichiarazioni-pubbliche-public-v2, 2 dossiers, 0 omitted.
- MiniPC source/config/runtime scan: zero obsolete project-identity matches;
- rename-era backup/rollback/timer-stamp residues removed after a fresh canonical backup.

The exact rebrand/runtime receipt is
docs/reviews/rebrand-cutover-2026-10-03.md.

The public IA decision is now frozen in `docs/35-public-product-architecture-v3.md`.
The maintained visual reference set is the nine page families under
`prototypes/final-hybrid/`. The real Astro route migration is intentionally the next
bounded implementation ticket, `DP-422`; it is not hidden WIP.

## Known external blockers

### Claim extraction

The official OmniRoute tiered path does not currently complete the required governed
claim-extraction flow.

Rules:

- do not change model/provider to hide the blocker;
- do not use a local-fork OmniRoute runtime;
- do not recreate claim-extraction child jobs while downstream capability is unavailable;
- resume with `DP-201` only when an official artifact makes a meaningful canary possible;
- then `DP-202` one parent canary + Giuliani benchmark;
- only then `DP-203` controlled fan-out.

### Remote ASR

Live remote ASR remains blocked until the required provider credential is configured
outside Git. Resume through `DP-204` with a bounded canary and cost receipt.

## Current program state (updated 2026-10-03, Mac + MiniPC)

DP-211 and DP-212 are DONE (runtime-certified 2026-09-30). DP-213 is DONE
(Mac-verified + MiniPC runtime proof 2026-10-01: migration replay, isolated
tracer, zero side effects, 968/968 suite, backups `20261001T154412Z` /
`20261001T160005Z`). DP-215 implementation is Mac-verified (8/9 ACs) with
MiniPC proof recorded in-ticket; it stays IN_PROGRESS until AC-215.9 via
FUTURE DP-214. Full Mac suite: 968/968 PASS, benchmark 5/5 PASS. See the two
tickets for the exact receipts.

Read `docs/34-research-corpus-knowledge-architecture-v1.md`, ADR 0007 and ADR 0008 before
implementing corpus work. The key path is now:

`Discovery -> Content -> ContentCapture -> Passage/transcript -> StatementCandidate -> ClaimCandidate -> explicit promotion -> AtomicClaim -> Evidence -> Verification -> Finding -> Public Projection`.

Do not start mass ingestion or broad visual polishing outside the frozen public architecture
before the corpus tracer bullet is usable. Public Product Architecture v3 in
`docs/35-public-product-architecture-v3.md` is now the canonical public IA; Public UX v2
is superseded as route/page guidance. The implementation sequence is DP-211 -> DP-212 -> DP-213 -> DP-214,
then DP-414..420; DP-421 decides whether a distinct public case/collection surface is
justified after the Garlasco pilot.

External provider blockers DP-201..204 remain unchanged and must not be hidden by the new
architecture.

The consolidated code/feature/UI snapshot is recorded in
docs/reviews/consolidation-baseline-2026-10-03.md. The owner-approved product and
technical identity is now **Dichiarazioni Pubbliche** /
DichiarazioniPubbliche.it / dichiarazioni_pubbliche. Domain purchase, handles and
qualified trademark/legal clearance remain separate launch gates.

## Safety invariants that must survive every change

- no auto-publication;
- evidence retrieval != approval != verification != publication;
- no person truth/reliability/political score;
- no political recommendation;
- no biometric speaker identity;
- public claim attribution requires approved speaker provenance;
- correction/right-of-reply are append-only and private by default;
- public projection is bounded and fail-closed;
- no raw/canonical transcript body or evidence body in public projection by default;
- no future evidence silently judging earlier claims;
- no generic model-invented evidence URLs/queries in the evidence core;
- no unnecessary major infrastructure;
- runtime completion requires MiniPC proof when the ticket says so.

## Standard validation

```bash
cd /Users/domenico/Code/DichiarazioniPubbliche.it
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
git diff --check
git status --short --branch
```

## Handoff discipline

Future handoffs should only record:

- current ticket/status;
- exact commit/state;
- runtime receipts relevant to unfinished work;
- blockers and the next deterministic action.

Durable product decisions belong in canonical docs or ADRs, not here.
