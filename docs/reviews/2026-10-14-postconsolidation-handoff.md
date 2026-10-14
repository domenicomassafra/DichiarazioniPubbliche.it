# DichiarazioniPubbliche.it — handoff operativo / pending finale

**Data:** 14 ottobre 2026, ora locale Europe/Rome. **Repo canonico:**
`/Users/domenico/Code/DichiarazioniPubbliche.it` su Mac Studio. **Integratore:**
`/Users/domenico/Code/DP-20261014-all-lanes-integrator`.
Questo documento è una ricevuta tecnica e un punto di ripartenza, **non** una
chiusura delle acceptance fisiche, legali, editoriali, di sicurezza applicata
alla produzione o delle autorizzazioni sulle fonti.

## TL;DR e autorità Git

- `main == origin/main` **`33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`**, pulito e intenzionalmente invariato.
- Il branch `integrate/dp-20261014-all-lanes` contiene **11 merge Git reali**
  delle corsie DP-231, DP-314, DP-320/431, DP-429, DP-435/436, DP-438,
  DP-439 e DP-440. La baseline integrata e revisionata è
  `28f57c4cdbe9a363a2b35d30647535ea4e6002f3`; il follow-up documentale
  già pubblicato è `2a85c7855f7c6438cfc57092388370ef183ac168`.
  Verificare sempre `git rev-parse HEAD` e `git ls-remote origin` per lo SHA
  dell'eventuale nuovo follow-up, non trattare i checkpoint come HEAD eterni.
- Protezione `main`: **11 check GitHub richiesti e PR review**. Zero PR aperte
  nell'ultimo readback; gli endpoint read-only Copilot account e repo danno
  HTTP **404**, dunque OFF auto-review non verificato. Gate obbligatorio:
  **`PR_HELD_AUTOREVIEW_BILLING_GUARD`**. Consentiti commit/push/readback su
  integratore, **non** nuovo PR/merge diretto/deploy senza superamento del gate.
- Ledger `python3 tools/report_ticket_status.py --json`: **162 ticket, 90 DONE,
  52 IN PROGRESS, 6 BLOCKED, 14 FUTURE, 72 non DONE**; PLAN e ticket
  coerenti. Nessun Status/AC modificato per far risultare pronto il prodotto.

## Funzionalità tecniche integrate e fix

1. **DP-231**: riconciliazione metadati privati fra release, Content collegati
   e standalone, pin SHA/URL/policy anti-TOCTOU, hold tipizzato
   `METADATA_EMPTY_RECORD_REVIEW`; nessun permesso fonte automatico.
2. **DP-314**: wave di ricerca, requirement coverage, research delta e
   transizioni di profili/eleggibilità; prove avversariali su diritti, review,
   root/famiglia indipendenti e batch tipizzati. Nessun verdetto automatico.
3. **DP-320 + DP-431**: revoca offline con coorte di 7/8 superfici e manifest
   coerente sotto un unico release pin; SQLite isolato, policy e source epoch
   fail-closed; ricerca Python compatibile con il consumer reale TypeScript
   `buildSearchIndexMaterial` / `finalizeSearchIndex` /
   `validateSearchIndex`, compreso `contents=[]`, first-class e legacy.
4. **DP-440**: sintesi citate in read model approvato e planner di
   rigenerazione offline; corretto falso rifiuto P2 su lineage legittimamente
   condivisi, mantenendo il blocco su perdita reale di indipendenza e diritti.
5. **DP-439**: Persona × Tema v3, navigazione mensile temporale, trend e
   continuità multi-release; snapshot detached e ricevute UTC separatamente
   originate, fonte/revoca/pin verificati, SSR **solo preview offline
   `noindex`**. Corretto P2 paginazione senza filtri (`?pagina=1` esplicito)
   e P2 URL operatore: `fonte` non pubblica e `q` senza match non devono essere
   riecheggiati in link condivisibili. Identità private mai in link pubblici.
