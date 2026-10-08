# Studio locale: sola lettura, avvio esplicito

This capability is an **operator-only technical preview**. It is not
public Studio, a cloud tunnel, an admin approval service, production
publication, or clearance of legal, rights, identity or evidence gates.

## 1. Provision a secret outside the repository

On the machine authorized to reach the private PostgreSQL database:

    install -d -m 700 "$HOME/.config/dichiarazioni-pubbliche"
    python3 - <<'PY'
    import os
    import secrets
    from pathlib import Path
    path = Path.home() / '.config/dichiarazioni-pubbliche/studio-local.token'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(secrets.token_hex(32) + '\n')
    print('Owner-only token file created. Token never printed.')
    PY

The file must be owned by the invoking Unix user, be a regular
non-symlink file, have no group/other permissions, and contain only
64–128 lowercase hex token characters. The example creates a new
256-bit secret and refuses to overwrite an existing token. Do not
put this token in Git, terminal arguments, URLs, chats or logs.

## 2. Start only when needed

From the project root on the authorized host (typically MiniPC):

    PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.studio_local_api --token-file "$HOME/.config/dichiarazioni-pubbliche/studio-local.token" --port 18777

The listener binds **only to 127.0.0.1**. It never registers a
systemd service, VPC route, reverse proxy, Cloudflare route, or tunnel.
Access http://127.0.0.1:18777/ from the same machine. Enter the
secret locally in the password field; the browser holds it in memory
only and uses Authorization: Bearer for same-origin POST requests.

To reach the **already-running** MiniPC listener from a trusted Mac,
use an authorized SSH local-forward instead of exposing the service:

    ssh -N -L 18777:127.0.0.1:18777 minipc

Then use http://127.0.0.1:18777/ on the Mac. The token is still
required. Do not use reverse forwarding, gateway ports, port
forwarding on the router or any public domain. Stop the listener
with Ctrl-C; rotate by stopping it and provisioning a new secret.

## 3. Exact read-only interface

Eight POST routes:

- /v1/corpus/search — private DP-116 query, safe IDs only.
- /v1/collections/list — persisted collection IDs/status/INCLUDED counts.
- /v1/collections/members — bounded, cursor-paged included Content IDs,
  Source IDs and rights/processing states in one exact collection.
- /v1/collections/member — exact included Content membership inspection,
  Source existence and bounded historic claim IDs with separate cursor;
  absent captures/passages/candidates are explicitly reported.
- /v1/collections/claim-provenance — exact included Content→Atomic Claim
  text-attribution provenance, with bounded IDs/status/hash/selector
  metadata only; never quote text, source_ref, approved rights or
  current reviewer authority.
- /v1/discovery/list — persisted discovery hit/run/Content IDs and disposition.
- /v1/candidate/matches — persisted match classes and feature codes;
  currentness/reviewer authority is **not verified**.
- /v1/capture/compare — two exact capture hashes and operational states.

The unauthenticated GET / returns a **data-free** operator login
shell, protected by a fresh nonce-based CSP, X-Frame-Options and
no-store headers. The JSON API requires bearer authorization. It
refuses cross-origin requests, cookie auth, unrecognized Host,
unknown paths, all HTTP write/control verbs, oversized or malformed
JSON and any browser CORS access from unrelated origins.

The database bridge forces default_transaction_read_only=on,
statement_timeout=3000 ms, lock_timeout=1000 ms,
PGCONNECT_TIMEOUT=3 sec and an 8-second subprocess cap. Read-only
DB roles are additionally recommended; the code-level restriction
does not replace DB privilege management. Raw PostgreSQL errors,
query text, private passages, titles, source URLs, provider receipts
and private evidence never enter HTTP response bodies.

## 4. Residual blockers

This is a secure technical slice, **not acceptance closure** of
DP-415..419. The private Garlasco historical baseline can now be read
as collection→Content→Source ID→Atomic Claim ID→text-provenance
metadata. Of the 30 historical Claims, 28 have a persisted APPROVED
quote-hash attribution record and two have none. These statuses do not
grant publication, reproduction or current reviewer approval. Captures/Passages
and Candidates are still absent. Needed: full-pilot Garlasco top-K
benchmark; persisted source→passage→candidate traversal and
rights-gated previews; durable
candidate/currentness/review authority and replay-safe actions;
operator permissions/roles for any expanded admin surface; real
MiniPC corpus read-back; keyboard, actual 200% zoom and screen-reader
acceptance. No public-release or private approval gate is changed.

DP-507 remains conditional while there is no remotely reachable
admin mutation surface. Enabling one would require its complete
AuthN/AuthZ/CSRF/security acceptance **before exposure**.
