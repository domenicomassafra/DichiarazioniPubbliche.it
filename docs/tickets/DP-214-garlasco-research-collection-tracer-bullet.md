# DP-214 — garlasco research collection tracer bullet

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-117, DP-209..213

## Problem

The architecture is not proven until a messy real-world corpus can be collected, searched, deduplicated and promoted without corrupting existing claims or creating public side effects.

## Outcome

Build the first real `research:garlasco` collection using a bounded set of 100 real Content items across direct interviews/articles, video/podcast, official/procedural material where available, secondary reporting and deliberate duplicate/derivation examples.

## Scope

- Create a versioned source/query manifest and ingest exactly the bounded pilot set.
- Read back Captures, Passages, entity candidates, Statement/Claim Candidates, clusters and Coverage Needs.
- Link/dedupe against the 30 existing Bruzzone/Lucarelli Garlasco Atomic Claims.
- Review a stratified sample of entity matches and proposition clusters.
- Run idempotent replay and record cost/capture/search metrics.
- Promote at least a small approved candidate slice through DP-117 only when provenance is sufficient; do not publish automatically.

## Non-goals

- No claim that 100 items are exhaustive coverage.
- No “who is more truthful” comparison.
- No automatic guilt/culpability inference.
- No public release of raw corpus bodies.

## Dependencies and sequencing

DP-117, DP-209..213

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-214.1:** 100 logical items have discovery/source provenance and successful items have immutable capture receipts.
- [ ] **AC-214.2:** Duplicate/derivation examples are surfaced without deleting source records.
- [x] **AC-214.3:** Existing 30 claims remain unique and discoverable/linkable.
- [ ] **AC-214.4:** Search benchmark can answer the agreed Garlasco research questions with measured Recall@K.
- [ ] **AC-214.5:** Open authoritative-source gaps are Coverage Needs.
- [ ] **AC-214.6:** Replay leaves logical counts stable except for intentionally new Capture versions.
- [ ] **AC-214.7:** Public Finding/PUBLISH counts do not increase merely from ingestion.
- [ ] **AC-214.8:** MiniPC read-back and private/public leak checks pass.

## Validation / proof

- `python3 -m compileall -q poc tests` when Python/runtime code changes;
- `PYTHONPATH=poc python3 -m unittest discover -s tests -v` when code/schema contracts change;
- `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark` when claim/evidence/publication semantics change;
- `cd web && npm run check && npm run build` when web/Studio code changes;
- `git diff --check` always;
- runtime-affecting completion additionally requires MiniPC read-back from `/home/udodo/src/DichiarazioniPubbliche.it` and PostgreSQL `dichiarazioni_pubbliche`.

Ticket-specific proof must include the exact acceptance fixtures/receipts named above,
not only a green unit-test summary.

## Documentation, data, and migration impact

Real private production corpus on MiniPC. Rights/retention policy governs body storage; no public launch.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Local preflight/replay contract implemented in `garlasco_tracer.py`. It refuses a pilot
manifest unless it contains exactly 100 unique HTTPS logical items, discovery provenance,
rights state, all five required source-family classes and an explicit 30-claim baseline. A
replay receipt fails closed if logical item IDs/claims change or ingestion changes the public
Finding count; additional immutable Capture versions may be recorded without redefining a
logical item. Manifest hashing is deterministic and material-sensitive.

Read-only MiniPC reinspection on 2026-10-07 resolves the old **27-vs-30** baseline mismatch:
the authoritative PostgreSQL database now contains exactly **30** `claim:garlasco:*` Atomic
Claims. That recovery does not create the tracer-bullet corpus. The same current runtime has
**0** Research Collections, therefore no `research:garlasco` row or membership; the 18 current
Garlasco Content records linked by those claims have **0** `content_capture`, **0** `passage`,
**0** Statement Candidate, **0** Claim Candidate and **0** collection Coverage Need rows.
All 18 current Garlasco Content rows remain `rights_status=UNKNOWN`. No real 100-item Garlasco
manifest was found in the repository, current MiniPC `/tmp`, runtime mirror or the searched
operator-state/backups paths; the former curated intake manifest documented at
`/tmp/garlasco-curated-2026-09-28.json` is no longer present.

The current MiniPC global corpus-search benchmark still passes **13/13 (100% case recall)**,
which confirms the existing claims remain searchable. It is not a `research:garlasco`
collection-scoped tracer run and therefore does not close AC-214.4 or substitute for AC-214.1,
.2, .5, .6, .7 or .8. None of AC-214.1..8 is marked complete from this inspection.

The exact remaining data blocker is the real bounded pilot itself: a versioned 100-item manifest
with the five required source-family classes, discovery provenance and rights state, persisted as
`research:garlasco` and then processed through DP-209..213/117 so the required captures,
passages, candidates, derivation/duplicate examples, Coverage Needs, replay and MiniPC leak/public
count checks can be read back. No synthetic collection or fixture is accepted as a substitute.

### 2026-10-08 live baseline proof and seed export

