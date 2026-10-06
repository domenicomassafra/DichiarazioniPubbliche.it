# DP-304 — Privacy, minimization, and sensitive-person policy

Status: **IMPLEMENTED (deny-by-default classification); lawful basis, retention
periods, and rights workflow remain BLOCKING**
Policy version: `privacy-minimization-v1`
Owner: product owner + privacy reviewer
Code: `poc/dichiarazioni_pubbliche/policy/privacy_policy.py`
Tests: `tests/test_policy_privacy.py`

## Scope of this document

This implements the **machine-checkable** part of DP-304. It does **not** decide a
lawful basis, a GDPR role, a special-category condition, a retention period, or a
rights-request outcome. Those are Q-304-01..07 / Q-306-08..10 and remain
`OPEN`/`BLOCKING` in `legal-closure-register.md`. Where a decision was needed, the
code takes the **least public, least inferential, most reversible** branch (P-306-03).

## Data classification

| Class | Public projection | Notes |
|---|---|---|
| `PUBLIC_CORE` | allowed via allowlist + review | stable IDs, bounded provenance, approved assessment |
| `PUBLIC_SAFE_TEXT` | only when explicitly approved | sanitized claim, bounded rationale, approved notice |
| `OPERATIONAL_PRIVATE` | **prohibited** | raw/canonical transcript, evidence body, prompts, receipts, notes |
| `SENSITIVE_CANDIDATE` | **prohibited** | hold/quarantine; no automated promotion |
| `HIGH_RISK_IDENTITY` | **prohibited** | minors, victims, witnesses, exact private location, contact, ID |
| `EPHEMERAL` | **prohibited** | TTL + fail-closed purge |

Classification is a **product** decision, not a claim that a datum is legally
sensitive (the ticket says so explicitly). A reviewer may downgrade or reject a
candidate; no model may silently reclassify a high-risk item as public.

## The deny-by-default gate

`decide_projection()` runs a fixed order and fails closed:

1. unknown class → `PROHIBIT`
2. class not in `{PUBLIC_CORE, PUBLIC_SAFE_TEXT}` → `PROHIBIT`
3. field name is an operational-private name → `PROHIBIT` (even if mislabelled
   `PUBLIC_CORE` — a serializer bug still loses)
4. high-risk identity marker → `HOLD_FOR_REVIEW`
5. sensitive-category marker → `HOLD_FOR_REVIEW`
6. PII shape (email/phone/long digit run) → `PROHIBIT`
7. no recorded public-interest relevance → `HOLD_FOR_REVIEW`
8. `PUBLIC_SAFE_TEXT` without explicit approval → `HOLD_FOR_REVIEW`
9. intent/person-score language in the field → `PROHIBIT`
10. otherwise → `ALLOW`

## No trait inference (C-304-02)

The module ships **marker lists** for quarantine (`HIGH_RISK_IDENTITY_MARKERS`,
`SENSITIVE_CATEGORY_MARKERS`). They are consumed only by boolean detectors
(`contains_high_risk_marker`, `contains_sensitive_marker`). They are never
converted into a published trait, a category field, or a DataClass.
`assert_no_trait_inference()` enforces that no marker can become a `DataClass`.

A marker produces a **hold for a human**, not a claim that a person belongs to a
category. An unflagged item is not presumed safe when context is ambiguous — the
relevance gate (P-304-01) still applies.

## Public-interest relevance (P-304-01)

Public-figure status alone is **not** sufficient. Every projected item needs a
recorded reason from `REQUIRED_RELEVANCE_REASONS`:
`PUBLIC_ROLE`, `PUBLIC_INTEREST_FUNCTION`, `OFFICIAL_RECORD`,
`DOCUMENTED_PUBLIC_ACTIVITY`. A test asserts that `"IS_PUBLIC_FIGURE"` is *not* an
acceptable reason.

## Minimization (C-304-03)

`minimize_public_fieldset()` returns a sorted, de-duplicated tuple with
operational-private names, sensitive/high-risk schema names, and any person-score/
intent field removed. The sensitive/high-risk check is against the field/schema name
only; it does not inspect a person's value or infer a sensitive attribute. This is the
projection-side allowlist complement.

## Private access and content-free audit (E-304-06)

`decide_private_access()` is the pure authorization seam for local inspection of
private material. It uses a closed runtime role/purpose vocabulary, accepts only
read-only access, and rejects unknown roles, purposes, classes, modes, malformed actor
identifiers, or malformed field requests. Sensitive/high-risk classification must
already exist upstream; this helper never derives or publishes a sensitive trait.

`build_private_access_audit()` emits a minimized private receipt containing only policy
version, bounded actor/record identifiers, declared purpose, decision, bounded timestamp,
requested-field count, and legal-hold flag. Requested field names and body values are
never copied into the receipt. Contact-shaped identifiers and invalid timestamp text are
reduced to generic placeholders instead of being logged verbatim.

An active legal hold never widens access. A permitted inspection remains read-only;
`LOG`, `EXPORT`, `MUTATE`, and `DELETE` modes are denied by this seam regardless of hold
state. Destructive state changes remain owned by the existing append-only rights and
retention workflows.

## Retention interaction — no numbers invented (P-304-06)

`RETENTION_PERIODS_APPROVED = False`. `retention_decision()` returns a **class**,
never a period:

| Input | Result |
|---|---|
| legal hold active | `LEGAL_HOLD` (overrides ordinary retention, P-304-07) |
| `EPHEMERAL` | `EPHEMERAL_PURGE_ELIGIBLE` |
| any other class | `AWAITING_APPROVED_PERIOD` |
| unknown class | `AWAITING_APPROVED_PERIOD` |

Media purge still requires the existing fail-closed manifest/transcript/receipt
checks in `retention.py`; this module does not weaken them. Because no period is
approved, **no automatic deletion is scheduled from here** — the safe, reversible
branch (B-304-06 is a runtime concern; this keeps the code side honest).

## Rights requests (E-304-08/09)

`rights_request_outcome()` is a pure decision over (kind, affects_published_version,
reviewed):

- not reviewed → `OPEN_PRIVATE` (the default; a case outcome is never inferred from
  a status column);
- deletion/restriction touching a published version → `REVIEWED_PUBLIC_HOLD` (a
  reviewed hold, **not** a silent erase of history);
- correction touching a published version → `REVIEWED_CORRECTION`;
- unknown kind → `OPEN_PRIVATE`.

The key property: a rights decision never mutates a published historical version. It
routes to a reviewed correction/hold.

## Known limits

- Field classification in this module is a **name-based** deny list plus marker
  heuristics. It cannot detect a sensitive value inside arbitrary free text beyond
  the marker and PII-shape detectors, and it is not a substitute for the runtime
  field inventory (E-304-01), which remains outstanding.
- The pure private-access authorization and content-free audit contract is implemented,
  but persistence/enforcement wiring to an authenticated admin/runtime surface remains
  runtime work. Encryption, transport, incident response, and the rights-request
  *workflow* (case persistence, not just the outcome decision) also remain outside this
  pure policy module.
- No conclusion is drawn about GDPR roles, journalistic exemptions, or the Italian
  implementing law of Art. 85; see the closure register.

## Evidence basis

The one place this policy touches a verified external text is the deny-by-default
posture, consistent with GDPR Art. 5(1)(f), Art. 9(1), and Art. 89(1) as read on
2026-09-26 (see `legal-closure-register.md` S1). Those texts justify *minimizing and
holding*; they do **not** by themselves supply the lawful basis this product needs.
That remains Q-306-08, `OPEN`/`BLOCKING`.