6. **DP-438 e DP-435/436**: snapshot immutabili Person/Statement, homonym,
   scadenze cross-reader e pin di componenti/JSON-LD/API; nessuna rotta
   pubblica v3 o permesso di pubblicazione automaticamente ottenuti.
7. **DP-429**: filtri Explore mobile, suggerimenti e confine corpus pubblico,
   fixture browser vuote/demo con tastiera, AX, zoom/reflow 200%.

## Prove tecniche e limiti

- **Full Python su codice integrato baseline**: 3.624/3.624 PASS, exit 0,
  460.402 s, `/tmp/dp-20261014-integrated-11-leaf-FULL.log`.
  Quest'ultima prova è sul codice **prima** del follow-up lint/handoff; non
  sostituisce una nuova esecuzione se il codice cambia.
- Focused integrati nella ricevuta baseline: **304/304 PASS**. Benchmark
  deterministico **5/5 PASS**. Astro `npm run check` **129 file,
  0 errori/0 warning, 1 hint preesistente**; Node Python→TypeScript reader,
  Source/Person/Topic, paginazione, sessione operatore e cross-reader PASS;
  DP431 parità **9 build TypeScript reali**, `check:rebuild` demo confinato,
  4 failure injection fail-closed; browser DP429 isolato vuoto/demo PASS.
- Reviewer `worker-11` realmente indipendente sul diff
  `28f57c4..`: 141/141 test mirati DP320/431/DP231/DP440 e attacchi mirati
  DP439/231/440, senza nuovi P1/P2 nel perimetro **offline**. Non ha
  rieseguito la full suite, né ha validato diritti fisici o produzione.
- **Follow-up piccolo fix 14 ottobre:** eliminato import Python inutilizzato
  `RequirementClaim` in `tests/test_dp314_requirement_research_batch_20261014.py`
  (Ruff F401). Ruff ora **PASS su tutti i 40 file Python modificati**;
  64/64 test DP314 PASS e benchmark 5/5 PASS dopo la correzione. Questa
  modifica non cambia il comportamento runtime. La nuova full Python sul
  follow-up va annotata solo dopo conclusione effettiva.
- `ruff format --check` globale non era verde sul checkpoint integratore:
  14 file storici non conformi; non fare mass-format mentre altre verifiche
  dipendono da SHA, senza ticket e review del diff.
- Non equiparare Python/Node/Astro o browser isolato a CI su PR, MiniPC
  operativo, reale ritiro HTTP/CDN, PostgreSQL live, VoiceOver fisico, diritti o
  verifica qualificata dei fatti.

## Inventario, quattro host, cleanup

- Mac Studio è unico integratore Git; MiniPC Linux in
  `/home/udodo/src/DichiarazioniPubbliche.it` è **mirror runtime non Git**,
  non un secondo branch da forzare. MacBook Air e MateBook Linux sono stati
  raggiunti da SSH e sottoposti a survey bounded; nessun checkout sorgente
  DP aggiuntivo è stato trovato nei percorsi controllati.
- La pulizia precedente ha chiuso **50 worktree** dopo preflight di
  contenuto: clean già in main, file byte-identici, lavoro superseded da
  test/commit salvati, e branch leaf confermati antenati dell'integratore
  remoto. Due worktree restano intenzionalmente: canonico e integratore.
- **1.652.548 KiB nominali** di directory ritirate cumulativamente, circa
  **1,58 GiB**. Non è un delta `df` APFS e **NON sono 10 GiB**. Non cancellare
  dati di altri progetti per raggiungere il numero richiesto; cache in uso e
  `web/node_modules` canonico preservati. Backup/rollback MiniPC e transcript
  raw sono beni con restore non dimostrato e restano intatti.
- I vecchi branch sorgente erano stati verificati antenati dell'integratore
  remoto prima del cleanup: la cronologia rimane raggiungibile nel branch
  integratore. Il branch integratore non è ancora integrato in `main`.
  Revalidare stato worktree/stash/remote prima di ulteriori pulizie, non
  dedurre l'assenza di WIP dalle conversazioni passate.

