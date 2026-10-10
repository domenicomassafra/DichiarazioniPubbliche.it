# Transcription Quality and Routing

Data: 2026-09-21.

## Perché la trascrizione è critica

La pipeline di fact-checking non può trattare lo speech-to-text come fonte infallibile.

Un singolo errore può cambiare un finding:

- 7,5 -> 7;
- 2,3 -> 2;
- una negazione persa;
- un nome proprio sbagliato;
- una legge o un articolo trascritto male;
- una percentuale o una data deformata;
- una citazione attribuita allo speaker sbagliato.

Il ContentAudit raffagiulians-bollo-2026 ha già dimostrato il problema: il primo ASR lungo aveva perso i decimali, mentre una seconda trascrizione bounded ha recuperato 7,5 / 2,3 / 5,2.

## Correzione terminologica

Il primary STT attuale è Groq, provider di inferenza, con whisper-large-v3-turbo.

Non è Grok.

## Principio

Non esiste un singolo transcript considerato infallibile.

Esistono:

1. source captions;
2. transcript raw del provider A;
3. transcript raw del provider B;
4. eventuale forced alignment;
5. canonical transcript derivato;
6. token o segmenti marcati come incerti.

I raw transcript non vengono mai sovrascritti.

## Routing consigliato

### Lane 0 — transcript già esistente

Ordine:

1. sottotitoli manuali ufficiali;
2. transcript o caption ufficiali della piattaforma;
3. sottotitoli automatici della piattaforma.

Se esistono, evitano download e STT completo.

I claim sensibili possono comunque essere ricontrollati sull'audio.

### Lane 1 — remote volume STT

Primary iniziale:

groq/whisper-large-v3-turbo

Motivi:

- multilingua;
- molto veloce;
- costo molto basso;
- timestamp;
- già funzionante attraverso OmniRoute;
- quota gratuita significativa.

La documentazione Groq corrente indica:

- 0,04 USD per ora per Whisper Large v3 Turbo;
- 20 RPM;
- 2.000 RPD;
- 7.200 audio-secondi/ora;
- 28.800 audio-secondi/giorno nel free tier mostrato;
- 25 MB upload nel free tier;
- 100 MB nel dev tier.

28.800 audio-secondi equivalgono a 8 ore audio/giorno.

Il costo paid è abbastanza basso da non giustificare account farming:

- 100 ore = circa 4 USD;
- 1.000 ore = circa 40 USD.

Più account o provider possono essere usati soltanto come entitlements legittimi e conformi ai termini del provider, non per aggirare artificialmente i limiti.

### Lane 2 — accuracy remote

Per segmenti ad alto rischio:

groq/whisper-large-v3

Groq raccomanda Large v3 quando l'applicazione è error-sensitive.

È più costoso di Turbo ma va usato soltanto su finestre brevi, per esempio 15-45 secondi.

Nella documentazione Groq corrente, Large v3 è indicato con WER 10,3% contro
12% per Turbo. Sono benchmark generali del provider, non una garanzia specifica
sull'italiano o sui nostri contenuti, quindi il nostro benchmark resta
necessario.

### Lane 3 — local independent ASR

Già implementato:

faster-whisper

Sul MiniPC Ryzen 7 5700U con 30 GB RAM, il modello small, già caldo, ha trascritto un frammento di 27,2 secondi in circa 9,6 secondi con circa 640 MB RAM.

Ha preservato correttamente:

- 7,5;
- 2,3;
- 5,2.

Ha però commesso errori lessicali su parole vicine.

Conclusione:

ottimo second opinion o fallback, non transcript authority unico.

Sul medesimo tipo di segmento sensibile è stato inoltre provato localmente
faster-whisper large-v3-turbo:

- circa 25 secondi di audio;
- circa 29,9 secondi di warm inference CPU;
- circa 1,66 GB max RSS;
- 7,5 / 2,3 / 5,2 preservati;
- ancora possibili errori lessicali.

Quindi il modello large locale è utilizzabile come bounded accuracy fallback,
ma non conviene come primary bulk transcription sul Ryzen 7 5700U.

