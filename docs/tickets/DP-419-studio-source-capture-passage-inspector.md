# DP-419 — studio source capture passage inspector

Status: IN PROGRESS
Milestone: M4 — Public product, API, and hosting
Depends on: DP-210, DP-414

## Problem

Trust in the research corpus requires seeing which exact version was captured and which passage/time range generated a candidate, without dumping copyrighted/raw material into public views.

## Outcome

Implement a private provenance inspector for logical Content, locators, capture versions/hashes, parser/archive receipts, passage selectors, transcript references and derivation candidates.

## Scope

- Version timeline with capture hash/change indicators.
- Safe bounded passage preview according to retention/rights policy.
- Jump from candidate to exact selector/time range.
- Show parser/archive/fetch failure states and derivation candidates.
- Copy stable internal IDs/hashes for audit without exposing credentials/private headers.

## Non-goals

- No public source-body viewer.
- No raw cookie/auth header display.
- No “archived” badge without succeeded receipt.

## Dependencies and sequencing

DP-210, DP-414

Do not bypass an unresolved prerequisite by fabricating empty-success output. Preserve
concurrent work and use the smallest independently provable vertical slice.

## Acceptance criteria

- [ ] **AC-419.1:** Two changed captures can be compared at metadata/selector level.
- [ ] **AC-419.2:** Purged-body state remains understandable from hash/receipt metadata.
- [ ] **AC-419.3:** Media candidate jump synchronizes to canonical segment/time range.
- [ ] **AC-419.4:** Sensitive headers/secrets do not render.

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

Private Studio + storage metadata API.

Update canonical docs only where actual implementation changes the contract. Historical
research/receipts stay historical; do not rewrite them to make the new architecture look
older than it is.

## Completion receipt

### 2026-10-12 — Real read-only media Capture context linked to authenticated Studio

The new PostgreSQL media context inspector from this tranche has been wired
into the existing bearer-authenticated Studio API at /v1/media/capture-context
and its operator Catture panel. The operator supplies one Content, exact
Statement Candidate and canonical-media Passage plus one Capture ID/SHA.
One canonical-schema PostgreSQL SELECT binds them and reports canonical
time range, duration, Capture retention/body/hold/rights state and explicit
source-version blocker codes. The browser validates the typed private-only
response; never receives raw media, URLs, transcript wording, provider headers
or secrets. A second real HTTP PostgreSQL suite tested 401/403/422 and
cross-Content/wrong SHA negatives; the executable UI script fixture validates
non-rendering of an injected unapproved media URL and clearing on logout.

Crucial schema blocker: MEDIA_SEGMENT_REF Passage requires canonical_segment_id
and prohibits capture_id, and there is no independent canonical Segment to
Capture-version FK. Therefore even an apparently CLEARED Capture cannot certify
the segment belongs to its exact immutable version. The interface explicitly
reports capture_segment_binding=UNPROVEN and seek_authorized=false, never
pretends playback access; AC419.3 and original ticket closure remain open
pending real source/version provenance, rights and MiniPC acceptance.

Pending implementation. Record changed surfaces, commands/results, MiniPC proof when
required, migration/rollback state, residual blockers and the resulting commit before
marking DONE.

### Fail-closed capture version comparison (private backend) — 2026-10-08

`studio_capture_inspector.py` adds an additive metadata-only read seam for two
**distinct** known capture hashes on one Content. It uses the existing persisted
`CapturePipelineStore.find_capture` contract and rejects missing/tampered versions,
status enums, identity collisions and backend failures. It compares hash,
capture/hold/archive status and `PURGED/STORED_UNVERIFIED/NOT_STORED` body state:
stored references do not assert readable body or rights clearance.

The returned data is limited to stable IDs, hashes and operational states. It never
copies source URL, private text, parser payload, raw capture metadata, archive
receipt or credentials, and confers no review/publication authority. This is **not**
yet a connected private browser inspector or approval to show excerpt bodies:
real capture-history UI, exact passage/media jump, rights-gated preview, keyboard
acceptance and MiniPC persisted replay remain open.

Follow-up 2026-10-08: the exact two-hash persisted capture comparison
now has authenticated loopback read-only HTTP/HTML transport. Raw bodies,
source URLs, archive receipts and credentials are still excluded.
Exact media selector jump, retention/rights-gated passage preview and
real browser/DB acceptance remain open.

Follow-up 2026-10-08: the adjacent private collection inspector
can now read historical Claim text-provenance hash/selector
records scoped to Collection→Content→Claim. The Garlasco baseline
has 28 approved-state TEXT_QUOTE_HASH records but still zero
Content Captures/Passages. This adds **no** archive verification,
rights-granted passage preview or exact media-segment jump; all
DP-419 AC remain open.

### 2026-10-09 capture lifecycle receipt authenticity (Wave 12)

