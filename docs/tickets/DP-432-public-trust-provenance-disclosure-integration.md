# DP-432 — Public trust/provenance disclosure integration for Statement and Method

Status: DONE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-216..DP-223, DP-308, DP-427, DP-428

## Problem

The Statement and Method pages are already owned by DP-427/DP-428. The new Trust &
Evidence hardening must be surfaced publicly without reopening those completed/active page
ownership tickets or inventing a second trust UI. Readers need to understand what is an
exact quote, how the speaker was attributed, what source role was used, what was translated
or paraphrased, and why the system sometimes abstains.

## Outcome

Integrate the implemented safety contracts into the existing v4 Statement/Method grammar
using progressive disclosure and plain language. Public trust comes from inspectable
provenance, not confidence badges or "AI verified" marketing.

## Scope

- Statement page disclosure for wording type: original/verbatim, paraphrase, translation,
  reported quote where applicable.
- Show bounded original-source locator and source/capture date/version metadata allowed by
  public schema/rights policy.
- Show attribution method in human-readable form when useful (for example official record,
  reviewed source metadata, manually reviewed media span) without exposing internal notes.
- Show when a translation is present and provide the original-language wording/locator when
  rights/public schema allow it.
- Explain evidence roles/contextual authority: a first-party source can prove what someone
  said without proving the factual truth of what they said.
- Method page documents the fail-closed/abstention rule, source-span quote binding,
  non-biometric attribution, reported-speech separation, context review, source suitability,
  human review and correction propagation.
- Do not show internal confidence/source scores because those are not publication proof.

## Non-goals

- No new visual system or separate dashboard.
- No raw transcript/evidence/reviewer notes.
- No claim that the displayed method or a confidence label guarantees legal/factual truth.
- No reopening DP-428's completed document grammar; this ticket updates content/components
  through the already-approved grammar.

## Acceptance criteria

- [x] **AC-432.1:** A reader can distinguish direct quote, paraphrase and translation from
  text/semantics, not color alone.
- [x] **AC-432.2:** A public direct quote is displayed only when DP-216/DP-308 marks the
  underlying provenance eligible; UI never fabricates a fallback quote.
- [x] **AC-432.3:** Reported speech cannot visually appear as the reported person's direct
  statement unless DP-219 original-source requirements are satisfied.
- [x] **AC-432.4:** Attribution/source/time/context are retraceable from the Statement page
  without exposing private operational data.
- [x] **AC-432.5:** Method clearly distinguishes occurrence proof from truth evidence and
  explains why first-party/official sources have bounded roles rather than universal trust.
- [x] **AC-432.6:** Method explains abstention/hold behavior and human review honestly; no
  percentage confidence or "AI verified" badge is used as proof.
- [x] **AC-432.7:** Correction history links through DP-431 and cannot leave stale wording
  in the current canonical view.
- [x] **AC-432.8:** Desktop/mobile/keyboard/200%-zoom and public-schema compatibility tests
  pass with no provider/LLM request path.

## Validation / proof

Use synthetic projected fixtures for direct quote, paraphrase, translation, reported quote,
held/unresolved and corrected records. Run `web` checks/build plus public-projection/API
tests and screenshot/keyboard review.

## Documentation, data, and migration impact

Update Method copy and Statement provenance component contract only after upstream safety
contracts are implemented. No new operational data becomes public solely for this ticket.

## Completion receipt

Local Statement/Method integration now consumes only already-public provenance. The
normalized claim heading is no longer rendered inside quotation marks; every Statement labels
it as `PARAPHRASE`/non-verbatim and explicitly states that a missing source body is never
reconstructed as a quote. When DP-221 wording metadata is present, the disclosure preserves
`VERBATIM_ORIGINAL` vs `REPORTED_QUOTE`, source language and translation review metadata
without exposing original/translation bodies. The same page retains the public source URL,
date, locator and bounded speaker provenance kinds. The Method page now documents wording
separation, reported speech, non-biometric attribution, occurrence-proof vs truth-evidence
roles and fail-closed holds without a confidence badge/score.

`check:trust` inspects rendered Statement/Method HTML and fails if a normalized Statement h1
is quoted, required disclosures disappear, or `AI verified`/rating-style shortcuts appear.
The rendered-browser QA also scans accessibility trees for forbidden private/provider/score
markers and records zero external/provider requests. Correction-aware Explore, Person, Topic,
Content and Trace links now target the Statement `#storia` history anchor, and the static
correction-consistency checker verifies those links against the built search index and correction
register.

DP-431's synthetic correction rebuild now proves that the current Statement, its social/JSON-LD
metadata, API record, search row and every linked Person/Topic/Content/Trace surface converge on
the corrected projection while the superseded wording is absent from the current canonical view.
The Statement history block retains current/superseded Finding identifiers and the derived
surfaces link to `#storia`, closing AC-432.7.

AC-432.8 is now fully machine-proven at its literal scope. The current tree passes the rendered
Chrome matrix (desktop/phone keyboard flows, reduced motion, 640 px 200%-equivalent reflow and
zero external/provider requests) plus an exact Chrome browser-zoom factor of `2.0` verified by
`outerWidth=1280`, `innerWidth=640`, `devicePixelRatio=2` and `visualViewport.scale=1`. MiniPC
Chrome 150 independently reports the same zoom identity with `scrollWidth=635` and a 44 px filter
target. An isolated MiniPC build against the exact approved
`dichiarazioni-pubbliche-public-v2` projection serves `/`, `/esplora/`,
`/metodo/`, `/search-index.v1.json`, `/api/v1/health` and `/api/v1/openapi.json` with `200` and a
matching `501348d9638e...` search/API fingerprint. This closure does not claim real screen-reader
or manual visual acceptance; those cross-surface judgments remain owned by DP-410 rather than this
ticket's AC-432.8. The final 2026-10-06 production promotion subsequently removed the recorded
DP-401 drift: live static search, API health and the internal linked-data receipt now converge on
`501348d9638e...`. The approved production projection is empty, so the trust checker now treats
zero rendered Statement pages as valid only when the public search index also has zero Finding
records; Method disclosures remain mandatory. Populated fixtures still require every rendered
Statement trust disclosure.

All DP-432 acceptance criteria are machine-proven. The final upstream blocker, DP-223,
closed on 2026-10-07 after its persisted 59-case projection/serializer replay and isolated
MiniPC release-candidate attribution-integrity sub-rehearsal both passed with zero known false
public attribution and zero fabricated direct quote. DP-432 is therefore DONE. Real
screen-reader/manual visual acceptance remains separately owned by DP-410 and is not inferred
from this ticket.
