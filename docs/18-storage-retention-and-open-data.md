# Storage, Retention and Open Data

Data: 2026-09-21.

## Decisione

Non usare:

- Obsidian come database canonico;
- Git come database operativo;
- una cartella piena di MP4;
- un vector DB come source of truth.

Usare tre livelli distinti.

## 1. Operational source of truth

### PostgreSQL

Contiene dati strutturati:

- Source;
- Person;
- ContentItem;
- Appearance;
- Speaker;
- TranscriptVariant;
- TranscriptSegment;
- AtomicClaim;
- Evidence;
- Finding;
- ClaimRelation;
- Correction;
- RightOfReply;
- Job;
- ProviderReceipt;
- CostReceipt;
- SourceHealth.

Postgres può inizialmente includere anche:

- full-text search;
- pgvector;
- job queue semplice.

### Object store

Sul MiniPC v0 può essere un filesystem content-addressed.

In futuro può diventare:

- S3;
- Cloudflare R2;
- MinIO;
- altro S3-compatible.

Contiene soltanto gli artifact che conviene davvero conservare.

## 2. Transient media spool

Video e audio usati per estrazione non sono patrimonio permanente del progetto.

Lifecycle:

discover
-> acquire media o audio
-> hash
-> transcribe
-> optional secondary ASR o frame extraction
-> persist transcript + receipt + hashes
-> delete media.

Default:

DELETE MP4/AUDIO AFTER SUCCESSFUL EXTRACTION.

Hold temporaneo soltanto se:

- secondary ASR pending;
- speaker diarization pending;
- visual evidence pending;
- capture o transcript hash non scritto;
- pipeline incident da debuggare.

Anche in questi casi deve esistere un TTL.

## Purge contract

È stato aggiunto un primo contract eseguibile:

poc/dichiarazioni_pubbliche/retention.py

Il media può essere cancellato soltanto se:

- transcript_status = complete;
- content_hash_status = complete;
- provenance_status = complete;
- transcripts/ esiste;
- receipts/ esiste.

La funzione elimina soltanto media/.

Test:

tests/test_retention.py

## Applicazione al primo ContentAudit

Per il Reel raffagiulians:

- MP4 temporanei eliminati;
- audio temporanei eliminati;
- transcript JSON conservati;
- metadata conservati;
- receipts conservati;
- hash conservati.

I due item LifeOS interessati sono passati da circa 45 MB complessivi di media a circa 36 KB di metadata e transcript.

Una copia persistente del transcript necessario al progetto è ora anche
conservata nel runtime Dichiarazioni Pubbliche del MiniPC:

~/.local/share/dichiarazioni-pubbliche/transcripts/raffagiulians-bollo-2026.json

I residui media/audio temporanei del Reel sono stati cancellati dopo il
salvataggio.

Per Pulp Podcast #64 con Beppe Grillo è stato applicato il percorso ancora più
economico: nessun media download. È stata conservata soltanto la caption
automatica italiana originale di YouTube più metadata/hash in:

~/.local/share/dichiarazioni-pubbliche/transcripts/pulp-grillo-2026-09-21/

## 3. Public open-data projection

Open source e open data sono due cose diverse.

Il repository pubblico può contenere:

- IDs;
- source URL;
- publication dates;
- timestamps;
- normalized claims;
- short source excerpts quando consentito;
- evidence metadata;
- finding;
- rationale;
- model e policy version;
- hashes;
- correction history;
- speaker attribution;
- relation graph.

Non deve automaticamente contenere:

- MP4 altrui;
- audio altrui;
- copie integrali di podcast;
- transcript integrali di opere protette;
- screenshot massivi.

La pubblicazione di un transcript integrale dipende da licenza, diritti e policy della fonte.

La projection v1 è ora eseguibile in `poc/dichiarazioni_pubbliche/public_projection.py` e
riapplica fail-closed i gate di finding, transcript, evidence e speaker provenance;
non esporta transcript text o evidence body.

## Transcript interno vs pubblico

### Interno o canonico

Conservare:

- raw transcript per provider;
- canonical transcript;
- timestamped segments;
- uncertainty markers;
- ASR receipts.

Il testo è piccolo rispetto al media ed è essenziale per re-analysis.

### Pubblico

Pubblicare per default:

- claim;
- timestamp;
- breve excerpt necessario;
- link alla fonte originale;
- evidence e rationale.

Full transcript soltanto se la policy diritti lo consente.

## Git strategy

Non far crescere all'infinito il repository codice con milioni di record.

Fase iniziale:

- piccoli fixture e dossier rappresentativi possono vivere nel repo;
- schema e test restano nel code repo.

Quando il dataset cresce:

- code repo;
- data repo o release dataset separato;
- API pubblica;
- snapshot JSONL o Parquet versionati.

Possibili distribuzioni future:

- GitHub Releases;
- repository dichiarazioni-pubbliche-data;
- Hugging Face Datasets;
- Zenodo;
- object storage pubblico.

## Obsidian

Obsidian può essere una projection generata:

- pagina persona;
- pagina topic;
- dossier content;
- queue o incident view.

Non deve essere authoritative storage.

DB -> generated Markdown.

Non Markdown -> DB.

## Backup

Sul MiniPC:

- backup PostgreSQL;
- backup transcript e object metadata;
- public dataset export;
- config e source registry;
- secrets esclusi.

DP-311 reviewer-authority credentials remain excluded from the ordinary PostgreSQL/public
backup. Historical review receipts must remain verifiable after restart/restore, so the
private authority root requires a separate operator-controlled secret-backup/recovery procedure
before production use. The repository does not copy that root into DB dumps, public artifacts
or general config backups and does not prescribe a vendor-specific secret store. If the
authority root is unavailable after restore, publication remains held.

Il media transient non va incluso nei backup.

## Retention suggested defaults

- downloaded video o audio: delete appena completate tutte le estrazioni richieste;
- failed media job: 24h debug TTL;
- bounded audio window: delete appena conclusa secondary ASR;
- raw transcript: persistent;
- canonical transcript: persistent;
- evidence metadata: persistent;
- source snapshot usato in published finding: persistent secondo policy;
- provider receipt e cost receipt: persistent;
- model cache: allowlist esplicita + size budget.

La policy machine-readable iniziale è:

config/transcription-policy.v1.json

## Storage budget

Imporre:

- max spool GB;
- max model-cache GB;
- max failed-job GB;
- disk high-water mark;
- emergency purge degli artifact transient scaduti.

Il worker deve rifiutare nuovi download se il disco supera la soglia di sicurezza invece di riempire il MiniPC.

Durante il benchmark locale, un tentativo di scaricare faster-whisper
large-v3-turbo ha lasciato un blob modello di circa 1,62 GB. Il benchmark è
stato interrotto e il blob eliminato. Questo dimostra che anche le model cache
devono avere budget, allowlist e garbage collection.
