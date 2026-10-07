# DP-702 — Pre-launch legal, security, and privacy review closure

Status: FUTURE
Milestone: M7 — stable v1 launch
Depends on: M3 (DP-301..DP-310), M5 (DP-501..DP-511), and DP-223; coordinate with DP-105, DP-401, DP-431/DP-432, and DP-603
Launch state: BLOCKED until qualified legal decisions, security/privacy controls, and MiniPC acceptance close every required launch surface

## Problem

The repository has fail-closed technical defaults and a private correction/reply
lifecycle, but those are not legal clearance, security approval, or proof that the
selected deployment is safe to operate publicly. Launch-sensitive questions remain
open across Italy/EU editorial responsibility, defamation and wording, privacy and
sensitive people, public submissions, copyright and platform terms, AI/DSA transparency,
retention, incident response, and the actual MiniPC operating profile.

The M5 plan also names security, restore, retention, SLO, alerting, and cost/outage work
that is not equivalent to DP-509 provenance hardening. The current checkout has no
qualified legal decision register, no accepted public launch profile, and no complete
release-facing M5 packet. A green deterministic test suite cannot close these gates.

## Outcome

Produce a versioned pre-launch closure packet that lets an authorized owner make one
explicit launch decision. The packet must:

- carry every required DP-301..DP-307 legal/privacy/rights decision to a dated owner and
  qualified-reviewer disposition;
- prove the Trust & Evidence publication boundary: DP-223 adversarial attribution benchmark,
  DP-308 evidence-safety profile, DP-309 high-risk escalation, and DP-310 review separation;
- prove the M5 security, restore, retention, SLO, alert, cost, and outage controls that
  apply to the chosen deployment;
- define the public/private trust boundaries, intake status, incident path, and rollback
  behavior for the actual v1 surfaces;
- list every remaining `PENDING-OWNER`, `EXTERNAL`, `BLOCKED`, or `NOT_APPLICABLE` item
  with an owner and exact action; and
- fail closed if any required surface lacks an accepted decision or proof.

This is an engineering/operational gate specification, not legal advice. It does not
appoint counsel, decide a lawful basis, or authorize a public launch.

## Baseline and evidence limits

- [`PRODUCT.md`](../../PRODUCT.md), [`CONTEXT.md`](../../CONTEXT.md), and
  [`ARCHITECTURE.md`](../../ARCHITECTURE.md) require provenance-first, private-by-default,
  append-only, and fail-closed behavior.
- ADR 0001 requires projection-time revalidation; ADR 0002 keeps the public read path
  separate from operational tables; ADR 0004 makes MiniPC the runtime authority.
- DP-301..DP-305 contain safe defaults and qualified questions, not legal decisions.
  DP-306 is a closure register and DP-307 is the required qualified-review handoff.
  DP-308..DP-310 are additional fail-closed publication controls and do not substitute
  for DP-307's qualified legal dispositions.
- [`docs/04-legal-safety-research.md`](../04-legal-safety-research.md) is preliminary
  research and explicitly says qualified review is required before public launch.
- The plan assigns M5 to DP-501..DP-511. DP-501..DP-506 are now `DONE` with their required
  implementation and MiniPC receipts, and DP-510/DP-511 are likewise `DONE` with targeted
  quarantine and source-drift/supersession runtime proof. DP-507/DP-508 remain conditional
  FUTURE surfaces and must be re-reviewed before any admin/intake exposure; their absence is
  not converted into `NOT_APPLICABLE` without the owner/security record required below.
- The current runtime baseline reports private processing and zero public dossiers, with
  OmniRoute claim extraction blocked and Groq ASR blocked. Those provider states remain
  visible in the launch packet.
- No files named `W0S`, `W0R`, or `W0O` were found in this checkout. External reports,
  if supplied later, must be referenced by stable ID/hash and not silently treated as
  this ticket's proof.
- No accepted qualified legal reviewer, public security contact, approved deployment
  profile, or production launch authorization is present.

## Scope

### 1. Legal/privacy/rights closure

Consolidate the DP-306 register and DP-307 dispositions for every launch-sensitive
question. The packet must record, per decision:

