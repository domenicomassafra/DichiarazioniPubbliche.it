# DP02 — esecuzione parallela, bug fix e gate di release (14 ottobre 2026)

## Ottava tranche — hardlink account, prova negativa reale e nuovo source SHA

**Commit pubblicato:** `dfd178d3ae05cf3d11e8f6ec78f574902023e022`,
branch `integrate/dp-20261014-all-lanes`, readback remoto identico; stage
esclusivamente `public_api.py`, `test_dp517_account_static_exposure_20261014.py`
e `DP-517-reader-google-login.md`. È un P1 aggiuntivo, **non** la
riedizione del controllo root/symlink di `2516e42` già integrato.

**RED:** sei combinazioni HTTP `GET`/`HEAD` di hardlink del database SQLite,
WAL e SHM più la route `/` con alias `index.html` potevano esporre file
privati: sette failure reali su soli dati sintetici e socket loopback. La
protezione `Path.resolve()` non rileva identità di inode. Una regressione
separata del segreto OAuth hardlink ha inizialmente fallito perché il server
programmatico non riceveva la path privata del secret.

**GREEN:** dopo il controllo delle identità `(st_dev, st_ino)` sul file
finale, incluso il default index, database e sidecar non sono scaricabili
con un alias hardlink. Il secret file protetto viene fornito al server
tramite il percorso CLI e controllato con gli stessi criteri; una
configurazione diretta con segreto dentro public root è respinta.
`GET /index.html`, `GET /`, `HEAD` pubblici e `401` dell'account anonimo
restano validi. **156/156** test account/API/privacy collegati PASS; lint
Ruff, `compileall`, `git diff --check` PASS. Nessuna autenticazione reale,
payload privato dell'owner, binding esposto o modifica MiniPC.

**Full suite precedente distinta:** source `2516e42`, log
`/tmp/dp02-wave7-dp517-full-20261014.log`: **3670 test in 1213,821 s,
3 FAIL, exit 1**. Precisamente DP-238
`test_encrypted_document_needs_external_authority`,
`test_page_count_limit_precedes_text_extraction`,
`test_pdf_image_mixed_with_text_requires_ocr_or_independent_review` hanno
ottenuto `DOCUMENT_PDF_WORKER_UNAVAILABLE` invece della categoria PDF
attesa. Retest isolato PDF **11/11 PASS**; causa deterministica ancora non
provata, nessun aumento del timeout. La full suite sul più recente
`dfd178d` richiede un exit finale proprio; un `OK` del parent non basta.

**Run completi sul nuovo source:** primo run su `dfd178d` e documenti
ancora in modifica: `Ran 3674 tests in 681.616s`, `FAILED (failures=1)`,
exit1. Il test originale
`LiveDocumentationAuthorityTests.test_plan_labels_pre_expansion_125_ticket_checkpoint_as_historical`
richiedeva il comando reporter nei primi 1500 caratteri di `PLAN.md`:
la sezione DP02 era stata aggiunta sopra i metadata canonici. **RED→GREEN**
spostando solo la sezione sotto i metadata, senza modificare il test:
test mirato e repository contract PASS. La successiva full suite sullo
stesso source `dfd178d` e sul `PLAN.md` corretto è **3674/3674 PASS,
exit0, 1353.431s**, log `/tmp/dp02-wave8-planfixed-full-20261014.log`.
Questo non costituisce un fix della precedente intermittente DP238:
nessuna modifica al parser PDF/timeout è stata fatta.

**CI di branch per `dfd178d`:** GitHub Actions run `38617805928` risulta
`completed/success`, ma il dettaglio job prova esclusivamente
`repository contract=success`; `backend matrix`, `web static frontend` e
`detached clean-clone smoke` sono tutti `skipped`. Questo NON attesta CI di
PR o readiness di produzione e non supera la guardia di auto-review billing.

**Originali:** AC-517.1–7 ancora OPEN e ticket FUTURE; il guard inode
locale non è sandbox atomica contro writer malevoli, né certifica Google,
privacy/retention, reverse proxy/MiniPC, CDN o accessibilità. Anche DP312
resta OPEN; registro 162/90 DONE/72 non DONE, preflight NO-GO/49, guardia
PR billing e tutte le decisioni Q-306 invariati.

## Settima tranche — DP-517 isolamento del database account da static HTTP

Nuovo commit sorgente separato
`2516e42f4421757c393cf912f9483a70f2bbf1d4` pubblicato sul medesimo
branch `integrate/dp-20261014-all-lanes` con SHA remoto uguale. In una
prova HTTP reale, loopback e account SQLite **temporaneo con utente
sintetico**, il server account che serviva anche una `static_dir` coincidente
con quella del database permetteva `GET /accounts.sqlite3` anonimo 200
e restituiva header SQLite e indirizzo fittizio. Un symlink pubblico a file
SQLite privato passava; un segreto OAuth posto sotto public root superava
la configurazione CLI. Le tre classi erano RED prima del fix.

Il server ora rifiuta l'account SQLite la cui path reale ricade sotto la
root pubblica; la CLI controlla allo stesso modo SQLite e secret OAuth;
GET e HEAD statici, quando account è attivo, rifiutano symlink il cui target
esce dalla root. Pagine statiche GET/HEAD e sessione anonima mantengono i
comportamenti precedenti. Test mirati e adiacenti account/HTTP/API/inventario
privacy **121/121 PASS**, Ruff, compileall e diff-check PASS. La review
del prime ha limitato lo stage ai tre file DP517 (source, nuovo test, ticket).

**AC-517.1–7 restano tutti OPEN / ticket FUTURE**: non è stato usato
Google reale né letto un account vero; mancano approvazione della privacy,
WAL/backups/retention e diritti, replica MiniPC/proxy/CDN, accessibilità,
owner signoff, PR/CI e rollback. Non trasformare in evento pubblico la
fixture localhost. La full suite Python sul nuovo SHA è da attestare con
un nuovo run; quella DP312 3665/3665 PASS appartiene al parent
`4873a2f`, non basta automaticamente come gate di DP517.

## Sesta tranche — DP-312 citazioni contestuali e full Python sul nuovo codice

Il branch integratore `integrate/dp-20261014-all-lanes` è passato dal sigillo
precedente `bf96a8bab02b4f24abcbb9dcab83096bb25aa36a` al fix
**DP-312** `4873a2fb7508165a62a6de42ed49a9cbc4fa9379`, con
`HEAD == ls-remote origin` e worktree pulito dopo push. Una fonte inglese
racchiusa nei quattro stili di virgolette CJK (U+300C/D, U+300E/F,
U+300A/B, U+3010/11) produceva falsamente `ASSERTION/ENDORSE` come
fosse l'adesione diretta dell'utterer. Il nuovo test ha riprodotto quattro
failure RED prima del fix; ora le quote complete sono `QUOTE/NON_COMMITTAL`
e le forme incomplete, invertite o annidate generano `HOLD_FOR_CONTEXT`
con `UNBALANCED_QUOTATION`. Controllo positivo di frase davvero diretta,
replay metadata immutabile, 32/32 test DP312, 15/15 legacy context,
26/26 relations, 7/7 opinion reader, benchmark 5/5, Ruff,
repository contract e diff-check PASS. Commit con soli sorgente, test e
ticket DP312, senza provider/host/diritti pubblici.

**Full Python sulla source esatta `4873a2f`:**
`PYTHONPATH=poc python3 -B -m unittest discover -s tests -q`,
`Ran 3665 tests in 571.183s`, `OK`, exit0,
log `/tmp/dp02-wave6-dp312-full-20261014.log`.
La formattazione globale di quei due Python resta debito preesistente:
`ruff format --check` falliva anche sulle rispettive versioni `bf96a8b`;
`ruff check` nuovo PASS, nessuna riscrittura cosmetica. La quinta tranche
precedente era già 3664 PASS sullo SHA diverso `e7210a7`/sigillo docs
`bf96a8b`, e la vecchia failure DP238 della quarta wave resta storica.

**Disposition originale non cambiata:** DP-312.1–6 OPEN (Gold/speaker,
licensed multilingual source, rights, downstream invalidation, MiniPC).
Registro 162/90 DONE/72 non DONE, preflight NO-GO/49 con 16 Q-306,
4 artefatti release mancanti e 29 launch ticket non DONE, più guardia
PR billing/CI, documenti legali, approvazioni, rights e test reader/CDN.
Questo solo commit di branch remoto non autorizza PR/merge o deploy.

## Quinta wave — tre ulteriori fix indipendenti e prerequisiti di rilascio

**Response lane02 pubblicata sul packet ControlCenter Ops `main`:**
`94feaad5401a1abab29856a480d6bb7dbe4e88e8`, commit normale che
contiene **solo**
`tasks/20260929-main-release-closure/297-handoff-restart-20261012/02-dichiarazioni-pubbliche.response.md`.
Lease Git Ops esclusiva concessa esplicitamente dal prime Core07, preimage
`941252f0ff7406d533e47343517735167d03f4f9` HEAD e origin/main uguali,
indice vuoto; staged path unico verificato, `git diff --cached --check`
PASS, push normale e readback `ls-remote` uguale a `94feaad`. Lease
**rilasciata esplicitamente** subito dopo il commit. WIP 01/05/305 e tre
documenti Core07/tools estranei intatti, nessun PR/merge prodotto.

