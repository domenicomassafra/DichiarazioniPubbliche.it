# DP-220 — Context integrity and semantic-clipping guard

Status: FUTURE  
Milestone: M2 — Live pipeline readiness and source coverage  
Depends on: DP-216, DP-217, DP-219

## Problem

An exact quotation can still be misleading if it is clipped from the question, conditional,
negation, interrupted sentence, immediately adjacent qualification, or quoted material that
changes its meaning. Exact text alone therefore does not establish that a bounded excerpt is
a fair representation of the source occurrence.

The product needs an inspectable context-integrity decision before a quotation or statement
can become a public canonical occurrence.

## Outcome

Create a deterministic/reviewable context-integrity layer that preserves the surrounding
source structure and blocks publication when omission or clipping materially changes what
the source says. Automation may raise risk signals; only explicit rules/review can clear
ambiguous cases.

## Scope

- Bind each public Statement occurrence to a bounded context window or structural parent
  sufficient to inspect the original exchange.
- Preserve question/answer linkage when available, speaker turns, sentence/paragraph
  boundaries, interruptions, adjacent qualifications and discontinuous excerpt markers.
- Add risk signals for at least: negation, conditional/hypothetical language, quotation
  nesting, antecedent-dependent pronouns, incomplete sentence, cross-talk, answer without
  its question, immediate correction/qualification, sarcasm/irony uncertainty and edited
  montage boundaries.
- Signals are not verdicts. `NEEDS_CONTEXT_REVIEW` remains a hold until cleared.
- A reviewer may approve the bounded excerpt, expand its context, reclassify it as
  paraphrase/summary, or reject it. The decision records the exact source/span version.
- A later source/transcript/version change invalidates context approval for affected spans.
- Public UX may show a concise original-context link/locator while keeping raw transcript
  bodies private under DP-305.

## Non-goals

- No claim that software can perfectly detect sarcasm, rhetoric or speaker intent.
- No automatic intent/deception inference.
- No requirement to publish a whole transcript or article around every statement.
- No free-form LLM judgment as the sole context-approval authority.

## Acceptance criteria

- [ ] **AC-220.1:** Every public direct quotation/statement occurrence has a recorded
  context-integrity state tied to the exact source/span version.
- [ ] **AC-220.2:** A fixture where removing `non` reverses meaning is blocked even if the
  remaining words form a grammatically plausible quote.
- [ ] **AC-220.3:** A yes/no answer whose meaning depends on the preceding question retains
  the question link or remains held.
- [ ] **AC-220.4:** Conditional/hypothetical and immediate-qualification fixtures cannot be
  flattened into unconditional public assertions without review.
- [ ] **AC-220.5:** Discontinuous excerpts disclose every omission and cannot concatenate
  clauses across a source boundary invisibly.
- [ ] **AC-220.6:** Cross-talk/interruption/montage boundaries preserve distinct speakers
  and source spans; one speaker cannot inherit another speaker's surrounding context.
- [ ] **AC-220.7:** A reviewer decision is append-only/versioned and becomes stale when any
  covered source/transcript/span hash changes.
- [ ] **AC-220.8:** Public context metadata is bounded and does not leak raw private bodies.
- [ ] **AC-220.9:** Adversarial context fixtures produce zero known misleading public
  excerpts; uncertainty results in under-publication rather than a guessed clearance.
- [ ] **AC-220.10:** Full suite, benchmark and MiniPC canary pass.

## Validation / proof

Maintain a reviewed fixture set covering negation, conditionals, Q/A dependency, pronouns,
immediate correction, interrupted speech, sarcasm uncertainty, montage and discontinuous
excerpting. Run standard checks and MiniPC read-back of context state + source hashes.

## Documentation, data, and migration impact

Add only the minimum versioned context metadata/review seam required to make the gate
replayable. Update `CONTEXT.md`/`ARCHITECTURE.md` after the contract is implemented; keep
rights/public-body policy in DP-305.

## Completion receipt

Pending prerequisites and implementation.

