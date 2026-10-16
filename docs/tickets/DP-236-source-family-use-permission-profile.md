# DP-236 — Source-family acquisition/use profile with real permission decisions

Status: IN PROGRESS
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

## 2026-10-11 — First implementation slice

Source-use guard implemented as an optional exact RightsSubject/PrivateRightsRecord operation check in `private_capture_rights.py` and opt-in `capture_pipeline.py` integration (commit `acf6541`). Exact source, status, expiry, per-use and redirect/revocation checks are fail closed; public EXCERPT use is denied pending separate qualified clearance. Focused offline tests pass. No production source-family approval, DB-backed current-rights receipt or MiniPC acceptance; all original AC remain unchecked.

## 2026-10-11 — Bounded source-guard hardening (local, uncommitted)

- A `CLEARED` private use without an explicit `expires_at` previously remained permitted with no freshness deadline. The operation-time guard now returns private `UNRESOLVED / SOURCE_USE_EXPIRY_REQUIRED` with action `SET_REVIEW_EXPIRY`; this blocks before a capture fetch. A perpetual source license, if one is applicable, still needs an explicit bounded **review** validity window, independently of the license's legal duration. No rights status or expiry is minted by code.
- A malformed rights-reader result with `permitted_uses="NOT_FETCH"` previously authorized `FETCH` through Python substring membership. The guard now demands the registry's tuple-of-string contract and returns `DENIED / SOURCE_USE_RECORD_CONTRACT_INVALID` for other shapes. This protects operation-time checks even if a non-DB reader returns malformed data.
- Both cases were proven RED then GREEN by offline regression tests; existing authorized, replay, revocation, public-quote and historical preflight test paths remain covered. No issuer authentication, immutable source-version clearance, signed permission, live DB readback, or production operation was demonstrated.

Original AC-236.1–AC-236.6 remain open pending authenticated qualified decisions, complete use/artifact authority wiring, and MiniPC permit/capture acceptance. In particular, accepting a `reviewer_ref` or `rights_receipt_ref` string is **not** proof of authenticated reviewer authority, and an optional capture byte pin is not an enforced artifact-version policy.

## 2026-10-13 — Offline rights-reader receipt contract regression (worker tranche)

- RED proven in `tests/test_dp236_source_use.py`: `evaluate_source_use` returned `PERMITTED` for a synthetic current `CLEARED` record containing `rights_receipt_ref=" "`, a whitespace-containing receipt, a numeric receipt, or blank/numeric reviewer. The real `capture_content` path progressed to its fetcher with the whitespace-only receipt. These values bypassed the registry's write-time normalization when provided by an untrusted or malformed current-record reader.
- The operation-time guard now checks receipt/reviewer types, nonblank reviewer, bounded length and registry-compatible opaque receipt syntax. Malformed values return `SOURCE_USE_REVIEW_INVALID`, blocking before acquisition. The new negative tests and the existing legitimate capture, deterministic replay, current-rights re-read, revocation, expiry and final-URL redirect tests all pass (17/17 focused on 2026-10-13). No source or permission is minted.
- **Still open:** syntactically well-formed receipt/reviewer references are not cryptographic proof, qualified reviewer authentication or verified current DB authority. A crafted `CLEARED` object from a compromised reader can still claim such references; production permit integrity, source-version binding, MiniPC readback and original AC-236.1–236.6 remain pending. No remote provider or MiniPC DB was exercised.

## 2026-10-13 — P1 operator CLI guard regression (offline source-only)

