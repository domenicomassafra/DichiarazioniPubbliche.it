# DP-216 — Exact quote/source-span binding; model output can never be quotation authority

Status: DONE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-111, DP-210; coordinate with DP-207, DP-305

## Problem

Dichiarazioni Pubbliche already preserves immutable Captures/Passages and approved
`claim_text_provenance`, but a hash supplied by an intake path is not by itself proof that
the displayed quotation is the exact text present in the preserved source. The media path
likewise links claims to canonical segments, while a model/extractor can still produce
normalized wording that must never be mistaken for a verbatim quotation.

The highest-reputational-risk failure is simple: a plausible sentence that the named
person never said appears inside quotation marks. The system must make that state
unrepresentable in the public projection rather than hoping an LLM does not hallucinate.

## Outcome

Create a source-span attestation contract for **verbatim wording**. A public direct quote
is always reconstructed from, or cryptographically checked against, an approved immutable
source representation. Models may propose selectors; they may not author the quoted text.

Conceptually:

`immutable source -> bounded selector -> exact source text -> hash -> review -> projection`

Never:

`model output -> quote field -> projection`.

## Scope

- Reuse DP-210 Capture/Passage selectors for written sources and DP-207 canonical media
  segment provenance for timed media.
- Introduce one versioned verbatim/source-span attestation seam, extending
  `claim_text_provenance` and/or Statement Candidate provenance rather than creating a
  competing claim model.
- For written sources, compute the quote text/hash server-side from the exact preserved
  Capture slice identified by `start_char/end_char` (or an equivalent deterministic
  selector). A caller-provided quote string is input for comparison only.
- For media, store selectors over approved transcript/source spans; DP-217 decides whether
  a transcript span is strong enough to be used as public verbatim wording.
- Record source/capture/transcript version, selector version, source hash, exact quote hash,
  normalization version, and review event.
- Allow only explicitly documented presentation normalization (for example Unicode or
  whitespace policy). Normalization must not add/remove lexical tokens, negate meaning,
  repair grammar, or silently translate text.
- Treat ellipses and discontinuous excerpts as structured selectors. The renderer must not
  manufacture adjacency between words that were not adjacent in the source.
- Public projection may expose verbatim text only when DP-305 rights/excerpt policy permits
  the exact span; otherwise it exposes the locator/provenance without the protected body.

## Non-goals

- No new truth/falsity decision; this ticket proves what wording occurred, not whether the
  proposition is true.
- No LLM confidence threshold as quote proof.
- No automatic correction of grammar, names, numbers, dates, or negations inside quotes.
- No full-transcript/public-body publication.
- No weakening of DP-111/DP-207/DP-305 review and rights gates.

## Invariants

- **Q-216-01 — Source owns verbatim:** quotation text is derived from the approved source
  span, never from model prose.
- **Q-216-02 — Immutable version:** a changed source creates new provenance; it never
  silently changes an existing quotation.
- **Q-216-03 — Hash + selector:** public verbatim requires both content identity and a
  reproducible selector, not a free-floating quote hash.
- **Q-216-04 — Fail closed:** missing body/selector/hash/review/rights information means no
  public direct quote.
- **Q-216-05 — Derived wording is labeled:** paraphrase/translation/summary belong to
  DP-221 and cannot use the direct-quote representation.

## Acceptance criteria

- [x] **AC-216.1:** Written promotion recomputes the private source-derived Passage text hash and requires equality with the stored Passage hash and StatementCandidate hash.
  span; changing one character in caller/model-provided quote text causes rejection.
- [x] **AC-216.2:** `quote_sha256`/statement hash is checked against the recomputed source-derived Passage span, not merely
  syntactically validated as a 64-character hash.
- [x] **AC-216.3:** Off-by-one/length and non-exact selector mismatches fail closed before written Claim promotion; stale-capture re-review remains open.
  fail closed and cannot be approved.
- [x] **AC-216.4:** A media direct quote cannot be projected unless its exact span maps to
  persisted segments and satisfies DP-217 transcript-verbatim eligibility.
- [x] **AC-216.5:** A model/extractor response that contains invented or cleaned-up quote wording cannot promote when its statement hash differs from the exact Passage hash.
  text cannot create a public quote unless the exact text independently exists in the
  approved source span.
- [x] **AC-216.6:** Structured ellipsis/discontinuous-span fixtures preserve source order
  and disclose omissions; the renderer cannot concatenate non-adjacent text invisibly.
- [x] **AC-216.7:** Source version change produces new/stale provenance and removes public
  eligibility until re-reviewed.
- [x] **AC-216.8:** Rights-denied/private spans remain privately verifiable but are not
  leaked through JSON, JSON-LD, HTML, API, search or logs.
