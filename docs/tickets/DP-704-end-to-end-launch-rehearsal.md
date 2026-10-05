# DP-704 — End-to-end launch rehearsal from source to correction

Status: FUTURE
Milestone: M7 — stable v1 launch
Depends on: M2..M6 exit gates; final sign-off also requires DP-701, DP-702, and DP-703 decisions
Launch state: BLOCKED until a full MiniPC rehearsal, failure-path proof, and rollback receipt are accepted

## Problem

Individual pipeline tests and historical runtime receipts do not prove that one accepted
candidate can traverse the complete provenance chain without a manual database edit:

`source -> content -> transcript -> speaker provenance -> verbatim/context/wording integrity ->
atomic claim -> evidence -> observation -> verification -> finding -> review -> public
projection -> correction/reanalysis`

A launch rehearsal must be more than a happy-path fixture. It must prove replay,
idempotency, provider/source failure, provenance tampering, stale review, budget
exhaustion, rights/privacy hold, correction/reanalysis, projection regeneration, and
rollback behavior. It must also prove that a failure never turns into an automatic
publication or a fabricated verdict.

This ticket is a controlled acceptance rehearsal. It does not itself launch the public
product, create a release, or mutate production data for the purpose of obtaining a
pass.

## Outcome

Run and record one bounded, reproducible rehearsal on the MiniPC that:

- uses an approved launch-set candidate and its exact commit/configuration/policy/schema
  fingerprints;
- traverses every required pipeline stage with inspectable IDs and receipts;
- exercises a successful source-to-projection path and a correction/reanalysis path;
- injects or otherwise proves the required failure paths, including provider outage and
  fail-closed publication behavior;
- verifies public/private read-back, replay/idempotency, source health, queue state,
  cost/budget behavior, and operator recovery;
- restores the prior known-good canary snapshot and records a durable rollback receipt;
  and
- produces an owner-signed `GO-CANARY`, `GO-WITH-HOLDS`, or `NO-GO` decision that
  DP-705 can consume without treating a local or fixture result as production proof.

`GO-WITH-HOLDS` is a rehearsal disposition only. It cannot authorize a public launch;
every held surface remains disabled or private until its blocker is closed and the
release gate is re-run.

A rehearsal is complete only when the actual resulting state is read back, not merely
because a command exited zero.

## Baseline and evidence limits

- The authoritative runtime is the MiniPC mirror at
  `/home/udodo/src/DichiarazioniPubbliche.it`; it is not a Git checkout and the Mac checkout
  is not runtime proof.
- The latest handoff reports 190 tests, deterministic benchmark 5/5, compileall pass,
  active source/worker/health timers, blocked OmniRoute claim parents, blocked Groq ASR
  jobs, and zero public dossiers. These are historical/development receipts and must be
  rerun against the candidate.
- M2 has explicit provider blockers; M3 has no accepted qualified legal decisions; M4
  public schema/hosting/API contracts are not all closed; M5 has missing ticket files or
  proofs in this checkout; M6 release/CI/licensing gates are specifications, not a
  release.
- The current production queue must not be used as a convenient fixture or modified to
  make a rehearsal pass. Use an isolated schema/database, approved private fixture, or
  explicitly authorized canary source with cleanup and a residue receipt.
- No files named `W0S`, `W0R`, or `W0O` were found in this checkout. Any external report
  must be linked by stable ID/hash and its claims must be checked against actual
  rehearsal state.

## Scope

### 1. Rehearsal identity and preflight

Create a rehearsal record with a stable `rehearsal_id` and record:

- candidate Git commit, MiniPC mirror hash, schema/migration version, policy version,
  public projection/API version, source-registry hash, and effective configuration hash;
- operating system, Python/Node/package versions, service/unit versions, and fixture
  hashes;
- database name/schema, isolation boundary, source/content IDs, operator/reviewer, start
  and end timestamps, and approved cost/time bounds;
