# DP-211 — passage candidate extraction

Status: DONE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-114, DP-210; claim taxonomy DP-102

## Problem

The project needs to extract useful research structure from a large corpus without spending a full verification call on every passage or treating model output as truth.

## Outcome

Build a cost-aware extraction cascade from Passage/canonical media segment to entity mentions, Statement Candidates and Claim Candidates with schema-constrained outputs and provider receipts.

## Scope

- Deterministic segmentation/metadata and known-alias lookup before LLM calls.
- Bound model input windows and output schema.
- Extract attributable statement candidates separately from atomic claim candidates.
- Persist proposed claim type, check-worthiness, temporal scope and source pointers.
- Record extraction/model/version/cost receipt and blockers.
- Do not auto-promote; enqueue match/dedupe review.

## Non-goals

- No evidence retrieval/verdict.
- No identity merge from model output.
- No invented URLs/citations.
- No full-source giant prompt when bounded windows suffice.

## Dependencies and sequencing

DP-114, DP-210; claim taxonomy DP-102

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [x] **AC-211.1:** Every candidate points to exact Passage/segment provenance.
- [x] **AC-211.2:** Schema-invalid/model-failed output creates no candidate and records failure.
- [x] **AC-211.3:** Non-check-worthy/value candidates can remain searchable without entering verification.
- [x] **AC-211.4:** Replay under same operation key is idempotent.
- [x] **AC-211.5:** Cost/call counts are attributable per content/capture.

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

Private processing/runtime + provider receipts. No public side effect.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Implementation progress

Implementation is present in the working tree and remains intentionally private/non-public:

- `poc/dichiarazioni_pubbliche/candidate_extraction.py` implements bounded Passage/canonical
  segment extraction, deterministic operation/run/receipt identities, exact span validation,
  deterministic alias lookup before provider calls, schema-constrained Statement Candidate,
  Claim Candidate and entity-mention preparation, provider cost gates, durable failure
  receipts, lease/crash reconciliation and idempotent replay;
- the model may propose mention spans/types but never database identity IDs. Known aliases
  create reviewable `entity_resolution_candidate` rows only; they do not merge identities or
  approve written-speaker attribution;
- non-check-worthy/non-factual candidates remain private/searchable and are not promoted;
- `candidate_extraction_run` and `entity_mention_candidate` are defined additively in the
  canonical schema and `20260929-add-candidate-extraction-runs.sql`, with provider/call/cost
  accounting and exact Passage + Capture/canonical-segment provenance;
- `tools/extract_passage_candidates.py` provides the bounded operator entrypoint through the
  configured OmniRoute endpoint without hard-coding a model;
- provider receipts now reject secret-bearing keys and raw prompt/body/response payloads;
  schema-invalid provider output that cannot itself be serialized still terminates as a
  durable FAILED run rather than leaving a RUNNING lease until expiry;
- replay identity now fingerprints the validated extraction config, OmniRoute prompt version
  and template fingerprint, plus the exact deterministic alias-hint set used for the Passage.
  Alias/config changes or an actual prompt-template edit cannot silently reuse candidates
  produced under a different extraction request, even if a manual prompt-version bump is
  accidentally omitted;
- provider result cost/latency/usage contract failures terminate fail-closed with conservative
  cost accounting instead of leaving a stale RUNNING lease;
- immediately before any provider request the run durably reserves `call_count=1` and the
  validated cost upper bound. If the process dies while the request is in flight, an expired
  lease reconciles to `BLOCKED/ATTEMPT_RECONCILIATION_REQUIRED` with
  `provider_call_state=UNCERTAIN_RECONCILED`; replay never issues a second provider call;
- the provider lease is never shorter than the configured HTTP timeout plus a 30-second margin,
  preventing another worker from reconciling an in-flight request prematurely;
- canonical schema + migration enforce one-call semantics, zero cost before the call, and
  `COMPLETED => call_count=1 + provider_receipt_id`. The migration refreshes these named
  constraints so databases that saw an earlier DP-211 draft are hardened too;
