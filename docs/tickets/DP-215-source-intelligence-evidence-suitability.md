# DP-215 — source intelligence and evidence suitability

Status: IN PROGRESS
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

2026-10-06 finalization re-read confirms this is still a real external dependency rather
than a missing deterministic unit test. DP-214 has no completed acceptance criteria for the
real `research:garlasco` collection/tracer and its required source-role/lineage/scope/time/
rights explanation before promotion is therefore unavailable. AC-215.9 remains unchecked;
no synthetic fixture or unrelated MiniPC canary is treated as a substitute.

2026-10-07 read-only reinspection against the authoritative MiniPC runtime narrows that blocker.
The historical baseline is now healthy at exactly **30** `claim:garlasco:*` Atomic Claims, so the
former 27-vs-30 mismatch is no longer blocking DP-214. The tracer collection itself is still
absent: `research_collection` has 0 rows, with 0 `research:garlasco` members/captures/passages/
Coverage Needs. Only 18 existing Garlasco Content records are currently identifiable in the live
database; all 18 have `rights_status=UNKNOWN`, none has a private rights record, and the 10 source
IDs represented by those records map to **0** active Source Intelligence profiles, roles, scopes
or approved source relations. The runtime also has 0 research-discovery manifests/runs/hits and 0
content-derivation candidates. A repository/MiniPC file search found no real 100-item tracer
manifest to evaluate.

The existing non-collection Garlasco search benchmark was rerun against the current MiniPC and
passes **13/13 (100% case recall)**. That proves searchability of the historical claim corpus, not
AC-215.9: there is still no selected 100-item DP-214 source set for which every source can be
explained by role, lineage, scope, time and rights state before promotion/publication checks.
AC-215.9 therefore remains unchecked and this ticket remains `IN_PROGRESS`. The required closure
input is the real DP-214 manifest/collection plus its persisted Source Intelligence and rights/
lineage data; fabricating profiles, rights decisions or a synthetic corpus would invalidate the
acceptance.

Original pending note: implementation, migration, deterministic fixtures, MiniPC proof
and DP-213/DP-214 integration were all pending before this Mac-side verification.

2026-10-09 follow-up: the DP-214 read-only readiness adapter reports missing
ACTIVE source profile, evidence role and authority scope separately for every
included Content, and distinguishes exact-family capture rights from mere
presence of a non-superseded rights row. The new SQL was run read-only against
authoritative MiniPC PostgreSQL: the PAUSED Garlasco baseline has 18 included
Contents and no active Source Intelligence profile/role/scope on those items.
This adds accurate operator diagnostics; it does not create source authority,
legal rights, lineage review or the 100-item tracer. **AC-215.9 remains open.**

2026-10-09 temporal/role suitability follow-up: the evaluator no longer
truncates malformed ISO timestamp suffixes to a valid date. For contextual
`AUTHORITY_SCOPE`, it requires the explicitly requested jurisdiction and
other match fields, binds a scope to its applicable required evidence role
instead of borrowing an unrelated secondary role, and enforces effective
`[valid_from, valid_until)` dates. Required temporal cutoff fails closed
when statement date is missing and emits an inspectable Coverage Need.
Both valid timestamp controls and disjoint required-role groups are covered
by focused tests. This does not certify a real Garlasco source or close
AC-215.9.

2026-10-09 private Candidate preflight safety follow-up: a persisted Content
locator or private-rights locator that merely normalizes to the requested URL
but is not *exactly* canonical now blocks model analysis before provider use.
The same exact-string comparison is re-applied by the operator guard upon
revalidation. Focused local regressions prove the previously accepted
upper-case-host mismatch is refused. This is a safety correction, not a
qualified Source Intelligence role/scope/lineage/rights evaluation of genuine
Garlasco Content; **AC-215.9 remains unchecked**.