- all prerequisite ticket IDs and statuses, including `PENDING-OWNER`, `EXTERNAL`, and
  `BLOCKED` items;
- the expected public and private outputs; and
- the cleanup/restore plan and rollback owner.

Preflight fails if any required dependency is unresolved, the graph has a cycle/collision,
the source is not authorized, the candidate contains secrets/private material, or the
canary boundary is unclear. Preflight never mutates production.

### 2. Required success path

The rehearsal must exercise, in order, the following observable contract:

| Stage | Required evidence and read-back | Fail-closed condition |
|---|---|---|
| Source discovery | source ID, effective registry hash, locator/content identity, source-health result, bounded receipt | unsupported, unauthorized, duplicate, malformed, or over-budget source is explicit, not successful |
| Content registration | content/locator IDs, publication time, source metadata, deterministic job identity | missing stable ID, conflicting identity, or unsafe URL blocks downstream work |
| Transcript acquisition | provider/source variant ID, hash, acquisition time, segment ranges, uncertainty markers | provider failure, partial response, sensitive disagreement, or missing provenance holds material use |
| Canonical transcript | canonical variant/segment IDs, timebase, source-variant links, replay result | changed input, ambiguous sensitive token, or missing segment mapping blocks claims |
| Speaker provenance | candidate method, source/official/manual provenance, review event, per-segment coverage | missing/ambiguous/biometric identity blocks publication |
| Verbatim/source-span integrity | DP-216 source/capture/span IDs, exact quote hash, selector/version and DP-217 verbatim eligibility | model-authored/unbound/stale quote or unverified transcript span blocks direct-quote publication |
| Origin/context/wording integrity | DP-219 reported-speech origin, DP-220 context state, DP-221 wording type, DP-222 Person identity/role-at-time | nested/reported quote, clipping ambiguity, translation/paraphrase confusion or identity ambiguity holds publication |
| Atomic claim | claim ID, type, temporal scope, segment edges, extraction receipt, replay result | free-form/out-of-window timestamp or missing edge rejects/holds the claim |
| Evidence | candidate/approved evidence IDs, fetched/observed URL/hash, approval and review events | unapproved, unfetched, ambiguous, unsafe, or future-only evidence cannot verify |
| Observation | observation IDs, typed values, source/evidence linkage, extraction receipt | missing observation, conflicting observation, or stale extraction blocks verification |
| Verification | rule/version, statement cutoff, input fingerprint, assessment, and run ID | no approved complete input, policy violation, or future-evidence misuse produces unresolved/hold |
| Finding/review | finding version, assessment, evidence/observation links, independent review event, publication status | stale review, missing review, or auto-publish path omits the finding |
| Public projection | projection fingerprint, JSON/JSON-LD/HTML/static/API artifacts, field allowlist, private-leak scan | missing/stale/incompatible/tampered projection yields no public dossier |
| Correction/reanalysis | correction request, superseding finding, trigger, processed re-analysis, parent/child review, public history | invalid chain, unprocessed trigger, or stale review leaves prior public version unchanged |

The success path must include a deterministic fixture lane and, where the launch set
requires it, the approved live/provider lane. A fixture must be labeled fixture-backed;
it cannot be reported as a live source receipt.

### 3. Full failure-path rehearsal

The rehearsal must exercise each row below and record the actual resulting state:

