# DP-307 — Qualified legal review and resulting ADR/policy changes

Status: FUTURE

Milestone: M3

Depends on: DP-306 closure register and a qualified Italy/EU legal reviewer

Launch state: BLOCKED; no qualified review or accepted decision record is present
  This ticket defines the handoff and acceptance boundary for qualified review. It is
not legal advice, does not appoint counsel, and does not authorize a public launch.

## Problem
  The M3 tickets can identify safe technical defaults and enumerate unresolved legal
questions, but a maintainer, agent, or generic research document cannot decide the
applicable Italy/EU obligations. The repository currently has no accepted qualified
review, no signed decision register, and no resulting ADR/policy closure. Silently
treating the checklist as approval would violate the product’s fail-closed launch
rules.

## Outcome
  Require a qualified, scoped, dated review of the DP-306 register and an explicit
owner decision for every launch-sensitive question. Accepted decisions must be
translated into durable ADRs/policy changes and implementation tickets; unresolved
or stale decisions remain visible blockers, and no affected public surface launches.

## Scope
- Select and record a qualified Italy/EU reviewer, scope, jurisdiction, assumptions,
  conflicts, and deliverable format.
- Review the complete DP-306 register and the current correction/reply, privacy,
  copyright, and public-projection contracts.
- Record each decision, condition, prohibited behavior, affected surface, policy
  version, and re-review trigger.
- Create resulting ADRs and policy/ticket changes through their owning work; verify
  that implementation and public gates match the accepted decisions.
- Define launch acceptance evidence and the process for later legal re-review.

## Non-goals
- Providing legal advice or pretending that this ticket itself is an opinion.
- Letting an LLM, web search, repository maintainer, or automated test certify
  legal compliance.
- Implementing public intake, changing production data, opening a public launch, or
  resolving a question by assumption.
- Weakening no-intent, private-by-default, append-only, provenance, or fail-closed
  invariants to obtain a desired launch date.

## Current baseline
- DP-301..DP-305 are specification work; their safe defaults are not legal sign-off.
- DP-306 is the required closure register and remains open.
- `PRODUCT.md` says a missing required legal decision results in non-publication.
- `PLAN.md` makes M3 policy closure a prerequisite for public launch and assigns
  DP-307 after DP-306.
- The runtime correction/reply lifecycle and public projection are already
  fail-closed, but they do not establish legal compliance.
- No qualified reviewer, written opinion/decision, or accepted resulting ADR is
  present in the repository.

## Constitution and non-negotiable constraints
- **C-307-01 — Human authority:** only the designated qualified reviewer and the
  product owner can accept a legal decision; agents may organize evidence and test
  implementation only.
- **C-307-02 — No implicit launch:** absent, partial, stale, or conditional review
  leaves the affected surface blocked and the M3 packet incomplete.
- **C-307-03 — Preserve safe defaults:** while review is pending, keep submissions
  private, omit unresolved excerpts/takedowns, use neutral claim-level wording, and
  fail closed.
- **C-307-04 — Traceability:** every accepted decision has a stable question ID,
  source/evidence reference, date, jurisdiction, assumptions, owner, policy version,
  and re-review trigger.
- **C-307-05 — No silent policy change:** a decision that changes durable product,
  architecture, public schema, or operational rules requires an ADR or canonical
  policy update plus an implementation ticket.
- **C-307-06 — No privilege leakage:** confidential legal advice, personal data,
  credentials, and reviewer notes stay in the approved controlled store; Git holds
  only the minimum decision record and identifier.
- **C-307-07 — Public safety over schedule:** under-publication is the required
  outcome when a decision is unresolved.

## Policy decisions

| ID | Decision | State |
|---|---|---|
| P-307-01 | A qualified review packet is mandatory before any public launch or public submission route. | Accepted launch gate |
| P-307-02 | DP-306 is the single question register; DP-307 records dispositions and resulting changes, not a second competing checklist. | Accepted documentation boundary |
| P-307-03 | An unresolved `BLOCKER` is a launch blocker even if the technical tests pass. | Accepted fail-closed rule |
| P-307-04 | A legal disclaimer, privacy notice, or “for research” label never substitutes for a required qualified decision. | Accepted product/security rule |
| P-307-05 | Any future intentionality, full-transcript, public UGC, or automated takedown capability requires a new decision and cannot be inferred from this ticket. | Accepted scope boundary |
| P-307-06 | Material changes to source, data class, deployment, model, public copy, or jurisdiction trigger re-review. | Accepted change-control rule |

