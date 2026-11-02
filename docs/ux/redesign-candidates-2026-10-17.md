# DP-441 — confronto redesign, 17 ottobre 2026

**Aggiornamento 2/11/2026:** selezionata la direzione A, Atlante delle parole, per la preview. [Decisione motivata](dp441-design-selection-2026-11-02.md). Le note successive sul rinvio documentano lo stato storico al 17/25 ottobre.

**Decisione dell'owner: in attesa.** Le alternative sono anteprime offline, non
una nuova UI pubblicata. Baseline: il codice Astro sotto `web/src/pages/` e il
prototipo già presente in `prototypes/final-hybrid/`. Sono stati riutilizzati
l'architettura a nove famiglie `docs/35-public-product-architecture-v3.md`, il
lessico, la distinzione originale/sintesi/verifica e i confini delle proiezioni.

## Compiti e dati identici

| Domanda del lettore | Dato pubblico ammesso | Azione e stato nell'anteprima |
| --- | --- | --- |
| Che cosa offre il sito oggi? | Indice pubblico autorizzato | Home: **zero elementi**, ingresso chiaro a Esplora |
| Dove trovo una frase? | Dossier approvati con Persona, Tema, data, fonte | Esplora: **zero**, nessun risultato inventato |
| Quali parole sono state dette? | Parole letterali + attribuzione + data + fonte | Scheda Statement: **fixture inventata** etichettata |
| Che cosa si sa della frase? | Finding opzionale distinto dalla quote | Nessuna verifica eseguita; sintesi dimostrativa separata |
| Che cosa ha detto P sul tema T? | Intersezione di record approvati, con date | Persona × Tema: sola fixture, nessuna generalizzazione reale |
| Dov'è il contesto originale? | Fonte approvata, versione, localizzatore | Contenuto: fonte dichiarata inesistente, nessun URL fasullo |
| Che cosa è cambiato o corretto? | Revisioni pubbliche autorizzate e datate | Traccia: due versioni **inventate**; nessuna valutazione d'intento |

Non si aggiungono login, editor, chatbot, classifiche, finding obbligatori,
immagini di persone o contenuti la cui ri-pubblicazione non sia autorizzata.
Entrambe le opzioni adottano esattamente `SAMPLE` dal generatore e condividono
la stessa dicitura di stato e il medesimo numero di schermate. La fixture serve
solo per verificare densità e gerarchia nel confronto; non è la proiezione pubblica.

## Differenze strutturali

| | A — Atlante delle parole | B — Biblioteca delle fonti |
| --- | --- | --- |
| Primo gesto | Identificare la dichiarazione e andare alla ricerca | Entrare dall'indice e scegliere il tipo di documento |
| Gerarchia | Parole → attribuzione → origine → sintesi/correzione | Provenienza/catalogo → documento → parole → cronologia |
| Desktop | Apertura editoriale a colonne asimmetriche, poi citazione ampia | Scaffale laterale persistente e pannello di lettura |
| Mobile | Pila lineare: claim e link origine, poi contesto | Scheda catalogo compatta prima del lettore |
| Vantaggio | Trovare subito l'oggetto pubblico condivisibile | Verificare subito origine e collocazione nel documento |
| Rischio da misurare | Fonte meno evidente nel primo colpo d'occhio | Fonte troppo dominante rispetto alla frase cercata |
| Manutenzione | Tipografia narrativa e componenti source path | Componenti catalogo/scheda/lettore; più densità |

## Revisione comparativa e scelta

Per ogni schermata usa gli URL locali equivalenti `atlante.html?view=<stato>` e
`biblioteca.html?view=<stato>`. Misura a **1440, 390, 320 CSS px**, 200% di zoom,
tastiera, label e focus; rendi nota la comprensione dei primi 5 secondi, i click
verso la fonte e l'eventuale scroll orizzontale. La verifica *automatica* non
costituisce la scelta estetica dell'owner. Se l'opzione risultasse simile al v4,
la scelta deve precisare il miglioramento misurato e le pagine coinvolte.

