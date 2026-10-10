# Public Google account activation — preparatory, disabled in production

Status: **LOCAL READY / REMOTE BLOCKED** (2026-10-10). This document records
engineering behavior, not consent, legal sign-off, Google provider acceptance,
or deployment authority. It implements the owner's later request for public
**iscrizione/account** while retaining DP-507's separate admin security gate,
DP-508's disabled public-intake gate and the zero-account public reader API.

## Local contract and trust boundary

- The default `public_api` starts **without** `account_service`, leaves OIDC
  endpoints at HTTP 404 and remains a public-projection-only reader.
- `/accedi/` and `/account/` are static, noindex utility pages. Each obtains
  account status through a same-origin, `no-store` authenticated request. They
  never embed a subject, email, session or token at build time; the public
  sitemap excludes them. Unconfigured login is shown as unavailable.
- POST `/account/auth/google` initiates Authorization Code with PKCE S256,
  one-time server-side `state`, nonce and browser-bound flow cookie. A signed,
  pseudonymous browser cookie supplies a per-bucket start limit of **5/minute**
  and a durable global limit of **120/minute**. Rate/quota is shared across
  threads through SQLite `BEGIN IMMEDIATE`; a denied start returns HTTP 429.
  Neither raw IP nor device identifier enters the throttling ledger.
- GET `/account/oauth/callback` consumes the state once, exchanges the code
  only at Google's HTTPS token endpoint, checks a server-retrieved JWKS RSA
  signature, pinned issuer, exact client audience/authorized party, nonce,
  issue/expiry times, verified email and stable Google `sub`. A wrong/replayed
  state, changed browser or invalid token never creates an account/session.
  The backend never stores the OAuth code, access token, refresh token or JWT.
- `sub` is the unique account key. Email may change after another verified
  sign-in and is only account contact/display, never an identity key or a
  person's public attribution. Session IDs are random; only their SHA-256
  digests are stored. Cookies use `__Host-`, Secure, HttpOnly, SameSite=Lax,
  Path=/ and fixed lifetime; session lifetime is **24 hours**.
- GET `/account/api/session` returns only the current member's verified email
  and an opaque CSRF value; POST `/account/api/logout` and
  `/account/api/delete` require exact HTTPS Origin, same-origin fetch, session
  and CSRF. Delete removes the member and **all** sessions by FK cascade;
  no account ever grants a review/admin/publication permission. No CORS
  permission, tokens in JS storage or redirects to user-provided URLs exist.
- Responses carry `Cache-Control: no-store, private`, `Vary: Cookie`,
  `Surrogate-Control: no-store`, nosniff, no-referrer, framing and CSP denies.
  Any configured account server must bind loopback only; the reverse proxy
  must preserve host/origin and never cache `/account/` or `/account/api/**`.
- The server's normal HTTP access log stays disabled. No callback code/state,
  verified email, Google secret or IP is emitted as a diagnostic or receipt.

## New private data classes (DP-304/307/702 review required)

| Data | Purpose | Local retention / deletion boundary |
|---|---|---|
| `users.subject` (Google `sub`) | Stable member identifier | Until member deletion; never joins public Person/Claim |
| `users.email` (verified) | Show member's account identity | Updated on new login; deleted with member |
| `users.created_at`, `last_login` | Account lifecycle | Deleted with member |
| `pending.state_hash`, `browser_hash`, `verifier`, `nonce` | OAuth anti-CSRF/PKCE | Five-minute expiry; cleanup at requests |
| `sessions.session_hash`, `csrf`, `expires_at` | Revocable membership session | 24-hour expiry or immediate logout/delete; cleanup at requests |
| `throttle.bucket`, minute, count | Pseudonymous per-browser/global abuse limit | Expired window cleanup at requests |

Local SQLite is a **separate private store**, not part of the approved
PostgreSQL inventory. It requires an owner-owned directory mode 0700 and
database 0600; `secure_delete=ON` is set for SQLite record removal. WAL,
filesystem snapshots, logs and off-host backup retention are separate controls
which qualified privacy review must settle. Expired rows are opportunistically
purged on requests; an approved unattended cleanup/backups schedule and account
data-erasure procedure are still required before remote activation. No source
uploads, private dossiers or other personal records are linked to members.

## Required before enabling on MiniPC

1. Product owner confirms purpose, terms, identity-controller/contact channel,
   retention and backup-erasure periods. Qualified privacy/legal reviewer
   accepts DP-304/307/702 treatment of the new SQLite data classes, Google
   as identity provider, account deletion and necessary user disclosures.
2. Register the real Google Cloud OAuth **Web application** (client ID and
   client secret), consent screen and allowed redirect URI exactly
   `https://dichiarazionipubbliche.it/account/oauth/callback`. Never paste
   client secrets into Git, browser JavaScript or a static file. Use a regular
   private secret file with owner UID and mode 0600, inside a 0700 directory.
3. Install the explicit backend account crypto profile (`pip install
   '.[account]'`) in the target runtime. Supply **all four** opt-in arguments
   `--account-client-id`, `--account-client-secret-file`, `--account-db`,
   `--account-site-origin https://dichiarazionipubbliche.it` when starting the
   existing public host. Omission of any argument must refuse startup; omission
   of all keeps the account backend disabled. Confirm runtime binds 127.0.0.1.
4. Validate the same-origin HTTPS reverse proxy end to end on MiniPC. Deny
   external access to loopback ports, strip untrusted forwarded host/identity
   headers, refuse cross-origin POST and cookie duplicates, preserve Secure
   cookie headers and **never cache authenticated responses**. Verify no
   Studio/admin endpoint accepts member cookies or allows member mutation.
5. Execute real Google OIDC sign-up, same-account re-login, wrong-state replay,
   rejected hostile origin, expired nonce, logout and account deletion with
   an authorized test account. Independently inspect private DB permissions,
   expiry, rate limit, and backup/restore/delete receipts. Run browser phone,
   keyboard, zoom, reduced-motion and screen-reader review of both account
   pages. Disable/rollback to the default read-only host if any step fails.
6. Update public policies, privacy register, retention jobs, security runbook,
   owner/legal approvals and deployment evidence. DP-508 public submission
   remains disabled; accounts do not make submissions publishable or reviewed.

## Local validation (does not establish remote GO)

`PYTHONPATH=poc python3 -m unittest tests.test_public_account
tests.test_public_api tests.test_public_web_boundary -q` validates signed
RS256 JWTs and adversarial live loopback HTTP flows. The optional crypto
profile must be installed for the signed-JWT cases to run without skips.
`cd web && npm run check`, and an **explicit local demo-only** build with
`DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build` plus
`npm run check:routes && npm run check:quality` validate frontend routes and
noindex boundaries. A demo build must never be deployed or called a signed-off
public projection.

**Release decision:** account source and pages can be reviewed locally; live
Google OIDC, user privacy/retention, operator abuse controls and MiniPC proof
remain `BLOCKED`. No credentials, external deployment, provider validation
or legal sign-off is claimed by this record.