## Engineering requirements
- **E-307-01 — Review identity and scope:** record reviewer qualifications,
  engagement/scope, jurisdictions, deployment assumptions, conflicts/independence,
  dates, and the exact DP-306 version reviewed.
- **E-307-02 — Decision intake:** require one disposition per Q-306 row with
  `DECIDED`, `DEFERRED`, or `BLOCKED`; attach the decision text/identifier, source
  evidence, conditions, affected surfaces, and next review date.
- **E-307-03 — Policy gate:** maintain a release-facing gate that refuses a public
  launch or affected intake surface when any required row is not `DECIDED`, is
  stale, or has an unaccepted condition.
- **E-307-04 — ADR routing:** route durable changes to PRODUCT/CONTEXT/ARCHITECTURE,
  an ADR, public schema, policy configuration, or implementation ticket according to
  the decision; do not hide a change in a code comment or fixture.
- **E-307-05 — Contract verification:** add deterministic policy tests for every
  accepted condition that can be represented in the runtime. A passing test is
  evidence of implementation, not legal proof.
- **E-307-06 — Re-review invalidation:** a material change marks affected decisions
  stale and returns the relevant surface to blocked/under-review until reaccepted.
- **E-307-07 — Audit and controlled evidence:** store the minimum decision metadata
  in the repository and a pointer/reference to the approved controlled review
  record; never paste privileged content or personal data.
- **E-307-08 — Runtime acceptance:** if a decision changes publication, intake,
  projection, retention, or rights behavior, run focused tests, the full suite,
  deterministic benchmark, migration/replay checks, `git diff --check`, and MiniPC
  runtime proof before unblocking the surface.
- **E-307-09 — Rollback-safe change:** if a policy is tightened, existing public
  versions remain traceable; the projection under-publishes or applies the approved
  correction/hold process rather than silently rewriting history.

## Qualified questions

| ID | Question for the owner/counsel | Why it matters | Until answered |
|---|---|---|---|
| Q-307-01 | Who is the qualified Italy/EU reviewer, what jurisdictions and deployment contexts will be covered, and are there conflicts? | Establishes authority and scope. | DP-307 remains blocked. |
| Q-307-02 | What deliverable is required: issue-specific dispositions, a written memorandum, or both, and what may be stored in the repository? | Defines the evidence handoff. | Use only a controlled reference; no launch decision. |
| Q-307-03 | Which DP-306 questions are launch blockers versus surface blockers, and what assumptions/conditions attach to each? | Drives release gating. | Treat every current `BLOCKER` as blocking. |
| Q-307-04 | Which changes require an ADR, policy version, migration, public notice, or new implementation ticket? | Prevents silent contract drift. | Route every material change to review; do not infer scope. |
| Q-307-05 | When does a material product/data/deployment change invalidate the review, and who accepts the re-review? | Defines ongoing governance. | Treat changes as stale and keep affected surfaces blocked. |
| Q-307-06 | What non-public contact, complaint, rights, or security channel must be available at launch? | Determines operational readiness. | Do not launch a public intake or user-facing policy surface. |

## Launch blockers
- **B-307-01:** No qualified reviewer or accepted scope is recorded.
- **B-307-02:** Any Q-306 row remains `OPEN`, `EVIDENCE_COLLECTED`, `DEFERRED`, or
  `BLOCKED` for a surface required at launch.
- **B-307-03:** A decision is not reflected in the owning policy/ADR/schema/runtime
  contract or its tests are missing.
- **B-307-04:** A material change invalidates the reviewed deployment but the
  decision was not reaccepted.
- **B-307-05:** A public route, source, or dataset is enabled without the applicable
  privacy, copyright, platform, editorial, and security decisions.
