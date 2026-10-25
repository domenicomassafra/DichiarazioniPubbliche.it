# DP-234 — DVNS/read-only structured evidence adapter

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-215, DP-228; external source contract/API availability

## Problem

The DVNS sister-platform audit identified useful structured-source patterns: explicit
provenance dates, source policy, zero-vs-missing semantics, fail-closed refresh and
generated-artifact receipts. The AGPL repository is not a default code donor, and
Dichiarazioni Pubbliche currently has no direct read-only adapter for any future approved
DVNS data/API contract.

## Outcome

Define and implement a narrow provider-neutral structured-evidence adapter that can consume
approved DVNS-style records through an API/export/shared permissive schema without
importing the sister application's runtime or AGPL source code into this core.

## Acceptance criteria

- [x] Provider-neutral contract distinguishes PRESENT numeric zero from MISSING and
  NOT_APPLICABLE states.
- [x] Publication date, reference period, observed-at and effective interval remain
  separate fields.
- [x] Every normalized value retains HTTPS source URL, source record ID/version,
  deterministic adapter record ID and bounded provider receipt.
- [x] DP-215 source role/authority scope determines what the record can establish.
- [x] Provider/source BLOCKED/FAILED/DEGRADED states require an explicit blocker and cannot
  carry records or masquerade as empty-success evidence.
- [x] Unsupported schema version is rejected fail closed.
- [x] The normalized record contract contains no approval, assessment or verdict field;
  existing Evidence/Observation review remains downstream authority.
- [x] No AGPL implementation code is copied into the permissively licensed core; this is an
  independently implemented provider-neutral contract.
- [x] A pure/offline DVNS-style adapter seam preserves stable external IDs, source/schema
  versions, exact field selectors, HTTPS source URLs and opaque rights/availability status;
  explicitly private input fields are excluded from normalized records, receipts and replay
  identity.
- [x] Replay identity is deterministic and input-order independent; exact duplicate records
  collapse, while conflicting content under the same stable record identity, schema drift and
  unknown public/provenance fields fail closed.
- [x] The DVNS-style seam is read-only and candidate-only: it has no upstream write/fetch
  client, rejects verdict/publication-authority input fields and cannot confer publication
  authority.
- [ ] Wire an approved DVNS/API/export provider into this contract and DP-228/DP-215.
- [ ] Add source-specific schema/rights mapping under an
  explicit compatible licensing decision.
- [x] MiniPC canary is required before any production source family uses the adapter.

## Completion receipt

Provider-neutral structured-evidence contract plus a synthetic, offline DVNS-style adapter
fixture and focused replay/provenance/privacy tests added 2026-10-05. The adapter input schema
is an internal seam, not a claim about the current DVNS API/export schema. A real DVNS/API/export
integration remains blocked on an approved external/shared contract, compatible licensing,
source-specific rights/schema review and MiniPC canary.

DP-215 bridge proof 2026-10-06: a pure candidate-only suitability bridge binds each imported
record to an explicit `SourceProfile`, granted evidence role and exact `AuthorityScope`; imported
self-declared roles cannot grant authority. Exact metric/unit/dimension, authority-scope,
reference-period, publication-cutoff and effective-interval compatibility are retained as
pre-assessment metadata. `BLOCKED`/`FAILED`/`DEGRADED` fetch, rights, availability or profile
access state holds the candidate before compatibility is evaluated. The bridge contains no
verdict, approval, publication, network or database authority. Focused bridge tests: **7/7 PASS**;
DVNS/structured-evidence/DP-215 regression set: **44/44 PASS**; `compileall` and `git diff --check`
PASS. Complete shared suite: **1552/1552 PASS**; deterministic benchmark: **5/5 PASS**.

Final dependency-free runtime proof on 2026-10-06 runs the provider-neutral structured-evidence,
offline DVNS import and DP-215 suitability bridge as **26/26 PASS** in an isolated MiniPC
`/tmp` bundle with production/provider credentials removed. This proves the current seam on the
runtime authority but closes none of the three external ACs: there is still no approved
DVNS/API/export provider wired into DP-228/DP-215, no source-specific compatible-license/rights
decision, and therefore no production source family on which a meaningful MiniPC provider
canary can run. The synthetic contract remains candidate-only and confers no source approval.

### 2026-10-09 Wave 14 — no prefix-truncated temporal authority

The DP-215 suitability bridge previously parsed only the first ten characters
of any date-like value. Malformed statement dates, requested `effective_at`
and authority-scope effective intervals, including impossible clocks and
appended garbage, therefore evaluated as valid dates and could produce
`READY_FOR_DP215_ASSESSMENT`. The adapter now validates the **entire**
date or timestamp string and valid ISO clock/zone syntax without truncation.
Existing valid ISO dates/timestamps remain supported; field-specific DVNS
error codes remain stable. RED→GREEN tests cover malformed dates and both
authority interval endpoints. This is source-only safety, not an approved
DVNS provider, compatible license, owner scope decision, or MiniPC canary.
DP-234 remains IN PROGRESS with external ACs open.

