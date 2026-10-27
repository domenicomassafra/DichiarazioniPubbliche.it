# Documentation map

Dichiarazioni Pubbliche distinguishes **canonical contracts** from **design/history evidence**.

## Canonical contracts

Read these first:

- `../PRODUCT.md` — product constitution, scope, non-goals, invariants;
- `../CONTEXT.md` — domain vocabulary;
- `../ARCHITECTURE.md` — system boundaries and runtime topology;
- `../PLAN.md` — frozen historical milestone/ticket graph to stable v1;
- `../AGENTS.md` — contributor/agent execution rules;
- `../GOVERNANCE.md` — decision hierarchy;
- `adr/` — accepted architecture decisions;
- `tickets/` — implementation specs.

## Historical and research documents

The numbered files `00-*` through `29-*` are valuable primary-source history: research,
benchmarks, implementation-wave receipts, and earlier design hypotheses. They should be
preserved, cited, and mined for evidence, but they are not allowed to silently override
the canonical contracts above.

When a historical document disagrees with current architecture, record the resolution in
an ADR or update the canonical contract instead of editing history to make it look as if
the disagreement never existed.

## ADR policy

An ADR records a durable decision when alternatives existed and future contributors
would otherwise re-open the same question. Accepted ADRs are immutable except for small
clarifications; a new decision supersedes an older ADR with a new ADR.

## Ticket policy

Repo-local tickets are frozen historical specifications, including unique acceptance,
rights, legal and implementation context. Their old status fields are archival.
[GitHub Issues](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues)
is the sole authority for current status, priorities, ownership and completion.
The original tickets and plan remain available for source context, not dispatch.
