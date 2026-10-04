# Processing Worker, Cost Control e Runtime Health v0

Data: 2026-09-22.

Questo documento descrive la prima pipeline runtime realmente consumer della
queue PostgreSQL di Dichiarazioni Pubbliche. L'ordine operativo è:

**deterministico -> gratuito -> economico -> costoso soltanto se necessario**.

## Queue worker

Implementazione:

- poc/dichiarazioni_pubbliche/queue_runtime.py
- poc/dichiarazioni_pubbliche/worker_daemon.py
- db/job_queue.v0.sql

PostgreSQL resta l'unica queue. Il contract include enqueue idempotente,
SKIP LOCKED, lease renewal, reaper delle lease scadute, retry/backoff,
dead-letter, defer senza consumare attempt, BLOCKED esplicito, unblock e
singleton lock locale del worker.

Una lease scaduta non può più lasciare un job zombie in RUNNING.

## Percorso platform-first

Implementazione: poc/dichiarazioni_pubbliche/platform_transcript.py.

Per Pulp il resolver parte da RSS, cerca la copia YouTube, preferisce marker di
episodio come Pulp Podcast #64 al solo fuzzy title, sonda la caption italiana e,
quando disponibile, cattura soltanto JSON3. Non scarica video/audio.

Le copie YouTube members-only/private vengono classificate access-restricted:
nessun retry infinito e nessun tentativo di aggirare l'entitlement. Se l'RSS
pubblico espone audio, il contenuto passa alla lane ASR.

## Canonical transcript fail-closed

Con un solo transcript candidate:

- segmenti ordinari possono essere RESOLVED;
- segmenti con numeri, negazioni o altri sensitive token diventano
  TRANSCRIPT_UNCERTAIN;
- publication_blocked = true;
- una seconda trascrizione indipendente è necessaria prima che un finding
  materiale possa dipendere da quel token.

## Private artifact store

Default: ~/.local/share/dichiarazioni-pubbliche/

Guardrail:

- directory 0700;
- file 0600;
- scritture atomiche;
- raw caption/ASR response fuori dal repository;
- nessun media audio/video persistito dalla lane URL-ASR.

## Remote ASR

Implementazione: poc/dichiarazioni_pubbliche/remote_asr.py.

La lane primaria implementata è Groq whisper-large-v3-turbo. Il contract usa
l'endpoint OpenAI-compatible di Groq, verbose_json e segment timestamps.
Quando l'origine è un podcast RSS con URL audio pubblico, viene passato
direttamente l'URL: il MiniPC non deve scaricare l'MP3 solo per inoltrarlo.

Documentazione upstream verificata il 2026-09-22:

- https://console.groq.com/docs/api-reference
- https://console.groq.com/docs/speech-to-text

Il prezzo documentato di whisper-large-v3-turbo al momento della verifica era
USD 0,04 per audio-hour. È un policy input versionabile, non una garanzia
permanente.

Stato MiniPC: GROQ_API_KEY non è configurata nel runtime Dichiarazioni Pubbliche. I job ASR
sono quindi BLOCKED con GROQ_API_KEY_MISSING: zero richiesta di rete e zero
costo finché la credenziale non viene configurata esplicitamente.

## Cost accounting e circuit breaker

Ogni operazione provider può scrivere provider_receipt con provider/model,
operation, request ID, input bytes/seconds, costo stimato, status e receipt JSON.

Il worker fa budget preflight prima di una lane a costo:

- USD 5/giorno globale;
- USD 1/giorno per source;
- USD 0,25 per job.

Il worker ufficiale sul MiniPC usa inoltre un lock file 0600 per evitare
concorrenza accidentale fra timer e invocazioni manuali.

## Health digest

Implementazione: poc/dichiarazioni_pubbliche/health_digest.py.

Output privato: ~/.local/state/dichiarazioni-pubbliche/health.json.

Permessi: directory 0700, file 0600.

Il digest espone soltanto aggregati di queue, blocker, source health, content
status, receipt/costi, transcript counts, atomic-claim counts/tipi, evidence
candidate/observation status, verification assessment, finding publication
status, relation candidate, reanalysis trigger, speaker identity provenance e private storage. Non contiene
transcript text, evidence body, raw error messages o secret.

## Claim extraction runtime

Implementazione:

- `config/claim-extraction.v1.json`;
- `poc/dichiarazioni_pubbliche/claim_windows.py`;
- `poc/dichiarazioni_pubbliche/claim_runtime.py`;
- persistenza tramite `QueueRuntimeStore.insert_atomic_claims()`.

Il contract evita di duplicare il transcript nella queue: un window job salva
soltanto segment IDs/indices, hash, limiti temporali, stima token, model e
prompt version. Il testo viene ricostruito dal canonical transcript soltanto
quando il job viene realmente eseguito.

