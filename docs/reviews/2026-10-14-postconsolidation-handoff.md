# DichiarazioniPubbliche.it — handoff operativo / pending finale

**Ottava tranche DP02, source remoto:** nuovo hardlink P1 dopo la
protezione root/symlink DP517: alias HTTP pubblico con stesso inode del
database SQLite/account o delle sidecar WAL/SHM poteva ancora esporre
contenuto privato. Le nuove prove HTTP locali hanno mostrato sette RED
più il gap del path segreto; `dfd178d3ae05cf3d11e8f6ec78f574902023e022`
introduce guard di inode sul file realmente selezionato (anche index),
passaggio del secret path CLI e divieto di segreto dentro public root;
**156/156 test account/API/privacy, Ruff, compileall e diff-check PASS**.
Branch remoto uguale, nessun `main`/PR/deploy/MiniPC. [Dettagli della
tranche](2026-10-14-dp02-execution-closure.md) e
[runbook account](../release/account-oidc-activation.md).

**Full Python wave8 successiva alla correzione PLAN:** sorgente immutata
`dfd178d3ae05cf3d11e8f6ec78f574902023e022`, **3674/3674 PASS,
exit0, 1353.431s** sul tree documentale corretto, log
`/tmp/dp02-wave8-planfixed-full-20261014.log`. Il primo run su
`dfd178d` aveva `3674/1 FAIL` nel test originale di autorità documentale:
la sezione nuova in testa a PLAN oscurava il comando canonico richiesto.
Riposizionamento della sola sezione, test immutato e RED→GREEN mirato.

**Gate Python storico da non nascondere:** full sul source
`2516e42` era **3670 test, tre FAIL DP238 PDF worker unavailable, exit 1**,
nonostante retest isolato PDF 11/11 PASS. Il precedente 3665/3665 PASS
appartiene al commit DP312 `4873a2f`; la prova completa su `dfd178d` è
riportata sopra. **162/90 DONE/72 aperti e preflight NO-GO/49**;
DP312 e DP517 mantengono gli AC originali aperti, così come i gate
PR/CI, dati/diritti, legal/privacy, source reali, MiniPC e screen reader.

**Settima tranche DP02, 14 ottobre:** nuovo commit DP-517
`2516e42f4421757c393cf912f9483a70f2bbf1d4`, separato da DP312 e
pubblicato sul branch integratore con readback SHA uguale. Server account
misconfigurato poteva consegnare SQLite account e dati fittizi con GET
anonimo, oppure via symlink; secret OAuth sotto static root ammesso dalla
CLI. RED HTTP reale ma solo locale/temp, protezione di path privati e
static GET/HEAD, **121/121 test** specifici+adiacenti, Ruff/diff-check
PASS. Nessuna autentica Google, legal approval, CDN/MiniPC, PR/main/deploy.
DP-517 FUTURE con AC1–7 OPEN. Full Python sul nuovo commit distinta da
quella DP312, da attestare; launch preflight resta NO-GO/49 e reporter
90 DONE/72 non DONE.

**Sesta tranche DP02, 14 ottobre:** nuovo source commit DP-312
`4873a2fb7508165a62a6de42ed49a9cbc4fa9379` su branch
`integrate/dp-20261014-all-lanes`, push/readback remoto uguale e worktree
pulito. Quattro falsi endorsement da quote CJK complete sono passati da RED
a GREEN con test avversari per delimitatori malformati; 32 focused, 48
adiacenti, benchmark 5/5, Ruff e diff-check PASS. **Full Python 3665/3665
PASS, exit0, 571,183 s** sullo SHA del codice. L'originale DP312 AC1–6
è ancora OPEN: non è stata ottenuta alcuna licenza/identità/Gold, prova
MiniPC, approvazione editoriale o via libera a un lettore pubblico.
Contatori **162/90 DONE/72 non DONE** e preflight **NO-GO/49** invariati;
`main` DP rimane distinto e non avanzato. [Dettagli e prove](2026-10-14-dp02-execution-closure.md).

