# DP-517 — Reader Google sign-up/login/logout/delete MiniPC activation

Status: FUTURE
Milestone: M5 — reliability, security, operations, and data lifecycle
Depends on: DP-304, DP-307, DP-501, DP-502

## Problem
 public_account.py and the static /accedi/ + /account/ pages contain a local opt-in Google OIDC contract, but account routes were live 404 at 2026-10-10 reconnaissance; real OAuth consent, privacy/retention/secret setup and MiniPC host acceptance are absent. Showing the presence of local source as a publicly working login would mislead users.

## Outcome
 Owner-approved Google first-time registration and recurring login, same-origin session, logout, account deletion/erasure with clear privacy and availability/error UX, disabled by default unless all gate inputs are present. No member identity can become editor, Studio admin, verifier, public source subject, or right-of-reply approver. Unauthenticated readers continue to read approved projection.

## Traceability & constraints
 R37/R25, 2026-10-10 owner account request. Existing docs/release/account-oidc-activation.md is implementation evidence; future legal/profile acceptance still absent. Google OIDC client secret, signed ID-token validation, PKCE S256/state/nonce, exact HTTPS origin, secure HttpOnly cookie, CSRF, one-time flow, 5/min browser and 120/min global throttling are existing local design, not proof of production protection. Privacy applies to separate SQLite account store, WAL, backups/logs and erasure, not only PostgreSQL.

## Scope
 Real owner Google Cloud web OAuth client and exact redirect registered outside Git, approved consent/legal basis, account-specific notices/contacts, retention/erasure/backups, rate-limit failure controls, 127.0.0.1 private service behind explicitly configured same-origin proxy, consistent logout/delete all sessions, no-store/cache/header checks, mobile/keyboard/screen-reader treatment, security runbook/circuit-breaker. Test genuine registration/re-login under owner-provided test identity and deleted/revoked session readback. Disabled states show unavailable without broken fake “sign in” CTA. Privacy deletion waits for qualified backup retention decision; no dishonest claim of erasing immutable off-host snapshots instantly.

## Non-goals
 Admin interface, contributor intake, paid accounts, bookmark/feed/chat, person verification, allowing Google account to bypass source rights or publication policy.

## Dependencies and sequencing
 An account may be enabled when approved independently of stable editorial v1 if its own legal/security/host gates are signed; it must never be mistaken for approval of source ingestion or public intake. If accounts are not selected for a given release profile, record signed disabled applicability/trigger while preserving the roadmap commitment. Coordinator maps hard dependency accurately without forcing all of DP-702 stable-v1 closure when qualified scope can approve the account separately.

## Acceptance criteria

- [ ] `AC-517.1`: Real owner-authorized new Google member signs up then re-logs as same stable Google sub (email changes do not duplicate identity), with exact origin/callback and protected headers.
- [ ] `AC-517.2`: Invalid/replayed state, nonce, signature, issuer/audience, cookie, CSRF, hostile origin, cross-site request and expired session all deny mutation and never create/store identity.
- [ ] `AC-517.3`: Member session grants zero Studio/review/admin/publication/intake capability; static pages and API responses expose no PII to public build, indexing, CDN or cache.
- [ ] `AC-517.4`: Logout invalidates one session, account deletion invalidates ALL sessions and the member row; retained WAL/backups/logs follow the signed erasure timetable and auditable completion/refusal.
- [ ] `AC-517.5`: Credentials, private DB, proxy origins, rate stores, HTTPS, no-store and loopback/MiniPC route readback all pass; absent/incomplete config disables service.
- [ ] `AC-517.6`: Mobile 320/390/768, keyboard, reduced motion, zoom, screen-reader and disabled/error flow are accepted; unauthenticated public-reader routes remain operational.
- [ ] `AC-517.7`: Rollback disables account endpoints without touching public projection or losing existing private audit in violation of retention; owner/security/legal approval references are current.

## Validation / proof
 Reuse existing local OIDC tests and adversarial loopback harness, then future permitted real Google test-account MiniPC canary; inspect proxy and headers/cookie behavior, SQLite 0600/dir 0700, backup/restore/erase, public host URL and reverse proxy. Retain sanitized evidence only, never tokens, secret or email.

## Documentation, data, and migration impact
 Single owner-approved account launch/runbook and private SQLite data/retention registry, no new Postgres membership grant; alias to existing account OIDC activation document. Public route/SEO and privacy-policy updates under their existing owners.

## Completion receipt
 Not implemented/activated remotely; planning only. Future exact signed owner scope, Google registration/redirect, runtime hash, account lifecycle + erasure results, MiniPC before/after route/public readback and rollback record.

## Source-only redirect origin regression — 2026-10-14

The opt-in OIDC service previously accepted any syntactically valid HTTPS `.it`
host as its configured `site_origin`, including unrelated and lookalike domains.
The owner account activation runbook specifies the single registered callback
`https://dichiarazionipubbliche.it/account/oauth/callback`; an unapproved
origin could therefore be used to construct a Google authorization redirect
outside that reviewed host boundary. A RED regression reproduced admission of
unrelated, lookalike and `www` origins. `AccountService` now admits only the
canonical configured origin, retaining the original HTTP/HTTPS syntax check.
The regression and existing local account, web-boundary and privacy inventory
tests pass offline. This is a source hardening result for AC-517.2/5 only;
real client registration, lawful handling and retention/backup acceptance,
MiniPC proxy/host readback, live token, deletion and UX evidence remain OPEN.

## Source-only private account file containment — 2026-10-14

**RED real local HTTP, synthetic only:** With an opt-in `AccountService` backed
by a temporary 0600 SQLite file and `static_dir` aimed at that same directory,
an anonymous `GET /accounts.sqlite3` returned HTTP **200**, SQLite bytes and a
synthetic user's email. The public host inherited static file serving without
verifying separation from the private account store. An additional public
symlink to an out-of-root SQLite file also returned 200; a configured OAuth
client secret inside the public document root passed CLI admission. The new
DP-517 regression reproduced all three fail-open paths before the fix.

**GREEN local correction:** `build_server` now refuses any activated account
store whose resolved SQLite path is under the selected static document root.
The account CLI separately refuses an OAuth secret or SQLite DB whose resolved
path falls inside that root, before constructing an account server. With
accounts enabled, static GET and HEAD also refuse symlinks escaping the root,
including aliases to account data. Ordinary site HTML GET/HEAD and the
unauthenticated session endpoint retain their previous behavior when private
files are outside the served root. No Google code exchange, live credentials,
public host or production database was involved.

These are bounded source-only protections relevant to `AC-517.3` (private
account data absent from public static routes) and `AC-517.5` (safe local
configuration). They neither authorize remote Google OAuth nor prove actual
MiniPC/proxy/CDN configuration, privacy erasure of WAL/backups, legal review,
browser accessibility or owner-approved rollback. **All original AC-517.1–7
remain unchecked; DP-517 remains FUTURE, account launch disabled.**

**Source verification:** focused DP-517 account HTTP, existing account,
public API/HTTP and privacy-inventory suites **121/121 PASS**, scoped Ruff
check, new-test Ruff format, Python compilation and `git diff --check` PASS.
The pre-existing `public_api.py` does not pass whole-file Ruff format on its
unchanged baseline; this narrow correction does not reformat unrelated code.
Only synthetic local files and ephemeral loopback HTTP were exercised.