- The actual `tools/capture_content.py` path calls `private_capture_rights_guard` in `capture_authorization.py`, independently of the optional `SourceFamilyUseGuard`. A baseline `HEAD` fixture ran that original operator guard and real `capture_content` with a synthetic in-scope `CURRENT/CLEARED` record, matched subject fingerprint, `rights_receipt_ref="receipt with spaces"`, and `reviewer_ref=" "`. It **accepted** the record and performed **one fake fetch, one acquisition permit, one capture, one passage and one local body write**. No live network, registry write or MiniPC DB was involved.
- The operation-time operator gate now rejects malformed receipt/reviewer refs consistently with registry normalization (opaque receipt string, nonempty, at most 512 chars, no whitespace/NUL; reviewer string, nonblank, at most 256 trimmed chars, no NUL). It also requires `permitted_uses` to be a tuple of strings before exact membership: a malformed `"NOT_RESEARCH_CAPTURE_PRIVATE"` string formerly passed as a substring, as did malformed list/tuple containers. Negative tests failed before this second fix and pass after it.
- CLI-equivalent guard/capture regression verifies **zero fetch, zero acquisition permit and zero body/passage/capture persistence** for both the forged review and malformed uses. A legitimate opaque receipt with a valid spaced reviewer name still completes offline fetch, capture, parse and one body write. Operator tests **18/18**, DP-236 and capture pipeline **43/43**, extended five-module focused suite **90/90**, Ruff, compileall and diff check passed locally.
- This closes the reproduced **operation-time malformed-review/use-list bypass** in the CLI guard only. Strings accepted as receipt references are **not** authenticated signatures or legal permission; no production current-rights/issuer validation, full source-version proof, MiniPC readback or public excerpt approval occurred. AC-236.1–236.6 remain open.

## 2026-10-14 — Attribution-constraint integrity of source-use decisions (offline)

- The optional `evaluate_source_use` reader boundary admitted a synthetic
  `CURRENT/CLEARED` record with `attribution_requirements="CREDIT_AUTHOR"`
  (a string instead of the registry's normalized code tuple). It returned
  `SOURCE_USE_PERMITTED` despite the malformed rights condition. Independently,
  two otherwise identical valid synthetic records differing only in
  `attribution_requirements=()` versus `("CREDIT_AUTHOR",)` produced the
  **same** use-decision fingerprint, concealing the changed source-use
  condition in the Capture audit fingerprint. Both cases were observed **RED**
  in focused tests before correction.
- The optional operation-time guard now validates the attribution tuple's
  machine-code shape and registry count bound, just as it already validates
  `permitted_uses`, and includes the constraints in the decision fingerprint.
  New negative cases cover a string, list, invalid/mixed tuple and excessive
  entries; a synthetic `capture_content` path proves malformed constraints
  block **before any fake fetch, Capture/Passage persistence or body write**.
  A valid changed attribution condition now yields a distinct fingerprint.
  This is a contract/audit boundary, **not** enforcement or approval of any
  claimed legal attribution duty or actual licence.
- Local, offline verification: DP-236/DP-237 and adjacent lawful-exact-quote/
  historical-corpus preflight suites **59/59 PASS**, rights-registry
  PostgreSQL/capture/schema/legacy locator/authorization suites **69/69 PASS**,
  targeted Python compilation and `git diff --check` PASS. No live rights
  decision, source acquisition, external-provider use, MiniPC readback,
  original-media locator or public excerpt release was performed.
  **DP-236 stays IN PROGRESS; AC-236.1–.6 remain OPEN** pending authenticated
  current permissions, exact source-version rights, legal dispositions and
  runtime proof. DP-237 was regression-checked but unchanged.

### 2026-10-16 — Per-source use previews, without rights escalation

Wave26's `source_inventory` now presents, for each of 11 independently observed
URL candidates, separate `catalog_link_metadata`, `fetch_source_body`,
`store_or_parse_body`, `analyze_or_translate_body`, `capture_or_transcribe_media`
and `publish_exact_quote` dispositions, plus source-specific rights evidence,
origin and required review action. All content/media operations are held while
their source-specific permissions remain UNKNOWN; a metadata link is not a
`private_source_rights_record` permit. Read-only MiniPC `psql` returned `0|0`
for all/cleared rights records. No licensed operational body capture, authenticated
decision or public excerpt approval has been established. AC-236.1–6 remain open.
