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
