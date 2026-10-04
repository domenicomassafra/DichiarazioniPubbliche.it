# Content audit — Raffaele Giuliani / bollo auto / settembre 2026

Questo folder è la proiezione research del primo ContentAudit end-to-end.

## Contenuto

- creator: Raffaele Giuliani;
- handle: raffagiulians;
- TikTok ID: 7686596204074896672;
- Instagram Reel: DdZseq2tjn4;
- durata: 444,84 secondi.

## Pipeline provata

Percorso finale:

MiniPC
-> TikTok public oEmbed/embed identity
-> public embed media URL
-> MP4 locale
-> LifeOS/watchthis
-> OmniRoute STT
-> Groq whisper-large-v3-turbo.

watchthis ha completato capture + transcript e ha poi fermato il job in
dead-letter sul successivo semantic media stage con HTTP 400.

Il transcript è quindi disponibile come evidence locale, ma non viene
committato integralmente nel repository.

## Ground truth v1

Il dossier canonico è:

poc/content/raffagiulians-bollo-2026/content-audit.json

Contiene:

- 84/84 segmenti classificati;
- 36 claim atomici;
- 23 evidence source;
- 2 speaker;
- nessun person/creator score.

## Secondary ASR

La prima ASR aveva perso i decimali 7,5 e 2,3 nel passaggio sui dati del
bollo. Una seconda trascrizione bounded del solo intervallo 1:38–2:05 ha
confermato:

- 7,5 miliardi;
- 2,3 miliardi;
- 5,2 miliardi.

Quindi l'aritmetica pronunciata è corretta.

Il finding rilevante è la baseline: il gettito totale di 7,5 miliardi non è la
perdita causata dalla specifica esenzione. Il DL 162/2026 quantifica la
riduzione di gettito della misura in 2.293,5 milioni e prevede un trasferimento
compensativo dello stesso importo.

## File

- source-metadata.json — provenance e hash;
- claims.json — projection dei claim normalizzati;
- docs/16-content-audit-raffagiulians-bollo.md — lettura metodologica completa.

I conteggi per assessment sono descrittivi del contenuto e non devono essere
trasformati in un voto di affidabilità della persona.