- question and affected surface;
- jurisdiction, deployment assumptions, and data/source/model assumptions;
- evidence source, date, version, and controlled-store reference;
- qualified reviewer and product owner acceptance;
- decision, conditions, prohibited behavior, and policy/version identifiers;
- retention, notice, rights, appeal, takedown, and re-review behavior where applicable;
- safe default while unresolved; and
- implementation ticket/ADR/test evidence.

The packet must not paste privileged advice, personal data, or confidential source
material into Git. A disclaimer, generic legal article, automated test, or model answer
cannot mark a question `DECIDED`.

### 2. M5 control closure

For the selected v1 deployment, the packet must link evidence for:

- **DP-501:** threat model and security regression matrix, including projection leakage,
  SSRF/fetch abuse, provider compromise, intake abuse, secrets, and operator boundaries;
- **DP-502:** PostgreSQL and public-projection backup/restore drill, with checksum and
  post-restore read-back;
- **DP-503:** retention matrix for raw media, transcripts, evidence, cache, backups,
  replies, corrections, rights requests, and legal holds;
- **DP-504:** SLOs, health/error taxonomy, bounded queues, and measurable failure states;
- **DP-505:** alert/digest acceptance and the operator runbook, including escalation and
  incident ownership;
- **DP-506:** cost caps, provider outage drills, circuit breakers, and no-budget
  fallback behavior;
- **DP-507:** AuthN/AuthZ/CSRF design and tests only if a public admin surface exists; and
- **DP-508:** public-intake rate limiting, spam controls, privacy review, and rollback if
  a public intake surface exists.
- **DP-510:** targeted provenance quarantine/hold with reviewed release and projection
  cleanup for a known-bad dependency; and
- **DP-511:** source drift/supersession/rights-expiry revalidation with bounded alerts and
  no silent evidence/source replacement.

If a conditional ticket is not applicable, the owner must record why the surface does not
exist, the evidence that it is not reachable, and the re-review trigger. “Not built yet”
alone is not a closure decision.

### 2A. Trust & Evidence closure

Before any public launch candidate is accepted, the packet must also prove:

- DP-223 runs against the candidate and reports zero known false public person
  attributions and zero fabricated direct quotations;
- DP-308 projection-time safety evaluation is enabled for every public Statement/Finding
  class in the launch set and has no fail-open warning mode;
- DP-309 high-risk/legal-status cases either satisfy the accepted stronger evidence/review
  policy or remain held; and
- DP-310 review-separation requirements are enforced for every risk class that requires
  dual control, with no self-approval fallback when a second reviewer is unavailable.

These are technical/editorial controls, not legal clearance. Any unresolved qualified
question still follows DP-306/DP-307 and blocks the affected surface.

### 3. Deployment trust-boundary decision

Record the exact v1 deployment topology and classify each component as public,
operator-only, private-runtime, or unavailable. The packet must prove:

- public reads use only the approved projection/static/API contract;
- public request paths make no LLM, provider, PostgreSQL, or private-filesystem call;
- administrative/review actions are local/operator-only or use a separately reviewed
  authenticated surface;
- provider credentials and runtime configuration stay outside Git;
- intake is either disabled/private or has the approved abuse and privacy profile; and
- source, media, transcript, evidence, and public-data lifecycles follow the accepted
  retention and rights decisions.

### 4. Failure and incident contract

The packet must include a failure matrix with an owner, expected state, detection
signal, safe user-visible behavior, recovery action, and durable receipt for at least:

- provider unavailable, timeout, quota, or changed response schema;
- stale/tampered transcript, speaker, evidence, observation, or review provenance;
- conflicting or incomplete source/evidence observations;
- projection schema mismatch, partial bundle, stale cache, or public-host failure;
- budget exhaustion and queue back-pressure;
- rights/retention hold, correction/takedown/appeal pending, or public omission;
- intake spam, malicious URL, rate-limit, or reviewer outage, if enabled;
- backup/restore failure or storage high-water mark; and
- suspected secret, private-data, or public-projection disclosure.

Every row must end in `BLOCKED`, `OMITTED`, `POLICY_HOLD`, `REJECTED`, or an explicitly
approved recovery state. No failure may become a fabricated verdict or an automatic
publication.

### 5. Closure packet and handoff

The final packet must include:

