# DP-229 — Bounded adversarial challenger / counter-case packet

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-228, DP-215; coordinate with DP-110 and DP-308

## Problem

Source conflict handling exists, but the pipeline has no first-class bounded step whose job
is to search for the strongest counterevidence, missing qualification or alternative
explanation before a consequential Finding is ready.

## Outcome

Create a private challenger packet using only approved evidence and bounded research
assignments. It surfaces counterevidence and limitations; it never votes on truth and never
overrides deterministic verification.

## Acceptance criteria

- [x] Pure challenger packet has a deterministic identity distinct from verification and
  Finding identity.
- [x] It may request missing counterevidence through DP-228/DP-213 but cannot fabricate it.
- [x] Packet keeps approved/suitable CONTRADICT, LIMITATION, CONTEXT and UPDATE evidence
  separate and retains independence groups/rationale codes.
- [x] Unapproved/unsuitable counterevidence is ignored with an explicit blocker.
- [x] Absence of discovered counterevidence creates no assessment/verdict and is not proof
  of truth.
- [x] Incomplete challenger research remains INCOMPLETE rather than ready.
- [x] Material challenger gain stales readiness/review until the exact material packet is incorporated and reviewed.
- [ ] High-risk DP-309 cases require the challenger step unless qualified policy says
  otherwise.
- [x] DP-223 includes cases where only the challenger lane reveals the unsafe conclusion.

## Completion receipt

Local counter-case packet + focused tests added 2026-10-05. The 2026-10-06 readiness seam
binds readiness/review to the exact material challenger packet, so a newly gained material
countercase stales both until incorporated and reviewed. DP-223 carries an explicit
challenger-only adverse/control pair and the offline release gate holds the stale case.
The evaluator also has a fail-closed high-risk switch. The 2026-10-06 closure pass adds a
typed adapter over the actual DP-309 `HighRiskDecision`: high-risk input requires the exact
incorporated/reviewed challenger packet, while a waiver is accepted only when it binds the
same qualified `policy_decision_ref` carried by an otherwise publication-eligible DP-309
decision.

The pure eligibility composer can bind a `ChallengerReadinessDecision` to a high-risk decision
for deterministic policy/testing, including an exact qualified-policy waiver. That helper is not
a runtime authority boundary. A follow-up combined audit found that the runtime wrapper had
incorrectly accepted the same caller-supplied in-memory readiness object even though no durable
challenger packet/review authority exists. An arbitrarily instantiated `READY` decision could
therefore satisfy the challenger portion of pure/runtime eligibility when the reviewer chain was
otherwise valid.

The runtime boundary now fails closed. `evaluate_publication_eligibility()` never forwards a
caller-supplied challenger readiness or waiver into the pure composer. Supplying readiness adds
`CHALLENGER_READINESS_AUTHORITY_UNAVAILABLE`; supplying a waiver adds
`CHALLENGER_WAIVER_AUTHORITY_UNAVAILABLE`; high-risk cases continue to carry
`HIGH_RISK_CHALLENGER_REQUIRED`. Rejected challenger values are not reflected as trusted packet,
version or waiver refs in the runtime result. Standard-risk eligibility remains possible from an
authority-attested durable reviewer chain, proving the fail-closed change is challenger-specific
rather than a global publication lock.

This deliberately reopens the high-risk integration AC and returns DP-229 to `IN PROGRESS`.
There is still no durable challenger packet/review ledger or independent challenger authority in
the current runtime, and none is invented here. Until such an existing/approved authority is
wired, runtime high-risk publication eligibility cannot be satisfied by challenger readiness or
waiver supplied by a caller.

Focused regression proof for the fail-closed repair is **18/18 PASS** for pure
countercase/eligibility, **12/12 PASS** for disposable-PostgreSQL durable runtime eligibility,
and **4/4 PASS** for production projection revalidation. The same three groups pass unchanged in
an isolated MiniPC `/tmp` bundle with production/provider credentials removed. The runtime suite
includes a directly instantiated forged `READY` challenger decision and an exact-looking forged
waiver; neither can authorize runtime eligibility.

