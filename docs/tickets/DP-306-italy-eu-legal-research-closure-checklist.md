# DP-306 — Italy/EU legal research closure checklist

Status: DONE

Milestone: M3

Depends on: DP-301..DP-305

Launch state: BLOCKED; this checklist can be prepared, but it cannot substitute for
qualified legal review in DP-307

This is a research and decision-control checklist, not legal advice. It records
questions, evidence needs, owners, and safe defaults. It does not answer any legal
question or authorize public launch.

## Problem
  The repository contains preliminary legal/safety research and a safe technical
baseline, but the launch decisions span editorial responsibility, defamation and
reputational language, privacy/sensitive data, public submissions, copyright and
platform terms, AI/DSA transparency, retention, and incident response. Those
questions currently have no qualified disposition. A list of general web links is
not a closure record, and a model or maintainer cannot self-certify legal closure.

## Outcome
  Produce one traceable, versioned closure register that maps every launch-sensitive
question to a qualified Italy/EU reviewer, dated evidence, an explicit decision or
remaining blocker, affected product surfaces, and a safe default until the decision
is made. The register must make it impossible to treat an unresolved question as
implicitly approved.

## Scope
- Consolidate the qualified questions from DP-301 through DP-305 and the repository
  legal/safety backlog.
- Define the evidence packet, decision IDs, status vocabulary, owner/authority,
  review date, affected surfaces, and re-review triggers.
- Track unresolved questions as explicit launch blockers, not as model-generated
  answers.
- Define the handoff to DP-307 and the conditions for resulting ADR/policy changes.
- Define documentation and completeness checks for the M3 packet.

## Non-goals
- Providing legal advice, a legal opinion, a privileged conclusion, or an assurance
  of compliance.
- Selecting a lawful basis, exception, retention period, quotation right, platform
  permission, notice deadline, or regulator position.
- Treating general research, a disclaimer, or a “legal note” as closure.
- Implementing code, changing production data, opening a public intake route, or
  editing `PLAN.md` in this specification-only ticket.
- Delegating the legal decision to an LLM, search result, or unreviewed community
  interpretation.

## Current baseline
- `PRODUCT.md` and `CONTEXT.md` establish the no-intent, private-by-default,
  append-only, provenance-first, and no-biometric invariants.
- `ARCHITECTURE.md` requires fail-closed public projection, bounded acquisition,
  private operational data, and explicit review.
- `PLAN.md` places DP-301..DP-307 in M3 and makes legal policy a prerequisite to
  public launch.
- `docs/04-legal-safety-research.md` is explicitly preliminary product research and
  lists the legal questions to study; it is not a closure artifact.
- `docs/28-claimreview-correction-reply-policy-v1.md` and
  `docs/29-data-provenance-security-hardening-v2.md` document the implemented
  private reply/correction lifecycle and fail-closed projection.
- The correction/reply runtime is a technical baseline, not legal approval.
- No qualified Italy/EU legal reviewer, signed opinion, or accepted decision
  register is present.

## Closure register schema
  Every question row must contain:
- stable question ID and topic;
- question phrased without an assumed answer;
- jurisdiction(s), deployment context, and affected product surface;
- evidence/source list with publisher, date, version, and exact relevant passage;
- qualified reviewer/owner and review date;
- status: `OPEN`, `EVIDENCE_COLLECTED`, `DECIDED`, `DEFERRED`, or `BLOCKED`;
- decision/condition, if any, with no secret or privileged body in Git;
- safe default while status is not `DECIDED`;
- linked tickets/ADRs/policy versions;
- re-review trigger and next review date;
- launch impact (`BLOCKER`, `SURFACE_BLOCKER`, or `NON_BLOCKING`).
  A row may be `DECIDED` only when the named qualified reviewer accepts the decision
and the owner accepts its product consequences. A generic search result, an
uncited note, or a test passing is never sufficient.

## Qualified questions