**AC-214.3 closed independently of the still incomplete 100-item tracer.**
Read-only MiniPC queries confirmed exactly 30 distinct
`claim:garlasco:*` rows, 30/30 live content joins across 18 unique
Content IDs, and 30/30 **individual indexed lexical search retrievals**:
each historical normalized claim query returns its exact claim ID joined
to the correct Content ID within top 20. The existing 13-case top-5
Garlasco benchmark independently passed **13/13, p95=51.904ms**
(`CorpusSearchStore`, real MiniPC PostgreSQL). This proves persisted
baseline uniqueness, private searchability and linkability, *not* the
completeness or attribution accuracy of future sources. See
`docs/ops/garlasco-pilot-seed-readback-20261008.md`.

`garlasco_pilot_inventory.py` now reconstructs the **18 real Content**
URLs and exact 30 claim IDs from PostgreSQL without fetching, updating
or publishing anything. It writes the optional candidate manifest
outside the repository under a 0700 MiniPC operator directory with
a 0600 new-file-only constraint. The private file is explicitly
`INCOMPLETE_UNREVIEWED_SEED_NOT_FOR_INGESTION`: its 18 items have
**no manufactured discovery refs or source-family roles**, and all
have `rights_status=UNKNOWN`. The preflight therefore correctly reports
**82 missing logical items** and outstanding provenance, source role,
rights, capture, passage, Coverage Need and collection gates. 28
approved text-attribution rows are distinct from rights clearance.
The production public Finding count remains 2 `PUBLISH`.

AC-214.1/.2/.4/.5/.6/.7/.8 remain unchecked. Baseline query recall
without the real 100-item collection **does not** close AC-214.4.
The 18-item seed is a traceable operator starting point, not a
50/100/100-item filled fixture or a launch artifact.

The separate `config/garlasco-public-discovery-leads.v1.json`
registers six unreviewed public URL candidates with no present
Garlasco Content URL collision (MiniPC read-only comparison 0/6),
plus an official authority website as a *source locator only*.
All six remain rights/provenance unknown, not captured or ingested;
none is counted toward the accepted 100. The register is a concrete
next-step shortlist for reviewed discovery, not AC-214.1 proof.

### 2026-10-08 private PAUSED historical collection seed

The separate additive `garlasco_collection_seed.py` was executed only after
read-only dry-run, an actual PostgreSQL transaction ending in `ROLLBACK`,
and a protected MiniPC preimage backup. A guarded, atomic, explicitly
opted-in transaction persisted one **PAUSED** `research:garlasco`
collection with exactly **18 included links to the existing historical
Content IDs**. This is a *metadata-only research baseline*, not the full
100-item pilot and not an approved discovery/capture manifest.
The transaction verifies the exact versioned 18-item SHA-256, all 30
historical claims, Content ID/URL/Source ID bindings, unresolved rights,
absence of historic Captures/Passages, and unchanged public PUBLISH count.
It refuses concurrent source/claim drift, preexisting wrong-state
collection/memberships or hash mismatch, rather than force-overwriting.
Reapplying the same seed was verified against MiniPC PostgreSQL and
left exactly one collection and 18 members; no duplicates.

**Observed live postflight:** state `PAUSED`; collection 1, members 18/18,
rights `UNKNOWN` 18/18, claims 30, Capture 0, Passage 0, discovery
hits 0, public `PUBLISH` findings 2 (unchanged). DP-209's canonical
discovery manifest persists only for `collection.status='ACTIVE'`, so this
paused baseline is not an active intake campaign.

The previous unscoped Garlasco 13-case benchmark passed 13/13; scoped
to the first persisted collection, two PERSON queries initially failed
because the search filtered only `content_id` (11/13). The DP-116 SQL
was corrected to bind a PERSON result only through an included Content
with an exact persisted `atomic_claim.speaker_person_id`, and to
resolve COLLECTION results only for the exact collection ID. The
**real MiniPC collection-scoped benchmark now passes 13/13 (100% @5)**,
including both person cases, without exposing arbitrary persons.
This is a historical-baseline retrieval proof, not yet the full
100-item corpus AC-214.4 acceptance.

AC-214.1/.2/.4/.5/.6/.7/.8 remain unchecked. No source/capture rights
were granted, no discovery candidate was added to Content, no new
candidate/claim/finding was promoted and no public projection was changed.
Detailed receipt and rollback info: `docs/ops/garlasco-paused-baseline-20261008.md`.

### 2026-10-09 batch capture identity fence

The reviewed-input `private_capture_batch.load_private_capture_batch` now
rejects a manifest containing two different logical Content IDs with the
same canonical URL (`PRIVATE_CAPTURE_BATCH_DUPLICATE_URL`) before any
network acquisition. This prevents a single source locator from being
processed twice under competing logical identities in the same batch;
persisted discovery lineage and current rights gates still apply to every
item. Focused Capture/Candidate/Discovery tests passed **20/20** locally.
This is an engineering guard, **not** a successful real Garlasco Capture,
not rights clearance, and does not close any additional AC-214 criterion.

### 2026-10-09 readiness snapshot integrity

