# DP-315 — «Non ho mai detto X»: tre verifiche e relazione storica

Status: FUTURE
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
 non implementato; pianificazione soltanto.
