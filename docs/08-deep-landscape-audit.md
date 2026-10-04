# Deep Landscape Audit

Data audit: 2026-09-21.

## Obiettivo

Questa fase non cerca semplicemente un'altra repo da forkare. Cerca i migliori mattoni esistenti per discovery, monitoring, extraction, preservation, trascrizione, diarization, claim extraction, retrieval, verification, evidence aggregation, knowledge graph, UX, auditability, API e benchmark.

Il vincolo più importante è operativo: il progetto deve poter restare un side-project fortemente automatizzato, non diventare una redazione manuale da mantenere ogni giorno.

## Fact-check e claim verification

### Loki / OpenFactVerification

Repository: https://github.com/Libr-AI/OpenFactVerification

Ruolo potenziale: donor principale per claim extraction e verifica.

Punti forti: claim decomposition, check-worthiness, query generation, retrieval, verification e più tipi di input.

Gap: non è centrato sul record longitudinale di una persona e non risolve la semantica position-change vs contradiction vs retrospective-contradiction.

Decisione: **POC / ADOPT PARTS**.

### Claim Polygraph NG

Repository: https://github.com/moshiur00/claim-polygraph-multi-agent-evidence-investigator

Ruolo: evidence-governance e adversarial verification.

Pattern interessanti: supporting vs contradictory evidence, source quality, temporal/numerical checks, citation auditing, agenti con ruoli differenti, history e policy.

Decisione: **STUDY + REUSE PERMISSIVE PARTS**, dopo audit source-level.

### AVeriTeC

Repository: https://github.com/MichSchli/AVeriTeC

Benchmark e pipeline accademica per real-world claim verification con evidenza dal web. La pipeline documentata usa coarse retrieval, question generation, search, evidence reranking, verdict e justification. Il formato dati collega claim, verdict, giustificazione, domande/risposte, source URL e copie archiviate.

Licenza del repository: CC BY-NC 4.0.

Conseguenza: ottimo benchmark/reference architetturale, ma non code donor per un core commercialmente utilizzabile.

Decisione: **BENCHMARK / REFERENCE ONLY**.

### AIC CTU AVeriTeC

Repository: https://github.com/aic-factcheck/aic_averitec

Sistema AVeriTeC basato su retrieval, reranking e generation di evidence/label. Utile come esempio di pipeline RAG relativamente contenuta.

Licenza: CC BY-NC 4.0.

Decisione: **REFERENCE ONLY**.

### HerO

Repository: https://github.com/ssu-humane/HerO

Pattern: evidence retrieval, question generation, veracity prediction, hybrid retrieval, BM25 + embeddings, HyDE-like retrieval e reranking.

Le pipeline accademiche di questo tipo possono richiedere hardware importante. Per un side-project interessa soprattutto il pattern, non necessariamente la stack completa.

Decisione: **REFERENCE / BENCHMARK**. Verificare licenza prima di qualunque riuso.

### FEVER

Repository: https://github.com/awslabs/fever

Licenza: Apache-2.0.

Dataset classico con oltre 185k claim e classi Supported, Refuted e NotEnoughInfo. Include evidence annotations per support/refute.

Per noi: benchmark base per regressioni. Codebase storica, non foundation moderna.

Decisione: **BENCHMARK + POSSIBLE TEST CODE**.

### FEVER-it

Repository: https://github.com/crux82/FEVER-it

Adattamento italiano di FEVER, utile per test linguistici italiani, retrieval/evidence matching e regression suite.

Decisione: **ITALIAN BENCHMARK**, previa verifica puntuale di licenza/dataset.

### GEAR

Repository: https://github.com/thunlp/GEAR

Licenza: MIT.

Idea interessante: aggregare evidenze con una struttura graph-based invece di trattarle tutte isolatamente. Il valore è soprattutto concettuale perché la codebase precede la generazione attuale di modelli.

Decisione: **STUDY EVIDENCE AGGREGATION**.

### FactCheck-AI / FactCheck

Repository: https://github.com/FactCheck-AI/FactCheck

Licenza: MIT.

Benchmark 2025 dell'Università di Padova dedicato alla verifica di fatti in knowledge graph con LLM, RAG e consensus multi-modello. Include oltre 13.500 fatti distribuiti su più dataset e confronta conoscenza interna del modello, external evidence via RAG e consenso fra modelli.

Non è un motore per verificare direttamente una dichiarazione naturale pronunciata in TV, ma è utile per due motivi:

- benchmarkare la parte structured-fact / knowledge-graph;
- ricordare che il RAG ha un costo computazionale misurabile e non va invocato automaticamente quando una verifica deterministica o un lookup strutturato è sufficiente.

Decisione: **BENCHMARK / KG-VERIFICATION REFERENCE**.

### ClaimBuster Spotter

Repository: https://github.com/utaresearch/claimbuster-spotter

Licenza: GPL-3.0.

Storico progetto di check-worthiness detection con SVM, Bi-LSTM e transformer adversarial training. Il valore oggi è soprattutto il task definition/dataset e il confronto con classifier economici.

Non serve incorporarne il codice nel core.

Decisione: **CHECK-WORTHINESS REFERENCE / BENCHMARK, NOT CORE DONOR**.

### DeReC

Repository: https://github.com/alamgirqazi/DeReC

Approccio recente che combina dense retrieval e classificatori specializzati. È interessante perché suggerisce che una grossa parte del workload può restare su retrieval/classification economici, lasciando gli LLM forti ai casi difficili.

Decisione: **STUDY FOR COST CASCADE**.

### IMRRF

Repository: https://github.com/quark233/IMRRF

Pattern rilevanti: multi-source retrieval, redundancy filtering e diversità delle evidenze.

Decisione: **STUDY FOR SOURCE DIVERSITY / DEDUPE**.

### TrustworthyRAG

Repository: https://github.com/GPT-Laboratory/TrustworthyRAG

Pattern: verifier NLI, poison/suspicious-context detection e trust signals per documenti recuperati.

Decisione: **OPTIONAL RAG-SAFETY REFERENCE**.

## Verification assistants e UX

### OpenErrata

Repository: https://github.com/ZeroPathAI/OpenErrata

Licenza: AGPL-3.0.

Principi molto compatibili con noi:

- when in doubt, do not flag;
- segnalare solo errori con controevidenza concreta;
- evitare satira e ambiguo;
- audit completo;
- provenance;
- source snapshots;
- prompt/model/tool traces;
- public GraphQL per investigation completate.

Stack documentato: Svelte/SvelteKit, Postgres, job queue, object storage e deployment containerizzato.

Decisione: **STRONG REFERENCE; NON EMBED BY DEFAULT** per non trascinare AGPL nel core senza decisione esplicita.

### DoppelCheck

Repository: https://github.com/Doppelcheck/main

Licenza: MIT.

Pattern molto interessante per futuro BYOK: niente server obbligatorio, API key client-side, chiamate dirette ai provider, supporto a endpoint locali/OpenAI-compatible, lookup di fact-check esistenti e evidence vicino al claim.

Decisione: **STRONG DONOR FOR FUTURE BYOK / EXTENSION UX**.

### FactScope

Repository: https://github.com/abhirupr123/factscope

Licenza: AGPL-3.0.

Posizionamento utile: mostrare il contesto dietro un claim, non un semplice truth button.

Pattern: supported, contradicted, mixed, open; source signals separati dal finding; uncertainty visibile.

Decisione: **UX / METHODOLOGY REFERENCE**.

### FYI

Repository: https://github.com/datavisards/FYI

Progetto focalizzato su claim quantitativi, esplorazione dei dataset e BYOK.

Decisione: **REFERENCE FOR QUANTITATIVE-CLAIM UX**.

## Monitoring e discovery

### Full Fact AI

Sito: https://fullfact.org/ai/

È una validazione di prodotto importante. La decomposizione dichiarata è molto vicina a quella che serve a noi: raccogliere news/TV/podcast/social, convertire a testo, classificare claim, filtrare per topic, fare claim matching e rilevare ripetizioni.

Full Fact dichiara che i propri tool processano circa un terzo di milione di frasi in un tipico giorno feriale. Il report 2026 afferma inoltre che i tool sono stati usati da più di 40 organizzazioni in 30 paesi.

Lezione: **claim classification + claim matching devono precedere il fact-check completo**.

Decisione: **PRODUCT / ARCHITECTURE REFERENCE**.

### Factiverse

Siti:

- https://www.factiverse.ai/
- https://api.factiverse.ai/v1/redoc

Prodotto commerciale molto utile come benchmark di packaging e programmabilità. Le API documentano claim detection, stance detection, fact checking, claim search, media fact-checking, feed subscriptions, sessioni video e speaker annotation.