- the OmniRoute prompt treats Passage text as untrusted quoted JSON data, explicitly rejects
  instructions embedded in source material, and uses a validator-compatible field/type
  template. Its pre-call cost bound covers the complete prompt bytes plus maximum output,
  including taxonomy and alias hints rather than only Passage text;
- missing OmniRoute credentials/model/rate fail before the network call, and HTTP failures are
  classified from status without parsing or retaining error bodies;
- extraction config is validated both from disk and direct provider overrides, with hard upper
  bounds on input, response, output and candidate fan-out. Config/prompt/alias fingerprints are
  part of replay identity so a semantic-input change cannot reuse stale model output;
- the atomic SQL batch has explicit data-modifying CTE dependencies for Passage -> Statement ->
  Claim and ProviderReceipt -> completed run, on top of `psql ON_ERROR_STOP=1`, so a child or
  receipt failure cannot be reported as a completed partial batch;
- focused unit/schema tests cover exact offsets, ambiguous aliases, non-factual check-worthiness,
  written/media provenance, provider/schema failure, pre-call and post-call cost gates,
  replay/in-progress/expired lease behavior, receipt minimization and public-projection
  isolation.

Remaining before DONE:

1. execute focused DP-211 tests plus compile/diff checks after the latest receipt hardening;
2. execute the complete suite and deterministic benchmark;
3. replay the additive migration in an isolated MiniPC schema and run a functional tracer
   proving candidate counts, provenance, invalid-output failure, cost-block and idempotent replay;
4. run one explicitly budgeted provider canary only if model/rate/provider configuration is
   valid; provider unavailability remains BLOCKED rather than being substituted;
5. apply/read back production migration only after backup, prove zero Atomic Claim/Evidence/
   Verification/Finding/publication side effects, then commit and record exact receipts below.

## Certification tracer — prepared, not yet executed

Use the same proof shape as DP-210: isolated PostgreSQL first, then bounded production
read-back. This section is an execution contract, **not** a completion receipt.

### Isolated PostgreSQL

1. Create a fresh `dp211_canary` schema from the current canonical schema and separately
   prove upgrade replay from the pre-DP-211 schema by applying
   `20260929-add-candidate-extraction-runs.sql` twice with `ON_ERROR_STOP=1`.
2. Seed one written Content + immutable Capture + `TEXT_POSITION` Passage and deterministic
   Person/Organization aliases. Keep all IDs under the `dp211-canary:` namespace and do not
   create Atomic Claim, Evidence, Verification or Finding rows in the seed.
3. Run a deterministic local provider stub through the real `CandidateExtractionStore` with
   one factual claim, one `VALUE_JUDGMENT`, one known alias and one ambiguous alias. Assert:
   - run `COMPLETED`, `call_count=1`, provider receipt present;
   - exact Passage/child-Passage offsets and hashes point back to the seeded Capture;
   - factual and value-judgment claims remain `CANDIDATE`; the value judgment is
     `check_worthy=false`;
   - alias matches create reviewable resolution candidates only; written
     `speaker_person_id` remains null;
   - `provider_call_state=FINISHED_COMPLETED` and persisted cost equals the validated
     provider result, not the reserved upper bound.
4. Replay the exact same operation and assert the same run/candidate IDs, one provider call
   total and no extra candidate rows.
5. Change only the extraction prompt/config fingerprint, then only the alias-hint fingerprint,
   and prove each change yields a distinct operation key rather than replaying stale output.
6. Run invalid-output, raw/sensitive receipt, invalid request-id, invalid cost/latency/usage,
   provider failure and pre-call cost-cap cases. Every case must be terminal and create zero
   candidate rows for that operation; pre-call blocks must keep `call_count=0`, while
   post-call failures keep `call_count=1`.
