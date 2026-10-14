# DP-435 — Public Statement with exact original wording

Status: IN PROGRESS
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

## 2026-10-11 — First implementation slice

Opt-in v3 public Statement contract in `public_schema.py`/`public_projection.py` (commit `2405049`) validates source literal against independent source span/SHA, distinct attribution/context/wording/rights/publication attestation fields, optional Finding and typed separate summary/translation. Ten focused tests pass; v2 default unchanged, v3 writer still held before consumer cutover. No real approved source/qualified rights, DB attestation, public activation or MiniPC readback; AC remain open.

## 2026-10-11 — Mutable source locator boundary hardening

The opt-in `_sanitize_public_statement` previously took `row["locator"]` directly from the mutable private candidate, verified its start/end against the immutable source text and independent attestation, then returned the same dictionary reference in the public record. A candidate that changed its locator during the independent attestation callback could therefore publish the approved quote and review/hash alongside a *different, unapproved source span* of identical length. Mutating the private candidate after building the bundle also altered the previously validated public locator without recomputing its dataset fingerprint.

Two deterministic synthetic negative tests reproduced both bugs (**RED: 2 failures**). The v3 sanitizer now snapshots the locator before the external attestation callback, fails closed if the private locator changes before the callback returns, and returns the independent snapshot so later candidate mutations cannot change an already built public bundle (**GREEN: 12/12 DP-435 seam tests**). `python3 -m compileall -q poc tests`, `git diff --check` and the deterministic benchmark (**5/5**) pass. This modifies only the isolated, explicitly opted-in Statement v3 sanitization boundary; the public-v2 default and the five separate approval requirements remain unchanged.

Source-only evidence improves the negative selector-provenance and replay aspects of AC-435.1/.3/.4. Full acceptance still needs a source-specific authorized quotation-rights decision, real statement/source and approved publication attestations, coordinated API/HTML/index migration, and MiniPC readback with correction/withdrawal proof. **DP-435 remains IN PROGRESS; all AC unchecked.**

## 2026-10-11 — Public excerpt expiry must be explicit

The opt-in v3 projection previously accepted a rights gate with
`expires_at=None`, allowing a private candidate with otherwise synthetic
approvals to become a public original-wording Statement without any bounded
review horizon. An adversarial test in `test_dp435_public_statement_seam.py`
was **RED** (one published row, expected none). The sanitizer now requires
a nonblank timezone-aware future expiration date for the current explicitly
bounded `PUBLIC_EXACT_EXCERPT` authorization. Missing/unbounded expiry is
held, not treated as implied perpetual rights. After the correction the
DP-435 suite passes **12/12**; scoped lint and diff checks pass.

This is an engineering deny-by-default contract, not a legal determination
that perpetual licenses cannot exist. Such an exception would require a
qualified, versioned policy and its own proof. No source-use rights, review,
MiniPC readback, consumer cutover or publication authority was granted;
the original AC-435.1–.5 remain unchecked.

## 2026-10-13 — Immutable frontend original validator, source-only

The shared TypeScript `validateOriginalStatement` previously checked a
caller-owned v3 Statement, awaited its exact original-quote SHA-256, then
returned the same mutable input object. A consumer could therefore display
an unapproved source URL, original quotation, locator, speaker or translation
under already checked hashes. This affects an **opt-in**, currently unrouted
source-reader primitive shared by Person/Topic and synopsis previews, not an
approved live public endpoint.

Two adversarial synthetic tests reproduced the behavior before the fix:
(1) mutation of the returned, previously validated nested input (RED:
`approved quote aliases private caller text`); and (2) modification of the
caller input immediately after the asynchronous digest calculated the
approved hash but before the validator resumed. The validator now detaches
the complete source object **before** any asynchronous integrity step and
returns that independently validated snapshot (GREEN). The quote, speaker,
source URL, locator and translated text remain bound to the approved
snapshot even when the input is subsequently mutated.

Verified `npm run check:statement`, `npm run check:statement-parity`,
`node scripts/check-public-synopsis-v3.mjs`,
`node scripts/check-private-statement-opinion-preview-v3.mjs` and
`npm run check` (Astro 0 errors, 0 warnings; one existing unused-import
hint in DP-429 test). No source-use approval, new public v3 route, MiniPC
release, Capture or publication was performed. All original
**AC-435.1–.5 remain OPEN** until independently qualified source rights,
the full authorized consumer/correction rollout and real host readback.

## 2026-10-14 — Unresolved Person identity blocked at public Statement schema

The opt-in v3 `validate_public_statement` accepted any nonempty `person_id`.
Even if all five supplied publication proofs repeated the same unresolved
identity placeholder, `_sanitize_public_statement` and the bundle validator
emitted a public exact-wording Statement with that Person as the apparent
speaker. Syntactically consistent source/rights/review references cannot
resolve a human identity. This is a false-eligible attribution at the schema
boundary, despite the separate requirement for authoritative Person approval.

**RED** against the previous implementation: the actual opt-in projection
published the Statement in four negative subcases, with `person_id` equal to
`UNKNOWN`, `person:unknown`, `person:unresolved` or `person:unspecified`.
**GREEN:** the v3 schema now rejects unknown/unresolved/unspecified/none or
empty namespace segments in the Person identifier; the projection omits the
private candidate entirely without emitting a public placeholder or leaking
its identity. Both syntactically resolved synthetic Person fixtures and the
default public-v2 projection preserve their existing behavior. No external
identity authority is inferred from this string check.

The source-only regression suite exercises the real isolated projection with
synthetic independent-looking approvals. It does not establish real editorial
review, identity or source-rights clearance, true quoted-source chronology,
MiniPC readback, public v3 activation, correction/revocation, or consumer
migration. **DP-435 remains IN PROGRESS; AC-435.1–.5 all OPEN.**
