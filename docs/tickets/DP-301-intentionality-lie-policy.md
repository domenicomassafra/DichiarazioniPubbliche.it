# DP-301 — Intentionality and “lie” policy

Status: IN PROGRESS

Milestone: M3

Depends on: M0 baseline; coordinate with DP-103, DP-104, and DP-105

Launch state: BLOCKED until DP-306 and DP-307 close the qualified legal questions

This is a product and engineering policy specification, not legal advice. Questions
marked **Qualified** require a decision by the owner and qualified Italy/EU counsel;
they are not answered by this ticket.

## Problem
  The runtime already distinguishes factual verification, review, and publication, and
its assessment vocabulary does not contain a finding for intentional deception. The
product still needs a durable editorial and public-projection contract so that a
contradiction, a changed position, or a false factual claim cannot be rendered as
proof that a person lied or acted maliciously. That contract must also prevent a
future model, reviewer, UI, or API from introducing a person-level reliability score.

## Outcome
  Define and test a versioned policy boundary in which public findings may describe a
bounded factual assessment and its evidence, but do not infer intent, knowledge,
deception, or dishonesty. Unsupported or legally unresolved intentionality language
is held or escalated for qualified review rather than silently translated into a
public label.

## Scope
- Define the allowed assessment, claim-type, relation, rationale, and public-copy
  vocabulary for intentionality.
- Specify deterministic and review-layer behavior when a prompt, extraction, relation,
  correction, or reply contains intentionality language.
- Specify public projection, JSON-LD, API, UI-copy, and audit requirements for the
  policy.
- Define tests and evidence for policy drift, stale reviews, future evidence, and
  contradiction/position-change cases.
- Carry unresolved legal/editorial questions into DP-306 and DP-307.

## Non-goals
- Making a legal determination about whether a person lied, defamed, or acted in
  bad faith.
- Adding a new runtime assessment, database enum, model, provider, or public ranking.
- Inferring intent from tone, contradiction, omission, source disagreement, or a
  model confidence value.
- Changing the existing reply/correction lifecycle.
- Providing legal advice or representing this ticket as legal review.

## Current baseline
- `verification_run.assessment` is a factual assessment vocabulary such as
  `SUPPORTED`, `FACTUALLY_FALSE`, `OUTDATED_DATA`, `INSUFFICIENT_EVIDENCE`, and
  `UNRESOLVED`.
- `FACTUALLY_FALSE` is a claim-level assessment, not a statement about a speaker's
  state of mind.
- `claim_relation_candidate` includes relation candidates such as
  `POSITION_CHANGE_CANDIDATE` and `CONTRADICTION_CANDIDATE`; these are not intent
  findings.
- The public projection is allowlist-based and must not emit numeric ratings or
  reliability fields.
- A reply or correction can trigger re-analysis, but cannot directly rewrite a
  finding.

## Constitution and non-negotiable constraints
- **C-301-01 — No intent inference:** contradiction, position change, and factual
  falsity do not imply deception, knowledge, or intent.
- **C-301-02 — No person score:** no person-level truth, reliability, trust,
  ideology, competence, or fitness score may be created, displayed, or inferred.
- **C-301-03 — Separate stages:** retrieval, approval, verification, finding
  review, and publication remain distinct and append-only at their review seams.
- **C-301-04 — Fail closed:** missing, stale, ambiguous, or unsupported provenance
  causes a hold or omission, never a weaker automatic intent conclusion.
- **C-301-05 — Time-bounded reasoning:** evidence after the statement date cannot
  be used to judge what was knowable then unless the finding explicitly evaluates a
  later outcome.
- **C-301-06 — Public allowlist:** the public projection exposes bounded provenance
  identifiers and approved assessment text, not raw transcript, evidence body, or
  hidden intent scores.

## Policy decisions

| ID | Decision | State |
|---|---|---|
| P-301-01 | The v1 public vocabulary contains no `LIE`, `DELIBERATE_FALSEHOOD`, `DECEIVED`, `DISHONEST`, or equivalent intentionality assessment. | Accepted product invariant |
| P-301-02 | `FACTUALLY_FALSE` means only that the claim is sufficiently contradicted by the approved, time-bounded evidence set under the named verification rule. | Accepted product invariant |
| P-301-03 | A contradiction or position-change relation is descriptive context; it never carries an intent conclusion. | Accepted product invariant |
| P-301-04 | `OUTDATED_DATA` is reserved for information that became relevant after the statement date; it is not a synonym for a lie. | Accepted product invariant |
| P-301-05 | User- or reviewer-supplied intentionality language is treated as untrusted text: retain it privately only when needed for review, and do not promote it to a finding label. | Safe product default |
| P-301-06 | Public copy must use neutral, claim-level wording and identify limitations and evidence scope. | Safe product default; editorial wording awaits DP-306/DP-307 |
| P-301-07 | No intentionality capability is added in v1. Any future proposal requires a new ADR, qualified review, and migration/public-schema decision. | Future gate |

