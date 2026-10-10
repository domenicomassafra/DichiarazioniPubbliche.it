# DP-239 — Multilingual original and translation derivation in the private corpus

Status: FUTURE
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-210, DP-211, DP-221

## Problem

Corpus holds language and translation fields, but current `assess_translation` language risk rules cover only a small list; German is not validated by those heuristics. The owner wants sources in any language, with original exact words and visibly different Italian translations. German historical sources are a practical early adversarial sample.

## Outcome

Private text/ASR/document records retain immutable original-language spans; translation is a separately versioned derivative connected to the original source/hash, with documented language identification, uncertainty and an independently assessed meaning-risk result for each supported language pair. Unsupported languages remain discoverable and indexable as original-language material with explicit capability state.

## Traceability & constraints

R04/R09/R27, Q11/Q15; B owns substantive machine meaning assurance/authorization, C owns public dual-language presentation. A method labeled MACHINE must never be relabeled HUMAN_REVIEWED to pass old policy.

## Scope

Source-language detection + uncertainty, code-switch passages, original BCP-47 language and script, transcription/OCR normalization references, translation provider/model/prompt/version/hash + exact parent mapping, number/date/name/negation/modality/legal terms and quote-origin preservation. An original German text + machine IT translation is a **test pair**, not a guarantee of all languages; model/LLM entitlement and cost routed through D.

## Non-goals

Publicly substituting translated words for quote; asserting translations are legally licensed; claiming every language reliable; requiring a full-time human translator or switching providers without gate.

## Dependencies and sequencing

Hard corpus+wording existing DP; external source/derivative rights, soft B semantic assurance/authoritative states, C rendering and D runtime provider budget.

## Acceptance criteria


- [ ] `AC-239.1`: Original capture/Passage words, encoding, script, language, offset and hash remain recoverable while Italian translation resides in distinct derived record with method/model/version/source reference.
- [ ] `AC-239.2`: Frozen German→Italian adversarial matrix catches at least deliberate negation, number, date, subject, modality, quoted-vs-endorsed and judicial-status mismatches; report measured coverage/errors and holds, no self-certified truth.
- [ ] `AC-239.3`: Unknown/mixed language or unsupported risk rule remains explicit and cannot be silently assumed Italian or granted exact original-quote authority.
- [ ] `AC-239.4`: Translation cannot change the original selector's content hash and cannot reassign speaker/Person; altered source version invalidates affected translation confidence and triggers reevaluation.
- [ ] `AC-239.5`: Replay on same original and model/config is idempotent, changed translation stays a new version, and consumer can fetch original independently of derivative.
- [ ] `AC-239.6`: MiniPC real approved text pair passes source/translation/Passage readback with zero private-leak or unauthorized rights upgrade; B-specific meaning gate remains separate.

## Validation / proof

B-approved adversarial reference set and decision rubric, rights and language provenance, frozen model/config and pair hashes, cross-script numerals names negations, MiniPC negative+positive, D usage receipt if real provider invoked in future authorized phase.

## Documentation, data, and migration impact

Extend `wording_contract`/Corpus derivative seam after B designs automated meaning-assurance state; preserve old human-review historical events, no falsified reviewers. Public output solely through C filtered schema.

## Completion receipt

**NOT IMPLEMENTED — planning only**.
