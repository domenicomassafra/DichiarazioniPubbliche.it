# DP-507 — AuthN/AuthZ/CSRF for any future admin HTTP surface

Status: FUTURE
Milestone: M5
Depends on: an approved admin HTTP surface

## Acceptance criteria

- The ticket remains FUTURE while no remotely reachable admin mutation surface exists.
- Before exposure, AuthN, role/permission boundaries, CSRF/session behavior where applicable, audit receipts, secret handling, and rate limits are specified.
- Negative authorization tests prove unauthorized callers cannot review, approve, moderate, control queues, or publish.
- MiniPC acceptance is required before exposure.

No public/admin mutation HTTP surface is part of the current architecture. Review/approval remains local/operator-only. This ticket becomes active before any administrative HTTP route is exposed.

Re-review trigger: a design or code change introduces a remotely reachable review, approval, moderation, queue-control, or publication mutation endpoint. At that point the change must define AuthN, authorization roles, CSRF/session behavior where applicable, audit receipts, secret handling, rate limits, and negative tests before exposure.

## 2026-10-10 narrow public membership addition (separate from admin authorization)

The product owner subsequently requested public registration/accounts. The opt-in
`public_account.py` Google OIDC implementation and `/accedi/` + `/account/` static
utility pages implement a **member** identity only. No member token/cookie can
authorize Studio, approval, moderation, queue control or publication. The existing
admin trigger and all DP-507 acceptance criteria remain unchanged; **Status: FUTURE**
until a remotely reachable admin mutation surface is actually proposed and safely
tested. Public-member runtime enablement also remains gated by the real OAuth
client, approved DP-304/307/702 privacy/legal controls and MiniPC canary.
The exact configuration and remaining conditions are recorded in
`docs/release/account-oidc-activation.md`.

## Checkpoint 2026-10-10 — future activation boundary

Keep FUTURE / disabled while no remote admin mutation endpoint exists. Trigger immediately **before** any owner-authorized exposure, with AuthN/AuthZ, CSRF/roles/negative tests, audit receipts and MiniPC validation. Do not build unneeded surface for ticket closure.
