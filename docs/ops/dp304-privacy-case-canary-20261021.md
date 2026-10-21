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
| Rights | `DELETION` case on the published version | `REVIEWED_PUBLIC_HOLD`, `PUBLIC_HISTORY_HOLD_REQUIRED`, byte-for-byte identical release files, `UPDATE` rejected by the append-only trigger |
| Private access | bounded read-only inspection | authorized reviewer read allowed, wrong role and `DELETE` mode denied; the complete persisted audit rows are scanned for every sentinel and for the field name, and the event count and outcomes are read back |
| Revocation | superseding review with relevance revoked | decision lineage `ALLOW,HOLD_FOR_REVIEW`, release rewritten, `dossier_count=0`, `omitted_count=1`, the three claim artifacts and the record route return 404, collection routes stay 200, the original decision row is still readable, a stale v1 binding does not republish |

## Deny-list gap fixed by the rehearsal

`OPERATIONAL_PRIVATE_FIELDS` covered `raw_text`, `transcript_text` and `excerpt` but
not `raw_transcript`, `transcript_body`, `reviewer_note`, `asr_text` or `ocr_text`.
A serializer that mislabelled one of those names `PUBLIC_CORE` could therefore have
published private material, even though `public_http_client`, the DP-422/DP-437
canaries and the projection tests already treat `raw_transcript` as private. The
five names are now refused at the field-name boundary, and the regression fails if
any of them becomes publishable again.

## Scope of the selection proof

`CASE_FIELDS` classifies **14 fields of this case**, not the whole projection
allowlist: the dossier published from this row also carries assessment, rationale,
bounded dates, evidence metadata and provenance, which the projection allowlist
admits and the sentinel scan covers. The persisted replay in this rehearsal binds
`normalized_claim`; the other allowlisted fields are checked at the gate level.

## Retention

The rehearsal reads `RETENTION_PERIODS_APPROVED is False`, expects
`AWAITING_APPROVED_PERIOD` for operational-private data and `LEGAL_HOLD` when a hold
is active. No period is approved, so no deletion is scheduled from this case.

## Limits

- Name-based deny list plus marker and PII-shape detectors: it cannot find a
  sensitive value inside arbitrary free text beyond those detectors.
- Retention: no period is approved (`RETENTION_PERIODS_APPROVED = False`); the
  rehearsal proves the class decision, not a deletion schedule.
- The rehearsal uses an isolated adapter that replays the private review; production
  wiring is `production_projection_revalidation.py`.
- Article 9/10 handling, minors/victims, notices, processor controls, log/backup
  retention and per-family approvals remain with their own tickets and evidence.
