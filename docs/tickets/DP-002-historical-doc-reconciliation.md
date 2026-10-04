# DP-002 — Reconcile historical docs against canonical contracts

Status: DONE  
Milestone: M0  
Depends on: DP-001

## Problem

Earlier numbered docs contain valuable evidence but also superseded vocabulary and open
questions that are now resolved.

## Outcome

Create a reconciliation matrix: current, superseded, still-open, or historical-only for
every numbered document/major claim. Add pointers rather than rewriting historical
receipts.

## Acceptance criteria

- every `docs/00-*` through current numbered doc has a classification;
- resolved license/governance/domain questions point to canonical docs/ADRs;
- no historical file is silently presented as current authority;
- genuinely open questions become PLAN tickets or are explicitly deferred.

## Validation

Documentation consistency review and `git diff --check`.

## Completion receipt

Completed in `docs/historical-document-reconciliation-2026-09-22.md`; every numbered
document is classified and all material open questions are mapped to `PLAN.md` tickets.