### 2026-10-10 — Scope boundary for official Senate data

The official Senato `OpenData` RDF sitting-metadata import remains the relevant
CC BY 3.0 **metadata candidate** route under the existing DP-234 contract.
Separate Senato `AkomaNtosoBulkData` assembly resoconti are CC BY 4.0 and now
have a pure DP-233 **private speech candidate** importer; they do not constitute
an approved DVNS provider/export, a DP-215 evidence-suitability decision, or a
source-specific source-family grant for the three unchecked DP-234 ACs.

### 2026-10-10 — Real official-data HTTPS canary and independent MiniPC read-back

`poc/dichiarazioni_pubbliche/dvns_official_source_probe.py` now provides a
**disabled-by-default, manually invoked** source-specific technical probe:
`acquire_senato_official_candidate()` fetches the fixed official Senato
`OpenData/Leg19/dump-sedute-19.zip` published at
`https://raw.githubusercontent.com/SenatoDellaRepubblica/OpenData/main/Leg19/dump-sedute-19.zip`,
refuses redirects, arbitrary URLs, bad status/type/length, and archives exceeding
512,000 bytes. The existing RDF importer validates the source schema and keeps
per-field provenance; the DP-215 profile bridge then checks source role and
scope, retaining `HELD`/`DVNS_RIGHTS_BLOCKED`. It returns a bounded hash-based
technical receipt without writing Evidence, downloading other sources,
introducing a worker job, or authorizing a person, claim, verdict or publication.

Two **independent network downloads**, one on the Mac checkout and one on the
MiniPC, plus a separate Python stdlib `zipfile`/`ElementTree` reader on MiniPC,
observed the same source snapshot:

| Property | Observed value |
| --- | --- |
| Archive bytes | `29841` |
| Archive SHA-256 | `5d6b9e3ca95c51c457d26065374389090ac0ac5ca93cf91ee921db2f3c958b29` |
| Assembly sitting records | `186` (independent stdlib count matches) |
| First / last assembly ID | `http://dati.senato.it/sedutaassemblea/23908` / `http://dati.senato.it/sedutaassemblea/24093` |
| First / last sitting number | `1` / `186` (independent stdlib read-back) |
| Mac acquisition observed UTC | `2026-10-10T15:33:34Z` |
| MiniPC acquisition observed UTC | `2026-10-10T15:35:00Z` |
| Recomputed replay at original Mac observation | `dvns-replay:3c8e0a9e05475356408456e551d80c8bf9bc7b199a080d76591387a480738d3c` on both hosts |
| Source/DP-215 rights status | `BLOCKED_PENDING_PROJECT_SOURCE_PROFILE_REVIEW`; `HELD` with `DVNS_RIGHTS_BLOCKED` |

The MiniPC used a copy of the single new probe under `/tmp`, importing
the existing non-Git deployment mirror read-only. Nothing was changed in the
live worker, database, deployed source tree or publication projection. The
archive's verified *source hash* is independent of observed timestamp; the
DVNS replay identity intentionally changes with observation timestamp and
is equal across hosts only when the original timestamp is supplied for
recomputation. `verify_senato_official_readback` rejects a modified source
archive rather than accepting a changed replay or calling it a new success.
Tests also cover redirect/error/oversize/type/length rejection and absent
publication authority.

**AC accounting: 12/14 checked.** The original MiniPC canary requirement is
now technically demonstrated for the *specific Senato OpenData assembly-sitting
metadata family*, with independent source fetch, DP-215 held-state validation,
and exact cross-host receipt reconstruction. AC-14 does **not** authorize
production activation; another future source family requires its own equivalent
canary before use. The **two remaining external ACs** require a real approved
DVNS/API/export provider and an explicit project-specific compatible licensing,
schema, and rights decision. Senato's observed CC BY 3.0 OpenData metadata notice
does not grant DVNS provider entitlement, source permit, production family
authorization, reviewer signoff, archival rights, or attribution of speech.

## Post-grilling planning reconciliation — 2026-10-10

**Status unchanged; original acceptance checkboxes and dated proof remain authoritative.** This is a future target update, not source-rights approval or completion. Source: native lane A packet.

**Baseline and preserved proof:** **12/14 existing bullets checked**; the two unchecked are real approved DVNS/API/export provider integration and source-specific compatible license/schema/rights. Verified **Senato OpenData RDF** technical read-only probe: 186 assembly-sitting *metadata* records, archive SHA256 `5d6b9e3ca95c51c457d26065374389090ac0ac5ca93cf91ee921db2f3c958b29`; held DP-215 suitability/rights.

**Target delta and remaining acceptance:** Do not treat Senato RDF sitting metadata as the AKN stenographic corpus or proof that DVNS provider itself exists. The technical MiniPC RDF canary is scoped to that official metadata family; retain unmet DVNS external gates. Recheck immutable schema/right mappings for each approved integration.

