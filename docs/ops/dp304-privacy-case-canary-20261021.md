# DP-304 — real-case privacy rehearsal (21 October 2026)

Status: **engineering rehearsal only.** It proves the deny-by-default gates on one
fictional case. It is not a lawful basis, a retention period, a real data-subject
outcome, an independent review, or a publication authorization.

Executable: `tools/dp304_privacy_case_canary.py` (`python3 tools/dp304_privacy_case_canary.py`).
Fixture: `poc/dichiarazioni_pubbliche/dp304_case_fixture.py` (fictional data only).
Regressions: `tests/test_dp304_privacy_case_canary.py`.

The rehearsal reuses the existing runtime seams instead of adding a parallel
engine: `decide_projection`, `PrivacyPublicationDecisionStore`,
`PrivacyRightsAccessStore`, `build_public_projection`/`write_public_bundle` and the
loopback public API. The release directory, the PostgreSQL cluster and the
database are disposable and removed at the end; no MiniPC runtime, live database,
provider, backup or public release was touched.

## What one case proves

The fictional record is a public-role statement contaminated with raw transcript
text, an evidence excerpt, a reviewer note, contact data, an identity document,
an exact private location and sensitive markers (minor, victim, health).

| Step | Mechanism | Observed |
|---|---|---|
| Selection | `decide_projection` per field | 5 publishable fields, 9 refused or held; public-figure status alone is `HOLD_FOR_REVIEW`; a private field mislabelled `PUBLIC_CORE` is `PROHIBIT` |
| Publication | persisted review + projection revalidation replay | `dossier_count=1`, 7 public files, HTTP 200 on `/api/v1/health`, `/api/v1/index.json`, `/api/v1/findings`, `/api/v1/findings/{record}`, `/index.nt` |
| Leak scan | every written file plus every loopback response | zero private sentinels |
| Rights | `DELETION` case on the published version | `REVIEWED_PUBLIC_HOLD`, `PUBLIC_HISTORY_HOLD_REQUIRED`, published dataset SHA unchanged, `UPDATE` on the ledger rejected |
| Private access | bounded read-only inspection | authorized reviewer read allowed, wrong role and `DELETE` mode denied, audit rows contain no body and no field name |
| Revocation | superseding review with relevance revoked | decision lineage `ALLOW,HOLD_FOR_REVIEW`, `dossier_count=0`, `omitted_count=1`, stale v1 binding does not republish |

## Deny-list gap fixed by the rehearsal

`OPERATIONAL_PRIVATE_FIELDS` covered `raw_text`, `transcript_text` and `excerpt` but
not `raw_transcript`, `transcript_body`, `reviewer_note`, `asr_text` or `ocr_text`.
A serializer that mislabelled one of those names `PUBLIC_CORE` could therefore have
published private material, even though `public_http_client`, the DP-422/DP-437
canaries and the projection tests already treat `raw_transcript` as private. The
five names are now refused at the field-name boundary, and the regression fails if
any of them becomes publishable again.

## Limits

- Name-based deny list plus marker and PII-shape detectors: it cannot find a
  sensitive value inside arbitrary free text beyond those detectors.
- Retention: no period is approved (`RETENTION_PERIODS_APPROVED = False`), so the
  rehearsal asserts `AWAITING_APPROVED_PERIOD`, not a deletion schedule.
- The rehearsal uses an isolated adapter that replays the private review; production
  wiring is `production_projection_revalidation.py`.
- Article 9/10 handling, minors/victims, notices, processor controls, log/backup
  retention and per-family approvals remain with their own tickets and evidence.