| Failure injection | Required expected state | Required receipt/check |
|---|---|---|
| Official claim provider unavailable, timeout, or schema drift | `BLOCKED`/deferred claim work; no child-job amplification; no fabricated claim | provider/recovery receipt, queue count, no-fan-out proof |
| Remote ASR credential absent or provider outage | ASR-dependent content held; caption/transcript path may continue; no guessed transcript | blocked job, source health, cost/provider receipt |
| Transcript disagreement around number, negation, date, or name | `TRANSCRIPT_UNCERTAIN`/hold; no material publication | candidate hashes, segment flags, projection omission |
| Speaker identity missing/ambiguous | claim remains private; no person ID or public attribution | candidate/review/projection read-back |
| Model/extractor invents plausible quote text absent from source span | quote candidate rejected/held; no direct quote in any public serializer | DP-216 source-span/hash check + projection read-back |
| Reported/nested speech is attributed to the reported person without original source | reported person remains unverified/held; Coverage Need may be created | DP-219 origin relation + no false public occurrence |
| Context clipping changes meaning (negation/qualification/question dependency) | `NEEDS_CONTEXT_REVIEW`/hold | DP-220 context receipt + projection omission |
| Paraphrase/translation is serialized as direct quote | serializer/policy rejects or labels the derived wording; no quote-equivalent fallback | DP-221 wording type + API/HTML/JSON-LD read-back |
| Same-name/stale-role person mapping | attribution held/role omitted until DP-222 identity proof passes | entity-resolution + role-at-time + projection read-back |
| Unsafe or partial evidence fetch | candidate rejected/held; no approved evidence or stronger verdict | fetch policy/error category, no body/secret leakage |
| Missing or conflicting observation | `NEEDS_MORE_EVIDENCE`/unresolved; no finding publication | observation and verification state |
| Future evidence used for an earlier statement | verification rejected or explicit later-outcome analysis only | cutoff test and policy receipt |
| Stale/tampered review or projection | projection omits affected finding/version and alerts operator | tamper fixture, before/after projection fingerprint |
| Correction chain invalid or re-analysis trigger unprocessed | old approved version remains; no new public version | correction/chain/trigger read-back |
| Rights/privacy/takedown hold | current public output is omitted or corrected per policy; private history remains | hold event, projection regeneration, audit receipt |
| Global/source/job budget exhausted | cheap discovery may persist; expensive work is blocked/deferred; no fallback verdict | cap values, cost receipts, queue state |
| Source timeout, access restriction, or policy rejection | only that source degrades/blocks; unrelated source behavior remains valid | per-source health and failure isolation receipt |
| Replay/restart after each committed stage | deterministic IDs, no duplicate content/jobs/versions, or explicit conflict | before/after counts and idempotency receipt |
| Public-host/API projection mismatch or cache staleness | fail closed with bounded error/omission; no operational data fallback | schema/fingerprint/ETag/error read-back |

At least one failure must be injected at each boundary: acquisition, transcript,
speaker, verbatim/origin/context/wording/identity, claim, evidence, verification, review,
projection, correction, and operations.
The rehearsal must not weaken a gate to make an injected failure pass.

### 4. Correction and reanalysis rehearsal

Use a private, bounded canary finding to exercise:

1. a private correction or right-of-reply request;
2. the deduplicated re-analysis trigger;
3. a new or superseding Finding with explicit review;
4. projection of the approved public version and correction history;
5. invalid-chain, stale-review, and unprocessed-trigger negative cases; and
6. a hold/omission case that removes only projection-owned stale artifacts while
   preserving private history and the prior approved version according to policy.

No correction or reply may be treated as intent evidence, and no operator may edit a
public version by changing a status column.

### 5. Rollback receipt

A successful rehearsal includes a durable rollback receipt with this exact minimum
shape:

- `rehearsal_id`, candidate commit, MiniPC mirror hash, operator, reviewer, and timestamps;
- isolated database/schema and source/fixture identifiers;
- migration/config/policy/schema fingerprints and `ON_ERROR_STOP` results;
- before/after hashes for database state, queue/health digest, projection bundle, and
  generated public files;
- stage receipts and failure-injection IDs with expected/actual states;
- exact restore/cleanup commands, restore read-back, and residue count;
- whether the canary was destroyed, retained under an explicit hold, or quarantined;
- owner disposition `ROLLBACK_VERIFIED`, `ROLLBACK_FAILED`, or `PENDING-OWNER`; and
- any residual blocker with an owner and next action.

