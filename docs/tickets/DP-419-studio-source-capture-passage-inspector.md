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