7. Simulate a hard process crash after `mark_provider_call_started`: before reconciliation
   the row must be `RUNNING`, `call_count=1`, `cost_usd=cost_upper_bound_usd` and
   `provider_call_state=STARTED_COST_UPPER_BOUND_RESERVED`. Expire the lease and replay;
   assert `BLOCKED/ATTEMPT_RECONCILIATION_REQUIRED`,
   `provider_call_state=UNCERTAIN_RECONCILED` and no second provider call.
8. Assert the named DB constraints exist and reject impossible direct writes:
   `candidate_extraction_run_call_count_check`,
   `candidate_extraction_run_pre_call_cost_check`, and
   `candidate_extraction_run_completed_receipt_check`.
9. Before and after the entire tracer, compare counts/digests for `atomic_claim`, `evidence`,
   `verification_run`, `finding`, review/publication queue surfaces and public projection.
   They must be byte/count stable. Cleanup all `dp211-canary:%` rows and prove the baseline
   digest is restored.

### Bounded provider canary

Run only when all three are explicitly configured and valid: OmniRoute credential,
`DICHIARAZIONI_PUBBLICHE_CANDIDATE_EXTRACTION_MODEL`, and
`DICHIARAZIONI_PUBBLICHE_CANDIDATE_MAX_USD_PER_1K_TOTAL_TOKENS`. Use one private canary Passage and a
non-zero explicit cost cap. Missing credentials/model/rate, provider rejection, rate limit,
timeout or malformed output is a truthful `BLOCKED`/`FAILED` result; do not substitute a
different provider/model and do not call that success.

### Production read-back

Take the governed pre-migration backup and baseline digest first; apply/replay the migration;
read back the three named constraints; run at most the bounded private canary above; prove
there are no new Atomic Claim/Evidence/Verification/Finding/publication rows; remove only the
canary rows; prove baseline digest restoration; run the complete MiniPC suite, deterministic
benchmark and any corpus-search acceptance required by the repository; then take/read back the
post-migration backup. Record exact commands, counts, IDs, cost receipt and backup names below
before changing this ticket to `DONE`.

## Completion receipt

Completed and runtime-certified on 2026-09-30 from implementation candidate
`ef784b1c8c8341cd4680b1b215ed8bf1b0505633` on `main`.

Local source-authority proof:
- `python3 -m py_compile poc/dichiarazioni_pubbliche/candidate_extraction.py tools/extract_passage_candidates.py`: PASS;
- focused DP-211 unit/schema suite: **52/52 PASS**;
- complete deterministic suite: **922/922 PASS**;
- deterministic verification benchmark: **5/5 PASS**;
- contributor acceptance, licensing/hash inventory and `git diff --check`: PASS.

Isolated MiniPC PostgreSQL proof:
- mirror key-file digest matched the Mac candidate exactly:
  `89a6871b2c117e66c2816b064fe25b0758a722814cc0a199b6e46f117be8c40f`;
- a fresh schema accepted the current canonical schema; a separate `dp211_canary` schema
  was built from pre-DP-211 commit `a8bb9ec` and migration
  `20260929-add-candidate-extraction-runs.sql` applied and replayed with
  `ON_ERROR_STOP=1`;
- deterministic stub success run
  `candidate-extraction-run:5cb52418ce72d014ff7413105cc9d8e2a814dbd24bf9d5180ad06ca4492c3cfc`
  completed with `call_count=1`, 3 Statement Candidates, 3 Claim Candidates, 4 entity
  mentions, 3 resolution candidates and provider receipt
  `provider-receipt:0b5cefef516a6c3913961edfa0b39f1abd9b941f98b0ab0ddb0ba48a353e1de7`;
- the three child Passage selectors round-tripped to exact parent offsets/hashes
  `(135,169)`, `(171,197)`, `(198,229)`; all written statement speakers remained null;
  the `VALUE_JUDGMENT` stayed `check_worthy=false`; `Mario Rossi` remained two ambiguous
  resolution candidates while `Roberta Bruzzone` produced one known-alias candidate;
