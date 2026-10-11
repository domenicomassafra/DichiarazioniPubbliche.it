# DP-243 — Initial permanent historical corpus from mixed Italian/German primary sources

Status: IN PROGRESS
Milestone: M7 — stable v1 launch
Depends on: DP-210, DP-215, DP-703, DP-443

## Problem

Hitler/Mussolini historical materials are owner-chosen initial areas, but identifying an archive's topic landing page does not authorize a transcript, a quote or a body download. Historical materials mix speeches, quotations, newsreels, reproductions, later translations and derivative films. A deceased figure's corpus grows with newly found/digitized sources; no finite crawl can claim exhaustiveness.

## Outcome

After first full-slice acceptance, create **permanent**, versioned private historical research collections/Content for both named public figures with correctly scoped source use, original IT/DE wording, German→Italian translation links where permitted, explicit authors/speakers and documentation of missing/held source families; promoted/public entries occur only through B/C validated downstream and not automatically from acquisition.

## Traceability & constraints

R04/R07/R09/R10/R27; original/source language protected, no endorsement inference for historical narration/quotation. Candidate archive starting points (not approved inputs): Archivio Luce Mussolini topic index and Bundesarchiv Hitler-themed holdings/digitization listings, supplied in master prompt. Their terms, artifact-level rights and personal data policy require independent decisions. No archival truth or clip quote is invented here.

## Scope

Curate separate genuine Italian and German period sources, multi-format scans/video/transcript, immutable version/rights/discovery manifest, source/copy relations, period/origin timezone, speech/event/date/author roles and scope; track translations/editorial editions and historical scholarship as different evidence roles. Include small cross-person comparison-ready topics with source-confirmed semantic identity only; B/C own public comparisons.

## Non-goals

Claims that the two persons' entire historical record is collected; mass uncontrolled crawling; bundled publication of archive footage; source-specific legal clearance based on death; replacing original quote by translation.

## Dependencies and sequencing

Hard full first reader/correction path accepted at milestone gate, existing DP-210/215/703; DP-236, DP-238, DP-239 as applicable; external Archive/Luce and Bundesarchiv source-family permits, archive-licensing/third-party transcript choices and German meaning validation; soft D bulk/cost, B/C publication.

## Acceptance criteria


- [ ] `AC-243.1`: Two versioned historical manifests each identify primary originals, archive copies, modern editorial/text translations, rights/use states, precise retrieval selectors and coverage horizon; denied items are held with reason.
- [ ] `AC-243.2`: A real permitted original-language document for each chosen person yields immutably hashed Capture/Passage and source/author/speaker status, with no accidental inference from film narrator/actor/reported speech.
- [ ] `AC-243.3`: German original and optional authorized Italian translation have distinct fingerprints, dates, methods and named mismatch holds; translations never override original words.
- [ ] `AC-243.4`: Same uploaded source/repost across collections dedupes logical Content while preserving independent collection membership and source provenance; replay creates no duplicate statements.
- [ ] `AC-243.5`: A new archival transcription/version or corrected translation triggers a new retained source version, revalidation and exact impact list (candidate/public downstream), with no silent overwrite.
- [ ] `AC-243.6`: MiniPC private readback, source/rights receipts and source coverage report are verified; public record count changes only under separately approved B/C policy and release.

## Validation / proof

Immutable approved archive artifact refs, source-specific licenses, language/version hash, roles/origin negative checks, replay and MiniPC snapshot; a small accepted corpus can prove process, not historical completeness.

## Documentation, data, and migration impact

Collections and source profile reuse; add language/editorial-edition/coverage metadata only where absent; retain private files only for permitted period and explicit retention.

## Completion receipt

**2026-10-11 local source-only preflight — IN PROGRESS, not a created historical corpus.**
The new `historical_corpus_preflight_v1.py` guards exact two-person/IT-DE
manifest scopes, bounded private candidate intake, per-operation DP-236 use
permissions, immutable DP-237 Capture selectors and source-version links,
translation/editorial derivative separation, narrator/reported-speech holds,
replay dedupe, and source supersession requiring reanalysis. No actual archive
material was fetched, indexed, licensed, translated, or publicly displayed.
The real DP-443 source-to-reader+correction pilot and source-specific qualified
permissions remain hard blockers for any permanent corpus. **17** focused
synthetic tests and **99** DP-236/237/241/243/244/515/321 combined tests
PASS locally, Ruff PASS; source commit `4a586dd`. All six AC remain unchecked:
no genuine archive artifacts/rights/person provenance, MiniPC readback or
public B/C approval is yet demonstrated.
