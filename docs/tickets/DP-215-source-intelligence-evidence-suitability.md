# DP-215 — source intelligence and evidence suitability

Status: IN_PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-102, DP-113, DP-115, DP-118, DP-209, DP-210

## Problem

Dichiarazioni Pubbliche can discover, capture, preserve, search and fetch evidence from configured
sources, but source configuration is still split between acquisition-oriented source
metadata and evidence-fetch allowlists. Fields such as `priority`, `evidence_class` and a
global `authoritative` boolean are not sufficient to explain why a source is appropriate
for one factual question but not another.

The system needs an auditable methodology for source identity, source role, contextual
authority, independence/derivation, temporal applicability, rights/access state and
claim-type-specific evidence suitability. This must improve retrieval and review without
creating a political, publisher or person-level trust score.

## Outcome

Create one source-intelligence contract shared by Discovery, Research Corpus, Coverage
Needs, Evidence retrieval and review. The contract answers:

- what a source is and how it was observed;
- what evidentiary role it can play;
- for which jurisdiction/topic/record type it is authoritative or first-party;
- whether two sources are independent, derivative, syndicated or copies of one record;
- what time period/version a source can support;
- what rights/access/retention constraints apply;
- which evidence roles are required or merely useful for each claim type; and
- why an evidence set is sufficient, insufficient, conflicting or blocked.

No single global source-quality, truthfulness, trust or reliability score is introduced.

## Domain contract

### Source identity versus evidence role

Keep stable source identity separate from contextual evidence suitability. A publisher,
database, feed, official gazette, parliamentary record, first-party statement, independent
report, expert synthesis or archive copy may play different roles for different claims.

Minimum role vocabulary should cover at least:

- `PRIMARY_RECORD` — the underlying act, record, dataset or proceeding;
- `OFFICIAL_STATISTICS` — official statistical release/dataset for the stated scope;
- `AUTHENTIC_LEGAL_TEXT` — legally authoritative promulgated text where applicable;
- `OFFICIAL_PROCEDURAL_RECORD` — parliamentary/administrative proceeding or vote record;
- `FIRST_PARTY_STATEMENT` — what a person/organization itself publicly said or published;
- `INDEPENDENT_REPORTING` — reporting not merely copied from the same upstream item;
- `EXPERT_SYNTHESIS` — analysis or synthesis whose premises remain separately inspectable;
- `ARCHIVE_COPY` — preservation/copy role, not independent corroboration;
- `SECONDARY_REFERENCE` — navigation/context source that may point to stronger evidence.

Role names are evidentiary functions, not prestige labels.

### Contextual authority

Replace any semantic dependence on a global `authoritative=true/false` judgment with
explicit `authority_scope` records. A source can be authoritative for a bounded record
class while having no special authority outside it.

Each scope should identify, where applicable:

- jurisdiction/organization;
- record or dataset class;
- effective/valid dates;
- authenticity/status basis;
- canonical locator rules;
- supersession/version rules; and
- known limitations or required companion sources.

Legacy booleans may remain during migration but must not independently decide verification.

### Independence and derivation

Use inspectable relations rather than source reputation scores. At minimum support:

- `DERIVED_FROM`;
- `REPRINTS` / `SYNDICATED_FROM`;
- `MIRRORS` / `ARCHIVES_COPY_OF`;
- `OFFICIAL_RELEASE_OF`;
- `SUMMARIZES`;
- `INDEPENDENT_OF` only when there is affirmative reviewed evidence for independence;
- `UNKNOWN_RELATION` when independence cannot be established.

Multiple URLs repeating one upstream release count as one evidentiary lineage, not multiple
independent confirmations.

### Evidence requirement profiles

Define a versioned requirement profile per claim type (and optional jurisdiction/domain)
that specifies permitted/preferred evidence roles and minimum review conditions. Examples:

- numerical/statistical claims prefer the primary dataset/release for the exact metric,
  unit, population and reference period;
- legal-status claims require the applicable authentic/official legal record and temporal
  validity rather than a generic article summarizing it;
- quote/statement attribution requires the original attributable source or an approved
  provenance path. Source Intelligence only says what kind of source/evidence is required;
  DP-216..DP-222 own exact wording, transcript-verbatim eligibility, speaker/origin,
  context, derived wording and Person-identity integrity. A `FIRST_PARTY_STATEMENT` role by
  itself never proves that a particular quoted span was actually spoken by the named Person;
