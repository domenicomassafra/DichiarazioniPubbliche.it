# Product Positioning, Use & Marketing

## Ruolo nel portfolio

Questo progetto va trattato come un **serious side-project / public-interest AI infrastructure**, non come core business, quotidiano online, redazione politica, social network o AI che decide chi è affidabile.

La sua forza per un futuro personal brand di divulgazione AI è mostrare un'applicazione concreta di agentic pipelines, provenance, retrieval, structured data, automation, open source, safety-aware AI, cost control e machine-readable public information.

## Posizionamento consigliato

Da evitare:

> L'AI che scopre i politici bugiardi.

Più forte e più generale:

> Una memoria verificabile delle dichiarazioni pubbliche.

Oppure:

> Ogni affermazione, la fonte, le prove e ciò che è stato detto prima.

Questo posizionamento è più ampio dei politici, meno partisan, più difendibile e valorizza il temporal graph. Funziona anche per giornalisti, influencer, avvocati mediatici e personaggi TV.

## Differenziatore

Esistono già:

- fact-check atomici;
- AI verification assistants;
- browser extensions;
- fact-check databases;
- media monitoring.

La combinazione meno comune è:

**public-person timeline + source preservation + claim graph + temporal contradiction/change tracking.**

Esempio concettuale:

2024 statement -> 2025 clarification -> 2026 contradictory statement -> 2026 official action -> evidence graph.

Questo è più distintivo di un semplice bollino vero/falso.

## Product surfaces ad alto valore

### Person page

Pagina condivisibile principale:

- biografia pubblica minima;
- ruoli nel tempo;
- timeline;
- filtri topic;
- statement;
- finding;
- cambi di posizione;
- correzioni;
- fonti.

### Topic page

Non classifica persone.

Mostra claim, timeline, fonti, documenti ufficiali e relazioni fra claim.

### Finding page

È il commit del GitHub delle affermazioni:

- claim;
- quote originale;
- contesto;
- finding;
- evidence pro;
- evidence contro;
- limitations;
- provenance;
- changelog;
- diritto di replica;
- versione policy/modello.

### Source/content page

Solo precomputed nella v1:

- video/podcast/articolo;
- speaker;
- timestamp;
- extracted claims;
- finding collegati.

### Change page

Feature distintiva:

> Cosa è cambiato?

Confronta due statement della stessa persona sullo stesso concetto senza assumere automaticamente che il cambiamento sia scorretto.

## Shareability

Per crescere organicamente:

- URL stabile per finding;
- preview social chiara;
- timeline visiva;
- link diretto alla fonte/timestamp;
- sezione “come è stato verificato”;
- history/version;
- short summary senza perdere accesso alle prove.

No screenshot opachi senza URL/provenance.

## Contenuti utili al personal brand AI

Il progetto può generare divulgazione AI senza diventare marketing politico.

Esempi:

- Come monitorare centinaia di fonti spendendo poco.
- Perché un LLM non deve decidere da solo se una frase è falsa.
- Come impedire a un fact-checker AI di inventare le fonti.
- Embeddings vs LLM per ritrovare una dichiarazione di anni fa.
- Come evitare STT quando i sottotitoli esistono già.
- Che cosa significa provenance in un'app AI.
- Come costruire un sistema che preferisce non pubblicare invece di inventare.
- Come rendere un sito leggibile direttamente dagli AI agent.
- Quanto costa davvero una pipeline automatica di fact-check.
- Come aggiornare un finding dopo una rettifica senza cancellare la storia.

Questo racconta competenza AI/software più che una posizione politica.

## Open source come marketing

Parte del valore di brand può essere:

- metodologia pubblica;
- policy engine pubblico;
- benchmark pubblico;
- data schema pubblico;
- prompt/template pubblici quando appropriato;
- changelog;
- issue tracker;
- esempi riproducibili.

Messaggio:

> Non fidarti del nostro bollino: guarda come ci siamo arrivati.

## Programmabilità

### V1

Fare bene:

- HTML semantico;
- stable URLs;
- canonical JSON;
- JSON-LD ClaimReview;
- OpenAPI;
- RSS/Atom feed degli aggiornamenti;
- sitemap;
- ETag/cache headers.

Questa superficie è già ottima per browser, motori, RAG e agenti.

### V1.5

- API key per rate limits elevati;
- bulk export JSONL;
- webhooks;
- changes-since timestamp;
- per-person/per-topic feeds.

### V2

- thin MCP wrapper;
- official skill/tool spec;
- browser extension;
- BYOK advanced research;
- paid research quota.

## Perché non MCP subito

MCP è un adapter.

Se l'API ha schema stabile, search, entities, provenance, pagination e filters, aggiungere MCP dopo è relativamente semplice.

Se il dominio/API è confuso, MCP non lo corregge.

## llms.txt

Spec proposta:
https://github.com/AnswerDotAI/llms-txt

Può essere un extra utile per documentare il sito agli agenti. Non deve essere il meccanismo principale di discoverability.

Restano fondamentali:

- structured HTML;
- JSON-LD;
- OpenAPI;
- stable URLs;
- sitemap;
- API.

## BYOK futuro

Pattern preferibile:

- API key conservata nel browser/client;
- chiamata diretta al provider;
- backend del progetto non vede o conserva la chiave.

Applicazioni:

- approfondisci questo finding;
- cerca correlazioni;
- genera un report;
- analizza un contenuto per uso personale.

Il risultato BYOK dell'utente non deve diventare automaticamente un finding ufficiale.

## Subscription futuro

### Free public record

- read;
- search;
- API limitata;
- richieste in queue.

### Pro research

- query avanzate;
- export;
- higher rate limits;
- report generati;
- alert personalizzati;
- quota LLM inclusa.

### API

- usage-based;
- bulk access;
- webhooks;
- change streams.

Nessuna di queste feature è necessaria per validare il prodotto.

## Growth loop

1. nuovo finding pubblicato;
2. pagina condivisibile e indicizzabile;
3. utenti/agenti la citano;
4. arrivano nuove fonti, repliche e request;
5. il database migliora;
6. emergono nuove relazioni temporali;
7. nuove pagine e aggiornamenti vengono generati automaticamente.

## Anti-goal marketing

Non costruire il brand attorno a:

- outrage;
- gotcha;
- classifiche di persone;
- giudizi politici;
- titoli più forti delle evidenze.

Per un progetto a lungo termine, credibilità tecnica e neutralità metodologica sono asset più riutilizzabili.