### Lane 3A — whisper.cpp opt-in CPU (2026-10-10)

`whisper-cpp-local` (`local/whisper.cpp`) is an additional **operator-enqueued**
`TRANSCRIPT_ACQUIRE_ASR` option. It never downloads a model or audio, and it is
deliberately `proven_in_owner_runtime: false` for automatic routing until a
representative Italian corpus has a reviewed quality/resource receipt. It cannot
substitute for DP-204's Groq live receipt or DP-208's diarization decision.

The worker needs four explicitly configured environment variables:
`DICHIARAZIONI_PUBBLICHE_LOCAL_ASR_AUDIO_ROOT`,
`DICHIARAZIONI_PUBBLICHE_LOCAL_ASR_CLI`,
`DICHIARAZIONI_PUBBLICHE_LOCAL_ASR_MODEL`, and
`DICHIARAZIONI_PUBBLICHE_LOCAL_ASR_MODEL_SHA256`. The model and CPU `whisper-cli`
must already exist. A private-root, mono 16-kHz 16-bit PCM WAV of no more than
30 seconds must match the content duration and explicit job `duration_seconds`,
`audio_sha256`, `local_audio_path`, `canonical_url`, `rights_basis`,
`rights_receipt_id`, and `local_audio_authorized: true`. For
`rights_basis: EXPLICIT_CONSENT`, `consent_confirmed: true` is also mandatory.
The owner must independently verify the rights receipt; a queue payload is not
a legal approval. Model digest, input digest, model identifier, transcript digest,
segments, timestamps, and rights-receipt ID survive in the private transcript
and cost receipt; no WAV or model bytes enter Git or transcript storage. Rejected
input, rights uncertainty, hash mismatch, CLI failure, or timeout puts the job
in `BLOCKED` and creates no canonical/public transcript. Existing speaker
approval and publication gates remain mandatory.

An isolated non-production MiniPC CPU canary on 2026-10-10 used a 4.444-second
Italian test phrase written for this test and synthesized locally on macOS.
`whisper.cpp` source commit `d1be6fde11ac6e0407606b4e42fe72d34add8037`
was built on MiniPC in `/tmp`; the `ggml-tiny.bin` model had SHA-256
`be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21`
(77,691,713 bytes; official model SHA-1 matched). The WAV had SHA-256
`e8fe004ff383df5ea5f9940f8d9693635f140615b105b7cc64d911515bfeef1b`
(142,284 bytes), rights/fixture receipt `synthetic:local-tts:20261010`;
one segment with timestamps 0–4,300 ms was produced in 1.184 s on the first
run and 1.710 s on the measured run, with peak child RSS 180,568 KiB.
Private result text SHA-256:
`e55a6ae2d5007951d5090bcabb631aac768a863998d756bbd07d7766fad0233e`.
This is actual Italian CPU inference, not a representative accuracy benchmark
or automatic fallback approval. The private WAV and model are temporary
test artifacts; no service or production worker was reconfigured.

### Explicit provider admission in the queue worker (2026-10-10)

`provider_optin.configure_provider_clients()` now gates the **actual** worker
runtime. Its defaults disable local ASR, local claim extraction and remote Groq
ASR. `LOCAL_CLAIM_ENABLED=1` and a pinned 64-character
`LOCAL_CLAIM_MODEL_SHA256` require the explicit zero external-token-cost rate
`CLAIM_MAX_USD_PER_1K_TOTAL_TOKENS=0` (all names prefixed by
`DICHIARAZIONI_PUBBLICHE_`). Local claim extraction cannot coexist with an
official `OMNIROUTE_API_KEY`; the official model remains exactly as configured
in `config/claim-extraction.v1.json`. The local canary uses synthetic text and
must produce a bound numeric claim before private jobs can be processed.

