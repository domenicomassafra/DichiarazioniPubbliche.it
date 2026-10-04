# Donor Extraction Map

Data: 2026-09-21.

Scopo: trasformare il landscape audit in una lista concreta di moduli da adottare, adattare, riscrivere in forma più piccola o ignorare.

## Regola generale

Anche quando la licenza è MIT:

- non importare un intero progetto se servono poche funzioni;
- mantenere provenance del codice riusato;
- conservare notice/licenza richiesti;
- preferire API/contract nostri;
- evitare dipendenze runtime che esistono soltanto perché esistono nel donor;
- scrivere test nostri contro il comportamento desiderato.

## Claim Polygraph NG — primary design donor

Upstream:
https://github.com/moshiur00/claim-polygraph-multi-agent-evidence-investigator

Audit HEAD: fb29808.

Licenza: MIT.

### A. judgment_policy.py

Path upstream:
src/claim_polygraph_ng/analysis/judgment_policy.py

Dimensione audit: circa 142 righe.

Valore:

- matrice deterministica fra proposition resolution e verdict labels;
- proposed label separato da enforced label;
- reason codes;
- blocking challenges;
- policy version.

Per noi:

**REIMPLEMENT SMALLER IN CORE**.

Motivo:

il concetto è essenziale, ma le enum e il modello dominio devono essere nostri.

Contract suggerito:

- input: proposed finding + evidence resolution + blockers;
- output: publication decision + allowed labels + reason codes;
- nessun modello LLM dentro il policy engine.

### B. citation_assurance.py

Path:
src/claim_polygraph_ng/analysis/citation_assurance.py

Dimensione audit: circa 597 righe.

Valore:

- ogni assertion deve collegarsi ad evidence approvata;
- fail-closed;
- issue codes;
- publication gate;
- revision suggestions.

Per noi:

**PORT CONCEPTS, REIMPLEMENT AGAINST OUR FINDING MODEL**.

Non serve copiare tutta la struttura report-specifica.

MVP nostro:

1. ogni material assertion ha almeno un evidence link;
2. evidence id esiste;
3. source è fetchata e verificata;
4. span/passage esiste;
5. stance è compatibile;
6. evidence non è rejected/quarantined;
7. URL/source receipt è valido;
8. nessuna material assertion rimane unsupported.

### C. evidence_families.py

Path:
src/claim_polygraph_ng/analysis/evidence_families.py

Dimensione audit: circa 265 righe.

Valore:

- raggruppare fonti che derivano dallo stesso origin;
- evitare di contare copie come prove indipendenti.

Per noi:

**REIMPLEMENT AS SOURCE FAMILY / INDEPENDENCE GROUP**.

Il data model nostro ha già il campo independence group: questo modulo suggerisce come popolarlo.

### D. independence.py

Path:
src/claim_polygraph_ng/analysis/independence.py

Dimensione audit: circa 204 righe.

Valore:

- independence logic esplicita;
- riduzione del rischio di source amplification.

Per noi:

**STRONG REIMPLEMENT CANDIDATE**.

Regola:

dieci articoli derivati dalla stessa agenzia non valgono dieci fonti indipendenti.

### E. source_quality.py

Path:
src/claim_polygraph_ng/analysis/source_quality.py

Dimensione audit: circa 283 righe.

Valore:

- qualità fonte separata dalla stance;
- classificazione source type.

Per noi:

**ADAPT CON ATTENZIONE**.

Non creare un misterioso score globale di “affidabilità del giornale”.

Preferire attributi descrittivi:

- primary/secondary;
- official/non-official;
- original/copy;
- recency;
- directness;
- methodological transparency;
- data/document source.

### F. temporal_verification.py

Path:
src/claim_polygraph_ng/analysis/temporal_verification.py

Dimensione audit: circa 235 righe.

Valore:

- temporal scope come fase di verifica esplicita.

Per noi:

**HIGH PRIORITY DESIGN DONOR**.

Il nostro progetto è più temporale di Polygraph, quindi il modulo finale sarà nostro e più ricco:

- statement date;
- claim reference interval;
- evidence effective date;
- publication date;
- observed date;
- role interval;
- law/policy effective interval;
- superseded evidence.

### G. numerical_verification.py

Path:
src/claim_polygraph_ng/analysis/numerical_verification.py

Dimensione audit: circa 400 righe.

Per noi:

**HIGH PRIORITY DESIGN DONOR**.

Serve per:

- percentuali;
- delta;
- unità;
- denominatori;
- intervalli;
- rounding;
- baseline;
- confronto fra periodi.

Da integrare anche con structured data provider come DVNS, ISTAT ed Eurostat.

### H. cost_ledger.py

Path:
src/claim_polygraph_ng/application/cost_ledger.py

Dimensione audit: circa 309 righe.

Valore:

- paid operation receipt;
- token usage;
- cost measured/upper-bound;
- attempt count;
- duration;
- provider/task.

Per noi:

**REIMPLEMENT EARLY, NON DOPO**.

Un side-project automatico deve sapere quanto costa ogni:

- source;
- person;
- content item;
- finding;
- provider;
- model.

### I. providers/idempotent.py

Path:
src/claim_polygraph_ng/providers/idempotent.py

Dimensione audit: circa 432 righe.

Valore:

- paid-provider calls durable;
- retry ambiguity;
- idempotent operation keys;
- recovery.

Per noi:

**STRONG DESIGN DONOR**.

