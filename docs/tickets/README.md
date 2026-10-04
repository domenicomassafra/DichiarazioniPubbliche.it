# Repo-local tickets

`PLAN.md` is the canonical ordered backlog. Files in this directory are implementation
specs for individual ticket IDs.

## Required ticket sections

Every ticket should contain:

- Status and milestone;
- Problem;
- Outcome;
- Scope;
- Non-goals;
- Dependencies;
- Acceptance criteria;
- Validation/proof;
- Documentation/data/migration impact;
- Completion receipt once done.

## Status discipline

Do not mark a ticket DONE because code was written. Required tests, docs, migration
checks, and MiniPC proof must all exist when the ticket says they are required.

When the project gains a public issue tracker, issue titles should begin with the same
ticket ID, for example `DP-101: Role intervals and organization provenance`.