## Pending espliciti / dipendenze esterne

1. **Gate PR e merge:** provare OFF Codex auto-review su **account e repo**
   oppure ottenere approvazione esplicita dei possibili costi dall'owner;
   aprire PR solo con SHA remoto esatto, `python3 ~/.dstack/scripts/check_pr_merge_gate.py
   --github-repo domenicomassafra/DichiarazioniPubbliche.it --pr N`, CI
   exact-head, zero thread irrisolti e `PR_MERGE_GATE_PASS` prima del merge.
   Verificare poi `main` e ref remoto: niente push diretto come scorciatoia.
2. **DP-214/215** role di fonte ufficiale e source approval: owner/source
   gated, vietati GET body/capture non autorizzati. Retrieval e candidato
   metadata **non** provano approvazione o diritti.
3. **DP-409** Statement `archive_added_at`: decisione upstream non
   autorizzata. Non fabbricare timestamps storici o Statement v3 pubblici.
4. **DP-514** PostgreSQL SQLSTATE 57014: causa radice non provata;
   nessun incremento speculativo timeout/retry e nessuna dichiarazione
   di chiusura su una run verde.
5. **DP-443 e rollout reale:** pilot owner/editoriale/source rights,
   fact-check qualificato, media, accessibilità manuale, MiniPC fisico e
   revoca HTTP/CDN restano gate espliciti; release `NO-GO` finché mancano.
6. **WIP residuo di prodotto:** 72 ticket non DONE, status invariati;
   le implementazioni private/offline non bastano a completare criteri
   editoriali, legali o di produzione.

## Problemi Chat On Steroids e fix proposti (NON implementati)

- **Worker che non rispondono**: il browser non espone a volte un composer
  utilizzabile oppure non acquisisce il comando entro la deadline. Serve un
  health probe composer/tab **prima** del dispatch, con eventuale fallback
  seriale e senza deleghe duplicate o revival ripetuti.
- **Risultati esecuzioni/sessions intermittenti**: alcuni `write_stdin`
  su sessioni precedenti diventano `EXEC_SESSION_UNAVAILABLE`; distinguere
  processo terminato, sessione evicted e backend non raggiungibile tramite
  result-id persistente, log append-only e readback `git`/file effettivi.
- **Blocchi safety/transport intermittenti** anche su certi comandi shell
  innocui: registrare input minimizzato, codice errore e correlazione
  sessione, non ripetere operazioni distruttive dopo errore ambiguo.
- **Prevenzione conflitti**: owner lease per path/worktree, record degli SHA
  prima/dopo, `git status` esatto, integrazioni idempotenti e conferma
  indipendente dei test. Nessuna radice diagnostica dimostrata finché non
  si verifica un test riproducibile sull'implementazione CoS stessa.

## Istruzioni per ripartire in sicurezza

1. Leggere `AGENTS.md`, `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`,
   `PLAN.md`, questo documento e
   `docs/reviews/2026-10-14-all-lanes-consolidation-receipt.md`.
2. Controllare `git status --short --branch`, `git worktree list`, `git
   stash list`, `git ls-remote`, ledger con script canonico, PR, gate costi.
3. Continuare solo su branch isolato/integrazione preservando i pin dei
   reader; RED→GREEN, reviewer indipendente, `git diff --check` e readback
   remoto; non modificare `main` salvo PR approvata + gate.
4. Aggiornare i numeri di questo handoff **con prove sullo SHA esatto**.
   Se full suite si interrompe o un worker fallisce, segnare outcome reale,
   non convertire in PASS né in ticket DONE.

**Nessun nuovo deploy, nessuna pubblicazione editoriale, nessuna scrittura
su DB di produzione, nessun servizio/provider a pagamento e nessuna nuova
spesa infrastrutturale in questa tranche.**
