# DP-301 — Intentionality and "lie" policy (implementation)

Status: **IMPLEMENTED (engineering); legal closure BLOCKING (DP-306/DP-307)**
Policy version: `intentionality-policy-v1`
Owner: product owner
Code: `poc/dichiarazioni_pubbliche/policy/intent_policy.py`
Tests: `tests/test_policy_intent.py`

## The invariant this file protects

`PRODUCT.md`, non-negotiable:

- No inference that a contradiction proves deception or malicious intent.
- A position change is not automatically a lie.
- A false factual claim is not automatically a deliberate falsehood.

Everything below is a machine-checkable consequence of those three sentences. Where
this document and `PRODUCT.md` appear to differ, `PRODUCT.md` wins.

## The allowed assessment vocabulary

`AssessmentIntent` is the **complete, closed** set of things an assessment may be
about. Every member is a claim-level proposition:

| Member | Meaning |
|---|---|
| `SUPPORTED_BY_EVIDENCE` | the approved, time-bounded evidence supports the claim |
| `CONTRADICTED_BY_EVIDENCE` | the approved, time-bounded evidence contradicts the claim |
| `STALE_AT_STATEMENT_TIME` | the information became relevant only after the statement date |
| `UNRESOLVED_BY_AVAILABLE_EVIDENCE` | the evidence does not settle the claim either way |

There is deliberately **no member** expressing intent, knowledge, belief, motive, or
good/bad faith. `assert_no_intent_member()` runs at import time and is re-asserted
in the test suite, so adding one is impossible without breaking an import.

### Why the mapping from a relation is `None`

`relation_to_assessment()` returns `None` for **every** relation type, including
`CONTRADICTION_CANDIDATE` and `POSITION_CHANGE_CANDIDATE`. This is deliberate and is
the machine-checkable form of the invariant: a relation is *descriptive context*, not
an assessment, so there is no value for it to map to. A future caller cannot smuggle
an assessment in by reaching for a relation, because the function has no
non-`None` branch.

`relation_policy.PROHIBITED_INTENT_TERMS` remains the seed of the prohibited-term
set. `PUBLIC_INTENT_PROHIBITED_TERMS` is a strict **superset**: the ticket asked us
to extend the existing vocabulary-guard pattern, not to invent a parallel one, so the
existing guard stays authoritative and the policy adds the terms the invariant's own
prose uses (`deliberate`, `dishonest`, `mens rea`, and the Italian families).

## Prohibited public vocabulary

`scan_public_label()` returns a machine-readable reason for any label, key, or enum
value that carries:

- **intent/deception terms** — English (`lie`, `lying`, `intent`, `intentional`,
  `deliberate`, `deception`, `deceived`, `dishonest`, `bad faith`, `motive`,
  `mens rea`, `knowingly`, …) and Italian (`bugiardo`, `menzogna`, `dolo`, `disonesto`,
  `mala fede`, `inganno`, `intenzionale`, …);
- **person-score terms** — `score`, `rating`, `rank`, `credibility`, `attendibilita`,
  … , which leak the same invariant by a different route.

Matching is case-, accent-, and separator-insensitive, so `BUGIARDO`,
`bad_faith`, `bad faith`, and `MalaFede` are all caught.

## Untrusted text is held, never promoted

`classify_text_intent_risk()` classifies submitted text (extraction output, a
reviewer note, a reply body) into `ALLOWED`, `HOLD_FOR_REVIEW`, or
`PROHIBITED_LABEL`. It **never rewrites text into an intent claim**; it only decides
whether the text may be a public label at all.

The distinction between `HOLD_FOR_REVIEW` and `PROHIBITED_LABEL` matters: text that
*reports* an accusation ("they accuse him of lying; I deny it") is a different risk
from text that *makes* one. Both are non-public; only the second is a hard
rejection. A rejection is a **quarantine for a human**, not a judgement that the
submitter is wrong.

## Publishability is a fail-closed conjunction

`assess_publishability()` requires, in a fixed order: a publishable assessment; a
clean public label; an approved review event; a verification rule version; a
statement cutoff; approved evidence ids; approved observation ids; a non-stale
review; no future evidence (unless the finding explicitly evaluates a later outcome);
and recorded limitations. Any missing item is a blocker and the answer is `False`.

`FACTUALLY_FALSE` remains legal as a claim-level label. What is forbidden is
re-framing it as intentionality, which is exactly what `scan_public_label` blocks.

## Known limits

- This module is a **vocabulary and gate** boundary. It does not make the legal
  judgement about what wording is permissible in Italy/EU — that is Q-306-01 and
  Q-306-02, both `OPEN`/`BLOCKING`.
- The prohibited-term list is intentionally conservative. It may over-reject an
  unusual but legitimate public phrase; over-rejection is the intended failure mode
  and is resolved by a human, never by loosening the guard.
- The policy pins three domain-vocabulary versions. A bump to
  `CLAIM_TYPE_VERSION`, `VERIFICATION_ASSESSMENT_VERSION`, or `RELATION_VERSION`
  should trigger a re-review of this policy.
