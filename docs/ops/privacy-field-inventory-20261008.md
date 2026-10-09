# DP-304 — Complete technical privacy field inventory, 2026-10-08

This is **technical classification and drift detection**, not qualified legal
approval, an adopted retention period, a privacy impact assessment, or an
authorization to release the application. Q-306 and DP-307 remain open.

## Canonical artifact

- Versioned private-field metadata: `config/privacy-field-inventory.v1.json`.
- Check/generate: `python3 tools/check_privacy_field_inventory.py` (read-only
  by default) or `--generate` *only after deliberate review of changed DDL*.
- Production schema metadata proof: `python3 tools/check_privacy_field_inventory.py
  --verify-live-db` with the authorized PostgreSQL connection. It executes
  a read-only query against `information_schema`, not private table data.
- CI: the repository-contract job now requires the inventory to match the
  canonical DDL, two exact migration-only additions, and the public schema's
  explicit field allowlists. A new SQL column or allowlisted projection field
  requires a versioned inventory update before CI can pass.

Every persisted column has an explicit name, classification, purpose, access
role, retention behavior, direct database projection DENY decision and DDL
origin. All direct database-to-public projection is denied, even for fields
whose data classification is PUBLIC_CORE. Approved public exposure is an
independent `public_schema` plus review/rights/relevance gate, never a
consequence of being listed in this inventory.

**No retention duration is invented.** All rows say
`NO_UNAPPROVED_AUTOMATIC_DELETION`; a qualified owner/legal decision is
necessary before any timed cleanup can be authorized.

## Mac plus real MiniPC PostgreSQL readback

| Check | Observed |
|---|---:|
| Canonical `schema.v1.sql` tables | 98 |
| Migration-only `public_schema_contract` table | 1 |
| Canonical DDL columns | 1,230 |
| Historical migration-only columns | 8 |
| **Persisted table/column inventory** | **99 / 1,238** |
| Public allowlist validator groups | 11 |
| Fields explicitly named within those public groups | 89 |
| **Real MiniPC PostgreSQL columns** | **1,238** |
| Missing from production | **0** |
| Live columns without inventory classification | **0** |
| Qualified legal/privacy review complete | **No** |
| Permission to publish | **No** |

The migration-only fields are seven columns in
`public_schema_contract` created by
`20260926-add-public-schema-v1-contract.sql` and one
`claim_relation_candidate.policy_version` created by
`20260926-add-relation-approval-policy.sql`. Previously these eight were
unaccounted for when checking the base schema alone. The schema in production
was **not altered** to make the proof green.

The inventory is explicitly *deny by default*; field-name classification is
not the same thing as inspecting sensitive values or a decision about an
individual. The 89 public schema fields represent conditional schema-level
allowlists only, not approved content or an exhaustive human-reviewed data
dictionary for deeply nested dynamic payloads.

## Remaining closure before AC-304.1 / product release

The coverage proof closes the **technical persisted-column inventory drift**
gap, but does not establish purpose/retention/legal approval for every use
case, all nested JSON payload variants or external service logs. A qualified
review must inspect the classifications and purposes, establish approved
periods, verify value-level sensitive-data minimization and public JSON/JSON-LD,
HTML, API, analytics and log boundaries, and sign Q-306/DP-307 dispositions.
The public projection and private-access runtime continue to be guarded
independently. Do not mark DP-304 DONE or reduce the launch preflight's legal
blockers based solely on this technical inventory.

## DP-417 follow-up — local schema inventory refresh, 2026-10-09

The new `research_discovery_triage_decision` table in `db/schema.v1.sql`
  adds ten persisted fields: `actor_ref`, `attestation_receipt_id`, `collection_id`, `created_at`,
`decision`, `expected_revision`, `hit_id`, `payload_sha256`, `request_key`,
and `revision`. The intentionally regenerated inventory now covers
  **100 tables / 1,248 fields**, up from the 99 / 1,238 baseline above.
The public allowlist remains unchanged at **11 groups / 89 fields**.

All ten new fields have `OPERATIONAL_PRIVATE` classification,
`AUTHENTICATED_PRIVATE_OPERATOR` access, and
`DENY_DIRECT_DB_PROJECTION`; none has permission to appear directly in
the public projection. `actor_ref` and `request_key` are opaque private
operator/audit identifiers; `attestation_receipt_id` is an opaque private
reference to an off-database HMAC proof, not a signature verification result.
All require the same protection as the other
triage history fields. The inventory continues to deny legal retention
approval and publication authority by default.

Verification: `PYTHONPATH=poc python3 tools/check_privacy_field_inventory.py
--generate` and `PYTHONPATH=poc python3 -m unittest
tests.test_privacy_field_inventory -v` passed (9/9 tests). The table and
field totals above describe the **updated local canonical DDL**. The
earlier 1,238-column MiniPC comparison remains a historical readback;
this refresh neither queries nor proves deployment to the live database.
