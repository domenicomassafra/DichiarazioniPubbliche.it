# DP-432 — Public trust/provenance disclosure integration for Statement and Method

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-216..DP-223, DP-308, DP-427, DP-428

## Problem

The Statement and Method pages are already owned by DP-427/DP-428. The new Trust &
Evidence hardening must be surfaced publicly without reopening those completed/active page
ownership tickets or inventing a second trust UI. Readers need to understand what is an
exact quote, how the speaker was attributed, what source role was used, what was translated
or paraphrased, and why the system sometimes abstains.

## Outcome

Integrate the implemented safety contracts into the existing v4 Statement/Method grammar
using progressive disclosure and plain language. Public trust comes from inspectable
provenance, not confidence badges or "AI verified" marketing.

## Scope

- Statement page disclosure for wording type: original/verbatim, paraphrase, translation,
  reported quote where applicable.
- Show bounded original-source locator and source/capture date/version metadata allowed by
  public schema/rights policy.
- Show attribution method in human-readable form when useful (for example official record,
  reviewed source metadata, manually reviewed media span) without exposing internal notes.
- Show when a translation is present and provide the original-language wording/locator when
  rights/public schema allow it.
- Explain evidence roles/contextual authority: a first-party source can prove what someone
  said without proving the factual truth of what they said.
- Method page documents the fail-closed/abstention rule, source-span quote binding,
  non-biometric attribution, reported-speech separation, context review, source suitability,
  human review and correction propagation.
- Do not show internal confidence/source scores because those are not publication proof.

## Non-goals

- No new visual system or separate dashboard.
- No raw transcript/evidence/reviewer notes.
- No claim that the displayed method or a confidence label guarantees legal/factual truth.
- No reopening DP-428's completed document grammar; this ticket updates content/components
  through the already-approved grammar.

## Acceptance criteria

- [ ] **AC-432.1:** A reader can distinguish direct quote, paraphrase and translation from
  text/semantics, not color alone.
- [ ] **AC-432.2:** A public direct quote is displayed only when DP-216/DP-308 marks the
  underlying provenance eligible; UI never fabricates a fallback quote.
- [ ] **AC-432.3:** Reported speech cannot visually appear as the reported person's direct
  statement unless DP-219 original-source requirements are satisfied.
- [ ] **AC-432.4:** Attribution/source/time/context are retraceable from the Statement page
  without exposing private operational data.
- [ ] **AC-432.5:** Method clearly distinguishes occurrence proof from truth evidence and
  explains why first-party/official sources have bounded roles rather than universal trust.
- [ ] **AC-432.6:** Method explains abstention/hold behavior and human review honestly; no
  percentage confidence or "AI verified" badge is used as proof.
- [ ] **AC-432.7:** Correction history links through DP-431 and cannot leave stale wording
  in the current canonical view.
- [ ] **AC-432.8:** Desktop/mobile/keyboard/200%-zoom and public-schema compatibility tests
  pass with no provider/LLM request path.

## Validation / proof

Use synthetic projected fixtures for direct quote, paraphrase, translation, reported quote,
held/unresolved and corrected records. Run `web` checks/build plus public-projection/API
tests and screenshot/keyboard review.

## Documentation, data, and migration impact

Update Method copy and Statement provenance component contract only after upstream safety
contracts are implemented. No new operational data becomes public solely for this ticket.

## Completion receipt

Pending upstream Trust & Evidence implementation.