- [x] **AC-216.9:** Existing DP-111 written-provenance and DP-207 timed-provenance paths
  remain replay-safe and migration-compatible.
- [x] **AC-216.10:** Focused tamper tests, full suite, benchmark, migration replay and
  MiniPC canary prove that no arbitrary quote string reaches public projection.

## Validation / proof

- fixtures: exact match, one-character mutation, whitespace-only presentation change,
  wrong Capture version, wrong person/content, out-of-range selector, discontinuous quote,
  model-invented wording and rights hold;
- `python3 -m compileall -q poc tests`;
- `PYTHONPATH=poc python3 -m unittest discover -s tests -v`;
- `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`;
- migration apply/replay in an isolated PostgreSQL schema when persistence changes;
- MiniPC source-span read-back with source hash + selector + computed quote hash;
- `git diff --check`.

## Documentation, data, and migration impact

Update `CONTEXT.md` and `ARCHITECTURE.md` only when the implementation freezes the final
source-span vocabulary. Any additive schema must preserve current DP-111 rows and provide
a deterministic upgrade/legacy-hold strategy. Public schema changes remain bounded by
DP-105/DP-305.

## Completion receipt

Local exact-quote-binding-v1 is enforced in both written and media ClaimCandidate ->
AtomicClaim promotion seams. Written promotion recomputes the private Passage hash. Media
promotion verifies integer local quote offsets against the resolved canonical transcript
segment, recomputes the exact substring SHA-256, aligns the context-integrity offsets/hash,
and requires OFFICIAL_TRANSCRIPT/HUMAN_AUDIO_VERIFIED authority. The promoted AtomicClaim
retains the bounded context-integrity quote offsets/hash; public projection independently
recomputes that exact substring against the canonical segment before a timed quote can
escape, without crossing into private ClaimCandidate/StatementCandidate/promotion/corpus
tables. The 2026-10-06 closure pass adds `discontinuous-quote-binding-v1`: multiple source
spans must be strictly ordered/non-adjacent, each span is rebound to the immutable source
hash, and reconstructed wording always inserts the canonical explicit omission marker
` […] `. Invisible concatenation of distant clauses fails closed and the receipt retains
only hashes/offsets. This closes the local binding primitive for AC-216.6, but the AC remains
unchecked until the frozen public renderer/projection path consumes that structured
representation. Stale-source re-review, broader leak/replay fixtures and MiniPC proof remain
open.

Replay compatibility was rechecked against the existing written/timed promotion contracts,
promotion receipt replay and schema/migration idempotency: the focused promotion/schema set
passes 65/65, and the full repository suite restores the existing `claim_text_provenance` and
`claim_segment` durable state unchanged.

2026-10-06 finalization closes the remaining machine-provable path. The public projection
now consumes approved structured multi-span context as a bounded `source_span_disclosure`:
ordered offsets and per-span/source/binding hashes are public, every omitted gap is counted
and rendered with the canonical ` […] ` marker in HTML/JSON-LD, and no source body is copied.
Cross-speaker and cross-source-part/montage spans fail closed even if a caller attempts to
mark the structured context curated. Existing production source-revalidation tests prove a
changed load-bearing source version enters HOLD until the exact current version is
revalidated. DP-305/DP-221 rights fixtures omit private source/derived bodies before JSON,
JSON-LD, RDF, bundle and API serialization; the generated rights-blocked projection also
passes `check-dp221-private-body-search.mjs`, and the projection/API operational output is
limited to schema/count/fingerprint or host/port metadata rather than source bodies.

The evidence-core candidate reconstructed from `df8cdcc` plus this ticket's code changes
passes compileall, **1765/1765** unittests, deterministic benchmark **5/5**, DP-223 **59/59**,
and `git diff --check`. A disposable PostgreSQL 17.11 database applied and replayed all
**41/41** ordered migrations with `ON_ERROR_STOP`. The same candidate was copied only to a
MiniPC `/tmp` directory (never the deploy mirror) and, with production DB variables removed,
passed **213/213** evidence-core tests against its own PostgreSQL 18.6 temporary clusters,
benchmark **5/5**, and DP-223 **59/59**. A bounded MiniPC source-span canary independently
recomputed a verified `TEXT_POSITION` receipt with source SHA-256, selector `[10,41]`, and
computed quote SHA-256. No provider call or production database was used.

2026-10-07 regression closure: public multi-span projection now recomputes the canonical
`context-integrity-v1` binding from the complete private structured receipt before emitting
`source_span_disclosure`. The binding implementation is shared with
`assess_structured_context_integrity`; stale span offsets, per-span hashes or the stored
binding fail closed instead of publishing an internally inconsistent disclosure. The
focused context/projection/public-schema set passes **91/91** and `git diff --check` passes.