| ID | Question | Required evidence/decision | Owner/authority | Affected surfaces | Safe default while open | Launch impact |
|---|---|---|---|---|---|---|
| Q-306-01 (DP-301) | What editorial/publication role and wording apply to a claim-level `FACTUALLY_FALSE` assessment, and when is any additional notice required? | Written Italy/EU analysis with assumptions and approved wording | Qualified Italy/EU counsel + product owner | Findings, JSON-LD, API, UI, notices | Neutral claim-level wording; no intent language | BLOCKER |
| Q-306-02 (DP-301) | Can any intentionality/deception assessment ever be offered, and what evidence/review threshold would be required? | Explicit decision whether capability is prohibited, deferred, or conditionally permitted | Qualified Italy/EU counsel + product owner | Verifier, schema, all public copy | No intentionality assessment | BLOCKER |
| Q-306-03 (DP-302) | What notice, lawful basis, consent/identity, retention, and withdrawal rules apply to reply intake? | Written data/privacy analysis and intake notice | Privacy counsel + product owner | Intake, receipts, private store | Intake disabled or private-only operator path; no identity publication | BLOCKER |
| Q-306-04 (DP-302) | Do user submissions/replies create platform/UGC/intermediary or moderation obligations in the intended deployment? | Scope analysis and required notices/reporting/takedown controls | Qualified platform/editorial counsel | Intake, moderation, notices | Do not describe or operate as a public hosting service | BLOCKER |
| Q-306-05 (DP-302) | Which abuse signals, cookies/device data, logs, retention, and access rights are acceptable? | Privacy/security decision with data-flow and retention table | Privacy/security counsel + owner | Rate limits, logs, anti-abuse | Minimum data, no public intake until profile is approved | BLOCKER |
| Q-306-06 (DP-303) | What correction, retraction, notice, response, and appeal duties apply to each Finding type? | Written editorial/legal analysis and workflow decision | Editorial/qualified counsel + owner | Correction, takedown, appeal, notices | Private requests, append-only, no automated takedown | BLOCKER |
| Q-306-07 (DP-303) | What evidence, authority, independence, and disclosure are required for an appeal or takedown? | Role matrix, decision record, and public-notice rules | Owner + qualified counsel | Review queue, projection, audit | No appeal deadline/outcome promise; hold only through explicit review | BLOCKER |
| Q-306-08 (DP-304) | What roles, lawful bases, journalistic/public-interest conditions, notices, and data-subject rights apply to each data class? | GDPR/data-protection analysis tied to field inventory | Privacy counsel + owner | Ingestion, Person, public projection, API | Minimize and keep private; no public launch | BLOCKER |
| Q-306-09 (DP-304) | What special handling is required for sensitive data, allegations, criminal matters, minors, victims, and exact locations? | Class-specific decision and review procedure | Privacy/editorial counsel + owner | Claims, evidence, intake, public copy | Hold/quarantine; no inference or publication | BLOCKER |
| Q-306-10 (DP-304) | What retention, deletion, restriction, legal hold, and incident-notification rules apply? | Retention matrix, rights workflow, incident decision tree | Privacy/security counsel + owner | Storage, backups, rights requests, ops | Preserve required audit; no unapproved purge | BLOCKER |
| Q-306-11 (DP-305) | What quotation/excerpt rights, licenses, attribution, and source-specific permissions govern text, transcript, audio, and video? | Source-family rights matrix and counsel decision | IP/media counsel + owner | Transcript, excerpts, evidence, open data | No new/full public excerpt; links/metadata only | BLOCKER |
| Q-306-12 (DP-305) | Which platform/API terms, access controls, and scraping/data-acquisition restrictions apply? | Platform-by-platform source review and approved allowlist | IP/platform counsel + maintainer | Discovery, acquisition, source registry | Do not bypass or enable unresolved source | BLOCKER |
| Q-306-13 (DP-305) | What disclosure or representation is required for machine-generated transcripts and derived public data? | Written AI/media guidance and approved method copy | AI/IP counsel + owner | Method fields, API, JSON-LD, notices | Show only approved provenance; no accuracy claim | BLOCKER |
| Q-306-14 (cross-cutting) | What AI Act, DSA, ePrivacy/cookie, consumer, transparency, or platform-specific obligations apply to the chosen deployment? | Applicability analysis with deployment assumptions | Qualified technology/media counsel | Public site, intake, AI metadata, hosting | Do not claim compliance; block affected launch surface | BLOCKER |
| Q-306-15 (cross-cutting) | What terms, privacy notice, contact, complaint channel, security-incident process, and possible registration/insurance obligations apply? | Approved public-facing documents and operational ownership | Owner + qualified counsel | Website, intake, operations, launch | No public launch without an owned contact/runbook | BLOCKER |
| Q-306-16 (cross-cutting) | What material product/data/deployment changes invalidate a prior decision? | Re-review trigger policy and owner sign-off | Product owner + counsel | All M3/M4/M5 surfaces | Treat stale decisions as open and block affected surface | BLOCKER |

## Launch blockers
- **B-306-01:** DP-307 cannot start as accepted legal review until a qualified
  reviewer, scope, jurisdiction, and controlled evidence location are recorded.
