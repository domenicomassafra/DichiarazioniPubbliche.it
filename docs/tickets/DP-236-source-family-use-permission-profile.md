# DP-236 — Source-family acquisition/use profile with real permission decisions

Status: FUTURE
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-210, DP-305

## Problem

Current source/evidence allowlists and observed licensing metadata can coexist with zero source-specific private capture permits. `rights_status=UNKNOWN` remains normal in Garlasco and Senato AKN. An official domain, HTML reachability, CC license for a **different dataset**, or source role must not silently authorize fetch/storage/transformation/excerpt.

## Outcome

Every operational source-family action has an inspectable effective *acquisition/use* decision bound to exact family/artifact/version and use kind, read at operation time with revocation/freshness checks. The qualified legal interpretation and **public excerpt** authority remain B/DP-305's remit; A implements its input enforcement and audit path.

## Traceability & constraints

R08 interface, R09/R10/R05/R25, owner Q15–Q20. Separate license for underlying text, third-party transcription/translation, attached media, site photos, archives, platform terms, and publication; do not adopt blanket legal rules.

## Scope

Reuse `rights_registry`, `private_capture_rights`, `capture_pipeline` rights-guard hooks, `source_intelligence` exact scoped role/authority and DP-305 decision version. For each `DISCOVER_METADATA`, `FETCH`, `STORE_BODY`, `PARSE/OCR`, `TRANSLATE`, `ASR/MEDIA`, `ARCHIVE`, `EXCERPT_PUBLIC` operation, model explicit permitted/denied/unresolved/expired/revoked and reason/evidence URL, effective time, source family, artifact, medium, retention, person/privacy flags. Discovery metadata may be allowed while body capture is denied. Signature/actor authority must be authenticated without minting rights from normal model output. Do not leak confidential legal notes publicly.

## Non-goals

Issuing legal clearance within software, universal copyright threshold, bypassing B's public quote gate or cancelling safe metadata lookup.

## Dependencies and sequencing

Hard DP-210/215/305; external qualified source-specific policy disposition and host/provider terms, soft B rights/citation and D production launch set. AKN CC BY4.0 must be evaluated only against its immutable repo artifact; OpenData RDF CC BY3.0 independently; DVNS external unrelated.

## Acceptance criteria


- [ ] `AC-236.1`: Permit is bound to exact source family, artifact, use type, policy version, rights evidence and validity; unsupported/unknown families produce specific private blocked state before fetch or model work.
- [ ] `AC-236.2`: A record cleared for metadata discovery cannot be reused for body store, OCR, transcription, public quote or WebTV; tests cover differing dataset licenses and derivative works.
- [ ] `AC-236.3`: Expired/revoked/superseded permit causes a fresh guard failure before and after acquisition race where feasible; persisted old receipt never changes to CLEARED silently.
- [ ] `AC-236.4`: An approved bounded private use follows existing Capture/retention path; exact replay is idempotent and records permit fingerprint; a changed permit creates auditable new decision.
- [ ] `AC-236.5`: Operator sees resolving authority, missing evidence and specific unblock route; public readers see neither private rights notes nor raw body.
- [ ] `AC-236.6`: MiniPC permit/capture readback proves both successful authorized and denied attempts; zero accidental writes/charges on denied branch.

## Validation / proof

Source-family decision IDs, dated immutable licensing/source terms where applicable, reviewed policy refs, negative permission matrix, MiniPC guard/readback and revoke/replay. **Decision is required externally; this ticket does not grant it**.

## Documentation, data, and migration impact

Extend existing registry schema only where current `RightsSubject` cannot express use-specific artifact/medium. Preserve immutable decision history and purge/retention traces; B owns legal wording/cutover policies.

## Completion receipt

**NOT IMPLEMENTED — planning only**.
