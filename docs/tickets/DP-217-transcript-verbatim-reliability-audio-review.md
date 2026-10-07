# DP-217 — Transcript reliability tiers and audio-to-verbatim review gate

Status: DONE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-204/DP-207 where their live lanes apply; deterministic fixture path may proceed; coordinate with DP-216

## Problem

A quotation can be perfectly bound to a transcript and still be wrong if the transcript
is wrong. Existing transcript reconciliation already holds disagreements around sensitive
tokens such as numbers and negations, but public verbatim wording needs a stronger,
explicit answer to: **what evidence establishes that these are the words actually spoken?**

Single-ASR output, platform captions and a canonical transcript are useful research
artifacts; none should silently become an authoritative public quotation.

## Outcome

Define a versioned transcript-evidence and verbatim-eligibility contract. Public media
quotes are allowed only from an approved source whose exact span has adequate evidence.
When no authoritative/official transcript exists, the conservative v1 path requires a
human audio review of the exact quoted span before it can be represented as verbatim.

## Scope

- Preserve existing Transcript Variant and Canonical Segment contracts.
- Add an inspectable transcript-evidence level/method to the span/review layer, for
  example `OFFICIAL_TRANSCRIPT`, `HUMAN_AUDIO_VERIFIED`, `PLATFORM_CAPTION`,
  `MULTI_ASR_AGREEMENT`, `SINGLE_ASR`, `UNVERIFIED`.
- The vocabulary describes evidence provenance, not an accuracy percentage.
- Define `VERBATIM_ELIGIBLE` as an explicit reviewed state, never inferred from model
  confidence or provider brand.
- For v1, `OFFICIAL_TRANSCRIPT` still requires source identity/version validation;
  non-official machine transcripts require human listening for any span projected as a
  direct quote.
- Keep existing secondary-ASR/sensitive-token reconciliation as a **triage/hold signal**;
  agreement between two models does not substitute for the human/verifiable-source gate.
- Audio review records exact start/end, transcript version/hash, reviewer, decision,
  corrected source-faithful text when needed, and reason codes without overwriting the
  original transcript variant.
- Changes to names, numbers, dates, negations, legal terms or other configured sensitive
  tokens invalidate downstream quote approval until reviewed again.

## Non-goals

- No universal ASR accuracy score.
- No assumption that platform captions are official merely because a platform serves them.
- No voiceprint/face identification.
- No public full transcript.
- No automatic publication after human transcript review.

## Acceptance criteria

- [x] **AC-217.1:** Transcript reconciliation now emits an explicit verbatim evidence method and eligibility state; media promotion and public SQL no longer treat canonical RESOLVED alone as direct-quote authority.
  direct quote cannot be public merely because `canonical_transcript` exists.
- [x] **AC-217.2:** `SINGLE_ASR`, `PLATFORM_CAPTION` and unreviewed `MULTI_ASR_AGREEMENT`
  are not v1 public-verbatim authority.
- [x] **AC-217.3:** Runtime reserves HUMAN_AUDIO_VERIFIED as the only non-official eligible method and the private append-only `transcript_verbatim_review_event` ledger binds the human decision to the exact source variant hash, segment hash and audio range.
  tied to the exact audio/time range and immutable transcript/source version.
- [x] **AC-217.4:** Existing fixtures cover dropped negation, changed number/name-sensitive disagreement, machine-only holds and dedicated homophone/punctuation/cross-talk cases in DP-223.
  punctuation ambiguity and overlapping speech remain held until source-faithful review.
- [x] **AC-217.5:** Reviewer correction creates a derived reviewed representation and
  preserves the original provider/platform variant and hash.
- [x] **AC-217.6:** A deterministic freshness check now detects later transcript/source-version, source-segment hash or reviewed-range changes, and the canonical projection path consumes that persisted freshness; any such change must stale the approval and
  block projection until re-review.
- [x] **AC-217.7:** The internal/publication gate distinguishes official, human-verified and machine-only provenance without accuracy scores; bounded public disclosure can reuse existing source_kind metadata.
  provenance without exposing provider prompts, raw transcript bodies or accuracy hype.
- [x] **AC-217.8:** Deterministic fixture, full suite, benchmark and MiniPC canary prove the
  publication gate with zero live-provider substitution.

## Validation / proof

Use synthetic/cleared audio fixtures containing numbers, dates, negations, names,
cross-talk and low-confidence spans. Prove both positive human-reviewed and negative
unreviewed paths. Run standard Python/full-suite/benchmark checks, migration replay if
needed, `git diff --check`, and MiniPC read-back. DP-204 live provider proof remains a
separate external dependency and must not be fabricated.

## Documentation, data, and migration impact

Update transcript policy/domain docs only after vocabulary is implemented. Reuse review
ledger and transcript versioning. Any new review table/fields must be additive and must not
turn a human-corrected transcript into a destructive rewrite of provider evidence.

## Completion receipt

Local verbatim-evidence gate implemented 2026-10-05: transcript reconciliation classifies OFFICIAL_TRANSCRIPT, HUMAN_AUDIO_VERIFIED, PLATFORM_CAPTION, MULTI_ASR_AGREEMENT, SINGLE_ASR and UNVERIFIED; media Claim promotion and public projection both require official/human-verified authority. On 2026-10-06 the additive private `transcript_verbatim_review_event` ledger and `source_span_review.py` runtime added exact variant/segment/range binding, append-only review history, a derived HUMAN_AUDIO_VERIFIED representation that leaves provider evidence unchanged, and deterministic stale-review detection. Disposable PostgreSQL proof loads the canonical schema, replays the migration twice and verifies both append-only enforcement and source preservation. The adversarial fixture is now v2026-10-06.3 and includes dedicated homophone, punctuation and cross-talk adverse/control pairs through a transcript-verbatim gate; the 59-case offline benchmark passes with zero fabricated public quotes.

The final 2026-10-06 integration removes the remaining source-kind shortcut: non-official
media promotion and the production public SQL require an `APPROVED`
`transcript_verbatim_review_event` whose variant hash, source-segment hash, reviewed
canonical-text hash and covered time range all still match the persisted transcript rows.
An isolated PostgreSQL acceptance seeds an ASR variant plus a current human review, proves
the dossier is public, changes the persisted source-segment bytes and observes zero
projectable findings, then restores the exact bytes and recovers eligibility. Thus the
append-only review is consumed at the canonical public boundary rather than merely exposed
by a helper.

Candidate validation is compileall + **1765/1765** full unittests + benchmark **5/5** +
DP-223 **59/59** + `git diff --check`; all **41** migrations apply/replay on disposable
PostgreSQL 17.11. The exact candidate copied to MiniPC `/tmp` passes **213/213** focused
evidence-core tests with PostgreSQL 18.6 temporary clusters plus both benchmarks. Production
database variables were removed and no live provider was invoked; DP-204 live-provider proof
remains a separate dependency rather than a substitute for this deterministic gate.
