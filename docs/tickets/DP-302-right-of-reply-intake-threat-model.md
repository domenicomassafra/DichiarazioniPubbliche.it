# DP-302 — Right-of-reply public intake threat model and abuse controls

Status: IN_PROGRESS

Milestone: M3

Depends on: M0 baseline; coordinate with DP-303, DP-304, DP-505, and DP-508

Launch state: BLOCKED until the intake security/privacy profile and DP-306/DP-307
qualified review are accepted

This is a product, security, privacy, and engineering specification, not legal
advice. A **Qualified question** is not a legal conclusion and requires the owner or
qualified Italy/EU counsel.

## Problem
  The runtime already records a right of reply privately, links it to an explicit
re-analysis trigger, and requires a separate review before publication. It does not
yet have a public intake boundary, authentication/rate-limit design, abuse policy,
privacy-minimized acknowledgement, or incident path. Exposing the existing CLI
helper directly to the internet would turn a private review queue into an unsafe
untrusted-input surface.

## Outcome
  Specify a bounded public reply-intake contract that treats every submission as
untrusted and private, prevents spam/abuse/SSRF/resource exhaustion, preserves
append-only auditability, and cannot publish or fetch a submitted URL without the
existing review and safe-acquisition gates. The implementation remains disabled
until its security and legal launch blockers are closed.

## Scope
- Define the public intake actor, trust boundaries, request/response contract, and
  abuse-control requirements.
- Specify rate limiting, quotas, deduplication, bot/spam handling, moderation,
  privacy-safe logging, and operator review controls.
- Reuse the existing deterministic reply identity, private lifecycle, re-analysis
  trigger, and publication gate.
- Define the data retention, deletion, abuse-evidence, and incident requirements for
  intake metadata.
- Define tests and MiniPC acceptance for the eventual endpoint or adapter.

## Non-goals
- Implementing an HTTP endpoint, user accounts, CAPTCHA vendor, mail service, or
  public moderation UI in this ticket.
- Letting a submitter alter a Finding, approve evidence, publish a reply, or trigger
  a model verdict directly.
- Fetching submitted URLs at intake time.
- Replacing the operator-only review surface with unauthenticated administration.
- Promising a response time, identifying a submitter, or making a legal service-level
  commitment.

## Current baseline
- `poc/dichiarazioni_pubbliche/correction_runtime.py` validates a reply body of 1–20,000
  characters, optional identity fields of at most 300 characters, up to 32 HTTP(S)
  evidence URLs of at most 2,048 characters each, and a deterministic reply ID.
- `review_admin.record_right_of_reply` inserts `RECEIVED/PRIVATE`, enqueues
  `RIGHT_OF_REPLY` re-analysis, and links the job.
- `QueueRuntimeStore.publish_right_of_reply_with_review` requires a public parent
  Finding with its own `FINDING/APPROVED` review event, a processed reply trigger,
  and a separate `RIGHT_OF_REPLY/APPROVED` review event.
- `public_projection.py` omits replies unless status, visibility, re-analysis, and
  review event all pass.
- There is no public intake endpoint, authentication, rate limiter, or public
  anti-abuse runtime today.

## Constitution and non-negotiable constraints
- **C-302-01 — Private by default:** a submission is never public because it was
  received, stored, or marked accepted; publication is a separate explicit review.
- **C-302-02 — Untrusted input:** request data is bounded, validated, escaped, and
  treated as content, never as a URL-fetch instruction, policy override, or SQL
  fragment.
- **C-302-03 — No silent provenance widening:** duplicate/replayed submissions are
  idempotent and cannot append new evidence or alter the parent Finding.
- **C-302-04 — No unsafe fetch:** submitted URLs are candidate references only;
  retrieval uses the existing HTTPS/allowlist/DNS/redirect/size controls.
- **C-302-05 — Privacy-minimized operations:** logs, metrics, notifications, and
  abuse records do not expose reply bodies, contact details, secrets, or unnecessary
  submitter identity.
- **C-302-06 — Append-only audit:** receipt, moderation, hold, rejection, withdrawal,
  and publication decisions are recorded as events; no destructive status update
  erases prior history.
