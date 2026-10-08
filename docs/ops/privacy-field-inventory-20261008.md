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