- a decision index with stable IDs and status for every required item;
- accepted ADRs/policy versions and implementation tickets;
- security/privacy/restore/retention/SLO/cost test receipts;
- public notices, privacy/terms placeholders or accepted documents, and contact paths;
- the affected-surface launch matrix and safe defaults;
- MiniPC mirror hash, service/queue/health state, and read-back evidence; and
- an explicit list of non-blocking follow-ups and re-review triggers.

The packet is an input to DP-704 and DP-705, not permission to deploy.

## Non-goals

- giving legal advice, selecting a lawful basis, or appointing a reviewer;
- implementing a new provider, admin service, intake endpoint, identity system, CDN, or
  security vendor;
- weakening no-intent, private-by-default, provenance, rights, retention, or fail-closed
  behavior;
- mutating production data, applying a production migration, or deleting evidence to
  obtain a pass;
- treating DP-509, a POC benchmark, a test pass, or a disclaimer as M5/legal closure;
- selecting a final domain, trademark, hosting vendor, or public URL; or
- opening a public site, dataset, API, tag, release, or deployment.

## Invariants

- `retrieved evidence != approved evidence != verification != publication` remains
  explicit in every gate.
- Public output is a bounded, sanitized projection; raw transcripts, evidence bodies,
  credentials, internal notes, and provider prompts remain private.
- A current status column, green test, or provider response is not a review event.
- Missing legal, privacy, security, rights, restore, retention, or runtime evidence is a
  blocker, not a reason to lower the quality bar.
- The public product must remain useful with providers offline.
- MiniPC proof is required for runtime-affecting acceptance; Mac proof is development
  evidence only.

## Launch blockers and exact unblock actions

| ID | Blocker | Exact unblock action | Evidence required | Owner/state |
|---|---|---|---|---|
| B-702-01 | DP-301..DP-305 policies are safe defaults, not accepted legal policy | Implement the policy contracts, answer their qualified questions, and hand the register to DP-307. | Cross-referenced Q-306 rows, policy versions, tests, and owner acceptance. | Product owner; `BLOCKED` |
| B-702-02 | No qualified Italy/EU review or accepted decision | Appoint the qualified reviewer, review the exact register/deployment assumptions, and record each disposition. | Reviewer identity/scope/date, controlled evidence reference, signed decision IDs. | Owner/counsel; `EXTERNAL` |
| B-702-03 | **CLOSED (technical)** — DP-501..DP-506 controls are implemented and carry MiniPC receipts | Keep the linked controls current for the selected candidate; any material change reopens this row. | DP-501 security matrix; DP-502 restore receipt; DP-503 retention matrix; DP-504 SLO/error tests; DP-505 alert/runbook receipt; DP-506 cost/outage drill. | Maintainer/operator; `CLOSED` |
| B-702-04 | Conditional DP-507/DP-508 status is unknown | Decide whether public admin/intake exists. If yes, implement the applicable auth/abuse controls; if no, record a verified `NOT_APPLICABLE` decision and re-review trigger. | Surface inventory and tests/runbook, or owner-signed non-applicability record. | Owner/security; `PENDING-OWNER` |
| B-702-05 | Deployment profile and public contact path are unowned | Freeze the MiniPC/static/API topology, operator roles, security/privacy/complaint contact, and incident owner. | Approved topology/profile, public policy documents, contact/runbook references. | Product owner; `PENDING-OWNER` |
| B-702-06 | Failure behavior is not proven end to end | Run the failure matrix on the MiniPC using isolated/canary data and verify blocked/omitted outcomes and receipts. | Sanitized receipts, actual read-back, queue/projection state, no publication. | Operator; `BLOCKED` |
| B-702-07 | Rights/retention/incident decisions are stale or missing | Re-review affected data classes, source families, public notices, and operational changes. | New decision IDs, policy versions, implementation receipts, and owner acceptance. | Owner/counsel; `EXTERNAL` |
| B-702-08 | **CLOSED (technical)** — attribution/evidence safety gate passes on runtime code candidate `4c93246` | Re-run this gate after any material attribution, projection, safety, high-risk, reviewer-authority or launch-candidate change; failing classes remain held. | DP-216..DP-224 closure; candidate DP-223 zero-tolerance benchmark plus persisted projection replay; DP-224 citation assurance; DP-308 safety, DP-309 high-risk and DP-310 review-separation receipts. | Maintainer/editorial engineering gate; `CLOSED` |