- **B-306-02:** Every Q-306 row remains `OPEN`, `EVIDENCE_COLLECTED`, `DEFERRED`,
  or `BLOCKED` until the designated reviewer and owner accept a dated disposition.
- **B-306-03:** Any public launch claim is blocked while a `BLOCKER` row lacks an
  accepted decision, safe default, owner, and re-review trigger.
- **B-306-04:** A generic research link, disclaimer, automated test, or model answer
  cannot close a question.
- **B-306-05:** A material change to source, data class, deployment, model, public
  copy, or jurisdiction invalidates dependent decisions until re-review.
- **B-306-06:** Privileged advice, personal data, or secrets must remain in the
  controlled review store rather than Git or public output.

## Policy decisions
- **P-306-01 — No implicit closure:** an unanswered question retains `OPEN` or
  `BLOCKED`; absence of a recorded answer never means permission.
- **P-306-02 — Qualified authority:** only the designated qualified reviewer and
  product owner can mark a question `DECIDED`; agents and maintainers can organize
  evidence but cannot supply the legal conclusion.
- **P-306-03 — Safe default:** while a question is open, the least public,
  least inferential, most reversible behavior applies.
- **P-306-04 — Surface-level blocking:** a blocker may disable only the affected
  surface, but no public launch may claim the M3 milestone is closed while a
  `BLOCKER` row remains.
- **P-306-05 — Versioned evidence:** every decision has a date, jurisdiction,
  deployment assumption, policy version, and re-review trigger.
- **P-306-06 — No privileged payload in the repository:** a public ticket may link
  to a controlled review record/identifier, but must not paste confidential legal
  advice or personal data into Git.

## Engineering requirements
- **E-306-01 — Single register:** maintain a machine-readable or plainly table-driven
  register with the fields in the closure schema; every DP-301..DP-305 question has
  a stable cross-reference.
- **E-306-02 — Blocker propagation:** each `BLOCKER` row names the exact public
  surface and the safe fallback; release automation/docs must not mark M3 complete
  while a blocker is open.
- **E-306-03 — Evidence traceability:** each source has publisher, title/identifier,
  date, version, relevant section/passage, and the question it supports. Search
  snippets without a durable source do not close a row.
- **E-306-04 — Decision record:** each `DECIDED` row records the decision,
  assumptions, conditions, owner, reviewer, accepted policy version, affected
  tickets, and re-review trigger.
- **E-306-05 — Change invalidation:** a material change to deployment, source
  family, data class, public copy, model disclosure, hosting, or jurisdiction marks
  dependent rows stale/open.
- **E-306-06 — Handoff to DP-307:** produce a counsel-ready packet containing the
  register, open questions, safe defaults, affected surfaces, and requested
  decisions. Do not mark DP-307 complete from this ticket.
- **E-306-07 — Documentation gate:** all public notices, terms, privacy/security
  contact, rights workflow, and source policy placeholders are enumerated as
  deliverables or explicit blockers.

## Acceptance criteria
- [x] **AC-306.1:** Every DP-301..DP-305 qualified question maps to a unique Q-306
  row with a stable ID, jurisdiction/deployment context, affected surface, and safe
  default.
- [x] **AC-306.2:** Every row has an evidence requirement, owner/authority, status,
  decision/condition field, and re-review trigger; a missing field remains open.
- [x] **AC-306.3:** Only the designated qualified reviewer and product owner can
  mark a row `DECIDED`, with date, assumptions, conditions, and accepted policy
  version recorded.
- [x] **AC-306.4:** A `BLOCKER` row names the exact surface that cannot launch and
  the safe fallback while it is unresolved.
- [x] **AC-306.5:** Material product, data, source, deployment, model, or copy
  changes invalidate dependent decisions and reopen the affected rows.
- [x] **AC-306.6:** The counsel-ready handoff contains the register, evidence index,
  open questions, safe defaults, affected surfaces, and requested decisions without
  privileged content in Git.
- [x] **AC-306.7:** DP-307 is not marked accepted until every required disposition
  and owner/counsel sign-off is present.

## Validation/proof
- **Closure-register check:** verify unique question IDs, required fields, valid
  status values, source/date presence, and at least one affected surface/default per
  row.
- **Cross-reference check:** verify every DP-301..DP-305 qualified question maps to
  one or more Q-306 rows and every `BLOCKER` maps to an owner/decision request.
- **Repository checks:** `python3 -m compileall -q poc tests`,
  `PYTHONPATH=poc python3 -m unittest discover -s tests -v`,
  `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`, and
  `git diff --check`.
- **M3 packet check:** seven DP-301..DP-307 files pass the ticket completeness and
  collision check; unresolved legal questions remain visibly open.