- **C-302-07 — No public model authority:** an LLM may not accept, reject, score, or
  publish a reply; deterministic controls and human review decide the transition.
- **C-302-08 — Availability:** limits and queue back-pressure fail closed without
  turning a public outage into a publication bypass.

## Policy decisions

| ID | Decision | State |
|---|---|---|
| P-302-01 | The v1 intake is a reply submission, not a general comment, account, or direct Finding edit surface. | Accepted scope boundary |
| P-302-02 | Submitter name and role are optional; no account or identity document is required for the baseline product. | Safe product default; owner/counsel confirmation required before launch |
| P-302-03 | The body and evidence references remain private until a reviewer explicitly approves publication and the parent Finding remains publishable. | Accepted product invariant |
| P-302-04 | A submitted URL is never fetched or rendered by the intake request; it is a candidate reference for the separate evidence pipeline. | Accepted security invariant |
| P-302-05 | The public acknowledgement contains only a bounded receipt/reference and generic state, never a copy of the body or an implication of acceptance. | Safe product default |
| P-302-06 | Abuse signals may quarantine or reject a submission, but may not create a person score, accusation, or public finding. | Accepted product invariant |
| P-302-07 | Rate limits, quotas, retention, and notice are explicit launch-profile values; until they are configured, the public intake remains disabled. | Owner/security decision required |
| P-302-08 | Identity verification, CAPTCHA, authenticated submission, and notification are future options, not implicit requirements of this ticket. | Pending owner decision |

## Threat model and required controls

| Threat | Required control | Fail-safe behavior | Proof seam |
|---|---|---|---|
| Spam or duplicate flooding | Per-network and per-Finding token buckets, global bounded queue, deterministic idempotency key, burst/cooldown policy | Return a generic bounded response; quarantine or reject without publishing | Intake contract and rate-limit tests |
| Bot or credential abuse | Optional privacy-reviewed challenge, request fingerprinting, anomaly quarantine, and operator review | Hold for review; never use a model verdict as a final decision | Abuse-control tests and audit events |
| Malicious URL | HTTP(S)-only validation, no userinfo, bounded length/count, no intake-time fetch | Store only a normalized candidate or reject; never resolve/fetch from request path | URL/SSRF regression fixture |
| Resource exhaustion | Request/body/field limits, timeouts, queue back-pressure, bounded response size, concurrency caps | Reject or defer with a generic response; do not degrade the reviewer path | Load/queue test on MiniPC |
| Impersonation or doxxing | Optional identity fields are bounded; no public identity disclosure; sensitive-data quarantine; reviewer separation | Keep private and route to a human; never auto-publish | Privacy/projection tests |
| Replay or forged provenance | Deterministic ID, source hash, request fingerprint, append-only event, parent Finding lookup | Idempotent duplicate or reject; never widen evidence links | Replay and concurrency tests |
| Review-gate bypass | Authenticated operator surface, explicit review event, projection revalidation | Omit reply and alert; no fallback to current status field | SQL/projection canary |
| Sensitive or abusive content | Deterministic intake bounds, optional quarantine, human moderation, incident handling | Private hold; no public copy | Moderation fixture and review receipt |
| Operational or provider failure | Provider/reviewer unavailable state, bounded retries, durable receipt, no LLM fallback | Queue/blocked state and generic user response | Failure-injection test |

## Engineering requirements
- **E-302-01 — Intake adapter contract:** define a narrow adapter with a request
  containing `finding_id`, bounded `body`, optional `submitter_name`,
  optional `submitter_role`, bounded evidence URL list, policy version, and a
  request fingerprint. The response contains only an opaque receipt ID, receipt
  time, and a generic state.
- **E-302-02 — Validation at the edge:** enforce exact types, UTF-8/size limits,
  normalization, URL scheme/host/userinfo rules, finding existence, and allowed
  content type before persistence. Reject malformed input without echoing it.
- **E-302-03 — Idempotency and deduplication:** reuse the deterministic reply ID
  and source hash; a replay returns the existing receipt or a bounded conflict
  response and cannot create a second re-analysis trigger.
