# DP-309 — High-risk assertion and legal-status escalation gate

Status: FUTURE  
Milestone: M3 — Editorial, correction, privacy, and legal policy  
Depends on: DP-215, DP-304, DP-306; DP-307 required for final launch decisions; DP-308

Launch state: BLOCKED for final public enablement until applicable DP-306/DP-307 decisions
are accepted. Conservative hold logic may be implemented and tested before then.

## Problem

Some wording errors are disproportionately harmful: confusing investigation/prosecution/
conviction status, attributing criminal conduct to the wrong person, publishing a sensitive
private allegation, or turning a source's allegation into the site's asserted fact.

The product needs a technical escalation boundary so these cases cannot travel through the
ordinary low-risk publication lane merely because generic provenance is present.

## Outcome

Define a versioned high-risk assertion profile that detects/records risk classes and
requires stronger evidence/review conditions or a fail-closed hold. It does not decide the
law; qualified questions remain in DP-306/DP-307.

## Scope

- Define bounded risk classes for at least:
  - criminal/procedural status terminology;
  - allegation of criminal or seriously wrongful conduct;
  - identity-sensitive accusation;
  - health/private/sensitive-person information already governed by DP-304;
  - minors/victims/private incidental persons where DP-304 requires special handling;
  - legal-status claims whose precise term/date/jurisdiction is material.
- Classifiers/signals are triage only. A hit can escalate/hold; a non-hit cannot certify
  safety.
- Legal/procedural terms require a DP-215 requirement profile with the appropriate official
  record, jurisdiction, effective date/status and temporal match.
- Preserve source framing: allegation, charge, investigation, prosecution, conviction,
  acquittal/dismissal or other states must not be normalized into one another.
- A source saying "X alleges Y" does not authorize the product to state Y as fact.
- Require explicit human review and the DP-310 separation rule for `HIGH/LEGAL` cases once
  enabled by policy.
- Any unresolved identity/procedural status produces `HOLD_HIGH_RISK`, not a softer label.

## Non-goals

- No autonomous legal conclusion.
- No inference about guilt, innocence, character, intent or fitness.
- No sensitive-trait inference from unrelated evidence.
- No model confidence threshold that clears a high-risk assertion.

## Acceptance criteria

- [ ] **AC-309.1:** High-risk state is explicit/versioned and can only add restrictions;
  absence of a detected token never becomes a safety certification.
- [ ] **AC-309.2:** Fixtures distinguish material procedural/legal terms without silently
  mapping them to one generic status.
- [ ] **AC-309.3:** A legal-status Finding cannot run/publish without the DP-215 official
  record/scope/time requirements selected by the accepted policy.
- [ ] **AC-309.4:** "Source alleges X" remains attributed allegation/reporting context and
  cannot become an unqualified product assertion through normalization.
- [ ] **AC-309.5:** Wrong-person/same-name high-risk fixtures remain held through DP-222.
- [ ] **AC-309.6:** Sensitive/private/minor/victim cases inherit DP-304 minimization/hold
  rules and cannot be cleared by this ticket alone.
- [ ] **AC-309.7:** Every `HIGH/LEGAL` public candidate has an explicit reviewed evidence
  packet and DP-310 review separation, or stays non-public.
- [ ] **AC-309.8:** Qualified-policy rows remain linked to DP-306/DP-307 and a code/test pass
  cannot mark them legally `DECIDED`.
- [ ] **AC-309.9:** Public serializers never expose internal risk scores/notes.
- [ ] **AC-309.10:** Full regression + DP-223 + MiniPC canary pass.

## Validation / proof

Use synthetic legal/procedural fixtures with deliberately wrong terms, dates, jurisdictions,
people and source framing. Prove safe holds before qualified review and exact policy-driven
behavior after accepted decisions. Run standard checks and MiniPC read-back.

## Documentation, data, and migration impact

Record qualified questions/decisions only through DP-306/DP-307. Implementation may add
versioned risk/escalation metadata and requirement-profile links, but no legal opinion or
privileged material belongs in Git.

## Completion receipt

Pending DP-306/DP-307 policy closure and implementation.

