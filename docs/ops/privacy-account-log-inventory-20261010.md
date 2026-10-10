# DP-304 — Optional account and runtime-log privacy inventory (2026-10-10)

## Machine-verified scope and classification

This document extends the PostgreSQL/public-schema receipt in
[`privacy-field-inventory-20261008.md`](privacy-field-inventory-20261008.md).
The checked-in canonical artifact is `config/privacy-field-inventory.v1.json`.
It now includes these separate namespaces, each with exactly one `data_class`,
`purpose`, `access_role`, `retention_behavior` and public projection decision:

| Namespace | Source | Tables / fields | Public exposure |
|---|---|---:|---|
| PostgreSQL operational columns | canonical SQL plus two migration-only fields | 100 / 1,248 | `DENY_DIRECT_DB_PROJECTION` |
| Reviewed public-schema allowlists | `public_schema.py` | 11 groups / 89 keys | Conditional on independent review and publication gates |
| Optional account SQLite | `AccountStore` literal `executescript` | 4 / 16 | `DENY_ACCOUNT_STORE_PUBLIC_PROJECTION` |
| Optional account JSON responses | `AccountService` literal `_json` response keys | 5 | `DENY_SHARED_PUBLIC_PROJECTION` |
| Optional account HTTP sensitive headers | OIDC `Location` and `Set-Cookie` | 2 | `DENY_SHARED_PUBLIC_PROJECTION` |
| Source-owned public-host diagnostic log shapes | stdlib optional HTTP logger and server-start message | 2 groups / 8 named fields | `DENY_PUBLIC_PROJECTION` |

Account `users.subject`, `users.email` and the pseudonymous throttle `bucket`
are classified as identity-relevant; OAuth verifier/nonce/CSRF and session
hashes remain operational-private. `users.email` in a session response is
personal account data and is **not** part of the publicly cacheable projection.
The account source is analyzed statically through Python AST, without executing
account code or fetching Google identity information. A new SQLite column or
private account JSON key makes the checked-in inventory drift check fail until
it receives an explicit inventory update.

The existing account implementation has technical expiry of five minutes for
pending OAuth state, 24 hours for sessions and minute-window throttling, with
opportunistic on-request cleanup. Users persist until the authenticated member
deletion operation. These **code behavior descriptions are not lawful retention
period approvals**, especially for SQLite WAL/snapshots or backups. The original
PostgreSQL rows still have no approved automatic retention expiry.

The HTTP access logger is normally quiet in the current handler. If enabled,
its `request_line` may contain the complete OIDC callback query, including
authorization `code` and `state`. This requires sanitization and a host-level
retention/security review **before enabling verbose access logs or accounts**.
The inventory records this risk; it does not claim the log is sanitized or
authorize writing it. External systemd journal retention, reverse-proxy access
and error formats, third-party identity/provider logs and backup logs are
explicitly flagged as **not verified**. These cannot be considered exhaustive
without inspecting actual enabled host configuration and logs under authorization.

## Repeatable read-only verification

```bash
python3 tools/check_privacy_field_inventory.py
PYTHONPATH=poc python3 -m unittest tests.test_privacy_field_inventory -v
python3 tools/check_privacy_field_inventory.py --verify-account-db /path/to/private/accounts.sqlite
```

The last command is optional: it opens the owner-protected SQLite database in
`mode=ro`, reads only `sqlite_master` and `PRAGMA table_info` metadata, and fails
on unexpected or missing table/column names. It never selects account records.
The PostgreSQL metadata check remains `--verify-live-db` and requires an
authorized DB connection. Neither live database is opened by the default run.

Local candidate verification: **13/13 inventory tests PASS**; static SQL
inventory **100 tables / 1,248 fields**, account **4 tables / 16 fields**,
account responses **5**, public allowlists **89 fields**, public HTTP log
shapes **8 named fields**. A disposable `AccountStore` was created and its live
SQLite catalog matched **16/16**, including a negative drift and mode check.
No production SQLite account records, MiniPC host log policy or public data
were modified or asserted to have been checked.

## Sources and legal decisions outstanding

Primary public legal guidance used as **scope and documentation context**:

- [GDPR Regulation (EU) 2016/679, Articles 5, 25 and 30 (EUR-Lex)](https://eur-lex.europa.eu/legal-content/IT-EN/TXT/?uri=CELEX%3A32016R0679): minimization, accountability, privacy by default and processing records.
- [Garante FAQ on records of processing activities](https://www.garanteprivacy.it/home/faq/registro-delle-attivita-di-trattamento): a processing register must track current reality, including changed purposes and data categories.
- [Garante principles of processing](https://www.garanteprivacy.it/home/principi-fondamentali-del-trattamento): necessity, retention limitation and security by design.
- [Garante guidance on cookies and other tracking tools](https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/9677876): technically necessary cookies and further tracking need a reviewed deployment/notice profile.

This is a code-level inventory, **not** the owner's GDPR Art. 30 processing
record, a DPIA, a legal basis, an approved privacy notice or counsel signoff.
Q-306-05 (cookies/logs), Q-306-08 (roles, purposes, personal data), Q-306-10
(retention, WAL, deletion and backups) and Q-306-14 (deployment/ePrivacy)
remain `OPEN` or `BLOCKED`. The qualified register retains those states.
**AC-304.1 remains open** until all deployed/externally persisted and logged
fields and nested payloads are reviewed, and the stated classifications,
purposes, access and retention decisions are accepted by the owner/qualified
privacy authority. The source inventory intentionally has no publication grant.