2026-10-09 Wave 12 review-state fail-closed safety: `evidence_item_from_row`
previously inferred `APPROVED` when an otherwise plausible evidence row
omitted or blanked `status`, allowing a known registry source to qualify
without explicit observation review. It now defaults to `UNREVIEWED`, and
`assess_evidence_set` excludes and reports non-`APPROVED` rows as
`EVIDENCE_NOT_APPROVED`. Real guarded `approved_verification_evidence`
SQL already selects and filters the explicit approved state; this patch
protects other untrusted rows, not a newly proven provider. Synthetic
missing/null/blank/PENDING RED→GREEN plus explicit APPROVED positive
control passed. **AC-215.9 remains open** and no authentic Garlasco
evidence/rights were added.

## Post-grilling planning reconciliation — 2026-10-10

**Status unchanged; original acceptance checkboxes and dated proof remain authoritative.** This is a future target update, not source-rights approval or completion. Source: native lane A packet.

**Baseline and preserved proof:** **AC-215.1–.8 checked**, exact source-role/scope/lineage/period/source assessment contracts and MiniPC isolated canary. **AC-215.9 OPEN**. Historical rights facts and source-counts preserved.

**Target delta and remaining acceptance:** Only close AC-215.9 on **real selected DP-214 sources**, each traceable by role, derivative grouping, context scope/time, version and rights, before promotion. A role/authority classification is not an independent public quote grant or factual verdict. Avoid a second "source ranking" system.

**Phase / dependencies:** Phase 1 ongoing through Garlasco; hard DP-214 real corpus/rights decisions; soft B evidence requirements, A-NEW-02, D launch set.

**Related future specifications (separate ownership):** DP-236, DP-314. These coordination links are not newly asserted hard dependencies on this existing ticket. Hold when rights, attribution, budget or actual MiniPC acceptance is absent.

## 2026-10-13 — independent MiniPC selected-source explanation check (AC-215.9)

**Decision: AC-215.9 OPEN; status IN PROGRESS.** A fresh, actual read-only query
of the authoritative MiniPC PostgreSQL `dichiarazioni_pubbliche` evaluated the
persisted `INCLUDED` members of `research:garlasco` as they exist, rather than
substituting fixtures or unpersisted URL hints. It returned the following
aggregate without source identifiers, URLs, titles, bodies or private receipts:

| Selected-source prerequisite | MiniPC 2026-10-13 readback |
|---|---:|
| Collection status / included Content | `PAUSED` / **18** |
| Distinct represented Source IDs | 10 |
| Content `published_at` non-null | 18/18 |
| Content rights `UNKNOWN` | 18/18 |
| Membership `capture_authorized=true` | 0/18 |
| Bound active Source Intelligence profile | 0/18 |
| Active evidence role with a nonblank basis on that profile | 0/18 |
| Active contextual authority scope with a matching active role, basis and scope dimension | 0/18 |
| Approved source-profile relation with evidence basis | 0/18 |
| Approved Content derivation edge | 0/18 |
| Current exact-URL reviewed and unexpired private Capture-rights metadata | 0/18 |
| Active profile **and** role **and** scope **and** non-null publication date | **0/18** |

Independent live PostgreSQL sanity control: the overall tables are populated
with **13 ACTIVE profiles, 19 ACTIVE evidence roles and 10 ACTIVE scopes**;
their zero Garlasco bindings are not caused by absent Source Intelligence
tables. Globally there are zero `APPROVED` profile relations and zero approved
Content-derivation candidates. These are counts of database metadata, not
reviewed judgments about any unrecorded real-world relationships.

`published_at` being populated shows a stored timestamp, **not** verified
temporal applicability: the specific event/record version, valid interval,
claim cutoff and supersession still require per-source review. Missing an
approved derivative edge does **not** prove independence (or itself disqualify
an original source); lineage remains unassessed unless a documented origin,
derivation or affirmative independent relation is independently reviewed.
Likewise the scope counter is a necessary positive signal for applicable
contextual authority, not a blanket requirement that all ordinary reporting
sources claim official authority. The absence of every active source profile
and role independently prevents explanation of *every selected real source*.
`UNKNOWN` records a rights state; it does not grant retrieval, retention,
model processing or publication authority.