Un claim extractor può diventare eseguibile solo se passano tutti i gate:

1. credenziale OmniRoute disponibile al worker;
2. costo massimo per 1k total-token configurato esplicitamente; zero è ammesso
   soltanto se l'operatore ha verificato zero marginal cost;
3. canary **non banale** sullo stesso model/prompt path;
4. budget globale/source/job ancora disponibile.

Il canary non usa `Return OK`: quel probe minimale aveva prodotto un falso
positivo. Usa invece lo stesso schema JSON e una piccola frase italiana con
claim numerico.

La risposta model viene validata fail-closed:

- claim type in allowlist;
- max claims/window;
- source segment indices obbligatori e confinati alla window;
- claim text bounded;
- JSON response bounded;
- nessun claim produce automaticamente un finding.

`atomic_claim` e `claim_segment` vengono scritti con ID deterministici.
Rerun identici sono idempotenti; output materialmente diversi non sovrascrivono
silenziosamente quelli precedenti.

### Queue fan-out rule

La queue contiene **solo lavoro eseguibile**.

Durante un canary iniziale erano stati materializzati 1.467
`CLAIM_EXTRACT_WINDOW BLOCKED` su 11 contenuti mentre OmniRoute era
indisponibile. Questo è stato riconosciuto come write amplification inutile.

Migrazione:

`db/migrations/20260922-collapse-disabled-claim-fanout.sql`

Risultato live MiniPC:

- 1.467 child BLOCKED rimossi;
- 11 parent riportati a `CLAIM_EXTRACT BLOCKED`;
- windows non materializzate finché capability + cost gate non passano;
- windows rigenerabili deterministicamente dal canonical transcript.

Il queue contract live rimuove inoltre la vecchia funzione
`enqueue_blocked_processing_job`.

## Runtime proof MiniPC — 2026-09-22

Partenza: 20 job reali TRANSCRIPT_RESOLVE_PLATFORM Pulp in QUEUED.

Risultato:

- 20/20 resolver completati;
- 11 contenuti caption-first;
- 9 contenuti ASR fallback;
- 6 dei 9 fallback dovuti a copie YouTube members-only;
- 11 caption catturate senza video/audio;
- 11 transcript variants;
- 30.006 raw transcript segments;
- 30.006 canonical transcript segments;
- 4.635 canonical segments publication-blocked;
- 11 CLAIM_EXTRACT bloccati sul blocker OmniRoute;
- 9 TRANSCRIPT_ACQUIRE_ASR bloccati su GROQ_API_KEY_MISSING;
- 42 job completati;
- 20 job bloccati;
- 0 job queued al termine della prova;
- 34 provider receipts;
- costo stimato osservato: USD 0,00;
- private transcript runtime: circa 24,1 MB / 38 file.

Claim runtime proof aggiuntivo:

- canary significativo sulla route
  `antigravity/gemini-3.8-flash-tiered`: HTTP 400 `bad_request` in circa
  5,15 s sul runtime ufficiale corrente;
- quindi zero fan-out e zero chiamate claim a pagamento;
- persistence canary sul PostgreSQL reale: 1 `atomic_claim` + 1
  `claim_segment` inseriti, verificati e cancellati; residui 0;
- baseline dopo claim-runtime wave: 91/91 test verdi + benchmark deterministico 5/5;
- baseline dopo official-evidence runtime v1: 111/111 test verdi + benchmark deterministico 5/5;
- baseline corrente dopo deterministic verification/reanalysis/review v1: **137/137 test verdi + benchmark deterministico 5/5** su Mac e MiniPC.
- baseline corrente dopo speaker provenance/public projection v1: **149/149 test verdi + benchmark deterministico 5/5** su Mac e MiniPC.
- baseline corrente dopo ClaimReview/correction/right-of-reply policy v1: **163/163 test verdi + benchmark deterministico 5/5** su Mac e MiniPC.

## User services attivi

Sul MiniPC sono enabled + active:

- dichiarazioni-pubbliche-source-poll.timer;
- dichiarazioni-pubbliche-worker.timer;
- dichiarazioni-pubbliche-health.timer.

Cadence: source poll circa 5 minuti + jitter, worker circa 2 minuti + jitter,
health digest 15 minuti.

## Blocker reali rimasti

1. Claim extraction: l'artefatto OmniRoute ufficiale corrente non completa
   ancora la route tiered su prompt reali. Executor, cost gate e DB persistence
   sono già implementati; manca soltanto un runtime provider sano e la
   configurazione least-privilege della credenziale/cost rate.
2. Remote ASR: la lane è implementata ma manca GROQ_API_KEY nel runtime.

Questi blocker sono modellati come BLOCKED, non come retry infiniti.
