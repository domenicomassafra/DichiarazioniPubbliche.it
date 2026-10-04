# Content Audit v1 — Raffaele Giuliani / bollo auto

Data audit: 2026-09-21.

Questo è il primo test end-to-end del progetto su un intero contenuto politico
lungo, invece che su singole fixture isolate.

## Contenuto

- creator: Raffaele Giuliani (@raffagiulians);
- Instagram: DdZseq2tjn4;
- TikTok: 7686596204074896672;
- durata verificata: 444,84 secondi;
- tema principale: bollo auto, fiscalità e divergenze nel centrodestra.

Il progetto non produce un voto complessivo sul creator e non usa i conteggi
dei finding come punteggio di affidabilità personale.

## Acquisizione realmente provata

La pipeline finale usata è stata:

MiniPC
-> TikTok public oEmbed/embed identity
-> public embed media URL
-> MP4 locale immutabile
-> LifeOS / watchthis
-> audio extraction
-> OmniRoute STT
-> Groq whisper-large-v3-turbo.

La cattura canonica non richiede login o cookie e nessuna sessione browser del Mac fa parte del percorso finale valido.

La cattura pubblica canonica misura circa 40,2 MB e dura 444,8 secondi. Un secondo remux MiniPC dello stesso contenuto è stato usato per segment coverage e secondary-ASR validation; i due hash restano distinti nella provenance.

watchthis ha completato capture e transcript, poi il successivo stadio
semantico è andato in dead-letter con media-model-permanent-http-400.

Questo non invalida il transcript: il receipt separa gli stadi e conserva gli
hash degli artefatti.

## Raw transcript policy

Il transcript integrale e il receipt che lo contiene restano evidence locale e
non vengono committati.

Nel repository entrano hash, modello/request receipt, timestamp, normalized
claim, evidence IDs, assessment e segment coverage senza testo integrale.

Questo permette regressioni e audit senza trasformare il repository in una
copia del contenuto originario.

## Coverage

La fixture canonica contiene:

- 84 segmenti su 84 classificati;
- 36 claim atomici;
- 23 evidence source;
- speaker attribution esplicita.

Da 6:54 a 7:14 il video inserisce un vecchio clip di Giorgia Meloni.

Quei segmenti vengono attribuiti a Giorgia Meloni (inserted clip) e non a
Raffaele Giuliani.

Questo è un test importante per la futura diarization/source attribution.

## Finding metodologici principali

### 1. “Abolito” vs effetto giuridico corrente

La comunicazione politica del governo usa il termine abolizione.

Il DL 162/2026 rende però operativa l'esenzione per il 2027. Il MIT dichiara
contestualmente che l'obiettivo del governo è renderla strutturale con la
successiva legge di bilancio.

Il finding corretto deve quindi rappresentare separatamente l'effetto giuridico
oggi finanziato e l'obiettivo politico dichiarato.

### 2. La seconda ASR ha evitato un falso finding

La prima trascrizione lunga aveva perso due decimali: 7 invece di 7,5 e 2
invece di 2,3, pur mantenendo 5,2 come risultato.

Prima di creare un finding aritmetico è stato ritrascritto soltanto il passaggio
1:38–2:05.

La seconda ASR ha confermato che il parlato originale era circa 7,5 miliardi,
circa 2,3 miliardi e differenza 5,2 miliardi.

L'aritmetica è quindi corretta.

Regola candidata:

numeric-sensitive claim + incoerenza interna ASR -> mandatory bounded
re-transcription before verification.

### 3. Numero corretto, baseline sbagliata

ACI indica circa 7,5 miliardi di gettito 2024 della tassa automobilistica.

Il decreto quantifica invece in 2.293,5 milioni la riduzione di gettito
derivante dalla specifica esenzione 2027 e prevede un trasferimento dello
stesso importo a compensazione.

Sottrarre 2,3 dal gettito totale di 7,5 produce matematicamente 5,2, ma quel
5,2 non rappresenta il buco lasciato dalla misura.

