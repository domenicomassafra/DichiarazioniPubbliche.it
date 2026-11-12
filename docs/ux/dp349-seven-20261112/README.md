# DP-349 · le sette tavole del redesign, confrontate con il design · 12 novembre 2026

**Riferimento:** `docs/ux/dp349-figma-20261111/` — le sette cornici del Figma del proprietario
«Dichiarazioni Pubbliche — Redesign editoriale V1» (`emKLEdxy5o1R5e2tDOsafZ`), acquisite con l'embed
ufficiale e affiancate a catture Chrome reali. Il file Figma non è nel repository e non serve: il
confronto usa quelle coppie, che sono la traccia approvata del design.

**Cosa contiene questa cartella**

| Cartella | Cosa è |
| --- | --- |
| `before/` | le sette pagine catturate sul sito pubblico **prima** di questa consegna (Chrome reale, 1440 e 390 px) |
| `sites/` | le stesse sette pagine catturate sul sito pubblico **dopo** la release (Chrome reale, 1440 e 390 px) |
| `pairs/` | per ogni tavola: design a sinistra, sito pubblico a destra, 1440 px |

Nelle coppie la cornice Figma è resa alla sua scala; il confronto riguarda struttura, gerarchia
tipografica, colore e sezioni, non il pixel. Le immagini del Figma hanno il ritratto già oscurato
nella copia approvata.

## Le sette tavole

| # | Tavola | Il design mostra | Il sito pubblico mostra | Esito |
| --- | --- | --- | --- | --- |
| 1 | Home | hero a due colonne: ricerca a sinistra, scheda di una dichiarazione a destra; sotto, i quattro percorsi in una striscia compatta | hero a due colonne con lo stesso ritmo; a destra lo stato «Archivio in preparazione»; quattro percorsi con le didascalie del design su una riga | **Corrisponde** |
| 2 | Esplora | ricerca, barra dei tipi con i conteggi, filtri laterali, righe compatte | intestazione e percorso editoriale identici; al posto dei risultati, lo stato vuoto «Non ci sono ancora record pubblicati.» | **Corrisponde nello scheletro**; ricerca e barra dei tipi non compaiono perché non c'è nulla da filtrare |
| 3 | Metodo | titolo, una frase di premessa, le quattro fasi subito sotto | titolo, premessa di tre righe, le quattro fasi subito sotto, indice del documento e apparato | **Corrisponde nella struttura**; premessa più lunga, e due delle quattro fasi hanno un nome diverso |
| 4 | Dichiarazione | pagina record: citazione in grande, esito, prova in un colpo d'occhio | HTTP 404 | **Non esiste**: nessuna dichiarazione pubblicabile |
| 5 | Persona | pagina persona: ritratto, identità, cronologia con filtri | HTTP 404 | **Non esiste**: nessuna persona pubblica e nessun ritratto licenziato |
| 6 | Tema | pagina tema con registro cronologico delle dichiarazioni | HTTP 404 | **Non esiste**: nessun tema pubblico |
| 7 | Fonte | media ed estratto affiancati, dichiarazioni selezionabili sotto | HTTP 404 | **Non esiste**: nessun contenuto pubblico |

**Tre tavole su sette corrispondono.** Le altre quattro non sono un difetto di design: il sito serve
una proiezione pubblica con zero record, e le quattro tavole sono pagine di record. Il modello delle
quattro pagine è su `main` e corrisponde al design (lato destro delle coppie in
`docs/ux/dp349-figma-20261111/`, catturato sulla build dimostrativa privata, più la matrice
`after-matrix/`): manca il contenuto, non la pagina.

## Cosa è stato corretto

1. **Didascalie dei quattro percorsi (Home).** Il design dà a ogni percorso una didascalia di una
   riga; il sito portava tre righe di testo, che trasformavano la striscia compatta in schede alte e
   spingevano le frecce in fondo a ogni voce. Ora la sezione legge come il frame: una riga per voce a
   390, 768 e 1440 px.
2. **Pagina 404.** I cinque documenti di fiducia comparivano due volte: nella colonna di destra senza
   «Privacy», e in fondo al corpo come una riga unita
   («MetodoCorrezioniDati & APIProgettoPrivacy»). Ora compaiono una volta sola, nella colonna, tutti e
   cinque. Conta perché è la pagina che si vede aprendo le quattro tavole mancanti.

## Cosa resta e perché non si risolve qui

- **Quattro tavole senza record.** Servono dichiarazioni, persone, temi e contenuti pubblicabili: il
  gate di pubblicazione è descritto nelle issue #413 e #638, non in questo lavoro.
- **Ritratto della Persona.** Le 22 immagini approvate il 12/11 sono catture di confronto e ritagli
  di persone non identificate (inventario `docs/licensing/fixture-inventory.v1.json`, righe
  `OWNER-GRANT-DP349-20261112`; l'unico file immagine è `web/src/data/preview-portrait-349.jpg`, il
  ritaglio della build dimostrativa privata). Metterne una sulla pagina di una persona nominata
  sarebbe un'attribuzione falsa: lo slot resta vuoto finché non esiste un ritratto licenziato della
  persona reale, oppure finché il proprietario non decide di non mostrarne nessuno.
- **Premessa e nomi delle fasi del Metodo.** Il design apre con una frase ("Una procedura
trasparente: dalle parole originali fino ai dati che le sostengono o le contraddicono.") e chiama le
quattro fasi Dichiarazione, Fonte originale, Confronto, Giudizio; il sito ha un paragrafo che dice
cosa viene controllato prima di pubblicare e chiama le fasi Dichiarazione, Fonte, Verifica, Storia.
La gerarchia (quattro fasi subito dopo titolo e premessa) è quella del design. Cambiare le parole è
una scelta di testo, non di struttura: resta al proprietario, e basta dirlo per farla in una riga.

## Release e prova consumer

Release immutabile `a953c2bc2c5edaa1122555fb928fcdc852661271a59c9701744e74ff79c64246` sul MiniPC,
sorgente `ffd6de2a9d48da7d080f5696e1c83f3ca3ba8f14`, commutata con CAS dall'ID precedente
`4e124868392c3f2d639739b2cf56193444112910642ba82299abce0438839d07`; `dichiarazioni-pubbliche-web.service`
riavviato; `verify --origin http://127.0.0.1:18090` → `status PASS`, `http_origin_verified true`, 453
asset. `code_sha256` è identico alla release precedente (`05da9ac0…`): il runtime non cambia, cambia
solo il payload statico. `publication_authorized` resta `false` e `rights_epoch_ref`
`PRIVATE_DRAFT_NO_GO`: è una release di design, non una pubblicazione di contenuti.

## Riproduzione

Catture Chrome reali via `agent-browser`, viewport 1440×900 e 390×844, pagina intera, sulla URL
pubblica `https://dichiarazionipubbliche.it`. La build servita è quella di `main` dopo la release:
i sette file statici pubblici (`/`, `/esplora/`, `/metodo/`, `/correzioni/`, `/dati/`, `/progetto/` e
la pagina 404 servita dalle quattro URL mancanti) sono byte-identici alla build locale con la stessa
proiezione (`SHA-256` uguale). Nessun overflow orizzontale misurato a 1440, 768 e 390 px, nessun
errore di console sulle sette URL.
