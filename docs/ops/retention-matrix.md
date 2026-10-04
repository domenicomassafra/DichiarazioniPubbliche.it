# Retention matrix

Status: technical matrix implemented; legal retention periods and rights decisions remain subject to DP-306/DP-307.

The machine-readable matrix is `poc/dichiarazioni_pubbliche/ops/retention_policy.py`. It classifies artifacts as durable provenance, durable private data, transient data, cache, or append-only receipt and names the deletion trigger/mechanism and implementation owner.

Key technical rules are intentionally conservative:

- published finding/projection history and review/provider receipts are not bulk-deleted;
- raw media may be purged only after durable transcript/hash/provenance prerequisites pass the existing fail-closed retention guard;
- raw provider payloads remain private and are not public projection data;
- evidence HTTP bodies are cache data governed by source TTLs and are regenerable;
- the health digest is an aggregate cache overwritten atomically rather than accumulated;
- backups inherit the sensitivity of the operational store and must remain private.

No numeric legal retention period, lawful basis, deletion entitlement, or rights outcome is invented here. Those decisions remain governed by DP-304, DP-306, and qualified review under DP-307.

Validation: `PYTHONPATH=poc python3 -m unittest tests.test_ops_retention_policy tests.test_retention -v`.

## Research Corpus lifecycle extension — DP-118 (2026-09-29)

The private Research Corpus adds a technical lifecycle without inventing a legal
retention period. `RETENTION_PERIODS_APPROVED` remains false under DP-304, so no age-based
automatic deletion is enabled by this work.

| Artifact/state | Technical class | Current behavior |
|---|---|---|
| `content_capture` metadata + SHA-256 | durable private provenance | Retained. A body purge clears `body_ref` but preserves the capture identity/hash and lifecycle history. |
| captured body/object bytes | transient only when the capture is explicitly `EPHEMERAL` | `POLICY_PENDING`, durable classes, quarantine, or any active legal/rights/privacy/copyright/dispute hold block purge. |
| `capture_lifecycle_event` | append-only receipt | Records archive request/pending/success/failure, body-purge request/success/failure, hold set/release, and later rights-state changes. |
| `Passage.private_text` | durable private research text | No automatic purge while retention periods remain unapproved. Never part of Public projection. |
| archive state | private operational state | `NOT_REQUESTED -> REQUESTED -> PENDING -> SUCCEEDED/FAILED`; terminal states require a non-empty receipt. A failure is never represented as success. |

Body deletion is deliberately split into three observable phases:

1. prepare in PostgreSQL (`CAPTURED -> PURGE_PENDING`) only for an explicit
   `EPHEMERAL` capture with no active hold;
2. verify the local body path is relative to the configured private storage root, refuse
   symlinks/path traversal, hash the bytes against the persisted capture SHA-256, and
   delete only after a successful dry-run/eligibility check;
3. finalize PostgreSQL state to `PURGED_BODY`, clear `body_ref`, preserve the SHA-256,
   and append a non-empty purge receipt. A failed deletion records failure/quarantine
   rather than forging a successful purge.

`purge_local_capture_body()` is dry-run by default. Capture metadata, archive receipts,
purge receipts, and extension metadata reject explicit secret-bearing keys such as
`authorization`, `cookie`, `api_key`, `access_token`, `password`, and `client_secret`.

These are engineering guardrails, not a legal conclusion. DP-304/DP-305/DP-306/DP-307
remain authoritative for unresolved periods, source-specific rights, holds, and qualified
Italy/EU review.