A rollback receipt is not a backup filename, a successful `git checkout`, or an
uninspected command result. The prior known-good state must be read back before the
rehearsal can be signed.

## Non-goals

- launching the public site/API, publishing a dataset, creating a tag/release, or
  changing production data for rehearsal convenience;
- substituting a local fork, cheaper model, fabricated provider receipt, or fixture for
  an approved live path;
- changing the domain, provider, public schema, publication policy, or infrastructure;
- testing only the happy path or only local unit tests;
- deleting private history, raw media, or correction/reply records to obtain a clean
  output; or
- declaring stable v1 from a Mac, fixture-only, or zero-dossier run.

## Invariants

- No auto-publication; retrieval, approval, verification, finding review, and publication
  remain separate.
- A public claim requires approved non-biometric speaker provenance for every supporting
  segment.
- The public projection is sanitized, versioned, and fail-closed.
- Provider failure, budget exhaustion, stale state, rights holds, and ambiguous
  provenance produce blocked/omitted states.
- Replay is idempotent and cannot silently widen provenance.
- Runtime completion requires MiniPC evidence and actual read-back.
- A rollback receipt must describe an exercised, recoverable state.

## Launch blockers and exact unblock actions

| ID | Blocker | Exact unblock action | Evidence required | Owner/state |
|---|---|---|---|---|
| B-704-01 | M2 provider/attribution-integrity gate is open | Close DP-201..204 for every required live launch-set path or hold/exclude affected sources through DP-703; close DP-216..DP-224 for public-attribution paths. | Live receipts where applicable, DP-223 zero-false-attribution/fabricated-quote receipt, DP-224 citation-assurance receipt, queue/projection state. | Runtime/provider/maintainer owner; `BLOCKED/EXTERNAL` |
| B-704-02 | M3 policy/legal/evidence-safety gate is open | Close DP-301..DP-310 decisions/controls and update policy/ADR/test contracts before rehearsal sign-off. | Decision IDs, DP-308 safety-profile receipt, DP-309 high-risk state, DP-310 review-separation proof, accepted public wording/rights. | Owner/counsel; `EXTERNAL/BLOCKED` |
| B-704-03 | M4 public contract is unresolved | Close DP-105 and the required DP-401..410 acceptance path, including public schema and projection fingerprint. | Schema/API/UI/build/runtime receipts. | Maintainer; `BLOCKED` |
| B-704-04 | M5 controls are incomplete | Implement/prove DP-501..506, conditional DP-507/508 decisions, and DP-510/DP-511 quarantine/revalidation behavior. | Security, restore, retention, SLO, alert, cost, quarantine/source-drift and failure receipts. | Operator; `BLOCKED` |
| B-704-05 | M6 release inputs are incomplete | Close DP-601..605 as applicable, including clean-clone, CI, licensing, and release-policy gates. | Reproducibility, inventory, version/changelog, and owner receipts. | Maintainer; `BLOCKED` |
| B-704-06 | Launch decisions are open | Obtain DP-701 identity and DP-702 closure packet plus DP-703 source/disclosure decision. | Signed decision IDs and safe defaults. | Product owner; `PENDING-OWNER` |
| B-704-07 | No isolated canary boundary | Approve schema/source/fixture, permissions, cleanup, and production non-mutation boundary. | Canary manifest and operator sign-off. | Runtime owner; `PENDING-OWNER` |
| B-704-08 | Rollback cannot be proven | Execute the failure/recovery path, restore the prior snapshot, and attach the exact receipt. | `ROLLBACK_VERIFIED` receipt with hashes and read-back. | Operator/owner; `BLOCKED` |

## Acceptance criteria

- [ ] **AC-704.1 — Preflight:** The rehearsal manifest records exact commit, mirror,
  versions, hashes, dependencies, isolation boundary, owners, limits, and cleanup plan;
  all required gates are closed or explicitly held.
