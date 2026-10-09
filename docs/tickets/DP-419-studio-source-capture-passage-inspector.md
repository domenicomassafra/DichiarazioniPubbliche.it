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
