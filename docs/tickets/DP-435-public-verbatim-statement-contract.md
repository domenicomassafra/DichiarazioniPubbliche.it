# DP-435 — Public Statement with exact original wording

Status: FUTURE
Milestone: M4 — public product/API
Depends on: DP-216, DP-221, DP-305, DP-312, DP-317

## Problem

The current public-v2 projection is Finding/dossier-centric and treats `normalized_claim` as the publicly displayed paraphrase. Source-wording metadata and hashes are available, but the present no-body boundary does not allow a legal, attributable exact quotation to become the public Statement itself. Q15–Q20 require the **actual words spoken or written**, not an editor's normalization, to be the declaration across the product. An authentic source does not independently clear quotation or recording rights.

## Outcome

One authorized, verifiably literal written or timed Statement can traverse a private approved source span and rights decision to a versioned *public Statement* projection, a canonical reader page and an API read without a paraphrase replacing the quotation. The legacy approved-empty public shape remains safe while consumers migrate; unsupported or rights-denied items remain private.

## Traceability & constraints

R01, R02, R04, R05, R08, R11, R16; owner Q15–Q20; preserve DP-216, DP-217, DP-218, DP-219, DP-220 and DP-305's verified provenance, clip/context and public isolation gates. This is a new requirement beyond DP-221 DONE's wording metadata/no-body baseline; that receipt is not retroactively extended. No release or source approval in this planning task.

## Scope

- Extend the existing Statement/quotation approval and publication projection seam (not a parallel corpus) with stable public Statement ID, immutable source Content/Capture/version and locator, literal original-language span(s), omission/discontinuity markers, language, speaker-or-author identity, context/speech-act state, quote hash, rights-use scope/expiry and publication version.
- Bind written selectors to exact text and media selectors to exact approved timed speaker coverage; verify fidelity of ASR/OCR-derived text before an original verbatim is eligible. A reported quotation is never silently interpreted as endorsement by its current narrator.
- Permit a **separate** named `summary` and an explicitly labeled translation representation, each derived and version-bound. Neither populates the declaration string nor quote metadata. No editing away meaningful qualifiers or negatives.
- Build a first public Statement reader + API projection with a deliberate schema-version/compatibility strategy. Retire or label the prior paraphrase-only reader until all quote consumers in DP-436 migrate; no mixed contradictory client where paraphrase is emitted in a quote field.
- Project only a deliberately approved excerpt and rights metadata allowed for readers, never raw captures, private transcript or full operational evidence bodies. Fail closed on stale capture, rights withdrawal, provenance mismatch or speech-act uncertainty.

## Non-goals

Universal copyright clearance, indiscriminate full-transcript publication, live provider inference on a public request, chatbot, or permission to publish a draft. Full index/card/linked-data migration is owned by DP-436; independent opinion-only publication is DP-437.

## Dependencies and sequencing

Hard edges are the existing completed provenance and public-safety contracts. Coordinate with future source-family quotation-rights and speech-act assurance tickets, DP-402/403 API compatibility and DP-436 consumers. **EXTERNAL/qualified:** before showing an actual excerpt, obtain an applicable source-family rights-use decision with scope, jurisdiction, date, authority, expiration and revocation semantics; model-generated legal confidence is not clearance. A schema migration must be staged expand → consumer migrate → contract with rollback and no unsafe fallback.

## Acceptance criteria

- [ ] `AC-435.1`: Given an approved captured original and independently supported speaker/author attribution and rights scope, a rendered Statement and API quote field reproduce exactly the authorized original words, preserve meaningful omissions and identify source locator/version/hash and language; roundtrip equals the approved substring/segment set.
- [ ] `AC-435.2`: Given a summary, normalization or Italian translation, no page, API, metadata title or quotation property describes its words as the speaker's original; summary/translation are separately typed, visibly labeled and tied to the original version.
- [ ] `AC-435.3`: Given rights-denied/unknown, unverifiable ASR/OCR, identity mismatch, disallowed secondary speaker, altered negation, stale Capture, missing source span or discontinuity that changes meaning, public projection omits the Statement and exposes no private membership, placeholder paraphrase or bodies.
- [ ] `AC-435.4`: Replay of the same publication inputs produces byte-equivalent public records; a changed source or correction produces a new version with traceable lineage, never silent rewrite, and can withdraw prior output before serving stale copies.
- [ ] `AC-435.5`: Public Detail/API read, static build/JSON schema checks and a genuine rights-authorized MiniPC readback agree on IDs, exact text, locator and fingerprint, including zero-statement and incompatible-schema cases.

## Validation / proof

Add local positive and tampered-selector/rights/translation/speech-act tests at existing projection boundaries; verify public client contract, snapshot replay, no-body scan and change/revoke races. Capture distinct written and timed samples, fixture versus genuine source proven separately. Before completion require source-specific permission decision, versioned projection on MiniPC, exact HTTP/API/HTML readback with fingerprint, and negative search for leaked operational bodies. No acceptance is marked by this specification alone.

## Documentation, data, and migration impact

Record additional `PublicStatement` fields/representation semantics in CONTEXT, public schema and privacy/rights contracts as part of future implementation; use additive migration and client version handshake where required. Existing DP-221/305 receipts and historical projection versions remain unchanged. Update API/search/linked data through dependent ticket DP-436; do not change production in the documentation-only phase.

## Completion receipt

2026-10-10: Planning-only new ticket; **not implemented**; zero new acceptance evidence, rights approval or MiniPC promotion.