The private, read-only pilot readiness inventory now uses one SQL/MVCC
snapshot for Collection and Content membership metrics. Real MiniPC
read-back with the new source query (read-only connection, no mirror
deployment) confirms `research:garlasco` **PAUSED, 18/18 members**, no
Discovery Runs or unlinked Discovery Hits. See
`docs/ops/garlasco-research-readiness-20261008.md`. This is a monitoring
integrity improvement, not a source/capture/Candidate acceptance proof.
AC-214.1/.2/.4/.5/.6/.7/.8 remain open.

### 2026-10-09 follow-up: capture readiness and Discovery authority

The read-only readiness report now distinguishes a merely persisted rights
record from **current, reviewed, unexpired, exact-family private-capture
permission**. It reports missing active Source Intelligence profile, role
and scope separately, along with pending/approved derivation relations;
contradictory aggregate counts fail closed. The new SQL was evaluated against
the real MiniPC PostgreSQL in a read-only transaction: `research:garlasco`
remains PAUSED with 18 included Contents, no accepted Discovery provenance,
and no current source profile/role/scope, Capture or Candidate readiness.

The shared Discovery proof also refuses a database Content/Hit URL that is
not already exactly canonical and constrains its SQL scope parameters to
their semantic Collection/Content/URL roles. This blocks a noncanonical
persisted locator from being normalized into apparently accepted discovery
for a canonical operator batch. These are source-safety regressions and
diagnostics, **not** any new completed AC-214.1/.2/.4-.8.

The operator Capture preflight now applies the manifest's uniqueness,
bounds, canonical URL and optional SHA-256 integrity checks even when a
caller constructs a `CaptureBatch` directly instead of using the file
loader. The file loader refuses repeated JSON keys rather than silently
using the last `items` value. Both controls run before database reads or
network acquisition; they do not grant capture rights or imply a live
provider/corpus run.

### 2026-10-09 follow-up: pilot URL and source-family identity

The Garlasco structural manifest preflight now refuses noncanonical URLs
(including alternate host case, default-port spelling, fragment or padded
value) and checks logical duplicate URLs after canonicalization, not merely
the raw input strings. It rejects non-global literal IPs, invalid/custom
ports and unrecognized source-family values. The check aligns structural
intake with the stricter private Capture fetch destination restrictions.
Adversarial local fixtures confirm private-network URLs and hidden duplicate
locators cannot make a synthetic 100-item manifest appear structurally ready.
No genuine Content was added, and AC-214.1/.2/.4-.8 remain unchecked.

### 2026-10-09 follow-up: private inventory draft filesystem binding

The Garlasco inventory's optional private 0600 export now opens the
0700 owner-controlled destination directory without following a symlink,
verifies its descriptor/inode and creates the file with `O_EXCL` relative
to that descriptor. A concurrent pathname replacement can no longer
redirect the write into the replacing directory. Tests prove refusal of a
symlinked parent and safe containment under a simulated parent swap.
This is an operator-local private draft, not an ingestible Discovery
manifest or evidence of reviewed source rights.

### 2026-10-09 follow-up: Discovery restart and uncertain provider cost

The bounded Discovery runner now restores a persisted `cost_uncertain` state
from its canonical provider-receipt ledger when resuming a partially completed
run. A previous invoked paid adapter with `billing_basis=UNKNOWN` can no
longer appear to have spent zero merely because `research_discovery_attempt`
recorded `cost_usd=0`. The next adapter remains `BUDGET_BLOCKED` with
`COST_STATE_UNCERTAIN` and receives no provider call. A deterministic
restart fixture demonstrated a real RED on the prior code and GREEN after
the correction. It creates no new approved Discovery Hits or source rights;
the Garlasco tracer acceptance remains incomplete.

### 2026-10-09 private operator intake preflight hardening

The bounded private Capture batch now rejects syntactically canonical URLs
that the acquisition pipeline's *static* destination policy would reject
(loopback, ambiguous IP literals, internal names, non-443 ports), before
reading rights or Discovery state. The 25-item JSON manifest loader reads at
most 256,001 bytes and rejects over-limit files before parsing. Both failures
were reproduced RED and verified GREEN in focused local tests.

The Candidate batch also enforces exact stored Content and private-rights URL
spelling before model use, rather than allowing equivalent normalization
where the downstream persistence contract requires literal canonical URL
equality. Revalidation guards repeat this check after initial preflight.
These checks cannot certify DNS binding, rights, a real source, or model
processing. The MiniPC read-only snapshot remains **PAUSED / 18 included
Content / 30 historical Atomic Claims / 0 Discovery Hits, Captures, Passages,
Statement Candidates, Claim Candidates and collection Coverage Needs**.
AC-214.1/.2/.4-.8 remain open; these checks are not a live corpus tracer.

2026-10-09 follow-up: candidate `TEXT_POSITION` extraction also refuses
an internally inconsistent parent selector before invoking the model;
the safe DNS-pinned transport has been shared with optional Vimeo oEmbed.
The parent selector is not yet independently proven against immutable
Capture canonical text when a tampered span has the same length. Neither
change supplies genuine Content, review authority or the 100-item
acceptance, which remains open.