Ripresa da checkpoint source `7607a20caed2462e11e304b664219676d6e4b196`
e risposta Ops già su `main` `c49809baada076fcb4f6a88ea9f8e82adb9a3a59`;
il primo aggiornamento documentale allineato al risultato **non verde**
della precedente full suite è `8014da07014f3dfcc72946198b515e32f9555d6b`.
I fix DP-313/317/318/435/438/439 sono già in history e non sono stati
ripetuti. Quattro assignment disgiunti ai worker CoS per DP-238/320/440/436
sono stati tentati; le sessioni UI di revival/nuovi worker non hanno preso
in carico il lavoro in modo affidabile. **Non** sono attribuiti loro test o
commit inesistenti. Il prime ha eseguito tre nuove TDD disgiunte, staging
esclusivo e singolo writer Git sull'integratore:

| Ticket | SHA pubblicato e letto da `ls-remote` | Nuova dimostrazione RED→GREEN | Acceptance originale |
| --- | --- | --- | --- |
| DP-319 | `1746acac54c872ded5570ef3b8ad35edc097c765` | Receipt di spesa `0.04` su assignment con cap `0.03` ma budget complessivo `0.10` era falsamente ammessa; ora `INVESTIGATION_ASSIGNMENT_COST_EXCEEDED`, planner/store 44/44 PASS | AC-319.1–5 OPEN |
| DP-440 | `e91b44fb354b0673248c69e33a8763a6091f8c5c` | Un evento di membership/currentness era riusato come review autonoma di frase di synopsis, 2/2 RED e ora `SYNOPSIS_SENTENCE_PROVENANCE_INVALID`, 43/43 PASS | AC-440.1–7 OPEN |
| DP-320 | `e7210a73fdfcdf8f3cf42fe78264127a48a6221c` | Ticket con 129 dipendenze auto-consistenti poteva passare la fence pur superando cap 128 di `mint`; ora `FENCE_DEPENDENCY_SCOPE_INVALID`, controllo positivo 128, 51/51 PASS | AC-320.1–5 OPEN |

Ogni patch è stata testata RED prima del source change e GREEN dopo, con
Ruff sui Python modificati e `git diff --check` PASS, commit di soli path
owned e readback remoto effettivo. Nessun provider, spesa, fonte, permesso,
release PostgreSQL, UI reale, CDN o MiniPC è stato attivato. I ticket
restano `IN PROGRESS`, non DONE: autenticazione dei review/rights, ledger D,
owner ed editorial entailment restano decisioni esterne. DP-436 consumer
parity e DP-238 worker PDF sono stati riesaminati, ma nessun nuovo source
fix è stato attribuito senza gap riproducibile e una prova sicura; la
precedente full-suite DP238 resta storicamente NON GREEN.

**Suite Python integrale finale GREEN sull'esatto codice
`e7210a73fdfcdf8f3cf42fe78264127a48a6221c`:** eseguito realmente
`PYTHONPATH=poc python3 -B -m unittest discover -s tests -q`; output
`Ran 3664 tests in 358.844s`, `OK`, **exit 0**, log originale
`/tmp/dp02-wave5-final-full-20261014.log`. Nessuna failure o ERROR.
Tutti e tre i fix DP319/320/440 della quinta wave erano già nel codice di
questa esecuzione. Il precedente `3661/1` su `91b1783` resta documentato
come prova storica NON VERDE e non è stato alterato. Il retest integrale
nuovo non riproduce il `DOCUMENT_PDF_WORKER_UNAVAILABLE` di DP238, ma da
solo non ne determina la causa né chiude AC-238 sul runtime reale.
I gate tecnici frontend, privacy, repository/asset e launch preflight sono
attestati separatamente sotto. Il registro è ancora **162 total / 90 DONE /
52 IN PROGRESS / 6 BLOCKED / 14 FUTURE / 72 non DONE / ready 0** e la
release è **NO-GO/49**, oltre a ogni eventuale nuovo blocco da full suite.

**Verifiche di integrazione sul source `e7210a7` (quinta wave):**
Astro `check` senza errori o warning (un hint preesistente), build demo
noindex 34 pagine PASS; search index 7 records, Statement v3 consumer e
backend parity, route contract canonico 8/8, production projection boundary,
design a11y automatico 8/8, quality, trust disclosure e corrections tutti
PASS. Build reale senza proiezione autorizzata resta intenzionalmente HELD;
screen reader manuale PENDING. Repository contract PASS; privacy inventory
1.266 campi è solo `TECHNICAL_ONLY_NOT_LEGAL_CLOSURE`; licensing 47 asset,
fixture inventory e VERSION/changelog PASS. Il preflight reale riporta
**49 blocker** (16 Q-306, quattro release artifact assenti e 29 ticket
launch non DONE). Il crosswalk SOP/Skills/Rules/Operations/packet 297
documenta **138/138 link relativi esistenti** su sette file, con tre locator
esterni ControlCenter/Skills verificati; la presenza di quattro route
informative e l'assenza delle route legali/contatti sono registrate nel
[censimento pubblico](2026-10-14-dp02-declarations-inventory.md).

**CI branch non equivale a CI PR:** GitHub Actions run `38606585858`
riporta `completed/success` sul preciso SHA sorgente
`e7210a73fdfcdf8f3cf42fe78264127a48a6221c`, ma l'unico job eseguito
concluso `success` è `repository contract`: `web static frontend`, matrice
backend e smoke `detached clean-clone` risultano **skipped**. I gate web
citati sopra sono esecuzioni **locali** e non colmano il gate PR/CI esterno
né la review; lo stato release resta NO-GO. Ruff lint sui **sei file Python**
modificati rispetto a `7607a20` PASS, `git diff --check` PASS. Nessun
`ruff format --check` globale è attribuito a file con debito preesistente.

**Riconciliazione esatta del registro (reporter Git, 72 ticket non DONE):**

| Fascia | Conteggio | Ticket non conclusi (stato originale nel file ticket) |
| --- | ---: | --- |
| DP-2xx | 20 | DP-201, DP-202, DP-203, DP-204, DP-208, DP-214, DP-215, DP-229, DP-233, DP-234, DP-235, DP-236, DP-237, DP-238, DP-239, DP-240, DP-241, DP-242, DP-243, DP-244 |
| DP-3xx | 13 | DP-301, DP-304, DP-307, DP-312, DP-313, DP-314, DP-315, DP-316, DP-317, DP-318, DP-319, DP-320, DP-321 |
| DP-4xx | 24 | DP-405, DP-406, DP-407, DP-408, DP-409, DP-410, DP-412, DP-416, DP-417, DP-418, DP-419, DP-420, DP-421, DP-422, DP-429, DP-435, DP-436, DP-437, DP-438, DP-439, DP-440, DP-441, DP-442, DP-443 |
| DP-5xx | 10 | DP-507, DP-508, DP-512, DP-513, DP-514, DP-515, DP-516, DP-517, DP-518, DP-519 |
| DP-7xx | 5 | DP-701, DP-702, DP-703, DP-704, DP-705 |

`20+13+24+10+5=72`; tra essi **52 IN PROGRESS, 6 BLOCKED e 14 FUTURE**;
`files_agree_with_plan=True`, `ready=0`. Il preflight di release include
**esattamente 29** `TICKET_NOT_DONE` direttamente bloccanti:
DP-201, DP-202, DP-203, DP-204, DP-214, DP-215, DP-229, DP-301, DP-304,
DP-307, DP-405, DP-406, DP-407, DP-408, DP-409, DP-410, DP-412, DP-416,
DP-417, DP-418, DP-419, DP-420, DP-421, DP-422, DP-429, DP-701, DP-702,
DP-703, DP-704; gli altri 43 non DONE non sono cancellati ma non figurano
nella lista selettiva del preflight. Inoltre le **16** Q-306-01..16 (04 e
14 BLOCKED, le altre OPEN) e i quattro artefatti `launch_rehearsal`,
`launch_set`, `prelaunch_closure`, `release_authority` mancanti portano il
preflight a `16+4+29=49`. Il gate ulteriore full Python, il PR billing
guard, CI PR, diritti/owner, miniPC/cache/manual AT **non** sono conteggiati
come ticket DONE né inventati in questi 49.


## Quarta wave — checkpoint `0eba7fb`, sei nuovi fix e verifica DP-517

Ripresa dall'integratore locale/remoto
`0eba7fb77dde1e6867f2114527f9dc241bffbe48` e dal packet ControlCenter
Ops `main` `65dafd8ecb31b45889d2dc90fbdb63dd81d7d1c2`. Le quattro fix
DP-517/516/243/515 della terza wave erano **già** nei commit precedenti;
non sono state rigiocate o contate come nuove correzioni. La checkout
integratrice rimane la sola branch `integrate/dp-20261014-all-lanes`;
`origin/main` del prodotto non è stato toccato.

