# Source-level Donor Audit

Audit eseguito il 2026-09-21 clonando direttamente i repository finalisti e ispezionando struttura, dipendenze, test e moduli.

Questo documento distingue il valore concettuale di una repo dal valore pratico di inserirla nel runtime del nostro side-project.

## Sintesi esecutiva

La prima ricerca suggeriva una possibile composizione di diversi servizi Meedan + Loki + knowledge graph.

Il source-level audit porta invece a una soluzione più piccola:

- non adottare un monolite fact-checker esterno;
- non eseguire Alegre come servizio;
- probabilmente non eseguire Pender come servizio;
- provare alcuni moduli/pattern di Loki, senza prenderne il verdict model come publication authority;
- riusare/adattare selettivamente pattern MIT di Claim Polygraph;
- usare CIMPLE come reference/interoperability/external graph, non come nostro storage primario;
- tenere il core in una codebase nostra con pochi servizi.

## Snapshot locale dell'audit

Clone shallow eseguiti il 2026-09-21.

| Repo | HEAD audit | Data commit HEAD | Tracked files | Test-like files | Nota |
|---|---:|---:|---:|---:|---|
| Loki/OpenFactVerification | 6e1ee9e | 2024-10-03 | 74 | 0 | research/tooling sized |
| Claim Polygraph NG | fb29808 | 2026-08-26 | 965 | 213 | engineering-heavy portfolio/research platform |
| Meedan Pender | 017b99f | 2026-08-02 | 331 | 95 | mature Rails service |
| Meedan Alegre | 8ee993a | 2026-06-01 | 188 | 49 | heavy similarity service |
| CIMPLE knowledge-base | dda51b9 | 2026-09-06 | 23 | 0 | deployment/config repo around Virtuoso |

I conteggi sono solo una fotografia del clone e non una metrica di qualità.

## Loki / OpenFactVerification

Upstream:
https://github.com/Libr-AI/OpenFactVerification

Licenza: MIT.

### Cosa fa realmente il core

La classe principale compone cinque passaggi:

1. Decompose;
2. Checkworthy;
3. QueryGenerator;
4. evidence retriever;
5. ClaimVerify.

Decomposition, check-worthiness e query generation sono parzialmente parallelizzati. Poi vengono recuperate evidenze e classificate come supporting/refuting.

Il summary calcola anche una factuality numerica come rapporto fra evidenze SUPPORTS e totale SUPPORTS+REFUTES.

### Cosa ci piace

- pipeline molto leggibile;
- boundary chiari fra claim decomposition, check-worthiness, retrieval e verification;
- client provider separati;
- retriever intercambiabili;
- buona base per un POC veloce.

### Cosa NON adotterei

Il semplice rapporto SUPPORTS/(SUPPORTS+REFUTES) non è sufficiente per il nostro publication gate:

- non pesa adeguatamente qualità e indipendenza delle fonti;
- non risolve conflitti temporali;
- non distingue una fonte primaria da molte ripetizioni secondarie;
- non rappresenta sufficientemente context/limitations;
- non deve diventare uno score pubblico della verità.

Nel clone non è presente una vera test suite applicativa paragonabile a quella che vogliamo per un sistema di pubblicazione.

Le dipendenze includono provider LLM, Playwright e retrieval web. È quindi più corretto trattarlo come toolkit/research donor che come foundation production.

### Decisione

**POC SELECTIVE**.

Testare separatamente:

- claim decomposition;
- check-worthiness;
- query generation.

Non adottare automaticamente:

- final score;
- UI;
- runtime architecture.

## Claim Polygraph NG

Upstream:
https://github.com/moshiur00/claim-polygraph-multi-agent-evidence-investigator

Licenza: MIT.

### Dimensione e struttura

È di gran lunga la repo più strutturata fra i donor analizzati:

- typed domain;
- application layer;
- provider adapters;
- persistence;
- analysis modules;
- reporting;
- evaluation;
- API;
- dashboard;
- molti test e fixture.

