# DP-413D / #466 — Live correction HOLD (technical activation)

The opt-in `/intake/corrections` HTTP adapter binds a verified, same-origin OIDC
session and CSRF token to an append-only private DP-303 challenge. It creates a
`PRIVATE_RECEIVED` challenge that immediately yields `HOLD`, queues the existing
`REGISTER_REANALYSIS` job, purges the Cloudflare zone and confirms **three public
readbacks** (`/`, `/api/v1/index.json`, and the finding resource) have HTTP 503
with `Cache-Control: no-store`. Only then does it return HTTP 202 with a stable
request ID. The submitter may read `/intake/corrections/<request-id>` with the
same authenticated account; another account receives 404. Requests, reasons and
OIDC subject hashes remain private. The standalone, unindexed
`/segnalazioni/` form remains reachable while the published correction
register at `/correzioni/` is fenced with the rest of the projection.

Each authenticated account is limited to two attempts per minute, and the
entire listener to four per minute. `SqliteCorrectionQuota` atomically reserves
these counters in the existing private account SQLite `throttle` table across
listener processes; missing storage fails closed. An identical retry from the
original account reuses the same durable challenge and attempts queue/purge
completion again after a partial failure. It does not create a second request;
another account or changed reason cannot resume it.

This is a site-wide emergency fence: all current public projection/HTML reads
return 503 when any challenge on the public release is active or its ledger is
unavailable. This trades availability for immediate non-disclosure and has a
large production blast radius. A corrected release and reviewed DP-303 state
transition are required before this fence can clear; the reader cannot resolve
or publish a correction. The queue uses the existing automatic reanalysis
worker, with source type `PUBLIC_CORRECTION_CHALLENGE` and trigger `CORRECTION`.
It cannot claim a corrected public version without the subsequent review and
release gates. If any queue/purge/readback step fails, the HOLD remains active
and the submitter receives HTTP 503; no success is inferred from a purge API
response alone.

The persistent runner added by #464 does not by itself resolve these
public challenges. Its production review depends on distinct actual model
identities, authentic source/rights evidence, and installed consumer adapters.
The intake returns `HOLD` as long as those inputs do not justify correction or
reviewed republishing. No automatic email acknowledgment can be sent until #300
provides the real contact endpoint.

## Activation, only after independent review and consumer installation

The default public API still accepts only GET/HEAD. Opt in with the full
authenticated-account configuration and **both** purge parameters:

```text
python -m dichiarazioni_pubbliche.live_correction_cli \
  --projection-path /path/to/current-public/index.json \
  --static-dir /path/to/current-public/static \
  --host 127.0.0.1 --port 18090 \
  --account-client-id <registered-oidc-client-id> \
  --account-client-secret-file /private/account-client-secret \
  --account-db /private/accounts.sqlite3 \
  --account-site-origin https://dichiarazionipubbliche.it \
  --correction-cloudflare-zone <32-hex-zone-id> \
  --correction-cloudflare-token-file /private/cloudflare-purge-token
```

Configure PostgreSQL credentials privately for `psql` and the existing queue
consumer. Keep the Cloudflare token on a protected private path, never in static
assets, command-line arguments, logs or issues. Fail closed unless the token
can purge the *actual* public zone and public readback reaches the live
consumer. Do not enable against an unreviewed demo projection.

Cloudflare primary references: [Purge API](https://developers.cloudflare.com/api/resources/cache/methods/purge/), [Purge everything](https://developers.cloudflare.com/cache/how-to/purge-cache/purge-everything/).
The zone purge clears cached assets across the entire site; expect elevated
origin traffic. Three readback requests from one vantage point do not prove
cache invalidation across all geographic locations; the Cloudflare purge
acknowledgment supplies the distributed invalidation authority.

## Existing external dependencies and scope

- [#464](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/464) supplies the private runner (merged 26 October 2026); verify the installed consumer receives and processes the queued reanalysis job before live activation.
- [#353](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/353) supplies existing rights/withdrawal foundations; the DP-466 HTTP adapter does not infer source rights or authorize publication.
- [#300](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/300) tracks the owner's private mailbox, MX records and account access. The web status response is automatic and traceable; an email acknowledgment or a general privacy mailbox **cannot** be claimed until the real contact endpoint is operational and tested. Do not post secrets or personal email addresses publicly.

Legal and privacy boundaries rely on primary sources already collected in
[`privacy-account-log-inventory-20261010.md`](privacy-account-log-inventory-20261010.md):
[GDPR EU 2016/679](https://eur-lex.europa.eu/legal-content/IT-EN/TXT/?uri=CELEX%3A32016R0679)
and [Garante — principles of processing](https://www.garanteprivacy.it/home/principi-fondamentali-del-trattamento).
The new HTTP adapter makes no declaration of GDPR compliance or publication
clearance; minimization and purpose/retention decisions still require the
existing rights and privacy gates.

## Acceptance evidence to capture at installation

Use a **genuine** public finding and authorized test account. Record its public
ID, POST result, private request ID, job ID, GET/HEAD status from the origin,
real public CDN responses for the affected item and index/HTML, and automatic
response through the configured contact mechanism. The test suite uses only
synthetic fixtures, which do not satisfy the live acceptance criterion.

Local automated checks:

```text
python3 ~/.local/share/controlcenter/resource-guard/workload_launcher.py build -- env PYTHONPATH=poc python3 -m unittest tests.test_dp466_live_correction tests.test_dp466_cloudflare tests.test_dp466_quota tests.test_public_api tests.test_public_account -q
python3 ~/.local/share/controlcenter/resource-guard/workload_launcher.py build -- npm --prefix web run check
```
