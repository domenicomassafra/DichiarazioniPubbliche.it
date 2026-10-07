# DP-220 — Context integrity and semantic-clipping guard

Status: DONE
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

- [x] **AC-220.1:** New candidate/promotion paths carry a versioned context-integrity state with source/quote/context hashes and offsets, and promotion/finding/public gates require CLEAR_AUTOMATIC or APPROVED_CURATED; every public direct quotation/statement occurrence has a recorded
  context-integrity state tied to the exact source/span version.
- [x] **AC-220.2:** A deterministic fixture where removing `non` reverses meaning is held by NEGATION_NEAR_BOUNDARY_OMITTED even if the
  remaining words form a grammatically plausible quote.
- [x] **AC-220.3:** A yes/no answer whose meaning depends on the preceding question remains NEEDS_CONTEXT_REVIEW via ANSWER_REQUIRES_QUESTION_CONTEXT until a reviewed context decision retains
  the question link or remains held.
- [x] **AC-220.4:** Conditional/hypothetical and immediate-qualification fixtures are held by explicit signal codes and cannot be
  flattened into unconditional public assertions without review.
- [x] **AC-220.5:** Discontinuous excerpts disclose every omission and cannot concatenate
  clauses across a source boundary invisibly.
- [x] **AC-220.6:** Cross-talk/interruption/montage boundaries preserve distinct speakers
  and source spans; one speaker cannot inherit another speaker's surrounding context.
- [x] **AC-220.7:** A reviewer decision is append-only/versioned and becomes stale when any
  covered source/transcript/span hash changes.
- [x] **AC-220.8:** Context metadata is bounded to hashes, offsets, state/version and signal codes; raw surrounding source text is not persisted in the context decision or projected publicly.
- [x] **AC-220.9:** Adversarial context fixtures produce zero known misleading public
  excerpts; uncertainty results in under-publication rather than a guessed clearance.
- [x] **AC-220.10:** Full suite, benchmark and MiniPC canary pass.

## Validation / proof

Maintain a reviewed fixture set covering negation, conditionals, Q/A dependency, pronouns,
immediate correction, interrupted speech, sarcasm uncertainty, montage and discontinuous
excerpting. Run standard checks and MiniPC read-back of context state + source hashes.

## Documentation, data, and migration impact

Add only the minimum versioned context metadata/review seam required to make the gate
replayable. Update `CONTEXT.md`/`ARCHITECTURE.md` after the contract is implemented; keep
rights/public-body policy in DP-305.

## Completion receipt

First fail-closed context-integrity layer implemented 2026-10-05. The extractor binds context decisions to the exact source hash, quote hash/range and bounded context-window hash; deterministic risk signals cover negation near a clipping boundary, conditional/hypothetical wording, short Q/A-dependent answers, immediate qualifications, ellipsis/omission markers, dependent pronouns and incomplete boundaries. Candidate promotion, all promotion mutation SQL, finding publication and public projection require CLEAR_AUTOMATIC or APPROVED_CURATED. On 2026-10-06 the private `context_integrity_review_event` ledger added append-only/versioned review provenance bound to source/quote/context hashes and all covered offsets. Freshness fails closed on any binding change, and the ledger stores no surrounding raw source text.

The final local closure pass adds a structured multi-span context receipt. It hashes each
source span, records an explicit omission count, always returns `NEEDS_CONTEXT_REVIEW`, and
adds `CROSS_TALK_OR_SPEAKER_BOUNDARY` / `MONTAGE_OR_SOURCE_BOUNDARY` when speaker or source
part changes across spans; no raw surrounding text is retained. Focused tests prove source
ordering and no neighboring-context inheritance. The 2026-10-06 finalization wires an
approved same-speaker/same-source-part structured receipt into public wording metadata as
hashes + ordered offsets + `omission_count`; HTML and JSON-LD render the canonical ` […] `
marker, while the private omitted/source text never enters the public payload. A structured
receipt that crosses speaker or source-part/montage boundaries is omitted even if its state
is manually changed to `APPROVED_CURATED`, preventing neighboring-context inheritance.

The offline adversarial gate remains fail closed after the structured-context additions:
59/59 cases pass with `context_review_escape_count=0`, while discontinuous/cross-speaker/
cross-source-part focused cases return `NEEDS_CONTEXT_REVIEW` rather than guessed clearance.

The isolated candidate passes compileall, **1765/1765** full unittests, benchmark **5/5**,
DP-223 **59/59** and `git diff --check`; all **41** migrations apply/replay on disposable
PostgreSQL 17.11. MiniPC `/tmp` validation passes **213/213** focused tests and both
benchmarks against temporary PostgreSQL 18.6 clusters, with no production DB or provider
access.

2026-10-07 regression closure binds the public discontinuous-excerpt disclosure back to
the canonical private `context-integrity-v1` receipt at projection time. The projection
recomputes the receipt binding with the same helper used during assessment and omits the
finding when an offset, per-span hash or stored binding is stale. A regression that mutates
the second span offset while retaining the old binding is held fail closed. The focused
context/projection/public-schema set passes **91/91** and `git diff --check` passes.