**DP-517 verificato di nuovo sulla source esistente:** il test di origine
OIDC esatta PASS, cinque varianti ostili (`unrelated.it`, lookalike, suffisso
host, `www`, `:443`) e la callback positiva sono coperte; la suite di
account, web boundary, privacy e public API è **107/107 PASS**, Ruff e
`git diff --check` PASS. Il runbook
[`account-oidc-activation.md`](../release/account-oidc-activation.md) ora
spiega le tre classi di abuso, l'origine strettamente registrata e i limiti
del test locale. Il solo commit documentale è
`a302cd896ab647a6f34247b18190e8f80a594a82`, pubblicato e riletto.
**AC-517.1–7 restano tutti OPEN**: Google Cloud reale, controller/legal,
consenso, retention, proxy HTTPS/MiniPC e UX fisica non attestati.

| Ticket | Commit remoto della quarta wave | Difetto con RED→GREEN e prova locale | Stato originale |
| --- | --- | --- | --- |
| DP-313 | `0870c48b7f84a6f08c5324237a8f4409345f4d24` | Condanna/assoluzione/archiviazione annullata poteva apparire come stato corrente: ora `STATUS_REVERSAL_UNRESOLVED/HOLD`; 88/88 test mirati e adiacenti PASS | AC-313.1–6 OPEN |
| DP-318 | `5ad4bf4810d0dcb0f83f829083187f72c4946359` | Un solo span immutabile assegnato a due persone o alias nello stesso giorno poteva generare agreement/reaffirmation; ora `IDENTICAL_SOURCE_SPAN_REUSED/HOLD`; 98/98 suite allargata PASS | AC-318.1–5 OPEN |
| DP-438 | `2b2880e6dbe2eef34d282f6ac38119516f416c20` | Approvazione storica Person riutilizzata per altra Person o ruolo pubblicabile; ownership lungo tutta la cronologia, 107/107 adiacenti e benchmark 5/5 PASS | AC-438.1–6 OPEN |
| DP-317 | `f126d00eccce34a2aa8f186f19dbb5dabd18f954` | Traduzione editoriale con solo `STORE_BODY` risultava coerente senza diritto `TRANSLATE`; ora blocco esplicito, 50/50 rights/quote/revocation PASS | AC-317.1–6 OPEN |
| DP-439 | `3f090b9e1d0514e6ff820ac7ee856068dfbdd30f` | Falsa riammissione post-`REVOKED` cambiando `membership_id` o retrodatando `reviewed_at`; lineage e tempo fail closed, 106/106 adiacenti PASS | AC-439.1–7 OPEN |
| DP-435 | `91b1783654b69888196b509bab71c19dc1aaf1ce` | Placeholder persona `UNKNOWN`/`person:unresolved` poteva arrivare nello Statement pubblico v3 con cinque gate formalmente coerenti; ora escluso, 45/45 schema/proiezione PASS | AC-435.1–5 OPEN |

Ogni consegna è stata preceduta da un fallimento RED riprodotto, poi
corretta e rieseguita GREEN. Le sei pubblicazioni Git sono state serializzate
dal **solo prime**, con staging esclusivo dei path del ticket,
`git diff --cached --check`, push e readback `ls-remote` della SHA esatta;
i worker CoS hanno consegnato diff e prove con **NO_GIT**. Le acceptance
originali rimangono `IN PROGRESS`, perché sorgente sintetica, review/cattura
non attestate, legge/diritti, vera UI pubblica e MiniPC/CDN richiedono prove
e autorità separate. Per DP-318, DP-438 e DP-439 il check globale Ruff di
formattazione presenta debito già presente nella baseline: lint Ruff sui
diff PASS, nessuna riscrittura cosmetica massiva o dichiarazione di formatter
verde è stata effettuata.

**Documenti e superfici verificate:** il censimento
[`2026-10-14-dp02-declarations-inventory.md`](2026-10-14-dp02-declarations-inventory.md)
ha una prova ripetuta di **117/117 link Markdown relativi esistenti** in sei
file (inclusi 68 nel suo crosswalk SOP/Skills/Rules/Operations/handoff).
Una nuova scansione, successiva all'aggiunta dei link della quarta wave,
conferma **124/124 link relativi e zero path mancanti** sui medesimi sei
documenti: 68 nel censimento, 4 nella ricevuta, 7 nel post-handoff,
44 in HANDOFF, 1 nel runbook operatore e 0 nel runbook account. Sono verifiche
dei file sorgente, non HTTP live né autorizzazioni legali o editoriali.
Metodo, Correzioni, Dati/API e Progetto esistono come source route;
Privacy, Termini, Contatti e Contribuisci non esistono ancora nel tree
`web/src/pages/` e **non** possono essere dichiarate approvate o pubblicate
senza owner e consulente qualificato. La demo Astro noindex non è una
proiezione editoriale autorizzata.

**Gate finali della wave:** `python3 tools/check_launch_preflight.py
--expect-no-go` restituisce `NO-GO/49` (16 decisioni legali Q-306 non
concluse, 4 artefatti release mancanti e 29 ticket di lancio non DONE).
Il reporter restituisce **162 total / 90 DONE / 52 IN PROGRESS / 6 BLOCKED /
14 FUTURE / 72 non DONE / ready=0**, `PLAN.md` coerente. Il ramo resta
soggetto a `PR_HELD_AUTOREVIEW_BILLING_GUARD`; PR/CI backend+web completa,
manual AT, rights, pilot e deploy non sono sostituibili dai test di fixture.

**CI Github sul source della quarta wave** `91b1783654b69888196b509bab71c19dc1aaf1ce`:
run `38600359003` `completed/success`, ma **solo** `repository contract`
è `success`; `web static frontend`, `backend matrix` e `detached clean-clone`
sono `skipped`. Le vere prove frontend locali sullo stesso codice sono Astro
check **0 errori / 0 warning / 1 hint**, demo noindex controllata 34 pagine,
search, Statement, parity, routes canoniche 8/8, projection-boundary,
accessibilità automatica 8/8, quality, trust e corrections tutti PASS.
La build di produzione priva di `DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH`
è giustamente **HELD**, non va dichiarata PASS per aver usato la demo opt-in.
Il readback finale del bundle autorizzato, VoiceOver/device e la CI PR
rimangono prove autonome non eseguite.

**Pubblicazione della risposta Ops:** mentre le altre lane avanzavano la
propria checkout, `origin/main` ControlCenter si è attestato a `fd7aef3`;
da quella base il writer DP02 ha committato **il solo file**
`297-handoff-restart-20261012/02-dichiarazioni-pubbliche.response.md`, commit
`685a04e74878516f30edeb7e4b8720d68c1c012a`, push regolare e
`git ls-remote origin refs/heads/main` identico. I WIP non owned (lane
01/05/305, fleet, Hermes, DStack) non sono stati staged, resettati o
modificati dalla lane02. Questo è un receipt documentale Ops, non una
promozione del codice DP `main`.

**Gate full-suite obbligatorio sul codice `91b1783654b69888196b509bab71c19dc1aaf1ce`: NON SUPERATO.**
La vera esecuzione `PYTHONPATH=poc python3 -B -m unittest discover -s tests -q`
ha eseguito **3.661 test in 826,816 s**, exit **1**, con **una failure**:
`tests.test_dp238_born_digital_pdf.BornDigitalPdfTests.test_real_two_page_pdf_roundtrip_and_explicit_unreviewed_fidelity`
ha restituito `FAILED / DOCUMENT_PDF_WORKER_UNAVAILABLE` mentre il test
chiedeva `SUCCEEDED`. Log originale preservato:
`/tmp/dp02-wave4-final-full-20261014.log`. Nessun altro test è indicato
come FAIL/ERROR. Non è lecito chiamare questa esecuzione 3661/3661 PASS.
La stessa suite DP-238 rilanciata subito **isolatamente** è risultata
**11/11 PASS**, e il retest con adiacenti estrazione-documento è risultato
**22/22 PASS**, exit0 in 4,457 s; Ruff parser/test e `git diff --check`
PASS. Il PDF worker ha una deadline di 5 secondi e fallisce **chiuso** in
caso di subprocess non disponibile/timeout. In assenza di diagnostica del
subprocess nella prova fallita, il sovraccarico host è un'ipotesi, **non una
causa accertata**. Non sono stati aumentati i limiti o nascosti test per
ottenere un falso verde. Il gate richiede una nuova suite integrale verde
sullo SHA candidato in ambiente sufficientemente isolato e, se il problema
si ripete, diagnosi deterministica e fix con RED→GREEN. Questo NO-GO tecnico
si aggiunge ai 49 vincoli di launch preflight, senza sostituirli.

**Addendum definitivo Ops sotto lease esclusiva:** dal checkpoint Ops
`8aa5f0d36a55f65b7a1cc3c43fca9dbee1b927c4` il solo file
`02-dichiarazioni-pubbliche.response.md` è stato aggiornato con il risultato
full-suite e retest realmente misurati al commit
`c49809baada076fcb4f6a88ea9f8e82adb9a3a59` su `main` Ops;
`ls-remote` ha letto lo stesso SHA. I WIP 01/05/305 e di Core07/fleet sono
rimasti intatti. La lease concessa dal writer Core07 è stata **rilasciata
esplicitamente**; ulteriori scritture Ops necessitano una nuova lease.


## Terza wave, codice DP `186ef17`, risposta ControlCenter Ops pubblicata

