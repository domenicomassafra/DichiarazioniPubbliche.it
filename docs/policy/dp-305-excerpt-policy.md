# DP-305 — Copyright, transcript, and excerpt publication policy

Status: **IMPLEMENTED as a fail-closed gate; NO public excerpt may ship (profile not
approved)**
Policy version: `excerpt-rights-v1`
Owner: product owner + IP/media counsel
Code: `poc/dichiarazioni_pubbliche/policy/excerpt_policy.py`
Tests: `tests/test_policy_excerpt.py`

## The fail-closed spine

C-305-01 — **rights unknown means private.** Only `RightsStatus.CLEARED` can ever
authorize a public excerpt. `UNKNOWN`, `UNRESOLVED`, `EXPIRED`, `CONFLICTING`,
`REVOKED`, plus operational block/hold states (`BLOCKED`, `FORBIDDEN`, `LEGAL_HOLD`,
`RIGHTS_HOLD`, `TAKEDOWN_HOLD`, `REMOVED`) all prohibit. There is deliberately **no**
"the URL was fetchable, so it is allowed" path (E-305-01): technical reachability is
not permission (C-305-07).

C-305-02 — **no substitute republication.** `FULL_TRANSCRIPT` and media-copy request
kinds are rejected *before* any other excerpt check, by design. The legacy
`dossier_excerpt_budget()` count check remains available, while
`decide_excerpt_budget()` is the structured authority: it returns bounded machine
codes for profile-not-approved, invalid lengths, per-item overflow, count overflow,
and derived total-character overflow. The total is derived only from the supplied
profile (`max_excerpts × max_excerpt_chars`), so this module still invents no separate
legal quotation limit.

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
When an expiry/review date is supplied, `decide_excerpt()` parses the caller-supplied
ISO dates on every decision. A declared expiry without a valid current date, a future
review date, or a current date after expiry is prohibited with a bounded machine code.
The module chooses no duration and does not require or invent a source-specific expiry.

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

`decide_excerpt_budget()` follows the same rule: the repository default profile is
unapproved and therefore prohibits. Tests may pass explicit profile values to exercise
the arithmetic, but those values are test inputs, not legal/source-specific clearance.

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

## Public media/embed authorization seam

The current public-v2 Content contract has bounded `public_media_url` and
`media_policy_version` fields for timed `VIDEO`/`AUDIO` content. DP-305 does not treat
their mere presence as permission. `decide_media_use()` is the pure precondition seam:

- only `EMBED` can ever be allowed by this baseline; media copy/audio copy/video copy
  and source-capture modes are prohibited;
- rights must already be `CLEARED`;
- `MEDIA_EMBED_PUBLIC` must be present in the pre-resolved permitted-use set;
- the media URL must be HTTPS, non-local/non-private-literal and credential-free;
- `media_policy_version` must be non-empty and content kind must be `VIDEO` or `AUDIO`;
- an explicit source-specific media profile must be approved. The default is false.

This seam performs no fetch and grants no permission. It only enforces a clearance
that some separately approved source policy has already supplied.

## Bounded audit reasons (E-305-12 technical seam)

`build_rights_policy_audit()` emits only the policy version, a bounded subject ID,
disposition, and up to `MAX_AUDIT_REASON_CODES` allowlisted enum reason codes. Free-form
reason text, excerpt/source text, URLs, licence receipts, and rights notes are not copied
into the receipt. Contact-shaped/unbounded subject identifiers are replaced by a generic
placeholder. This is a content-free audit representation; append-only persistence still
belongs to the runtime workflow.

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
- It does not fetch, resolve, or render an embed. It only authorizes/denies a resolved
  media/embed proposal for a later runtime/public seam.
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
