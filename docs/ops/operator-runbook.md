# Operations runbook

The health digest is private operator telemetry. It contains aggregate queue/source/provider/provenance counts, blocker categories, SLO evaluations, and deduplicated actions. It must not contain transcript text, evidence bodies, prompts, credentials, or private reply text.

Use the blocker taxonomy in `poc/dichiarazioni_pubbliche/ops/taxonomy.py` rather than improvising recovery actions. Repeated instances of the same cause collapse into one action row. `SLO_BREACH`, exhausted dead-letter work, or other explicitly paging conditions are escalation signals; expected credential/provider blocks remain visible without being converted into fabricated success.

## Incident ownership and contact

The **primary operational incident owner is the repository owner acting as the production
runtime operator for the MiniPC**. That owner is responsible for acknowledging paging
conditions, choosing the fail-closed operational action, preserving a sanitized receipt,
and explicitly handing the incident to another owner when specialist review is required.
An unattended page is not an accepted operating state.

For a security/privacy incident, or any incident that could expose credentials, private
operational data, raw transcript/evidence material, production infrastructure, or a
publication-gate bypass, use the private reporting path in
[`SECURITY.md`](../../SECURITY.md): contact the repository owner through the same private
channel by which repository access was granted. Do **not** copy sensitive incident data to
a public issue, the public projection, or the health digest. The public security email and
public-facing complaint/contact paths are still pre-launch decisions owned by DP-702 and
the legal/privacy closure work; this internal incident route must not be misrepresented as
proof that those public contacts are configured.

## Paging decision matrix

This is the minimum representative matrix to exercise against a real MiniPC digest. The
`page`/`no-page` decision is owned by `ops/taxonomy.py`; this table is an operator-facing
rendering of that policy, not a second source of truth.

| State/cause | Decision | Operator response |
|---|---|---|
| `DEAD_LETTER` | `PAGE` | Fix the underlying cause, then requeue deliberately; never bulk-requeue. |
| `FAILED` | `PAGE` | Investigate the failed source and retire it explicitly only if it is truly gone/unsupported. |
| `OMNIROUTE_HTTP` | `PAGE` | Leave affected work blocked and investigate the configured route; do not substitute a provider/model. |
| `CLAIM_EXTRACTION_CANARY_FAILED` | `PAGE` | Keep claim fan-out disabled and preserve the failed canary receipt. |
| `SLO_BREACH` | `PAGE` | Follow the breached SLO's named action without lowering a publication or validation gate. |
| `OMNIROUTE_API_KEY_MISSING` | `NO_PAGE` | Expected credential blocker; configure the intended credential and rerun the canary before unblocking. |
| `GROQ_API_KEY_MISSING` | `NO_PAGE` | Leave audio work blocked until the intended credential is configured. |
| `DEFERRED` | `NO_PAGE` | Respect budget/rate-limit backoff; do not reset counters or change provider/model. |
| `COST` | `NO_PAGE` | Verify that the configured cap is intentional and let the budget window roll. |
| `SLO_AT_RISK` | `NO_PAGE` | Review in the routine digest; do not page solely for the at-risk state. |
| `SLO_UNKNOWN` | `NO_PAGE` | Fix the missing measurement before trusting a green status; UNKNOWN is never healthy. |

Operator rules:

- fix the named cause, not the symptom;
- never switch model/provider merely to turn a blocked lane green;
- never lower validation/publication gates;
- never hand-edit canonical transcript/evidence/finding state to clear a queue;
- never treat `UNKNOWN` as healthy;
- never publish from an incomplete restore or stale/tampered projection;
- record runtime-affecting acceptance on the MiniPC.

The private digest is extended by `poc/dichiarazioni_pubbliche/health_digest.py`; SLOs live in `ops/slo.py`; taxonomy/actions live in `ops/taxonomy.py`. DP-505 remains in progress until the representative matrix above is exercised against the MiniPC runtime and the resulting sanitized receipt is accepted.

## Local reviewer identity authority (DP-311)

Publication-review identity is not the PostgreSQL `actor_ref` string and is not provided by
the future DP-507 admin surface. While review remains local/operator-only, configure a private
reviewer-authority root outside the repository and database. The root plus `credentials/` and
`receipts/` directories must be owned by the runtime user and mode `0700`; credential and
receipt files must be mode `0600`. The authority refuses group/world-readable material.

Use `python -m dichiarazioni_pubbliche.reviewer_identity_admin` (with `PYTHONPATH=poc` in a
source checkout) to provision/show/revoke a reviewer credential and attest an exact DP-310
event. `attest-event` accepts a credential ID plus event JSON; actor and credential fingerprint
come from the private credential and a mismatch is rejected. Receipt output never contains the
credential secret.

Operational rules:

- use one distinct private credential per human reviewer expected to count toward HIGH/LEGAL
  separation; reusing one credential under different actor labels is rejected;
- revocation blocks new receipts while retained historical key material remains verification-
  only so append-only history can still be replayed;
- ordinary PostgreSQL/public-projection backup must never absorb reviewer secret files;
  protect the authority root through a separately controlled secret-backup/recovery procedure
  before production use and test that recovery on the MiniPC;
- authority loss/unavailability is a publication hold, never permission to trust DB-only rows;
- compromise of both DB and private authority root is outside this application-level guarantee
  and is handled as a security incident;
- any remotely reachable review/admin mutation endpoint still activates DP-507 before exposure.