Il prodotto Live combina trascrizione, speaker attribution e claim detection su video/audio. La documentazione API mostra inoltre un modello con autenticazione, piani e capability granulari.

Per noi è soprattutto una reference per capire come una pipeline simile può diventare API/prodotto senza obbligarci a copiarne l'architettura.

Decisione: **PRODUCT / API / MONETIZATION REFERENCE**.

### Media Cloud

Siti:

- https://www.mediacloud.org/
- https://github.com/mediacloud/backend

Pattern utili: source collections, RSS/sitemaps, query nel tempo e corpus news su larga scala.

Backend: AGPL-3.0.

Per un side-project è più sensato usare pattern/API/dati che operare un Media Cloud personale.

Decisione: **REFERENCE / POSSIBLE EXTERNAL DATA SOURCE**.

### Miniflux

Repository: https://github.com/miniflux/v2

Licenza: Apache-2.0.

Caratteristiche utili: Go single-binary, PostgreSQL, scheduler interno o cron, REST API, webhooks, ETag/Last-Modified e footprint ridotto.

Questo è quasi il profilo ideale di un componente side-project: maturo, piccolo e sostituibile.

Decisione: **POC / LIKELY ADOPT AS SEPARATE SERVICE OR PATTERN**.

### RSSHub

Repository: https://github.com/DIYgod/RSSHub

Licenza corrente upstream: **AGPL-3.0**.

Ruolo: trasformare molte fonti senza feed puliti in route RSS. Riduce il problema delle integrazioni a un protocollo comune.

La fattibilità tecnica non sostituisce il controllo di ToS e policy della fonte.

Per noi il boundary è importante: può essere un servizio separato opzionale o una reference per capire quali fonti sono trasformabili in feed, ma non va copiato/incorporato nel core commercialmente flessibile senza accettare consapevolmente gli obblighi AGPL.

Decisione: **OPTIONAL SEPARATE CONNECTOR / REFERENCE, NOT CORE DONOR**.

### Huginn

Repository: https://github.com/huginn/huginn

Licenza: MIT.

Molto flessibile per event automation, ma probabilmente più machinery del necessario.

Decisione: **REFERENCE; ADOPT ONLY IF IT REPLACES MULTIPLE CUSTOM COMPONENTS**.

### changedetection.io

Repository: https://github.com/dgtlmoon/changedetection.io

Ottimo concetto per siti senza feed. Durante la ricerca è emersa complessità/ambiguità sulla situazione licensing commerciale delle versioni correnti, quindi serve audit puntuale prima di incorporarlo.

Decisione: **INTEGRATION/REFERENCE ONLY UNTIL LICENSE CLEARED**.

## Web extraction

### Trafilatura

Repository: https://github.com/adbar/trafilatura

Licenza delle versioni moderne: Apache-2.0; il progetto segnala che le versioni precedenti a 1.8 erano GPLv3+.

Funzioni: main text extraction, metadata, feeds, sitemap discovery, crawling limitato e output strutturato.

Decisione: **STRONG ADOPT CANDIDATE**.

### Newspaper4k

Repository: https://github.com/AndyTheFactory/newspaper4k

Parser articolo/metadata utile come fallback.

Decisione: **SECONDARY PARSER FALLBACK**.

### Playwright

Repository: https://github.com/microsoft/playwright-python

Usarlo soltanto quando API/feed/static fetch/parser non bastano. Browser automation è più costosa e fragile.

Decisione: **LAST-RESORT EXTRACTION LAYER**.

## Preservation

### ArchiveBox

Repository: https://github.com/ArchiveBox/ArchiveBox

Licenza attuale: MIT.

Salva HTML, PDF, screenshot, TXT/JSON, WARC, media e altri formati; espone CLI/API/webhooks.

Decisione: **POC / STRONG PRESERVATION CANDIDATE**.

### Perma.cc

Repository: https://github.com/harvard-lil/perma

Progetto nato per citazioni permanenti in contesti legali/accademici.

Decisione: **EXTERNAL DURABLE CITATION OPTION**.

### Monolith

Repository: https://github.com/Y2Z/monolith

Licenza: CC0-1.0/public-domain dedication.

Salva una pagina in un singolo HTML. Ottimo fallback leggero.

Decisione: **LIKELY LIGHTWEIGHT SNAPSHOT FALLBACK**.

## YouTube, audio e speaker attribution

### youtube-transcript-api

Repository: https://github.com/jdepoix/youtube-transcript-api