- **B-307-06:** Privileged/personal legal material is copied into Git or public
  output, or a disclaimer is used as a substitute for review.

## Acceptance criteria
- [ ] **AC-307.1:** Reviewer identity, qualifications, scope, jurisdictions,
  assumptions, dates, conflicts, and DP-306 version are recorded in the controlled
  review packet.
- [ ] **AC-307.2:** Every Q-306 row has an explicit disposition, evidence pointer,
  conditions, affected surface, owner acceptance, and re-review trigger.
- [ ] **AC-307.3:** No row is marked `DECIDED` solely because a generic web source,
  disclaimer, test, or agent summary exists.
- [ ] **AC-307.4:** Each durable accepted decision has an ADR/canonical policy
  update and/or a separately scoped implementation ticket; no policy change is
  hidden in code.
- [ ] **AC-307-5:** Deterministic tests cover every machine-testable accepted
  condition, including fail-closed behavior when the condition is absent or stale.
- [ ] **AC-307-6:** A material change to source, data class, deployment, model,
  public copy, or jurisdiction reopens dependent decisions and blocks affected
  surfaces.
- [ ] **AC-307-7:** Focused tests, full suite, deterministic benchmark, migration/
  replay checks, `git diff --check`, and MiniPC proof pass for any runtime-affecting
  change.
- [ ] **AC-307-8:** The final launch packet contains the accepted register, ADRs,
  policy versions, public notices/runbooks, test evidence, and an explicit list of
  any remaining non-blocking follow-ups.
- [ ] **AC-307-9:** No public launch or public submission is claimed while any
  required blocker remains.

## Validation/proof
- **Decision-register proof:** unique question IDs, complete dispositions, reviewer
  and owner sign-off, evidence/date fields, policy versions, and re-review triggers.
- **Contract proof:** ticket completeness/collision check for DP-301..DP-307;
  cross-reference all Q-306 rows to resulting ADRs/policy/test changes.
- **Repository checks for documentation-only closure:** `git diff --check`, relative
  link audit, and the ticket completeness/collision check.
- **Runtime proof when required:** focused tests, `python3 -m compileall -q poc
  tests`, `PYTHONPATH=poc python3 -m unittest discover -s tests -v`,
  `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`, and MiniPC inspection
  of the actual public/private output.
- **M3 packet check:** the seven ticket files, closure register, accepted decisions,
  and blockers form one coherent packet; no file claims legal clearance by itself.

## Documentation/data/migration impact
- The review packet and decision register belong in the approved controlled review
  store; this ticket may link to a stable identifier without storing privileged
  content.
- Material decisions may require updates to canonical product/architecture docs,
  ADRs, public schema, policy configuration, retention/rights records, and
  implementation tickets. Those are separately owned changes, not edits to this
  specification alone.
- Any runtime/data change requires an additive migration plan, replay/rollback
  proof, and MiniPC acceptance; no production data is changed to obtain sign-off.
- This specification does not implement legal controls or authorize public launch.

## Completion receipt
  Pending qualified review, owner acceptance, resulting ADRs/policy changes, and the
required runtime/documentation proof. Until then, the safe result is
  non-publication.

### 2026-10-09 release-preflight register completeness fence

`launch_preflight` now requires the entire **Q-306-01..16** decision universe
even if one or several rows disappear from the parsed legal register. A
missing row explicitly becomes `LEGAL_DECISION_NOT_CLOSED:<ID>:MISSING`,
not silent clearance. `EVIDENCE_COLLECTED` and `DEFERRED` are recognised but
remain launch blockers. Duplicate rows (even identical decisions) are
refused by the parser. Focused tests confirm that a fully green technical
ticket/artifact set with only Q-306-01 marked `DECIDED` still returns
**NO-GO** with 15 distinct missing legal questions.

Actual register remains **14 OPEN, 2 BLOCKED**, and preflight remains
**NO-GO / 41 blockers**. This is a fail-closed *engineering gate*, not
qualified legal review, a signed reviewer/owner opinion, approved policy,
or closure of any DP-307 acceptance criterion.