### DP-228 challenger-request bridge — 2026-10-05

Added `poc/dichiarazioni_pubbliche/challenger_research.py`, a pure narrowing bridge from a
READY DP-228 `ClaimResearchPlan` to an explicit bounded challenger research request.

The bridge never manufactures a challenger lane: it selects only assignments whose lane
is already `CHALLENGER`, requires `challenger_enabled=True`, and blocks when DP-228 did
not opt into challenger research. Questions, adapter permissions, stop conditions and
budgets are copied/narrowed from the assignments; no evidence ID, source URL,
counterevidence text, verification assessment, Finding ID, publication status or truth
verdict exists in the request contract.

Independent caps bound challenger assignment count, aggregate results and aggregate cost;
exceeding a cap returns `BLOCKED` rather than truncating or widening permissions. A
blocked claim research plan cannot emit a READY challenger request.

Focused proof in `tests/test_challenger_research.py` covers deterministic request
identity, explicit opt-in, exact Coverage Need question reuse, no evidence/verdict
authority, assignment/result/cost caps, and refusal of blocked DP-228 plans.

The pure DP-309/challenger seam remains useful for deterministic tests, while the runtime gate is
intentionally blocked on a real durable/authority-backed challenger mechanism. DP-228/DP-209
research receipts by themselves are not challenger review authority and are not treated as such.

### Durable-authority audit — 2026-10-08

A closure audit intentionally made **no implementation change** because the missing runtime
authority cannot be made trustworthy by adding an append-only table around the current pure
packet object.

- `build_countercase_packet()` currently derives a deterministic packet from caller-supplied
  `CounterEvidence.approved/suitable/relation/rationale_code/independence_group` values plus a
  caller-supplied `research_complete` boolean. Those inputs are useful pure-policy fixtures, but
  they are not an independently replayable statement of the current canonical challenger
  material.
- Existing persisted `claim_evidence_candidate` / research-discovery / DP-228 records do not yet
  define the complete material authority required here: in particular there is no canonical
  versioned challenger snapshot covering the exact approved/suitable counterevidence set,
  `LIMITATION` semantics, rationale/independence approval, and invalidation when newly relevant
  material appears. The production projection revalidation path therefore has no safe current
  challenger packet to resolve.
- The attested DP-310 publication reviewer authority cannot be silently reused as challenger
  packet authority: no packet-specific attestation is defined that binds claim/finding version,
  current material hash/sequence, incorporation state and challenger review. Likewise DP-309's
  qualified `policy_decision_ref` approves the high-risk decision; it is not, by itself, an
  independently accepted challenger-waiver decision. DP-307 has no accepted decision authorizing
  such a waiver, so none is inferred.
- Persisting the present in-memory `READY` object would therefore launder caller-controlled
  approval flags and could remain apparently current after material challenger evidence changed.
  The runtime correctly continues to reject caller-supplied readiness with
  `CHALLENGER_READINESS_AUTHORITY_UNAVAILABLE` and caller-supplied waiver values with
  `CHALLENGER_WAIVER_AUTHORITY_UNAVAILABLE`.

Safe implementation is blocked until the contract defines: (1) authoritative current challenger
material selection plus a stable version/fingerprint and supersession rule; (2) exact incorporation
target; (3) independently attested challenger review bound to claim + record/version + packet
material/hash + policy; and (4) a separately scoped qualified waiver authority/freshness contract.
Only after those semantics exist is an additive private append-only ledger appropriate.

Focused audit validation on the current tree passes **50/50** across countercase, challenger
research, pure/runtime eligibility, durable publication review and high-risk persistence,
including disposable PostgreSQL; compileall and `git diff --check` also pass. The unchecked
high-risk challenger AC therefore remains a deliberate fail-closed blocker rather than a
machine-green placeholder.