**Readback finale ControlCenter Ops:** dopo il primo commit packet 297
`3cfb3c4`, l'addendum della sola risposta DP02 è stato pubblicato
su `origin/main` con SHA `65dafd8ecb31b45889d2dc90fbdb63dd81d7d1c2`,
verificato identico al checkout. Altri WIP Ops (prompt 01/05 e documenti
305) restano deliberatamente unstaged/unchanged. Nessuna accettazione
editoriale o rilascio pubblico deriva da questo commit documentale.

| Ticket | Commit remoto integratore | Difetto riprodotto e prova |
| --- | --- | --- |
| DP-517 | `df4c0ee1f102c62913a2c96e24ebec1f5f4e9c9c` | Account OIDC accettava origine HTTPS `.it` estranea/lookalike al callback registrato; dominio esatto ammesso, 107/107 account/web/privacy test PASS, Ruff PASS. Login Google reale e legale ancora OPEN. |
| DP-516 | `a595450ee4b8560ff190c2960484d977bdf3f225` | Rami di backfill già completati/deduplicati accettavano current rights receipt con CR/LF, padding o overlength; quattro RED→GREEN, 55/55 test planner, SQLite, PostgreSQL e DP243 PASS, Ruff/format PASS. Diritti veri, pilot e MiniPC aperti. |
| DP-243 | `e9afd0ec5c847b0ff4a859895961d14e77624587` | Traduzione/copia d'archivio da originale HELD poteva diventare PRIVATE_REVIEW_ONLY; parent source/role/locator/rights ora trasferiscono `PARENT_SOURCE_UNVERIFIED`; 51/51 DP243/516 PASS. Fonte primaria autentica e review aperte. |
| DP-515 | `186ef17e59fe73cab061a5301ffbe0d9f5443721` | HTTP 200 con bytes/versione diversi e Last-Modified più vecchio poteva fare rollback del source head confermato; ora `UNAVAILABLE/LAST_MODIFIED_REGRESSED`, backoff/review privati, zero figli, 70/70 test mirati/adiacenti PASS. Originali AC runtime/rights aperti. |

I quattro commit sono in un unico branch `integrate/dp-20261014-all-lanes`,
con staging dei soli path owned, `git diff --cached --check`, push e
`git ls-remote` corrispondenti. `origin/main` DP resta al checkpoint
protetto `33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`, senza PR.
La run GitHub `38596675716` su `186ef17` è `completed/success` soltanto
per `repository contract`; backend matrix, frontend e clean-clone sono
`skipped` secondo il workflow branch, non un accettato CI/PR.

La risposta di lane è **pubblicata su ControlCenter Ops `main`**:
commit `3cfb3c433d79fd1dc4f7c543e5dae1263700303f`, SHA di `origin/main`
verificato identico, soltanto
`297-handoff-restart-20261012/{02-dichiarazioni-pubbliche.prompt.md,02-dichiarazioni-pubbliche.response.md,README.md}`;
WIP concorrenti delle lane 01/05/305 preservati nel checkout Ops. Il
[censimento delle dichiarazioni](2026-10-14-dp02-declarations-inventory.md)
contiene 68 link validati fra route, SOP/Skills/Rules/Operations e packet
297. Sei route informative in sorgente, ma Privacy/Termini/Contatti/
Contribuisci e revisione Q-306 non autorizzate come pagine legali pubbliche:
nessun testo o recapito personale inventato. L'archivio di dichiarazioni
reali richiede readback MiniPC/CDN/source permit separati.

I controlli già rieseguiti sul source `186ef17`: `ruff check` sui nove
source/test della wave, `git diff --check`, repository contract, privacy
inventory tecnico 1.266 campi, 47 asset licensing, fixture hashes e
version consistency PASS. Astro 0 errori/0 warning (1 hint), search,
Statement, backend parity, 8/8 accessibilità automatica, route 8/8 e
projection boundary PASS. **Preflight release NO-GO/49**: 16 quesiti Q-306
non conclusi, quattro artefatti release mancanti, 29 ticket di lancio
non DONE. Registro esatto: 162 total, 90 DONE, 52 IN PROGRESS, 6 BLOCKED,
14 FUTURE, 72 non DONE, ready=0. Manual screen reader e reale PR CI
rimangono assenti. La full suite Python finale viene attribuita soltanto
al relativo codice e all'exit code misurato, separatamente dalle 3.645
prove della seconda wave.

**Full suite finale della terza wave, codice `186ef17e59fe73cab061a5301ffbe0d9f5443721`:**
`PYTHONPATH=poc python3 -B -m unittest discover -s tests -q` ha
concluso **3.652/3.652 PASS, exit 0, 322,598 s** nel log locale
`/tmp/dp02-wave3-final-full-20261014.log`. Nessuna failure o error;
ResourceWarning SQLite/HTTP non fatali. I test includono i consumer
originari, PostgreSQL disposable e le regressioni delle quattro tranche.
Questa prova appartiene al source `186ef17`; un commit successivo
solo-documentale richiede comunque git SHA readback e repository contract.

Questa è una ricevuta **della lane 02** del packet ControlCenter
`20260929-main-release-closure/297-handoff-restart-20261012`, non un nuovo
backlog né un permesso di pubblicare dichiarazioni o distribuire software.
I ticket originali e `PLAN.md` governano i criteri di acceptance.

## Autorità e WIP preesistente

- Source canonica Mac Studio: `/Users/domenico/Code/DichiarazioniPubbliche.it`,
  main remoto iniziale ed effettivo letto nella ripresa
  `33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`.
- Integratore esistente: `/Users/domenico/Code/DP-20261014-all-lanes-integrator`,
  `integrate/dp-20261014-all-lanes` basato su `15fee6c2aa490743f59ff36504efd672b3197a35`,
  contenente gli undici merge delle lane precedenti. Le corsie storiche non
  sono state ricostruite, né i due checkout utili eliminati.
- Quattro worker **reali** sotto CoS run
  `15fd2ced-d33d-4160-a58a-bf685202ff54`: `worker-1` DP-514 e poi DP-512;
  `worker-2` DP-409 e poi DP-315; `worker-3` DP-429 e poi DP-410;
  `worker-4` DP-214/215 e poi DP-236/237. Ogni worker ha agito su file
  disgiunti; per commit/index/ref è stata assegnata una lease esclusiva
  breve, confermata rilasciata tra i writer.

## Tranche pubblicate nel branch integratore

| Ticket | Commit integratore | Modifica e prova di regressione |
| --- | --- | --- |
| DP-409 | `7930035388de0e0b46388187408ff78b8e7c8c53` | v3 recente ordina su `statement_date`; protezione da `archive_added_at`/`declared_at` non attestate, ricerca/Statement e 20 test Python PASS; decisione archive ancora owner |
| DP-214/215 | `4d89005424ed6da6f496300d28a91d31e595d160` | Source Intelligence esige tutte le 5 dimensioni del FIELD_MATCH e non conserva IDs di evidenza non qualificante; RED→GREEN, 77 source + 120 security/source + 27 consumer/PG, benchmark 5/5 |
| DP-514 | `3afb1968f8e37674ce8438e53a82097c1810ae24` | overhead LLVM-JIT cold-plan misurato su PostgreSQL temporaneo Linux; `SET LOCAL jit=off` limitato alla transazione snapshot READ ONLY; 34/34 locale e Linux, 141/141 cost policy; causa completa CI 57014 ancora aperta |
| DP-429 | `1713486b7eedaf31257d78902a962e8426d59314` | focus ripristinato dopo reset; Chrome reale RED→GREEN, suggerimenti opt-in e query/filtri/URL originali conservati su desktop/640/375 e zoom 200% |
| DP-410 | `644e75a8c6f8e8e3e81406b2364c8c16ac36896c` | date originali fonti come `<time datetime>`; test RED→GREEN sul build demo Astro noindex, Astro check senza errori |
| DP-315 | `2cd783d00915c5210d710994e6380005cc6c5010` | input di negazioni congelato in dataclass validati prima di receipt e decisione; attacco REVOKED→CURRENT/quoted→ASSERTION RED→GREEN, 18+35 test e benchmark 5/5 |
| DP-236 | `7e139d0c9929695d807a5c88e5e62d7af9da5ad3` | `attribution_requirements` malformato non può concedere FETCH, requisiti mutati cambiano fingerprint della decisione; 59/59 + 69/69 test rights/locator/PG; DP-237 ricognizione NO_CHANGE |
| DP-512 | `2b55fa74bc03b72b63ab756a1c9bd2857ad5bceb` | ricevuta PostgreSQL non fidata con `local_energy_basis` arbitrario poteva trapelare dal risultato classificato; whitelist `UNKNOWN/ESTIMATED/MEASURED` e fallback sicuro, 33/33 prove fresche e 101/101 matrice precedente |
| DP-303 consumer | `d10ef72acae2505811abf3929c4cd4a6bf174937` | Canary reale verifica→correzione→ri-analisi→proiezione corretto con le cinque dimensioni del claim approvato; produzione DP-215 fail-closed invariata; RED→GREEN e 111/111 test adiacenti |
| DP-238 | `8815c8fe4bd6b0f4df2331259f0bc273495287b1` | Child subprocess PDF `python -m` ora trova il proprio package anche da cwd estranea e `PYTHONPATH` vuoto; RED→GREEN, 22/22 test PDF/documento e 6/6 parallel readers; deadline/resource caps originali invariati |
| DP-240 | `0da37940007da3ac9346c29867c50b947daf1e6d` | Rifiuto di `partition_id` scambiato tra due persone/content anche dopo checksum del piano ricalcolato; regressioni pure+SQLite RED→GREEN, 77/77 DP240/private candidates/Studio |
| DP-241 | `a63fe1330e6de73f03ebe8a9341d2c5f0abe6573` | Guard di recupero fonti su diritti del Content esatto e locator `PASSAGE` originale; mismatch rights leaf Content/locator RED→GREEN su PostgreSQL, 93/93 DP241/319 e 12/12 adiacenti |

