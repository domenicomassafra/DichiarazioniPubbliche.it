# MiniPC source-mirror promotion — 2026-10-10

## Scope and authority

- Canonical Mac/source Git HEAD promoted: \`e345911c4c10e44d819d5fe816a60c8557ba7618\`
  (GitHub Actions run 38011818285, 11/11 SUCCESS).
- Target: \`udodo:/home/udodo/src/DichiarazioniPubbliche.it\`, the existing
  **non-Git** production backend/runtime mirror.
- Changes: 881 canonical Git-tracked non-\`web/\` files (source, tests,
  configuration/schema/migration *files*, operator docs and tools).
  Diff from the original mirror had 102 changes in the runtime/tool
  subset. No remote files were deleted.
- Explicitly excluded: local \`web/dist\`, uncommitted frontend WIP,
  runtime/claim credentials, Cloudflare token, live PostgreSQL migrations,
  database data, projection artifact and publisher approvals.
- This is a source/runtime hardening promotion, **not** an authorized v1
  release, a dataset re-projection, rights grant, or production migration.

## Acceptance performed before cutover

1. Took a full local same-host copy of the preexisting 275 MB runtime
   mirror, overlaid tracked source files in a **separate**, private
   candidate directory and verified source parity by checksum-mode
   \`rsync\` (zero differing selected paths).
2. On the MiniPC candidate, compiled Python source and ran **37/37**
   focused real disposable-PostgreSQL/domain tests and the deterministic
   benchmark **5/5**. An earlier focused integration pass of 67/67
   also passed in an independently staged candidate.
3. At promotion time, paused the five user-systemd worker, source-poll,
   daily-poll, health and edge-guard timers; checked that the related
   one-shot services were inactive, no worker lock was held, and the
   production queue had **zero RUNNING jobs** (30 BLOCKED and 86
   COMPLETED). No paid/provider job was invoked.
4. Stopped the existing same-origin preview web service, renamed the
   old mirror to a rollback path, moved the validated candidate into
   the authoritative path, and restarted the web service. All five
   user timers were restored to active. No database migration or SQL
   write was attempted.
5. Before and after, the static preview HTML SHA-256 was
   \`60e76f42a138b8a5fde390cee1c21c8b2053ee3f661c7a3ef78f49aebe49a1b0\`
   and the existing public projection \`index.json\` SHA-256 was
   \`adffa37fcd7c3b85af33c9c09ce0cb8b3c37925ed529894473dd5621f769dc73\`.
   Loopback GET \`http://127.0.0.1:18090/\` returned HTTP 200 and
   byte-identical response hash. The Cloudflare tunnel service had
   independently stopped cleanly during the maintenance period and
   was restarted; both Cloudflare and web service were subsequently
   observed ACTIVE, as were all five timers. Managed external ingress
   routing was not separately attested.

## Source vs installed vs published

| Layer | Observed |
| --- | --- |
| GitHub \`main\` source at promotion | \`e345911\`, CI 11/11 SUCCESS |
| MiniPC backend mirror | 881/881 selected tracked source hashes match |
| Selected source bytes | \`queue_store.py\` \`88336e08c518...\`; \`queue_runtime.py\` \`bace549711f1...\` |
| Public serving process | Restarted against updated mirror; loopback HTTP 200 |
| Existing static site / projection | **UNCHANGED**, verified by SHA-256 |
| Live PostgreSQL | **UNCHANGED**, no migrations or data write; 30 BLOCKED/86 COMPLETED jobs |
| Launch preflight | **NO-GO, 43 blockers**, unchanged |

The previous mirror is retained at
\`/home/udodo/src/.dpub-rollback-20261010-pre-e345911\` (275 MB).
Rollback requires the same coordinated timer/web service stop, a swap
back of this directory and loopback verification; it was **prepared**,
not intentionally exercised on live traffic after successful cutover.

## Why this does not close the launch backlog

The rights-UNKNOWN Garlasco corpus is still 18/100; there is no
rights-authorized Discover/Capture/Passage/Candidate chain, no
accepted OmniRoute/Groq meaningful paid-provider canary, and no
qualified legal/owner release gate for DP-307/DP-702..705. The
frontend preview build was not replaced because unresolved launch
gates and unrelated uncommitted UI work must not be silently published.
This mirror promotion does not mark any of the 39 open tickets DONE.
