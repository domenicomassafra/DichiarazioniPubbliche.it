# AGENTS.md

Instructions for coding agents and human contributors working in this repository.

## Read first

Before changing code, read in this order:

1. `PRODUCT.md` — product constitution and non-negotiable invariants.
2. `CONTEXT.md` — canonical domain language.
3. `ARCHITECTURE.md` — target system shape and runtime authority.
4. `PLAN.md` — current milestone/ticket graph.
5. relevant ADRs under `docs/adr/`.
6. the ticket/spec being implemented.

Historical `docs/00-*` through later wave documents are evidence and design history, not
the primary authority when they conflict with the canonical files above.

## Repository and runtime authority

- Authoritative Git checkout: `/Users/domenico/Code/DichiarazioniPubbliche.it`.
- Work on `main` unless the owner explicitly requests another workflow.
- Keep one worktree and zero unnecessary branches/WIP.
- Runtime/backend authority: MiniPC.
- MiniPC deploy mirror: `/home/udodo/src/DichiarazioniPubbliche.it` and is not a Git checkout.
- Do not claim runtime completion from Mac-only evidence.

## Safety/product invariants

Never weaken these as a convenience fix:

- no auto-publication;
- evidence retrieval != evidence approval != verification != publication;
- no person truth/reliability score or political ranking;
- no voting/political recommendation;
- no inference of intent from contradiction alone;
- no face/voice biometric identity matching;
- public claim attribution requires approved speaker provenance for every segment;
- right of reply/correction are append-only and private by default;
- public projection must fail closed and must not expose raw transcript/evidence bodies;
- do not use future evidence to judge an earlier claim unless evaluating a later outcome;
- do not invent evidence URLs or generic model-generated evidence queries;
- do not add major infrastructure without measured need;
- do not materialize downstream child jobs when the downstream capability is unavailable.

## Engineering workflow

For non-trivial work:

1. identify the governing ticket/spec;
2. inspect current behavior before editing;
3. write or update tests at the agreed seam;
4. implement the smallest coherent change;
5. run focused tests frequently;
6. run the full suite once before completion;
7. run deterministic benchmark when domain/publication behavior changes;
8. run `git diff --check`;
9. update docs/ADR/ticket state when the behavior or architecture changed;
10. prove runtime-affecting changes on MiniPC;
11. commit a coherent change to the current branch.

Preferred commands:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
git diff --check
```

## Database changes

- Treat `db/schema.v1.sql` plus ordered migrations as a compatibility contract.
- Prefer additive migrations.
- Migrations must be idempotent where the runtime procedure expects replay.
- Production migrations require `ON_ERROR_STOP` and MiniPC proof.
- Never mutate production data to make a test pass.
- Use isolated canary DB/schema for destructive or publication-gate acceptance.

## Provider/runtime blockers

Provider failure is an explicit blocked state. Do not switch model/provider, lower the
quality bar, or fabricate a receipt to turn a blocked test green. A provider-path fix
must first pass a meaningful canary and any cost gate required by the current ticket.

## Documentation rules

- Put durable product rules in `PRODUCT.md`.
- Put domain vocabulary in `CONTEXT.md`.
- Put system boundaries in `ARCHITECTURE.md`.
- Put sequencing/dependencies in `PLAN.md`.
- Put irreversible/significant technical decisions in `docs/adr/`.
- Put implementation requirements in `docs/tickets/`.
- Put historical investigation and benchmark receipts under `docs/` without promoting
  them to authority.
- Do not turn `HANDOFF.md` into a second architecture or backlog.

## Definition of done

"Done" means code/spec behavior, tests, documentation, and required runtime proof agree.
It never means "the code exists on the Mac".