Recupera caption manuali e automatiche senza browser/headless. Se una trascrizione esiste già, è molto più economico usarla che eseguire STT.

Rischio: usa una parte non documentata dell'API web di YouTube e il progetto stesso avverte che può cambiare o subire blocchi IP.

Decisione: **FIRST CHEAP TRANSCRIPT ATTEMPT, NEVER SINGLE POINT OF FAILURE**.

### yt-dlp

Repository: https://github.com/yt-dlp/yt-dlp

Ruolo: metadata e media/subtitle acquisition dove consentito.

Decisione: **TOOLING LAYER**, con audit ToS e licenze degli artefatti usati.

### faster-whisper

Repository: https://github.com/SYSTRAN/faster-whisper

Implementazione Whisper su CTranslate2 orientata a inferenza più efficiente.

Decisione: **STRONG SELF-HOSTED STT CANDIDATE**.

### pyannote.audio

Repository: https://github.com/pyannote/pyannote-audio

Toolkit per speaker diarization.

Regola: separare sempre licenza del codice, licenza dei model weights/pipeline ed eventuali servizi premium.

Decisione: **PRIMARY DIARIZATION CANDIDATE, MODEL-LICENSE AUDIT REQUIRED**.

### diarize

Repository: https://github.com/FoxNoseTech/diarize

Nuovo candidato CPU-oriented che dichiara Apache-2.0 e funzionamento senza API key. Interessante per ridurre dipendenza da GPU, ma va benchmarkato seriamente su italiano, TV, overlap e audio sporco.

Decisione: **BENCHMARK AGAINST PYANNOTE, NOT DEFAULT YET**.

## Retrieval e claim matching

### Sentence Transformers

Repository: https://github.com/huggingface/sentence-transformers

Uso: semantic similarity, claim clustering, candidate historical retrieval e reranking.

Decisione: **LIKELY ADOPT LIBRARY; AUDIT MODEL LICENSES INDIVIDUALLY**.

### Ordine di lookup consigliato

1. nostro database;
2. Google Fact Check Tools;
3. dataset/ClaimReview esterni autorizzati;
4. fonti primarie già registrate;
5. ricerca web aperta;
6. deep verification con modello forte.

Questo riduce costo, latenza e duplicazione.

## Knowledge graph e interoperability

### CIMPLE

Repository: https://github.com/CIMPLE-project/knowledge-base

Il progetto descrive un knowledge graph con aggiornamento notturno, 70+ organizzazioni di fact-check, oltre 200k documenti, oltre 15 milioni di triple, oltre 203k claim, 26 lingue e 36 paesi, più endpoint SPARQL pubblico.

Lezione: URI stabili e RDF projection sono utili per interoperabilità, senza obbligarci a usare RDF/SPARQL come storage primario.

Decisione: **STRONG DATA-MODEL / EXPORT REFERENCE**.

### Google Fact Check Tools API

Documentazione: https://developers.google.com/fact-check/tools/api/reference/rest

Offre search di claim già fact-checkati, image search e oggetti Claim/ClaimReview; include anche operazioni di gestione ClaimReview per siti autorizzati.

Decisione: **ADOPT AS EXTERNAL LOOKUP**.

### Schema.org ClaimReview

https://schema.org/ClaimReview

Decisione: **PUBBLICARE UNA PROIEZIONE CLAIMREVIEW** quando semanticamente applicabile.

## Methodology reference

### IFCN Code of Principles

https://ifcncodeofprinciples.poynter.org/

Principi da trasformare in policy machine-readable:

- stesso standard indipendentemente da chi fa il claim;
- fonti primarie quando disponibili;
- prove replicabili;
- mostrare evidence che supporta e indebolisce;
- metodologia pubblica;
- criteri di selezione;
- corrections policy;
- submission di claim con aspettative chiare.

Decisione: **METHODOLOGY BASELINE**, senza affermare certificazioni che non abbiamo.

## Insight complessivo

Non costruire un monolite AI fact-checker.

Composizione consigliata:

source registry e feeds
-> cheap ingest
-> text normalization
-> claim extraction
-> existing-claim lookup
-> historical-person retrieval
-> evidence retrieval
-> verification
-> challenger
-> deterministic policy
-> precomputed public record.

La parte che vale davvero costruire e mantenere come nostra proprietà è:

**temporal public-record graph + provenance + publication policy + UX/API.**

Il resto deve essere sostituibile.
