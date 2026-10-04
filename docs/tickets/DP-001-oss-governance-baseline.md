# DP-001 — Establish canonical OSS/governance surface

Status: DONE  
Milestone: M0

## Problem

Project truth is spread across a long handoff and chronological wave docs. A new
contributor cannot reliably distinguish durable product rules from historical decisions.

## Outcome

Create the canonical root contracts, OSS community files, documentation hierarchy,
license, ADR mechanism, issue/PR surfaces, and one master plan.

## Non-goals

- rewriting working runtime code;
- changing publication semantics merely to fit new documentation;
- public deployment.

## Acceptance criteria

- `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`, `PLAN.md`, `AGENTS.md` exist and agree;
- contribution/governance/security/support/conduct/license files exist;
- docs authority hierarchy is explicit;
- README is a concise front door instead of a chronological document dump;
- GitHub issue/PR templates and CI are contributor-facing;
- full existing tests/benchmark remain green;
- no extra branch/worktree/WIP remains.

## Validation

Local compile, full unit suite, deterministic benchmark, `git diff --check`, clean Git.

## Runtime proof

No MiniPC behavior change is intended. If only documentation/CI metadata changes, local
validation is sufficient; do not redeploy production for paperwork alone.

## Completion receipt

- canonical product/domain/architecture/plan/agent contracts added;
- Apache-2.0 license + OSS community/governance/security surface added;
- README and HANDOFF refactored into front-door and operational roles;
- CI expanded to Python 3.11/3.12; issue/PR templates added;
- historical docs reconciled; architecture deepening + autoplan reviews recorded;
- compileall PASS;
- unit/regression suite 185/185 PASS;
- deterministic benchmark 5/5 PASS;
- markdown relative-link audit: 0 missing;
- `git diff --check`: PASS;
- single worktree, single `main` branch.