The authenticated metadata-only two-version reader formerly trusted an
`archive_status=SUCCEEDED` without an archive completion receipt or timestamp,
and could show `PURGED` from a standalone purge timestamp while the row
remained `CAPTURED`. This could present nonexistent archival/purge proof as
established state. The reader now re-enforces the `ContentCaptureRecord`
contract: completed archive status requires its timestamp and nonempty receipt,
other non-new archive states require provider and request time, and
`PURGED_BODY` requires absent body ref plus purge time, reason and receipt.
Inconsistent mixed states are blocked without returning private receipts.
Nine adversarial cases reproduced RED, then passed GREEN with a valid control.
This is local source-only proof, not evidence of a real archive or MiniPC
capture comparison. All DP-419 AC remain open.

2026-10-09 Wave 13 chronology refinement: a completed archive
(`SUCCEEDED` or `FAILED`) with otherwise present receipts could
still be displayed when `archive_completed_at` preceded
`archive_requested_at` (including timezone-offset disguises).
The inspector now checks their aware instants in chronological
order before reporting completion. RED→GREEN cases cover both
terminal outcomes and offset inversions; an equivalent instant
across offsets is accepted. This remains metadata-only and does
not cryptographically attest an archive provider or install
the private browser runtime.

### 2026-10-09 Wave 15: persisted written Passage selector drill-down

The authenticated local Studio `/v1/capture/passages` read path now accepts an
exact Content ID and Capture SHA-256, loads/revalidates the persisted Capture
lifecycle before querying a strictly bounded (1–20) list of written Passage
selectors. SQL fetches only ID, capture/content/segment bindings, selector type,
hash and character/page positions; it **never selects** `private_text`,
credentials, arbitrary `metadata` or canonical transcript body. Response
excludes all backend-only fields, even when forged rows inject private text.

The inspector rejects cross-Content and cross-Capture rows, unsupported media
selectors, invalid hashes, non-increasing cursor pages, malformed selector
coordinates and backend errors. The private HTML compare panel has keyboard-
reachable buttons to inspect either known Capture's selectors; pagination is
by validated after-ID, with explicit `rights_clearance=false` and
`publication_authority=false`.

Proof: RED missing import for new tests, then 25 focused Capture/HTTP tests
GREEN. An independent disposable PostgreSQL cluster loaded actual
`schema.v1.sql`, inserted two unrelated Contents, Captures and three Passages,
and passed the real SQL + exact Capture/Content scoping + paginated projection
acceptance. `AC-419.1..4` are **not** declared closed: this vertical supports
written Passage navigation only. In particular, `MEDIA_SEGMENT_REF` belongs
to canonical Content segments rather than Capture versions and still needs
a separately bound, tested time-range/candidate jump; rights-gated source
preview, real MiniPC installation, browser/manual AT and provider receipts
remain unavailable. No migration, corpus mutation, rights decision, reviewer
authority or production deployment was performed.

### 2026-10-09 Wave 16: content-scoped media Candidate time locator

Because a `MEDIA_SEGMENT_REF` Passage belongs to a **canonical Segment on
logical Content**, not to a versioned Capture, it must not be put into the
version-specific written selector list. A distinct authenticated loopback
`/v1/media/segment` read now resolves the exact persisted
StatementCandidate→statement_candidate_passage→Passage→canonical_transcript_segment
join, requiring the supplied Content ID, Candidate ID and Passage ID and
all three related Content bindings to agree. The SQL projection never
fetches transcript/statement/passage wording, private metadata, URLs or
speaker identity. The pure inspector also validates the media selector,
stable source IDs, Passage hash, stored segment index/time range,
transcript status and publication-blocked state.

The private Studio Catture workspace offers an explicit keyboard-usable
lookup form and a live region showing the stored canonical time interval in
seconds, **not** a real media-player seek, attribution verification, playback
right, approval or publication eligibility. An uncertain or held segment
retains its actual persisted states and all authority flags are false.

Additional synthetic RED→GREEN and HTTP/SQL projection regressions plus an
isolated PostgreSQL fixture with actual linked Candidate/Passage/Segment
records cover mismatched candidate/source IDs, wrong selector, missing joins
and secret-text non-disclosure. This remains a partial DP-419.3 locator
step, **not** AC-419.3 closure: real preview/seek synchronization and a
rights-approved MiniPC/real-media operator replay are still pending.

### 2026-10-09: persisted Capture chronology and private UI clearing (Wave 18)

