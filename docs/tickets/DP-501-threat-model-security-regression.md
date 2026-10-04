# DP-501 — Threat model and security regression matrix

Status: IN PROGRESS
Milestone: M5
Depends on: M0

## Outcome

Maintain one executable threat register spanning source ingest, transcripts, claims, evidence, findings, public projection, and public API. Every high/critical threat has an enforcement mechanism; critical threats name the product invariant they defend.

## Acceptance criteria

- The register covers every current pipeline/public boundary with a closed severity/status vocabulary.
- Every HIGH/CRITICAL row names concrete mitigations and enforcement evidence.
- Every CRITICAL row names the product invariant it protects.
- Enforcement pointers resolve to real repository artifacts or deterministic tests.
- Focused security regression and the full deterministic suite pass on Mac and MiniPC.
- Missing evidence or a future surface never counts as a security pass.

## Implementation receipt — 2026-09-27

- Added `poc/dichiarazioni_pubbliche/ops/threats.py`.
- Added `tests/test_ops_threat_matrix.py`, which resolves enforcement evidence to real code/config/unit/test artifacts.
- Added `docs/ops/threat-model.md`.
- Regression coverage includes source spoofing/SSRF, ingestion tampering, biometric identity, queue replay/flooding, evidence fabrication, auto-publication, future-evidence misuse, person scoring, reply leakage, projection tampering, admin exposure, secret leakage, cost abuse, retention/destructive deletion, backup exposure, and restore fabrication.

Mac full-suite validation is green. Remaining acceptance: fresh MiniPC security/runtime read-back and inclusion in the DP-702 closure packet. Do not mark DONE from Mac-only evidence.