- historical claims may require contemporaneous primary records and/or independent
  scholarship depending on the question;
- causal or motive claims cannot become deterministic fact findings merely from correlation
  or repetition and must retain explicit assumptions/limitations.

Profiles define evidence requirements, not political outcomes.

### Evidence-set assessment

Persist an inspectable assessment of the evidence set for a claim/candidate:

- `SUFFICIENT_FOR_RULE`;
- `INSUFFICIENT_PRIMARY_SOURCE`;
- `INSUFFICIENT_INDEPENDENCE`;
- `TEMPORAL_MISMATCH`;
- `SCOPE_MISMATCH`;
- `CONFLICTING_EVIDENCE`;
- `ACCESS_OR_RIGHTS_BLOCKED`;
- `UNRESOLVED_SOURCE_IDENTITY`;
- `UNRESOLVED_DERIVATION`;
- `NEEDS_REVIEW`.

This assessment is a gate/input to verification and review; it is not itself a verdict.

## Scope

- Define source-profile, authority-scope and evidence-role persistence without duplicating
  existing `source`, Content, Capture, source-derivation or evidence tables.
- Add a migration path from `config/source-registry.v1.json` and
  `config/evidence-sources.v1.json` into the unified contract while retaining adapters as
  configuration seams.
- Link source relations to existing DP-115 derivation/independence records.
- Add versioned evidence-requirement profiles for existing ClaimType values.
- Compile requirement profiles into deterministic evidence retrieval/review constraints;
  generic model output may suggest queries but may not create/approve source authority.
- Feed missing requirements into DP-213 Coverage Needs.
- Expose source/evidence rationale to Studio review and, when appropriate, sanitized public
  method metadata.
- Add regression fixtures for duplicate news copies, official-vs-summary legal material,
  statistical period mismatch, first-party attribution and genuinely conflicting sources.

## Non-goals

- No universal source ranking, trust score, reliability score or political-balance score.
- No whitelist meaning “everything from this publisher is true”.
- No automatic truth verdict from source type alone.
- No forced equal weighting of evidence with materially different provenance.
- No automated accusation of deception, intent or bad faith.
- No broad crawling or source expansion merely because a source has a preferred role.
- No replacement of explicit Evidence approval, Verification, Finding review or Publication.

## Acceptance criteria

- [x] **AC-215.1:** The same source can have different explicitly scoped evidentiary roles
  without a global trust/reliability score.
- [x] **AC-215.2:** Two derivative/reprinted items do not satisfy a requirement for two
  independent sources.
- [x] **AC-215.3:** A claim-type requirement profile deterministically reports which
  evidence roles/scopes/time constraints are satisfied or missing.
- [x] **AC-215.4:** Legal/statistical/attribution fixtures reject scope or temporal mismatch
  even when the fetched source is otherwise approved and healthy.
- [x] **AC-215.5:** Conflicting qualified evidence produces an inspectable conflict/hold,
  never a hidden tie-break by publisher prestige or model preference.
- [x] **AC-215.6:** Missing required evidence creates/updates an DP-213 Coverage Need rather
  than infinite autonomous search or a weaker verdict.
- [x] **AC-215.7:** Existing evidence fetch allowlists, SSRF protections, cache hashes,
  review ledger and deterministic verification remain intact through migration.
- [x] **AC-215.8:** Public projection exposes only the approved bounded rationale/method
  metadata and never raw bodies, private notes, global source scores or operational secrets.
- [ ] **AC-215.9:** Garlasco tracer fixtures can explain every selected source by role,
  lineage, scope, time and rights state before DP-214 promotion/publication checks.

Mac-side verification 2026-10-01 (AC-215.1..215.8 proven on source authority;
AC-215.9 belongs to FUTURE DP-214 and MiniPC proof is still required, see below):

- AC-215.1: `test_same_source_can_have_multiple_roles_without_global_rating` +
  `test_source_intelligence_has_no_global_rating_fields` PASS.
- AC-215.2: `test_two_syndicated_items_do_not_satisfy_two_independent_lineages` +
  `test_independence_requires_affirmative_basis` PASS.
