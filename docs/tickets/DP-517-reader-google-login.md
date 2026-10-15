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

## 2026-10-14 — independent hardlink escape of private account files

**New P1 beyond the prior symlink/root containment fix:** an anonymous real
loopback HTTP request could still download a hardlinked copy of the private
SQLite file under the public asset root. A hardlink shares a device/inode
with the confidential original but has a separate public path; resolving the
path stays inside the root. A forged `index.html` hardlink reached the same
bytes through the directory-default resolution. New synthetic tests were RED
for database, WAL, SHM aliases via GET/HEAD (six failures) and default index
(one failure). A separate OAuth-secret hardlink scenario was initially RED
because the programmatic server did not accept a protected-secret path.

**GREEN scoped source repair:** when the account feature is enabled, the
static-path guard checks the final directory-index target and compares the
served file's device/inode with the private account SQLite, WAL and SHM
paths (when present), plus the CLI's protected OAuth secret path. The
programmatic server explicitly accepts an optional private secret path for
the same protection and rejects it outright if placed inside public root.
Unrelated index.html assets and account 401 responses remain available.
Nine focused HTTP tests and **156/156** related account/API/privacy tests
PASS, including synthetic negative GET/HEAD, positive HTML, root index and
no provider invocation. Ruff, compileall and scoped diff-check PASS.

This is a local same-inode exposure guard, not an atomic filesystem sandbox
against a malicious concurrent filesystem writer, production MiniPC/proxy
admission, genuine secret handling or legal/retention approval. **All
AC-517.1–7 stay OPEN, ticket FUTURE; no OAuth or public account activation.**

## 2026-10-14 — authoritative MiniPC and public-reader readback (read-only)

The canonical MiniPC (`ssh minipc`, host `udodo`) has the deploy mirror at
`/home/udodo/src/DichiarazioniPubbliche.it` (`VERSION` `0.0.1`), but that
installed mirror does **not** contain
`poc/dichiarazioni_pubbliche/public_account.py`. The live public origin
`https://dichiarazionipubbliche.it/` returned HTTP 200 while
`https://dichiarazionipubbliche.it/account/session` returned HTTP 404;
an exploratory localhost port 8765 request also returned 404, but is not
treated as proof of the production routing topology. No live credentials,
private account bodies, OAuth, host configuration or production files were
read or modified. The source-only protections above are **not installed or
accepted on the MiniPC**.

**Acceptance gate / owner:** AC-517.1, .4, .5 and .7 need owner/security/legal
authorization of the exact Google OAuth application and redirect, approved
notices/retention/backup-erasure procedure, and a reversible MiniPC/proxy
installation; then an authorized synthetic/test-account registration,
re-login, logout, full-session deletion and rollback with actual public
origin readback. AC-517.2/.3 require that real installed boundary's
adversarial negative/privacy/cache tests; AC-517.6 additionally needs
accessible device/screen-reader acceptance. **Responsible:** owner for
legal/OAuth scope and genuine test identity, deployment operator for the
approved MiniPC/proxy path, accessibility reviewer for manual AT evidence.
**Observable unblock:** recorded qualified approvals and test-client
configuration, followed by an installed exact-source MiniPC canary and
public reader proof. The ticket remains FUTURE, with AC-517.1–7 unchecked;
do not enable a production login as a workaround.

## 2026-10-15 — preserve a valid browser rate bucket on session reads

**RED synthetic loopback HTTP:** After five accepted login starts using the
same signed `__Host-dp-visitor` cookie in one minute, an anonymous
`GET /account/api/session` returned HTTP 401 **and replaced the valid cookie**.
That newly signed cookie selected a fresh 5/minute throttle bucket, making the
ordinary account status check reset the advertised per-browser limit.

**GREEN local correction:** The account handler now validates and preserves
an existing signed visitor cookie when a session is unauthenticated; it issues
a new visitor cookie only when none valid is supplied. The new test asserts
first issuance, preservation on a subsequent 401 and HTTP 429 for the sixth
login attempt in the same minute. Deliberately clearing/rotating client cookies
can still evade a cookie-scoped limit; the separate durable global 120/minute
limit remains the aggregate guard. No live Google provider, credentials,
MiniPC installation or public account activation was involved.

This is a source-only repair relevant to `AC-517.2/.5`; **AC-517.1–7 remain
OPEN** pending the signed privacy/OAuth/host acceptance and real reader proof.

**Read-only host check (2026-10-15):** `curl` GET of the canonical public
`https://dichiarazionipubbliche.it/account/api/session` returned HTTP **404**.
The named `ssh minipc` metadata check found the account source absent from
`/home/udodo/src/DichiarazioniPubbliche.it/poc/dichiarazioni_pubbliche/public_account.py`.
Neither result establishes an authorized activation or installed source match;
the new local protection has not been deployed.
