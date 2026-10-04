# DP-210 — capture preservation parser pipeline

Status: DONE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-113, DP-118, DP-209

## Problem

A Discovery Hit needs a durable observed representation before extraction, but current Content metadata is not a versioned capture ledger.

## Outcome

Implement safe bounded capture + parser + optional archiver adapters that produce immutable Content Capture receipts and Passages while keeping browser/render/archive fallbacks replaceable.

## Scope

- Normalize/fetch with existing SSRF/DNS/redirect/size protections.
- Persist response/source metadata and content hash before/with parser output according to retention policy.
- Use lightweight article/document parsing first; browser rendering only as bounded fallback.
- Create written Passages with selectors/hash; map media to existing transcript/canonical segment path.
- Add archiver adapter state machine inspired by Pender/Perma patterns without taking Pender as runtime dependency.
- Detect changed page versions via new capture hash.

## Non-goals

- No logged-in scraping unless a source-specific approved adapter exists.
- No blanket preservation of full copyrighted bodies forever.
- No claim extraction in parser itself.

## Dependencies and sequencing

DP-113, DP-118, DP-209

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [x] **AC-210.1:** Changed source bytes create a new Capture under the same logical Content.
- [x] **AC-210.2:** Unchanged replay does not create uncontrolled duplicate captures.
- [x] **AC-210.3:** Parser failure preserves a truthful capture/error receipt.
- [x] **AC-210.4:** Browser/archive failure is isolated from successful safe capture when policy allows.
- [x] **AC-210.5:** Passage selectors/hash round-trip to the captured version.

## Validation / proof

- `python3 -m compileall -q poc tests` when Python/runtime code changes;
- `PYTHONPATH=poc python3 -m unittest discover -s tests -v` when code/schema contracts change;
- `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark` when claim/evidence/publication semantics change;
- `cd web && npm run check && npm run build` when web/Studio code changes;
- `git diff --check` always;
- runtime-affecting completion additionally requires MiniPC read-back from `/home/udodo/src/DichiarazioniPubbliche.it` and PostgreSQL `dichiarazioni_pubbliche`.

Ticket-specific proof must include the exact acceptance fixtures/receipts named above,
not only a green unit-test summary.

## Documentation, data, and migration impact

Runtime, storage and queue. MiniPC filesystem/object path and retention must be proven.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

Completed 2026-09-29 in commit `26d2b1f` (`feat: add capture preservation parser pipeline`).

Implemented:
- shared `fetch_bytes()` primitive in the existing source watcher, retaining the same
  HTTPS/DNS/redirect/SSRF policy and adding bounded bytes, declared Content-Length
  consistency, final URL, media type/charset, ETag and Last-Modified receipt data;
- private per-Capture body store with generated relative paths, 0700 directories, 0600
  files, atomic write, hash verification and no global SHA-dedup that could make one
  capture purge delete another capture's body;
- deterministic Capture identity by logical Content + body SHA-256; unchanged bytes reuse
  the Capture while appending `CAPTURE_REOBSERVED`; changed bytes create a new Capture;
- stdlib-only `STDLIB_VISIBLE_TEXT` parser for `text/html`, XHTML and plain text. Script,
  style, template, SVG and similar non-visible blocks are excluded; canonical private text
  is split into bounded Passage records with deterministic IDs, `TEXT_POSITION` selectors
  and SHA-256 hashes;
- deterministic `verify_passage_roundtrip()` reparses the stored capture and proves each
  Passage slice/hash against that exact captured version;
- unsupported/binary material remains a valid Capture with append-only `PARSE_FAILED`
  receipt and no fabricated written Passage; existing media transcript/canonical-segment
  path remains authoritative for media;
- replaceable browser-render fallback contract used only after HTML parse failure. A
  browser failure appends `BROWSER_FALLBACK_FAILED` and leaves the safe HTTP Capture
  intact; a successful render becomes a separate versioned Capture when bytes differ;
- replaceable archive adapter wired into the existing DP-118
  `REQUESTED -> PENDING -> SUCCEEDED/FAILED` lifecycle. Archive failure leaves Capture and
  Passage intact and records `ARCHIVE_FAILED`; replay of an existing Capture does not
  blindly call the external archiver again;
- pipeline lifecycle expands the existing append-only event constraint with
  `CAPTURE_REOBSERVED`, `PARSE_SUCCEEDED`, `PARSE_FAILED`, and
  `BROWSER_FALLBACK_FAILED`; no parallel parser-status table was added;
