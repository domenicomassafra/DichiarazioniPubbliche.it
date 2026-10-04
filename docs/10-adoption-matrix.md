# Adoption Matrix

Questa matrice serve a evitare due estremi: riscrivere tutto da zero oppure assemblare così tanti progetti da creare un sistema ingestibile.

Legenda:

- **ADOPT/POC** — candidato concreto da provare.
- **DONOR** — codice/pattern da estrarre con licenza compatibile.
- **REFERENCE** — studiare, non dipendere dal progetto.
- **BENCHMARK** — dataset/test/evaluation.
- **HOLD** — non adottare finché licenza/maturità non è chiarita.

| Area | Progetto | Status | Motivo |
|---|---|---|---|
| Claim verification | Loki/OpenFactVerification | ADOPT/POC | Copre gran parte del claim-to-evidence-to-verification flow |
| Evidence governance | Claim Polygraph NG | DONOR | Adversarial/support-contradict/policy patterns |
| URL parsing / preservation | Meedan Pender | REFERENCE/DONOR | Maturo e MIT, ma Rails+Postgres+Redis è troppo stack se Trafilatura+ArchiveBox bastano |
| Similarity infrastructure | Meedan Alegre | REFERENCE, NOT RUNTIME | MIT ma deployment molto pesante; replicare ruolo con embeddings+Postgres |
| Research benchmark | AVeriTeC | BENCHMARK | Real-world web evidence; BY-NC code |
| Research benchmark | FEVER | BENCHMARK | Support/refute/NEI, Apache |
| Italian benchmark | FEVER-it | BENCHMARK | Regression italiana |
| Italian benchmark | Check-IT! | BENCHMARK | Fact-check politici italiani; access controlled |
| KG verification | FactCheck-AI/FactCheck | BENCHMARK | MIT; structured-fact/RAG/consensus evaluation |
| Check-worthiness | ClaimBuster Spotter | REFERENCE | GPL; useful historic task/data patterns |
| Evidence aggregation | GEAR | REFERENCE | Graph evidence reasoning |
| Cheap verification | DeReC | REFERENCE | Retrieval/classifier cascade |
| Retrieval diversity | IMRRF | REFERENCE | Multi-source/redundancy ideas |
| RAG safety | TrustworthyRAG | REFERENCE | Poison/NLI/trust patterns |
| Fact-check UX | OpenErrata | REFERENCE | Fail-closed + provenance + GraphQL; AGPL |
| BYOK/browser UX | DoppelCheck | DONOR | MIT, direct-provider BYOK pattern |
| Uncertainty UX | FactScope | REFERENCE | Mixed/open states; AGPL |
| Quantitative UX | FYI | REFERENCE | Dataset exploration + BYOK |
| Media monitoring | Full Fact AI | REFERENCE | Valida collect/classify/match pipeline |
| News corpus | Media Cloud | REFERENCE | Strong corpus/search; AGPL backend |
| Feed polling | Miniflux | ADOPT/POC | Small, mature, Apache, API/webhooks |
| Feed connectors | RSSHub | REFERENCE/OPTIONAL SERVICE | Current upstream AGPL-3.0; useful boundary service, not flexible-core donor |
| Automation | Huginn | REFERENCE | Powerful but likely overkill |
| Change detection | changedetection.io | HOLD | Useful concept; licensing audit needed |
| Web extraction | Trafilatura | ADOPT/POC | Apache, feeds/sitemaps/text extraction |
| Web extraction fallback | Newspaper4k | ADOPT/POC | Secondary parser |
| Dynamic pages | Playwright | ADOPT/POC | Last-resort JS extraction |
| Preservation | ArchiveBox | ADOPT/POC | Robust evidence archiving |
| Preservation | Monolith | ADOPT/POC | Cheap static snapshot fallback |
| Durable citation | Perma.cc | REFERENCE/INTEGRATE | Legal/research citation use case |
| YouTube transcript | youtube-transcript-api | ADOPT/POC | Cheap first attempt; unofficial endpoint risk |
| Media extraction | yt-dlp | ADOPT/POC | Mature extractor; use carefully |
| STT | faster-whisper | ADOPT/POC | Efficient self-hosted fallback |
| Diarization | pyannote.audio | ADOPT/POC | Strong candidate; model-license audit |
| Diarization alt | diarize | BENCHMARK | Promising CPU candidate, young |
| Embeddings | Sentence Transformers | ADOPT/POC | Similarity/retrieval/reranking |
| KG/interoperability | CIMPLE | REFERENCE/INTEGRATE | URI/RDF/SPARQL/ClaimReview patterns |
| Existing checks | Google Fact Check Tools | ADOPT | Cheap external lookup |
| Public schema | Schema.org ClaimReview | ADOPT | Standard output |
| Methodology | IFCN Principles | REFERENCE | Neutral standards/source/corrections baseline |
| Transparency | Community Notes | REFERENCE | Auditability/data openness, not truth authority |
| Real-time fact check | InTruth | REFERENCE ONLY | Custom non-commercial license |
| Parliament pipeline | Open Parliament TV | REFERENCE | CC0 architecture; code GPL/AGPL |
| Italian parliament | Openparlamento | REFERENCE | Legacy/GPL, useful domain/data concepts |

## V0 technology bias

Senza congelare ancora lo stack, l'audit suggerisce una direzione minimalista.

### Core nostro

- PostgreSQL;
- API/web app;
- job queue;
- object storage;
- temporal/evidence domain model;
- policy engine;
- public pages;
- stable JSON API.

### Dependency candidates

- Trafilatura;
- Sentence Transformers;
- moduli Loki dopo audit;
- Google Fact Check Tools;
- faster-whisper;
- pyannote o alternativa;
- ArchiveBox/Monolith;
- RSSHub/Miniflux se evitano codice custom.

## Cosa NON costruire subito

- crawler web general-purpose;
- sistema RSS general-purpose;
- browser automation framework;
- STT model;
- diarization model;
- vector DB separato;
- graph DB separato;
- SPARQL endpoint;
- MCP server;
- browser extension;
- subscription/billing;
- mobile app;
- live fact-check;
- user-generated public comments.

Costruire queste cose solo quando il valore del prodotto le rende necessarie.

## Core IP / valore originale

Il codice originale su cui vale la pena investire:

1. identity + role timeline;
2. statement/claim canonicalization;
3. temporal claim graph;
4. contradiction vs position-change reasoning;
5. evidence provenance;
6. publication policy engine;
7. versioned corrections/right-of-reply;
8. human + agent friendly public-record UX.
