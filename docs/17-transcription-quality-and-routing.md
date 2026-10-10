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
