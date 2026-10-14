# DP02 — esecuzione parallela, bug fix e gate di release (14 ottobre 2026)

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