- [ ] **AC-704.2 — Full success path:** One approved candidate traverses all stages from
  source to public projection, with each required ID, receipt, review event, cutoff, and
  read-back present.
- [ ] **AC-704-3 — Fixture/live separation:** Deterministic fixture evidence is labeled
  separately from any live provider receipt; no fixture is represented as production
  evidence.
- [ ] **AC-704.4 — Failure coverage:** The rehearsal injects or proves every required
  boundary failure, including provider outage, budget exhaustion, stale/tampered state,
  rights hold, and source isolation.
- [ ] **AC-704.5 — Fail-closed result:** Every injected failure produces the expected
  blocked, held, omitted, rejected, or recovery state; no fabricated finding, transcript,
  evidence, provider receipt, or public dossier appears.
- [ ] **AC-704.6 — Correction/reanalysis:** A private challenge produces a processed
  trigger, explicit review, versioned correction/reanalysis, and public/private read-back;
  invalid or stale paths preserve the prior version.
- [ ] **AC-704.7 — Replay/idempotency:** Restarting each stage or the whole rehearsal
  produces deterministic identities, no duplicate public versions/jobs, and no silent
  provenance widening.
- [ ] **AC-704-8 — Private/public boundary:** Secret/private-content scans, projection
  allowlist tests, logs, health output, and generated files contain no prohibited data.
- [ ] **AC-704.9 — Runtime proof:** The MiniPC mirror runs the same candidate and records
  service/queue exit codes, source health, actual public/private state, and cleanup.
- [ ] **AC-704.10 — Rollback receipt:** The receipt includes the required before/after
  hashes, restore commands, read-back, residue, actor, time, and owner disposition.
- [ ] **AC-704.11 — Decision:** An owner records exactly one of `GO-CANARY`,
  `GO-WITH-HOLDS`, or `NO-GO`, with residual blockers and next actions.
- [ ] **AC-704.12 — No false launch claim:** The ticket cannot be marked complete while
  any required provider/legal/brand/data/security gate is open, and it does not authorize
  a public release by itself.
- [ ] **AC-704.13 — Attribution integrity release gate:** The same release candidate runs
  DP-223 with zero known false public person attributions and zero fabricated direct quotes;
  DP-308 publication-safety evaluation is active; and all injected reported-speech,
  context, translation/paraphrase, identity and stale-provenance cases remain held/omitted.

## Validation / proof

The rehearsal receipt must run and record the standard candidate checks:

```text
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
cd web && npm run check && npm run build
cd .. && git diff --check
```

Then execute the full stage/failure/correction matrix on the MiniPC and read back the
resulting database, queue, health, private artifact, projection, and public host/API
state. Run a read-only dependency/collision audit over the M2..M7 ticket graph and a
separate filename/owner collision audit. Any command that cannot be run is classified
`BLOCKED` or `PENDING-OWNER`; its expected output is not reported as a pass.

The rollback receipt is mandatory even when the success path is green. A clean local
rehearsal without MiniPC evidence is development proof only and cannot close DP-704.

## Documentation, data, and migration impact

- Add a sanitized rehearsal manifest, stage/failure matrix, correction receipt, and
  rollback receipt in the controlled operator/evidence store.
- Use an isolated schema/database and approved fixture/canary. Do not mutate production
  data to create a path through the pipeline.
- Any candidate migration uses the ordered, replay-safe procedure with `ON_ERROR_STOP`
  and isolated apply/replay proof; the rehearsal does not authorize a production
  migration.
- Preserve prior projections, findings, review events, replies, and corrections. A
  rollback restores the known-good candidate or omits output; it never silently deletes
  public history.
- Do not edit `PLAN.md`; M2..M7 sequencing remains canonical.

## Completion receipt

Pending all prerequisite gates, MiniPC full-path and failure-path receipts, correction
read-back, rollback verification, and owner decision. This ticket does not claim that
stable v1 is launchable or that a public deployment/release has occurred.
