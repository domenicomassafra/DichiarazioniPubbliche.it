# DP-105 — Public schema v1 compatibility contract

Status: DONE
Milestone: M1  
Depends on: DP-101, DP-102, DP-103, DP-104

## Problem

The current projection is secure and versioned operationally, but stable public clients
need an explicit compatibility contract independent of database layout.

## Outcome

Define `dichiarazioni-pubbliche-public-v1` as a documented public schema with JSON Schema/examples,
versioning policy, required/optional fields, provenance identifiers, and correction
semantics.

## Acceptance criteria

- schema contains no raw/canonical transcript body or evidence excerpt by default;
- person/claim/finding/evidence/review/reply/correction fields are explicitly bounded;
- backward compatibility/deprecation rules are written;
- projection is validated against fixtures in CI;
- stale/tampered operational state still causes omission;
- JSON, JSON-LD, and later HTTP API derive from the same contract.

## Resolved Discrepancy

The ticket Outcome mentions `dichiarazioni-pubbliche-public-v1`, whereas the hardened runtime and
production projection emit `dichiarazioni-pubbliche-public-v2` (`PUBLIC_SCHEMA_VERSION = "dichiarazioni-pubbliche-public-v2"`).
Per ownership and architectural constraints, the runtime constant value was kept unchanged as
`dichiarazioni-pubbliche-public-v2`. The v2 contract is the authoritative, fail-closed public projection
contract. An explicit v1 alias or downgrade is a separate future external compatibility decision.

## Implementation receipt

- Created `poc/dichiarazioni_pubbliche/public_schema.py`:
  - `PUBLIC_SCHEMA_VERSION = "dichiarazioni-pubbliche-public-v2"` (unchanged)
  - `PUBLIC_FINDING_STATUSES`: `frozenset({PUBLISH, DISPUTED, CORRECTED, RETRACTED})`
  - `PUBLISHABLE_ASSESSMENTS`: `frozenset({SUPPORTED, FACTUALLY_FALSE, OUTDATED_DATA})`
  - `DOSSIER_REQUIRED_KEYS` & `DOSSIER_ALLOWED_KEYS`: explicit top-level key bounds (`claim` is bounded/optional, required keys must be present and non-null)
  - `PROJECTION_BUNDLE_REQUIRED_KEYS` & `PROJECTION_BUNDLE_ALLOWED_KEYS`: explicit projection bundle metadata bounds
  - Pure `validate_dossier` and `validate_public_bundle` validators enforcing schema rules, canonical vocabularies, recursive detection of forbidden numeric rating fields (`ratingValue`, `bestRating`, `worstRating`, etc.) and person aggregate/scoring tokens (`person_score`, `reliability_score`, `leaderboard`, etc.) in structured data and serialized JSON.
- Updated `poc/dichiarazioni_pubbliche/public_projection.py`:
  - Imports `public_schema` constants and validators
  - Validates sanitized dossiers via `validate_dossier` and the final bundle via `validate_public_bundle`
  - Fails closed: any dossier violating the schema contract is counted as omitted and never serialized.
- Created `db/migrations/20260926-add-public-schema-v1-contract.sql`:
  - Replay-safe migration wrapped in `BEGIN`/`COMMIT`
  - Creates append-only `public_schema_contract` table recording the contract version without modifying or rewriting existing table rows or projection data.
- Created `tests/test_public_schema.py` and updated `tests/test_public_projection.py`:
  - 17 unit tests in `test_public_schema.py` covering valid dossiers, missing required keys, unknown top-level keys, numeric rating rejections, person aggregate rejections, publishable/non-publishable assessments, canonical claim types, and bundle validations.
  - Added fail-closed omission verification in `test_public_projection.py`.

## Verification

Ran:
`PYTHONPATH=poc python3 -m unittest tests.test_public_schema tests.test_public_projection -v`
All 37 tests (17 in `test_public_schema`, 20 in `test_public_projection`) pass deterministically with zero network, zero DB access, and zero side effects.
