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

## Preparatory runtime receipt — 2026-10-05

The dependency-safe local abuse-control seam now exists in
`poc/dichiarazioni_pubbliche/public_intake_abuse.py`. It consumes only the bounded result of
DP-302 validation, a caller-supplied pseudonymous bucket key, an explicit abuse profile,
an atomic caller-supplied rate store, and an explicit clock. It accepts no raw IP/source
identifier, request body, identity, URL, network handle, or provider client.

Locally proven controls: deterministic replay/idempotency, atomic per-bucket rate limiting,
global quota, explicit window reset, bounded duplicate retention and duplicate-burst
suppression, PII/policy quarantine, reserved-field quarantine signalling, bounded private
log receipts, and fail-closed behavior when profile/rate-store/clock configuration is
missing. The included in-memory store hashes the pseudonymous bucket key before retention
and the guard requires the caller key itself to be `bucket:<sha256-hex>`, so a raw IP or
source identifier is refused before rate-store access. The store uses a lock only to make
the local counter/reservation operation atomic; no DNS,
network, file, provider, schema, queue, or publication operation exists in this seam.

These proofs advance the machine-checkable portion of the second and third acceptance
criteria only. The ticket remains `FUTURE`: public intake is still disabled unless a
separate launch profile explicitly enables it. Retention/operator-escalation decisions,
disable/rollback operational proof, production rate-store integration, and MiniPC
acceptance remain open before exposure.

Local validation: `tests.test_public_intake_abuse` passes 15/15 and the existing
`tests.test_policy_intake` + `tests.test_right_of_reply_intake` surface passes 54/54;
`compileall` over `poc`/`tests` and `git diff --check` pass. Contributor acceptance reaches
the repository/version/governance/release gates but remains red on the pre-existing DP-603
fixture-inventory mismatch for `web/src/data/studio.ts`; that unrelated dirty licensing
surface is not modified by this tranche.

## Checkpoint 2026-10-10 — future activation boundary

Keep FUTURE / disabled while public intake remains off. Trigger immediately **before** any owner-authorized intake launch, with abuse/SSRF/rate/privacy/retention/rollback evidence. Never let intake imply publication authority.
