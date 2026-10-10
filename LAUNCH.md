# Pubblicazione essenziale — domenica 11 ottobre 2026

**Decisione operativa:** prima rendere leggibile, funzionante e onesto il sito pubblico;
poi costruire l'archivio di dichiarazioni con fonti e revisione approvate.
Non trasformare il secondo obiettivo in una dipendenza del primo.

## Un prodotto, due stati distinti

**Sito pubblico essenziale (ora):** sei pagine canoniche statiche (`/`,
`/esplora/`, `/metodo/`, `/correzioni/`, `/dati/`, `/progetto/`), API pubblica
di sola lettura e un indice coerente con l'unica proiezione approvata. È
possibile che l'indice contenga **zero dichiarazioni**: l'interfaccia deve
dirlo chiaramente. Il servizio HTTPS esiste già: la pubblicazione essenziale
è un aggiornamento verificato di questo sito, **non** una stable-v1 release.

**Archivio editoriale di dichiarazioni (successivamente):** prima di rendere
pubblica **una** dichiarazione reale sono necessari attribuzione verificata,
fonte citabile, diritti, privacy, eventuali correzioni e approvazione editoriale.
La pubblicazione essenziale non autorizza deduzioni, giudizi sulle persone,
raccolta automatica o copia di contenuti di terzi. Non riempire il sito con
fixture/demo, fonti dai diritti ignoti o affermazioni inventate.

## Scope vincolante della pubblicazione essenziale

1. Homepage con una promessa reale e senza metriche, pubblicazioni o utenti
   inventati; messaggio esplicito se non esistono record approvati.
2. Esplora e ricerca che leggono **solo** l'indice della medesima proiezione
   pubblica. In caso di indice vuoto il risultato è uno stato vuoto chiaro,
   non un errore apparente, un'analisi live o una ricerca su contenuti privati.
3. Metodo, correzioni, dati/API, progetto: testo leggibile, limiti e stato
   effettivo del progetto; non inventare identità, contatti, politiche legali
   approvate o diritti sui materiali di terzi.
4. Layout responsivo, navigazione da tastiera, contrasto, zoom 200%,
   noindex per Studio/demo, URL canonici e zero chiamate LLM dal browser.
5. Build esclusivamente con
   `DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH` impostato al file
   **approvato**; la variabile `DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION`
   deve essere assente. Gli artefatti demo locali non vanno mai copiati sul sito.
6. Prima del cambio: backup di `web/dist`, verifica read-only dell'API e della
   proiezione, build in directory isolata. Dopo: checksum e test delle sei
   route HTTPS/API, validazione dell'indice, `robots.txt`/sitemap e rollback
   pronto. Nessuna migrazione SQL, chiamata a provider o modifica di credenziali.

## Cosa NON deve bloccare queste sei pagine

Il pilota **Garlasco** è una verifica sperimentale privata e non è la
linea editoriale né il tema del sito. Il requisito di 100 elementi, il
benchmark Garlasco, le integrazioni OmniRoute/Groq, l'intera Studio privata,
i clienti SDK/MCP, il sistema di triage, le funzioni di intake/account, la
pubblicazione di dossier e la stable-v1 release **non sono dipendenze** di
questo sito informativo con zero record approvati.

Questi elementi possono restare come codice e ticket di ricerca o roadmap,
ma non generano lavoro nello sprint di pubblicazione essenziale. **Non**
convertire ticket aperti in DONE per ridurre artificialmente un contatore.
`PLAN.md` resta il registro storico della release completa, non la checklist
di domani. Questo documento non cambia gli stati dei 125 ticket e non
disattiva i blocchi di sicurezza della release `1.0.0`.

### Razionalizzazione dei 35 ticket ancora aperti (snapshot 2026-10-10)

**30 fuori dallo scope delle sei pagine informative, non DONE:**

- 10 di ricerca, sorgenti e provider: DP-201/202/203/204/208/214/215/229/233/234;
- 1 su giudizi/attribuzioni: DP-301;
- 8 per pagine con record reali e componenti connessi: DP-405/406/407/408/409/412/422/429;
- 6 per Studio privata e raccolte di ricerca: DP-416/417/418/419/420/421;
- 2 condizionali, lasciati disabilitati: DP-507/508;
- 3 per la release piena, distribuzione di dataset e governance estesa:
  DP-703/704/705. I ticket DP-604 e DP-606 sono già `DONE` e non vanno
  ricontati tra i residui.

**5 aree con condizioni applicabili alla preview, senza spacciarle per ticket
completati:** DP-304 (privacy e logging del sito informativo); DP-307 e
DP-702 (disclosure/responsabilità e valutazione legale per questa pagina, non
approvazione della pubblicazione di claim); DP-410 (test manuale essenziale
di accessibilità); DP-701 (dominio, titolarità e canale di contatto realmente
approvato).

Il progetto non deve attendere la risoluzione dei 30 ticket differiti per
mostrare pagine statiche veritiere. **Non deve neppure fingere che le cinque
aree residue siano approvate**: titolarità, contatto, informativa privacy e
revisione giuridica devono essere verificati da chi ha l'autorità di farlo.

## Il confine che resta obbligatorio

L'attuale proiezione pubblica approvata ha zero dossier, zero Topic e zero
Content: non c'è materiale per dichiarare l'**archivio editoriale** lanciato.
Le decisioni legali, di titolarità, contatto/privacy e approvazione v1 ancora
aperte rimangono pubblicamente rappresentate come limiti o blocchi: nessun
workflow tecnico ne presume il superamento. La pubblicazione di contenuto
reale o una release stabile richiederà una **decisione separata**, con gli
attuali controlli fail-closed.

**Handoff del checkpoint:** vedere `MEGA-HANDOFF-2026-10-10.md` per lo stato
verificato di tutti i 125 ticket, i rischi, il percorso fonti → candidati →
verifica → frontend, i test e le domande da sottoporre al prossimo agente.
Il presente documento descrive **soltanto la preview informativa** e non
riduce l'ambizione del prodotto editoriale completo.
