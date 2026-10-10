# DP-319 — Indagine attiva dei casi dubbi con coda minima

Status: FUTURE
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-213, DP-215, DP-225, DP-228

## Problem
 Mettere `PENDING` o `QUEUED_FOR_HUMAN_REVIEW` non risolve dubbi su originalità, speaker, quote, chronology, evidence. Niente review testuale umana ordinaria e nessun budget infinito; un'assenza di risultati da corpus incompleto non è una prova negativa.

## Outcome
 Per ogni blocker preciso, un `InvestigationAttemptLedger` privato e deduplicato pianifica/risolve ricerche ammesse per fonte, stop condition e budget e produce `RESOLVED`, `CHECKED_INSUFFICIENT`, `CONFLICT`, `EXHAUSTED`, `WAIT_EXTERNAL` + residual reason, escalation piccola/rapida solo se deve decidere un owner/qualified authority.

## Traceability & constraints
 R23/R12/R13/Q9/Q14, forte autonomia. Nessun provider switch/paid canary automatico fuori policy.

## Scope
 Typed question (speaker, original, date, rights, contextual speech, primary evidence, jurisdiction, version) → ordered plan using DP-228, DP-225, archive alternative, long-form scene, official metadata, captions/ASR alternatives where permitted → approved source/resolution and refusal receipts → dedup/version+attempt budget → terminal outcome, read-only Studio oversight and reopen signal on new source. Research success alone **non** grants review/rights/publication. Collapsing dependent source copies prevents false independent corroboration.

## Non-goals
 Endless scraping, collecting unauthorised corpora, empty queue success, blocking every case until owner edits every paragraph.

## Dependencies and sequencing
 Source access permits from A and measured cost/cap from D; negative unavailable authority gets external question to owner/legal with exact scope, no retry loop. Existing DP-228 research-plan compiler reused.

## Acceptance criteria

- [ ] `AC-319.1`: All actionable hold codes map to a concrete question, allowed source/attempt family, cap/time/stop reason; unresolved external legal authority never recast as completed factual check.
- [ ] `AC-319.2`: Replay of identical source and plan never repeats cost-bearing attempt; new relevant version can reopen one bounded attempt, old receipt preserved.
- [ ] `AC-319.3`: Failure after original/full-context/official/independent-source alternatives records coverage and `CHECKED_INSUFFICIENT` or `EXHAUSTED` distinct from `NOT_CHECKED`; never labels false by search absence.
- [ ] `AC-319.4`: Real closed case has source→hash→reason→downstream proof and leaves exception queue; genuine legal/visual/identity edge receives one limited owner task with evidence and no false reviewer availability.
- [ ] `AC-319.5`: Provider outage, cost cap, revoked rights and stale plan block new child tasks and mark resumable state; D ledger reconciles exact consumed work.

## Validation / proof
 Simulated retries, changed sources, sourced independently vs mirrors, budget exhaustion, qualified-owner blocking; future MiniPC replay receipts from real authorized sources.
## Documentation, data, and migration impact
 Append-only attempt/counter receipts referencing existing discovery/coverage source tables, no parallel scheduler.
## Completion receipt
 non implementato; pianificazione soltanto.
