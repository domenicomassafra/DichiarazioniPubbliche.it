# Product Vision

## Missione

Rendere interrogabile, verificabile e temporalmente coerente il record pubblico di persone esposte al dibattito pubblico.

Il progetto non deve essere un sito di opinioni sulle persone, ma un sistema che collega dichiarazioni originali, contesto, fonti, evidenze, verifiche, cambi di posizione, contraddizioni, azioni documentate, correzioni, repliche e revisioni.

## Geografia

Priorità: Italia. In secondo luogo, un numero limitato di figure internazionali di primo piano, come capi di Stato e di governo. La struttura dati deve comunque essere internazionalizzabile.

## Soggetti

Inclusi: politici, giornalisti, presentatori e conduttori TV, opinionisti, influencer/creator, avvocati e professionisti con forte esposizione mediatica e altre figure pubbliche.

Esclusi: cittadini privati privi di rilevanza pubblica; informazioni sulla vita privata prive di connessione con la funzione o il ruolo pubblico.

## Tre viste

### Persona

Timeline con filtri per data, tema, tipo di claim, status di verifica, fonte, contenuto di origine, cambi di posizione, contraddizioni e correzioni.

### Tema

Esempi: nucleare, immigrazione, lavoro, sanità, giustizia, un caso giudiziario mediatico, una legge o un provvedimento.

La vista aggrega claim ed evidenze senza produrre classifiche politiche complessive.

### Contenuto

Per video, podcast, trasmissioni e interviste già processati: timeline, speaker, transcript segmentato, claim estratti, finding associati, link e timestamp alla fonte originale.

## Richieste utenti

La v1 non espone il nostro LLM direttamente. L'utente può inviare URL, nome persona, argomento o contenuto; la richiesta viene deduplicata, classificata, accodata e processata internamente.

## Filosofia

Il progetto è simultaneamente archivio storico, fact-checker, contradiction engine, evidence graph e sistema di monitoring continuo.

## Non-obiettivi iniziali

- fact-check live pubblico a consumo libero;
- scoring sintetico della credibilità di una persona;
- classifiche tipo “chi mente di più”;
- giudizi sulle motivazioni psicologiche;
- raccolta indiscriminata di informazioni private.