Dipendenze/core architecture:

- Python 3.12;
- FastAPI;
- Pydantic v2;
- LangGraph;
- SQLite/WAL;
- Next.js dashboard;
- search/model provider adapters.

### Pattern di altissimo valore

#### Deterministic judgment policy

Il modello può proporre un label, ma una matrice deterministica limita i label compatibili con la resolution derivata dall'evidence ledger.

Questo pattern va mantenuto.

Nel nostro caso, dove Polygraph può instradare a human review, noi useremo soprattutto POLICY_HOLD, UNRESOLVED o NEEDS_MORE_EVIDENCE.

La full automation non deve rimuovere il gate: deve sostituire l'escalation umana ordinaria con una non-publication automatica.

#### Citation assurance

Esiste un modulo dedicato a verificare in modo fail-closed che le affermazioni del report siano collegate a evidence approvate.

Questo è uno dei pattern più importanti da riusare.

#### Evidence integrity / families / independence

La repo tratta:

- duplicate/near-duplicate evidence;
- evidence families;
- independence;
- source quality;
- original source resolution;
- provenance links.

È esattamente il rimedio al problema “dieci articoli che copiano la stessa agenzia non sono dieci prove indipendenti”.

#### Temporal + numerical verification

Sono moduli separati, scelta architetturale che conviene replicare.

#### Paid operation receipts / cost ledger

Le chiamate a provider possono produrre receipt persistenti con provider/task, attempts, token usage, measured cost, upper bound, duration e billing basis.

Per un side-project automatico è molto più utile di una dashboard token generica.

#### Idempotency, recovery e backpressure

Il sistema tratta chiamate costose e job come operazioni durevoli, non come una catena fragile di API call.

### Cosa NON adottare interamente

- LangGraph non è automaticamente necessario;
- Next.js dashboard investigativa non serve alla v0;
- durable human-review ledger va semplificato;
- 900+ file sono troppa superficie per il nostro core iniziale;
- SQLite architecture è una decisione loro, non nostra;
- non abbiamo bisogno del loro intero evaluation history/runtime.

### Decisione

**PRIMARY DESIGN DONOR, SELECTIVE MIT REUSE**.

Prima di scrivere il nostro engine, mappare i moduli:

- judgment_policy;
- citation_assurance;
- evidence_integrity;
- evidence_families;
- independence;
- source_quality;
- temporal_verification;
- numerical_verification;
- paid_operations / cost_ledger;
- provider idempotency.

Per ciascuno decidere:

1. import/adapt;
2. rewrite from concept;
3. not needed.

## Meedan Pender

Upstream:
https://github.com/meedan/pender

Licenza: MIT.

### Stato

Servizio Rails maturo con test e feature concrete:

- generic metadata/oEmbed parsing;
- provider-specific parsing;
- URL normalization;
- Archive.org archiver;
- Perma.cc archiver;
- async webhooks;
- API authentication.

Runtime/dependencies includono Rails, PostgreSQL, Sidekiq, Redis, S3 integration e monitoring.

### Valore per noi

I pattern di parser/archiver sono ottimi.

Ma installare un intero servizio Rails + Redis solo per parsing e archiviazione aumenterebbe deploy surface, memory, backup, monitoring, migrations e upgrade burden.

Trafilatura + nostri source adapters + ArchiveBox/Monolith possono probabilmente coprire la v0 con meno componenti.

### Decisione

**DONOR/REFERENCE, NOT DEFAULT RUNTIME DEPENDENCY**.

Rivalutare Pender solo se i provider-specific parser o gli archiver ci fanno risparmiare abbastanza codice da giustificare un servizio in più.

## Meedan Alegre

Upstream:
https://github.com/meedan/alegre

Licenza: MIT.

### Stato reale del deployment

Il compose include:

- Elasticsearch;
- Kibana;
- Redis;
- PostgreSQL;
- queue worker;
- servizio Alegre;
- optional model workers.

La documentazione suggerisce per lo sviluppo Docker risorse nell'ordine di 12 GB RAM e 128 GB disk.

Il requirements file conserva molte dipendenze ML/framework di generazioni precedenti, insieme a pgvector, sentence-transformers, Elasticsearch/OpenSearch, TensorFlow e Torch.

### Valore concettuale

- media/text similarity;
- duplicate detection;
- translation/similarity patterns;
- queue separation.

### Perché non adottarlo

Il nostro problema iniziale di similarity è molto più piccolo:

- embedding del claim;
- nearest-neighbor search;
- reranking;
- cluster/duplicate logic.

Possiamo farlo in PostgreSQL + vector extension e una libreria moderna di embeddings senza Elasticsearch/Kibana/Redis come stack obbligatoria.

### Decisione

**REFERENCE ONLY; DO NOT RUN ALEGRE IN V0/V1**.

## CIMPLE Knowledge Base

Upstream:
https://github.com/CIMPLE-project/knowledge-base

### Cosa è realmente la repo

Il repository principale ispezionato è soprattutto deployment/configuration per Virtuoso, SPARQL e webhook/update scripts.

La logica di extraction/conversion/data vive in repository separati.

### Valore

Molto alto per:

- URI design;
- RDF mapping;
- ClaimReview ingestion;
- external knowledge graph;
- SPARQL interoperability;
- data release strategy.

### Perché non adottare Virtuoso come primary DB

Il nostro access pattern principale richiede transactional domain state, jobs, corrections, versions, provenance, user requests, vector search e una normale web API.

PostgreSQL è una base operativa più semplice per la v0.

Possiamo aggiungere una RDF projection/export successivamente senza avere due source-of-truth.

### Licenze

La costellazione CIMPLE va verificata repository per repository. Non assumere che la licenza di un componente si propaghi automaticamente agli altri.

### Decisione

**INTEROPERABILITY / DATA-MODEL REFERENCE + POSSIBLE EXTERNAL SPARQL SOURCE**.

No Virtuoso nel core iniziale.

## Revised minimal architecture after source audit

Il source audit riduce la v0 a pochi componenti.

### Core application

Una nostra codebase contiene:

- domain model;
- source registry;
- ingestion jobs;
- claim pipeline;
- evidence graph;
- temporal graph;
- policy engine;
- correction lifecycle;
- API;
- public website.

### Infrastructure

Idealmente:

- PostgreSQL + vector extension;
- S3-compatible object store;
- una queue semplice;
- stateless workers.

### External / replaceable tooling

- Trafilatura per article extraction;
- Playwright soltanto fallback;
- transcript provider adapters;
- faster-whisper come fallback;
- diarization adapter;
- Monolith/ArchiveBox per preservation;
- search/fact-check provider adapters.

### Patterns adapted from donors

Da Claim Polygraph:

- evidence packet;
- source independence;
- deterministic verdict constraints;
- citation assurance;
- cost receipts;
- idempotency;
- retrieval/provider safety.

Da Loki:

- pipeline boundaries;
- atomic claim extraction/check-worthiness/query generation.

Da Pender:

- URL normalization;
- parser-adapter concept;
- archiver adapter concept;
- async archive callback pattern.

Da Alegre:

- semantic duplicate/similarity concept.

Da CIMPLE:

- URI/public identifiers;
- RDF/ClaimReview projection.

## Decisione finale dell'audit

**Non forkare nessuna delle cinque repo come base dell'app.**

Costruire una codebase piccola nostra, usando codice MIT selezionato solo quando riduce davvero complessità e mantenendo tutti i donor come componenti sostituibili.

Questo massimizza:

- semplicità operativa;
- controllo commerciale;
- capacità di aggiornare modelli/tool;
- chiarezza delle licenze;
- valore originale del temporal graph;
- sostenibilità da side-project.
