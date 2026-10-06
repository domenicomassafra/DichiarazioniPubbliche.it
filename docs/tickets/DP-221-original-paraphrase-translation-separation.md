# DP-221 — Original wording, paraphrase, summary and translation separation

Status: DONE
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

- [x] **AC-221.1:** Only `VERBATIM_ORIGINAL` can render as a direct quotation/public quote
  field without an explicit translation label.
- [x] **AC-221.2:** Paraphrase and summary output cannot be serialized through the direct
  quote field in JSON, JSON-LD, HTML or API.
- [x] **AC-221.3:** Translation always retains the original occurrence/language and a
  visible machine/human-reviewed status appropriate to the approved public schema.
- [x] **AC-221.4:** A translation that changes a number, name, date, negation, legal term or
  modality is held by deterministic fixture tests.
- [x] **AC-221.5:** Search/index normalization cannot erase wording type or create a direct
  quote from normalized text.
- [x] **AC-221.6:** Reported quotes remain governed by DP-219 and cannot be upgraded to
  `VERBATIM_ORIGINAL` through translation/paraphrase processing.
- [x] **AC-221.7:** Rights/private-body rules from DP-305 remain enforced for both original
  and derived text.
- [x] **AC-221.8:** Full suite, schema/API compatibility checks and MiniPC canary pass.

## Validation / proof

Fixtures must include original Italian, foreign-language speech, machine translation,
human-reviewed translation, headline paraphrase, editorial summary and deliberate
negation/number translation errors. Test every serializer and search projection.

## Documentation, data, and migration impact

Add a small versioned wording/derivation contract rather than duplicating Statement or
Atomic Claim models. Public schema changes require DP-105/DP-403 compatibility updates.

## Completion receipt

Local wording-contract implementation is in progress. `wording-contract-v1` now keeps a
source occurrence distinct from every derived representation: `VERBATIM_ORIGINAL` is the
only direct-quote-eligible source type; `REPORTED_QUOTE` stays a non-authoritative source
occurrence; and `PARAPHRASE`, `SUMMARY` and `TRANSLATION` are explicitly derived
representations tied to the same occurrence and source wording type. Source language and
bounded Passage/Capture/canonical-segment provenance are retained without copying private
source bodies into Claim metadata. Translation metadata carries source/target language,
method, review state and deterministic risk signals. Candidate extraction preserves
reported-speech origin as `REPORTED_QUOTE`, curated written intake preserves source
language/provenance, and ClaimCandidate promotion requires a validated
`VERBATIM_ORIGINAL` source occurrence in both Python and mutation SQL.

Focused adversarial fixtures prove that editorial cleanup and summaries cannot acquire
direct-quote authority, reported quotes remain reported through paraphrase/summary/
translation derivation, and translation changes to numbers, names, dates, negation, legal
status terms or modality are held.

The additive public-v2 boundary now projects only bounded wording metadata: source and
derived wording hashes/types/languages/derivation/review state plus references to already
public source provenance. It never publishes the original source body, summary text,
translation text, private capture/passages, or private reviewer/author references. JSON,
HTML/JSON-LD, API detail, OpenAPI and RDF/N-Triples agree that the normalized claim is a
`PARAPHRASE` with no direct-quote authority, `SUMMARY`/`TRANSLATION` remain derived, and a
`REPORTED_QUOTE` source occurrence cannot become a public direct quote. Translation
metadata retains the original occurrence, source/target language and review state.
Pre-wording `dichiarazioni-pubbliche-public-v2` dossiers remain valid because the new
`wording` member is optional/additive.

Public-boundary validation is green across 176 focused projection/schema/API/linked-data/
topic/content/wording tests plus Ruff, compileall and `git diff --check`. The static search
index now preserves normalized Finding wording explicitly as `PARAPHRASE`, retains the
source occurrence type when available, fixes `direct_quote_eligible=false` on every search
record, and rejects index records that try to elevate normalized text into quote authority.
The search contract also asserts that serialized index bytes contain no
`direct_quote_eligible=true`, proving AC-221.5.

AC-221.7 is closed against the **current DP-305 no-body baseline**, not by granting any
source right. Public projection already emits only bounded wording metadata for source and
derived representations; it now also fails closed when the public normalized claim has the
same SHA-256 as the private source occurrence body or any private
`PARAPHRASE`/`SUMMARY`/`TRANSLATION` representation. This prevents a verbatim source or
derived body from escaping merely by relabelling it as the public paraphrase, while keeping
the pure wording model free to describe semantic provenance independently of publication
rights. Focused projection/schema/API/linked-data/wording plus real PostgreSQL projection
tests are **171/171 PASS**. This receipt does **not** clear a source, approve an excerpt,
select a quotation exception, or close DP-305's rights/legal launch blockers. AC-221.8
is closed by the final post-change acceptance receipt below.

Final acceptance 2026-10-06: the integrated repository suite is **1567/1567 PASS** with the
restore drill exact, and the focused projection/schema/API/linked-data/wording/PostgreSQL
matrix is **171/171 PASS**. On MiniPC (`udodo`, Python 3.14.4, Linux
7.0.0-27-generic x86_64), the post-change public boundary ran from an isolated `/tmp` bundle:
the official focused guard is **2/2 PASS**, and an explicit four-case receipt confirms
source-body equality, SUMMARY equality and TRANSLATION equality each produce
`dossier_count=0, omitted_count=1`, while a distinct paraphrase still projects
(`dossier_count=1, omitted_count=0`). The bundle and local helper were removed after the
canary. No production DB/provider/config/deploy mutation occurred. This completes DP-221
without granting any source/excerpt right beyond the separate DP-305 policy.
