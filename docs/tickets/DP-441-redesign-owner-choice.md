# DP-441 — Brief e alternative comparabili del redesign, decisione owner

Status: FUTURE
Milestone: M4 — public product/API
Depends on: DP-413, DP-423

## Problem

Il sito pubblico ha una grammatica v4 storicamente implementata, con tre composizioni corrette il 10 ottobre e check locali/MiniPC su approved-empty, ma l'owner valuta ancora l'insieme troppo generico. La scelta visiva v4 dei DONE DP-411/424 è fatto storico, non approvazione della **nuova** richiesta di redesign completo. L'audit indipendente segnala gerarchie simili tra pagine, vuoto sotto fold su telefono, copy disallineato e un problema di overflow a 320px. Senza decisione esplicita si rischia una ripetizione cosmetica del design corrente.

## Outcome

Consegnare brief e **almeno due alternative realmente divergenti** che risolvono gli stessi compiti/record/stati, con matrice comparativa e decisione formale del proprietario su una direzione o revisione ulteriore. Nessuna immagine o implementazione nel mandato corrente; i mockup/visuali sono un artefatto futuro dopo questa pianificazione.

## Traceability & constraints

R35/R36, Q18/Q20, audit 2026-10-10 UX, DP-411/412/413/423/424/425; proprietà editoriale della dichiarazione originale, source path, statuses, finding optional e correction links non si possono togliere per estetica. Non scegliere il vincitore dal vecchio Done DP-424. Designer/operator review non sostituisce privacy/rights approval.

## Scope

Una design brief con inventory reader jobs: 5-second current-public-state understanding; ricerca nel corpus zero e pieno; aprire un PublicStatement originale fino a source locator/context/summary/optional Finding; confrontare same-take cross-person e same-person nel tempo; esplorare Persona×Tema con sintesi; esaminare correction/reply. Ogni alternativa applica stessa terminologia/identici input public-safe e copre Home, Esplora, Statement, Person, Topic, Content, Trace, Method e utility, su mobile/desktop e la matrice empty/approved/populated/unavailable/held-safe. Territori candidati **da valutare**: Atlante delle parole, Biblioteca delle fonti, Linea del tempo leggibile, Indice radicale, senza dichiararne uno selezionato. Scrivere scelta/ADR finale a cura owner dopo confronti, con nuova token direction o preservazione ragionata, rischio di legacy CSS migration e condizioni di manutenzione. Assenza di immagini oppure uso di un asset corretto/licenziato; nessun volto ricostruito dall'AI.

## Non-goals

Scegliere concept per delega, generare immagini oggi, copiare componenti/framework grandi o mockup-candidate come dati reali, creare chatbot/feeds/bookmarks, cambiare la pubblicazione e le politiche.

## Dependencies and sequencing

Hard DP-413/423 per naming/brand context già approvato, DP-437/02/03 come contratti **input di target**, non prerequisiti alla stesura del brief; il prime decide se hard o soft per l'ultima fase. Soft DP-410/412/425, DP-426/427/428 e audit UX. Owner è l'unico soggetto che decide la direzione visiva; registrare decision pending come EXTERNAL/PENDING-OWNER senza bloccare i ticket source/review indipendenti.

## Acceptance criteria

- [ ] `AC-441.1`: brief specifica tutti gli reader jobs in termini di domanda→dati autorizzati→azione→stato; include same screenshots input e no simulated publication, senza ridurre prodotto a una sola funzione.
- [ ] `AC-441.2`: almeno due alternative differiscono concretamente per hierarchy/flow/composizione, non solo palette, font o radius, e usano le stesse identiche pubbliche quote/summary/source/optional Finding.
- [ ] `AC-441.3`: per entrambe esistono comparabili **specifiche future** di Home/Esplora con corpus zero, una Statement/populated **fixture etichettata**, Persona×Tema, Content/Trace, desktop 1440 e mobile 390/320, con test del primo viewport; niente screenshot spacciato per live.
- [ ] `AC-441.4`: ogni alternative ha outcome misurabili: comprensione entro primo viewport, tempo/click verso fonte, distinguibilità di stato, 320 reflow, 200% zoom, keyboard/AX, costi performance e source/rights evidence trace.
- [ ] `AC-441.5`: criteri, pro/contro e decisione finale dell'owner sono registrati in ADR/spec con data e outcome; senza decisione DP-442 resta solo pianificato, nessun token freeze.
- [ ] `AC-441.6`: se il proprietario seleziona un concetto già vicino al v4 attuale, la decisione dimostra quale funzione/esperienza cambia, quale difetto misurato corregge e perché la modifica è sufficiente.

## Validation / proof

Prima futura valutazione: screenshot/stati/viewport/source fingerprint allineati, verifica 5-second task con criteri concordati, matrice touch/keyboard/reader/contrast e 320/390/1440, quota di false promises (zero). Confronti fra almeno 2 alternative e schermate equivalenti, link verso la reale public schema version; design decision owner firmata per passaggio a DP-442. Nessun mockup nel task documentale corrente.

## Documentation, data, and migration impact

Nuovo ADR di direzione dopo decisione, append alla storia v4 senza riscrivere DP-411/424 DONE; aggiorna DESIGN/tokens *solo* a scelta avvenuta. Nessun DB/API in questo ticket; eventuali nuovi componenti si mappano alla grammatica DP-412/425 in DP-442.

## Completion receipt

Non implementato; pianificazione soltanto. Future brief, alternatives comparison, owner-decision signature, visual check receipts, current/proposed schema and final option.