No row may be closed by deleting the blocker text, changing a status string, or adding a
generic “compliant” label.

## Acceptance criteria

- [ ] **AC-702.1 — Complete decision index:** Every DP-301..DP-307 question that affects
  the selected launch surfaces has a stable ID, status, owner, evidence pointer, safe
  default, and re-review trigger.
- [ ] **AC-702-2 — Qualified review:** The required reviewer and product owner accept
  the exact deployment assumptions; unresolved or conditional questions remain visibly
  blocked.
- [x] **AC-702-3 — M5 control packet:** DP-501..DP-506 have implementation and MiniPC
  receipts. These controls are mandatory for the selected v1 deployment; no
  `NOT_APPLICABLE` substitution is allowed for DP-501..DP-506.
- [ ] **AC-702-4 — Conditional surfaces:** Public intake and any admin surface have
  explicit enabled/disabled decisions; enabled surfaces have the required auth, CSRF,
  rate-limit, abuse, privacy, and rollback controls.
- [ ] **AC-702-5 — Trust boundary:** Public/static/API reads use only the approved
  projection, contain no private fields, and make no provider/LLM/PostgreSQL call.
- [ ] **AC-702-6 — Security/privacy regression:** Secret, raw-content, SSRF, URL,
  projection-tamper, stale-review, rights-hold, and access-control tests pass on the
  candidate and the MiniPC canary.
- [x] **AC-702-7 — Restore and retention:** A disposable backup restores successfully and
  the retention/hold dry run blocks unsafe deletion; no production data is mutated.
- [x] **AC-702-8 — Operations:** SLO/error taxonomy, health digest, alerts, cost caps,
  provider outage, and incident escalation are exercised with bounded receipts.
- [ ] **AC-702-9 — Failure matrix:** Every required failure path is injected or
  otherwise proven with an expected fail-closed state, recovery owner, and no fabricated
  public output.
- [ ] **AC-702-10 — Public communications:** Terms/privacy/method/security/contact
  documents are either accepted for the selected surfaces or the affected surface stays
  disabled; no placeholder is presented as a final legal document.
- [ ] **AC-702-11 — Re-review invalidation:** A material source, data-class, model,
  public-copy, hosting, jurisdiction, or rights change marks dependent decisions stale.
- [x] **AC-702-12 — No launch claim:** The packet reports `NO-GO` while any required
  blocker, missing M5 proof, or unresolved owner/external decision remains.
- [ ] **AC-702-13 — Handoff:** DP-704 consumes the packet and DP-705 can cite exact
  decision/control IDs without treating technical tests as legal approval.
- [ ] **AC-702-14 — Attribution/evidence safety:** DP-223 passes on the release candidate
  with zero known false public attribution/fabricated quote; DP-308 is active; applicable
  DP-309/DP-310 gates are satisfied; and unresolved cases remain held rather than downgraded
  to warnings or confidence-based publication.

## Validation / proof

The implementation receipt must run the standard checks from the candidate commit:

```text
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
cd web && npm run check && npm run build
cd .. && git diff --check
```

It must also include:

1. a decision-register validation for required fields, valid statuses, owner/reviewer
   evidence, dates, safe defaults, and re-review triggers;
2. a M5 control matrix linking each applicable ticket to test, runtime, and incident
   evidence;
3. a public/private projection and secret/private-content scan;
4. isolated backup/restore, retention dry-run, and migration apply/replay evidence when
   applicable;
5. a MiniPC failure-injection receipt with actual queue, health, projection, and public
   read-back state;
6. a read-only dependency/collision audit for the M3/M5/M7 ticket graph; and
7. an explicit statement that no production mutation, public route, remote, tag, or
   release occurred.

A local test pass is not legal/security/privacy closure. A missing reviewer, decision,
control proof, or MiniPC read-back remains `PENDING-OWNER`, `EXTERNAL`, or `BLOCKED`.

### Machine-only closure refresh — 2026-10-07

