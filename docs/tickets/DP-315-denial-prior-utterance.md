# DP-315 — «Non ho mai detto X»: tre verifiche e relazione storica

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-216, DP-219, DP-220, DP-222, DP-227, DP-312, DP-314

## Problem
 Trovare stringa X non prova che Persona avesse sostenuto X; non trovarla in corpus incompleto non prova la negazione universale. `non l'ho detto`, `non l'ho sostenuto`, `non l'ho mai voluto dire` hanno diversi predicati e scope temporali.

## Outcome
 Pacchetto auditabile che decide separatamente autenticità delle parole precedenti, speech-act/endorsement precedente, semantica/scope della successiva negazione, factual status della negazione sull'insieme coperto e relazione storica; la verità della proposizione X resta un'altra verifica opzionale.

## Traceability & constraints
 R17/R18/R19/Q11; esempi precedenti ipotetici con persone reali **non** testimoni reali. Nessun dolo/menzogna intenzionale.

## Scope
 Two source occurrences + identities and context + `denial_predicate=UTTERED/ENDORSED/MEANT/OTHER` + quantifier `NEVER`, start/end, public/private scope and content identity -> evidence of one counterexample within claimed universal scope or explicit incompleteness -> denial verification and separate relation candidate provenance. One authenticated prior utterance refutes `NEVER_UTTERED` only if same speaker, exact/semantically matching assertion and stated scope. Prior ironic quote **does not** refute `NEVER_ENDORSED` absent endorsement proof.

## Non-goals
 No proving a universal negative from incomplete archives, no inference speaker intent, no checking X's external factual content as part of denial verdict.

## Dependencies and sequencing
 Context/identity before match; source completeness inventory from A/DP-215; C displays each of the three tracks separately. DP-318 consumes relation only after cross-person/temporal validation.

## Acceptance criteria

- [ ] `AC-315.1`: Counterexample to exact universal `never uttered` within time/speaker/scope can refute denial, with approved original locator; altering speaker/scope/time yields hold.
- [ ] `AC-315.2`: Prior quoted criticism/re-enactment cannot refute `never endorsed`; original X's independent factual truth remains unchanged.
- [ ] `AC-315.3`: Partial archive absence yields `CHECKED_INSUFFICIENT_EVIDENCE` with coverage manifest and attempts, never `SUPPORTED` by absence.
- [ ] `AC-315.4`: Changed prior or later source, transcript correction or newly found context invalidates denial and related trace, not the immutable historical wording.
- [ ] `AC-315.5`: Replay/versioned result and public downstream show denial finding (if checkable), earlier Statement and longitudinal relation as separate linked objects; no intentionality language or wrong-person relation.

## Validation / proof
 Table of uttered/endorsed/meant, wrong person, quotation as criticism, universal scopes, incomplete corpus and corrected transcript; inspect exact evidence links and public omitted/private-held states on MiniPC future pilot.
## Documentation, data, and migration impact
 Add bounded typed denial target/quantifier/scope relation and lineage; preserve claim/projection v1 identifiers.
## Completion receipt
 Historical planning-only note, superseded solely by the source-only slice below.

## 2026-10-11 — Bounded private three-track evaluator

Implemented opt-in `denial_prior_utterance.py` and new adversarial
`test_dp315_denial_prior_utterance.py` cases. Separate source-reviewed prior
utterance, explicit endorsement, and NEVER_UTTERED versus NEVER_ENDORSED
versus unverifiable NEVER_MEANT targets use version/hash/Person/time/scope
checks. A direct verified same-speaker occurrence can create a **private**
counterexample candidate; quotation, irony, reported speech, different
speaker, unknown currentness, changed source, absent review and sparse corpus
all HOLD or remain `CHECKED_INSUFFICIENT_EVIDENCE`. The underlying factual
truth of proposition X is always `NOT_EVALUATED`; there is no intent, lie,
human review or public publication authority inference. Focused offline tests
PASS. **No original AC-315.1–.5 is fully closed** without independent source
evidence/currentness, downstream DP-318 and public consumer, MiniPC pilot.

## 2026-10-11 — Exact review/window/occurrence snapshot binding

The private denial evaluator's receipt fingerprint previously included only
selected denial fields and matched occurrence **IDs**. A renewed source-review
event, amended time window, different utterance date or changed speech act
could reproduce the same receipt SHA and outcome while the underlying
review/provenance scope had materially changed. A six-case regression was
**RED** before correction (**6/6 failures**). The receipt now hashes the
complete bounded typed target and observation metadata, with UTC-normalized
dates and canonical occurrence ordering; no private utterance body is
included. Unreviewed/malformed observation types fail closed.

After correction, **24/24** DP-315 plus DP-319 focused tests PASS; scoped
Ruff F821 and `git diff --check` PASS. This is an integrity checksum over
supplied metadata, **not** a signature or independent source/rights review.
Real provenance, changed-source invalidation across consumers and the
MiniPC authorized readback are still missing. All AC-315.1–.5 remain
unchecked; **IN PROGRESS**, no new public Finding or opinion authority.
