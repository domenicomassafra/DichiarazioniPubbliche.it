# DP-221 — Original wording, paraphrase, summary and translation separation

Status: FUTURE  
Milestone: M2 — Live pipeline readiness and source coverage  
Depends on: DP-216; coordinate with DP-219, DP-220, DP-305

## Problem

A paraphrase or translation can be accurate while still not being the words a person
actually used. If derived wording is rendered with the same semantics as a direct quote,
the product can create a false quotation even though every underlying source is real.

This risk is especially high for translated speeches, article headlines, summaries,
machine-translated source material and editorially shortened statements.

## Outcome

Make wording type first-class. Every public textual representation is explicitly one of
`VERBATIM_ORIGINAL`, `PARAPHRASE`, `SUMMARY`, `TRANSLATION` or `REPORTED_QUOTE` (or an
equivalent frozen vocabulary), with provenance to the original occurrence and a clear
rendering contract.

## Scope

- Keep the DP-216 source-bound original as the only direct-quote authority.
- A paraphrase/summary stores its derivation method/version, author/reviewer and source
  occurrence IDs; it cannot carry direct-quote punctuation/structured-data semantics.
- A translation stores original language, target language, source occurrence, translation
  method/version and review state. The original remains retrievable/inspectable.
- Machine translation is private/reviewable by default for public quote-equivalent use;
  v1 public translation requires explicit review when meaning is material.
- Preserve names, numbers, negations, legal terms and modal language as high-risk tokens;
  divergence from the original requires review/hold.
- Search may index normalized/paraphrased representations, but result presentation must
  preserve wording type and never imply they are verbatim.
- JSON/JSON-LD/API must encode the distinction, not rely only on typography.

## Non-goals

- No universal translation-quality score.
- No automatic claim that a machine translation is authoritative.
- No destructive replacement of original-language text.
- No using paraphrase similarity as proof that two people said the same words.

## Acceptance criteria

- [ ] **AC-221.1:** Only `VERBATIM_ORIGINAL` can render as a direct quotation/public quote
  field without an explicit translation label.
- [ ] **AC-221.2:** Paraphrase and summary output cannot be serialized through the direct
  quote field in JSON, JSON-LD, HTML or API.
- [ ] **AC-221.3:** Translation always retains the original occurrence/language and a
  visible machine/human-reviewed status appropriate to the approved public schema.
- [ ] **AC-221.4:** A translation that changes a number, name, date, negation, legal term or
  modality is held by deterministic fixture tests.
- [ ] **AC-221.5:** Search/index normalization cannot erase wording type or create a direct
  quote from normalized text.
- [ ] **AC-221.6:** Reported quotes remain governed by DP-219 and cannot be upgraded to
  `VERBATIM_ORIGINAL` through translation/paraphrase processing.
- [ ] **AC-221.7:** Rights/private-body rules from DP-305 remain enforced for both original
  and derived text.
- [ ] **AC-221.8:** Full suite, schema/API compatibility checks and MiniPC canary pass.

## Validation / proof

Fixtures must include original Italian, foreign-language speech, machine translation,
human-reviewed translation, headline paraphrase, editorial summary and deliberate
negation/number translation errors. Test every serializer and search projection.

## Documentation, data, and migration impact

Add a small versioned wording/derivation contract rather than duplicating Statement or
Atomic Claim models. Public schema changes require DP-105/DP-403 compatibility updates.

## Completion receipt

Pending DP-216 and implementation.