- persisted success state was `FINISHED_COMPLETED`, actual cost `0.000050` against reserved
  upper bound `0.000100`; exact replay reused the run/candidates with one provider call total;
- config-only drift produced distinct run
  `candidate-extraction-run:f8ceed00352fbd8de712b677fcd35c2b051bb01a324dddaeed8365d98d59da1d`;
  alias-only drift produced distinct run
  `candidate-extraction-run:42851af41fb78207376745eefea7a40d84562c450f0f983fdf067e6d2cad9df0`;
- invalid output, raw receipt, sensitive receipt, invalid request ID, invalid cost, invalid
  latency, invalid usage and provider failure all became terminal `FAILED`; cost-cap became
  `BLOCKED/COST_CAP_PRECALL` with zero provider calls. Across all non-completed runs there
  were **0** Statement/Claim/EntityMention/EntityResolution candidate rows;
- simulated hard crash after provider invocation left
  `RUNNING|call_count=1|cost=0.000100|STARTED_COST_UPPER_BOUND_RESERVED`; expired-lease
  replay became `BLOCKED/ATTEMPT_RECONCILIATION_REQUIRED` with
  `UNCERTAIN_RECONCILED`, equal reserved/recorded cost and **0** second provider calls;
- all three named DB constraints both existed and rejected impossible writes:
  `candidate_extraction_run_call_count_check`,
  `candidate_extraction_run_pre_call_cost_check`,
  `candidate_extraction_run_completed_receipt_check`;
- isolated review/right-of-reply/correction/job and AtomicClaim/Evidence/Verification/Finding
  counts stayed zero; forbidden receipt bodies/secrets had zero persisted occurrences; both
  canary schemas were dropped after proof.

Production MiniPC proof:
- pre-migration state had no DP-211 tables and read back 30 Atomic Claims / 17 Evidence /
  9 Verification Runs / 9 Findings / 49 Review Events / 112 Processing Jobs / 0 replies /
  0 corrections;
- governed pre-migration backup `20260930T123059Z`: readable **10,083,622-byte** dump;
- production migration applied and replayed idempotently; both DP-211 tables read back empty
  and all three named constraints read back present;
- the frozen pre-backup versus post-migration normalized data for Atomic Claim, Evidence,
  Verification, Finding, Review, Processing Job, Right-of-Reply and Correction was exactly
  stable: **226 rows / 137,126 bytes**, SHA-256
  `39a7874aedbb2f6c39675e8cfa2c6849fa4afa8b8dfd385231675296eb55130e`;
- no bounded live-provider call was made because all three required runtime settings were
  absent: `OMNIROUTE_API_KEY`, `DICHIARAZIONI_PUBBLICHE_CANDIDATE_EXTRACTION_MODEL`, and
  `DICHIARAZIONI_PUBBLICHE_CANDIDATE_MAX_USD_PER_1K_TOTAL_TOKENS`. This is a truthful provider-canary
  blocker, not a substituted-provider success;
- final MiniPC suite: **922/922 PASS**; deterministic benchmark **5/5 PASS**; corpus-search
  benchmark **13/13 Recall@5**, p95 **74.4 ms**;
- the existing public projection bundle remained outside the migration path; its current
  bundle digest is `2f802df9cb9a67672845513a5516dd9f9fd460dd6f888d89be319c4ab489d5a0`
  and `index.json` mtime is 2026-09-27, predating the DP-211 rollout;
- post-migration backup `20260930T123520Z`: readable **10,096,495-byte** dump; manifest
  reads `candidate_extraction_run=0`, `entity_mention_candidate=0`, `atomic_claim=30`,
  `evidence=17`, `verification_run=9`, `finding=9`.

DP-211 creates no DP-212 downstream jobs and does not promote, verify, find or publish. The
provider canary may be exercised later when the exact credential/model/rate contract is
configured; its absence does not weaken the deterministic/runtime certification above.
