# DP-508 — Public intake rate limiting and abuse controls

Status: FUTURE
Milestone: M5
Depends on: DP-302 and an approved public intake implementation

## Acceptance criteria

- The ticket remains FUTURE while public intake is disabled.
- Before enablement, requests are size/type bounded and malicious URLs cannot trigger server-side fetch/DNS behavior.
- Rate/quota, spam/abuse, privacy/minimization, retention, and operator-escalation controls are defined and tested.
- Public submission can never directly authorize publication or bypass review.
- Disable/rollback behavior and a MiniPC acceptance canary are proven before exposure.

The current DP-302 implementation keeps public intake disabled and fail-closed. Therefore no public intake runtime is being claimed as protected by this ticket.

Re-review trigger: enabling a public right-of-reply/correction/request intake endpoint. Before enablement, the launch profile must define bounded payloads, malicious-URL handling, rate limits, spam/abuse controls, privacy/minimization, retention, operator escalation, rollback/disable behavior, and MiniPC acceptance. No request may directly authorize publication.