**Nuovo checkpoint quinta tranche, 14 ottobre:** il branch integratore
`integrate/dp-20261014-all-lanes` ha il source commit
`e7210a73fdfcdf8f3cf42fe78264127a48a6221c`, letto uguale da remoto,
con tre ulteriori RED→GREEN DP-319/440/320 (costo assignment, autonomia
review synopsis, limit 128 per ticket di revoca). Le prove locali sono
44/43/51 PASS con lint e diffcheck verdi; [ricevuta DP02](2026-10-14-dp02-execution-closure.md)
separa esattamente le fix dal mancato completamento degli AC reali.
**Full Python sul nuovo source: 3664/3664 PASS, exit0, 358,844 s**, log
`/tmp/dp02-wave5-final-full-20261014.log`: non trasferire a questo SHA
il precedente 3661/1 della wave4. Ops response precedente c49809b resta
pubblicata, eventuale nuovo addendum richiede lease esplicita concorrente.
Preflight **NO-GO/49**, contatori 162/90 DONE/72 non DONE invariati.
**Response lane02 quinta wave** è effettivamente pubblicata su Ops `main`
come `94feaad5401a1abab29856a480d6bb7dbe4e88e8` (uno e un solo path,
SHA remoto identico). Lease writer Core07 esplicita ricevuta e rilasciata;
dirty WIP 01/05/305 e Core07 sono rimasti non staged/intatti.


**Quarta wave DP02, nuova frontiera (14 ottobre):** source integratrice
`91b1783654b69888196b509bab71c19dc1aaf1ce` sul branch
`integrate/dp-20261014-all-lanes`, verificata con readback remoto; sei
tranche RED→GREEN DP-313/318/438/317/439/435, più runbook OIDC DP-517
verificato (107/107). Il [rapporto esecutivo](2026-10-14-dp02-execution-closure.md)
contiene gli SHA per ticket, le prove, la natura solo sintetica e i
criteri originali ancora OPEN. Il
[censimento delle dichiarazioni](2026-10-14-dp02-declarations-inventory.md)
ora documenta 117 link iniziali e **124/124 relativi sul tree aggiornato**,
e identifica con precisione le quattro
route informative/legali ancora assenti. ControlCenter Ops era
`65dafd8` a inizio ripresa; il successivo aggiornamento della sola
`02-dichiarazioni-pubbliche.response.md` è stato **pubblicato** con writer
Ops esclusivo su `main` a `685a04e74878516f30edeb7e4b8720d68c1c012a`
e readback remoto identico, senza toccare 01/05/305. Status registro: 162/90 DONE/72 non DONE;
`PR_HELD_AUTOREVIEW_BILLING_GUARD`, rights/qualifiche, pilot MiniPC e
`NO-GO/49` rimangono aperti. La full suite finale wave4 deve essere
identificata per l'esatto codice, non per test precedenti.
**Full run wave4 effettivo:** 3.661 test, **1 FAIL DP238 PDF worker unavailable**,
exit 1 in 826,816 s, source `91b1783`. Regressioni DP238 mirate 11/11 e
22/22 incluse adiacenti PASS; il gate integrale resta **non superato**.
Log e prova riproducibile in [ricevuta DP02](2026-10-14-dp02-execution-closure.md).
L'addendum al packet Ops 297 con la suite **non verde** è pubblicato in
Ops `main` a `c49809baada076fcb4f6a88ea9f8e82adb9a3a59`, sotto lease
esplicita esclusiva successivamente rilasciata, senza alterare altri WIP.


**Ultimo source checkpoint DP02 (terza wave):** `186ef17e59fe73cab061a5301ffbe0d9f5443721`
**ControlCenter Ops packet 297** ora contiene anche il readback della
terza wave in `main` a `65dafd8ecb31b45889d2dc90fbdb63dd81d7d1c2`,
commit documentale separato che preserva gli altri WIP 01/05/305.
nel solo branch integratore, con DP-517/516/243/515 pubblicati e lettura
remota verificata. Ticket e status originari restano aperti, release NO-GO.
La [ricevuta DP02](2026-10-14-dp02-execution-closure.md) e il
[censimento pubblico](2026-10-14-dp02-declarations-inventory.md)
sono l'autorità del nuovo readback. Ops packet 297 ha pubblicato la
risposta della lane su `main` con commit `3cfb3c433d79fd1dc4f7c543e5dae1263700303f`;
le altre lane Ops restano indipendenti. GH run `38596675716`: solo
repository contract PASS, PR/backend/web/clean-clone non attestati.
**Gate finale wave3 sul source `186ef17`:** 3.652/3.652 unittest PASS,
exit 0, 322,598 s; `PR_HELD_AUTOREVIEW_BILLING_GUARD` e
launch preflight `NO-GO/49` invariati.