L'implementazione DP-442 richiede l'opzione **A**, **B** o una revisione definita
dall'owner, con data e motivazione. Solo allora fissare token, componenti,
migrazione CSS e regressioni di tutte le nove famiglie Astro. Lo stato attuale è
`PENDING_OWNER_SELECTION`; non viene inventata una firma o una direzione.

## Evidence di rendering browser — 25 ottobre 2026

Sorgente: `prototypes/redesign-candidates/build.py`, fixture inventata identica per A/B.
Consumer di prova: Chrome di automazione dedicato sul Mac Studio (`automation-browser-visible`, CDP locale 17630), in una scheda temporanea poi chiusa.
Il readback MiniPC separato ha risposto `dichiarazioni-pubbliche-web.service=active`,
`/api/v1/health status=ok`, `contract_status=DRAFT`, `dossier_count=0`;
quindi le schede illustrate **non sono dati pubblicati**.

| Vista (primo viewport) | A · Atlante | B · Biblioteca |
| --- | --- | --- |
| Home, 1440 CSS px | [Screenshot A](../../prototypes/redesign-candidates/screenshots/atlante-home-1440.png) | [Screenshot B](../../prototypes/redesign-candidates/screenshots/biblioteca-home-1440.png) |
| Home, 390 CSS px | [Screenshot A](../../prototypes/redesign-candidates/screenshots/atlante-home-390.png) | [Screenshot B](../../prototypes/redesign-candidates/screenshots/biblioteca-home-390.png) |
| Esplora vuoto, 320 CSS px | [Screenshot A](../../prototypes/redesign-candidates/screenshots/atlante-explore-320.png) | [Screenshot B](../../prototypes/redesign-candidates/screenshots/biblioteca-explore-320.png) |
| Statement fittizio, 1440 CSS px | [Screenshot A](../../prototypes/redesign-candidates/screenshots/atlante-statement-1440.png) | [Screenshot B](../../prototypes/redesign-candidates/screenshots/biblioteca-statement-1440.png) |
| Statement fittizio, 390 CSS px | [Screenshot A](../../prototypes/redesign-candidates/screenshots/atlante-statement-390.png) | [Screenshot B](../../prototypes/redesign-candidates/screenshots/biblioteca-statement-390.png) |
| Persona × Tema, 390 CSS px | [Screenshot A](../../prototypes/redesign-candidates/screenshots/atlante-intersection-390.png) | [Screenshot B](../../prototypes/redesign-candidates/screenshots/biblioteca-intersection-390.png) |
| Contenuto, 390 CSS px | [Screenshot A](../../prototypes/redesign-candidates/screenshots/atlante-source-390.png) | [Screenshot B](../../prototypes/redesign-candidates/screenshots/biblioteca-source-390.png) |
| Traccia e correzioni, 390 CSS px | [Screenshot A](../../prototypes/redesign-candidates/screenshots/atlante-trace-390.png) | [Screenshot B](../../prototypes/redesign-candidates/screenshots/biblioteca-trace-390.png) |

Osservazione visiva personale sui PNG di Home desktop e Statement mobile:
A imposta una gerarchia editoriale frase → fonte, B imposta catalogo/fonte → frase;
su 390 CSS px il contenuto originale è leggibile con attribuzione e data
in entrambe, ma B richiede più scroll per arrivare alle parole perché precede
la scheda di catalogazione. Tradeoff da sottoporre all'owner, non risultato
di un test con lettori reali.

La cattura automatica certifica le dimensioni e i DOM osservati in
[render-evidence.json](../../prototypes/redesign-candidates/render-evidence.json),
con SHA-256 dell'HTML sorgente e di ciascuno screenshot.
Restano valutazioni umane: comprensione effettiva dopo cinque secondi,
VoiceOver/tastiera completi, preferenza estetica e scelta finale.
**Esito della scelta: PENDING_OWNER_SELECTION.**
