# Claim Extraction Benchmark + Pulp Long-form Scaffold

Data: 2026-09-22.

## 1. Benchmark Giuliani: harness pronto, run live bloccato

Implementazione:

`poc/dichiarazioni_pubbliche/claim_extraction_benchmark.py`

Ground truth:

`poc/content/raffagiulians-bollo-2026/content-audit.json`

Il benchmark usa i 36 claim già curati soltanto nella fase di valutazione. Il prompt inviato al modello contiene il transcript timestamped e la tassonomia dei tipi, ma **non** i claim ground-truth, i loro assessment o le evidence.

Metriche previste:

- claim recall;
- claim precision;
- possibili split/merge;
- type accuracy sui match;
- speaker attribution accuracy;
- check-worthiness accuracy;
- numeric-sensitive detection;
- latency;
- cost, quando il provider la espone.

Il matching v0 è deterministico e usa una combinazione di similarità testuale, distanza temporale e speaker. È un benchmark iniziale riproducibile, non una metrica semantica definitiva: i casi marginali vanno ispezionati prima di usare i numeri come acceptance gate.

### Stato live

Target mantenuto:

`antigravity/gemini-3.8-flash-tiered`

Sul runtime authority MiniPC:

- piccolo canary: 200;
- richiesta claim-extraction reale: 400;
- prompt neutri non banali: 400/timeout;
- produzione ufficiale: OmniRoute 3.8.50;
- il precedente fix tiered documentato in ControlCenter apparteneva a un runtime locale/fork e non è ammesso come soluzione production.

Per questo il repository conserva un diagnostic receipt, non un report di precision/recall inventato:

`poc/benchmarks/claim-extraction/20260922-gemini-3.8-flash-tiered/diagnostic.json`

Riprendere il run live soltanto dopo il cutover a un artefatto OmniRoute ufficiale che include/supersede il fix del tiered path.

### Timestamp acceptance deterministica — DP-207 chiuso il 5 ottobre 2026

La fixture Giuliani è ora anche il percorso eseguibile di acceptance per la provenienza
temporale, indipendente dal provider live. `timestamp_acceptance.py` valida senza chiamate
esterne:

- 84 segmenti canonici su 444,84 secondi;
- 36 claim e 57 edge claim→segmento;
- timestamp sorgente contenuto nel range dei segmenti con tolleranza documentata massima
  di 500 ms;
- C07/C08/C09 ancora marcati numeric-sensitive;
- segmenti 414–434s attribuiti a `Giorgia Meloni (inserted clip)`, non al narratore;
- timestamp mancante, malformato o fuori range respinto/held invece di diventare `0:00`;
- claim ID stabili al replay, senza provider call e senza finding/pubblicazione collaterale.

Il canary PostgreSQL isolato sul MiniPC persiste 36 claim, 84 segmenti e 57 edge e al
secondo inserimento restituisce ancora 36 record idempotenti. Il read-back mantiene
separati publication time, observation time e media offsets; produce 0 finding e 0
provider receipt. Il canary viene eseguito in uno schema temporaneo e rimosso integralmente
dopo il test.

Hash fixture accettati:

- audit: `aea03c8b1f607b219c43d33b9db094738fd1717b3de2265813fb66a5095bf3b3`;
- transcript file: `cba86393f725eedd22fe81595843ccbd2374a0874db2394b113f3f13ea4e53ad`;
- transcript content: `06ab8ecac12f71145834b559495a691cd669ff3636b73b8b3d6120a6c761b212`.

Il **live claim-extraction resta bloccato da DP-202**. La chiusura di DP-207 certifica il
contratto timestamp/segmento e il percorso fixture, non il funzionamento del provider live.

## 2. Pulp #64: preparazione long-form completata fino al gate LLM

Contenuto:

- YouTube ID: `QaE00l6JZ8w`;
- episodio: Pulp Podcast #64 con Beppe Grillo;
- policy: caption-first, nessun download video/audio per il first pass.

Il runtime MiniPC conserva il transcript/caption completo soltanto nel private artifact store:

`~/.local/share/dichiarazioni-pubbliche/transcripts/pulp-grillo-2026-09-21/`

Il Git repository contiene invece solo uno scaffold senza transcript integrale:

`poc/content/pulp-grillo-2026-09-21/content-audit.scaffold.json`

### Cattura del 22 settembre

La caption JSON3 è stata riacquisita senza media e normalizzata:

- 1.350.090 byte;
- raw SHA-256 `22d319cf58d4df9d042b0bf56553b8c551bf974c3c683d4c8156207b9876663c`;
- normalized-segments SHA-256 `9bfc7d71c43bb061a4a487f3f5a9f90adf2524ae47d2cced42d69f2c04c60633`;
- 1.981 segmenti;
- 67.821 caratteri;
- 4.683,56 secondi di coverage;
- 352 segmenti sensibili secondo il pre-filtro corrente;
- 28 capitoli dal podcast RSS;
- 114 finestre chapter-aware, massimo 45 secondi.

Lo storico registry riportava per una precedente cattura JSON3 della stessa dimensione SHA-256 `0784246cc9f4f3b658e076c7e86854f93b10726492119831df545f4629023e35` e 365 segmenti sensibili nel pre-filtro precedente.

Conclusione: le auto-caption di piattaforma sono **source candidates mutabili**. Vanno versionate per hash + acquisition time; non si deve presumere che un URL/video ID produca per sempre lo stesso transcript candidate.

## 3. Privacy/copyright boundary

Il preparatore:

`poc/dichiarazioni_pubbliche/longform_prepare.py`

separa esplicitamente:

- **private runtime**: segment text completo + sensitive signature completa + receipt;
- **public Git scaffold**: hash, tempi, indici, conteggi, categorie sensibili e stato pipeline;
- nessun transcript completo nel Git;
- nessun absolute home path nel Git;
- nessun claim/finding finché claim extraction non è realmente riuscita.

Le sensitive signature pubbliche espongono soltanto la categoria, per esempio `NUMBER`, non il valore originale.

## 4. Stato pipeline Pulp

`DISCOVERY -> CAPTION -> NORMALIZATION -> WINDOWING` è completato.

`CLAIM_EXTRACTION` è **BLOCKED** dal runtime OmniRoute ufficiale.

Di conseguenza:

- secondary ASR materiale: non ancora selezionabile;
- evidence retrieval: non avviata;
- verification: non avviata;
- publication: `POLICY_HOLD`;
- claims: 0;
- findings: 0.

Questo è intenzionale: non trasformare la disponibilità del transcript in un falso ContentAudit “completo”.
