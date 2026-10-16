# DP-317 — Percorso lecito per citazione pubblica esatta per source family

Status: IN PROGRESS
Milestone: M3 — editorial, correction, privacy, and legal policy
Depends on: DP-118, DP-216, DP-221, DP-305, DP-304, DP-306

## Problem
 Il vecchio public boundary omette i corpi e può esporre PARAPHRASE; il nuovo prodotto richiede parole esatte. Non vi è licenza universale delle frasi e non è automatico che la licenza del *documento* autorizzi trascrizione, edizione/traduzione, screenshot o embed. `DP-305` previene violazioni sul contratto precedente ma non seleziona nuove lawful grants di repertorio.

## Outcome
 Versioned `PublicExactQuoteRightDecision` per `source_family + content/capture/version + permitted_public_use + representation_type + jurisdiction + effective_interval`, con owner/qualified decision refs, condizioni e scadenza; riusa diritti esistenti, alimenta una superficie pubblica di parole originali **solo** se binding semantico e rights sono correnti.

## Traceability & constraints
 R08/R02/R04/R24/Q15–Q16; riferimento CGUE *Infopaq* nel prompt come questione da considerare, non verdetto blanket. Nessuna parafrasi sostitutiva della dichiarazione. Verbatim conservato privatamente quando blocked, con tentativi concreti di fonte/permesso lecito e case reason.

## Scope
 Separare acquisition vs private storage vs quote display, text originally authored vs official transcript vs OCR/ASR vs editorial translation vs excerpt of creative document vs image/audio/film/embed; formalize exact original offsets/segment hash/coverage context + attribution obligation + source-license/exception/permission receipt + allowed length/necessity **solo** nei singoli decision scopes; read-time revocation/version revalidation to C projection; link complaint to DP-303/510 and D cache purge. Document research attempts to alternate primary licensed source if current one cannot authorize the exact quotation.

## Non-goals
 No universal word-count ceiling, no blanket public-domain from death, no published raw transcript; no agent-created legal opinion.

## Dependencies and sequencing
 DP-307 must accept relevant per-source legal basis for public activation, not for writing specs. Pilot source grant and rights version precede C public exact quote acceptance. A source accessibility cannot stand in for rights decision.

## Acceptance criteria

- [ ] `AC-317.1`: For same source/wording, one lawful approved use may allow a bounded exact quote while different representation (translation/footage/edition) stays held; grant never generalizes to neighboring source families.
- [ ] `AC-317.2`: Rights record binds exact immutable hash/locator/wording context and source terms; unknown, expired, withdrawn, conflicting, jurisdiction changed or revoked approval prevents all public quote-consuming surfaces.
- [ ] `AC-317.3`: Source-only metadata may appear if authorized, but original public declaration **is not** replaced with normalized/paraphrase; explicit private ineligibility + repair attempts recorded.
- [ ] `AC-317.4`: Translated Italian quotation is visibly translation, never source original; edition/copy/transcript source versions distinguish authority and verify meaning-sensitive terms.
- [ ] `AC-317.5`: Complaint/revocation fences all public caches/routes through DP-320/D consumer and leaves append-only correction/public notice history without protected body leakage.
- [ ] `AC-317.6`: Authorized real source-family pilot demonstrates exact words on Statement, list, comparison, search, API, HTML/RDF/JSON-LD; unauthorised negative pilot omits them everywhere. MiniPC future readback and qualified register attached.

## Validation / proof
 Source-family matrix with underlying basis/version/approved use; positive licensed/approved synthetic fixture plus negative missing/expires; do not ingest protected media merely as QA. Legal evidence in controlled store, stable minimal refs in code.
## Documentation, data, and migration impact
 Add narrow rights-use/version mapping atop `rights_registry`, no broad replacement; public schema migration owned C, source ACL owned A, cache D.
## Completion receipt
**2026-10-11 local source-only exact-quote preflight — IN PROGRESS.**
`lawful_exact_quote_preflight_v1.py` binds proposed source family + locator,
Content/Capture/version SHA, exact verified DP-224 written selector, quoted
wording/context hash, original-vs-translation identity, representation, purpose,
jurisdiction, use/conditions/limited duration, case-specific rights reference,
and caller-supplied revocation epoch. Existing DP-236 `STORE_BODY` is checked
but explicitly not promoted into `EXCERPT_PUBLIC`. Film, audio, screenshot and
embed reuse remain HELD even when text clearance is claimed. An otherwise
coherent private metadata claim still returns `public_quote_permitted=False`
until external DP-307 qualified rights/signature, DP-320 authentic read-time
fence and DP-443 real pilot/public consumer proof. No blanket quote exception,
universal char ceiling or fabricated counsel receipt. Source/test commit
`1aac45c`: **10** focused tests and **39** selected DP-317/quote-binding/
DP-236/DP-320 regressions PASS; Ruff lint/format PASS. This does not authorize
actual archive licenses, translation reproduction, front-end v3 conversion,
CDN release or any quoted public record. All AC-317.1–.6 remain unchecked.

## 2026-10-14 — Distinct private translation-use preflight (source only)

A real source-only rights-use mismatch was reproduced: a scoped claim for
`EDITORIAL_TRANSLATION` + `IDENTIFIED_TRANSLATION` could reach
`source_only_consistent=True` when the underlying DP-236 private rights record
granted only `STORE_BODY` and explicitly did not grant `TRANSLATE`. The exact
requested public use, parent-hash labeling, capture scope and claimed legal
review were otherwise coherent. The negative test failed before the patch:
expected `SOURCE_USE_NOT_PERMITTED`, observed
`EXTERNAL_QUALIFIED_AND_LIVE_PROOF_REQUIRED` (source consistency asserted).

`evaluate_exact_quote_preflight` now separately checks `TRANSLATE` for an
editorial translation, in addition to the existing `STORE_BODY` requirement,
using the same source subject, current rights record, reviewed policy and
evaluation time. A matching explicit source-family `TRANSLATE` private use
restores *source-only consistency* in the synthetic positive control, while
`public_quote_permitted` remains **False** and the external DP-307/DP-320/
DP-443 gates remain mandatory. Original-language quotes and official source
transcriptions are not inferred to be new editorial translations.

Focused/adjacent local proof: DP-317, quote-binding, DP-236 source-use and
DP-320 revocation-epoch suites **50/50 PASS**; Ruff check and format check,
Python compileall and `git diff --check` **PASS**. No live provider or Git
integration performed in this source-only worker tranche.

This hardening is a local source/test receipt, **not** qualification of a
legal basis, a real translated document, a source-use grant, public rights,
revocation-at-request authority, MiniPC operation or end-user acceptance.
**All AC-317.1–.6 remain OPEN; ticket IN PROGRESS.**
