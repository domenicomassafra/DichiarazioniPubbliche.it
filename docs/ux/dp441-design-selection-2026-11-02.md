# DP-441 — scelta della direzione per la preview

Data: 2 novembre 2026 · Issue: [#84](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/84) · Esito: **A — Atlante delle parole**.

## Autorità e perimetro

Con le istruzioni dell'owner del 2 novembre 2026, la scelta tecnica della direzione è delegata all'agente per sbloccare il redesign. Questa è una **selezione motivata dell'esecutore**, non una firma estetica personale dell'owner. È valida per design, sviluppo e anteprima/staging; una nuova pubblicazione pubblica in produzione richiede l'autorizzazione prevista dalle decisioni correnti. DP-442 / [#349](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/349) resta proprietaria della migrazione Astro delle nove famiglie e delle prove di consumer.

## Decisione comparativa

L'**Atlante delle parole** parte dalla dichiarazione originale e mette nel primo viewport la promessa del prodotto, lo stato realmente vuoto del corpus pubblico e l'azione «Apri Esplora». Sulla scheda la sequenza è: parole originali, attribuzione/data, fonte, sintesi distinta, eventuale verifica e correzione. La **Biblioteca delle fonti** anticipa il catalogo/documento e rimanda la promessa e la frase più in basso sul telefono; dà più peso alla provenienza, ma obbliga il lettore occasionale a orientarsi nel catalogo prima di sapere cosa può leggere. Le due alternative usano la stessa fixture fittizia e non possono essere interpretate come pubblicazione.

Il punto debole della scelta A è il rischio di rendere la fonte secondaria: nella migrazione, il collegamento alla fonte primaria e il localizzatore devono restare raggiungibili subito dopo la citazione, anche a 320 px, con testo e semantica corretti. La Biblioteca resta come riferimento di una gerarchia alternativa; non è il design da costruire. Si conservano i token e le regole di provenienza, accessibilità e privacy già versionati finché #349 non dimostra la necessità di cambiarli; nessuna scorecard personale, immagine sintetica o verdetto inventato.

## Evidenza e metriche

- Compiti uguali per A e B: Home ed Esplora senza record autorizzati; Statement, Persona × Tema, Contenuto e Traccia con **fixture dichiaratamente inventata**. Il confronto è in [`compare.html`](../../prototypes/redesign-candidates/compare.html), con le viste indipendenti [`atlante.html`](../../prototypes/redesign-candidates/atlante.html) e [`biblioteca.html`](../../prototypes/redesign-candidates/biblioteca.html).
- Archivio del 25 ottobre recuperato con 48 osservazioni browser (6 stati × 2 alternative × 4 viewport: 1440×900, 390×844, 320×700, 195×422), 16 PNG, zero overflow orizzontale registrato. Ricevute, hash HTML e screenshot sono in [`render-evidence.json`](../../prototypes/redesign-candidates/render-evidence.json). Il viewport 195 è una **simulazione geometrica** del reflow al 200% da 390 CSS px: non prova zoom UI o screen reader.
- Criteri di accettazione per la migrazione: nel primo viewport a 390/320 devono comparire titolo significativo, stato corpus e azione; quote e attribuzione devono precedere la sintesi, la fonte deve essere accessibile con percorso breve, non devono esserci overflow a 320/390/1440 o regressioni a 200%; navigazione tastiera/AX, focus, contrasto, Empty/Populated/HOLD/Unavailable e fonte/diritti dovranno essere verificati su Astro/consumer reale in #349. Non si attribuiscono tempi di comprensione a utenti non osservati.
- Limiti: screenshot storici di prototipi offline, non del sito pubblico né di record reali. Nessuna verifica manuale con utenti o VoiceOver, nessuna distribuzione pubblica delle fixture come dati; il consumer corrente presenta `contract_status=DRAFT`, `dossier_count=0`. La scelta di design non autorizza dati, pubblicazione o cambio di policy.

## Conseguenze e passaggio di consegne

La grammatica da migrare in #349 è editoriale e orientata alle parole originali, con provenienza visibile e cronologia leggibile, senza scaffale/catalogo obbligatorio prima del contenuto. La scelta modifica il **percorso di lettura e la priorità nel primo viewport** rispetto al v4 già esistente; non si limita a palette o micro-CSS. La migrazione deve riusare le componenti e le primitive esistenti, mappare ogni route e stato, misurare 320/390/1440, 200% e accessibilità e preservare i gate delle proiezioni. Questo documento chiude la decisione comparativa DP-441; l'implementazione di produzione è tracciata separatamente in #349.