## Engineering requirements
- **E-301-01 — Versioned vocabulary:** publish one policy-versioned mapping for
  claim type, verification assessment, rationale code, relation type, and public
  wording. Reject unknown values at the review/projection boundary.
- **E-301-02 — Deterministic verifier:** the verifier may emit only the supported
  claim-level assessment enum. A request to score intent, deception, honesty, or
  person reliability must be rejected or held with a machine-readable policy error;
  it must not be approximated by a different label.
- **E-301-03 — Evidence contract:** every publishable `FACTUALLY_FALSE` finding must
  retain the verification rule/version, statement cutoff, approved evidence IDs,
  approved observation IDs, limitations, and a review event. Missing any of these
  causes omission.
- **E-301-04 — Relation separation:** relation candidates and approved relations
  retain their own IDs, types, review events, and publication status. No relation
  serializer may add an intent or accusation field.
- **E-301-05 — Re-analysis:** approved evidence changes, reply/correction
  processing, and approved relation changes create the existing explicit trigger;
  no trigger performs a direct intent inference or publication transition.
- **E-301-06 — Public projection allowlist:** JSON, JSON-LD, HTML, and any later API
  serializer reject or omit intent, deception, lie, dishonesty, reliability, trust,
  and numeric rating fields, even if a tampered operational row contains them.
- **E-301-07 — Review freshness:** a finding review is stale when its policy version,
  verification input fingerprint, claim/segment provenance, evidence set, or
  statement cutoff changes. A stale review cannot authorize public output.
- **E-301-08 — Auditability:** policy rejection/hold events record the reason code,
  policy version, actor, and input IDs without copying sensitive raw text into logs.
- **E-301-09 — Content safety:** editorial templates, notifications, and search
  indexing use the same vocabulary and reject unsupported labels rather than
  silently rendering them.

## Qualified questions
  These are intentionally open and are carried into DP-306:

| ID | Question for the owner/counsel | Why it matters | Until answered |
|---|---|---|---|
| Q-301-01 | What editorial role and public wording, if any, may the service use for a factually false claim in Italy/EU? | Determines whether the neutral assessment is sufficient and what disclosures are required. | Keep the assessment neutral; no intentionality language. |
| Q-301-02 | Is any future intentionality assessment permissible, and what evidence, attribution, and review threshold would be required? | Determines whether a future capability can exist at all. | Do not implement an intentionality assessment. |
| Q-301-03 | What correction, reply, and notice obligations attach to a published factual assessment? | Affects lifecycle copy and reviewer workflow. | Use the existing append-only reply/correction gates; obtain legal sign-off. |
| Q-301-04 | Does the deployment model, audience, or use of automated extraction create any additional disclosure or editorial obligations? | May change public labeling and process requirements. | Treat disclosure requirements as unresolved and block launch. |

## Launch blockers
- **B-301-01:** DP-306 has not produced a reviewed decision for the applicable
  jurisdiction and publication model.
- **B-301-02:** DP-307 qualified review has not accepted the policy and wording.
- **B-301-03:** Any implementation, fixture, or public artifact that introduces
  intentionality, deception, or person-score semantics.
- **B-301-04:** A public projection that can emit a stale or unreviewed assessment.
- **B-301-05:** A claim-level assessment whose evidence, observation, cutoff, or
  review provenance cannot be inspected.

## Acceptance criteria
- [x] **AC-301.1:** The policy registry has an explicit, versioned allowlist and
  rejects every intentionality/person-score label in deterministic, review, and
  projection paths.
- [x] **AC-301.2:** A `FACTUALLY_FALSE` fixture with complete approved evidence and
  a valid statement cutoff projects as a claim-level assessment and contains no
  intent or numeric rating field.
- [x] **AC-301.3:** A contradiction or position-change fixture projects only its
  relation type and provenance; no serializer or copy adds an accusation.
- [x] **AC-301.4:** A future-evidence fixture is rejected when the verification
  cutoff precedes that evidence, unless the fixture explicitly evaluates a later
  outcome.
- [x] **AC-301.5:** Tampering with a review timestamp, policy version, evidence set,
  or observation set makes the dossier non-projectable until a new review exists.
- [x] **AC-301.6:** Reply, correction, and relation triggers re-run the named
  verification path without directly changing a finding or inventing intent.
- [x] **AC-301.7:** Policy tests cover unsupported labels, model-output drift,
  stale review, ambiguous evidence, and public JSON/JSON-LD field allowlisting.
- [ ] **AC-301.8:** DP-306 records the qualified questions and DP-307 records the
  resulting owner/counsel decision before any public-launch use.

## Validation/proof
- **Focused policy proof:** table-driven tests for the vocabulary, relation mapping,
  cutoff rule, stale-review omission, and projection allowlist.
- **Repository checks:** `python3 -m compileall -q poc tests`,
  `PYTHONPATH=poc python3 -m unittest discover -s tests -v`,
  `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`, and
  `git diff --check`.