This refresh closes AC-702-3 and the technical B-702-03/B-702-08 rows. AC-702-14 remains
open because its wording is explicitly bound to the eventual release candidate; the repository
does not yet contain an owner-approved release candidate. This refresh does not create the final
pre-launch closure packet, qualify any legal/privacy decision, approve a deployment profile, or
authorize launch.

- **AC-702-3:** DP-501, DP-502, DP-503, DP-504, DP-505 and DP-506 are all `DONE` and each
  ticket contains its required MiniPC/runtime receipt. The authoritative MiniPC mirror's tracked
  files match current `HEAD`/`origin/main` `8b47c0cfc4fafea3136e6b9db7521f172ecf66dd` by
  checksum. On that mirror, a bounded M5 + publication-safety selection contains **191 tests**.
  With the normal SSH PATH, unittest reported **168 tests run, 2 class-level skips, 0 failures**:
  the two PostgreSQL-backed classes could not start because `initdb`/`pg_ctl` were outside PATH.
  Re-running those classes with `/usr/lib/postgresql/18/bin` on PATH passed the omitted **23/23**
  tests against disposable PostgreSQL. The selection exercises the security matrix,
  retention/destructive guards, restore verifier, SLO/taxonomy, operator runbook, cost policy,
  provider-outage behavior and downstream attribution/review gates. At the time of this
  2026-10-07 refresh, the separate production restore receipt was DP-502 set
  `20261007T160049Z`, with exact **97/97** persistent-table row-count parity; the
  2026-10-08 candidate-bound refresh below supersedes it with the 99-table receipt.
- **B-702-08 technical gate:** on the same current-main mirror, the dedicated DP-223 command
  reports **59/59 PASS**, `false_attribution=0`, `fabricated_quote=0`, `release_gate=True`. The
  PostgreSQL-backed persisted public-projection replay is included in the **23/23** rerun and
  exercises the authored corpus through persisted final-output handling. DP-216..DP-224 and
  DP-308..DP-310 are `DONE`; the current focused selection also exercises publication safety,
  high-risk gating/public serializers, review control, durable review replay and reviewer identity
  authority. Missing or stale proof remains a hold/omission rather than a warning-mode
  publication. This is current-candidate engineering proof only: DP-604 remains `IN PROGRESS`
  with no release authorized, the release policy still requires an owner-approved release
  candidate, and DP-704 remains `FUTURE`. AC-702-14 must be re-run and closed against that actual
  release candidate when it exists.

DP-702 remains `FUTURE` and launch remains `NO-GO`: AC-702.1/.2/.4-.6/.9-.11/.13/.14 and their
owner/external/release-candidate/composite-canary requirements are not inferred from these
engineering receipts.

### Candidate-bound restore/operations refresh — 2026-10-08

The DP-304 ingestion-relevance rollout materially changed the durable-table inventory, so the
restore/operations portion of this packet was refreshed against runtime code candidate
`4c93246f5f91ec5b29d710aa1dc73c80be732d8a`. This refresh closes only **AC-702-7** and
**AC-702-8**. It does not close the broader security/privacy regression matrix (AC-702-6), the
full failure matrix (AC-702-9), any qualified decision, or the release-candidate gate.

- **Restore/retention (AC-702-7):** after the additive DP-304 migration, production and repository
  inventories are **99/99** persistent tables. Backup set `20261007T225628Z` has dump SHA-256
  `f2f103e89e469538ab987e75e3dcaf68d3fd66488eca79db229d34444ad7fc96` and manifest SHA-256
  `004be1763d784c812447b06a2a2198c5fcbabf8781834cb85b43098f31721108`; the two new relevance
  ledgers are 0/0 rows. A disposable PostgreSQL 18 restore reproduced every **99/99** table count
  and the exact public-projection fingerprint
  `501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a` before automatic cleanup.
  On the same MiniPC mirror, the current retention/restore/health/ops selection passed
  **111/111**; its retention tests prove missing manifests/receipts, active holds, hash mismatch,
  path escape/symlink cases and non-ephemeral data fail closed. No production deletion was run.
