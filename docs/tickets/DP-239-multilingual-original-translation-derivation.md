# DP-239 — Multilingual original and translation derivation in the private corpus

Status: IN PROGRESS
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

Planning-only note superseded by the limited 2026-10-11 receipt below.

## 2026-10-11 — Original and machine-translation private seam

Commit `aedced9` adds opt-in `multilingual_derivation.py` and focused tests.
The private original text, immutable Capture/Passage locator and source hash,
parser/version, speaker and BCP-47/script/code-switch identity remain distinct
from a versioned machine-translation artifact with provider/model/config
fingerprints and source bind. German-to-Italian **heuristic risk flags** hold
negation, date, number, actor, modality, legal status and reported-quotation
mismatches. Translation is never relabeled a human-reviewed original, and
even low-risk machine output remains `NEEDS_REVIEW` and without public quote
authority. 13 focused DP-239 cases plus 37 adjacent DP-221/237/238 cases PASS;
no real provider, source rights, local DB, publishing or MiniPC used. Original
AC remain unchecked pending an independently accepted multilingual reference
gold, actual source/translation rights, durable pipeline and host readback.

## 2026-10-11 — Targeted regression hardening (source-only, uncommitted)

The private recheck now compares the observed immutable locator fingerprint,
original source version, parser and charset binding **before** reporting a
newer current version as `STALE`. An independently valid alternate passage
with a changed locator and an unrelated newer-source hint must be `BLOCKED`
as `TRANSLATION_ORIGINAL_BINDING_CHANGED`; an unchanged original with a real
newer-source hint remains `STALE`.

The German→Italian lexical number guard now preserves negative signs and
decimal magnitude, including comma decimals, dot-grouped thousands and
percentage units. `-12` versus `12` and German `1.200` versus Italian
`12,00` trigger `NUMBER_MISMATCH`; `1.200` versus `1200` and `1,20`
versus `1,2` do not. Malformed or ambiguous grouping emits
`NUMBER_UNPARSED_OR_AMBIGUOUS` instead of silently stripping separators.
These lexical checks do not establish independently verified semantics.

Two additional regression methods bring DP-239 to 15 focused passing cases,
with red-before-green failure observed for both defects. Ruff and compilation
pass. The independent adversarial reference gold, source/language provenance,
actual original and derivative-use rights, durable original/translation
readback, provider receipt and MiniPC proof remain absent. No acceptance
criterion is marked complete on synthetic source-only evidence.

## 2026-10-11 — Independent original consumer retrieval and derivative replay

Added a substantial **read-only private consumer contract** in
`multilingual_derivation.py` rather than a new language-specific guess:
`ImmutableOriginalReadback`, `read_immutable_original_consumer`, and
`read_private_translation_consumer`. A caller supplies independently
retrieved Capture/Passage/locator/bytes/parser text (or a versioned media
segment), indexed by exact Passage ID, plus a **separate mandatory current
source-version hash indexed by Content ID**. The original can be read **without
having or accessing a translation**. The locator resolver checks persisted
selector coordinates, original quote bytes/hash, parser/capture or transcript
variant/speaker and version binding; altered or unavailable metadata fails
closed. A newer current source version is explicitly `STALE`, not silently
treated as current.

For a separately versioned MACHINE draft, the consumer rebuilds the whole
derivation from that *independently read* original. It requires exact equality
with the stored private artifact: deterministic derivation ID, translated
text/hash, model/config/prompt, original locator/source/charset, speaker,
source-language and code-switch spans, signals, wording/translation lineage,
method and review state. Fabricated `HUMAN_REVIEWED`, altered translation
bytes, swapped Person, changed quote selector or mismatched WordingReference
are rejected without returning original/translation text. A genuinely newer
source version preserves only the independently validated **private original
snapshot** in a `STALE` readback and suppresses the translation. An unchanged
original can be served privately with distinct immutable translation IDs for
different Italian text/config versions, without changing the original hash.

Four new focused regression methods cover retrieval without any derivative,
absent/new current versions, corrupt independent Passage/locator, nine forged
derivative fields, German/Italian code-switch with two independently replayed
Italian versions, and immutable media-transcript speaker/version readback.
**RED** before implementation: test collection could not import the missing
`ImmutableOriginalReadback` and consumer entry points. **GREEN**:
`tests.test_dp239_multilingual_derivation` **19/19 PASS**, with adjacent
DP-221, DP-237 and DP-238 suites **54/54 PASS** overall. Ruff lint, targeted
Python compilation and `git diff --check` PASS. Existing baseline source/test
have unrelated Ruff formatter suggestions; those lines were not mass-edited.

This is an **offline, caller-supplied** private readback/replay seam, not a
connected trusted Corpus repository, a language detector, a certified
translation, a rights grant, a qualified review or a public source quote. All
returned views keep `public_quote_eligible=False`; translation method stays
`MACHINE` and `translation_reviewed=False`. The caller must independently
authenticate source/parser provenance, rights/retention and live current hash.
Original **AC-239.1–6 remain unchecked**, ticket stays **IN PROGRESS**:
persisted/MiniPC real-source dual readback, accepted DE→IT independent
meaning-risk gold, exact derivative-use permissions, consumer integration,
rights revocation, owner/qualified B review and authorized provider/budget
receipts remain external before public activation.

## 2026-10-15 — German/Italian Unicode minus sign safety

**RED on the actual private translation builder:** The German source
`Anna zahlte −12 Euro.` (U+2212 mathematical minus) and Italian
`Anna ha pagato 12 euro.` incorrectly received **no** `NUMBER_MISMATCH`,
because the numeric lexer silently discarded U+2212. Conversely a faithful
Italian `-12` was incorrectly flagged as a different number. The same
fail-open occurred for `−12,5` versus `12,5` and `−12%` versus `12%`.
One synthetic original/derivative test produced **four failing subcases**
before the fix.

**GREEN source-only:** The German/Italian lexical guard now recognizes
U+2212 as a leading minus and normalizes it with ASCII `-` for the existing
conservative numeric magnitude, decimal and percent comparison. The test
requires three lost-sign mismatches plus one same-value no-mismatch control;
all remain private `HELD` drafts, with no source/translation authority or
publication permission. This is an additional negative regression relevant
to `AC-239.2`; it does not establish a measured independently annotated
multilingual meaning-risk matrix, corpus persistence, licensed derivative
use, exact consumer rights or authorized real-source MiniPC readback.

**DP-239 remains `IN PROGRESS`, with AC-239.1–6 unchecked.** The accepted
DE→IT gold/reference set, source/language identification and rights grants,
durable original/derivative pipeline and MiniPC consumer canary are still
required before full original acceptance.

**Local validation and host boundary:** Focused DP-239 plus stable
wording/DP-237/original-locator suites **59/59 PASS**. Ruff `check` on the
two changed Python files, Python compilation and owned `git diff --check`
PASS. A broader 82-test adjacent run included four concurrent DP-238 PDF
worker failures (`DOCUMENT_PDF_WORKER_UNAVAILABLE`); these occurred only in
the separately owned DP-238 tests, so no combined-suite PASS is claimed.
A read-only named `ssh minipc` check found
`/home/udodo/src/DichiarazioniPubbliche.it/poc/dichiarazioni_pubbliche/multilingual_derivation.py`
**absent**. No real source, approved translation, provider, rights record,
production database or live reader was accessed or modified. The source
repair is not installed on that host.
