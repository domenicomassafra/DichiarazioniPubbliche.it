# Side-project Operating Model

## Premessa

Questo progetto non è il core business del product owner. Deve essere utile, credibile, pubblicabile/open source e tecnicamente serio, ma soprattutto deve poter funzionare con pochissima operatività manuale.

L'architettura deve quindi ottimizzare non solo accuracy, ma anche maintenance burden, costo, failure isolation, replacement cost, observability, auditability e capacità di funzionare senza una redazione.

## North star operativa

**Zero lavoro editoriale di routine.**

Intervento umano solo per incidenti tecnici, cambi di API/ToS, contestazioni eccezionali, questioni legali, upgrade pianificati e decisioni di prodotto.

Il sistema non deve richiedere approvazione umana per ogni finding. Quando l'automazione non è abbastanza sicura, non pubblica.

## 1. Non monitorare tutto internet

Errore da evitare: avere 200 persone e fare ogni giorno una ricerca web aperta completa per ognuna.

Meglio un Source Registry.

### Tier A — primary/official

- siti istituzionali;
- Parlamento;
- ministeri;
- ISTAT/Eurostat;
- account ufficiali;
- siti personali/ufficiali;
- canali YouTube ufficiali;
- podcast ufficiali.

### Tier B — high-value appearances

- principali TV;
- radio/podcast;
- agenzie;
- testate selezionate;
- trasmissioni ricorrenti.

### Tier C — discovery

- Google Fact Check Tools;
- Media Cloud;
- search engine;
- web search;
- user requests.

Tier C scopre; Tier A/B costruiscono gran parte del record stabile.

## 2. Preferire pull economico a browser automation

Ordine:

1. API ufficiale;
2. RSS/Atom;
3. sitemap;
4. static HTTP fetch;
5. Trafilatura/structured extraction;
6. platform-specific adapter;
7. headless browser;
8. agentic browsing.

Più si scende, più aumentano costo e fragilità.

## 3. Idempotency ovunque

Ogni job deve poter essere rieseguito senza duplicare dati.

Chiavi utili:

- canonical URL;
- external content id;
- content hash;
- source id + published_at;
- video id;
- statement hash;
- claim semantic fingerprint.

## 4. Event-driven, non mega-cron

Pipeline a job:

source_polled -> content_discovered -> content_acquired -> content_normalized -> claims_extracted -> claim_candidate_created -> evidence_retrieved -> verification_completed -> publication_gate_completed.

Ogni fase deve avere retry, timeout, idempotency, dead-letter state e cost record.

## 5. Priorità automatica

Non tutti i documenti meritano lo stesso costo.

Score candidate:

- figura monitorata?;
- claim check-worthy?;
- tema importante?;
- reach/source significance?;
- nuovo claim o ripetizione?;
- possibile contraddizione con history?;
- già verificato altrove?;
- confidence extraction?

Solo una piccola percentuale arriva al modello più costoso.

## 6. Cheap-first cascade

### Stage 0 — deterministic

- dedupe;
- language;
- source type;
- dates;
- exact quote matching;
- known ClaimReview lookup.

### Stage 1 — cheap ML

- embeddings;
- classifier;
- clustering;
- NLI;
- reranker.

### Stage 2 — economical LLM

- atomic claim extraction;
- query proposal;
- topic/entity normalization.

### Stage 3 — strong LLM

Solo per ambiguous evidence, temporal contradictions, nuanced context e final rationale.

### Stage 4 — adversarial model

Solo per finding che potrebbe effettivamente essere pubblicato.

## 7. Cost circuit breakers

Obbligatori:

- max cost/day;
- max cost/source/day;
- max cost/content;
- max tokens/run;
- max retries;
- per-model quota;
- circuit breaker in caso di provider error;
- fallback modello;
- queue instead of burst.

Quando si raggiunge il budget, il lavoro resta in coda. Non deve produrre un verdict peggiore o inventato solo perché è finito il budget.

## 8. Static-ish publication

Il sito pubblico dovrebbe leggere quasi esclusivamente dati precomputati.

Vantaggi:

- basso costo;
- alta velocità;
- facile caching/CDN;
- niente LLM nel request path;
- minore superficie abuse;
- migliore auditabilità.

La ricerca può usare DB/search index, ma nessuna pagina pubblica deve dipendere da una generazione LLM live.

## 9. Video pipeline come fallback chain

