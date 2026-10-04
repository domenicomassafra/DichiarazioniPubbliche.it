# Documentation map

Dichiarazioni Pubbliche distinguishes **canonical contracts** from **design/history evidence**.

## Canonical contracts

Read these first:

- `../PRODUCT.md` — product constitution, scope, non-goals, invariants;
- `../CONTEXT.md` — domain vocabulary;
- `../ARCHITECTURE.md` — system boundaries and runtime topology;
- `../PLAN.md` — milestone/ticket graph to stable v1;
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

Repo-local tickets are executable specifications. They are not a second backlog hidden
from maintainers: `PLAN.md` is the ordered index, and each ticket has a clear status.
When a public issue tracker is configured, issues should link to the same ticket ID.