### Seconda wave indipendente — nuove prove conseguenziali

| Ticket | Commit integratore remoto | Prova delimitata |
| --- | --- | --- |
| DP-242 | `0cee79d310cdbc78e53c6000914ce1eddb1b8b7c` | Preflight Studio rifiuta flag `segment_publication_blocked` omesso o pseudo-booleano (1, 0, stringhe): solo `None` osservato o `False` letterale è ammissibile come sorgente; 70/70 test DP242/DP240/Studio/discovery PASS |
| DP-244 | `0c7ee204c5eb4e5a290ddbea70279115df39d351` | Prima osservazione `CHANGED` senza baseline derivata revisionata non può dichiarare copertura corrente né emettere freshness descriptor; preservati i casi `UNCHANGED` legittimi; 17/17 mirati e 93/93 adiacenti PASS |
| DP-519 | `323deef771ff73c2d66fc04a6555116a6bde970e` | `WITHDRAWAL_PENDING_EXTERNAL_READBACK` anziano compare nell'arretrato reale; `NO_IMAGE_SELECTED` e immagine opzionale scaduta restano esclusi; 62/62 visual/SQLite/PostgreSQL/HTTP/Studio PASS |
| DP-518 | `bb00177a6138014cb66e627b61faf637c23f9df3` | Audit locale di release rifiuta vecchi HTML/JSON non inventariati, symlink e errori di scansione, limite 10.000 entry; tollera asset statici dichiarati; 50/50 test DP518/DP320 PASS |

Ogni finding è stato provato **RED prima del fix** e GREEN dopo, con Ruff,
compilazione e `git diff --check` sui file posseduti. Le quattro tranche
sono commit disgiunti e pubblicati con readback `git ls-remote` esatto; la
nuova source HEAD `bb00177a6138014cb66e627b61faf637c23f9df3` non è un
merge `main`. DP-242/244/518/519 mantengono tutti gli AC originali
**IN PROGRESS**: non esiste prova con fonti/autorizzazioni autentiche,
attestazione B, operatori qualificati, MiniPC o CDN. Il controllo locale
DP-518 non certifica il contenuto degli asset JavaScript di build tollerati
né l'assenza di cache esterne; l'accettazione HTTP/CDN rimane separata.

Ogni commit elencato è stato pubblicato **sullo stesso ramo remoto** con
readback effettivo della SHA, senza staging globale o sostituzione dei diff
altrui. Le ricevute per-ticket dettagliano le fixture, i confini e le AC
ancora mancanti. Le prove sintetiche non autorizzano una fonte reale.

Il [censimento puntuale delle dichiarazioni e delle pagine pubbliche](2026-10-14-dp02-declarations-inventory.md)
verifica i sei percorsi informativi e le schede prodotto nel codice sorgente,
e collega SOP operative, skill agenti, rules di governance e operazioni al
packet ControlCenter 297. In particolare le route pubbliche Privacy, Termini,
Contatti e Contribuisci non esistono nella checkout esaminata; Q-306 conta
14 decisioni `OPEN` e 2 `BLOCKED`, nessuna approvazione legale sostituibile
da un template o da un indice sintetico. Il conteggio di dichiarazioni
**realmente pubblicate** richiede un readback autorizzato MiniPC/reader,
che non è stato acquisito in questa wave.

Il readback successivo a DP-241 ha confrontato `git ls-remote origin
refs/heads/integrate/dp-20261014-all-lanes` con `HEAD` a
`a63fe1330e6de73f03ebe8a9341d2c5f0abe6573`, mentre `origin/main`
è rimasto `33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`. Il ramo
avanzerà con gli ultimi diff e con il commit documentale della ricevuta:
verificarne SHA finale. I commit intermedi sono tutti recuperabili nel
medesimo ramo remoto; ogni tranche contiene soltanto i percorsi dichiarati.

L'ulteriore prova sulla checkout integrata dopo DP-512 (3.632 test) aveva
**8 failure PDF `DOCUMENT_PDF_WORKER_UNAVAILABLE` e 1 errore canary DP-303**:
questo non era un full PASS. DP-303 è stato riprodotto e corretto con un
fixture positivo che esplicita le 5 dimensioni di Source Intelligence,
111/111 test adiacenti verdi. DP-238 ha poi riprodotto e corretto un caso
indipendente in cui `python -m` falliva con cwd estranea e `PYTHONPATH`
svuotato, 22/22 test PDF/testo verdi; il trigger preciso di tutte le otto
failure precedenti richiede ancora la riesecuzione completa sul codice finale.

**Suite finale sul codice `a63fe1330e6de73f03ebe8a9341d2c5f0abe6573`:**
`PYTHONPATH=poc python3 -B -m unittest discover -s tests -q` ha
concluso **3.637/3.637 PASS, exit 0, 520,154 s**, senza errori né failure.
La suite include i casi DP-303 e DP-238 prima falliti. Sono comparsi
`ResourceWarning` SQLite non fatali. Le prove dei singoli diff RED→GREEN
restano nei rispettivi ticket; la causa ambientale precisa dell'intera
precedente failure PDF non è attribuita retroattivamente a un solo fattore.

## CI, review e release

Il readback puntuale `gh run view 38561882494` (`15fee6c`) e
`38561730777` (`0228fa8`) conferma **`repository contract: success`**,
mentre le tre altre famiglie di job (backend matrix, web static, detached
clean-clone) erano **`skipped`**. Il workflow riserva queste tre ai push
`main` e alle PR; il badge globale `success` di questi branch push non
equivale a una CI completa. La precedente suite post-fix
**3.624/3.624 PASS** è prova locale sul codice di `0228fa8`, non su ogni
successivo codice di questa wave.

**CI source del commit precedente alla seconda wave:** GitHub Actions run `38587368015` su
`a63fe1330e6de73f03ebe8a9341d2c5f0abe6573` è `completed/success`:
`repository contract=success`, mentre backend matrix, web static e detached
clean-clone sono `skipped` sui branch push. Non è una CI PR né autorizzazione
al merge. In locale, Astro check ha 0 errori/0 warning (1 hint), ricerca,
Statement, parity, routes, projection-boundary e 8/8 check di accessibilità
automatici PASS; resta la prova manuale con screen reader e dispositivo.
I controlli repository, inventario privacy, asset/licenze, fixture, versioni,
Ruff sui sorgenti/test modificati e `git diff --check` sono PASS.

**Readback seconda wave (SHA `bb00177`):** GitHub Actions run
`38593285587`, `completed/success` con `repository contract=success`;
backend matrix, web static e detached clean-clone **`skipped`**. Il browser
GitHub non sta provando la suite completa di PR.

**Full suite definitiva, codice `bb00177a6138014cb66e627b61faf637c23f9df3`:**
`PYTHONPATH=poc python3 -B -m unittest discover -s tests -q`
**3.645/3.645 PASS, exit 0, 362,131 s**, test reali PostgreSQL disposable,
SQLite, prodotto/consumer e ripristino; log locale
`/tmp/dp02-wave2-full-20261014.log`. I `ResourceWarning` SQLite/HTTP
non fatali non costituiscono prove di accesso MiniPC/live. Il run completo
precedente da 3.637/3.637 resta attribuito al suo diverso source SHA
`a63fe133`.

**Controlli integrativi sul codice `bb00177`:** repository contract,
inventario privacy tecnico, hash e 47 asset licenze, fixture inventory,
version consistency, `ruff check` sugli otto file Python source/test della
wave e `git diff --check` PASS. `ruff format --check` non è verde su quattro
file (`coverage_catalog_v1.py`, `distributed_withdrawal_audit_v1.py`, e
rispettivi test DP244/DP518): gli stessi quattro file della baseline
`5f9cb1f` fallivano già il check formatter; la differenza del format mostra
molte righe preesistenti. Non è stata eseguita una riscrittura massiva fuori
dal fix; registrare questo debito cosmetico distinto dal lint, dai test e
dall'accettazione prodotto.

Il follow-up Ruff di DP-314 è già incluso dalla baseline `0228fa8`; il
verificatore generalista originale conserva **AC-314.1–.6 aperti** per
vincoli di fonti, decisioni, challenger, autorità e MiniPC. Nessun nuovo
checkmark è giustificato soltanto da un import Ruff o dalla suite verde.

