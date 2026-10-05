# DP-222 — Public attribution person-identity and same-name gate

Status: FUTURE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-101, DP-114, DP-216, DP-218

## Problem

DP-114 correctly keeps ambiguous entity matches reviewable, but public attribution still
needs an explicit cross-stage guarantee that the Person bound to the source occurrence is
the same stable identity projected on the public page. A copied display name, stale office,
alias collision or direct `speaker_person_id` mutation must never be enough.

## Outcome

Add a final public-attribution identity gate that ties approved occurrence provenance to a
stable Person identity, source-time role context and approved resolution evidence. Same-name
or conflicting identity cases remain private until resolved.

## Scope

- Reuse DP-114 entity identifiers/candidates and DP-101 role intervals; no second Person
  registry.
- Require a stable Person ID plus an approved attribution/resolution path for each public
  occurrence; display-name equality is never authority.
- Validate role/title at statement time separately from identity. A correct person with a
  stale or unsupported office title must not inherit a false role label.
- Preserve alias, organization, date, stable identifier and contradicting features used by
  the review decision.
- Direct DB/API tampering with Person linkage must make publication validation fail unless
  matching occurrence/identity review evidence exists.
- Handle same-name, surname-only, renamed organizations, changed offices and source aliases.

## Non-goals

- No biometric recognition.
- No identity inference from ideology, appearance, voice or social graph similarity.
- No assumption that verified social-account ownership proves every person appearing in
  content posted by that account.

## Acceptance criteria

- [ ] **AC-222.1:** Same-name/different-person fixtures remain separate and cannot share
  public occurrence provenance.
- [ ] **AC-222.2:** A direct `speaker_person_id`/person-link mutation without the matching
  approved provenance fails public validation.
- [ ] **AC-222.3:** Identity and role-at-time are validated independently; stale office
  labels are omitted/held without changing the stable Person identity.
- [ ] **AC-222.4:** Account ownership can establish authorship only within its approved
  method scope and cannot identify embedded/quoted third parties.
- [ ] **AC-222.5:** Ambiguous alias or contradicting organization/date evidence yields a
  review hold, never highest-score auto-selection.
- [ ] **AC-222.6:** Superseded entity identifiers/aliases invalidate affected unresolved
  publication links until re-reviewed.
- [ ] **AC-222.7:** Public projection emits stable approved identity/role fields only and
  no private resolution scores/features.
- [ ] **AC-222.8:** Full suite, tamper tests, schema replay and MiniPC canary pass.

## Validation / proof

Use deterministic fixtures for two people with identical names, one person changing
office, verified account with embedded third-party content, alias collision and a tampered
claim-person link. Run standard tests/benchmark and MiniPC read-back.

## Documentation, data, and migration impact

Prefer validation/index additions over a parallel identity model. Update canonical domain
docs after implementation; public schema changes remain under DP-105.

## Completion receipt

Pending prerequisites and implementation.
