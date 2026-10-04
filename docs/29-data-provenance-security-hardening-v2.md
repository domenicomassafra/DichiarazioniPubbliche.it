# Data, provenance e security hardening v2

Data: 2026-09-22.

## Obiettivo

Questa wave rende i confini di pubblicazione e ingestione fail-closed anche
quando lo stato persistito è parziale, rigiocato, obsoleto o manipolato fuori
dagli helper amministrativi normali.

Restano invarianti:

- nessuna auto-publication;
- nessun punteggio di affidabilità/verità della persona;
- raw transcript ed excerpt evidence restano privati;
- finding, evidence, observation, speaker attribution, correction e
  right-of-reply richiedono provenance esplicita;
- il MiniPC resta l'unica runtime authority.

## Public projection v2

La projection dichiarazioni-pubbliche-public-v2 espone identificatori di provenance, non
contenuto grezzo.

Per ogni dossier pubblicabile la query verifica:

- verification run e assessment coerenti col finding;
- set evidence del finding identico al set evidence verificato;
- observation effettivamente usate dalla verification, con ID persistiti;
- review ledger APPROVED per evidence candidate, observation, speaker e finding;
- transcript candidate appartenenti allo stesso content del segmento canonico;
- review del finding non antecedente all'ultimo aggiornamento di ogni segmento;
- zero blocker di verification;
- correction e right-of-reply pubbliche solo dopo reanalysis PROCESSED.

La projection espone finding/publication review IDs, candidate/review IDs per
speaker provenance, transcript candidate/variant ID e hash, evidence ID/hash,
review IDs e observation IDs usati dalla verification.

Non espone raw transcript, canonical transcript text o evidence excerpt.

## Replay e idempotenza

I replay non possono più allargare silenziosamente la provenance:

- un claim appena inserito può ricevere i suoi claim_segment; un replay di un
  claim esistente non può appendere segmenti;
- un finding viene creato solo se claim, assessment e set evidence coincidono
  con il verification run; i link finding_evidence vengono creati solo nello
  stesso insert;
- APPROVED non è più accettato dai generic status helper per evidence e
  observations: l'approvazione passa dagli helper transazionali che scrivono
  anche review_event.

## Verification e correction semantics

deterministic-verification-v2 corregge il caso historical maximum: un
counterexample già disponibile alla data della dichiarazione rende la claim
FACTUALLY_FALSE; OUTDATED_DATA resta riservato a informazione successiva.

Ogni correction registrata genera un trigger di reanalysis. La pubblicazione
della correction richiede catena supersedes coerente, current finding ancora
leaf, review sui due finding e reanalysis CORRECTION nello stato PROCESSED.
Il right-of-reply richiede analogamente un trigger RIGHT_OF_REPLY processato.

## Fetch hardening

Evidence runtime mantiene HTTPS, allowlist host/path/metodo, redirect
rivalidati, DNS non-public rifiutato e response-size bounded. Inoltre un
Content-Length noto che non coincide con i byte ricevuti fallisce: una risposta
troncata non viene hashata né messa in cache come evidence completa.

Discovery runtime ora applica HTTPS only, rifiuto di userinfo/porte non
standard/DNS non-public, redirect rivalidati, risposta massima 4 MiB e rifiuto
di Content-Length incoerente o body parziale.

Non esiste ancora un endpoint HTTP pubblico di amministrazione in questa
codebase: auth/CSRF non sono quindi oggi una superficie runtime esposta. Gli
input di review restano CLI/local-operator e sono bounded.

## Retention fail-closed

Il purge dei media transienti avviene solo se il manifest è un file reale,
JSON object valido e <= 1 MiB, transcript e receipts contengono almeno un file
durevole non-symlink, e la directory media non contiene symlink. Manifest
corrotto, directory vuote o symlink non autorizzano alcuna delete.

## Dedup e fixture avversariali

tests/fixtures/adversarial-ingestion-v1.json copre esplicitamente duplicate,
near-duplicate, conflicting sources, changed/deleted pages, missing timestamps,
speaker ambiguity, clip/transcript mismatch, out-of-order corrections, partial
fetch e replayed jobs.

Con timestamp mancante, il provisional key include platform + external ID:
preferisce under-dedup a una falsa fusione di episodi omonimi. Una URL evidence
mutabile continua invece a versionare per content hash.

## Migration order

Migration additiva:

db/migrations/20260922-deep-provenance-security-hardening.sql

Ordine obbligatorio:

1. applicare la migration;
2. verificarne l'idempotenza con una seconda applicazione;
3. distribuire il codice;
4. eseguire suite + benchmark;
5. rigenerare la projection v2.

Il codice v2 non va attivato contro uno schema privo di
verification_run.observation_ids.

## Verifica Mac

Stato prima del rollout MiniPC:

- 185/185 unit/regression test verdi;
- benchmark deterministico 5/5;
- compileall: PASS;
- git diff --check: PASS.

## Runtime proof MiniPC

Prova osservata sul MiniPC, runtime authority:

- mirror: /home/udodo/src/DichiarazioniPubbliche.it, senza directory .git;
- database: dichiarazioni_pubbliche, user udodo;
- migration production applicata due volte con ON_ERROR_STOP, entrambe PASS;
- verification_run.observation_ids presente una sola volta;
- constraint verification_run_provenance_arrays_check presente;
- suite sul mirror live: 185/185 PASS;
- benchmark deterministico sul mirror live: 5/5 PASS;
- projection production rigenerata come dichiarazioni-pubbliche-public-v2:
  dossier_count=0, omitted_count=0;
- index.json e index.jsonld production: mode 0600;
- source-poll.timer e worker.timer: active;
- service oneshot source-poll e worker: inactive a riposo.

La queue production prima e dopo il rollout è rimasta invariata:

- CLAIM_EXTRACT BLOCKED: 11;
- TRANSCRIPT_ACQUIRE_ASR BLOCKED: 9;
- TRANSCRIPT_ACQUIRE_CAPTION COMPLETED: 11;
- TRANSCRIPT_CANONICALIZE COMPLETED: 11;
- TRANSCRIPT_RESOLVE_PLATFORM COMPLETED: 20;
- finding pubblici: 0.

### Canary PostgreSQL isolato

L'utente runtime non ha il privilegio CREATEDB, quindi il canary non ha elevato
privilegi e non ha chiesto un database separato. È stato usato uno schema
isolato lane04_hardening_canary nello stesso PostgreSQL, poi eliminato.

Prove:

- schema v0 applicato nello schema canary: PASS;
- migration hardening applicata due volte: PASS/idempotente;
- fixture tests/fixtures/postgres-provenance-canary.sql: PASS;
- publish_finding_with_review reale: publish=True;
- projection con provenance completa: dossier_count=1, omitted_count=0;
- dopo modifica di canonical_transcript_segment.updated_at senza nuova finding
  review: dossier_count=0, quindi freshness fail-closed confermato.

Al termine lo schema canary e le directory temporanee sul MiniPC sono stati
rimossi.

## Security scan

La configurazione discovery non contiene feed URL HTTP e la scansione del
codice operativo non ha trovato pattern di private key, AWS access key o token
OpenAI hard-coded. Nessun nuovo endpoint pubblico o segreto è stato introdotto.