**Coordinamento writer:** il commit DP-240 `0da3794` è stato eseguito una
sola volta dal prime mentre un'istruzione di lease ritardata raggiungeva
worker-1. Il worker ha verificato la SHA, evitato un commit duplicato e
rilasciato la lease. Per DP-241 il prime ha revocato il messaggio pendente,
worker-6 ha confermato `NO_GIT` e il prime ha pubblicato un solo commit.
Gli altri working diff sono stati preservati; per ulteriori tranche è
necessaria una lease **effettivamente ricevuta** prima delle mutazioni Git.

L'account ChatGPT esplorato su `settings/code-review` mostra nessun repository
GitHub connesso: non dimostra che l'identità effettivamente collegata alle
review automatiche abbia `Automatic review=OFF` a livello personale e
override repo. Conservare il gate **`PR_HELD_AUTOREVIEW_BILLING_GUARD`**;
non aprire PR né effettuare push diretto su `main` per bypassarlo. Dopo lo
sblocco verificato, PR con 11 check richiesti, review di diff+AC,
`check_pr_merge_gate.py`, rights/editoriale e acceptance pertinente,
poi merge e readback esatto di `origin/main`; deploy MiniPC, reader/CDN e
accessibilità fisica sono verifiche separate.

## Acceptance ancora reali

Il reporter nella ripresa ha restituito **162 total / 90 DONE / 52 IN
PROGRESS / 6 BLOCKED / 14 FUTURE / 72 non DONE**, PLAN/file coerenti.
Nessuna delle implementazioni sopra giustifica nuovi checkmark che richiedono
source-use/diritti per la specifica esposizione, pilot DP-443 autentico,
100 Content Garlasco reviewati (baseline PAUSED 18/100), fact-check qualificato,
source/rights/license, decisione sull'evento `archive_added_at`, Gold,
VoiceOver/device fisico, test PostgreSQL MiniPC non disposable, HTTP/CDN
revocation, billing EUR/invoice/FX/quote o preview manuale. La release resta
**NO-GO**. I ticket `IN PROGRESS` restano tali e il programma non è concluso.

Il documento locale di raccordo ControlCenter della lane è
`/Users/domenico/ControlCenter/src/controlcenter-ops/tasks/20260929-main-release-closure/297-handoff-restart-20261012/02-dichiarazioni-pubbliche.response.md`;
il repository Ops è condiviso con altre lane e richiede una propria lease
esclusiva per commit e `origin/main`.

## LANE 02 · WAVE 001 · 2026-10-15 08:02 CEST (+02:00) · BLOCKED / WAIT_OWNER

**Esito e significato:** una tranche CoS conclusa come ricognizione finale
dei prerequisiti e review locale; zero delle quattro implementazioni
originali era ammissibile con input nuovi. Nessuna implementazione sorgente,
installazione, chiusura originale, approvazione, pubblicazione o attivazione
è stata simulata. La wave non apre una nuova coda di audit.

### Ticket originali, acceptance e responsabili

| Originale | Prima → dopo | Prova fresca 15/10 e AC autentiche | Residuo, responsabile e condizione osservabile |
|---|---|---|---|
| **DP-312** | IN PROGRESS → IN PROGRESS | `docs/tickets/DP-312-speech-act-context.md` AC-312.1–6 tuttora non spuntate; diff di `poc/dichiarazioni_pubbliche/context_integrity.py` sul ramo conferma riparazione lessicale quote CJK, non Gold indipendente. `python3 tools/report_ticket_status.py --json` concorde. Nessuna AC nuova provata. | **EXTERNAL/PENDING-OWNER**: responsabili source/rights, Gold DP-321, runtime. Acquisire contrast set annotato license-safe IT/DE/terza lingua realmente osservata con selector e identity review, replay/invalidation source-bound e capture MiniPC autorizzata. Il comando falsificante dopo lo sblocco è una replay suite su quella fonte/versione e relativi consumer, non altre fixture lessicali. |
| **DP-517** | FUTURE → FUTURE | `docs/tickets/DP-517-reader-google-login.md` AC-517.1–7 aperte; `ssh minipc` mostra `public_account.py=absent`; `curl` GET `https://dichiarazionipubbliche.it/account/api/session` = **HTTP 404** (endpoint canonico, senza conclusioni sul proxy). Nessuna AC nuova provata. | **PENDING-OWNER/EXTERNAL**: owner, privacy/legal, amministratore Google OAuth, operator MiniPC e reviewer AT. Grant scritto retention/backup-erasure e test identity, client Google con callback esatto `https://dichiarazionipubbliche.it/account/oauth/callback`, installazione reversibile consentita. Solo poi eseguire signup→relogin→logout→delete tutte le sessioni, negativi OIDC/CSRF/PII/cache, permessi/WAL/rollback su MiniPC+origin. Login resta spento. |
| **DP-515** | IN PROGRESS → IN PROGRESS | `docs/tickets/DP-515-source-incremental-monitoring.md` AC-515.1–7 non spuntate. `ssh minipc` conferma `incremental_source_watch.py=absent` e `source_watch_store_v1.py=absent`; la prova precedente distingue correttamente i timer polling legacy attivi dal consumer opt-in. Nessuna AC nuova provata. | **EXTERNAL/PENDING-OWNER**: diritti revalidation fonte-esatta, ricevute autentiche DP-514/budget EUR, integrazione lease/CAS e PostgreSQL canonico con queue/DP-511/510 sotto assegnazione esplicita, operator MiniPC/canary. Dopo tali input falsificare unchanged/no-duplicate e changed/restart/concorrenza/revoca/freshness su canary isolata. Non toccare timer legacy o DB live. |
| **DP-405** | IN PROGRESS → IN PROGRESS | `docs/tickets/DP-405-person-record-ui.md` mantiene AC-405.3 e .6 aperte. Route `web/src/pages/persone/[slug].astro` ancora dossier-v2-derived; il componente v3 con fixture zero non è route positiva approvata. Nessuna AC nuova provata. | **PENDING-OWNER/MANUAL**: DP-438 owner/editoriale deve autorizzare Person first-class **zero Statement** con pin immutabile di proiezione e cutover; operator MiniPC deve attestare HTML e negativo 404 per private/unknown; reviewer fisico deve passare screen-reader, keyboard, contrast e zoom per AC-405.6 indipendentemente. Non inventare Persona. |
| **DP-429** (gate coordinatore, non quinto posto) | IN PROGRESS → IN PROGRESS | `docs/tickets/DP-429-explore-page-v4.md`: prove storiche Chrome keyboard/AX/zoom non sono VoiceOver umano; AC mista resta non spuntata. Nessun retest invariato. | **MANUAL**: reviewer AT esegua un solo scenario `/esplora/` su build e pin esatti approvati: annuncio contatore, tipo Persone/Temi, filtri, history Back, modal focus/return e 200% senza perdita stato. Conservare riscontro anche negativo, senza chiamarlo pass automatico. |

**Totali e classificazione:** prima = dopo **162** originali, **90 DONE,
52 IN PROGRESS, 6 BLOCKED, 14 FUTURE, 72 non DONE, READY=0**;
`files_agree_with_plan=true`. **Ticket integralmente chiusi: 0**;
AC originali aggiuntive verificate: **0**; source fix nuove: **0**. Il
`python3 tools/check_launch_preflight.py --expect-no-go` emette
`NO-GO/49`, receipt
`96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f`:
16 Q-306, 4 artefatti release assenti, 29 gate di ticket; non 49 nuovi ticket
e nessun doppio conteggio con Core07.

### Quattro posti nativi e lavoro coordinatore

`mcp__Chat_On_Steroids_Core__agents(status)`: nessun worker di questa
sessione, **4 slot liberi**. **Avviati 0/4, primi turni 0,
identificativi/modello/effort N/A**; non si è cambiata alcuna selezione
GPT-6/high/provider. Sono rimasti PENDING, nell'ordine, posto 1 DP-312
(`context_integrity.py`/test/ticket), posto 2 DP-517
(`public_account.py`, `public_api.py` solo su lease, runbook/test),
posto 3 DP-515 (`incremental_source_watch.py`,
`source_watch_store_v1.py`, test/ticket), posto 4 DP-405 (route Astro,
`PersonRecord.astro` e test/ticket). **No dispatch**, poiché nessuno
aveva un cambiamento osservabile nei prerequisiti che autorizzasse un
intervento originale; quattro worker avviati per ripetere hardening o test
invariati sarebbero una falsa ammissione. Nessun worker, lease runtime,
processo o risultato è rimasto non assestato.

Il coordinatore ha letto contratti home/shared/repo, fonti canoniche,
ticket e receipt della lane. Ha verificato `main...HEAD`, hash del
diff `509719de706d10885e7a93b39e02b0a13fc717d9ba65ab18674aca7270f63032`,
overlay tracked/untracked **vuoto**, e condotto i due assi locali della
skill `~/.codex/skills/code-review/SKILL.md`: **Standards** sui seam
Python letti e invarianti fail-closed; **Spec** sul crosswalk AC e sui
receipt esistenti. Scope effettivamente ispezionato: elenco/statistica
del diff `main...HEAD` (**162 file, +18.181/−221**), diff sorgente
`context_integrity.py`, `incremental_source_watch.py`,
`public_account.py`, `public_api.py`, commit documentale
`8ebb12e..576472b`, quattro ticket originali, DP-429 e DP-438,
runbook/account, HANDOFF, consolidamento e PLAN. **Nessun finding
conseguenziale riproducibile** in questo perimetro, **nessun PASS
indipendente sull'intero diff** da rivendicare.

