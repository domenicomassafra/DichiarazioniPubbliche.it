# Deployment, Scaling, Sources and UX

Data: 2026-09-21.

## Premessa

Il MiniPC può essere il backend iniziale.

Non deve però essere progettato come unico motore computazionale per sempre.

Separare:

- control plane;
- data plane;
- compute workers;
- public serving.

## V0 — tutto controllato dal MiniPC

Sul MiniPC:

- PostgreSQL;
- API;
- source scheduler;
- job queue;
- OmniRoute;
- lightweight workers;
- local ASR fallback;
- canonical transcript e data store.

Il sito pubblico serve quasi esclusivamente dati precomputati.

Non eseguire un LLM per ogni page view.

## Public exposure

Esporre soltanto:

- web frontend;
- read API;
- submission e right-of-reply endpoint protetto.

Non esporre:

- PostgreSQL;
- OmniRoute admin o runtime ports;
- worker endpoints;
- object-store private internals.

Un reverse proxy, tunnel o CDN può stare davanti al MiniPC.

## Quando cresce

Migrare a pezzi, non fare un big bang.

Ordine probabile:

1. CDN e static assets;
2. public object storage;
3. compute workers;
4. managed o dedicated Postgres;
5. API e web origin.

Il Source Registry e i job contract non devono cambiare.

## Scaling ingestion

Errore:

200 persone
x decine di fonti
x tutti i video completi
x STT locale quotidiano.

Non scala.

Pipeline corretta:

### Discovery

Molto economica:

- RSS o Atom;
- YouTube channel feeds;
- podcast RSS;
- social metadata;
- sitemap;
- official APIs.

### Candidate triage

Prima di trascrivere:

- persona tracciata?;
- topic tracciato?;
- durata;
- caption già disponibili?;
- chapter o description;
- novelty;
- probabilità di claim verificabili;
- source importance.

### Transcript acquisition

Ordine:

1. manual captions;
2. platform transcript;
3. auto captions;
4. remote STT;
5. local fallback.

### Deep verification

Solo per claim check-worthy.

## Audio-first

Per podcast e interviste dove il contenuto visivo non è informativo:

- non scaricare il video;
- acquisire audio o transcript;
- frame extraction disattivata.

Se un claim fa riferimento a:

- grafico;
- documento mostrato;
- screenshot;
- gesto o oggetto;

allora attivare bounded visual extraction per quel timestamp.

## Pulp Podcast come source class

Pulp Podcast è un ottimo esempio di source ricorrente ad alto valore:

- ospiti pubblici;
- episodi lunghi;
- politica, cultura e attualità;
- capitoli;
- distribuzione podcast e video.

Il 21 settembre 2026 è uscito l'episodio #64 con Beppe Grillo:

- YouTube video ID: QaE00l6JZ8w;
- durata verificata via yt-dlp: 4.683 secondi, circa 78 minuti;
- automatic caption italiana originale disponibile;
- transcript candidate it-orig acquisito senza scaricare audio o video;
- podcast RSS disponibile via Megaphone.

Un source adapter non dovrebbe dire:

scarica ogni episodio intero e trascrivilo localmente.

Dovrebbe fare:

1. il feed scopre l'episodio;
2. parse di titolo, ospite e capitoli;
3. Beppe Grillo matcha il public-person registry;
4. acquire caption o transcript se disponibile;
5. classify transcript;
6. retrieve audio soltanto per missing o sensitive spans;
7. build ContentAudit;
8. purge media.

Fra distribuzione podcast e YouTube la durata riportata non è identica; il
principio operativo non cambia: il contenuto long-form entra transcript-first.

Nel test reale sull'episodio Grillo, il JSON3 delle caption automatiche italiane
pesava circa 1,3 MB mentre il video non è stato scaricato.

Questo è il percorso standard desiderato per long-form YouTube.

Il parser POC ha prodotto:

- 1.981 segmenti;
- 67.821 caratteri di transcript;
- 4.683,56 secondi coperti;
- 365 segmenti con almeno un token sensibile secondo il pre-filtro iniziale.

Quest'ultimo numero non significa 365 secondary-ASR. È volutamente
over-inclusive: la seconda trascrizione viene richiesta soltanto dopo claim
extraction, quando un finding materiale dipende davvero da quei token.

## Source Registry fields

Ogni source ricorrente dovrebbe avere:

- source_id;
- canonical_name;
- source_type;
- official URLs;
- feed URLs;
- platform o channel IDs;
- expected cadence;
- discovery interval;
- language;
- typical duration;
- transcript strategy;
- media retention policy;
- visual importance;
- topic hints;
- person matching mode;
- priority;
- legal e ToS notes;
- last_success;
- degraded status.