- **E-302-04 — Abuse controls:** implement configurable per-network, per-Finding,
  and global token buckets; bounded queue and concurrency; cooldown; optional
  privacy-reviewed challenge; and a quarantine disposition. The launch profile must
  record values, owner, review date, and rollback behavior.
- **E-302-05 — Safe URL handling:** validate submitted URLs but do not fetch,
  resolve, redirect, screenshot, or embed them at intake. Later retrieval must use
  the existing evidence fetch boundary and its allowlist.
- **E-302-06 — Private storage:** keep body, submitter fields, and raw request
  metadata in the private operational store with access controls and retention
  classification. Do not place them in public indexes, analytics events, URLs, or
  error messages.
- **E-302-07 — Append-only moderation:** record receipt, hold, quarantine,
  rejection, withdrawal, acceptance, and publication decisions as events. A status
  column is only a cache and cannot authorize publication.
- **E-302-08 — Review authorization:** only an authenticated/operator-approved
  reviewer can inspect or transition a submission. A future HTTP admin surface must
  use the separate AuthN/AuthZ/CSRF ticket; no unauthenticated mutation is allowed.
- **E-302-09 — Projection defense:** retain the existing parent Finding approval,
  processed re-analysis, reply approval, visibility, and status checks at both the
  write gate and public read-model query.
- **E-302-10 — Abuse incident path:** provide an operator runbook for spikes,
  credential abuse, leaked personal data, and provider failure; incidents are
  auditable and fail closed.
- **E-302-11 — Data lifecycle:** define TTL and deletion behavior for rejected,
  withdrawn, and unpublished submissions, while preserving only the minimum
  durable receipt/audit data required by policy. Legal holds override ordinary TTL
  only through an explicit recorded hold.
- **E-302-12 — No new infrastructure by default:** prefer the existing queue,
  PostgreSQL, and bounded worker seams; any external challenge, mail, or storage
  service requires a measured need and separate decision.

## Qualified questions

| ID | Question for the owner/counsel | Why it matters | Until answered |
|---|---|---|---|
| Q-302-01 | What notice, consent, lawful basis, and retention period apply to an anonymous or identified reply submission? | Governs intake notice, storage, and deletion. | Keep intake private and disabled until counsel supplies a profile. |
| Q-302-02 | Does accepting replies or hosting user submissions create a platform/UGC or intermediary obligation in the intended deployment? | May change moderation, notice, and takedown duties. | Treat as unresolved; do not describe the service as a hosting platform. |
| Q-302-03 | What identity verification or notice is required before a submitter's name/role may be published? | Controls public projection of submitter fields. | Publish no submitter identity by default. |
| Q-302-04 | Which abuse signals may be collected, how long may they be retained, and how may a person request access/deletion? | Governs IP/device/fingerprint handling and privacy impact. | Collect the minimum needed; do not fingerprint beyond approved profile. |
| Q-302-05 | What notification, response deadline, and withdrawal/correction duties apply to a submitter? | Affects the receipt and lifecycle contract. | Use a generic receipt and leave deadlines unset. |
| Q-302-06 | Is a challenge/CAPTCHA or authenticated submission necessary for the launch risk profile? | Determines abuse control and data-minimization choices. | Keep the endpoint disabled until the owner/security decision is recorded. |

## Launch blockers
- **B-302-01:** No public intake endpoint may be enabled without a reviewed threat
  model, configured rate/quota/retention profile, and security regression proof.
- **B-302-02:** No reviewer may publish a reply through an unauthenticated or
  client-controlled path.
- **B-302-03:** No submitted URL may be fetched or rendered at the public boundary.
- **B-302-04:** No body, identity field, request fingerprint, or personal data may
  appear in logs, metrics, public receipts, or static output.
- **B-302-05:** DP-306/DP-307 have not resolved the applicable notice, platform,
  privacy, and moderation questions.
- **B-302-06:** The operator has not accepted a documented abuse incident and
  rollback runbook.

