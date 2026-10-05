# DP-233 — Parliamentary speech/transcript/video alignment adapter

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-206, DP-217, DP-218, DP-231

## Problem

Open Parliament-style systems demonstrate a valuable pattern for public-statement archives:
official parliamentary proceedings, speaker identity, agenda/context and media can be
aligned so a public statement has both institutional text provenance and a precise source
locator. The repository already has Camera/Senato structured query capability and generic
media/transcript provenance, but no first-class adapter that binds these records together.

## Outcome

Create an Italy-first parliamentary adapter that can ingest approved Camera/Senato
proceedings, preserve official speaker/role/session metadata, and align transcript passages
with available media locators without biometric identity.

## Acceptance criteria

- [x] Pure intervention contract preserves official session/intervention/speaker refs,
  source URL/version and source transcript hash.
- [x] Speaker identity is emitted only when an external DP-114/DP-218-style resolution is
  explicitly approved; the alignment module performs no
  face/voice matching.
- [ ] Official transcript wording remains a source version and does not overwrite platform
  captions/ASR variants.
- [x] Official media timing becomes a direct official locator; without it, exact normalized
  transcript alignment creates only a REVIEW_CANDIDATE.
- [x] Missing or ambiguous text alignment never invents a timestamp.
- [ ] Agenda/item/session context is preserved separately from the quoted statement.
- [ ] Corrections or amended parliamentary records create new versions/supersession and
  trigger DP-227/DP-511 revalidation.
- [ ] Source terms/rights and public excerpt behavior remain governed by DP-305.
- [ ] A deterministic fixture proves multi-speaker session alignment with zero cross-person
  attribution.
- [ ] MiniPC canary exercises at least one approved official source family before DONE.

## Non-goals

- No biometric diarization identity.
- No scraping around authentication/access controls.
- No claim that an official transcript proves the factual truth of what a member said.
- No separate parliamentary database/service when the existing corpus model is sufficient.

## Completion receipt

Local official-intervention/alignment contract + focused tests added 2026-10-05. Camera/
Senato ingestion, persistence, source-version/reanalysis integration and MiniPC canary
remain open.
