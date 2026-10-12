# AGENTS.md

**Inherited global delivery authority:** load the owner-global DStack `contracts/shared-root/AGENTS.md` before these local instructions. This is a **public-facing editorial product**: a local commit is never delivered work, but neither is a direct push to `main` approval to expose statements to the public. The single integrator promptly pushes an exact reviewed change to a short-lived **remote PR branch**, then merges to `origin/main` only after CI and the acceptance required for that change. Legal/editorial approval, MiniPC install, public projection and public reader checks are independent downstream gates. Stage exact owned paths only; never erase unrelated dirty work or call an open PR `DONE`.

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
- `origin/main` is the canonical integration branch. Work on **one short-lived change branch per coherent fix/feature**, push it promptly and open/update a traceable PR. A Draft PR preserves remote work while source CI, reviewer feedback, human editorial approval or MiniPC preview is pending. Do not create long-lived branches or an unbounded worktree per subagent; one integrator remains responsible for the PR and its cleanup after merge.
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
11. commit only owned paths, push and verify the change branch remote SHA, and open/update its PR; `PUSHED_FOR_REVIEW` is not a done ticket;
12. merge only once the relevant CI and pre-merge acceptance pass, then verify the resulting `origin/main` SHA and separately track MiniPC/reader deployment.

**Manual bug before merge:** keep the same PR open or Draft, attach the reproducible fault and failing case, fix in that branch, rerun targeted and full relevant CI, and repeat only the affected preview/manual check. Do not discard that branch or create unrelated replacement work.

**Bug after deployment:** if the public reader or rights/integrity path is affected, first fail closed, withdraw the affected public projection or restore the last approved version through the existing rollback policy; then ship a small hotfix PR with regression and real reader readback. Never overwrite published history or turn a merely syntactic pass into source, editorial or legal acceptance.

`python3 ~/.dstack/scripts/verify_main_delivery.py --repo . --review-check` proves an existing branch is saved remotely, **not** that PR/CI/manual checks passed. After merge, `--check` proves the clean `origin/main` source state. The current GitHub CI is source-only and has **no deployment authority**. Informational-site preview (`LAUNCH.md`) is distinct from the full curated archive release; neither should be blocked by unrelated release scope, and neither gains publication permission from a Git merge alone.

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