**Data:** 14 ottobre 2026, ora locale Europe/Rome. **Repo canonico:**
`/Users/domenico/Code/DichiarazioniPubbliche.it` su Mac Studio. **Integratore:**
`/Users/domenico/Code/DP-20261014-all-lanes-integrator`.
Questo documento è una ricevuta tecnica e un punto di ripartenza, **non** una
chiusura delle acceptance fisiche, legali, editoriali, di sicurezza applicata
alla produzione o delle autorizzazioni sulle fonti.

**Ripresa DP02 del 14 ottobre:** la
[ricevuta delle nuove tranche](2026-10-14-dp02-execution-closure.md)
confronta i commit effettivamente consegnati e il CI readback sul branch
integratore con le acceptance ancora mancanti. Usa quella ricevuta e i ticket
originali per le successive decisioni; gli SHA storici sotto non sono l'HEAD
attuale.
Il codice `a63fe133` ha ora una suite completa fresca **3.637/3.637 PASS,
exit 0, 520,154 s**; la CI branch `38587368015` esegue il solo
`repository contract`, con gli altri job `skipped`. La
[mappa delle dichiarazioni e delle superfici SOP/Skills/Rules/Operations](2026-10-14-dp02-declarations-inventory.md)
documenta route presenti e testi legali/pubblici non ancora autorizzati.
**Aggiornamento successivo:** codice `bb00177` con DP242/244/519/518,
full Python **3.645/3.645 PASS, exit0, 362,131 s**; Github run
`38593285587` esegue solo repository contract. La
[ricevuta DP02](2026-10-14-dp02-execution-closure.md) è il punto di
ripartenza più recente, con tutti gli AC originali e release NO-GO.

## TL;DR e autorità Git

- `main == origin/main` **`33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`**, pulito e intenzionalmente invariato.
- **Chiarimento CI verificato il 14 ottobre:** `gh run view 38561882494`
  sul commit integratore `15fee6c` riporta `success` **solo** per
  `repository contract`; le tre famiglie di job backend (matrix), web e
  clean-clone sono `skipped`, conformemente ai rispettivi `if` PR/main
  nel workflow. Lo stesso vale per la run `38561730777` (`0228fa8`).
  Nessuna full matrix di PR/merge è stata quindi provata da queste run.
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
  modifica non cambia il comportamento runtime. Sul commit codice
  **`0228fa8196d4136ca4807b9fa224592fe666ea49`**, la full suite
  post-correzione è **3.624/3.624 PASS, exit 0, 664.442 secondi**;
  log `/tmp/dp-20261014-lint-handoff-postfix-full.log`. I successivi commit
  esclusivamente documentali non modificano il sorgente verificato.
- `ruff format --check` globale non era verde sul checkpoint integratore:
  14 file storici non conformi; non fare mass-format mentre altre verifiche
  dipendono da SHA, senza ticket e review del diff.
- Non equiparare Python/Node/Astro o browser isolato a CI su PR, MiniPC
  operativo, reale ritiro HTTP/CDN, PostgreSQL live, VoiceOver fisico, diritti o
  verifica qualificata dei fatti.

**Limite review finale:** la code review indipendente documentata riguarda
il checkpoint integratore sorgente `28f57c4...`; per il follow-up del solo
import F401 e handoff è stata effettuata una verifica source-only del diff,
dei test e delle corrispondenze byte. I tentativi di risvegliare due worker
per una seconda revisione non sono stati acquisiti dal composer Chat On
Steroids. Non dichiarare per questo commit un secondo PASS indipendente.

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
