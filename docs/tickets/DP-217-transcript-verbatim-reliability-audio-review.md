# DP-217 — Transcript reliability tiers and audio-to-verbatim review gate

Status: READY
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-204/DP-207 where their live lanes apply; deterministic fixture path may proceed; coordinate with DP-216

## Problem

A quotation can be perfectly bound to a transcript and still be wrong if the transcript
is wrong. Existing transcript reconciliation already holds disagreements around sensitive
tokens such as numbers and negations, but public verbatim wording needs a stronger,
explicit answer to: **what evidence establishes that these are the words actually spoken?**

Single-ASR output, platform captions and a canonical transcript are useful research
artifacts; none should silently become an authoritative public quotation.

## Outcome

Define a versioned transcript-evidence and verbatim-eligibility contract. Public media
quotes are allowed only from an approved source whose exact span has adequate evidence.
When no authoritative/official transcript exists, the conservative v1 path requires a
human audio review of the exact quoted span before it can be represented as verbatim.

## Scope

- Preserve existing Transcript Variant and Canonical Segment contracts.
- Add an inspectable transcript-evidence level/method to the span/review layer, for
  example `OFFICIAL_TRANSCRIPT`, `HUMAN_AUDIO_VERIFIED`, `PLATFORM_CAPTION`,
  `MULTI_ASR_AGREEMENT`, `SINGLE_ASR`, `UNVERIFIED`.
- The vocabulary describes evidence provenance, not an accuracy percentage.
- Define `VERBATIM_ELIGIBLE` as an explicit reviewed state, never inferred from model
  confidence or provider brand.
- For v1, `OFFICIAL_TRANSCRIPT` still requires source identity/version validation;
  non-official machine transcripts require human listening for any span projected as a
  direct quote.
- Keep existing secondary-ASR/sensitive-token reconciliation as a **triage/hold signal**;
  agreement between two models does not substitute for the human/verifiable-source gate.
- Audio review records exact start/end, transcript version/hash, reviewer, decision,
  corrected source-faithful text when needed, and reason codes without overwriting the
  original transcript variant.
- Changes to names, numbers, dates, negations, legal terms or other configured sensitive
  tokens invalidate downstream quote approval until reviewed again.

## Non-goals

- No universal ASR accuracy score.
- No assumption that platform captions are official merely because a platform serves them.
- No voiceprint/face identification.
- No public full transcript.
- No automatic publication after human transcript review.

## Acceptance criteria

- [ ] **AC-217.1:** Transcript/source spans carry an explicit evidence method/state and a
  direct quote cannot be public merely because `canonical_transcript` exists.
- [ ] **AC-217.2:** `SINGLE_ASR`, `PLATFORM_CAPTION` and unreviewed `MULTI_ASR_AGREEMENT`
  are not v1 public-verbatim authority.
- [ ] **AC-217.3:** A non-official span becomes verbatim-eligible only after a human review
  tied to the exact audio/time range and immutable transcript/source version.
- [ ] **AC-217.4:** Fixtures for dropped negation, changed number, wrong surname, homophone,
  punctuation ambiguity and overlapping speech remain held until source-faithful review.
- [ ] **AC-217.5:** Reviewer correction creates a derived reviewed representation and
  preserves the original provider/platform variant and hash.
- [ ] **AC-217.6:** Any later transcript/source-version change stales the approval and
  blocks projection until re-review.
- [ ] **AC-217.7:** Public method metadata can distinguish official/human-verified/machine
  provenance without exposing provider prompts, raw transcript bodies or accuracy hype.
- [ ] **AC-217.8:** Deterministic fixture, full suite, benchmark and MiniPC canary prove the
  publication gate with zero live-provider substitution.

## Validation / proof

Use synthetic/cleared audio fixtures containing numbers, dates, negations, names,
cross-talk and low-confidence spans. Prove both positive human-reviewed and negative
unreviewed paths. Run standard Python/full-suite/benchmark checks, migration replay if
needed, `git diff --check`, and MiniPC read-back. DP-204 live provider proof remains a
separate external dependency and must not be fabricated.

## Documentation, data, and migration impact

Update transcript policy/domain docs only after vocabulary is implemented. Reuse review
ledger and transcript versioning. Any new review table/fields must be additive and must not
turn a human-corrected transcript into a destructive rewrite of provider evidence.

## Completion receipt

Pending implementation and MiniPC proof.