Non serve copiare l'intera implementazione, ma ogni chiamata costosa deve avere operation key e receipt persistente.

### J. original_source_resolver.py

Path:
src/claim_polygraph_ng/application/original_source_resolver.py

Dimensione audit: circa 205 righe.

Per noi:

**ADAPT CON SOURCE CANONICALIZATION**.

Obiettivo:

- risalire dalla ripubblicazione alla fonte originaria;
- riconoscere syndication;
- preferire documento/statement originale.

### K. near_duplicates.py

Path:
src/claim_polygraph_ng/analysis/near_duplicates.py

Dimensione audit: circa 151 righe.

Per noi:

**REIMPLEMENT WITH EMBEDDINGS + DETERMINISTIC FEATURES**.

Serve a:

- deduplicare claim;
- trovare reiterazioni;
- trovare possibili contradiction candidates.

## Claim Polygraph modules da NON portare in v0

- Next.js investigation dashboard;
- human review UX;
- full LangGraph orchestration;
- entire evaluation-history framework;
- SQLite-specific persistence;
- social-specific pipelines non necessarie;
- research phases e migration artifacts interni al progetto.

## Loki / OpenFactVerification — POC donor

Upstream:
https://github.com/Libr-AI/OpenFactVerification

Audit HEAD: 6e1ee9e.

Licenza: MIT.

### A. Decompose.py

Circa 138 righe.

**POC DIRECTLY OR ADAPT**.

Valutare qualità su:

- dichiarazioni italiane brevi;
- interviste;
- frasi compound;
- claim con tempo/luogo/quantità.

Output nostro deve avere atomic claim strutturato, non solo stringa.

### B. CheckWorthy.py

Circa 53 righe.

**POC DIRECTLY**.

È abbastanza piccolo da essere sostituibile.

Benchmarkarlo contro classifier economici/non-generativi.

### C. QueryGenerator.py

Circa 60 righe.

**POC DIRECTLY, THEN LIKELY REIMPLEMENT**.

Il query planner nostro dovrà distinguere:

- primary-source query;
- existing fact-check query;
- historical person query;
- structured-data query;
- open-web escalation.

### D. ClaimVerify.py

Circa 97 righe.

**DO NOT USE AS PUBLICATION AUTHORITY**.

Può essere un verifier signal, ma il verdict finale deve passare dal nostro evidence ledger + policy.

### E. Retriever/base.py

Circa 235 righe.

**REFERENCE ONLY**.

La nostra retrieval abstraction deve essere provider-neutral e includere structured data providers.

### F. data_class.py

Circa 131 righe.

**REFERENCE ONLY**.

Il dominio nostro è già più ricco.

## Meedan Pender — parser/archiver donor

Upstream:
https://github.com/meedan/pender

Audit HEAD: 017b99f.

Licenza: MIT.

### Parti da studiare

- app/models/media.rb;
- app/models/concerns/media_archiver.rb;
- app/models/concerns/media_archive_org_archiver.rb;
- app/models/concerns/media_perma_cc_archiver.rb;
- app/models/parser/base.rb;
- app/models/parser/page_item.rb;
- provider_youtube.rb;
- provider_twitter.rb;
- provider_instagram.rb;
- provider_tiktok.rb.

### Decisione

**NON ESEGUIRE PENDER COME SERVIZIO IN V0**.

Estrarre soprattutto:

- URL canonicalization cases;
- provider metadata expectations;
- archive status model;
- asynchronous archive callback pattern;
- error taxonomy.

Implementare il nostro adapter piccolo con Trafilatura/HTTP e archiver separato.

## Alegre

Nessuna extraction map v0.

Il concetto da prendere è soltanto:

- embeddings;
- similarity;
- duplicate media/text search.

Implementazione nostra:

- modern embedding adapter;
- Postgres vector search;
- optional reranker.

## CIMPLE

Non importare runtime.

Studiare:

- URI strategy;
- RDF vocabulary;
- ClaimReview mapping;
- SPARQL query patterns;
- release/versioning.

Output futuro:

- RDF/JSON-LD projection generata dal nostro DB.

## DoveVannoINostriSoldi

Licenza AGPL-3.0: non code donor di default.

Riutilizzare tramite:

- API;
- MCP;
- source contracts concordati;
- shared schema futuro eventualmente creato con licenza permissiva.

Pattern architetturali da implementare indipendentemente:

- source policy;
- provenance dates separate;
- source health;
- fail-closed source refresh;
- generated artifact receipts;
- bounded read-only MCP.

## Ordine di implementazione suggerito

### Wave A — domain safety

1. evidence receipt;
2. source family / independence group;
3. deterministic publication policy;
4. citation assurance;
5. cost receipt/idempotent operation.

### Wave B — claim pipeline

1. decomposition;
2. check-worthiness;
3. normalization;
4. query planning;
5. evidence retrieval.

### Wave C — differentiator

1. temporal verification;
2. historical claim matching;
3. position-change relation;
4. contradiction relation;
5. retrospective contradiction.

### Wave D — structured verification

1. numerical verification;
2. DVNS adapter;
3. ISTAT/Eurostat/provider adapters;
4. official-document lookup.

## Regola finale

Se un donor module:

- aggiunge più dipendenze che codice risparmiato;
- forza il nostro domain model;
- impone un servizio separato;
- non ha test sufficienti;
- rende più difficile cambiare provider;

allora va riscritto in piccolo, anche se la licenza permetterebbe di copiarlo.
