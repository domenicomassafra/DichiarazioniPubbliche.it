# #170 — prova reale del renderer Playwright selettivo (23/10/2026)

Il criterio «Prova reale» di #170 chiede una pagina JS autorizzata resa con
fallback selettivo dopo il fetch statico, sandbox dimostrata, hash della
rendition e ricevuta privata. Qui c'è la ricevuta e il comando che la produce.

## Cosa è stato eseguito

Host: **Omarchy** (Arch Linux, kernel 7.0, `bubblewrap 0.13.1`, Chromium 155.0.8059.84,
Playwright Python 1.64.0 in un venv dedicato). Comando:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc \
  python3 tools/dp170_render_canary.py \
  --url https://demo.playwright.dev/todomvc/ \
  --rights docs/evidence/dp170/rights-canary.v1.json \
  --chromium /usr/bin/chromium \
  --out docs/evidence/dp170/canary-omarchy-2026-10-23.json
```

Ricevuta `canary-omarchy-2026-10-23.json`:

| Voce | Valore |
| --- | --- |
| Fetch statico | 865 byte, `d84724f9a3b5de3a6cf87b79d3efda1156663e964bba4e43f18b3755fee2ff36` |
| Rendition JS | 980 byte (+115), `23aaf7ee195a99e088c6d562326f6c201bb82da3586ac20fda7bc5d652015b5e` |
| Risorse servite | 5 richieste, 1 011 865 byte, tutte dal client HTTPS pinnato del processo padre |
| Sandbox | Chromium sandbox ON, `bwrap --unshare-net`, wrapper `818bd85b…2371c` |
| Cambio URL | solo fragment aggiunto dal router client (`#/`): permesso e registrato |
| Effetti | `downloads=0`, `uploads=0`, `profile_reuse=0`, `publication=HOLD` |

Il body della pagina non entra nel repository: la ricevuta conserva solo hash e
conteggi. Il fetch statico mostra una lista vuota (`<ul id="todo-list">` senza
elementi) e la rendition mostra il contenuto inserito dal JavaScript: è
esattamente il caso in cui il fallback selettivo è giustificato dai dati.

## Diritti della prova

`rights-canary.v1.json`: decisione `APPROVED`, host `demo.playwright.dev`, scope
`FETCH` + `STORE_BODY` + `PARSE_TEXT`, con `PUBLISH`, `REDISTRIBUTE`,
`MEDIA_DOWNLOAD` e `ASR_MEDIA` non concessi, scadenza 23/11/2026. Base: la pagina
è la demo applicativa pubblicata dal progetto Playwright per i test automatici
(nessun login, nessun dato personale, nessuna citazione pubblicata). Il canary
rifiuta decisioni prive di scope, host non elencati, redirect, corpi oltre il
budget e rendition senza effetto JS (`CANARY_NO_JS_DELTA`).

## Tre difetti reali trovati eseguendo un browser vero

Le fixture sintetiche della PR #201 passavano; una pagina reale no. Ognuno dei
tre è ora coperto da un test che fallisce senza la correzione:

1. **`SIGXFSZ` che chiudeva Chromium.** Il wrapper imponeva `ulimit -f 4096` (4 MiB
   per file): la cache disco di Chromium supera quel limite su una pagina vera e
   il browser usciva con `exitCode=153` (`128+25`), quindi `BROWSER_RENDER_FAILED`.
   Corretto portando il limite a 64 MiB e dichiarando `--disk-cache-size=8388608`.
2. **Gli script di lancio della distribuzione vengono rifiutati tardi.**
   `/usr/bin/google-chrome-stable` su Arch è `#!/bin/bash` che esegue
   `/opt/google/chrome/google-chrome`, path che la sandbox non monta: usciva 127
   dopo l'ammissione. Ora il preflight rifiuta un `#!` con
   `BROWSER_CHROMIUM_LAUNCHER_SCRIPT` e il wrapper fa lo stesso con exit 86;
   il test sceglie un eseguibile reale (`/usr/bin/chromium` o un symlink a `/opt`).
3. **Router client con solo fragment.** Una SPA aggiunge `#/…`: il confronto
   letterale di `page.url` con l'URL richiesto bloccava una rendition legittima.
   Il fragment non lascia mai il browser e non cambia la rappresentazione, quindi
   è ammesso **solo** quando è l'unica differenza ed è registrato
   (`fragment_only_url_change`); qualsiasi altro cambio resta
   `BROWSER_FINAL_URL_CHANGED`.

## Test

```bash
python3 -m unittest tests.test_browser_renderer tests.test_browser_renderer_netns \
  tests.test_dp170_renderer_rights_race tests.test_dp170_renderer_redirect_boundary \
  tests.test_dp170_render_canary
```

25 test, OK, incluso il test che avvia davvero Chromium con sandbox ON
(`test_actual_chromium_executes_local_synthetic_js`) e i test bwrap sul
filesystem ed egress negati. Con Playwright assente dal sistema i test reali si
saltano e la suite resta verde per i contributori.

## Cosa resta e dove è tracciato

- **MiniPC**: la prova reale non è ripetibile lì, `unshare -Ur` è negato dal
  kernel/AppArmor del MiniPC (`kernel.apparmor_restrict_unprivileged_userns=1`), e
  Playwright 1.64 non è installato nel mirror di runtime. La voce di verifica va
  nella checklist di `controlcenter#484` come richiesto dall'owner.
- **Consumer**: il renderer resta opt-in (`browser_render_enabled=False` di
  default, `BROWSER_POLICY_DISABLED` se spento) e non è attivo nel mirror di
  produzione; l'installazione e l'uso reale richiedono una fonte con diritti
  `FETCH`/`STORE_BODY`/`PARSE_TEXT` correnti e la decisione dell'operatore.
- Nessun contenuto di terzi è archiviato o pubblicato; nessuna modifica a
  AppArmor, kernel o sandbox del sistema.
