# ADR 0005 — Apache-2.0 license for repository code

Status: Accepted  
Date: 2026-09-22

## Context

The project is intended to be genuinely open source while preserving broad adoption and
future commercial use. Contributors also benefit from an explicit patent grant.

## Decision

Repository code is licensed under Apache-2.0 unless a file/directory states a different
compatible license. Third-party content, datasets, evidence, media, trademarks, and
service terms are not relicensed by the code license.

## Consequences

- Commercial reuse and forks are permitted under Apache-2.0 terms.
- Incompatible copyleft/restrictive code cannot be copied into the core casually.
- Data/content licensing must be documented independently before public releases.

## Alternatives considered

- MIT: simpler, but lacks Apache-2.0's explicit patent license.
- AGPL/GPL: rejected for the current core because they reduce the commercial flexibility
  explicitly required by the product owner.
- Source-available/non-commercial: rejected because it would not meet the project's
  open-source goal.
