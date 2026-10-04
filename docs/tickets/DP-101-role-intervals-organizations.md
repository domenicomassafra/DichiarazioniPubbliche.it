# DP-101 — Role intervals and organization provenance

Status: DONE
Milestone: M1  
Depends on: M0

## Problem

`person.public_role` is a timeless convenience field and cannot faithfully represent
public roles that change over time.

## Outcome

Model organizations/offices and dated role intervals with source provenance while
preserving existing person identity and public-figure constraints.

## Acceptance criteria

- additive schema/migration for organization + role interval;
- start/end/open interval semantics are explicit;
- provenance source/reference is required for public role claims;
- no role interval creates a political score/classification;
- public projection exposes only approved/public-safe role facts;
- compatibility path for existing `public_role` data is documented;
- tests cover overlap, unknown end, correction/supersession, and time-specific lookup;
- migration and runtime acceptance pass on MiniPC.

## Non-goals

Biometric identity, CV/resume reconstruction, private employment history.

## Completion receipt

- Additive organization and half-open person-role-interval migration applied with
  `ON_ERROR_STOP` and replayed successfully on the MiniPC runtime authority.
- Explicit review-ledger approval, time-specific lookup, supersession, and bounded public
  projection are implemented and covered by focused tests.
- MiniPC PostgreSQL canary registered, approved, resolved, and removed a temporary role
  interval without residual rows.
- Full local regression: 234 tests passed; deterministic benchmark: 5/5 passed;
  `python3 -m compileall -q poc tests` and `git diff --check` passed.
- `person.public_role` remains a compatibility field; it is not used as an
  independently approved public-role fact.
