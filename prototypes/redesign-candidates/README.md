# DP-441 — anteprime per scegliere il redesign

Apri **`compare.html`** per vedere le due proposte affiancate con gli stessi
stati. Apri `atlante.html` o `biblioteca.html` per valutare ciascuna a larghezza
intera o in modalità mobile. Nella barra alta puoi passare
fra gli stessi sei stati di entrambe le alternative. Puoi anche confrontare gli
stessi stati modificando `?view=home`, `explore`, `statement`, `intersection`,
`source`, `trace` dopo il nome del file. Le pagine non vengono caricate nel sito
pubblico e sono marcate `noindex,nofollow`.

* **Atlante delle parole**: punto d'ingresso nella dichiarazione, ricerca globale,
  percorso parola → fonte → verifica → cronologia. Composizione aperta, titolo e
  citazione come riferimento visivo principale.
* **Biblioteca delle fonti**: punto d'ingresso nel catalogo e nel documento; scheda
  di provenienza sempre associata al testo. Composizione a scaffale/lettore con
  pannello contestuale, non una variante cromatica dell'Atlante.

Tutte le schermate popolati usano le **stesse fixture inventate** nel generatore
`build.py`. Home ed Esplora dichiarano esplicitamente il corpus pubblico vuoto.
Nessuna fonte reale, identità reale, finding, approvazione o pubblicazione è
simulata come se fosse avvenuta. Non trasferire queste pagine sotto `web/src/pages`.

Per rigenerare le due pagine: `python3 prototypes/redesign-candidates/build.py`.
Il confronto, gli scenari e i criteri della scelta sono in
`docs/ux/redesign-candidates-2026-10-17.md`.
