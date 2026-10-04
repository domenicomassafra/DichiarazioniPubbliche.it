# Canonical Transcript + PostgreSQL v0

Data: 2026-09-22.

## Obiettivo

Trasformare le policy già decise in due contract eseguibili:

1. scegliere la lane ASR senza hardcodare un provider;
2. conservare raw transcript multipli senza permettere a una correzione
   semantica di riscrivere silenziosamente l'audio.

## ASR router

Implementazione POC:

poc/dichiarazioni_pubbliche/asr_router.py

Input:

- durata;
- lingua;
- risk class;
- timestamp requirement;
- provider health;
- quota audio residua;
- transcription-policy.v0.json.

Per NORMAL:

- usa il primary remoto provato e disponibile;
- se quota o health non lo permettono, passa a un fallback locale provato.

Per SENSITIVE:

- primary;
- second opinion indipendente;
- eventuale escalation soltanto se primary e second opinion discordano.

Un modello non ancora provato nel runtime owner non viene scelto
automaticamente.

## Canonical transcript

Implementazione POC:

poc/dichiarazioni_pubbliche/transcript_contract.py

Ogni candidate transcript conserva:

- provider;
- source kind;
- testo raw;
- start/end;
- candidate ID.

Il canonical segment non è una nuova parafrasi.

Stati:

- RESOLVED: i candidate concordano;
- CANDIDATE_DISAGREEMENT: differenza lessicale non sensibile, raw primary
  mantenuto finché un reconciler esplicito non decide;
- TRANSCRIPT_UNCERTAIN: disaccordo su numero, negazione o gazetteer term;
  publication blocked.

La logica verrà estesa a:

- date;
- currency;
- percentuali;
- legal identifiers;
- proper-name entity linking;
- semantic disagreement.

## PostgreSQL

Schema iniziale:

db/schema.v0.sql

Il DB è la source of truth strutturata.

Il media non viene conservato nel database.

### Raw transcript

transcript_variant conserva ogni versione:

- YouTube caption;
- Groq;
- Cohere;
- faster-whisper;
- futuri provider.

transcript_segment conserva i segmenti raw del singolo variant.

### Canonical transcript

canonical_transcript_segment conserva:

- testo canonico corrente;
- speaker;
- status;
- publication blocked;
- sensitive signature.

canonical_segment_candidate collega il canonical segment ai raw segment che
lo hanno prodotto.

Quindi è sempre possibile risalire dal testo pubblicato alle letture originali.

## Claim ed evidence

Catena:

content_item
-> canonical_transcript_segment
-> atomic_claim
-> finding
-> finding_evidence
-> evidence.

claim_relation abilita il record longitudinale:

- contradicts;
- updates;
- clarifies;
- retracts;
- same_claim;
- prediction_of;
- promise_of.

## Correzioni

right_of_reply non modifica direttamente un finding.

Crea invece nuova evidence e una re-analysis.

correction registra la modifica.

finding.supersedes_id mantiene la storia append-only.

## Job e costi

processing_job permette una queue PostgreSQL iniziale.

provider_receipt conserva:

- provider e model;
- request ID;
- durata o input;
- costo stimato;
- status;
- receipt machine-readable.

Questo permette di misurare realmente costo per fonte, contenuto, minuto audio
e finding pubblicato.

## Cosa resta fuori da PostgreSQL

- MP4 transient;
- audio transient;
- model cache;
- screenshot o frame non necessari;
- secret o API key.

I media vivono nello spool e vengono eliminati dal retention worker.

## Migrazione futura

Questo schema non richiede Neo4j, Elasticsearch o un vector DB separato per la
v0.

PostgreSQL può coprire dominio, queue iniziale, full-text e graph-like
relations.

pgvector può essere aggiunto soltanto quando il retrieval benchmark dimostra
che serve.

## Validazione runtime

Lo schema v0 è stato applicato sul PostgreSQL reale del MiniPC in un database
temporaneo:

- 21 tabelle create;
- constraint del canonical transcript presenti;
- ON_ERROR_STOP senza errori;
- database di test eliminato al termine.

Quindi non è soltanto SQL documentale: la sintassi e i constraint sono stati
provati sul runtime target.

## Caption adapter

Il parser iniziale per caption YouTube è:

poc/dichiarazioni_pubbliche/caption_adapter.py

Converte JSON3 in segmenti deterministici con start/end e rimuove soltanto
duplicati consecutivi identici.

Non modifica semanticamente il testo.

Lo stesso modulo estrae chapter timestamp da description in stile podcast.

Sul caso reale Pulp Podcast #64 / Beppe Grillo ha processato 1.981 segmenti
senza scaricare il video.

## Queue PostgreSQL v0

Il contract SQL è:

db/job_queue.v0.sql

Usa:

- job ID deterministico;
- INSERT ... ON CONFLICT DO NOTHING per idempotency;
- FOR UPDATE SKIP LOCKED per claim concorrenti;
- lease_owner e lease_until;
- retry con backoff;
- DEAD_LETTER dopo il massimo numero di tentativi.

Prova reale sul PostgreSQL MiniPC:

- primo enqueue dello stesso job: true;
- secondo enqueue: false;
- righe in queue: 1;
- claim: RUNNING / worker-a;
- complete: true;
- stato finale: COMPLETED.

Il database temporaneo usato per il test è stato eliminato.

Questo rende Postgres sufficiente anche come queue iniziale senza introdurre
Redis, Kafka o un broker separato.

## Discovery dedupe

poc/dichiarazioni_pubbliche/scheduler.py produce:

- provisional content key da source + giorno + titolo normalizzato;
- definitive content key da SHA-256 quando il media o source snapshot è noto;
- deterministic job ID.

RSS e YouTube dello stesso Pulp #64 convergono sullo stesso provisional
content key.

content_locator permette poi a un solo ContentItem di avere più locator
esterni senza duplicare il record.