`LOCAL_ASR_ENABLED=1` separately requires `LOCAL_ASR_AUDIO_ROOT`,
`LOCAL_ASR_CLI`, `LOCAL_ASR_MODEL`, and `LOCAL_ASR_MODEL_SHA256` under that same
prefix, plus the existing per-job rights and input-hash requirements. Even when
enabled, local ASR is never selected automatically from discovery. Both local
adapters share a nonblocking filesystem CPU admission lock; a busy MiniPC
retries later, with an explicit `LOCAL_INFERENCE_BUSY` status and no inference
or publication. Audio and claim receipts carry model provenance, bounded cost
basis, and an explicit unreconciled/private-review quality status.

A `GROQ_API_KEY` by itself no longer permits the worker to transfer audio to
Groq. Remote ASR requires `GROQ_REMOTE_ASR_ENABLED=1`,
`GROQ_REMOTE_ASR_TERMS_ACCEPTED=1`,
`GROQ_REMOTE_ASR_CONFIDENTIALITY_APPROVED=1`, and
`GROQ_REMOTE_ASR_SPEND_APPROVED=1`, each with the same prefix, plus the separate
`GROQ_API_KEY`. These are explicit owner decisions, not inferred free-tier
entitlement. Runtime quotas remain provider/account-specific and require
separate reservation/accounting before a free-tier-only dispatch claim can be
made. A separate opt-in Antigravity CLI quota transport exists for private
Passage analysis, as documented below; Gemini Developer API use remains separate.

For a real MiniPC synthetic Ollama proof, run
`python3 tools/check_local_provider_loopback.py` on an isolated checkout or
temporary source bundle with Ollama on localhost. It sends only a project-written
numeric sentence; it does not read production corpus data or provider secrets.

### Optional OmniRoute capability selector for private Passage candidates

`provider_optional_route.py` is a fail-closed offline selector linked to the
existing **private** `tools/extract_research_candidates.py` entrypoint through
`--optional-model-catalog <sanitized-json>` and a separately verified
`--optional-model-catalog-sha256 <64-hex-digest>`; an unpinned or changed file
is rejected before provider construction. The catalog must have
`schema_version: 1`, `catalog_origin:
OWNER_VERIFIED_SANITIZED_OMNIROUTE_CATALOG`, `approved_paid_model_ids` and
`models` with exact capability fields (`model_id`, `family`, `billing_tier`,
`catalog_model_verified`, `schema_canary_passed`, `operator_enabled`,
`terms_accepted`, `confidentiality_approved`,
`separate_api_entitlement_verified`, `quota_remaining_requests`,
`quota_remaining_tokens`, `usd_per_1k_total_tokens`,
`paid_owner_authorized`, and for Antigravity CLI `quota_source`,
`quota_observed_at`, `overage_policy`, `single_account_scope`). Credential fields and unknown model fields are
rejected; do not export credentials into this catalog.

The planner evaluates **every supplied actual model** in recognized families:
local, Antigravity **CLI quota**, OpenRouter, Cerebras, Cloudflare AI, Cohere, Groq, Gemini *Developer API*,
Mistral, Moonshot, Nvidia, OpenCode GO and OmniRoute. It chooses exactly one
supported route per batch: verified local zero-external-cost first, then
verified Antigravity CLI quota, verified OpenRouter free, then other separately approved API-free routes,
then explicit paid-model whitelist within a hard dollar budget. The sanitized
receipt records the chosen model, deterministic plan ID and per-model blocker
codes without source text or tokens. Missing rate, schema canary, terms,
privacy grant, quota snapshot, separate API entitlement or spending approval
blocks the route. The `--external-model-data-approved` flag is additionally
required for sending externally. Optional preflight makes **zero** model calls;
actual execution still requires `--execute`, a hard `--max-cost-usd` cap,
rights clearance, fixed source hashes and commit fences. Paid/API routes also
require the approved provider credential and exact local OmniRoute gateway
`http://127.0.0.1:20128`. A selected
`LOCAL_ZERO_EXTERNAL` route is **preflight-only** for private Passage
extraction: execution blocks with
`OPTIONAL_LOCAL_CANDIDATE_ADAPTER_UNAVAILABLE` until a dedicated loopback
candidate adapter exists. An Ollama *atomic claim* adapter does not fulfill
this separate Passage extraction schema. Decimal upper bounds round upward
before cost-cap comparison. No automatic cross-model retry occurs, and the
official DP-201 model remains unchanged.