To reproduce the scoped, metadata-only source-descriptor aggregate, on the
authorized Mac with working `minipc` SSH alias execute the following. It uses
one SQL transaction, `BEGIN READ ONLY` and `ROLLBACK`, and does not read source
bodies or emit Content or person identifiers:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=6 -o StrictHostKeyChecking=yes minipc \
  'env LC_ALL=C psql -X -qAt -d dichiarazioni_pubbliche -v ON_ERROR_STOP=1' <<'SQL'
BEGIN READ ONLY;
WITH members AS (
 SELECT m.content_id, c.source_id, c.canonical_url, c.rights_status,
        c.published_at, m.metadata
 FROM research_collection_content m
 JOIN content_item c ON c.id=m.content_id
 WHERE m.collection_id='research:garlasco' AND m.status='INCLUDED'
), audited AS (
 SELECT m.*,
 EXISTS (SELECT 1 FROM source_profile p
         WHERE p.source_id=m.source_id AND p.status='ACTIVE') AS active_profile,
 EXISTS (SELECT 1 FROM source_profile p JOIN source_evidence_role r
         ON r.source_profile_id=p.id AND r.status='ACTIVE'
         WHERE p.source_id=m.source_id AND p.status='ACTIVE'
           AND btrim(r.basis)<>'') AS active_role,
 EXISTS (SELECT 1 FROM source_profile p JOIN source_authority_scope a
         ON a.source_profile_id=p.id AND a.status='ACTIVE'
         JOIN source_evidence_role r ON r.source_profile_id=p.id
         AND r.evidence_role=a.evidence_role AND r.status='ACTIVE'
         WHERE p.source_id=m.source_id AND p.status='ACTIVE'
           AND a.authenticity_basis IS NOT NULL
           AND (a.jurisdiction IS NOT NULL OR a.organization_ref IS NOT NULL
                OR a.record_type IS NOT NULL OR a.dataset_class IS NOT NULL))
         AS scoped_role,
 EXISTS (SELECT 1 FROM source_profile p JOIN source_relation rel
         ON (rel.from_source_profile_id=p.id OR rel.to_source_profile_id=p.id)
         AND rel.status='APPROVED' AND rel.evidence_basis<>'{}'::jsonb
         WHERE p.source_id=m.source_id AND p.status='ACTIVE')
         AS approved_profile_lineage,
 EXISTS (SELECT 1 FROM content_derivation_candidate d
         WHERE (d.origin_content_id=m.content_id OR d.derived_content_id=m.content_id)
           AND d.status='APPROVED') AS approved_content_lineage,
 EXISTS (SELECT 1 FROM private_source_rights_record rr
         WHERE rr.content_id=m.content_id AND rr.locator_kind='URL'
           AND rr.locator_value=m.canonical_url AND rr.rights_status='CLEARED'
           AND rr.record_visibility='PRIVATE' AND rr.reviewed_at IS NOT NULL
           AND rr.reviewed_at<=now() AND rr.reviewer_ref IS NOT NULL
           AND rr.rights_receipt_ref IS NOT NULL
           AND rr.permitted_uses @> ARRAY['RESEARCH_CAPTURE_PRIVATE']::text[]
           AND (rr.expires_at IS NULL OR rr.expires_at>now())
           AND NOT EXISTS (SELECT 1 FROM private_source_rights_record child
                           WHERE child.supersedes_id=rr.id))
         AS eligible_rights_metadata
 FROM members m
)
SELECT json_build_object(
 'collection_state',(SELECT status FROM research_collection WHERE id='research:garlasco'),
 'selected',count(*), 'distinct_sources',count(DISTINCT source_id),
 'published_at_present',count(*) FILTER (WHERE published_at IS NOT NULL),
 'rights_unknown',count(*) FILTER (WHERE rights_status='UNKNOWN'),
 'capture_authorized',count(*) FILTER (WHERE metadata->>'capture_authorized'='true'),
 'active_profile',count(*) FILTER (WHERE active_profile),
 'active_evidence_role',count(*) FILTER (WHERE active_role),
 'contextual_scope_with_role',count(*) FILTER (WHERE scoped_role),
 'approved_profile_lineage_with_basis',count(*) FILTER (WHERE approved_profile_lineage),
 'approved_content_derivation',count(*) FILTER (WHERE approved_content_lineage),
 'cleared_capture_rights_metadata',count(*) FILTER (WHERE eligible_rights_metadata),
 'role_scope_temporal_descriptors',count(*) FILTER (
    WHERE active_profile AND active_role AND scoped_role AND published_at IS NOT NULL)
)::text FROM audited;
ROLLBACK;
SQL
```

**Independent operator cross-check, actual MiniPC:** `PGDATABASE=dichiarazioni_pubbliche
PYTHONPATH=poc python3 tools/report_research_pilot.py --collection-id
research:garlasco --leads-file config/garlasco-public-discovery-leads.v1.json`
from `/home/udodo/src/DichiarazioniPubbliche.it` returned `NO_GO_READ_ONLY`,
`PAUSED`, 18/100 included, 30 historical claims, **18/18 missing accepted
discovery, active profile, role, scope, source rights, privacy relevance,
Capture, Passage, Statement/Claim Candidates and capture authorization**;
0 Discovery Runs, 0 accepted source families and 0 unlinked Hits. Snapshot
fingerprint `2950aceec11606b462cb0cee82620cd2f5e64ce818b64e9d44c779f09b6ecb8c`.
The fingerprint denotes operator metadata, not a rights/capture attestation.
Both live SQL and the operator cross-check exited **0** as queries: successful
execution only proves that their negative readbacks were obtained. Missing
collection, selected items, role/basis, scope, temporal evidence, lineage or
rights must still be treated as **NO-GO**, never as empty-success admission.

The *separate* original six URL hints remain `UNREVIEWED_CANDIDATES_ONLY`;
the local zero-acquisition Wave 22 preview on 2026-10-13 reported six old
plus two additional public-metadata candidate locators, five **proposed**
family labels, one origin follow-up and **zero accepted DP-209 Hits**.
The verified-public-page inventory includes a prosecutor's actual procedural
PDF candidate and a proposed news reprint relationship; neither has a
persisted Garlasco Source Intelligence explanation, approved derivation edge
or rights grant. Counting an official homepage, an Apple distribution mirror,
or multiple reprints as independent accepted case Content would be incorrect.

**Closure condition:** provide a real, specifically selected and deduplicated
DP-214 source set with persisted identity, evidence role and basis,
case-relevant scope, reviewed original/derivation/independence lineage,
effective dates/version applicability and explicit separate rights/access
states per Content; repeat the authoritative MiniPC per-item readback before
any DP-214 promotion/publication acceptance. Do not close AC-215.9 merely
because metadata hints cover five proposed families or a synthetic unit test
passes. AC-215.1–.8 retain their existing checked state and prior migration,
schema, privacy and runtime receipts; this read-only audit did not change
the accepted methodology or public projection. Fresh Mac validation:
`test_source_intelligence`, `test_source_intelligence_schema`,
`test_garlasco_discovery_leads`, `test_garlasco_lead_identity_guard`,
`test_garlasco_pilot_inventory` **48/48 PASS**; `test_public_projection`,
`test_coverage_needs`, `test_evidence_runtime`, `test_ops_threat_matrix`
**82/82 PASS**; Wave 22 local metadata preview exit **0**, still marks
`dp215_ac_9_complete=false`; `git diff --check` PASS. These tests protect
the existing scoped-source and rights logic, but the real MiniPC negative
readback is what determines the pending AC-215.9 acceptance state.