**Phase / dependencies:** Phase 2 optional structured evidence; hard actual DVNS contract + compatibility decision; soft DP-215/228 B evidence and D license review; adapter owner.

**Related future specifications (separate ownership):** DP-236. These coordination links are not newly asserted hard dependencies on this existing ticket. Hold when rights, attribution, budget or actual MiniPC acceptance is absent.

### 2026-10-21 — rights-denial regression and upstream reuse receipt

The existing offline `dvns-style-readonly-evidence-v1` import and DP-215
suitability bridge remain provider-neutral, candidate-only, and Apache-2.0
core-owned: no AGPL runtime or code was imported. The DVNS sibling
[repository](https://github.com/Italian-Builders-Org/DoveVannoINostriSoldi/tree/569f8e80d6ba05c6a875781f43e53131b39ec58a)
commit `569f8e80d6ba05c6a875781f43e53131b39ec58a` (2026-10-20) has
AGPL-3.0-or-later LICENSE blob `1eb486300a202252221471cd61ecb296c147b05b`
(despite GitHub `NOASSERTION` SPDX). Reference alternatives are the
[Unlicense Data Package specification](https://github.com/frictionlessdata/datapackage/tree/da3526c4ed19563620d6a5e33ea55db6234cc411)
(commit `da3526c4ed19563620d6a5e33ea55db6234cc411`, 2026-08-25),
[MIT frictionless-py](https://github.com/frictionlessdata/frictionless-py/tree/c08fa29cb0708427ae65bb689ded8e2691078a82)
(commit `c08fa29cb0708427ae65bb689ded8e2691078a82`, 2026-10-15), and
[MIT jsonschema](https://github.com/python-jsonschema/jsonschema/tree/c497561ea0a95f5aac09cd63d15eb1420eb7bbec)
(commit `c497561ea0a95f5aac09cd63d15eb1420eb7bbec`, 2026-10-07).
Decisions, licensing and no-vendoring rationale are recorded in
`docs/donors/dvns-structured-evidence.md` and issue #42's Ricerca riuso.

The six synthetic rights regression cases (imported and profile `REVOKED`,
`DENIED`, `EXPIRED`) fail on the prior suitability implementation and hold with
explicit `DVNS_RIGHTS_*` / `DP215_PROFILE_RIGHTS_*` codes after the fix.
HELD records retain the original external identifier and provenance and do not
progress through suitability matching, Evidence, approval, verdict or publication.
This note does not amend historical acceptance checkboxes or authorize source use.

**Still uncovered:** a real approved DVNS partner API/export or separately
permissive shared contract, trusted partner identity and per-source
schema/rights/license mapping, owner clearance and a real-source MiniPC canary.
The existing official Senato probe cannot satisfy those DVNS partner conditions.
Until then #42 remains open with `needs-owner`/`later`.

### 2026-10-25 — Current DVNS public MCP: external ACs completed for one source

The upstream DVNS public **read-only MCP** (not a partner-only API) is a real
anonymous contract: `POST https://www.dovevannoinostrisoldi.com/api/mcp`, tool
`query_dataset`, dataset `opencoesione_progetti`. Its documented public access
and HTTP 200 + SSE/JSON-RPC response are independently observed. The external
rights basis is **the primary source's** OpenCoesione published CC BY 4.0 notice
at `https://opencoesione.gov.it/it/licenza/`, with source-specific private
`FETCH`/`STORE_BODY` grant, attribution and immutable receipt in the existing
private rights registry. No AGPL upstream code is copied.

The bounded adapter maps one `ricerca-e-innovazione` `projects` aggregate into
the original DVNS-style contract and DP-215 `SECONDARY_REFERENCE`; existing
Evidence/Observation stores retain separate source/snapshot SHA-256, row
selector, URL, record ID and dates. The original source is newer than DVNS:
46,437 projects as of 2026-06-30 on the primary endpoint versus 46,402 as of
2026-04-30 in DVNS. Consequently private Evidence is `SUPERSEDED`, Observation
`CANDIDATE`; no finding/claim/public projection is automatically approved.

Mac Studio resource-guard tests: **74/74 PASS** across DP-234, official probe,
MCP/rights/staleness, repository and DP-215/source-intelligence. MiniPC peer
PostgreSQL consumer `udodo` recorded a source-specific clearance valid for
30 days and an authenticated private Evidence/Observation with independent
readback (`1/1/1` rights/Evidence/Observation); simulated policy mismatch,
missing use, expiry and wrong artifact all deny. The original held Senato probe
continues to hold. Detailed evidence and ongoing software version/readback:
`docs/ops/dp329-dvns-mcp-private-evidence-20261025.md` and GitHub #329.

This completes only the two formerly unmet external ACs **for the exact
OpenCoesione aggregate**. No authority for other DVNS datasets, public
publication, arbitrary MCP tools or subscriber-only feeds follows from it.
