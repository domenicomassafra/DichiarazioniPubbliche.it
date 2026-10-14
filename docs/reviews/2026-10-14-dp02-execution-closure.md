# DP02 — esecuzione parallela, bug fix e gate di release (14 ottobre 2026)

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

**CI source corrente:** GitHub Actions run `38587368015` su
`a63fe1330e6de73f03ebe8a9341d2c5f0abe6573` è `completed/success`:
`repository contract=success`, mentre backend matrix, web static e detached
clean-clone sono `skipped` sui branch push. Non è una CI PR né autorizzazione
al merge. In locale, Astro check ha 0 errori/0 warning (1 hint), ricerca,
Statement, parity, routes, projection-boundary e 8/8 check di accessibilità
automatici PASS; resta la prova manuale con screen reader e dispositivo.
I controlli repository, inventario privacy, asset/licenze, fixture, versioni,
Ruff sui sorgenti/test modificati e `git diff --check` sono PASS.

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
