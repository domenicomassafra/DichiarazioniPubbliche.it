# DP-219 — Reported speech, nested quotation, and quote-origin separation

Status: FUTURE
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

- [ ] **AC-219.1:** `X says "Y said Z"` produces X as the current utterer and Y only as a
  reported speaker/coverage target; Y cannot receive a public Statement from this source.
- [ ] **AC-219.2:** A journalist/moderator reading another person's quote cannot be
  converted into the quoted person's direct occurrence without original-source proof.
- [ ] **AC-219.3:** Embedded old clips retain their own Content/source/span and speaker
  provenance instead of inheriting the surrounding narrator's source context.
- [ ] **AC-219.4:** Article chains that repeat one upstream quotation retain derivation
  lineage and do not create N independent attributions.
- [ ] **AC-219.5:** Finding a verified original source can satisfy the Coverage Need and
  link the reported occurrence without mutating the historical reporting source.
- [ ] **AC-219.6:** Nested quote depth/boundaries survive replay and public-safe metadata;
  private source text is not leaked.
- [ ] **AC-219.7:** Adversarial fixtures with ambiguous quotation marks, indirect speech,
  repost commentary and quoted tweets fail closed rather than guessing origin.
- [ ] **AC-219.8:** Full suite, benchmark and MiniPC canary prove zero cross-person public
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

Pending DP-216/DP-218 and implementation.
