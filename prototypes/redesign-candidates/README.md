# DP-441 — anteprime per scegliere il redesign

**Direzione selezionata per la preview il 2/11/2026: A, Atlante delle parole.** Decisione e limiti: docs/ux/dp441-design-selection-2026-11-02.md. Le note sullo stato in attesa si riferiscono alle catture storiche del 25 ottobre.

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

## Prove browser riproducibili (25 ottobre 2026)

La sorgente delle due alternative è `build.py`, che genera gli HTML
`atlante.html` e `biblioteca.html` dalla stessa fixture. Per ripetere il
confronto con il **Chrome dedicato `automation-browser-visible` sul Mac Studio**
già avviato (porta CDP locale `17630`), dal worktree del repository:

```sh
python3 /Users/domenico/.local/share/controlcenter/resource-guard/workload_launcher.py --max-wait 300 build -- node prototypes/redesign-candidates/capture.mjs
```

`capture.mjs` apre e chiude soltanto una sua scheda di Chrome. Rende sei viste
per ciascuna alternativa ai CSS viewport 1440, 390, 320 e 195: 48 osservazioni
in `render-evidence.json`, fra cui stato visibile, titolo, scroll orizzontale,
primo viewport, etichetta demo, destinazioni locali e SHA-256 dei PNG.
195 CSS px verifica solo il reflow (equivalente geometrico del 200% su 390 px),
non la visibilità del titolo nel primo viewport né l'effettivo zoom UI.
I 16 screenshot sono in `screenshots/` (Home 1440/390, Esplora 320,
Statement 1440/390, Persona×Tema 390, Contenuto 390 e Traccia 390
per ciascuna alternativa). Sono screenshot **veri del browser**, di
fixture inventate, **non del sito pubblico**.

Lo stato autentico del consumer pubblico va verificato separatamente e non
deve essere dedotto dalle fixture. Le prove automatiche di viewport e di
navigazione non sostituiscono VoiceOver, una sessione d'uso con persone o la
decisione estetica dell'owner. La scelta resta **PENDING_OWNER_SELECTION**.
