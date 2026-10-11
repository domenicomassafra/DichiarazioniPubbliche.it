# DP-318 — Same-take e relazioni corrette tra e dentro le Persone

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-104, DP-114, DP-219, DP-222, DP-227, DP-312

## Problem
 `relation_runtime` non ha `person_id`; stance opposte su stesso topic/proposition possono produrre position change anche fra persone distinte. `relation_policy` chiede due Finding pubblicati, impedendo confronto di opinioni in Statement non-fattuali.

## Outcome
 Versioned semantic relation classifier che usa identità, stessa proposizione/presa di posizione, speech act, polarità, tempo, luogo, condizioni e scope; distingue `CROSS_PERSON_AGREEMENT/DIVERGENCE` da `SAME_PERSON_POSITION_CHANGE/CLARIFICATION/CONTRADICTION_CANDIDATE` e permette **opinion Statement** senza Finding.

## Traceability & constraints
 R16/R18/R19; Q9–Q15. Contradizione non prova bugia, errore fattuale né intento, no score politico.

## Scope
 Inputs Statement IDs/person IDs+approved source/contexthashes, normalized proposition as *internal matching aid only*, stance polarity/modality, proposition object/entity/time/conditions/counterexample; relation candidate with rationale/conflicts, chronology/person cardinality and public eligibility on published Statement or Finding as appropriate. Review authority versioned/append-only; C graph/trace displays original quotes, corrected provenance and labels without false sameness.

## Non-goals
 No equivalence by keywords/topic or embedding score, no false opinion verdict, no ranking cross-person alignment.

## Dependencies and sequencing
 DP-312 verified speech act, public Statement target from C; no hard dependency on public Finding for non-factual opinion. Link corrected/cancelled statement events from DP-320; no need to create a chatbot.

## Acceptance criteria

- [ ] `AC-318.1`: Opposite stances by **different** persons same proposition/scope yield only cross-person divergence; same persons across times may yield position change if endorsement/scope supported.
- [ ] `AC-318.2`: Topic match, homonym, reported citation, conditional statement, different jurisdiction/period or question cannot generate an asserted same-take/contradiction.
- [ ] `AC-318.3`: Approved non-factual Statement A and B can appear in relation without any factual Finding; unverifiable opinion does not receive `FACTUALLY_FALSE`.
- [ ] `AC-318.4`: Explicit relation review/attestation, stable version/hash/identity and output privacy gating; new correction, source hash, person merge/split or context invalidates edge and read model.
- [ ] `AC-318.5`: Deterministic negative/positive fixture matrix and MiniPC public Persona/Topic/Trace readback with correct relation labels and original words after C implementation.

## Validation / proof
 Pair matrix same/different person, same/different scope, report/quote/endorse, non-factual, denial, corrections and cross-language match; inspect both store and C consumer.
## Documentation, data, and migration impact
 Existing relation schema may need additive subject/person-context bindings and upgraded relation policy instead of duplicate graph; preserve v1 edges under explicit compatibility/migration.
## Completion receipt
 non implementato; pianificazione soltanto.

## 2026-10-11 — First implementation slice

Versioned private pair-comparison preflight in `relation_runtime.py`/`relation_policy.py` (commit `d01fb22`) distinguishes same Person over time from cross-person differences, holds uncertain quote/identity/context and never grants public relation authority. 23 focused and 30 legacy relation tests pass. Legacy callers without `person_id`, independently approved semantic/reference gold, currentness/revocation and real MiniPC Trace remain to be integrated.

## 2026-10-11 — Identity placeholder regression guard (source-only)

An explicit but unresolved `person_id` such as `UNKNOWN`, `person:unknown`,
`person:unresolved` or the empty namespaced `person:` previously passed as an
identity in scoped comparisons. In two equal unresolved references the engine
incorrectly returned `SAME_PERSON_CONTRADICTION_CANDIDATE`, and in mixed pairs
it could return `CROSS_PERSON_DIVERGENCE`; the legacy compatibility function
could infer `POSITION_CHANGE_CANDIDATE` from an explicitly unresolved person.
The new syntactic guard holds scoped pairs with zero asserted person cardinality
and downgrades legacy pairs with an explicit unresolved identity to
`SAME_PROPOSITION` (unreviewed). Legacy callers omitting *both* person IDs keep
their v1 behavior pending migration. The identity string guard is **not** an
identity approval or a substitute for independently attested person resolution.

Adversarial RED: three new tests, nine failing subcases before the fix. GREEN:
the three new tests and the 56 focused DP-318/legacy relation-policy/runtime/
repository tests pass locally; public relation authority remains always false
in the scoped preflight. Status stays **IN PROGRESS**: the original AC require
reference gold, append-only relation attestation/revocation, original-quote
reader labels and MiniPC readback. No production publication proof is claimed.