- AC-215.3: `test_contract_covers_every_claim_type_and_registry_source` PASS
  (plus ISTAT/first-party sufficiency fixtures).
- AC-215.4: Gazzetta scope/jurisdiction, ISTAT period and future-evidence
  temporal-mismatch fixtures PASS.
- AC-215.5: `test_conflicting_qualified_primary_records_hold` PASS.
- AC-215.6: `test_missing_primary_emits_coverage_need_candidate` PASS.
- AC-215.7: SSRF/allowlist suites (`test_evidence_runtime`, `test_ops_threat_matrix`,
  `test_source_adapters`, `test_source_watcher`) green inside the full suite;
  migration is additive (new normalized tables reusing DP-115 derivation).
- AC-215.8: `public_projection.py` selects only `assessment`,
  `assessment_version`, `requirement_profile_version`, `rationale_codes`
  (NULL when absent); `test_public_projection.py` asserts the bounded codes.
- Focused suites `test_source_intelligence` (14) +
  `test_source_intelligence_schema`: all PASS; complete deterministic suite:
  **968/968 PASS**; benchmark **5/5 PASS**; `compileall` PASS;
  `git diff --check` PASS.

## Validation / proof

- `python3 -m compileall -q poc tests`;
- `PYTHONPATH=poc python3 -m unittest discover -s tests -v`;
- `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark` when verification semantics change;
- source-methodology fixture suite covering role/scope/lineage/time/conflict cases;
- migration apply/replay in an isolated PostgreSQL schema with `ON_ERROR_STOP`;
- MiniPC read-back for runtime-affecting changes;
- `git diff --check`.

Ticket-specific proof must show that no source/global reliability score is created and
that missing/ambiguous evidence fails closed into review/Coverage Needs.

## Documentation, data, and migration impact

Update `CONTEXT.md` for the accepted vocabulary, `ARCHITECTURE.md` for the Source
Intelligence seam, schema/migrations for accepted persistence, and Studio/public method
documentation only after the runtime contract is proven. Source-specific rights/legal
decisions remain owned by DP-304..307, DP-603 and DP-703.

## Completion receipt

Mac-side implementation + verification recorded 2026-10-01 (see AC section above).

### MiniPC runtime proof 2026-10-01 (against Mac source `b099543`)

Same session as the DP-213 proof (shared pre-backup `20261001T154412Z`,
10,168,368 bytes; mirror parity 12/12 key files byte-identical;
both migrations replayed idempotently with `ON_ERROR_STOP=1`, COMMIT).

Isolated tracer in schema `dp213_215_canary` (dropped after; AC-215.1..215.8
exercised DB-backed through the real stores, not only in-memory):

- `load_source_intelligence_contract` from the MiniPC mirror configs + `sync`
  into canary: profiles 13 / requirements 26 / roles 19 / rules 92 /
  scopes 10 — exactly the production shape;
- `SUFFICIENT_FOR_RULE` for exact-period ISTAT numeric; `TEMPORAL_MISMATCH`
  with coverage-need candidates for wrong period; `persist_assessment` True
  then False on replay (idempotent);
- missing primary emitted a coverage-need candidate that materialized into a
  real `coverage_need` row linked to the persisted assessment id (AC-215.6);
- no global score created anywhere: `source_intelligence` tables carry roles,
  scopes, relations and requirement rules only (AC-215.1);
- production `evidence_set_assessment` stayed 0 rows; all 8 protected tables
  byte-identical (sorted COPY) between pre-proof backup and post-proof live;
  SI/coverage counts unchanged (13/19/10/0/26/92/0/0/0).

MiniPC suite: **968/968 PASS**; deterministic benchmark **5/5 PASS**.
Governed post-proof backup `20261001T160005Z` (10,168,365 bytes, `BACKUP OK`).
No live-provider calls made or required.

Status stays IN_PROGRESS until (a) AC-215.9 via FUTURE DP-214 (Garlasco tracer
explainability before promotion/publication checks) and (b) the DP-213/DP-214
integration pass. Record their receipts here before marking DONE.

Original pending note: implementation, migration, deterministic fixtures, MiniPC proof
and DP-213/DP-214 integration were all pending before this Mac-side verification.
