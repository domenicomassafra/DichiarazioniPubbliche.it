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

## 2026-10-12 — Scoped same-take, polarity and Capture lineage guards (source-only)

The existing `evaluate_scoped_statement_relation` had three distinct
fail-open paths. Two Statement candidates could claim the same unresolved
namespaced proposition, equivalence-review or jurisdiction/subject/location/
qualifier reference (e.g. `review:unknown`, `jurisdiction:unresolved`), and
receive `CROSS_PERSON_AGREEMENT` because only whole-string placeholders were
checked. A positive assertion and an explicitly **negated** endorsed assertion
produced by the real Italian speech-act assessor could receive that same
agreement label when the caller supplied matching `position`/proposition,
because the classifier ignored source-receipt polarity. Finally, two different
Statement IDs assigned to **different statement dates** for precisely the
same captured source part, bytes, quote span and person produced a fictitious
longitudinal `SAME_PERSON_REAFFIRMATION`.

The scoped evaluator now holds unresolved segmented metadata references,
incompatible speech-act polarity, and the same captured quote reused as a
separate dated utterance for the same Person. All outcomes remain private
hypotheses and preserve the existing binding hash/version and non-publication
authority. Distinct source parts with a repeated wording remain independently
eligible for *candidate* comparison. The historical same-day candidate fixture
is preserved; same-day aliases still require independent store/reviewer
deduplication and must never be interpreted as automatically published facts.

Adversarial pre-fix **RED**: five real-function tests yielded **12 failing
subcases** (one polarity, one Capture-span reuse, six proposition/equivalence
placeholders, four scope placeholders). Source-only **GREEN**: new 5/5,
DP-318 legacy 26/26, `test_relation_runtime` 5/5 and `test_relation_policy`
13/13; `compileall` and `git diff --check` passed. This addresses bounded
negative fixture portions of **AC-318.1/.2/.5** only. The original AC-318.3
requires actually approved non-factual Statements and a consumer; AC-318.4
requires independent identity and equivalence review, append-only attestation,
revocation/currentness and projection gating; AC-318.5 still requires real
MiniPC Person/Topic/Trace readback and source rights. No original AC or ticket
is newly marked DONE, no source rights or public authority is inferred.

## 2026-10-14 — One captured utterance cannot substantiate two relation endpoints

An additional source-only fail-open remained after the different-day,
same-Person alias guard. With **two different Persons** and distinct Statement
IDs but the *same* source-part reference, immutable source hash, quote
boundaries and quote hash, independently hashed lexical receipts incorrectly
yielded `CROSS_PERSON_AGREEMENT`. The same captured utterance aliased under
two Statement IDs **on the same day** yielded `SAME_PERSON_REAFFIRMATION`.
Both misrepresent one captured utterance as independent relation evidence.

**RED:** two adversarial tests reproduced both false assertions against the
original evaluator (`CROSS_PERSON_AGREEMENT` and `SAME_PERSON_REAFFIRMATION`
instead of `HOLD`). The bounded guard now detects identical immutable source
spans regardless of Person, Statement ID and claimed date, returning `HOLD`
with `IDENTICAL_SOURCE_SPAN_REUSED`. Positive fixture references that
previously reused a fake common `capture:part` were corrected to represent
independent captured utterances. Distinct captures with the same exact words
remain eligible for private cross-Person agreement and same-Person
reaffirmation hypotheses; no review or publication authority is granted.

**GREEN:** 98 focused DP-318, legacy relation-runtime/policy and repository,
plus adjacent intent-policy tests pass. Ruff lint, Python compilation and
owned-file trailing-whitespace/newline checks pass. Whole-file `ruff format
--check` reports existing unformatted passages in these previously unformatted
DP-318 files; unrelated formatting was left intact for bounded review. The
integrator owns the final Git diff check under its exclusive lease. The
references and speaker receipts are still synthetic caller
inputs. No authoritative Capture/person ledger authentication, append-only
relation revocation, real published non-factual Statement review, source rights
approval or MiniPC Person/Topic/Trace readback is evidenced. **DP-318 remains
IN PROGRESS, AC-318.1–.5 all OPEN** pending their original acceptance gates.

## 2026-10-15 — Incompatible revisions of one captured source part

**RED source-only regression:** The real private speech-act assessor produced
two individually well-formed receipts sharing the same `source_part_ref` but
binding different immutable source SHA-256 values (two revisions of the same
Capture). The DP-318 relation classifier accepted the supplied common
proposition/equivalence and returned `CROSS_PERSON_AGREEMENT` for different
Persons, despite the incompatible source snapshots. This could also make
one Person appear to reaffirm a position across two revisions of one part.

**GREEN narrow correction:** Two inputs with the same source-part reference
and different source hashes now yield `HOLD` with
`SOURCE_PART_REVISION_CONFLICT`, before a private relation kind is emitted.
The regression covers both cross-Person and same-Person comparisons; a
distinct independent source part still yields a *private* positive candidate.
The original evaluator's result remains unauthoritative, with
`publication_authority=False` in both negative and positive cases.

This closes a reproducible source-version mixing gap relevant to
`AC-318.4`, **not** the original criterion. There is no independent
Capture/source-currentness authority, reviewer attestation, public relation
read model, approved original quotations, real Person/Topic/Trace MiniPC
readback or source-rights approval. **Status stays IN PROGRESS and
AC-318.1–.5 stay OPEN.**