### Git, PR, CI, pin e verifiche

- Integratore esistente `/Users/domenico/Code/DP-20261014-all-lanes-integrator`,
  `integrate/dp-20261014-all-lanes`; HEAD e remoto al checkpoint
  **`576472b384647e2c300f1d19eb11378ce42844d7`**, avanzato
  esclusivamente da `8ebb12e` per `PLAN.md` documentale, non per nuovi
  sorgenti. Canonical `/Users/domenico/Code/DichiarazioniPubbliche.it`
  `main == origin/main` **`33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`**.
  `git status --porcelain=v1` vuoto; due worktree puliti, zero stash,
  11 merge storici preservati. Nessuna nuova versione installata.
- `python3 tools/check_repository_contract.py` **PASS**;
  `git diff --check main...HEAD` **PASS**;
  `python3 ~/.dstack/scripts/verify_main_delivery.py --repo
  /Users/domenico/Code/DP-20261014-all-lanes-integrator --review-check`
  **REMOTE_BRANCH_SAVED** sullo SHA sopra, **PR_CI_MANUAL=NOT_VERIFIED**.
  Nessuna suite Python o web ripetuta, dato che nessun codice/runtime
  è cambiato in questa wave; 3674/3674 full rimane prova storica sul
  diverso sigillo `db03d51`.
- `gh pr list --state open` e `gh api repos/.../pulls` = **0 PR**.
  GitHub Actions `38688636967` su `576472b` è `completed/success`
  solo `repository contract`; backend matrix, web static e detached clone
  **SKIPPED**. Non è gate di merge né pass runtime.
- **`PR_HELD_AUTOREVIEW_BILLING_GUARD`**: la capacità browser CoS
  per confermare l'identità GitHub-linked ha risposto
  `BROWSER_NOT_DISPATCHED`; l'owner ha attestato OFF in passato,
  ma non esiste qui readback provider personale **e** override repository
  dello stesso account. Stato `EXTERNAL_AUTOREVIEW_SETTING_UNVERIFIED`.
  Nessuna PR creata, nessuna review a consumo/automatica, `@codex review`,
  merge o push diretto a main. `check_pr_merge_gate.py` non applicabile
  in assenza di PR; quando ammessa serviranno SHA esatto, CI PR completa,
  review/thread paginati, test e gate prima di un merge.
- MiniPC letto via SSH alias canonico `minipc` (host `udodo`),
  contratto host e repo verificati, mirror non-Git `VERSION=0.0.1`;
  moduli opt-in account/watch assenti; `/account/api/session` origine
  **404**. Nessuna scrittura su MiniPC/DB, no source rights/capture,
  budget provider, download massivo, deploy o pubblicazione. Non
  riesaminati pin installati che questa wave non ha modificato.

**File owned in questa wave:** soltanto `PLAN.md` Active workflow e
questa stessa ricevuta. Il loro commit documentale e il readback remoto
successivi vanno verificati come SHA branch di consegna, senza spacciare
il checkpoint sorgente per merge/main o prova live. Nessuna lease
ControlCenter/Core07 disponibile: la copia esatta
`310-prompt-to-prompt-20261015/02-WAVE-001-COS.response.md`
**non è stata scritta** nel repository Ops condiviso.
**Owner Core07:** ottenere lease Ops concreta, trascrivere questa
sezione integralmente come file di trasporto, commit/push/readback Ops
senza sovrascrivere WIP concorrente. La ricevuta canonica prodotto
e la risposta in chat consentono il recupero.

**WAIT_OWNER (una domanda manuale specifica):** qual è il **URL e pin/hash
della build approvata** di `/esplora/` su cui un reviewer umano può
eseguire la prova VoiceOver DP-429 (filtro, annuncio conteggi, ritorno focus
e cronologia), conservando esito PASS/FAIL? Fino a questa e alle altre
condizioni elencate, nessuna nuova audit wave, PR, main merge o release.

## LANE 02 · WAVE 001 · Continuazione owner 15/10/2026 08:36 CEST · PARTIAL / NO-GO

**Mandato aggiornato:** l'owner ha richiesto quattro subagenti nativi con
ticket differenti e implementazione A→Z, più file di risposta aggiornato.
L'esito precedente BLOCKED/0 worker riportato sopra è una fotografia della
tranche precedente, non il nuovo esito. Sono stati richiesti **quattro inviti**
CoS e sono stati verificati **tre veri primi turni**; un quarto startup è
fallito per backpressure nativa e la verticale è stata assunta dal coordinatore.
Tre difetti locali reali sono stati riprodotti RED→GREEN, integrati e
pubblicati senza trasformarli in acceptance reale di produzione.

### Quattro posti originali e settlement

| Posto | Agente nativo / primo turno / modello | Owned e risultato verificato | Settlement / limiti |
|---|---|---|---|
| **DP-312** | `worker-1`, primo turno acquisito, `gpt-6-thinking` high | `context_integrity.py`, `tests/test_dp312_speech_act.py`, ticket. Cinque false attribuzioni EN/DE (`none/neither/nobody`, `weder/niemand`) erano `ASSERTION/ENDORSE`; RED→GREEN ora `HOLD_FOR_CONTEXT/UNKNOWN`, replay di hash e rifiuto fonte alterata. 171 test/controlli adiacenti dichiarati PASS dal worker; 33/33 unit mirati rieseguiti dal prime, benchmark 5/5. | `worker-1` ha eseguito `agents finish`, sleeping, nessuna lease Git. Commit/push `6be686c84f81da1863bde81ee47aad900ed3fb28`. **AC-312.1–6 OPEN**: source/rights, contrast set Gold, lingua osservata, original/translation, downstream invalidation e MiniPC ancora esterni. |
| **DP-517** | `worker-2`, primo turno acquisito, `gpt-6-thinking` high | `public_api.py` (lease path specifica), `tests/test_public_account.py`, ticket e runbook OIDC. HTTP reale localhost RED: GET session 401 rigenerava anche un `__Host-dp-visitor` valido, azzerando il limite 5/min. GREEN: cookie firmato preservato, sesto login nella finestra = 429. 117/117 adiacenti PASS worker; 9/9 account focali PASS prime. | Lease path `public_api.py` esplicitamente rilasciata, `worker-2` `agents finish`, sleeping. Commit/push `908b17fc4c89506ddca7616cdd16094eb7e4f1fa`. Cookie cancellato intenzionalmente apre ancora bucket nuovo; limite globale 120/min resta distinto. **AC-517.1–7 OPEN**, account remoto spento: privacy, OAuth, test identity, installazione reversibile e AT mancanti. |
| **DP-515** | `worker-3`, primo turno acquisito, `gpt-6-thinking` high | `source_watch_store_v1.py`, `tests/test_dp515_durable_watch_next.py`, ticket. Prima un `IN_FLIGHT` con gate invariato poteva bloccare un source per sempre dopo crash. Ora expiry immutabile, lease 1–86400s/default 300, CAS `BEGIN IMMEDIATE` su state/gate/source, rifiuto observation oltre deadline, restart e due writer; 53/53 focused+adjacent PASS worker e prime, Ruff e format PASS. | `worker-3` `agents finish`, sleeping. Commit/push `25c94d145f5d813bde76bdf51851ebf3b37453ab`. Store resta **solo fixture SQLite opt-in disposable**, non writer PG né scheduler produttivo. **AC-515.1–7 OPEN** per diritti, budget autentico, PG/DP-511/510, canary MiniPC e reader freshness/cache. |
| **DP-405** | `worker-4`: invito creato `gpt-6-thinking` high ma **startup FAILED** (`command queue full`); **nessun primo turno**, non contarlo; coordinatore subentra | Letti route `web/src/pages/persone/[slug].astro`, `PersonRecord.astro`, `PublicPersonArchiveV3.astro`, `publicPersonV3.ts` e test. Route reale ancora dossier-v2-derived, nessun PublicPerson DP-438 zero-record effettivamente approvato e pin indipendente: cutover non autorizzato, **NO_CHANGE** source. `node web/scripts/check-dp405-approved-empty.mjs` lanciato ma primo Astro build `spawnSync ETIMEDOUT` (limite test 60s): **non PASS**. GET HTTPS unknown Person = 404. | Non ripetuto avvio nella coda satura; nessun worker o processo DP-405 lasciato attivo. **AC-405.3/.6 OPEN**: richiedono risorsa/pin owner/editoriale, readback MiniPC e VoiceOver manuale. Nessuna biografia/record sintetico pubblicato. |

**Totale worker realmente avviati:** **3/4**; quarto invito fallito,
nessun modello/effort alternativo, nessun fallback silenzioso e nessun
worker non assestato. Il coordinatore ha integrato ogni diff con **lease Git
esclusiva prime**, stage solo path owned e push puntuali con remoto uguale
a locale. Non sono stati creati ulteriori task o wave. Il ramo contiene ora
tre commit coerenti; non sono stati reinstallati 11 merge storici.

### Crosswalk ticket, AC e prove reali

