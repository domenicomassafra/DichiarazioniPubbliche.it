# DP-111 — First-class written-source claim provenance

Status: DONE
Milestone: M1
Depends on: DP-102, DP-105

## Problem

The original public-attribution contract assumed every publishable claim came from a
timed transcript. Real Garlasco intake immediately exposed the mismatch: articles,
written interviews, posts, and publisher pages contain attributable statements but have
no honest `start_ms/end_ms`. Manufacturing `0:00` segments would make provenance look
more precise while making it false.

## Outcome

Add a second, first-class provenance channel for written public sources. A claim can be
publication-eligible through either:

1. canonical timed segment(s) with approved speaker provenance; or
2. approved `claim_text_provenance` bound to the same claim, Content and Person.

All evidence, observation, verification, finding and publication-review gates remain
unchanged.

## Acceptance criteria

- written attribution stores an immutable quote SHA-256 and optional document SHA-256;
- `TEXT_QUOTE_HASH` and bounded `TEXT_POSITION_HASH` selectors are supported;
- no raw quote or source body is required in the public projection;
- candidate identity is deterministic and candidate creation cannot change the claim,
  content, or person it is bound to;
- approval atomically writes `CLAIM_TEXT_PROVENANCE/APPROVED` to the review ledger;
- claim validation requires timed segments **or** text provenance, never neither;
- finding publication and public projection accept either provenance channel but retain
  all pre-existing evidence/observation/verification/review gates;
- malformed hashes, mismatched person/content, missing review provenance, and empty
  provenance fail closed;
- OpenAPI exposes bounded text-provenance metadata and never `source_ref`/raw text;
- backup/restore verification treats text provenance as load-bearing data;
- timed-transcript publication remains regression-compatible;
- an isolated MiniPC database proves a text-only claim can traverse the full explicit
  review/publication path with zero synthetic transcript rows.

## Real-data motivation

The first Garlasco batch contains statements attributed through written articles,
published interviews, and pages quoting television appearances. They are currently
stored privately and correctly absent from the public projection. DP-111 removes the
architectural need for fake timestamps; it does **not** approve or publish those real
claims by itself.

## Implementation receipt

Closed on 2026-09-27 by commits `08991bc` (`feat: add written claim provenance`) and
`63a482f` (`fix: make text provenance approval replay-safe`).

- Added `claim_text_provenance`, deterministic quote-hash/position selectors, explicit
  attribution methods, `CLAIM_TEXT_PROVENANCE` review events, operator CLI actions, and
  a replay-safe approval transaction whose status transition is contingent on the
  append-only review ledger.
- The Atomic Claim contract now accepts either timed segment provenance or text-source
  provenance. Existing transcript publication behavior remains unchanged.
- The finding publication gate and public projection accept either provenance channel;
  evidence approval, observation approval, deterministic verification, finding review,
  and all other publication requirements remain mandatory.
- The public projection exposes only bounded selector/hash/review metadata. It does not
  expose the quote body or private `source_ref`. OpenAPI was regenerated from the same
  contract.
- Backup/restore manifests now treat both `claim_text_provenance` and the DP-110
  `inference_candidate` table as load-bearing data.
- Local acceptance after the replay-safety fix: full suite **695/695**, deterministic
  benchmark **5/5**, repository-contract check green, and `git diff --check` green.
- MiniPC acceptance after deployment: full suite **695/695** and benchmark **5/5**.
- Because the runtime database user has no `CREATEDB`, the destructive acceptance used
  an isolated `dp111_canary` PostgreSQL schema inside `dichiarazioni_pubbliche`, with an explicit
  `search_path`. The schema and all ordered migrations applied successfully and the
  canary schema was dropped after proof.
- The canary traversed the complete explicit publication path using a text-only claim:
  `transcript_variant=0`, `transcript_segment=0`, `canonical_segment=0`,
  `claim_segment=0`, `text_provenance=1`, and final `finding_status=PUBLISH`.
- Its generated public bundle had `dossier_count=1`, `segments=0`,
  `text_provenance=1`, `speaker.provenance.kind=TEXT_ATTRIBUTION`, and no private
  `source_ref`/fixture selector leakage.
- Production migration applied with `ON_ERROR_STOP` and replayed idempotently. Seven
  real Garlasco claims now have exact-quote SHA-256 provenance plus explicit
  `CLAIM_TEXT_PROVENANCE/APPROVED` review events. This approves attribution only, not
  factual truth or publication.
- Production readback after the real intake: 12 Garlasco claims, 7 approved text
  provenance candidates, 7 corresponding approval events, 14 evidence records,
  4 evidence observations, 6 private inference candidates, and **0 findings**.
- A fresh production projection still returns `dossier_count=0`, `omitted_count=0`, as
  required until evidence/verification/finding publication gates are separately passed.