### 2026-10-09 Wave 13 per-evidence replay fingerprint

The deterministic `countercase-v1` packet identity used only
the aggregate evidence IDs, rationale codes, relations and independent
lineage groups. Swapping the exact rationale/lineage assignments
between two otherwise valid evidence records left the packet ID
unchanged, allowing a stale incorporation/review marker to appear
current for different challenger material. A RED fixture reproduced
this collision. `countercase-v2` now fingerprints a canonical sorted
**per-evidence** tuple of evidence ID, relation, rationale code and
lineage, preserving order independence while invalidating changed
assignments. Focused adversarial, challenger, publication-eligibility
and high-risk tests passed. This is a breaking deterministic packet
identity upgrade, not an automatically authorized review migration,
waiver, signed high-risk approval or real Garlasco challenger
acceptance; DP-229 remains IN PROGRESS.

### 2026-10-10 retrieval replay / review authority integrity

An isolated real PostgreSQL regression exposed a defect in the upstream
evidence ledger: a retry of ClaimEvidenceObservationStore.link_claim_evidence
with the same (claim_id, evidence_id, retrieval_version) performed an
unconditional UPDATE. A reviewer-approved CONTRADICT evidence candidate
could become SUPPORT/RETRIEVED, with new score/metadata, solely because
the retriever replayed. REJECTED/QUARANTINED decisions could also be
silently reverted to RETRIEVED.

The writer now permits conflict updates only if the candidate is
RETRIEVED and there is no existing review event for that exact candidate.
An old review event also freezes previously demoted rows. Retrieval
cannot approve, reject, overturn reviewer decisions or publish.

The new tests/test_claim_evidence_retrieval_replay.py reproduced two
real PostgreSQL RED failures and passed five GREEN cases (approved,
rejected, quarantined, historical review event, and unreviewed replay).
This corrects a material provenance invariant but DOES NOT establish
durable challenger authority, qualified waiver, or runtime high-risk
publication acceptance. DP-229 remains IN PROGRESS.

The same integration pass closed a second review-ledger bug: reuse of
an unrelated review_event ID previously allowed the candidate status
to become APPROVED even though the event append conflicted and was
discarded. The approval writer now requires a newly appended exact
review event, or an exact idempotent replay against an already
APPROVED candidate. Historical stale events cannot reapprove a
demoted row. This does not relax DP-310 attestation requirements.

### 2026-10-10 evidence observation approval replay gate

The same update-before-review-event failure also affected
\`approve_evidence_observation_with_review\`. A real disposable PostgreSQL
RED fixture reproduced an unrelated event-ID collision setting an
observation to APPROVED without its own approval receipt. A second fixture
showed that an altered reviewer/reason could replay an event and that a
stale event could reapprove a downgraded observation. The observation
writer now gates approval on a newly inserted event or an exact replay
of a current APPROVED observation, preserving the DP-310 publication
review boundary. No DP-229 AC is marked done by this prerequisite fix.

### 2026-10-10 canonical live-material inventory (private, read-only)

Added `challenger_material_inventory.py` and adversarial tests. The inventory
uses one PostgreSQL statement over the real claim-evidence candidates,
their canonical evidence hashes/rights/record state and exact-identity
review events. Its deterministic digest includes pending and rejected
items, not only approved rows: new material, changed source bytes,
independence group, relation, rights, supersession or latest review action
invalidates the previous fingerprint. Its public return type has only
aggregates, digest and blocker codes, not URLs, excerpts or reviewer identities.

A read-only MiniPC canary (`default_transaction_read_only=on`) chose an
existing claim internally without printing its ID: **2 candidates,
2 pending/unverified, 2 counterevidence candidates,
`publication_authority=False`**. No DB write, service restart, reviewer
attestation or publication was performed.

This adds a canonical source-material fingerprint prerequisite, **not**
AC-229.8. Independent reviewer, research-completion, approved rationale
and incorporation authorities remain unavailable, and runtime high-risk
publication remains fail-closed.
