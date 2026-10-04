# DoveVannoINostriSoldi — Sister-platform Integration Strategy

Data audit iniziale: 2026-09-21.

Upstream:
https://github.com/Italian-Builders-Org/DoveVannoINostriSoldi

Licenza upstream corrente: AGPL-3.0.

## Contesto umano / collaborazione

Il product owner è già nel gruppo Telegram della community/team di DoveVannoINostriSoldi (DVNS).

Non si assume che il team contribuirà o approverà un'integrazione, ma questo rende realistico progettare fin dall'inizio una collaborazione possibile.

La strategia preferita non è fondere le due codebase e non è forkare DVNS.

È creare una **sister-platform autonoma, interoperabile e federabile**.

Possibili livelli di collaborazione futura:

1. reciproco linking;
2. API/MCP interoperability;
3. shared source contracts;
4. reusable schemas;
5. cross-project contributions;
6. shared civic-data adapters;
7. co-designed provenance standards;
8. eventuali pagine/feature integrate;
9. mantenimento di codebase e branding separati.

## Perché la separazione è utile

DVNS e DichiarazioniPubbliche.it risolvono problemi diversi.

### DVNS

Centro del dominio:

- dati economici e amministrativi pubblici;
- spesa pubblica;
- appalti;
- entrate;
- PNRR;
- PA;
- dataset ufficiali;
- indicatori e confronti con forti caveat semantici.

### Dichiarazioni Pubbliche

Centro del dominio:

- persone pubbliche;
- dichiarazioni;
- claim atomici;
- timeline;
- cambi di posizione;
- contraddizioni temporali;
- evidence;
- fact verification;
- correzioni e repliche.

La relazione naturale è:

**DVNS può essere una evidence/data authority per alcune famiglie di claim.**

Dichiarazioni Pubbliche può invece essere una narrative/public-statement layer che collega dichiarazioni pubbliche a dati verificabili, inclusi quelli esposti da DVNS.

## Source-level audit di DVNS

Clone ispezionato:

- HEAD: 2559335
- data commit HEAD: 2026-09-21

La repo è ampia e contiene oltre diecimila file tracked nel checkout auditato.

## Architettura rilevante

DVNS documenta una pipeline chiara:

1. acquisizione tramite ETL da fonti ufficiali;
2. snapshot/artifact versionati;
3. contratti tipizzati e verifiche;
4. read/aggregation layer;
5. pagine/API/MCP.

Non richiede un database locale per leggere i dataset principali: molti dati pubblici sono artifact versionati.

Questo dimostra che **non tutto deve diventare database live**.

Per dataset relativamente statici, benchmark e authority tables possiamo adottare anche noi artifact versionati con:

- source URL;
- publication date;
- acquisition/observed date;
- SHA-256;
- schema contract;
- caveat;
- verification command.

## Tre idee DVNS da adottare come principi

### 1. Data della fonte != data di osservazione

DVNS distingue:

- reference period;
- publication date;
- acquisition date / observedAt;
- checkedAt.

Questo è indispensabile per un fact-check temporale.

Esempio: un dato ISTAT relativo al 2025, pubblicato nel 2026 e acquisito da noi il 2026-09-21, deve mantenere tutte le date invece di diventare genericamente “dato aggiornato al 21 settembre 2026”.

### 2. Zero != missing != redacted

DVNS mantiene distinti:

- zero osservato;
- dato assente;
- dato oscurato;
- dato non applicabile.

Il nostro Evidence model deve fare lo stesso.

### 3. Upstream failure != zero/success

Se una fonte ufficiale è indisponibile:

- non inventare;
- non convertire in dato vuoto;
- non aggiornare artificialmente freshness;
- conservare ultimo snapshot valido;
- mostrare source degraded.

Questo si allinea perfettamente al nostro fail-closed.

## Source Registry / source-policy

DVNS ha già il concetto di source policy con:

- owner;
- official URL;
- source cadence;
- discovery cadence;
- cache duration;
- stale threshold;
- timeout;
- retry cap;
- cache tag.

Per Dichiarazioni Pubbliche conviene costruire una struttura analoga, aggiungendo:

- source category: primary / institutional / media / social / secondary;
- person coverage;
- topic coverage;
- transcript method;
- archival policy;
- copyright/publication policy;
- claim-discovery priority;
- expected speaker attribution quality.

## Data import standard

DVNS impone tre assi semantici:

1. cosa misura il dato;
2. periodo;
3. provenance.

Questo pattern va generalizzato nel nostro Evidence contract.

Un evidence item deve sempre poter rispondere:

- cosa dimostra realmente?;
- a quale periodo si riferisce?;
- da chi, dove e quando proviene?

Se uno di questi assi manca, va esplicitato.

## Source ledger

DVNS usa source identities, artifact hash, release proof, cardinality reconciliation, canonical URLs e generated artifacts versionati.

Per Dichiarazioni Pubbliche vogliamo un Evidence receipt con:

- evidence_id;
- source_id;
- canonical_url;
- archived_url;
- source hash;
- normalized content hash;
- publication date;
- observed date;
- extraction version;
- parser version;
- transcript version;
- evidence span;
- relationship to claim;
- source family;
- independence group.

## Freshness model

Una lezione chiave di DVNS:

**discovery frequency != publication frequency != data freshness.**

Possiamo controllare una fonte ogni ora senza rendere il suo dato “aggiornato ogni ora”.

Dichiarazioni Pubbliche deve registrare separatamente:

- last_source_check;
- last_new_content;
- content_publication_date;
- fact_reference_period;
- finding_last_evaluated;
- evidence_last_changed.

## MCP strategy

DVNS espone un MCP read-only con:

- list_datasets;
- query_dataset;
- catalog resource;
- related MCP services;
- starter prompts;
- bounded filters;
- pagination/size limits;
- no arbitrary URLs or SQL;
- no mutations.

È una reference eccellente per il nostro futuro MCP.

### Ma non dobbiamo costruire MCP subito

Prima:

- REST/JSON;
- stable domain contracts;
- ClaimReview;
- public search.

Poi MCP può essere un adapter.

### Federazione senza proxy

DVNS documenta un pattern utile: registra servizi MCP correlati senza fare proxy automatico.

Questo è quasi certamente il pattern giusto fra i due progetti.

Dichiarazioni Pubbliche potrebbe esporre un campo/risorsa relatedDataServices con DVNS e altri servizi pubblici. L'agente/client decide quale interrogare.

Vantaggi:

- niente doppia cache;
- niente timeout concatenati;
- provenance chiara;
- ogni servizio mantiene uptime e policy propri;
- nessun coupling di deploy.

## DVNS come evidence provider

Esempio:

Dichiarazioni Pubbliche rileva una dichiarazione numerica su spesa pubblica.

La pipeline:

1. estrae il claim numerico;
2. identifica topic/domain;
3. verifica se esiste un dataset DVNS pertinente;
4. chiama REST/MCP DVNS read-only;
5. salva risposta e provenance come evidence;
6. non tratta DVNS come fonte primaria se DVNS stesso dichiara la fonte primaria;
7. conserva anche riferimenti alla fonte ufficiale sottostante.

Catena:

Statement -> Claim -> DVNS projection -> Official source.

DVNS è una **verified structured-data intermediary**, non l'origine del fatto.

## Cross-link pubblico

Una pagina finding può mostrare:

- finding;
- evidence ufficiale;
- “Esplora i dati” verso DVNS;
- source metadata;
- periodo;
- caveat.

DVNS potrebbe reciprocamente, se il team lo vorrà, collegare dataset o indicatori a dichiarazioni pubbliche correlate registrate da Dichiarazioni Pubbliche.

## Shared identifiers

Da concordare se nasce collaborazione:

- ISTAT territory codes;
- IPA identifiers;
- government/legislature ids;
- public institution ids;
- canonical source ids;
- dataset ids;
- official URLs.

Per le persone conviene usare un namespace nostro con mapping verso:

- Wikidata QID quando appropriato;
- Camera/Senato identifiers;
- Openpolis identifiers;
- official profiles.

Non imporre a DVNS il nostro Person ID.

## Shared contribution opportunities

### Dal loro progetto verso il nostro

- source policy concepts;
- official-data adapters;
- provenance contracts;
- source freshness;
- source health;
- public-data semantics;
- MCP patterns.

### Dal nostro verso il loro

- claim extraction;
- statement provenance;
- timeline UI;
- media/source transcript tooling;
- contradiction/history graph;
- ClaimReview;
- AI-agent public-record tooling.

## Licensing boundary

DVNS è AGPL-3.0.

Se vogliamo mantenere il nostro core con una licenza differente e massima flessibilità commerciale:

- non copiare automaticamente codice AGPL nel core;
- integrare via REST/MCP/API;
- contribuire a DVNS upstream quando una feature appartiene naturalmente a loro;
- mantenere adapters lato nostro scritti indipendentemente;
- concordare esplicitamente licenze per eventuali componenti condivisi nuovi.

Se in futuro entrambe le community decidono una licenza compatibile o dual-license per un package condiviso, si può creare un repository neutro dedicato ai contracts.

## Possibile shared-contract repo futuro

Solo se la collaborazione diventa reale.

Esempio nome:

italian-public-evidence-contracts

Potrebbe contenere:

- source metadata schema;
- provenance receipt schema;
- temporal fields;
- official data identity mappings;
- source health vocabulary;
- ClaimReview extensions;
- JSON Schema;
- fixtures.

Licenza permissiva concordata, per esempio Apache-2.0, per facilitare riuso da entrambe le piattaforme.

Non è necessario crearlo ora.

## Cosa NON fare

- non fare Dichiarazioni Pubbliche come plugin interno DVNS;
- non dipendere dall'uptime DVNS per renderizzare le nostre pagine;
- non duplicare il loro intero dataset;
- non fare proxy permanente del loro MCP;
- non usare i loro indicatori senza i loro caveat;
- non copiare codice AGPL nel core senza una scelta consapevole;
- non promettere collaborazione pubblicamente prima di averla concordata.

## Modello ideale

Due prodotti separati.

### DoveVannoINostriSoldi

What the public data says.

### Dichiarazioni Pubbliche

What public figures said, when they said it, and what the evidence says.

Collegati tramite sources, IDs, API, MCP discovery, hyperlinks e provenance.

Questo dà valore a entrambi senza rendere uno dipendente dall'altro.