- **Runtime proof:** if runtime/publication code changes, run the same checks on
  the MiniPC mirror and inspect the generated public bundle. This ticket alone does
  not authorize deployment.
- **M3 packet check:** verify that the questions, blockers, and policy version are
  linked to DP-306 and DP-307.

## Documentation/data/migration impact
- Add the policy version and vocabulary documentation in the implementing ticket;
  do not change the current schema solely to store a new intent label.
- If a future decision requires a new assessment, relation, or public field, create
  an additive migration, compatibility plan, fixtures, and ADR first.
- No production data migration or public bundle regeneration is part of this
  specification-only change.

## Completion receipt
  Pending implementation, tests, MiniPC proof where applicable, and qualified legal
closure. No code, legal conclusion, or launch approval is claimed here.

---

## Implementation receipt — policy lane (2026-09-26)

Status: **engineering side implemented; legal closure still BLOCKING.**

### What was implemented

- `poc/dichiarazioni_pubbliche/policy/intent_policy.py` (new, pure/zero-I/O):
  `AssessmentIntent` (closed, claim-level only, no intent member);
  `PUBLIC_INTENT_PROHIBITED_TERMS` (strict superset of
  `relation_policy.PROHIBITED_INTENT_TERMS`, extended with the terms the
  invariant's own prose uses plus Italian families); `scan_public_label()`;
  `classify_text_intent_risk()`; `relation_to_assessment()` (returns `None` for
  every relation, the machine-checkable form of C-301-01); `assess_publishability()`
  fail-closed conjunction.
- `docs/policy/dp-301-intentionality-policy.md` (owner-reviewable policy doc).
- `tests/test_policy_intent.py` (34 tests).

### How the hard rule is now proven, not asserted

- `relation_to_assessment(CONTRADICTION_CANDIDATE) is None` and the same for
  `POSITION_CHANGE_CANDIDATE` — contradiction/position-change can never yield an
  assessment or intent.
- No public enum member (AssessmentIntent, VerificationAssessment,
  FindingPublicationStatus, RelationCandidateType) passes the intent/score label
  scan. `assert_no_intent_member()` runs at import, so adding a bad label breaks an
  import, not just a test.
- A complete-evidence `FACTUALLY_FALSE` finding is publishable; the *same* finding
  with a public label like "proved a deliberate lie" is blocked with
  `INTENT_LANGUAGE_IN_LABEL`. This is the AC-301.2 boundary in code.
- Future evidence without an explicit later-outcome scope is blocked
  (`FUTURE_EVIDENCE_USED`) — AC-301.4.

### What is NOT claimed

- No legal conclusion about permissible Italian/EU wording (Q-306-01/02 `OPEN`).
- No change to `verification_runtime`, `public_schema`, or any DB enum; the existing
  `FACTUALLY_FALSE` assessment is untouched.
- MiniPC runtime proof is not part of this change (pure policy modules, no runtime
  wiring); no deployment is authorized.

Repository checks run: `compileall` OK; full suite green (515 tests);
`git diff --check` clean. M3 remains blocked on DP-306/DP-307.

Final engineering-truth audit at clean HEAD `5a86666b` (2026-10-06): AC-301.1 through
AC-301.7 are closed by the current policy/relation/effective-time/re-analysis/public-projection
proof. The clean-HEAD M3 boundary is 523/523 PASS and the complete suite is 1720/1720 PASS.
AC-301.8 remains open: DP-306 records the questions, but no Q-306 row has a qualified
disposition and DP-307 has no accepted owner/counsel decision. No legal conclusion or launch
approval is inferred from the engineering proof.

2026-10-10 primary-source review: [GDPR Regulation 2016/679](https://eur-lex.europa.eu/legal-content/IT-EN/TXT/?uri=CELEX%3A32016R0679)
and the [Garante register guidance](https://www.garanteprivacy.it/home/faq/registro-delle-attivita-di-trattamento)
reinforce the need to document purpose, data processing, and accountable
decisions. They do not authorize a public allegation of intentional deception
or provide DP-307's qualified Italy/EU editorial decision. The Q-306-01 and
Q-306-02 entries remain `OPEN`, the policy still prohibits intent inference,
and **AC-301.8 remains unchecked**.

### 2026-10-10 — Unicode-format bypass of intent/public-score vocabulary

The shared public-label guard previously removed accents but retained invisible
Unicode format controls (`Cf`), including zero-width spaces/joiners, soft
hyphens and directionality marks. Inserting such a character into an otherwise
explicitly prohibited intent or person-ranking word made the deterministic scan
accept it. A RED test reproduced six such labels; `normalize_label()` now removes
invisible formatting before the existing token checks. This is an additional
engineering safeguard for machine-generated/reviewer-entered public copy, not
a new classification or inference about someone's intentions. **AC-301.8
remains open** until qualified DP-306/307 decisions exist; no launch permission,
person verdict or legal interpretation is granted by this change.
