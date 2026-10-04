# DP-302 — Right-of-reply intake threat model and abuse controls

Status: **SPECIFIED + machine-checkable; public intake DISABLED**
Policy version: `reply-intake-policy-v1`
Owner: product owner + security reviewer
Code: `poc/dichiarazioni_pubbliche/policy/intake_policy.py`
Tests: `tests/test_policy_intake.py`

## Trust boundary

```
   untrusted submitter
          |
          |  raw mapping (attacker controls the KEY NAMES)
          v
   validate_intake_payload()   <- key set checked before any value is read
          |
          |  IntakeRequest (typed, unknown keys already gone)
          v
   validate_intake_request()   <- types, bounds, URL safety, fingerprints
          |
          v
   PRIVATE / RECEIVED queue  (review required; publication is a separate gate)
```

**The submitter never crosses into a decision.** No public path can set
`status`, `publication_status`, `public_visibility`, `review_actor`,
`evidence_approved`, `moderation_decision`, `rights_status`, or `policy_override`;
these are in `RESERVED_OPERATOR_FIELDS` and refused at the edge, before the value is
even parsed.

## Threats and controls

| # | Threat | Control (code) | Fail-safe behavior | Proof |
|---|---|---|---|---|
| 1 | Spam / duplicate flooding | deterministic content fingerprint + reply ID (`compute_request_fingerprint`, `deterministic_reply_id`); bounded body/identity/URL counts | replay returns the same receipt; cannot create a second record or trigger | `IdempotencyTests` |
| 2 | Rate-limit / quota exhaustion | `rate_limit_decision()` over caller-supplied counters; unconfigured profile fails closed | defer or reject; never admit by default | `AbuseControlTests`, `LaunchProfileTests` |
| 3 | Resource exhaustion | `MAX_REPLY_BODY_CHARS`, `MAX_REPLY_IDENTITY_CHARS`, `MAX_EVIDENCE_URLS`, `MAX_REQUEST_FIELDS`, control-character rejection | reject with a bounded, non-reflective reason | `EdgeValidationTests` |
| 4 | Malicious URL (SSRF) | `validate_evidence_url()`: http(s) only, host required, no userinfo, length-bounded, duplicate-rejecting; **no resolution, no fetch** | store as a candidate reference only, or reject | `UnsafeUrlTests` (incl. a `socket` mock asserting no DNS/connect) |
| 5 | Impersonation / doxxing / personal-data flooding | bounded optional identity fields; quarantine signals for email/phone/long-digit shapes | `QUARANTINED` (private, human-routed); never auto-published, never a person score | `AbuseControlTests.test_quarantine_not_rejection_for_personal_data_shape` |
| 6 | Intent assertion by a submitter | `classify_text_intent_risk()` (DP-301) | `QUARANTINED` for a self-asserted accusation; `ACCEPTED` still private | `test_intent_language_in_body_is_quarantined_not_published` |
| 7 | Replay / forged provenance | fingerprint binds normalized body + identity + URL set + policy version | idempotent; no widened evidence links | `IdempotencyTests` |
| 8 | Review-gate bypass via field injection | raw-payload key allowlist + reserved-field refusal | `UNKNOWN_FIELD`, request refused | `ReviewGateBypassTests` |
| 9 | Information leak in the acknowledgement | `public_ack` returns only `receipt_id`, `policy_version`, `state`; `acknowledgement_is_bounded()` | bounded receipt; never an echo or an "accepted" claim | `test_public_acknowledgement_is_bounded_and_non_claimant` |
| 10 | Provider/reviewer outage | nothing in this module depends on an LLM, network, or DB | intake stays disabled; the reviewer path is unaffected | module is pure (no I/O) |

## What is deliberately NOT implemented

- **No HTTP endpoint, no CAPTCHA, no accounts, no mail, no moderation UI.** Out of
  DP-302's scope and dependent on unresolved Q-302-* / Q-306-03..05.
- **No IP/device fingerprinting.** Collecting one is an open privacy question
  (Q-302-04). `compute_request_fingerprint` deliberately hashes normalized *content
  only*. The launch profile must decide this explicitly; the code does not decide it
  by default.
- **No rate limiter state.** A token bucket is stateful; this module is pure. The
  stateful adapter calls `rate_limit_decision()` with the current counts.

## Launch posture

`INTAKE_ENABLED = False` and `LAUNCH_PROFILE_CONFIGURED = False` are module
constants. Every request is refused with `LAUNCH_PROFILE_MISSING` until an
owner/security-approved launch profile (rate, quota, retention, notice, owner,
review date, rollback) is recorded. This satisfies B-302-01 mechanically, not just
in prose.

## Residual risk

- The personal-data and intent detectors are **conservative heuristic markers**. They
  quarantine for a human; they are not classifiers and must not be read as one.
- Quarantine currently means "accepted privately with a flag", not "stored in a
  separate quarantine store". The separation is a runtime concern (DP-302 E-302-04)
  and is not implemented here.
- No abuse-incident runbook exists yet (E-302-10); it is a launch blocker B-302-06.