The earlier/later labels in the private Capture comparison previously followed
the order of user-supplied hashes without checking persisted observation time.
Both captures now require valid timezone-aware \`observed_at\` values; an
earlier/later request with reversed or indistinguishable UTC instants fails
closed. The private metadata response exposes each validated observation
timestamp (not any raw body/header/receipt). Regression fixtures proved RED for
reversed, offset-disguised, equal, absent and naive timestamps before this
change, and GREEN after it. The loopback browser also invalidates prior fetches
and clears its private media locator and capture jump links on token removal
or workspace switch, including delayed responses.

No rights-gated source excerpt, player seek, real media permission, external
archive proof, deployed MiniPC browser or assistive-technology acceptance is
inferred. DP-419 and all four AC remain open pending their full criteria.

### 2026-10-10 — persisted written selector difference and purge receipts

The authenticated private `/v1/capture/compare` now compares both persisted
Capture versions by exact written Passage selector coordinates and content
SHA-256. The bounded diff reports `UNCHANGED`, `CHANGED`, `ADDED` and `REMOVED`
for at most 20 Passages in each version. Passage IDs are version-local; changed
text at the same location is identified by hashes, without returning text.
Duplicate selector anchors, cross-Content/Capture bindings, invalid selectors,
unordered DB pages and secret-bearing backend exceptions fail closed. For an
over-limit version the diff reports `TRUNCATED` with **no inferred complete
counts**; the existing paginated selectors remain available for manual review.
The keyboard-reachable Studio Catture panel displays a summary and clears it
on disconnect or workspace switch, including stale asynchronous responses.

The Capture lifecycle metadata also exposes `purge_receipt_recorded`,
`archive_receipt_recorded` and a validated, timezone-aware `body_purged_at`
timestamp, alongside the original hash and PURGED state. Original receipt
contents, private source body, headers, URLs and purge reasons remain excluded;
receipt presence does not independently attest an archive provider or rights.

Focused Mac acceptance: **40/40 PASS** including actual disposable PostgreSQL
for two changed Capture versions and one purged-body Capture, loopback
authenticated HTTP, privacy negatives, and JS stale-response regression;
`compileall` and `git diff --check` PASS. The preceding full repository suite
ran **2241 tests PASS** before the final purge-receipt fixture addition;
focused regressions cover that addition. On MiniPC `udodo`, an **isolated
temporary copy** of the candidate source/tests ran the same **40/40 PASS**
with PostgreSQL 18 binaries and ephemeral database. This does **not** install
the feature in the production mirror or alter the real DB/public projection.
Production `content_capture` count remains **zero**, so no real source Capture
was represented as a live two-version acceptance.

The subsequent full-suite run after the fixture addition executed **2242 tests
with 1 failure outside DP-419**: `test_public_web_boundary` asserts the old
literal `robotsPolicy` expression, while concurrent uncommitted public-account
work had added `privatePage` to `BaseLayout.astro`. That overlapping public-web
source/test correction belongs to its other worker; the DP-419 source and
privacy-focused tests continued to pass. Full-suite GREEN is not claimed for
this moving shared-worktree snapshot.

**Still open:** AC-419.1/.2/.4 are functionally exercised by genuine SQL
with synthetic persisted rows but require installed/runtime live-source and
operator acceptance before final sign-off. AC-419.3 requires a rights-permitted
media artifact bound to its canonical Content, synchronized player seek to
the persisted segment interval and operator/keyboard replay. The existing
media locator is metadata-only. No source rights review, publication authority,
manual 200% zoom/screen-reader pass or approved media body was obtained;
DP-419 stays `IN PROGRESS`.

## Post-grilling planning reconciliation — 2026-10-10

**Status unchanged; original acceptance checkboxes and dated proof remain authoritative.** This is a future target update, not source-rights approval or completion. Source: native lane A packet.

**Baseline and preserved proof:** **AC-419.1–.4 OPEN.** Read-only capture version compare/hash/selector diff, purge receipts and content-scoped media Candidate locator; 40/40 focused Mac + isolated MiniPC proof, but live production Garlasco Capture still zero. Historic full 2242-suite had one unrelated concurrent failure, not full green.

**Target delta and remaining acceptance:** Real rights-permitted dual Capture versions in persistent MiniPC and operator/browser readback; body purged still legible from private receipt; exact media player seek to canonical segment/time on approved clip (current locator only metadata), safe bounded excerpt, keyboard/zoom/AT, no secrets. Expose copyable *private* audit locators, not raw body to public.

**Phase / dependencies:** Phase 2/3; hard DP-210, DP-414, real source captures and preview/media use permits; soft A-NEW-03/B rights; Studio owner.

**Related future specifications (separate ownership):** DP-237, DP-320. These coordination links are not newly asserted hard dependencies on this existing ticket. Hold when rights, attribution, budget or actual MiniPC acceptance is absent.

### 2026-10-11 — Persisted written Passage→Capture version locators (local-only)

The existing authenticated, loopback-only `/v1/capture/compare` and
`/v1/capture/passages` now return a bounded, copyable **metadata-only audit
locator** for each exact written Passage. Each locator contains the previously
validated `content_id`, `capture_id`, `capture_sha256` and persisted
`passage_id`; it contains no source URL, body, transcript, private headers,
receipt payload, permission or speaker identity. A comparison row has
`earlier_locator` and `later_locator`, set to `null` when that version has no
Passage at the selector anchor. The selector-page entry has `capture_locator`.
This preserves explicit provenance when a hash changes at the same character
range, or a Passage is added or removed in a later Capture. The caller can
copy the complete tuple for audit and correlate it with the already available
private Capture selector page, rather than guessing the Capture from the
Passage ID. No new route, database write or browser code was required.

The `limit+1` lookahead row for selector pagination now receives the same
full persisted Content/Capture/selector validation as displayed rows, so an
out-of-scope Passage cannot fabricate `has_more` for another Capture. An
adversarial fake store formerly returned success with a foreign sentinel;
after the change it refuses the page. No cross-version identity or textual
equivalence is inferred merely from coordinates and IDs.

**RED→GREEN receipts:** Two synthetic regression cases were RED on the
original code (missing per-version locator and cross-Capture sentinel
accepted). A third dedicated test exercises real `schema.v1.sql` on disposable
local PostgreSQL, two persisted Capture versions and their written Passages,
with exact `CHANGED`/`REMOVED`/`ADDED` metadata, page continuation, and the
existing `/v1/capture/compare` + `/v1/capture/passages` dispatch. The fixture
ensures no private text/URLs/headers appear and authority flags remain false.
`PYTHONPATH=poc python3 -m unittest tests.test_studio_capture_inspector
tests.test_studio_capture_selectors_pg tests.test_studio_local_api
tests.test_studio_media_selector -q`: **47/47 PASS**. The proof uses only
local, disposable data and no MiniPC or production source.

**AC-419.1–.4 remain OPEN** despite their metadata-only partial coverage:
no real rights-cleared two-version Capture corpus on the MiniPC; no authorized
private excerpt/receipt verification; no keyboard/operator and 200%-zoom
acceptance; no real authorized media artifact with synchronized player seek
to a canonical segment. These audit locators do *not* independently perform
a browser seek or authorize passage preview. No provider, rights, review,
publication, migration or deployment state changed.

### 2026-10-12 — Separate persisted media interval and Capture retention context

Added `inspect_candidate_media_capture_context()` as a source-only, opt-in
read model over the **real canonical PostgreSQL schema**, exercised against
disposable local PostgreSQL. One database SELECT joins exact
StatementCandidate → Passage → canonical_transcript_segment while independently
requiring a requested Content Capture ID *and* SHA-256 from the same logical
Content. It projects the canonical start/end milliseconds, Content duration,
Capture observation time, digest, body-presence state, retention class, hold,
and stored rights status. The projection is bounded to explicit metadata;
source URL, body reference, private text, credentials, receipt payloads and
speaker Person are excluded from both the SELECT and returned response.

The source schema **does not persist a Capture→canonical media Segment FK**:
`passage` requires exactly one of `capture_id` and `canonical_segment_id`,
and media Passages use the latter. The matching Capture returned here is
therefore only independently verified *same-Content context*, and the new
contract states `capture_segment_binding=UNPROVEN` for every result. It cannot
bind this media timestamp to a particular captured media version and it never
authorizes a seek, player URL, playback, attribution, publication or rights.
This is an operator diagnosis of the missing version link, not completion of
AC-419.3. All authority flags remain false regardless of a persisted
`rights_status='CLEARED'`; a fresh DP-236 use decision would still be needed.

Adversarial readback rejects foreign Content, Capture ID/hash mismatch, missing
Candidate/Passage or wrong selector, and a canonical media interval extending
beyond the persisted Content duration. Unknown duration, unresolved transcript,
blocked segment, unapproved Candidate, pending retention, held/purged Capture
and unverified rights remain visible as **private hold reason codes**. A false
purge timestamp on a non-purged Capture is rejected, with untrusted
body/archive/purge text never copied. No new public/private route or
schema was added, and existing `/v1/media/segment` remains unchanged.

**Evidence:** First regression RED on missing source API; later a dedicated
`TRANSCRIPT_UNCERTAIN` hold test was RED until the actual hold was implemented.
After the fix:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m unittest
tests.test_dp419_media_timeline_next tests.test_studio_media_selector
tests.test_studio_capture_selectors_pg tests.test_studio_local_api -q` —
**51/51 PASS**, including
disposable PostgreSQL built from `db/schema.v1.sql` with linked synthetic
Candidate, Passage, canonical Segment and two different Capture versions;
`ruff check` on the changed Python files and `git diff --check` PASS.
No MiniPC, provider, real source, publisher, installed Studio player or
production DB was touched. **Status: IN PROGRESS; AC-419.1–.4 remain unchecked.**
The missing durable media Capture-version linkage, independently checked
playback rights and real operator seek are still external integration blockers.