A verified quota snapshot is an **admission estimate**, not an atomic remote
reservation: it may expire before execution, so a 429/quota response must block
or defer rather than switching provider/accounts. Antigravity CLI quota is a
real supported and distinct capacity; it is not a Gemini Developer API grant.
There is no owner-verified sanitized live catalog
or approved paid whitelist in this repository; free remote routes cannot be
claimed available until real account/model evidence is supplied.

### Antigravity native CLI quota: real, opt-in private Passage adapter

Google's Antigravity CLI supports `/usage` (alias `/quota`) to view current
model-specific remaining requests/tokens. Its quotas are distinct from the
Gemini Developer API's API-key/free-tier quotas; do not demand a separate Gemini
Developer API entitlement for this native CLI route. The verified current
owner runtimes are `agy` 1.3.3 on Mac Studio and 1.3.0 on MiniPC, alongside
official OmniRoute 3.8.50 on MiniPC. `agy models` on both hosts advertised
literal CLI model identifiers `gemini-3.8-flash-low`,
`gemini-3.8-flash-medium` and `gemini-3.8-flash-high`, among others.
`gemini-2.5` variants were **not shown by the tested native `agy models`**;
they may be separately available through verified OmniRoute `agy/` routes,
but may not be invented as CLI choices. OmniRoute's distinct existing official
model `antigravity/gemini-3.8-flash-tiered` remains the DP-201 pinned route.

A real MiniPC native CLI loopback/session canary used
`agy --model gemini-3.8-flash-low --mode plan --sandbox --print` on one
synthetic sentence. It returned `SUCCESS`, the exact requested marker and
usage of 25,574 total tokens (25,149 input, 425 output). The CLI JSON did
**not** expose an independently attested served-model identifier or per-model
remaining quota. This proves the exact-option CLI invocation and successful
synthetic output, not correctness, quotas for bulk processing or provider
model identity independently signed by Google.

`ANTIGRAVITY_CLI_QUOTA` on the optional private Passage selector calls the
native `agy` binary **directly**, not OmniRoute `/v1/chat/completions` with
an auto-picked fallback. The catalog must contain a currently advertised
`gemini-*-(flash|pro)-(low|medium|high)` native CLI model and an operator
verified, independently SHA-pinned `/usage` receipt no older than 15 minutes:
`quota_source=ANTIGRAVITY_CLI_USAGE_PANEL`, UTC `quota_observed_at`, positive
`quota_remaining_requests` and `quota_remaining_tokens`, `overage_policy=NEVER`
verified in Antigravity settings, and a SHA-256 pseudonym for the **one** active
CLI account in `single_account_scope`. The exact model and active account must
agree with the verified snapshot. Source rights and the explicit
`--external-model-data-approved` flag are mandatory. Use `--max-cost-usd 0`
for quota-only work; any paid lane needs separate approval and a positive cap.

The adapter runs `agy` from an empty temporary workdir with explicit model,
plan mode, sandbox, disabled slash-command expansion, finite timeout and
bounded response size. It delivers the private prompt through the official
`--input-format stream-json` stdin protocol, so raw source text never appears
in process command-line arguments. Its CLI log file stays inside the temporary
workdir, which is deleted after each request; CLI-owned conversation retention
still needs the independent privacy approval recorded in the catalog.
Only the CLI's necessary HOME/PATH/XDG environment is
passed; no OmniRoute/Groq/API keys enter the process. It validates live
`agy models`, tracks request/token usage, refuses non-success/missing usage,
model mismatch, stale quota or exhaustion, and never rotates accounts or
falls back to another model. Failed calls exhaust local admission until a
fresh quota snapshot is verified. Private candidate schema/offset/review
gates stay unchanged. The receipt records requested CLI model, anonymous
account scope, quota plan/usage and explicitly marks the lack of signed
served-model reporting; it never claims the CLI response independently
certifies upstream model identity. No production profile, service or source
was enabled by these changes.

### Lane 3B — Cohere provider-diverse second opinion

OmniRoute ha già una route owner-proven:

cohere/cohere-transcribe-03-2026

Caratteristiche utili:

- italiano supportato;
- provider/model family diversa da Whisper/Groq;
- endpoint audio transcription;
- utile come seconda opinione su finestre sensibili;
- output plain transcript, quindi non va usato come unico timestamp authority.

La diversity del secondo ASR è preferibile al semplice invio dello stesso
audio allo stesso modello due volte.

### Lane 4 — Qwen3-ASR da benchmarkare

Qwen3-ASR è particolarmente interessante:

- modelli open-weight 0.6B e 1.7B;
- italiano supportato;
- streaming e offline;
- long audio;
- forced aligner separato;
- timestamp e alignment.

Non scaricare ancora automaticamente i pesi sul MiniPC.

Prima va fatto un benchmark controllato:

- WER su italiano;
- numeri, date e nomi propri;
- RAM;
- real-time factor CPU;
- dimensione cache;
- accuratezza su parlato televisivo e podcast.

### Parakeet

I modelli Parakeet verificati sono principalmente English ASR.

Non sono candidati primary per un progetto Italy-first.

## Sensitive-span trigger

Una seconda ASR diventa obbligatoria quando il claim contiene:

- denaro;
- percentuali;
- statistiche;
- date;
- quantità;
- nomi propri;
- nomi di organizzazioni;
- articoli di legge;
- citazioni dirette;
- negazioni;
- formule come mai, sempre, nessuno, tutti;
- differenze aritmetiche;
- parole su cui due transcript non concordano.

## Canonical transcript

Non va prodotto chiedendo genericamente a un LLM di correggere la trascrizione.

Questo rischia di trasformare una correzione in una riscrittura.

Il reconciler deve invece ricevere:

- raw candidate A;
- raw candidate B;
- timestamp o audio window;
- source title e description;
- gazetteer dei nomi noti;
- eventuali caption ufficiali.

Può:

- scegliere una variante attestata;
- correggere punteggiatura;
- normalizzare numeri;
- espandere nomi se l'evidence è sufficiente.

Non può:

- inventare parole non osservate;
- parafrasare;
- cambiare significato;
- correggere politicamente il contenuto.

Se non c'è consenso:

TRANSCRIPT_UNCERTAIN.

Un claim materialmente dipendente da quel token resta bloccato.

## Gazetteer dinamico

Per ogni contenuto costruire automaticamente un piccolo dizionario:

- persone citate;
- ospiti;
- partiti;
- istituzioni;
- luoghi;
- leggi;
- topic;
- termini tecnici.

Le fonti del gazetteer possono essere:

- titolo e description;
- capitoli YouTube;
- pagina evento;
- person registry;
- topic registry;
- named entities già note.

Questo migliora il post-processing senza falsificare l'audio.

## Speaker attribution

ASR e speaker attribution sono problemi separati.

La pipeline deve conservare:

- speaker diarization;
- speaker identity confidence;
- inserted clip o voice-over;
- interviewer vs guest.

Un transcript corretto attribuito alla persona sbagliata resta un finding sbagliato.

## Quota-aware routing via OmniRoute

OmniRoute deve vedere STT come capability, non come modello fisso.

Contract concettuale:

transcribe(audio, language, risk_class, timestamps_required)

Il router decide fra:

- Groq Turbo;
- Groq Large v3;
- local faster-whisper;
- Qwen3-ASR in futuro;
- altri provider canaried.

La policy considera:

- costo;
- quota residua;
- latenza;
- lingua;
- timestamp support;
- risk class;
- provider health.

Non hardcodare Groq nella business logic.

La policy eseguibile iniziale è versionata in:

config/transcription-policy.v1.json

Il file registra:

- provider roles;
- sensitive-span triggers;
- retention;
- reconciliation;
- quota policy;
- benchmark MiniPC.

## Regola finale

Per contenuti normali:

caption -> Groq Turbo se necessario.

Per claim sensibili:

bounded second ASR con modello o provider indipendente.

Per disagreement:

third opinion o TRANSCRIPT_UNCERTAIN.

Questo è più robusto di pagare sempre il modello più grande.