- **Operations (AC-702-8):** the real MiniPC health service completed successfully on the candidate
  and wrote a private aggregate digest at `2026-10-07T22:57:42.284590+00:00`; public availability,
  queue-age/drain and cost objectives were healthy while public freshness correctly remained
  `UNKNOWN`, not silently upgraded. The candidate-bound 111-test selection also covers SLO/error
  taxonomy, health redaction/private mode, executable PAGE/NO_PAGE runbook policy, cost caps and
  alert taxonomy; the already-recorded DP-505 runtime matrix remains the live PAGE/NO_PAGE
  acceptance receipt.
- A fresh isolated provider-outage drill loaded both canonical database baselines
  (`schema.v1.sql` and `job_queue.v1.sql`) and used the real worker path. Missing OmniRoute
  credentials yielded `CLAIM_EXTRACTION_CANARY_FAILED:OMNIROUTE_API_KEY_MISSING`; the claim job
  became `BLOCKED`, atomic claims stayed 0→0, claim windows stayed 0, successful provider receipts
  stayed 0→0, published findings stayed 0→0, provider cost was 0 and model invocations were 0.
  The disposable cluster was removed afterward; no provider/model/quality downgrade occurred.
- Current local `/api/v1/health` returns HTTP 200 with contract status still `DRAFT`, 0 dossiers and
  dataset fingerprint `501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`.
  The three worker/source-poll timers are active. Production processing jobs remain explicitly
  bounded (`BLOCKED=30`, `COMPLETED=86`), and the new ingestion-relevance authority/permit ledgers
  remain 0/0 rather than being synthetically seeded to make runtime acceptance pass.
- The current MiniPC mirror also re-ran the DP-223 zero-tolerance benchmark: **59/59 PASS**,
  `false_attribution=0`, `fabricated_quote=0`, `release_gate=True`. This refreshes technical
  B-702-08 to the deployed runtime code candidate only. Receipt-only documentation commits after
  that code SHA do not change the runtime proof. **AC-702-14 remains open** because there is still no owner-approved
  release candidate / DP-704 rehearsal against which that release-bound criterion can be closed.

The launch preflight intentionally remains fail-closed. Its future release artifacts are currently
presence-gated because canonical DP-702/DP-703/DP-704/DP-705 artifact schemas/authorization fields
are not specified tightly enough to encode a semantic validator without inventing product/release
authority. No invented schema was added to make those blockers disappear.

## Documentation, data, and migration impact

- Add the closure index, decision links, control matrix, failure matrix, and operator
  runbook in the implementing change or controlled review store.
- Do not edit `PLAN.md`; the existing M3/M5/M7 ordering remains canonical.
- Add no production migration or data deletion to this ticket. Any policy change that
  affects persistence, retention, rights, or projection behavior requires its owning
  ticket, additive migration where needed, replay proof, tests, and MiniPC acceptance.
- Keep privileged advice, personal data, credentials, raw transcripts, and evidence
  bodies out of Git and public projections.
- A policy change after approval must create a superseding decision/review record and
  re-open the affected gate; it must not silently rewrite history.

## Completion receipt

Pending qualified legal/privacy decisions, owner-approved deployment profile, the remaining
security/privacy and full failure-matrix proofs, public communications/re-review decisions, and
the DP-701/DP-703/DP-704 handoffs. Current restore/retention and operations receipts are recorded
above but do not imply legal/security approval or release authority.
This ticket does not claim legal compliance, public security approval, or stable v1
launch readiness.

### Local fail-closed preflight receipt — 2026-10-05

`launch-preflight-v1` now reads the canonical PLAN status table and qualified-decision
register, requires the exact M2/M3/Trust/M4/M5/M6/M7 ticket set, keeps DP-507/DP-508
conditional surfaces undecided unless an explicit non-applicability record exists, and
requires the future prelaunch/launch-set/rehearsal/release-authority artifacts. The checker
can emit only `NO-GO` while blockers exist or `PENDING-OWNER` when mechanical inputs are
complete; it has no `GO`/deploy authority. The current checkout deterministically reports
`NO-GO`, including DP-201..204 provider blockers, open/blocked Q-306 rows, incomplete M5/M7
tickets and absent release artifacts. DP-602 contributor acceptance runs this check with
`--expect-no-go`, so a local green suite cannot silently upgrade launch readiness.

This proves only AC-702.12. It is not qualified legal/security/privacy closure and does not
close any other AC in this ticket.
