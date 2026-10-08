# Studio — historical Garlasco text-attribution provenance

**2026-10-08.** DP-416/419 private operator, actual MiniPC
`dichiarazioni_pubbliche` PostgreSQL. Read-only; no ingestion,
rights grants, reviews, public publication or provider charges.

## New inspected link

The authenticated on-demand loopback HTTP endpoint
`POST /v1/collections/claim-provenance` requires one exact
Collection, included Content and existing Atomic Claim associated
to that Content. Up to 30 provenance ledger records are returned
with keyset cursor, ID, persisted status, method, selector type,
SHA-256 source/quote fingerprints and optional positions. Claims
and provenance records must bind to the same Content and Person.

No Claim or quote text, source URL, source_ref, raw metadata,
reviewer identity, request secret or capture body is selected.
The UI selects a historic Claim from a real Content using native
buttons, creating labels with textContent only. It has no write,
approve, extract, replay or publication controls.

`APPROVED` below is the *stored provenance record state*.
The endpoint explicitly returns
`rights_clearance=false`,
`review_authority_evaluated=false` and
`publication_authority=false`: these are **not** rights grants
or fresh reviewer decisions.

## Actual MiniPC measurements

| Real check | Observed |
|---|---|
| Collection | research:garlasco, PAUSED |
| Included Content / distinct Sources | 18 / 10 |
| Historical Atomic Claims | 30 |
| Claim-text provenance rows | **28** |
| Provenance persisted state | **28 APPROVED** |
| Provenance selector | 28 TEXT_QUOTE_HASH |
| Claims without provenance | **2** |
| Historic Claim/Content/Person binding errors | 0 |
| Content rights | 18 UNKNOWN |
| Captures / Passages | 0 / 0 |
| Loopback HTML, data-free GET / | 200 |
| Exact scoped Claim provenance POST | 200 |
| Missing token / wrong Claim / cross-origin | 401 / 422 / 403 |

Focused tests cover cross-Claim/Content/Person swaps, tampered
states/hashes/positions, invalid cursor, backend error redaction
and lack of publication authority. MiniPC real HTTP canary used
an ephemeral port and disposable mode-0600 token; the process
was terminated after the test. No persistent Studio listener or
new public route was created.

This is **not** acceptance for a rights-cleared 100-item pilot,
exact Capture-backed Passage selector or full Candidate review
chain. DP-214, DP-416 and DP-419 remain IN PROGRESS. The public
release decision remains NO-GO.