Questa è una classe di errore distinta:

VALID_ARITHMETIC + INVALID_BASELINE/SEMANTIC_INFERENCE.

### 4. Prezzo estremo vs prezzo rappresentativo

Il video dice che il diesel tocca 3 euro.

Esistevano effettivamente singoli prezzi comunicati superiori a 3 euro,
soprattutto servito/outlier, ma il 17 settembre la media nazionale
autostradale self era molto inferiore.

Serve distinguere EXISTS_AT_LEAST_ONE, AVERAGE, MEDIAN/TYPICAL, MAXIMUM,
SPECIAL_PRODUCT e SELF/SERVED.

### 5. Citazione vera, oggetto attribuito male

Antonio Tajani ha realmente usato il riferimento all'“Unione Sovietica”.

La dichiarazione documentata riguardava però la tassazione degli extraprofitti,
non una generica patrimoniale sui multimilionari.

Assessment: MISATTRIBUTED.

### 6. Ungheria: proposal != enacted law

Alla data dell'audit la nuova wealth tax ungherese risultava ancora in fase di
preparazione legislativa.

La formulazione secondo cui l'Ungheria l'avesse già approvata viene quindi
classificata come CONTRADICTED.

Il data model deve distinguere almeno proposed, announced, draft, submitted,
approved, enacted ed effective.

### 7. The Movement: relazione documentata != appartenenza identica

Matteo Salvini aderì a The Movement.

Viktor Orbán accolse positivamente il progetto di Steve Bannon, ma le fonti
usate nel dossier non dimostrano un'adesione formale equivalente.

Assessment: PARTIALLY_SUPPORTED.

### 8. Dati fiscali corretti non dimostrano automaticamente la conclusione

Sono supportati l'articolo 53 della Costituzione, l'aliquota agevolata del
12,5% sui titoli di Stato, il 26% su molte altre attività finanziarie e
l'aliquota IRPEF nazionale massima del 43% nel 2026.

Non segue automaticamente da questi soli numeri che l'intero sistema fiscale
italiano sia o non sia progressivo.

La conclusione sistemica richiede una metrica separata e un dataset adeguato.

## Tipi che il sistema non deve forzare in TRUE/FALSE

Nel video compaiono anche appelli politici, giudizi morali, previsioni
elettorali, preferenze politiche, attribuzioni di intento e generalizzazioni
teoriche.

Una previsione elettorale viene registrata come PREDICTION_PENDING, non
verificata come se fosse un fatto presente.

Una attribuzione del tipo “lo fanno apposta per ingannare” richiede evidence
indipendente sull'intento e non viene inferita dal solo contrasto fra
comunicazione e testo normativo.

## Fixture

Canonical machine-readable dossier:

poc/content/raffagiulians-bollo-2026/content-audit.json

Validator:

poc/dichiarazioni_pubbliche/content_audit.py

Tests:

tests/test_content_audit.py

Il validator vieta inoltre campi come truth_score, accuracy_score,
person_score, creator_score e overall_verdict.

## Primo contract di ContentAudit

Il modello emergente è:

Content
-> transcript provenance
-> segment coverage
-> speaker
-> atomic claim
-> claim type
-> evidence set
-> assessment
-> optional ASR verification
-> publication policy.

Questa struttura è abbastanza generale da essere applicata in futuro a Reel,
TikTok, podcast, intervista TV, conferenza, video YouTube e speech politico.

## Residui del POC

Il prossimo livello non è aggiungere altri verdict manuali allo stesso video.

Serve automatizzare e benchmarkare:

1. claim extraction dal transcript;
2. segment classification;
3. speaker switch detection;
4. numeric-sensitive trigger;
5. retrieval primario;
6. evidence-family dedupe;
7. assessment proposal;
8. deterministic publication gate.

Il dossier corrente diventa la ground truth contro cui misurare tali moduli.
