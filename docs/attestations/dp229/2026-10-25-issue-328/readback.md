# DP-229 / #328 — private source challenger canary, 2026-10-25

This is a bounded **HOLD** case, not an approved counter-case, high-risk
review, source clearance, or publication authorization. The source is real;
the Coverage Need and claim ID are explicitly synthetic and private.

## Source, question and rights

- Case: test whether a Senate S.1 *proposal* could be mistaken for a law in
  force. Original versioned Senate material and the two AI reviews are
  documented in [the 2026-10-21 attestation](../2026-10-21-senato-s1/attestation.md).
  They remain `NEEDS_MORE` and are not reviews of a live canonical Finding.
- Research source: `official-camera-temi`, the Italian Chamber of Deputies'
  [official RSS directory](https://documenti.camera.it/apps/rssFeeds/index.asp),
  with the exact feed URL
  `https://documenti.camera.it/rss/temi/bridgeTemiEvidenzaRss.xml` from
  `config/source-registry.v1.json`. The source is `public_rss`, metadata-only,
  `rights_status=RIGHTS_HOLD`. No text, media, or transcript body is imported.
- Rights assessment as of 2026-10-25: the Chamber's
  [legal notice](https://comunicazione.camera.it/policy/en_avvisolegale)
  restricts use/reproduction of its content (including noncommercial purpose,
  attribution and restrictions on derivative works); an accessible public RSS
  feed alone is not an unrestricted reuse or publication license. This test
  keeps the source metadata in a disposable private ledger and grants no
  rights clearance to its content or any Senate material. No personal data
  beyond publicly published institutional metadata was requested.

## Observed bounded execution

On 2026-10-25 the existing `tools/dp229_official_rss_canary.py` was executed
on Mac Studio through the resource guard against a newly created, private
PostgreSQL cluster at `/tmp/dp229-328-canary-20261025` (Unix socket, directory
mode 0700; no production database access). The received JSON reported:

| Provenance / observation | Value |
| --- | --- |
| Receipt observation | `2026-10-25T15:28:07.900615+00:00` |
| Run ID (historical scenario label, not an execution date) | `run:dp229:senato-s1:official-camera:20261022` |
| Request ID | `challenger-research:2bf438151372409d009272f5fb374a2dd6a30d6a09665d52e0aa531b27f1f5b5` |
| Manifest SHA256 | `1c55d2880d8b9215e741965e6f08c65685d232f3857769c3d5cb4d81b4eee14d` |
| Query/result/per-host caps | `1 / 2 / 1`, adapter `configured_registry` |
| Run/attempt | `COMPLETED`; one `HEALTHY`, zero blocked or failed |
| Raw/accepted hits | `0 / 0` |
| Ledger cost / cap | `0.000000 / 0` USD (not a provider billing invoice) |
| Replayed ledger | Identical; `readback_replay_equal=true` |
| Disposition and authority | `HOLD`; `publication_authority=false` |

No hit is not evidence that the underlying claim is true or false. A `HEALTHY`
attempt proves only that this configured adapter completed its bounded
discovery operation; it does not prove comprehensive contrary-source coverage.
The new `attempt_started_at_utc` field is read from the durable attempt row;
`new_healthy_attempt_this_invocation` distinguishes a newly persisted healthy
attempt from a replay of the same private state directory.

## Consumer and unresolved acceptance

Read-only MiniPC check on 2026-10-25: `dichiarazioni-pubbliche-web.service`
returned `active`; `127.0.0.1:18090/api/v1/health` returned `status=ok`,
`contract_status=DRAFT`, `dossier_count=0`, `omitted_count=0`. This is a
consumer availability check, not a high-risk challenger transaction.

The real authenticated AI challenger review of an *exact current* material
inventory, with current source-specific rights in the operational database,
bounded research completion, append-only incorporation into the correct
Finding/version and an independently attested review/revocation replay are
still missing. The prior Sol/Gemini analyses have outcome `NEEDS_MORE`, and
the dependency #332 remains open. The high-risk runtime must continue to
reject caller-supplied READY/waiver decisions. No production DB mutation,
publishing, provider purchase, or deployment is authorized by this receipt.