## Acceptance criteria
- [x] **AC-302.1:** The eventual intake contract accepts only the bounded fields in
  E-302-01 and rejects malformed, oversized, unsafe-URL, and wrong-type input with
  generic, non-reflective errors.
- [x] **AC-302.2:** A valid reply is stored `PRIVATE/RECEIVED`, receives a
  deterministic ID, and enqueues exactly one linked `RIGHT_OF_REPLY` re-analysis
  trigger.
- [x] **AC-302.3:** Duplicate and concurrent submissions cannot create duplicate
  public content, duplicate triggers, or wider provenance.
- [ ] **AC-302.4:** Rate/quota, queue, and concurrency tests demonstrate bounded
  memory, bounded work, and a stable response when the reviewer/provider is down.
- [x] **AC-302-5:** URL fixtures prove that intake performs no DNS, redirect, HTTP,
  screenshot, or embedding operation.
- [x] **AC-302.6:** Logs and public receipts are inspected to confirm that bodies,
  identity fields, raw request data, and unnecessary fingerprint data are absent.
- [ ] **AC-302-7:** Parent Finding approval, processed re-analysis, reply approval,
  visibility, and status are all required before the reply appears in any public
  serializer.
- [ ] **AC-302-8:** Abuse decisions are append-only, attributable, bounded, and
  explainable to a reviewer without exposing private content.
- [ ] **AC-302-9:** A privacy/security test demonstrates deletion or retention
  behavior for unpublished submissions and preserves an explicit legal hold.
- [ ] **AC-302-10:** The MiniPC canary exercises the real intake-to-private-review
  path under load, failure, and replay conditions without publishing an unreviewed
  reply.

## Validation/proof
- **Focused security proof:** edge validation, URL/SSRF, rate-limit, replay,
  concurrency, log-redaction, moderation-event, and projection-gate tests.
- **Repository checks:** `python3 -m compileall -q poc tests`,
  `PYTHONPATH=poc python3 -m unittest discover -s tests -v`,
  `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`, and
  `git diff --check`.
- **Runtime proof:** deploy only after implementation approval; run the intake
  canary and inspect private receipts, queue state, logs, and generated public
  projection on the MiniPC. No provider/model substitution is permitted.
- **M3 packet check:** link Q-302-01..06 to DP-306 and record the owner/counsel
  disposition in DP-307.

## Documentation/data/migration impact
- Add an intake threat model, field/retention classification, launch profile, and
  operator runbook in the implementing change.
- Reuse `right_of_reply`, `review_event`, and `reanalysis_trigger`; add only
  additive, bounded fields if the approved contract requires them.
- Any new field or state requires a replay-safe migration, compatibility tests,
  projection fixture updates, and MiniPC migration proof.
- No public endpoint, migration, or production intake is implemented by this
  specification-only change.

## Completion receipt
  Pending implementation, security/privacy review, MiniPC proof, and qualified legal
closure. The current private lifecycle remains the only implemented behavior.

---

## Implementation receipt — policy lane (2026-09-26)

Status: **threat model specified and the machine-checkable intake gate implemented;
public intake remains DISABLED; legal/security closure BLOCKING.**

### What was implemented

- `poc/dichiarazioni_pubbliche/policy/intake_policy.py` (new, pure/zero-I/O, no network, no
  DB): `validate_intake_payload()` (raw-mapping edge, key set checked before any
  value is read), `validate_intake_request()` (types/bounds/URL/fingerprint),
  `validate_evidence_url()` (http(s) only, no userinfo, length-bounded, **no
  fetch/resolve**), `compute_request_fingerprint()` (content-only; no IP/device
  fingerprint), `rate_limit_decision()` (pure decision over caller-supplied
  counters; unconfigured profile fails closed), `public_ack`/`acknowledgement_is_bounded`
  (bounded receipt, never an "accepted" claim).
- `docs/policy/dp-302-intake-threat-model.md` (threat→control→proof table, trust
  boundary, residual risk).
- `tests/test_policy_intake.py` (41 tests), including a `socket` mock that proves
  intake performs no DNS resolution and opens no connection.

### Key decisions

