# Governance

Dichiarazioni Pubbliche is currently maintainer-led. The project favors transparent written contracts
over informal decisions hidden in chat history.

## Decision hierarchy

From highest to lowest authority:

1. applicable law and third-party license obligations;
2. accepted ADRs in `docs/adr/`;
3. `PRODUCT.md` product constitution;
4. `CONTEXT.md` domain vocabulary;
5. `ARCHITECTURE.md` system contract;
6. `PLAN.md` sequencing and roadmap;
7. accepted ticket/spec;
8. implementation and tests;
9. historical/research documents and handoffs.

An implementation that contradicts a higher layer is a defect, not a new de facto
policy.

## Maintainer responsibilities

Maintainers are responsible for:

- protecting provenance/publication invariants;
- reviewing security and legal-risk changes carefully;
- keeping roadmap and ticket status honest;
- preventing hidden provider/cost dependencies in contributor CI;
- recording durable architectural decisions as ADRs;
- publishing corrections to project documentation when a previous claim was wrong.

## Changing product invariants

Any change to political-neutrality rules, publication gates, biometric scope, public
data exposure, correction history, or evidence/review semantics requires:

1. a written proposal;
2. an ADR describing alternatives and migration impact;
3. explicit maintainer approval;
4. tests covering the new safety boundary;
5. runtime acceptance when applicable.

## Releases

Until v1, releases may be development snapshots. A stable release requires the relevant
milestone in `PLAN.md` to be complete and the release checklist to include deterministic
CI, migration compatibility, public schema compatibility, security review, and MiniPC
runtime proof.

## Licensing

Code in this repository is licensed under Apache-2.0 unless a file/directory states a
different compatible license. Data/content rights are separate; a code license does not
grant rights to third-party media, transcripts, evidence, trademarks, or datasets.
