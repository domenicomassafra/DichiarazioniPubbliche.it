# Official Evidence Runtime v1

Data: 2026-09-22.

## Obiettivo

Il retrieval evidence deve essere source-first, economico, cache-first,
deterministicamente riproducibile, resistente a SSRF/redirect inattesi,
rispettoso dei rate limit e separato dal publication gate.

Un body scaricato non è un finding e non è automaticamente evidence approvata.

Pipeline:

atomic claim -> query/URL candidate -> safe fetch -> evidence record ->
claim/evidence candidate -> deterministic/semantic verification ->
finding candidate -> publication gate.

## Source registry

File: config/evidence-sources.v1.json

Il registry contiene host, path, method, MIME, rate limit, TTL e classe di
evidence per fonte.

Lane iniziali:

- ISTAT SDMX;
- ISTAT publications;
- Eurostat Statistics API;
- Normattiva Open Data;
- Gazzetta Ufficiale;
- Camera linked data;
- Camera publications;
- Senato linked data;
- Senato publications;
- EUR-Lex / Cellar.

Gli endpoint API/linked-data sono separati dalle normali pagine web ufficiali:
un adapter SPARQL non ottiene implicitamente accesso a tutto il dominio
editoriale.

Normattiva Open Data viene registrata come
OFFICIAL_LEGAL_INFORMATIONAL, non come testo legale autentico. Per
l'autenticità dell'atto il lane primario è Gazzetta Ufficiale.

Il rate cap ISTAT SDMX è configurato a 4 richieste/minuto, quindi sotto il
limite ufficialmente documentato di 5/minuto per IP.

## Safe fetcher

File: poc/dichiarazioni_pubbliche/evidence_runtime.py

Guardrail:

- HTTPS only;
- no URL userinfo;
- no non-standard port;
- host allowlist;
- path allowlist;
- direct IP literal refused;
- DNS resolution preflight;
- qualsiasi IP non-global viene rifiutato;
- ogni redirect viene rivalidato;
- redirect count cap;
- method allowlist per source;
- GET body refused;
- POST body byte cap;
- MIME allowlist;
- response byte cap;
- bounded network timeout;
- fixed User-Agent;
- Accept-Encoding identity;
- ETag / Last-Modified conditional refetch;
- rate limiter persistente cross-process con file lock;
- rate-limit localmente raggiunto => defer, mai sleep del worker.

## Cache

Root runtime privato:

~/.local/share/dichiarazioni-pubbliche/evidence/

Layout:

- body content-addressed per SHA-256;
- URL/request index separato;
- key = source + method + normalized URL + request-body SHA-256;
- body e index 0600;
- directory 0700.

Quindi:

- GET identici sono cache hit;
- POST diversi sullo stesso endpoint non collidono;
- una URL mutabile produce un nuovo evidence ID quando cambia il body;
- il DB non contiene una copia indiscriminata della pagina.

## Query compiler

File: poc/dichiarazioni_pubbliche/evidence_query.py

Il core non accetta query arbitrarie generate da un modello.

Template v1:

- ISTAT_SDMX_DATA;
- EUROSTAT_STATISTICS_API;
- NORMATTIVA_SIMPLE_SEARCH;
- PARLIAMENT_RESOURCE_PROPERTIES.

Ogni template valida identifier, dimension/filter names, filter values,
page size, query limit, resource URI, metodo HTTP ed endpoint.

Non esiste un template RAW_URL.

Il Parlamento usa query SPARQL generate dal codice, non stringhe SPARQL
arbitrarie.

## Claim -> evidence candidate ledger

Migration:

db/migrations/20260922-add-claim-evidence-ledger.sql

Tabella:

claim_evidence_candidate

Campi chiave:

- claim;
- evidence;
- retrieval method/version;
- candidate relation;
- status;
- optional score;
- statement cutoff;
- metadata.

Status:

- RETRIEVED;
- APPROVED;
- REJECTED;
- QUARANTINED.

Una evidence appena acquisita entra come RETRIEVED, non APPROVED.

Relation candidate:

- SUPPORT;
- CONTRADICT;
- CONTEXT;
- UPDATE;
- UNKNOWN.

La relation è ancora una candidate, non un verdetto.

## Worker jobs

EVIDENCE_FETCH_URL

Per URL già determinata e appartenente a una source registrata.

EVIDENCE_QUERY_OFFICIAL

Per query strutturate compilate da template.

Entrambi:

- usano lo stesso safe fetcher;
- scrivono evidence content-hash-versioned;
- collegano claim/evidence come candidate;
- salvano provider receipt costo zero;
- non creano finding;
- non salvano automaticamente excerpt/full body nel DB.

## Deterministic extractors

File: poc/dichiarazioni_pubbliche/evidence_extract.py

V1:

- JSON-stat 2.0 observation decoder con selector e result cap;
- Normattiva structured act metadata;
- bounded visible-text HTML parser;
- exact phrase excerpt.

Regola: prima parser deterministico, poi eventualmente semantica.

Numeri, dimensioni, date, codici atto e metadati strutturati non devono essere
riscritti da un LLM se l'API li espone già in forma machine-readable.

## Live proof MiniPC

Runtime authority: MiniPC.

### Gazzetta Ufficiale

- HTTP 200;
- text/html;
- 4.180 byte;
- SHA-256 77c9eba0d284aaa9a13ca00c10367ae1a42def3fd954bb602d1bbc8d5298ecdf;
- secondo fetch: cache hit;
- body mode 0600;
- authoritative = true.

### Eurostat

- compiled Statistics API request;
- HTTP 200;
- application/json;
- 368.137 byte;
- SHA-256 8259254becf1793049375f4f8680602e6d2c9519a5e6f99aabeb691211af17f6;
- authoritative = true.

Il JSON-stat reale viene decodificato correttamente dal parser v1.

### Normattiva Open Data

- query SIMPLE_SEARCH compilata;
- POST body 127 byte;
- HTTP 200;
- application/json;
- 8.372 byte;
- SHA-256 3a4158accebf2b8e95efac1218b9777146feeefc2dced1a5a1b169ec5f3a31a0;
- parser reale: 3 act metadata nel sample;
- authoritative = false per policy di autenticità.

Secondo canary attraverso EVIDENCE_QUERY_OFFICIAL:

- job completed;
- RETRIEVED;
- retrieval method NORMATTIVA_SIMPLE_SEARCH;
- retrieval version official-query-v1;
- source type OFFICIAL_LEGAL_INFORMATIONAL;
- cache hit;
- claim/job/evidence canary rimossi dopo la verifica.

### Senato publication page

La pagina articolo costituzionale testata ha risposto HTTP 202.

Il fetcher l'ha rifiutata.

Questo è intenzionale: una challenge/interstitial o risposta asincrona non viene
archiviata automaticamente come evidence HTTP 200 valida.

### ISTAT SDMX

Un probe troppo ampio su all dataflows ha raggiunto il timeout.

Non è stato aumentato il timeout.

La policy production resta:

- query SDMX specifiche e bounded;
- cache lunga;
- massimo 4/minuto;
- niente catalog crawl nel processing worker.

## Cost model

Le lane iniziali qui provate hanno marginal API cost osservato pari a zero.

Il costo operativo maggiore è quindi banda, storage cache, CPU parsing ed
eventuali future semantic verification calls.

Il retrieval non introduce un search provider commerciale nel core finché le
official APIs/direct URLs coprono il caso.

## Cosa NON fa questa wave

Questa wave di retrieval non approva automaticamente evidence e non pubblica
finding. Il layer successivo di approval, deterministic verification, relation
candidate e reanalysis è documentato in
`docs/26-deterministic-verification-reanalysis-v1.md`.

Restano fuori dal core: web search generico, ranking politico, automatic finding
publication, contradiction verdict da similarity, vector DB, Neo4j,
Elasticsearch, OCR PDF indiscriminato o semantic synthesis automatica su ogni
body.

Queste capability vanno aggiunte soltanto se un benchmark dimostra che servono.