- Reused `correction_runtime`'s bounds (body 20k, identity 300, 32 URLs, 2048 chars)
  so the public edge and the private runtime cannot disagree; the reply ID is
  deterministic and content-only, so a replay cannot widen provenance.
- `RESERVED_OPERATOR_FIELDS` refuses injected `status`,
  `publication_status`, `public_visibility`, `review_actor`, `evidence_approved`,
  `moderation_decision`, `rights_status`, `policy_override` at the edge (B-302-02).
- Intent language in a reply body is **quarantined for a human**, not published
  (DP-301 hard rule); PII shapes (email/phone/long digit) are quarantined, never a
  person score (P-302-06).
- `INTAKE_ENABLED = False`, `LAUNCH_PROFILE_CONFIGURED = False`: the endpoint cannot
  come up before an owner/security-approved profile exists (B-302-01, P-302-07).

### What is NOT claimed

- No HTTP endpoint, CAPTCHA, accounts, mail, moderation UI, or abuse runbook
  (out of scope / E-302-10, B-302-06).
- No retention period, notice, lawful basis, or platform determination
  (Q-302-01..06, Q-306-03..05 `OPEN`/`BLOCKING`).
- No network abuse signal collection; that is an open privacy decision (Q-302-04).

Repository checks run: `compileall` OK; full suite green (515 tests);
`git diff --check` clean. Public intake stays disabled pending DP-306/DP-307 and an
operator-accepted launch profile + MiniPC canary (AC-302.10).

## Implementation receipt — runtime edge follow-up (2026-10-05)

Status: **callable private-intake adapter implemented and locally proven; public intake
remains DISABLED and launch remains BLOCKED.** No HTTP listener or endpoint was opened.

Implemented `poc/dichiarazioni_pubbliche/right_of_reply_intake.py`, composing the existing
`policy/intake_policy.py` validator/rate decision with
`review_admin.record_right_of_reply`. The adapter defaults to an unconfigured/disabled
launch profile and will not persist until the caller supplies both an explicitly enabled
launch profile and caller-owned rate/quota state. It performs no DNS, HTTP, redirect,
fetch, provider, or publication operation.

Persistence remains owned by the existing API: the submission is inserted through
`record_right_of_reply`, whose store contract creates `RECEIVED/PRIVATE` and a
deterministic `RIGHT_OF_REPLY` re-analysis trigger. The adapter observes the existing
`insert_right_of_reply()` and `enqueue_followup()` idempotency booleans without adding a
query or schema field: `true/true` is a new receipt, `false/false` is a completed
duplicate replay, and a mixed result is reported as a concurrent replay/race. The
canonical intake fingerprint is used only inside validation/idempotency handling and is
not emitted in the public acknowledgement or loggable receipt.

The acknowledgement is capped and contains only receipt metadata (`receipt_id`, policy
version, UTC receipt time, generic `RECEIVED_PRIVATE` state). It contains no body,
identity, evidence URL, raw fingerprint, acceptance/approval/publication claim, or raw
persistence error. Rejected, quarantined, quota-blocked, and rate-deferred requests do
not enter the persistence path in this adapter.

Focused proof in `tests/test_right_of_reply_intake.py` (13 tests): valid private receipt;
invalid-before-store; quota reject; rate defer; missing caller rate state; DNS/network
forbidden; no fetch/provider/publication; deterministic duplicate replay; concurrent
replay distinction; canonical fingerprint not logged; private body/name/reference not in
ack/loggable receipt; private persistence-error redaction; quarantine does not persist.
The existing 41 policy tests and 13 `review_admin` tests also remain green in the focused
run (54 tests total).

**AC evidence from this follow-up:** AC-302.1 PASS; AC-302.2 PASS at the callable/store
contract seam; AC-302.3 PASS for deterministic duplicate/concurrent adapter replay;
AC-302-5 PASS; AC-302.6 PASS. AC-302.4 remains open beyond the proven caller-supplied
rate/quota decision because bounded queue/load/outage acceptance is not implemented here.
AC-302-7..10 remain open: no projection work was changed, no append-only abuse-event
runtime or retention/legal-hold lifecycle was added, and no MiniPC load canary was run.
