# DP-235 — Bounded rights-authorized private source-to-candidate pilot

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-209, DP-210, DP-211, DP-212, DP-213, DP-236

## Problem

Production has no new real immutable Capture→Passage→Statement/Claim Candidate records, so passing pure fixtures cannot establish the first integrated source path. DP-214's 100-item Garlasco campaign is independently required, not a blocker that forces the first valid experiment to use an unauthorized 100-item corpus.

## Outcome

A bounded frozen, source-permitted pilot produces real private persisted source-to-candidate lineage on MiniPC with safe replay and honest failure receipts, ready for later autonomous verification and the public Statement slice.

## Traceability & constraints

R05, R07, R09, R10, R11, R26, R28; Q11–Q20. Source words original, speaker non-biometric, rights scoped, no automatic promotion/publication or phantom provider cost. Current source/rights gates remain active.

## Scope

Choose a versioned manifest of a small representative set including different public people and original languages where actually permitted, plus official written and optional licensed media format. Reuse Discovery, Content, immutable Capture, Passage and Candidate contracts with precise text/timed locators, hashes and source-family use decisions. Record eligibility, provenance, missing source/permission arms, source-topic/person isolate, same-source dedup, replay and negative cases in private Studio; do not expose any candidate to the public automatically.

## Non-goals

Full Garlasco 100-item acceptance, universal source coverage, automatic factual verdict, bulk historical collection or license-by-URL.

## Dependencies and sequencing

Core completed DP-209..213 are hard. Coordinate source-use authorization DP-236, selectors DP-237, document/OCR DP-238, multilingual DP-239, multi-person batch DP-240 and machine workflow DP-242 as demanded by the selected samples. **EXTERNAL:** exact source/rights grants and approved budget for each actual source/operation; if unavailable, report the precise blocked arm, not fixture-based completion. Do not add DP-214 100-item prerequisite to this smaller path.

## Acceptance criteria

- [ ] `AC-235.1`: Manifest fixes exact Content/source family, version, people/roles, language, medium, use permission and method before executing the real sample; no invented clearance.
- [ ] `AC-235.2`: An authorized written and, if authorized, media item reaches persisted Capture/Passage/Candidate with literal source selector, checksum, attribution uncertainty, correct written versus timed provenance and no fake 0:00.
- [ ] `AC-235.3`: Cross-person/foreign-source/unknown speaker, denied rights, unsupported format and provider outage are held with explicit private reasons and zero accidental publication.
- [ ] `AC-235.4`: Repeating the same version yields no duplicate logical Content/Candidates; a material change retains immutable old version and triggers a new candidate/coverage review.
- [ ] `AC-235.5`: MiniPC authoritative DB/private Studio readback reconstructs each accepted or blocked path and receipts; public corpus count and Finding/PUBLISH counters are unchanged during private intake.

## Validation / proof

Future approved sample manifest, permit IDs, content-source hashes, fixture negatives and actual MiniPC private SQL/Studio consumer readback, dedup/replay and budget ledger, with host/schema/version and redacted receipt; no source download or new provider trial in this documentation run.

## Documentation, data, and migration impact

Reuse DP-209..213 and Source Intelligence, not a second ingestion system. Persist missing format/version metadata additively if proven necessary, retain legal receipts privately, and leave DP-214's existing 100-item AC unchanged.

## Completion receipt

**2026-10-11 local source-only manifest prototype — IN PROGRESS.**
Commit `725ac0f` added `bounded_private_pilot_manifest_v1.py` and three focused
tests. The current proposal guard sorts and hashes sample descriptors, rejects
duplicate `sample_id` values and altered hashes, and never grants dispatch
authorization or source rights. It does **not** require an actual rights
reference, validate source versions/locators or People/roles, enforce eligible
media/source families, or connect to persistent Capture/Passage/Candidate flow.
Therefore this is not an accepted or authorized manifest; all five AC remain
open pending source permissions, adequate private negative-case tests and
MiniPC readback. No provider execution or public exposure has been approved.

## 2026-10-11 — Source-only manifest hardening, no runtime acceptance

Implementation now checks the **proposal descriptor** through the existing
`PrivatePilotSample` / `freeze_private_pilot_manifest` /
`validate_private_pilot_manifest` interfaces. The original seven sample
constructor arguments are retained; the added fields must be provided before
the descriptor can be frozen:

- Versioned source identity: exact HTTPS `source_locator`, named
  `source_version` and lowercase 64-hex `source_version_sha256`, together
  with a concrete `content_id` and non-placeholder `source_family`.
  The hash is an **expected input pin**, not proof bytes were fetched or
  verified. Altering source bytes requires an independently reviewed new
  manifest and immutable capture/version history later in the actual pipeline.
- Attribution and method: original `language` tag, `person_id` and
  `attribution_role` (`AUTHOR`, `SPEAKER`, `REPORTED`, `UNKNOWN`),
  `medium` (`written`, `audio`, `video`) with an explicit supported
  `media_type`. `UNKNOWN` requires no Person ID; `REPORTED` and
  `UNKNOWN` are held for attribution review. A role descriptor **never**
  attests speaker identity or verifies a political statement.
- Rights pointer: absent `rights_reference` requires all optional
  `rights_source_family`, `rights_content_id`,
  `rights_source_locator`, and `rights_version_sha256` to be absent;
  this yields `HELD`. Present `rights:<id>` requires exact equality of
  family/content/locator/version hash to that sample's scope. Even a matching
  pointer remains **unverified**: this component cannot read, authenticate,
  date-check, revoke or grant actual DP-236 per-use permissions.
  `capture_permission` remains `APPROVED_EXTERNAL_REQUIRED`.
- Bounds: at most eight unique samples, four source families and an explicit
  per-manifest `max_samples` (1–8), `budget_eur_cents` (0–10,000)
  and nonnegative `estimated_cost_eur_cents` per sample, all exact integers.
  The declared estimates must fit the budget. They are not measured charges,
  a budget reservation or permission to invoke a provider.
- Frozen integrity: rejects duplicate sample IDs, logical Content IDs,
  source-family/locator/version triples and identical declared version bytes;
  deterministically sorts rows, binds metadata and budget/status/reasons to
  a SHA-256 checksum, and **rechecks all invariants** on validation (including
  manually constructed/tampered dataclasses). A checksum is not a signature:
  only trusted surrounding review can establish document authorship.

`review_status=HELD` means the declared rights reference is absent or
the subject attribution is unresolved, with stable private
`sample_id:reason` entries in `hold_reasons`. `PROPOSED` only means
the descriptor is internally well formed and has an exactly scoped
**unauthenticated reference**; it never means rights, attribution, funding or
the source bytes were approved. Both states set
`dispatch_authorized=False` and perform no I/O, publication or pipeline
dispatch. Malformed/inconsistent descriptors fail closed with ValueError
instead of a third approval-like state.

**Test scope:** deterministic source-only unittest cases for URL/version/hash,
source family, person/role, language/media pairing, rights scope, duplicate
logical content/bytes, cap/estimate overrun, and forged manifests. This
does not satisfy the real-source portions of AC-235.1, AC-235.2–5:
permission authenticity, byte hash comparison to an actual Capture,
cross-source identity and replay in persisted DB, MiniPC/private Studio
receipt, provider budget metering, and public counter readback still require
independent live acceptance. All five original AC stay unchecked, and issue
status stays **IN PROGRESS**.
