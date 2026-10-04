# DP-305 — Copyright, transcript, and excerpt publication policy

Status: **IMPLEMENTED as a fail-closed gate; NO public excerpt may ship (profile not
approved)**
Policy version: `excerpt-rights-v1`
Owner: product owner + IP/media counsel
Code: `poc/dichiarazioni_pubbliche/policy/excerpt_policy.py`
Tests: `tests/test_policy_excerpt.py`

## The fail-closed spine

C-305-01 — **rights unknown means private.** Only `RightsStatus.CLEARED` can ever
authorize a public excerpt. `UNKNOWN`, `UNRESOLVED`, `EXPIRED`, `CONFLICTING`, and
`REVOKED` all prohibit. There is deliberately **no** "the URL was fetchable, so it is
allowed" path (E-305-01): technical reachability is not permission (C-305-07).

C-305-02 — **no substitute republication.** `FULL_TRANSCRIPT` and media-copy request
kinds (`MEDIA_COPY`, `AUDIO`, `VIDEO`, `SOURCE_CAPTURE`) are rejected *before* any
other check, by design (E-305-03, AC-305.7). A dossier may carry at most
`MAX_EXCERPTS_PER_DOSSIER` excerpts (`dossier_excerpt_budget`).

C-305-03 — **exact provenance.** Every public excerpt must carry source URL,
content id, segment id, transcript variant id, a bounded timestamp range, and a
SHA-256 source content hash. Whitespace is collapsed and text is NFKC-normalized for
comparison, but punctuation is preserved so the quoted wording is not silently
altered.

C-305-04 — **no raw-body leakage.** The renderer emits only approved public fields:
`text`, `source_url`, `content_id`, `segment_id`, `transcript_variant_id`,
`timestamp_start_seconds`, `timestamp_end_seconds`, `excerpt_policy_version`,
`excerpt_chars`, plus allowlisted method fields. It HTML-escapes the text. It never
includes canonical transcript, evidence body, rights receipts, or internal rights
notes.

C-305-05 — **fail closed at read time.** Expiry, source-hash change, and segment
staleness are re-evaluated on every decision; a mismatch omits the excerpt.

## The excerpt profile is NOT approved (P-305-05, B-305-01)

The ticket explicitly forbids inventing a universal word/character limit. So the
numeric bounds in the module are a **placeholder**, and the authoritative switch
`EXCERPT_PROFILE_APPROVED = False`. With the placeholder, `decide_excerpt()` **always
returns `PROHIBITED`** via the `PROFILE_NOT_APPROVED` code. That is the correct
fail-closed default until an owner/counsel-approved profile supplies real numbers.
Tests exercise both the current (prohibited) behavior and the approved behavior with
explicit values.

The effective cap is the **smaller** of the absolute cap and a 10% ratio of the
source length (`effective_excerpt_cap`), so a placeholder profile cannot accidentally
authorize a whole short page.

## The fail-closed decision order

1. full-transcript / media request → prohibited;
2. rights not `CLEARED` → prohibited (distinct codes for expired / revoked /
   conflicting);
3. cleared but not permitted for `QUOTATION_EXCERPT_PUBLIC` → prohibited;
4. attribution or provenance incomplete (or malformed hash) → prohibited;
5. source changed since clearance (hash mismatch) → prohibited;
6. invalid or unbounded timestamp window (>300 s) → prohibited;
7. empty or over-length excerpt → prohibited;
8. stale segment or missing review → prohibited/held;
9. disallowed machine-transcript method field → prohibited;
10. intent language in the excerpt → prohibited (DP-301 hard rule);
11. profile not approved → prohibited;
12. otherwise allowed.

## Machine-transcript disclosure (E-305-08)

Only allowlisted method/limitation fields may appear:
`machine_transcribed`, `transcript_method`, `transcript_method_version`,
`asr_provider_class`, `asr_version`, `manual_correction_applied`. There is no
accuracy-claim, confidence, or score field. The product never claims a machine
transcript is authoritative or cleared (P-305-08).

## Rights complaints (E-305-09)

A rights complaint routes to the DP-303 private correction/takedown/appeal workflow
(`challenge_workflow.py`) and holds new excerpt generation pending review. It never
automatically deletes the operational record. See
`dp-303-challenge-workflow.md`.

## What this module does NOT do

- It grants no rights, clears no source, and declares no quotation fair. It only
  enforces that a *pre-existing, approved* clearance is present and current.
- It does not fetch, resolve, or embed any source.
- It implements no full-transcript path at all, by design.

## Corrected instrument mapping (research finding)

While collecting primary sources for DP-306 it was verified that the **public
quotation/press exception lives in Directive 2001/29/EC Art. 5(3)**, not in
Directive (EU) 2019/790. CDSM Art. 3 and Art. 4 are the **text-and-data-mining**
provisions (their official headings are "Text and data mining for the purposes of
scientific research" and "Exception or limitation for text and data mining"). A
rights design that leans on CDSM for quotation is leaning on the wrong instrument.
The verified text is in `legal-closure-register.md` (S2, S3). **No legal conclusion is
drawn**: which national implementing rules apply to a given source family is
Q-306-11, `OPEN`/`BLOCKING`.
