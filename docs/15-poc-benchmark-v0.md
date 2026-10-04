# POC Benchmark v0 — Evidence + Publication Gate

Data: 2026-09-21.

## Scopo

Questo POC non prova ancora a fare crawling o a chiamare un LLM.

Serve a congelare il contratto deterministico che una futura pipeline AI dovrà soddisfare:

1. claim strutturato;
2. evidence receipts realmente fetchati;
3. regola di verifica;
4. finding candidate;
5. publication gate;
6. expected outcome testabile.

L'AI potrà cambiare. Questo contract deve restare stabile.

## Perché partire senza LLM

Se non riusciamo a definire il risultato corretto su pochi casi noti, non abbiamo un benchmark per giudicare Loki, un modello proprietario, un modello economico, un classifier o un futuro agent graph.

Il benchmark è quindi precedente alla scelta del modello.

## Casi v0

### 1. Francesco Rocca — occupazione luglio 2026

Claim riportato: 24,37 milioni di occupati e tasso di occupazione al 63,2%.

Claim source:
https://www.ansa.it/lazio/notizie/2026/09/04/rocca-a-bari-orgoglioso-di-rappresentare-nel-lazio-la-stessa-maggioranza_02d0f9c3-2c23-40c2-876c-1e0c1b5ac816.html

Primary evidence:
https://www.istat.it/comunicato-stampa/occupati-e-disoccupati-dati-provvisori-luglio-2026/

Expected:

- verdict: SUPPORTED;
- publication: PUBLISH.

Questo è il caso numerico semplice.

### 2. Brochure Fratelli d'Italia — minimo storico disoccupazione giovanile 18,4%

Claim source:
https://www.ansa.it/sito/notizie/politica/2026/09/04/il-governo-meloni-supera-il-berlusconi-ii-il-record-di-longevita-e-la-festa_70bfd96c-a438-41fc-ba4b-3108938afbc8.html

Primary evidence:

- maggio 2026, 15,1%:
  https://www.istat.it/comunicato-stampa/occupati-e-disoccupati-dati-provvisori-maggio-2026/
- giugno 2026, 18,4%:
  https://www.istat.it/comunicato-stampa/occupati-e-disoccupati-dati-provvisori-giugno-2026/

Expected:

- verdict: FACTUALLY_FALSE;
- publication: PUBLISH.

Motivo: un valore ufficiale inferiore (15,1%) era già stato pubblicato, quindi 18,4% non può essere il minimo storico.

### 3. Brochure Fratelli d'Italia — picco storico tasso di occupazione 62,9%

Claim source:
stesso articolo ANSA sopra.

Evidence:

- giugno 2026: 62,9%;
- luglio 2026: 63,2%, pubblicato da ISTAT il 1 settembre 2026.

Expected:

- verdict: OUTDATED_DATA;
- publication: PUBLISH.

Il punto importante è temporale: il dato più alto era già disponibile prima della manifestazione riportata il 3-4 settembre.

### 4. Meloni / bollo auto — candidate contradiction

Source sulla dichiarazione del 2016 e sul confronto 2026:
https://www.ansa.it/sito/notizie/topnews/2026/09/17/scintille-renzi-meloni-sul-bollo-mi-davi-del-venditore-di-pentole-io-realizzo_0a91935b-177a-435d-8556-73162787cb10.html

Source sulla posizione 2026:
https://www.ansa.it/sito/notizie/politica/2026/09/16/meloni-abolizione-del-bollo-pensata-per-chi-usa-auto-e-moto_bcdb3555-3127-4c38-80c1-df662326f108.html

Expected:

- verdict: NO_CONTRADICTION_ESTABLISHED;
- publication: NO_FINDING.

Perché: nel testo del 2016 riportato da ANSA, la critica riguarda l'annuncio, il momento politico e Renzi; non stabilisce da sola una posizione “sono contraria all'abolizione del bollo”.

Questo caso è volutamente nel benchmark per impedire al contradiction engine di generare falsi positivi.

### 5. Synthetic control

Claim artificiale: a luglio 2026 il tasso di occupazione era 99%.

Evidence: ISTAT 63,2%.

Expected:

- FACTUALLY_FALSE;
- POLICY_HOLD nel gate tecnico.

Nota: è solo un controllo di sanità del benchmark. Il gate riconosce esplicitamente i casi sintetici e ne impedisce la pubblicazione.

## Implementazione

Code:

- poc/dichiarazioni_pubbliche/models.py
- poc/dichiarazioni_pubbliche/evaluator.py
- poc/dichiarazioni_pubbliche/gate.py
- poc/dichiarazioni_pubbliche/benchmark.py

Fixtures:

- poc/fixtures/italian_cases.json

Tests:

- tests/test_poc_benchmark.py

## Gate v0

Per SUPPORTED / FACTUALLY_FALSE / OUTDATED_DATA:

- deve esistere evidence fetchata;
- le material assertions devono essere coperte;
- nel POC numerico deve esserci almeno una PRIMARY_OFFICIAL evidence;
- blocker -> POLICY_HOLD;
- insufficient -> NEEDS_MORE_EVIDENCE;
- no contradiction -> NO_FINDING.
- synthetic benchmark source -> POLICY_HOLD.

Questo è intenzionalmente conservativo.

Le verifiche storiche filtrano inoltre le evidenze in base alla loro publication_date: un dato pubblicato dopo la dichiarazione non può essere usato per sostenere che il claim fosse già outdated nel momento in cui è stato pronunciato.

## Comandi

Benchmark:

PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark

JSON:

PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark --json

Test:

PYTHONPATH=poc python3 -m unittest discover -s tests -v

## Cosa NON dimostra ancora

- che un LLM estragga correttamente i claim;
- che trovi automaticamente le fonti;
- che risolva lo speaker;
- che la source independence funzioni;
- che il contradiction engine generalizzi;
- che la tassonomia legale/editoriale sia definitiva;
- che questi finding siano pronti per produzione.

Il POC dimostra soltanto che abbiamo iniziato a trasformare la metodologia in contratti eseguibili e regressioni.

## CI

La workflow .github/workflows/poc.yml esegue:

- compileall;
- unit tests;
- benchmark deterministico.

Qualsiasi futuro adapter LLM o retrieval deve essere integrato senza rompere questa baseline.