Ordine consigliato:

1. transcript ufficiale/manuale della piattaforma;
2. transcript automatico già fornito dalla piattaforma;
3. subtitle extraction;
4. download audio dove consentito;
5. self-hosted STT;
6. diarization solo se necessaria;
7. speaker identity assignment separato dalla diarization.

Non usare diarization se c'è un solo speaker o se speaker labels sono già affidabili.

Per claim numerici, nomi propri, date, citazioni, leggi o negazioni, eseguire
un secondo ASR bounded prima di pubblicare. Il full-video transcript non è
sufficiente come prova quando il finding dipende da pochi token sensibili.

I media scaricati sono transient: dopo hash, transcript, eventuale secondary
ASR e visual extraction devono essere eliminati automaticamente.

## 10. Preservation selettiva

Non archiviare compulsivamente tutto.

Archiviare soprattutto:

- fonti usate da finding pubblicati;
- dichiarazioni originali;
- pagine suscettibili di modifica;
- documenti essenziali;
- evidence che giustifica il verdict.

Livelli:

1. metadata + hash;
2. Monolith/static snapshot;
3. ArchiveBox/WARC/screenshot;
4. external archive permalink.

## 11. Self-healing source adapters

Ogni source adapter deve avere:

- health check;
- last success;
- last item date;
- expected cadence;
- consecutive failures;
- schema drift detection.

Se una fonte si rompe:

- source diventa degraded;
- il resto della pipeline continua;
- viene creato un alert/digest;
- retry con backoff.

## 12. Daily digest invece di babysitting

Report automatico:

- sources healthy/degraded;
- nuovi content;
- claim estratti;
- candidate contradictions;
- finding pubblicati;
- finding held;
- correction requests;
- costi;
- errori non risolti.

L'obiettivo è poter capire lo stato in pochi minuti quando serve, non dover guardare dashboard tutto il giorno.

## 13. Fail-closed publication

Un finding FACTUALLY_FALSE può essere pubblicato solo se, ad esempio:

- statement attribution verificata;
- source original disponibile;
- claim atomico;
- temporal scope definito;
- evidence fetchata realmente;
- primary source usata quando ragionevolmente disponibile;
- nessuna evidence critica ignorata;
- challenger completato;
- citation URLs verificati;
- threshold di confidence superato;
- nessun legal/policy blocker automatico.

Se no, possibili stati:

- INTERNAL_CANDIDATE;
- NEEDS_MORE_EVIDENCE;
- UNRESOLVED;
- POLICY_HOLD.

## 14. Right-of-reply automatic lifecycle

1. ricezione;
2. spam/abuse filtering;
3. verifica URL/documenti;
4. nuova evidence ingestion;
5. re-run del finding;
6. compare previous/new verdict;
7. publish new version o conferma;
8. changelog pubblico.

Quasi tutto può essere automatico.

## 15. Upgrade strategy

LLM e componenti devono essere intercambiabili tramite contract.

Non hardcodare provider, model name, embedding provider, search provider o transcript provider.

Ogni adapter deve avere interface, fixtures, benchmark, cost metrics e quality metrics.

Così il progetto può cambiare modello fra uno o due anni senza riscrivere il dominio.

## 16. Minimum operational footprint

Target iniziale:

- 1 relational DB;
- 1 object store;
- 1 job queue;
- 1 web/API app;
- worker stateless;
- optional ingestion sidecars.

Evitare inizialmente:

- Kafka;
- Kubernetes;
- Neo4j + Postgres + Elasticsearch + vector DB separati tutti insieme;
- microservizi per ogni funzione;
- custom crawler distribuito.

PostgreSQL può inizialmente coprire domain data, full-text, vectors e graph-like edges, oltre eventualmente alla queue se il volume lo consente.

## 17. Definition of automation complete

Il progetto è davvero automatizzato quando:

- aggiungere una nuova persona significa configurare fonti, non scrivere codice;
- nuovi contenuti entrano da soli;
- nuovi claim vengono deduplicati;
- claim importanti vengono verificati;
- finding dubbi restano bloccati;
- finding pubblicabili vengono pubblicati;
- pagine si aggiornano;
- sitemap/API/feeds si aggiornano;
- repliche riattivano l'analisi;
- errori producono alert;
- il budget non può esplodere.

Questa è una feature di prodotto, non solo DevOps.
