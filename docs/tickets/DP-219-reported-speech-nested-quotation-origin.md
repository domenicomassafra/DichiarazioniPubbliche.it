# DP-219 — Reported speech, nested quotation, and quote-origin separation

Status: DONE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-216, DP-218, DP-211

## Problem

One of the easiest ways to create a false attribution is to treat a sentence *quoted by*
Person X as a sentence *said by* Person Y. Examples include a politician quoting an
opponent, a journalist reading a statement, an article paraphrasing an interview, or a
video playing an old clip inside a new commentary.

The current candidate model can preserve source wording and speaker candidates, but it
does not yet define a hard public distinction between the current utterer, a mentioned
person, a reported speaker and the independently verified origin of the nested quote.

## Outcome

Represent quote origin explicitly so reported/nested speech cannot become a direct public
statement of the reported person until the original attributable source is independently
recovered and approved.

## Scope

- Extend Statement Candidate/provenance semantics with explicit roles such as
  `UTTERER`, `AUTHOR`, `MENTIONED_PERSON`, `REPORTED_SPEAKER` and `ORIGINAL_SPEAKER`.
- Preserve nested quote boundaries and source selectors; never flatten quotation levels.
- A reported quote may create a Coverage Need for the original source through DP-213.
- Only the current source's actual utterer/author may be directly attributed from that
  source. A `REPORTED_SPEAKER` remains unverified until a separate DP-216/DP-218 provenance
  path establishes the original occurrence.
- Handle written quotation, indirect speech, press-release quoting, moderator reading,
  embedded media and repost-with-comment cases.
- Keep proposition matching useful: the system may suggest that a reported proposition
  matches an independently found original, but DP-212 similarity cannot itself approve
  attribution.

## Non-goals

- No general natural-language understanding claim that sarcasm/intent is solved.
- No automatic promotion of a reported quote because many articles repeat it.
- No counting syndication/repetition as independent occurrence evidence.

## Acceptance criteria

- [x] **AC-219.1:** Candidate extraction now preserves DIRECT_UTTERANCE / REPORTED_SPEECH / NESTED_QUOTATION / EMBEDDED_MEDIA separately; the current media segment speaker remains the utterer while a reported speaker is only an offset-bound mention/coverage hint, and `X says "Y said Z"` keeps Y only as a
  reported speaker/coverage target; Y cannot receive a public Statement from this source.
- [x] **AC-219.2:** Written sources naming another speaker are conservatively classified as reported occurrence; Python promotion plus all mutation SQL refuse non-direct speech mode, so a journalist/moderator reading another person's quote cannot be
  converted into the quoted person's direct occurrence without original-source proof.
- [x] **AC-219.3:** Embedded old clips retain their own Content/source/span and speaker
  provenance instead of inheriting the surrounding narrator's source context.
- [x] **AC-219.4:** Article chains that repeat one upstream quotation retain derivation
  lineage and do not create N independent attributions.
- [x] **AC-219.5:** Finding a verified original source can satisfy the Coverage Need and
  link the reported occurrence without mutating the historical reporting source.
- [x] **AC-219.6:** Nested/reported mode and exact reported-speaker mention offsets survive candidate persistence; normalized depth/origin-link metadata is bounded to IDs, offsets and hashes, while non-direct speech remains excluded from direct public attribution and private source text is not leaked.
- [x] **AC-219.7:** Focused fixtures cover explicit nested quotation, written indirect/reporting source, mutation-gate bypass, ambiguous quotation marks, repost commentary and quoted-tweet cases; indirect speech,
  repost commentary and quoted tweets fail closed rather than guessing origin.
- [x] **AC-219.8:** Full suite, benchmark and MiniPC canary prove zero cross-person public
  attribution in the fixture set.

## Validation / proof

Use a deterministic adversarial corpus where expected current speaker, reported speaker,
source origin and publication eligibility are hand-authored. Include both media and text.
Run standard checks, isolated schema replay if required, and MiniPC read-back.

## Documentation, data, and migration impact

Prefer additive Statement Candidate/provenance metadata or a small normalized relation
table over encoding nested-speaker semantics inside free-form JSON only. Update domain
vocabulary after implementation.

## Completion receipt

First fail-closed reported-speech layer implemented 2026-10-05. Candidate extraction carries a bounded speech_mode and offset-bound reported-speaker mention without identity IDs; written speaker mentions are conservatively reported-source occurrences; ClaimCandidate metadata carries an ATTRIBUTION_GAP hint; promotion Python and all mutation SQL refuse non-direct speech; finding publication and public projection also require DIRECT_UTTERANCE metadata. Existing public-attribution and DP-223 fixtures prove that embedded/reposted third-party media cannot inherit the surrounding Content/speaker proof, while Source Intelligence collapses approved syndication lineages instead of counting copies independently.

The 2026-10-06 closure pass adds a persisted `reported_origin` representation to both StatementCandidate and ClaimCandidate payloads with `speech_mode`, nesting depth, current source/passage IDs, exact reported-speaker offsets plus mention hash, and unresolved/self origin state without copying the mention/source body. `ATTRIBUTION_GAP` satisfaction now records the reviewed original-root/path receipt together with the exact ClaimCandidate/assessment target in append-only Coverage Need/assessment metadata; it does not update the historical ClaimCandidate. Focused ambiguous-quotation, repost-commentary and quoted-tweet fixtures remain unresolved/context-held instead of guessing origin. Focused persistence tests plus the 59-case offline adversarial benchmark pass.

Final machine closure on 2026-10-06 reconstructs `df8cdcc` plus the evidence-core changes in
an isolated candidate: compileall, **1765/1765** unittests, benchmark **5/5**, and the
hand-labelled DP-223 suite **59/59** all pass with
`known_false_public_attribution=0`. A MiniPC `/tmp` copy of the exact candidate passes
**213/213** focused evidence tests and reruns the same 59-case benchmark at zero false
attribution, with production DB/provider variables absent. This is a runtime canary, not a
DP-704 release-candidate receipt.
