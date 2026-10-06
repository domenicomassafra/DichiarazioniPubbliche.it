# DP-222 — Public attribution person-identity and same-name gate

Status: DONE
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

- [x] **AC-222.1:** Same-name/different-person fixtures remain separate and cannot share
  public occurrence provenance.
- [x] **AC-222.2:** A direct `speaker_person_id`/person-link mutation without the matching
  approved provenance fails public validation.
- [x] **AC-222.3:** Identity and role-at-time are validated independently; stale office
  labels are omitted/held without changing the stable Person identity.
- [x] **AC-222.4:** Account ownership can establish authorship only within its approved
  method scope and cannot identify embedded/quoted third parties.
- [x] **AC-222.5:** Ambiguous alias or contradicting organization/date evidence yields a
  review hold, never highest-score auto-selection.
- [x] **AC-222.6:** Superseded entity identifiers/aliases invalidate affected unresolved
  publication links until re-reviewed.
- [x] **AC-222.7:** Public projection emits stable approved identity/role fields only and
  no private resolution scores/features.
- [x] **AC-222.8:** Full suite, tamper tests, schema replay and MiniPC canary pass.

## Validation / proof

Use deterministic fixtures for two people with identical names, one person changing
office, verified account with embedded third-party content, alias collision and a tampered
claim-person link. Run standard tests/benchmark and MiniPC read-back.

## Documentation, data, and migration impact

Prefer validation/index additions over a parallel identity model. Update canonical domain
docs after implementation; public schema changes remain under DP-105.

## Completion receipt

The local `public-attribution-v1` gate now composes the existing DP-218
SpeakerIdentityCandidate, DP-114 EntityResolutionCandidate/EntityIdentifier records and
DP-101 role intervals without introducing a second Person registry. It rejects display-name
authority, same-name ambiguity, contradicting identity features, tampered Person linkage,
superseded identifier dependencies, weak speaker methods and occurrence spans not covered by
the approved speaker proof. Role-at-statement-time is evaluated separately: an unproven or
stale office label is omitted while the already-approved stable Person identity remains
usable. PLATFORM_CREDIT can authorize only explicit source authorship scope and cannot be
reused for embedded/quoted third-party speaker identity. Focused tests cover these boundaries.

The final public read boundary now consumes the existing reviewed DP-218 speaker proof,
DP-114 resolution/identifier state and DP-101 role intervals as **internal-only**
`public-attribution-v1` inputs. For timed occurrences, `evaluate_public_attribution` must
approve the exact stable Person binding before a dossier can project. The public dossier
then carries only the stable Person ID/name, bounded reviewed speaker provenance and, when
independently valid at `statement_date`, one reviewed public role interval. A stale role is
omitted without changing the Person identity. Direct claim/segment Person-link mutation,
ambiguous/missing reviewed resolution, contradicting features or mismatched provenance
fails closed. This is the separately approved DP-222 bridge from DP-114 private review
state into the public projection; the historical DP-114 completion receipt remains
unchanged.

Private resolution material is never serialized. Projection tests inject private speaker
labels, aliases, identifier values/source refs, `retrieval_score`, supporting features and
contradicting features, then prove absence from public JSON, HTML and JSON-LD. The public
schema also rejects those private identity-resolution keys if a hand-built dossier tries to
introduce them. API read-back over the gated bundle (index, finding detail and people) is
private-free, the static search index is derived only from the sanitized Person/role fields,
and its contract explicitly rejects the same private field markers. Existing public-v2
schema/API/RDF compatibility remains intact.

Post-change proof on the shared checkout:
- `tests.test_public_attribution`: **9/9 PASS**;
- `tests.test_public_projection`: **43/43 PASS**;
- `tests.test_public_schema`: **29/29 PASS**;
- `tests.test_public_api`: **68/68 PASS**;
- `tests.test_linked_data`: **10/10 PASS**;
- disposable PostgreSQL public-projection tamper suite: **7/7 PASS**. The DP-222 case first
  projects reviewed Person A + statement-time role, confirms private resolution score data
  is present only in the internal SQL row, then mutates the persisted claim/segment link to
  Person B. Even with an approved/reviewed B speaker candidate, absence of matching reviewed
  identity-resolution evidence leaves the internal row queryable but makes public projection
  omit the dossier;
- pure API read-back: **3/3 routes PASS** with no private identity material;
- web search-index check PASS (**7 records, 3205 bytes**), Astro check PASS
  (**77 files, 0 errors/warnings/hints**) and demo-only static build PASS (**36 pages**);
- full suite: **1614/1614 PASS**;
- deterministic benchmark: **5/5 PASS**;
- `python3 -m compileall -q poc tests` and `git diff --check`: PASS.

Isolated MiniPC proof on `udodo` (Python 3.14.4, PostgreSQL 18 tooling), entirely under
`/tmp/dp222-attribution-worker13-20261006` with no production DB/provider/deploy/config
mutation:
- focused attribution/projection/schema/knowledge canary: **90/90 PASS**;
- disposable PostgreSQL tamper/read-back suite: **7/7 PASS**;
- fresh disposable PostgreSQL schema application plus exact replay of `db/schema.v1.sql`:
  **2/2 PASS**;
- deterministic benchmark: **5/5 PASS**;
- the MiniPC bundle and temporary PostgreSQL data directories were removed after the run.
