# DP-437 — Independent public Statements for opinions and positions

Status: IN PROGRESS
Milestone: M4 — public product/API
Depends on: DP-435, DP-104, DP-111, DP-312

## Problem

The public-v2 projection derives dossiers from published factual Findings. Authenticated opinions/positions and non-factual speech acts cannot appear as public Statements without an invented Claim/Finding, defeating the integrated mission.

## Outcome

A source/rights/attribution-approved opinion or other non-factual Statement can be published and read independently of factual verification, while any optional factual Finding remains separately linked and precisely labeled.

## Traceability & constraints

R01, R15, R16, R20; Q9–Q20. An opinion does not get a true/false verdict by default. Human textual review is not the future routine target, but existing review/publication controls remain until explicitly migrated and proven. No person score or inferred hidden belief.

## Scope

Define versioned public Statement identity/lifecycle, time, speaker/author, speech-act/endorsement state, exact quote/source hash, quote rights, optional finding reference and publication decision. Project for Person/Topic/Content with no Finding dependency. Publish states distinguish **not yet checked**, **a completed check with insufficient evidence**, non-factual opinion and an actual sourced factual finding; an internal held or unreviewed candidate is never a public status. Append correction/reply without editing historical original wording.

## Non-goals

No invented factual verdict, generic auto-publishing of candidates, ranking of people, private corpus membership disclosure or Statement-to-Claim semantic merger.

## Dependencies and sequencing

Hard DP-435 original wording, DP-104 relations policy and DP-111 written provenance; coordinate B future speech-act/authority contracts, DP-405/406/409 and DP-431. Qualified source-use and publication authority remain external gates, not automatically inferred by being an opinion.

## Acceptance criteria

- [ ] `AC-437.1`: An approved non-factual Statement with no Finding appears on its canonical page, attributed Person/Topic/Content routes and API with original wording, date and source, and no fabricated verdict.
- [ ] `AC-437.2`: A completed insufficient-evidence factual investigation remains distinguishable from unverified and from opinion; statement-level publication does not silently publish an unreviewed factual claim.
- [ ] `AC-437.3`: Reported speech, quotation under criticism, uncertain speaker, unauthorised rights or private-held candidates create no endorsed public position, badge or private membership count.
- [ ] `AC-437.4`: Later genuine Finding, reply, correction or retraction is append-only/versioned; replay and consumer readback retain original quote and correct current status.

## Validation / proof

Future deterministic and negative fixtures for opinion-only, claim+finding, reported quotes, cancelled approval, rights expiry and privacy isolation; compare HTML/API/search and real rights-authorized MiniPC projection with source/fingerprint. No AC is fulfilled by this ticket being written.

## Documentation, data, and migration impact

Extend CONTEXT vocabulary and the public read model additively; decouple Statement index from Finding-only dossiers with version compatibility. Preserve historical DP-105, DP-221 and DP-305 receipts; no new infra solely for optional Finding.

## Completion receipt

2026-10-10: specification only, **not implemented**, all new AC unchecked.

## 2026-10-11 — First implementation slice

New `PublicStatement` v3 opt-in projection (`2405049`) supports an attributable opinion with nullable Finding, separate checking semantics and source literal approval. Focused schema/projection tests pass. No genuine opinion public page, rights/publication eligibility, person/topic consumer, historical correction or real runtime acceptance; AC remain open.
