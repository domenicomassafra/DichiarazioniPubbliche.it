# DP #587 — script Node di test e prototipi
[Fonti, criteri e readback](native-first-inventory-2026-11-03.md).

Questi dodici file sono stati inclusi dopo la review indipendente della PR #588: otto `tests/*.(mjs|cjs)` (due invocati da unit test Python DP-419) e quattro prototipi con estensioni JavaScript. I tool Node nativi (`node:vm`, `node:assert`, esbuild) sono usati dove possibile, ma le assertions DOM/privacy e le fixture specifiche sono dominio DP. Il CDP del prototipo DP-441 e' storico e non attivato come servizio; prima di riproporlo al redesign finale, migrare la navigazione ad `agent-browser`.

| Percorso | Funzione osservata | Tool o alternativa nativa | Classe | Evidenza e motivazione |
| --- | --- | --- | --- | --- |
| `tests/dp410_public_source_dates.mjs` | Controllo date e fonti pubbliche DP-410 | Node.js + rendering SSR | **GAP** | S-LOCAL: test cross-artifact dominio DP, non coperto dal solo Node --test |
| `tests/dp429_explore_accessibility_regression.mjs` | Regressione a11y Explore DP-429 | Node.js + Astro/Chromium | **GAP** | S-ASTRO: comportamento accessibilita browser su corpus DP, oltre build/check nativi |
| `tests/studio_capture_diff_assertions.cjs` | Asserzioni di dominio per Capture diff privato | node:assert (nativo) | **GAP** | S-LOCAL: assertions condivise sull isolamento del token e clipboard private |
| `tests/studio_capture_diff_dom.cjs` | DOM simulato per eseguire JS Studio autentico | node:vm + node:assert | **GAP** | S-LOCAL: DOM fixture con nonce, clipboard e richieste private non sostituibile da runner generico |
| `tests/studio_capture_route_privacy.cjs` | Simulazione delle risposte private alle route Capture | node:vm + node:assert | **GAP** | S-LOCAL: consentono di intercettare leakage specifico di header/body in DOM |
| `tests/studio_local_page_accessibility_next.mjs` | Prova Chrome tastiera e layout Studio | Chromium + Node browser QA | **GAP** | S-LOCAL: test contenuti e keyboard flow DP; browser driver da riconsiderare se invocato da job live |
| `tests/studio_local_page_async_regression.cjs` | Regressione risposte async Studio | node:vm + node:assert | **GAP** | S-LOCAL: osserva race e stale-response privacy; comportamento non previsto dal test runner generico |
| `tests/studio_local_page_chrome_regression.mjs` | Chromium test in pagina Studio privata | Chromium + Node browser QA | **GAP** | S-LOCAL: regressioni DP specifiche e fixture isolate, non un servizio installato |
| `prototypes/redesign-candidates/capture.mjs` | Screenshot prototipi redesign, CDP su tab Studio storico | agent-browser per nuovi test | **GAP** | S-AGENT-BROWSER: prototipo DP-441 storico con porta Studio 17630, non installato; restano fixture multi-variant, hash e screenshots auditabili. Produzione rinviata al redesign |
| `prototypes/ux-v0/demo-data.js` | Modulo dati demo UX-v0 | Modulo JavaScript nativo | **NATIVE** | S-LOCAL: JavaScript caricato direttamente come modulo di dati di prototipo |
| `prototypes/v4-implementation/dp407/test-content-audit-keyboard-wave11.mjs` | Test Chrome isolato React DP-407 | Node/esbuild/Chromium | **GAP** | S-LOCAL: test della semantica e keyboard DP-407 su fixture isolata; non schedulato come worker |
| `prototypes/v4-implementation/dp407/test-contentrecord-real-wave11.mjs` | Test percorso pubblico contenuti DP-407 | Node/esbuild/Chromium | **GAP** | S-LOCAL: asserzioni specifiche di schemi e contenuti DP su fixture locale, non equivalenti a build |
