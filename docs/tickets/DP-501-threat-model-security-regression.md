# DP-501 — Threat model and security regression matrix

Status: DONE
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

## Final runtime receipt — 2026-10-06

- Candidate commit: `5a86666bf3bb955f18e036c010e53613425a6cf6`; `origin/main` points at the same commit.
- An independent detached Mac clone passed the focused threat/retention command and the full deterministic suite: **1720 tests OK**.
- The MiniPC mirror's tracked-file Git blob manifest matched the candidate commit exactly. On that mirror, `tests.test_ops_threat_matrix`, `tests.test_ops_retention_policy`, and `tests.test_retention` passed together (**29/29**), and the full deterministic suite passed **1620/1620** with 12 skips.
- No missing or future enforcement surface was converted into a pass; the threat register still fails closed on absent evidence.

DP-501 is technically complete. DP-702 must consume this security/runtime receipt in its pre-launch closure packet; that handoff remains a launch-review dependency rather than missing DP-501 implementation evidence.
