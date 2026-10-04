# Deterministic Verification, Review Ledger e Reanalysis v1

Data: 2026-09-22.

## Obiettivo

Questa wave separa in modo esplicito quattro concetti che non devono mai essere
confusi:

**retrieval -> approval -> verification -> publication**.

Un documento ufficiale scaricato non è automaticamente evidence approvata.
Un valore estratto da quel documento non è automaticamente approvato.
Una verifica deterministica riuscita non è automaticamente un finding
pubblicabile.

## Runtime

Implementazione:

- `poc/dichiarazioni_pubbliche/verification_runtime.py`;
- `poc/dichiarazioni_pubbliche/finding_runtime.py`;
- `poc/dichiarazioni_pubbliche/relation_runtime.py`;
- `poc/dichiarazioni_pubbliche/reanalysis_runtime.py`;
- `poc/dichiarazioni_pubbliche/review_admin.py`;
- glue nel processing worker e in `QueueRuntimeStore`.

Migration:

`db/migrations/20260922-add-verification-reanalysis-runtime.sql`

## Evidence observation

Il body evidence rimane content-addressed nel private runtime.

I valori strutturati usati dalla verifica vengono invece salvati come
`evidence_observation`, con provenance esplicita:

- evidence ID;
- observation type;
- metric;
- numeric/text value;
- unit;
- reference period;
- dimensions;
- extraction method/version;
- source pointer;
- status.

Status:

- `CANDIDATE`;
- `APPROVED`;
- `REJECTED`;
- `QUARANTINED`.

Ogni nuova observation nasce **CANDIDATE**. Il worker ignora intenzionalmente
eventuali payload che tentino di crearla già APPROVED.

La verifica legge una observation soltanto quando sono veri entrambi:

1. `claim_evidence_candidate.status = APPROVED`;
2. `evidence_observation.status = APPROVED`.

## Review ledger

Le approvazioni manuali/operative non sono UPDATE anonimi. Status transition e
review event vengono scritti **atomicamente nella stessa statement PostgreSQL**:
un crash non può lasciare un APPROVED privo di provenance.

La tabella append-only `review_event` registra entity type/id, action, actor
reference, reason, timestamp e metadata.

CLI:

`PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.review_admin --help`

Operazioni v1:

- `approve-evidence`;
- `approve-observation`;
- `enqueue-verification`;
- `trigger-reanalysis`.

Gli ID review sono deterministici, quindi lo stesso identico atto di review è
idempotente.

## Verification runtime

Ogni run persiste verification kind/version, **verification rule completa**,
input fingerprint, statement cutoff, assessment, evidence IDs, blockers,
rationale codes e structured result.

Il fingerprint include evidence e observation IDs, quindi una nuova observation
o una nuova versione del dato produce un run distinto.

Regola temporale: evidence pubblicata dopo la data della dichiarazione non viene
usata per stabilire cosa fosse verificabile a quella data.

V1 deterministic kinds:

- `numeric_exact`;
- `numeric_range`;
- `historical_minimum`;
- `historical_peak`;
- `legal_status_exact`;
- `text_exact`.

Guardrail:

- valori numerici richiedono evidence authoritative;
- evidence authoritative in conflitto -> `UNRESOLVED`;
- historical support richiede coverage completa o explicit record attestation;
- un singolo counterexample valido può confutare un historical minimum/maximum;
- evidence solo post-statement -> `INSUFFICIENT_EVIDENCE`.

## Finding draft

`verification_run` è il provenance anchor del finding.

Mapping v1:

- `SUPPORTED` -> `POLICY_HOLD`;
- `FACTUALLY_FALSE` -> `POLICY_HOLD`;
- `OUTDATED_DATA` -> `POLICY_HOLD`;
- `INSUFFICIENT_EVIDENCE` -> `NEEDS_MORE_EVIDENCE`;
- `UNRESOLVED` -> `UNRESOLVED`.

Quindi **nessun deterministic verifier produce `PUBLISH`**.

Un rerun con nuova evidence crea un nuovo finding draft append-only con
`supersedes_id`; il precedente non viene sovrascritto.

## Temporal / contradiction relation candidates

Il runtime relazionale non deduce intenzioni e non chiama “contraddizione” due
frasi solo perché appartengono allo stesso topic.

Input strutturato: proposition key, topic key, stance, statement date, temporal
scope e optional retrospective continuity assertion.

Output:

- `NO_RELATION`;
- `RELATED_TOPIC`;
- `SAME_PROPOSITION`;
- `POSITION_CHANGE_CANDIDATE`;
- `CONTRADICTION_CANDIDATE`.

Anche `CONTRADICTION_CANDIDATE` resta una candidate relation; non viene
promossa automaticamente in `claim_relation`, finding o pubblicazione.

## Reanalysis

Trigger versionati:

- `EVIDENCE_APPROVED`;
- `EVIDENCE_HASH_CHANGED`;
- `RIGHT_OF_REPLY`;
- `CORRECTION`;
- `RELATION_APPROVED`;
- `MANUAL_REVIEW`.

Ogni trigger ha ID deterministico e lifecycle:

`PENDING -> ENQUEUED -> PROCESSED`.

`REANALYZE_CLAIM` riusa l'ultima verification kind/rule/cutoff e accoda un
nuovo `VERIFY_CLAIM`. Non modifica il finding precedente.

## Health digest

Il private health digest ora include aggregati di evidence observations per
status, verification runs per assessment, findings per publication status,
relation candidates per status, reanalysis triggers per status e review events
per action.

Non include transcript text, evidence body, raw error detail o secret.

## Runtime proof MiniPC

Canary sintetico end-to-end sul PostgreSQL runtime authority:

- claim/evidence APPROVED;
- observation CANDIDATE -> APPROVED;
- approved verification input count: 1;
- `numeric_exact`: `SUPPORTED`;
- finding result: `POLICY_HOLD`;
- structured opposite stance sullo stesso proposition/scope:
  `CONTRADICTION_CANDIDATE`;
- reanalysis trigger: `PROCESSED`;
- synthetic content/evidence cleanup: residui 0;
- atomic review canary: 2 approval event + 1 approved verification input, residui canary 0;
- baseline corrente: 137/137 test verdi + benchmark deterministico 5/5 anche sul MiniPC.

Questo prova la plumbing e i guardrail, non costituisce un giudizio politico o
un finding pubblico.

## Cosa NON fa questa wave

Non introduce person reliability score, lie score, ranking politico, inference
automatica di intenzionalità, auto-approval di evidence, auto-publication di
finding, contradiction verdict basato su embedding/similarity o nuova
vector/graph infrastructure.

Queste capability non sono necessarie per il core v1 e non vanno aggiunte senza
un benchmark che dimostri un bisogno reale.