| Ticket originale | Stato prima → dopo | Criterio tecnico nuovo e comando falsificante | AC residue e owner di sblocco |
|---|---|---|---|
| DP-312 | IN PROGRESS → IN PROGRESS | Cinque quantificatori negativi in `tests/test_dp312_speech_act.py`; `PYTHONPATH=poc python3 -B -m unittest tests.test_dp312_speech_act -q` **33/33 PASS**. Risolve un false endorsement privato, NON un AC originale completo. | AC-312.1–6; owner source/rights + Gold DP-321 deve fornire fonti license-safe, contrasti annotati, pari traduzioni e replay MiniPC. |
| DP-517 | FUTURE → FUTURE | `tests.test_public_account` **9/9 PASS** prime, 117/117 adiacenti worker; localhost session401 preserving visitor/new-cookie when absent, sesto `/account/auth/google` 429. GET `https://dichiarazionipubbliche.it/account/api/session` **404**; modulo account assente sul MiniPC. | AC-517.1–7; owner/privacy/legal approva termini/erasure/backup, Google Cloud real app+test identity, operator MiniPC install/proxy e reviewer AT. |
| DP-515 | IN PROGRESS → IN PROGRESS | `PYTHONPATH=poc python3 -B -m unittest tests.test_dp515_incremental_watch tests.test_dp515_durable_watch_next tests.test_source_watcher -q` **53/53 PASS**, CAS/readback disposable. | AC-515.1–7; owner fonte/diritti, budget DP-514/operator e integration PG/queue, poi canary MiniPC e revoca/cache pubblica. |
| DP-405 | IN PROGRESS → IN PROGRESS | `web/src/pages/persone/[slug].astro` ancora v2. Test DP405 **ETIMEDOUT senza prova**; unknown HTTP 404, non route approved-zero positiva. | AC-405.3 e .6; owner DP-438 approvazione Persona+pin reale, operator release e reviewer AT fisico. |
| DP-429 (coordinatore, non quinto posto) | IN PROGRESS → IN PROGRESS | VoiceOver/screen reader reale non eseguito; keyboard/zoom automatici storici non chiudono AC mista. | MANUAL: URL+pin approvato di `/esplora/` e reviewer AT, test su contatore, filtri, history, focus e 200%. |

**Reporter originale:** 162 total / 90 DONE / 52 IN PROGRESS /
6 BLOCKED / 14 FUTURE / 72 non DONE / READY=0, file-ticket e PLAN
concordi. **Delta chiusure integrali = 0; nuovi fix tecnici = 3;
AC complete originali aggiuntive = 0**. Preflight rimane **NO-GO/49**
(16 Q-306, 4 artefatti release, 29 gate ticket), non 49 ticket ulteriori.

### Review, codice e delivery

Review locale `code-review` sui due assi Standards/Spec:
`git diff 3e906674b5e195fb88fe8a8a7a469fd1bc0ea91c..25c94d145f5d813bde76bdf51851ebf3b37453ab`,
hash SHA-256 del diff
`bf84b4c8c8ace3651a20056c861e3553f4e022fbe2597601f988e3953fb34a24`.
10 file, **522 inserzioni, 14 rimozioni**. Letti i tre seam Python,
i test di regressione, i tre ticket AC, il runbook OIDC e i contratti
repository; nessun finding consequenziale riproducibile sul nuovo delta,
non review esaustiva del vecchio diff vs main. `ruff check` sei file
source/test **PASS**, `ruff format --check` dei due DP-515 **PASS**,
`git diff --check` **PASS**, benchmark deterministico **5/5 PASS**,
`python3 tools/check_repository_contract.py` **PASS**. Format debt
preesistente su DP-312/517 non riscritto a tappeto. Il test DP-405 timeout
resta **non PASS**. Due full suite avviate e interrotte dai worker per
non duplicare la **singola full integrata prime** sul codice finale.

**Full Python integrata prime:** la prima run sul checkout integratore
condiviso è stata **interrotta intenzionalmente / exit 130**, log
`/tmp/dp02-wave001-continuation-full-20261015.log`, dopo che sono
comparse modifiche concorrenti estranee alla lane DP-512 in
`poc/dichiarazioni_pubbliche/health_digest.py`, nei test health/ledger,
nel suo ticket e in un nuovo test untracked. Non usare tale run per
attribuire PASS/failure al commit source isolato. La suite
`PYTHONPATH=poc python3 -B -m unittest discover -s tests -q` è stata
avviata **nel worktree temporaneo detached con tracked source pulito**
`/tmp/dp02-wave001-isolated-25c94d1-20261015`, fissato sullo SHA
`25c94d145f5d813bde76bdf51851ebf3b37453ab`;
la sola dipendenza locale aggiunta è il symlink temporaneo
`web/node_modules` verso i pacchetti installati (non sorgenti tracciati),
da scollegare dopo il test;
log `/tmp/dp02-wave001-isolated-full-20261015.log` —
**3.681/3.681 PASS, 426,148 secondi, exit 0, zero failures/errors**.
Rilevati ResourceWarning SQLite/HTTP non fatali; prova sul sorgente
fissato, non su DP-512 WIP concorrente. Verificata la sola dipendenza
symlink non tracciata, rimossa con `unlink` dell'alias (non del target);
poi `git worktree remove` senza force su tree pulito **PASS**:
ritornati ai soli due worktree canonici, senza eliminare dati unici.
Nessuno dei
diff concorrenti DP-512 è stato stage/commit dalla lane 02.
Non trasferire PASS storico 3674/3674 da
`db03d51` al nuovo codice. Se fallisce DP-238, conservare i failure
esatti e non convertire retest mirato in PASS generale.

Sorgente integratore Mac Studio:
`/Users/domenico/Code/DP-20261014-all-lanes-integrator`, branch
`integrate/dp-20261014-all-lanes`; commit source coorte e
`refs/heads/integrate/dp-20261014-all-lanes` remoto verificati identici
`25c94d145f5d813bde76bdf51851ebf3b37453ab`.
Main canonica locale e remoto
`33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`, non toccata;
due worktree preservati e nessuno stash. Prima della ricevuta restano
`PLAN.md` e questa receipt WIP **owned coordinatore**, oltre ai diff
DP-512 **estranei e preservati** (`health_digest.py`, `operation_ledger.py`,
test/ticket correlati): stage/commit finale limitato ai due owned.
Nessun merge/deploy, nessuna mutazione DB o server MiniPC.

PR sul branch esistente ancora **0**. `PR_HELD_AUTOREVIEW_BILLING_GUARD`:
nessun readback sicuro dell'identità effettivamente GitHub-linked per
`Automatic review=OFF` personale **e** override repository;
stato `EXTERNAL_AUTOREVIEW_SETTING_UNVERIFIED`. Nessun `@codex review`,
review a consumo, push su main o merge. La run GitHub Actions
`38693270893` su `25c94d1` è SUCCESS ma con il solo job
`repository contract` PASS: web/backend/detached clone SKIPPED;
non è CI PR completa.
`verify_main_delivery.py --review-check` va ripetuto sul commit finale
documentale; non attesta PR/CI/manual. Prima di un merge servono PR reale,
CI esatta, thread paginati/risolti, `check_pr_merge_gate.py` e gate
legal/editoriale/source/host/manual.

**PR description pronta ma HELD, base `main` / head
`integrate/dp-20261014-all-lanes`:** "Integrare i WIP originali DP02 e
tre regressioni fail-closed in semantica, account e incremental watch".
Scope: undici merge sorgente preesistenti, più tre commit piccoli di questa
continuazione e loro test/receipt; invarianti no automatic publication,
source-rights e identity-review separati. Evidence: Python focused/adjacent,
benchmark, Ruff, ricevute ticket e SHA sorgente fissato; la full exact-head
rimane separata e non può essere sostituita dal job solo-contract dei push.
**Readiness PR=HELD** finché non si dimostra il vero account linked
& override repo OFF o consenso esplicito owner ai costi. **Readiness
merge=NO** anche dopo apertura, finché non esistono CI PR completa,
review locale sull'intero range, paginazione threads GitHub,
`PR_MERGE_GATE_PASS` e approvals/source/runtime/manual dovuti.

### Risposta di trasporto e prossima azione

Il coordinatore aggiorna `PLAN.md` Active workflow e la presente
ricevuta prodotto; questa **sezione completa di continuazione** è la
risposta univoca da copiare nel file
`/Users/domenico/ControlCenter/src/controlcenter-ops/tasks/20260929-main-release-closure/310-prompt-to-prompt-20261015/02-WAVE-001-COS.response.md`.
Il repository Ops condiviso presenta WIP di altre lane: la copia locale
si produce senza toccare index/ref Ops e resta **PENDING_CORE07_OPS_LEASE**
per commit/push/readback Ops da parte dell'unico writer Core07. Non
duplicare alcun WIP già presente. Nessun worker ha processi pendenti
assegnati; nessuna attivazione provider, account, fonte, Persona, AT o
pubblicazione è implicita.

**Prossima frontiera:** blocchi di fonte/Gold, OAuth/privacy, budget/PG,
approvazione Persona/pin e AT. Unica domanda manuale precisa: **qual è
l'URL e l'hash della build approvata di `/esplora/` per il test VoiceOver
DP-429?** Non avviare una nuova wave di hardening invariata.