- **No runtime claim:** this checklist does not prove production or legal
  compliance; MiniPC proof is required only for later implementation changes.

## Documentation/data/migration impact
- The closure register and evidence index are documentation/review artifacts; they
  must not contain privileged advice, secrets, or personal data.
- No database migration, source ingestion, public projection change, or production
  data mutation is part of this ticket.
- If a decision later changes runtime behavior, create an implementation ticket,
  additive migration if needed, tests, ADR where significant, and MiniPC proof.

## Completion receipt
  Completed as a research/control artifact on 2026-10-05. The closure register now
contains an explicit crosswalk for every DP-301..DP-305 qualified question and a
one-to-one decision-control metadata row for every Q-306 entry, including deployment
context, current decision condition, reviewer/review-date state, linked policy,
re-review trigger, and next-review state. The DP-307 handoff is therefore
structurally complete.

  This completion is **not legal clearance**. All 16 launch-sensitive rows remain
`OPEN` or `BLOCKED`, none is `DECIDED`, and public launch remains blocked. Qualified
Italy/EU legal review, dated dispositions, owner acceptance, and any resulting policy,
ADR, or runtime changes are external DP-307 work.

---

## Implementation receipt — research lane (2026-09-26)

Status: **register built and evidence collected for the EU instruments; 0 rows
DECIDED; public launch remains BLOCKED.**

### What was produced

- `docs/policy/legal-closure-register.md` — the closure register, the verified
  source index (S1–S5), the honest "explicitly NOT verified" table, the 16-row
  closure table, and the DP-307 handoff.

### What was actually retrieved and read (2026-09-26, EUR-Lex, official OJ texts)

Five instruments were fetched over HTTPS and their article/recital text was read
directly: GDPR (32016R0679), CDSM (32019L0790), InfoSoc (32001L0029), DSA
(32022R2065), AI Act (32024L1689). Each OJ identifier was confirmed from the
document header. Short verbatim fragments of the load-bearing provisions are
recorded in the register. See `legal-closure-register.md` for the exact URLs,
locators, and quotes.

Two factual corrections were found and are recorded, because getting them wrong
would misdirect counsel:

1. **GDPR Art. 2(2) does not exempt journalism.** Art. 2(2)(c) is the purely
   personal/household exclusion. The journalistic route is Art. 85 (Member-State
   reconciliation) plus Art. 9(2)(j)/Art. 89(1) (public-interest archiving
   conditioned on Union or Member State law).
2. **The public quotation/press exception is Directive 2001/29/EC Art. 5(3)**, not
   CDSM; CDSM Art. 3/4 are text-and-data-mining provisions.

### What is honestly UNVERIFIED (no conclusion asserted)

The authentic **Italian** consolidated text of the Codice della Privacy, the Italian
implementing law of GDPR Art. 85, any Garante measure, any AGCOM measure, and any
EDPB guidance were **not** read in this session. `normattiva.it` and
`gazzettaufficiale.it` returned HTTP 200 landing/shell pages whose article text is
rendered client-side; `garanteprivacy.it` and `agcom.it` returned only homepages. No
Italian article number and no regulator position is asserted anywhere. These are the
first work item for DP-307.

### Closure state

- 16 rows: **0 DECIDED, 0 CLOSED**, 14 `OPEN`, 2 `BLOCKED`, all 16 with `BLOCKER`
  launch impact.
- DP-301..DP-305 qualified questions are each mapped explicitly to exactly one
  controlling Q-306 row. Every Q-306 row has companion decision-control metadata
  covering deployment context, current decision condition, reviewer/review-date
  state, linked policy, re-review trigger, and next-review state, satisfying
  AC-306.1..AC-306.5.
- Applicability of the DSA/AI Act to the intended deployment is explicitly left
  **undecided** — locating an instrument is not deciding that it applies.

### What is NOT claimed

No legal advice, opinion, or compliance assurance; no lawful basis, retention
period, quotation right, platform permission, or regulator position is selected. No
privileged advice or personal data is in the repository. DP-307 is **not** marked
accepted; it cannot start until a qualified reviewer, scope, and controlled evidence
location are recorded (B-306-01).

### Control validation — 2026-10-05

`tests/test_legal_closure_register.py` verifies the documentation contract: all source
question IDs from DP-301..DP-305 occur exactly once in the crosswalk; all 16 Q-306 rows
have one companion metadata row; statuses remain in the allowed vocabulary; and the
register continues to contain zero `DECIDED` legal dispositions. The test deliberately
does not interpret law or substitute for DP-307 qualified review.