- CLI `tools/capture_content.py`; default raw-body retention for this command is
  `EPHEMERAL`, not blanket durable preservation. No logged-in/browser adapter or archiver
  implementation is bundled.

Donor application:
- Meedan Pender/Perma patterns were adapted for immutable observed representations,
  replaceable parser/archiver boundaries and explicit archive states/error receipts; the
  Rails/Redis service was not adopted;
- Trafilatura/Newspaper were not added because the current Python package is intentionally
  stdlib-only and neither library is installed on MiniPC. The parser protocol keeps a
  future measured replacement possible without changing Capture/Passage semantics;
- Playwright remains an optional future fallback adapter rather than a mandatory runtime
  dependency.

Local proof:
- focused fetch/capture/schema suite: **23/23 PASS**;
- complete suite: **862/862 PASS**;
- deterministic verification benchmark: **5/5 PASS**;
- compileall over `poc tests tools` and `git diff --check`: PASS;
- unit fixtures prove changed/unchanged bytes, parser failure, browser success/failure,
  archive failed/pending, binary refusal, body-store isolation/hash checks and Passage
  round-trip.

Isolated MiniPC proof:
- `dp210_canary` was built from pre-DP-210 schema, migration applied and replayed
  idempotently; functional tracer produced 5 Capture versions / 7 Passage / 9 lifecycle
  events across changed/replayed/parser-fail/archive-fail/browser-fail cases, with 0
  Statement/ClaimCandidate/AtomicClaim/Evidence/Verification/Finding;
- same bytes replay returned the same Capture and all Passage as EXISTING plus one
  `CAPTURE_REOBSERVED`; changed bytes produced a second Capture under the same Content;
- parser failure left the body/Capture and explicit `PARSER_EMPTY_TEXT`; archive failure
  left a successful Passage while archive status became FAILED; browser failure left the
  safe Capture;
- every isolated body file read 0600 and storage directories 0700; all three first-version
  selectors round-tripped true;
- after final hardening, a clean `dp210_final` canary replayed one Capture as EXISTING and
  both Passage selectors round-tripped true;
- live bounded HTTPS fetch on MiniPC: `https://example.com/` -> HTTP 200, `text/html`,
  713 bytes through the shared safe fetch path.

Production proof:
- pre-migration baseline: 49 Content / 0 Capture / 0 Passage / 0 capture lifecycle events /
  112 jobs / 30 Atomic Claims / 17 Evidence / 9 Verification / 9 Findings / 2 PUBLISH;
  digest `133ef67fd4d6ffc3f1cf41dd37743d51`;
- pre-migration backup `20260929T104721Z`: readable **10,083,213-byte** dump;
- lifecycle constraint migration applied with `ON_ERROR_STOP` and replayed idempotently;
  all baseline counts and digest stayed unchanged;
- production canary used actual MiniPC body root
  `/home/udodo/.local/share/dichiarazioni-pubbliche-captures`: 5 canary Content produced 6 Capture
  versions, 8 Passage and 10 lifecycle events; versioned content had exactly 2 Capture / 2
  distinct hashes, parser/browser failures each retained their Capture, archive failure
  had status FAILED while its Passage remained; live CLI capture of `https://example.com/`
  succeeded through the real network path;
- every one of the **8/8** stored Passage selectors round-tripped from the exact body file;
  files were 0600 and directories 0700; jobs remained 112, claims 30, evidence 17,
  verification 9, findings 9 and PUBLISH 2;
- cleanup hash-verified and deleted exactly all six canary body_ref files, removed the five
  canary Content (cascading Capture/Passage/events), left **0 files** in the capture store,
  and restored the exact digest `133ef67fd4d6ffc3f1cf41dd37743d51`;
- final MiniPC suite **862/862 PASS**, verification benchmark **5/5**, corpus search
  **13/13 Recall@5**, p95 48.356 ms;
- post-migration backup `20260929T105031Z`: readable **10,083,321-byte** dump, manifest
  reads `content_capture=0`, `capture_lifecycle_event=0`, `passage=0`,
  `atomic_claim=30`, `evidence=17`, `finding=9`; capture body store contains 0 files.

No claim extraction, promotion, evidence lookup, verification, publication, authenticated
scraping or blanket durable body preservation was introduced.