Il primo registry machine-readable è:

config/source-registry.v0.json

Contiene già:

- Pulp Podcast / YouTube channel UCY99TnBJ8xyat2lpeN_hcEA;
- feed discovery podcast RSS + YouTube;
- caption-first policy;
- media ephemeral policy;
- Raffaele Giuliani come source social di esempio.

## Source watcher POC

È stato aggiunto:

poc/dichiarazioni_pubbliche/source_watcher.py

Il watcher:

- legge il registry;
- interroga il podcast RSS o il feed YouTube secondo source policy;
- normalizza ContentItem;
- filtra Shorts/promozionali per source policy;
- può interrogare yt-dlp per la presenza di caption italiane;
- restituisce un ingest plan senza LLM.

Prova runtime sul MiniPC per Pulp #64:

- il feed aveva come item più recente uno Short ADV, correttamente filtrato;
- il primo long-form utile risultava Beppe Grillo / Pulp #64;
- caption trovata: automatic_caption it-orig;
- ingest action: ACQUIRE_CAPTION;
- download_media: false;
- fallback: REMOTE_ASR soltanto se la caption è insufficiente.

Sul percorso RSS lo stesso watcher vede direttamente GUID, durata, description
con capitoli e URL MP3 del podcast. L'audio resta fallback: prima prova a
risolvere la copia YouTube e le caption.

Questa è la prima prova concreta che source discovery e transcript planning
possono restare deterministic/cheap.

## Compute policy

### Remote API

Usare per:

- volume;
- burst;
- long content;
- time-sensitive ingestion.

### MiniPC

Usare per:

- orchestration;
- fallback;
- bounded secondary ASR;
- deterministic transforms;
- overnight o background work;
- privacy-sensitive local processing;
- canary e benchmark.

### Multi-provider

OmniRoute deve poter distribuire per:

- quota;
- health;
- prezzo;
- capability;
- accuracy class.

La resilienza arriva da provider diversity, non dal moltiplicare account per aggirare limiti.

## UI/UX è parte del core

Il prodotto non deve sembrare un archivio JSON.

La UI deve permettere di capire un finding quasi immediatamente.

## Tre primary surfaces

### Person

Header:

- nome;
- ruolo;
- topic principali;
- timeline.

Timeline filtrabile:

- statement;
- fact-check;
- position change;
- correction;
- promise o prediction;
- source appearance.

### Topic

Esempi:

- nucleare;
- immigrazione;
- bollo auto;
- giustizia;
- IA;
- spesa pubblica.

Mostra:

- chronology;
- key claims;
- official data;
- people involved;
- changes over time.

Niente ranking politico complessivo.

### ContentAudit

Questa può diventare una delle UX più forti.

Layout:

- video o audio embed a sinistra;
- timeline sotto il player;
- marker sui timestamp con claim;
- transcript sincronizzato;
- finding panel a destra;
- evidence drawer;
- filtro per claim type e assessment.

Click sul finding:

- jump al timestamp;
- mostra parole originali;
- mostra normalized claim;
- mostra evidence;
- mostra rationale;
- mostra uncertainty.

## Discrepancy UX

Per relazioni temporali:

2023 statement
vs
2026 statement

UI side-by-side con:

- stesso topic;
- proposition diff;
- source;
- context;
- relation type.

Non scrivere automaticamente che una persona ha mentito.

Mostrare ciò che è cambiato.

## Visual language

Non dipendere soltanto dai colori.

Ogni stato ha:

- icona;
- label testuale;
- breve spiegazione;
- colore accessibile come supporto.

Esempi:

- Supported;
- Contradicted by evidence;
- Missing context;
- Misattributed;
- Prediction pending;
- Unresolved.

## UX prototyping

Prima del frontend definitivo creare almeno 3 prototipi:

1. editorial o newspaper;
2. GitHub-like evidence graph;
3. modern interactive media timeline.

Testarli sul dossier raffagiulians e su un episodio Pulp.

Non scegliere la UI da mock generici: usarla su contenuti reali e densi.

## Migrazione futura

Se il progetto cresce:

- workers in cloud;
- queue condivisa;
- object store esterno;
- CDN;
- API autoscaling.

Il MiniPC può rimanere:

- control o admin node;
- dev o staging;
- local fallback;
- backup worker.

Non serve cambiare il prodotto per migrare l'infrastruttura.
