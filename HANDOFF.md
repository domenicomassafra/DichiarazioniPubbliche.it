# Dichiarazioni Pubbliche — handoff operativo attuale

> **Quinta tranche DP02 (14 ottobre):** codice integratore pubblicato a
> `e7210a73fdfcdf8f3cf42fe78264127a48a6221c`, dopo tre nuovi commit
> RED→GREEN source-only: DP-319 `1746aca` (cap costi assignment, 44 PASS),
> DP-440 `e91b44f` (review sentence distinta da membership/currentness,
> 43 PASS), DP-320 `e7210a7` (ticket con >128 deps non ammesso, 51 PASS).
> Ruff/diff-check verdi, staging e readback remoti per ogni commit; tutte le
> acceptance originarie restano **OPEN**, come source/rights, PG/issuer,
> editoriale e pilot. [Ricevuta DP02 quinta wave](docs/reviews/2026-10-14-dp02-execution-closure.md).
> **Full Python FINALE 3664/3664 PASS**, `OK`, exit0, **358,844 s** sul
> source `e7210a7`, log `/tmp/dp02-wave5-final-full-20261014.log`.
> È una vera nuova esecuzione, non un riuso del run wave4 3661/1;
> l'intermittenza DP238 non si è ripresentata ma la causa resta ignota.
> Status 162/90 DONE/72 non DONE,
> preflight **NO-GO/49**; `main` prodotto ancora protetto dalla guardia PR.
> **Response Ops 297 quinta wave pubblicata** su ControlCenter `main` a
> `94feaad5401a1abab29856a480d6bb7dbe4e88e8`, `ls-remote` uguale,
> un solo file response02 staged sotto lease Core07 esplicita poi RILASCIATA,
> WIP 01/05/305 e Core07 preservati.

> **Quarta wave DP02, 14 ottobre — SOURCE `91b1783654b69888196b509bab71c19dc1aaf1ce` salvata su branch remoto:**
> ripresa dal checkpoint integratore `0eba7fb` e da ControlCenter Ops
> `main` `65dafd8`. Il precedente DP-517 OIDC origin è stato provato con
> negativo/positivo e 107/107 test, mentre il
> [runbook di attivazione](docs/release/account-oidc-activation.md) è stato
> allineato sul callback esatto (`a302cd8`). Sei patch RED→GREEN nuove sono
> pubblicate e rileggibili: DP-313 `0870c48`, DP-318 `5ad4bf4`,
> DP-438 `2b2880e`, DP-317 `f126d00`, DP-439 `3f090b9`,
> DP-435 `91b1783`, ogni commit con sole path owned e writer prime unico.
> [Ricevuta DP02 e limiti di acceptance](docs/reviews/2026-10-14-dp02-execution-closure.md)
> e [censimento pubblico/crosswalk 124 link ora validati](docs/reviews/2026-10-14-dp02-declarations-inventory.md)
> sono i locator correnti. La release resta **NO-GO/49**: 16 decisioni Q-306,
> 4 artefatti mancanti, 29 ticket di lancio aperti, PR/CI full/auto-review,
> source-use, Gold, screen reader e MiniPC/CDN/owner ancora indipendenti.
> **90 DONE / 72 non DONE**, `main` del prodotto non avanzato. Una suite
> completa sul codice wave4 deve essere attribuita al suo exit code, non alla
> precedente full suite di wave3. La risposta di lane nel packet Ops 297
> è **ora pubblicata** sul `main` ControlCenter a
> `685a04e74878516f30edeb7e4b8720d68c1c012a`, un solo path di risposta
> e readback remoto identico; WIP delle altre lane preservati.
> **Full suite wave4 ESEGUITA ma NON VERDE:** 3.661 test / 1 failure DP-238
> `DOCUMENT_PDF_WORKER_UNAVAILABLE`, exit1, 826,816 s sul source `91b1783`.
> Retest DP238 isolato 11/11 e con extraction 22/22 PASS, ma ciò non annulla
> la failure integrata. Vedere [ricevuta DP02](docs/reviews/2026-10-14-dp02-execution-closure.md)
> e log `/tmp/dp02-wave4-final-full-20261014.log`. Nessun aumento deadline
> o falsa promozione di source/diritti/release; nuovo run completo verde
> resta necessario prima di considerare questo gate soddisfatto.
> **Ops packet 297 addendum full-suite pubblicato** sotto lease esplicita
> poi rilasciata, `c49809baada076fcb4f6a88ea9f8e82adb9a3a59` su
> ControlCenter `main`, un solo file response02, SHA remoto uguale.

> **Terza wave DP02, 14 ottobre:** branch remoto
> **Ops packet 297 addendum pubblicato:** ControlCenter `main` aggiornato
> a `65dafd8ecb31b45889d2dc90fbdb63dd81d7d1c2`, un solo file
> `02-dichiarazioni-pubbliche.response.md` nel secondo commit. I WIP
> 01/05/305 sono conservati, lo SHA remoto Ops coincide col checkout.
> `integrate/dp-20261014-all-lanes` su codice `186ef17e59fe73cab061a5301ffbe0d9f5443721`.
> Fix indipendenti DP-517 OIDC redirect, DP-516 rights receipt, DP-243
> traduzione/copia da originale HELD, DP-515 fonte stale `Last-Modified`.
> TDD negativo→positivo, test mirati, Ruff, `git diff --check` e quattro
> commit separati con `ls-remote` verificato; ticket **IN PROGRESS** per
> acceptance esterne ancora aperte. La risposta DP02 è stata pubblicata
> anche nel packet 297 ControlCenter Ops `main` a `3cfb3c433d79fd1dc4f7c543e5dae1263700303f`
> con tre soli file owned e WIP delle altre lane preservato. Riferimenti:
> [receipt wave3](docs/reviews/2026-10-14-dp02-execution-closure.md),
> [inventario dichiarazioni](docs/reviews/2026-10-14-dp02-declarations-inventory.md).
> La CI GitHub `38596675716` sul codice wave3 è `success` **solo** per
> `repository contract`; backend/web/clean-clone ancora `skipped` sul
> branch. PR, approvazioni legal/editoriali, source-use, MiniPC/CDN e
> manual screen reader sono **NO-GO**.
> **Full suite finale wave3 sulla source `186ef17`: 3.652/3.652 PASS,
> exit 0, 322,598 s**, log `/tmp/dp02-wave3-final-full-20261014.log`;
> warning SQLite/HTTP non fatali. Questo non soddisfa PR/CI completa,
> accettazione MiniPC/CDN né i 49 blocker del preflight di release.

> **Aggiornamento operativo 14 ottobre 2026 (integratore):** il checkpoint
> corrente è nel branch `integrate/dp-20261014-all-lanes`, **non in `main`**.
> L'intera ricognizione Git, le 11 integrazioni effettive, i test post-review,
> la pulizia misurata dei worktree e i blocker di release sono in
> [ricevuta di consolidamento](docs/reviews/2026-10-14-all-lanes-consolidation-receipt.md).
> Per la prossima sessione, leggere prima
> [handoff aggiornato e pending](docs/reviews/2026-10-14-postconsolidation-handoff.md).
> La [ricevuta della ripresa esecutiva DP02 del 14 ottobre](docs/reviews/2026-10-14-dp02-execution-closure.md)
> elenca le correzioni recenti, i commit integrati, le prove e i gate
> ancora aperti. I ticket e `PLAN.md` mantengono l'autorità sulle acceptance.
> Lo SHA `2a85c7855f7c6438cfc57092388370ef183ac168` è il checkpoint remoto
> documentale precedente al follow-up Ruff/handoff; non attribuire test o CI
> a commit successivi senza riesecuzione. Il repository `main` è ancora
> `33b4590e37a06b0ee31ceb1a2c4ef6ae4f7296fe`, protetto da PR+review.
> **Post-fix verificato:** sul commit codice `0228fa8196d4136ca4807b9fa224592fe666ea49`
> full Python **3.624/3.624 PASS**, exit 0, **664.442 s**, log
> `/tmp/dp-20261014-lint-handoff-postfix-full.log`; lint Ruff sui 40 Python
> modificati e benchmark 5/5 PASS. Eventuali successivi commit solo-documento
> non modificano questo codice, ma vanno comunque verificati per SHA remoto.
> Status/AC e gate fonte/legale/editoriale/MiniPC/auto-review restano aperti.
> **Readback GitHub CI 14 ottobre, DP02:** le run `38561882494`
> (`15fee6c`) e `38561730777` (`0228fa8`) hanno conclusione globale
> `success`, ma **solo `repository contract` è stato eseguito**; backend
> matrix, web static frontend e detached clean-clone risultano `skipped`.
> Il workflow riserva quei job a PR e `main` (`.github/workflows/ci.yml`).
> Non confondere questo verde parziale con la CI backend/web di una PR,
> né con i 3.624 test locali documentati sopra.
> I commit di codice successivi a `0228fa8` richiedono prove proprie:
> la precedente full suite non li certifica retroattivamente.
> **DP02 sulla source `a63fe133`: suite conclusa con 3.637/3.637 PASS,
> exit 0, 520,154 s** (`PYTHONPATH=poc python3 -B -m unittest discover
> -s tests -q`). GitHub Actions run `38587368015` è `success` solo per
> `repository contract`; backend/web/clean-clone sono `skipped` prima di
> PR/main. [Ricevuta esecutiva DP02](docs/reviews/2026-10-14-dp02-execution-closure.md)
> e [inventario documenti pubblici](docs/reviews/2026-10-14-dp02-declarations-inventory.md)
> registrano i commit, le prove e i gate editoriali/legali/MiniPC NO-GO.
> **Seconda wave DP02, source `bb00177`: 3.645/3.645 Python PASS,
> exit 0, 362,131 s.** Quattro commit sul branch integratore per DP242,
> DP244, DP519, DP518, rispettive regressioni RED→GREEN e controllo di
> provenienza/ritiro/freschezza. GitHub Actions `38593285587`: solo
> `repository contract=success`, backend/web/clean-clone `skipped`.
> [Ricevuta aggiornata](docs/reviews/2026-10-14-dp02-execution-closure.md):
> nessuna autorità per nuova PR, merge, pubblicazione o deploy inferita.

**Tranche seconda ondata dopo c16d823, 12 ottobre 2026:**
[Post-commit HELD_SOURCE receipt isolation, Studio operatore Collection
PG, revocation-currentness, private v3 Person/Topic/Statement,
same-epoch search tamper, Chrome 320px](docs/reviews/2026-10-12-studio-release-currentness-second-wave.md).
Prime ha verificato e corretto un **nuovo** caso in cui, pur restituendo
HELD_SOURCE dopo revoca, il writer PostgreSQL riecheggiava la vecchia
ricevuta, e uno stesso request key conflittuale esponeva l'hash altrui.
Il percorso scritto HTTP→PG→reader storico distingue ora ricevuta
CREATED/REPLAY dalla revoca; Studio read-only rifiuta JSON duplicato
prima del query. La coda Collection PG reale (solo disposable e
token privato) è navigabile in Studio, non attiva sul server ordinario.
Il consumer v3 unisce fonti/opinioni/sintesi con epoch indipendenti;
DP-409 vieta wire JSON duplicato sotto lo stesso pin. Chrome 320px
verifica una parte dell'accessibilità, **non** VoiceOver/iOS fisico.
Nessun nuovo originale DONE senza AC reali: **90 DONE /72 pendenti,
NO-GO/49**. MacBook Air online, MiniPC non-Git intatto/servizi attivi,
MateBook Linux offline e WIP remoto non attestato. 0 byte rimossi.
Il nuovo SHA GitHub e la CI vanno accertati sul commit finale, mai
ereditati dalla precedente baseline.

**Tranche successiva a 52e4391 (12 ottobre 2026):**
[Studio Candidate firmato PG, metadata media revocabili,
historical checkpoint DP-516, month liabilities DP-514
e synopsis browser DP-440](docs/reviews/2026-10-12-private-candidate-binding-and-batch-next.md).
Il writer privato Candidate è attivato **separatamente**;
non è disponibile sul default Studio read-only né conferisce
Claim promotion o revisione qualificata. DP-419 aggiunge
una traccia metadata Capture→Segment con revoca CAS,
ancora senza derivazione indipendente, diritti o player.
Chrome reale ha verificato il nuovo modulo Studio contro
HTTP locale simulato; PostgreSQL+HTTP autentico verifica
separatamente firme, CAS e HELD_SOURCE senza ricevuta
fittizia. DP-516 blocca il backfill finché non esiste pilot
DP-443 autenticamente approvato; DP-514 non inventa
fatture EUR o costi misurati. MateBook Linux ancora offline
e WIP remoto non controllato, MiniPC non-Git intatto,
nessun byte eliminato. Originali AC non forzati a DONE:
**90 DONE / 72 pendenti; release NO-GO/49**.
Verificare su nuovo SHA finale git+CI, non ereditare 52e4391.

**Nuova tranche operativa dopo d5ab8e1, 12 ottobre 2026:**
[Studio annotazioni firmate reali con CAS PostgreSQL, media-context,
cost/usage PG e preview sintesi v3](docs/reviews/2026-10-12-private-studio-triage-media-billing-recovery-wave.md).
Lo Studio predefinito rimane read-only: la scrittura di un'annotazione
Discovery privata avviene solo tramite servizio loopback esplicitamente
avviato, receipt HMAC di revisore emessa separatamente e CAS PostgreSQL
con prova del retry dopo restart. Non confondere NEEDS_REVIEW/DEFERRED/
REJECTED come annotazioni con un'autorizzazione a usare fonti, rifiutare
un contenuto, approvare Claim o pubblicare. L'Inspector media presenta
intervallo canonico e metadati di Capture ma riporta
capture_segment_binding=UNPROVEN e seek_authorized=false perché manca
una FK/versione certa Segment→Capture nello schema. DP-512/513
distinguono report canonical provider e costo registrato da fattura
verificata, senza spend. DP-440 congiunge synopsis citata al
Person×Topic×Statement originale sotto pin esterni e SSR isolato.
MacBook Air online; MateBook Linux ancora Tailscale offline/SSH
timeout, WIP remoto non attestato. MiniPC mirror non-Git
inalterato, nessuna produzione, 0 byte rimossi. Originali AC
ancora OPEN e **90 DONE / 72 pendenti, release NO-GO/49**
senza nuove approvazioni legali/editoriali. Verificare CI
sullo SHA finale della tranche, non sul precedente 11/11.

**Tranche successiva a b239d20, 12 ottobre 2026:**
[integrazione operativa Studio PostgreSQL, decisioni Candidate firmate,
preview privata Statement v3](docs/reviews/2026-10-12-studio-pg-navigation-and-opinion.md).
La nuova verticale DP-416 consulta una sola snapshot PostgreSQL
Collection→Content→Capture→Passage→Statement Candidate, espone
navigazione tastiera e fa jump verso il dettaglio Claim esistente.
DP-418 ora conserva decisioni reviewer-attested con CAS PG, con
lettura storica autenticata HTTP/UI che revalida la revoca della
fonte e non abilita scritture/approvazioni attraverso il token.
DP-437 produce opinioni originali senza Finding con reader Persona/
Statement v3 e pin CURRENT controllati due volte, attraverso SSR
Astro isolato e noindex. Non duplicare gli stessi percorsi.
Il test Chrome esteso del readback decisione è rimasto bloccato ed
è stato interrotto solo nel processo generato da questa tranche:
**nessun PASS Chrome del nuovo readback**; l'originale Chrome
DP-416 e le prove JS DOM/HTTP nuove sono distintamente verdi.
Tre subagenti non sono riusciti ad avviarsi; il quarto DP-418
è stato verificato e integrato. MateBook Linux è risultato
offline su Tailscale/SSH (WIP non attestato), MiniPC mirror
non-Git intatto, nessun byte eliminato. Nessuna autorizzazione
editoriale/fonte/legale/MiniPC prod inventata:
**90 DONE / 72 pendenti, release NO-GO/49**. Lo SHA remoto,
la suite totale e la GitHub CI della nuova tranche devono essere
verificati sul commit finale, non ereditati da b239d20.

**Nuova tranche multi-ondata del 12 ottobre 2026, dopo main 61b7941:**
[undici commit di sviluppo in quattro wave su persistenza Studio,
isolamento multi-persona, budget e watch, lettori v3 e revoche](docs/reviews/2026-10-12-multiwave-durable-private-operations-and-v3.md).
Implementazioni distinte: DP-242 handoff SQLite con CAS/diritti; DP-240
batch per Persona/Passage riavviabile; DP-319 ricerca privata append-only;
DP-515 SourceWatch persistente; DP-514 ledger globale attempt cross-mese
e report privato read-only; DP-320 race PostgreSQL reale isolata; DP-438
Persona zero Statement e DP-439 Person×Topic con Astro SSR isolato; DP-409
ricerca statica a epoch/pin di release. Non ripeterle senza una diversa
regressione riproducibile. I ledger di prova **non** attestano diritto
fonte, fattura, reviewer, dispatch B o pubblicazione: AC originali ancora
aperti senza prove approvate. MateBook Linux non è raggiungibile in questa
tranche (Tailscale offline e SSH timeout), quindi NON dichiararne WIP
riconciliato. MiniPC mirror di deploy rimasto intatto, 0 byte rimossi.
Conservare **90 DONE / 72 pendenti, release NO-GO/49**. Per la consegna
esatta verificare nuovo SHA Git origin e GitHub Actions **dopo** il push;
la vecchia CI 11/11 su 61b7941 non certifica questi commit.

**Tranche operativa 12 ottobre 2026, successiva al GitHub SUCCESS
`13e6fff9`:**
[nuova verticale Studio autenticata, due journal persistenti, revoche,
consumer v3 e contestualizzazione processuale](docs/reviews/2026-10-12-operational-studio-persistence-withdrawal-synopsis-wave.md).
Non ripetere DP-416/417/418/440/518/519/516 o i fix DP-312/313 qui
documentati: le implementazioni nuove includono navigazione UI reale
Collection→Capture→Passage→candidati, loopback PostgreSQL read-only con
bearer/Host/Origin, target-source PG e script Python→TS→Astro SSR. I
journal SQLite privati implementano CAS/replay/durabilità senza autorità
di pubblicazione. Il test browser Chrome/CDP supplementare è andato in
timeout, **non** certifica a11y manuale; i test DOM/HTTP separati passano.
Non assumere nuovo DONE, diritti, revisori, CDN o prova MiniPC:
**90 DONE / 72 pendenti, NO-GO/49**. MacBook Air e MateBook Linux sono
raggiungibili per audit bounded, MiniPC resta mirror non-Git intatto.
Verificare `HEAD`/remoto e GitHub Actions sull'esatto SHA finale prima
di utilizzare la tranche; CI storica `13e6fff` riguarda soltanto la
baseline precedente.

**Nuova tranche successiva a `aca8809`, 11 ottobre 2026:**
[cinque funzionalità Studio/Watch/v3 e relativa prova locale](docs/reviews/2026-10-11-private-ops-v3-release-consistency-wave.md).
Commits locali `da56998` (DP-422 consumer v3 coerenti), `7fb3bdb`
(DP-416 Collection→Passage→Candidate), `3b50e62` (DP-418 confronto
sorgenti Candidate), `2dcb5a1` (DP-417 coda Capture con revoche rights
RED→GREEN), `1979ce8` (DP-515 digest quotidiano watch/coverage).
Non ripetere questi interventi senza regressione diversa e dimostrabile.
**MateBook Linux ora raggiungibile**, ma nessuna copia DP nei soli root
analizzati: non equipararlo a una scansione completa. MiniPC mirror non-Git
immutato; servizio web e Cloudflare attivi tramite `systemctl --user`.
Il programma resta **90 DONE/72 pendenti, release NO-GO/49**. Nessun nuovo
AC legale/editoriale, di accessibilità manuale o MiniPC accettato tramite
test sintetici. Verificare sempre esatto HEAD, GitHub push e CI del commit
terminale prima di aggiornare la baseline; non usare la vecchia CI
`aca8809` per certificare i nuovi commit.

**Nuova tranche operativa 11 ottobre 2026, dopo `753c112`:**
[nuovi consumer e percorsi original-quote Persona/Topic/Search, Studio,
derivazioni originali, contabilità e batch](docs/reviews/2026-10-11-first-class-public-private-workflows-wave.md).
I nuovi ingressi v3 sono opt-in, NON esposti in produzione, e dipendono da
fonte e diritti realmente attestati. Conservare `NO-GO/49`, non dichiarare
nuovi DONE per soli test sintetici o permessi in capo all'LLM. Audit host
limitato: MateBook Linux offline, MiniPC mirror non Git e invariato; nuovo
recupero misurato Mac Studio `web/dist` 1,093,632 byte. Verificare esatto HEAD,
push fast-forward e CI finale prima di sviluppi successivi.

**Tranche multi-wave del 11 ottobre 2026:**
[interventi funzionali, TDD e audit conservativo su quattro host](docs/reviews/2026-10-11-multi-wave-backlog-source-runtime-audit.md).
DP-416/417/418/435/436/438/440/512/514/515/516/518/519/320 hanno
ricevuto implementazioni o correggono difetti provati; il report distingue
CI, originali AC, blocchi esterni e un recupero mirato di soli **3.43 MiB**.
Non inferire nuovi DONE, deployment MiniPC o licenza da questa fonte.
Verificare l'esatto commit remoto, CI e status prima di eseguire qualunque
altra modifica; release resta **NO-GO/49** salvo nuova attestazione reale.

**Cinque nuove regressioni source-only, 11 ottobre 2026:**
[DP-304/439/312/313/318: fallimenti reali e limiti di acceptance](docs/reviews/2026-10-11-five-pending-integrity-wave.md).
Inventario privacy migrazioni, URL/identità indice ricerca, critica negata,
ruoli processuali e placeholder Persona: bug riprodotti RED→GREEN, test
semantici integrati 120/120 PASS; suite privacy/semantica aggregata
**199/199 PASS**. Nessun ticket DONE senza fonte/diritti,
attestazione e MiniPC: **90 DONE / 72 pendenti**, rilascio **NO-GO/49**.
La CI sul commit finale va controllata separatamente.

**Pending hardening wave, 11 ottobre 2026:**
[sei regressioni e relativi criteri ancora esterni](docs/reviews/2026-10-11-six-pending-safety-hardening-wave.md).
DP-236/237/242/244/315/319: permissions fonte, speaker esatto, handoff
Studio, catalogo osservazioni, fingerprint negazioni e budget/plan
dell'indagine. **75/75 test integrati mirati verdi**; nessuna source-only
fixture prova un'authority qualificata o MiniPC acceptance. Inventario
immutato **90 DONE / 72 pendenti**; release **NO-GO/49**. Verificare la
CI e il commit integrato prima di qualsiasi uso runtime.

**Nuova wave pending-closeout, 11 ottobre 2026:**
[audit di nove ticket con regressioni e blocker originali](docs/reviews/2026-10-11-pending-closeout-nine-ticket-wave.md).
DP-314/320/435/438/440/512/515/516/518 hanno ricevuto fix per
indipendenza fonti, fencing lettura/revoca, locator citazione, identità
Persona, sintesi e costi, monitoraggio e deduplicazione restart.
Nessuna acceptance esterna viene convertita in DONE usando prove
sintetiche. Inventario **90 DONE, 72 non DONE**, editorial release
**NO-GO/49**; nessun deploy su MiniPC. Le prove di full suite e CI
sono sempre da verificare sul commit finale.

**Closeout audit + sette ticket irrobustiti, 11 ottobre 2026:**
[verbale con criteri rimasti aperti e prove](docs/reviews/2026-10-11-closure-readiness-seven-ticket-hardening.md).
Audit DP-229/405/407/409/412/422/429, correzioni concretamente
testate per provenienza challenger, Persona senza Statement, stati
editoriali Content, Explore e accessibilità componenti. Suite Python
**2833/2833 PASS**, restore PASS, browser/Node e Astro check verde.
**Nessuno di questi ticket può essere promosso onestamente a DONE**
senza AT manuale, risorse/licenze pubblicabili reali, MiniPC readback
o revisore qualificato: base inventory ancora **90 DONE / 72 non DONE**,
editoriale **NO-GO/49**. Non usare test demo/fixture come atti di review.

**Nuova tranche a quattro subagenti, 11 ottobre 2026:**
[DP-238/239/240/241, fix e proof RED→GREEN](docs/reviews/2026-10-11-four-ticket-m2-hardening-wave.md).
Migliorati i confini privati di parsing PDF (inline image/formfeed),
traduzione con locator immutabile/numeri, batch manifest/replay/hold
multi-Persona e investigazione originale con ricevute uniche/cap tentativi.
**74/74 test mirati PASS**, benchmark deterministico 5/5 PASS,
Ruff dei file toccati e repository contract PASS.
I quattro ticket rimangono **IN PROGRESS** in attesa di gold
indipendente, source/rights permissions reali e readback MiniPC.
Nessuna autorizzazione al dispatch o alla pubblicazione è cambiata;
release **NO-GO/49**. Suite completa e CI si verificano
indipendentemente dal proof mirato.

**Follow-up cleanup + debug dell'11 ottobre:**
[type-hint runtime e clone QA recuperato](docs/reviews/2026-10-11-queue-annotation-wip-followup.md).
Clone temporaneo con HEAD antenato di `main` e zero WIP
rimosso recuperando **38944768 byte (~37,1 MiB)**;
`approved-empty.json` e rollback intatti. I tre recuperi
precedenti e questo sommano **809046016 byte (771,57 MiB,
0,753 GiB)**, senza inventare ulteriori GB. Corretti
42 riferimenti di tipo indefiniti F821 nelle annotazioni
di queue/worker: regressione RED→GREEN con
`typing.get_type_hints`. Suite Python **2821/2821 PASS**
con restore drill, benchmark **5/5 PASS**, repository
contract PASS, zero F821; rimangono 120 altri rilievi
lint storici. Nessun nuovo deploy; release **NO-GO/49**.

**Consolidamento Git + CI + cleanup del 11 ottobre 2026:**
[review, push e misure di pulizia sui quattro host](docs/reviews/2026-10-11-main-push-code-review.md).
Il main Studio è stato sincronizzato a GitHub con fast-forward
`f21c15c` (74 commit precedentemente locali, nessun force),
GitHub Actions run `38155719467` **11/11 job SUCCESS**
(otto backend macOS/Ubuntu Py3.11–3.14, web, contract,
clone pulito). L'unico Prompt2Prompt storico untracked
è stato preservato in Git, worktree/branch/stash locali
riconciliati. Pulizia selettiva di cache inutilizzate:
**770101248 byte (734,43 MiB)** su Mac Studio e MiniPC;
Air e MateBook Linux senza duplicati rilevati nel perimetro.
Il MiniPC ha ancora **304 file tracked differenti/mancanti**
rispetto al codice Studio e non è stato sincronizzato;
web service e tunnel rimangono attivi e HTTP localhost 200.
**Il push sorgente NON è un deploy del nuovo codice,
nessuna nuova pubblicazione editoriale, release NO-GO/49.**
Archivi Git e rollback conservati. Il checkpoint Git
di questo stesso verbale può avere SHA successivo a
`f21c15c`, senza cambiare questi esiti.

**Nona tranche locale, 11 ottobre 2026 — sviluppo + riconciliazione:**
[verbale implementazione DP-235/321/443 e checker CI](docs/reviews/2026-10-11-post-reconciliation-ticket-wave.md).
Commit sorgente/test locali `7fb263d` (DP-235), `30ce724` (DP-321),
`970191c` (DP-443, proposta di verifica sempre NO-GO);
`d72b47f` riallinea milestone e checker PLAN/ticket. **2819/2819**
test Python PASS (182.932 s) e restore drill PASS, benchmark sintetico
5/5 PASS, Astro check 89 file con 0 diagnostici e quattro controlli
web di statement/parità/ricerca/confine pubblico PASS, Ruff/formatter
dei nuovi moduli PASS, repository contract PASS. Registro:
**162 totali, 90 DONE, 52 IN PROGRESS, 6 BLOCKED, 14 FUTURE, 72 non DONE**.
Preflight **NO-GO/49** invariato e corretto. DP-443 è ancora FUTURE:
nessuna fonte autentica autorizzata né firma, MiniPC DB/reader, review
qualificata o rollout. **Nessun push, deploy o spesa provider.**

**Ricognizione multi-host e ultimo checkpoint QA del 11 ottobre:**
[WIP/Git/ticket/MiniPC/four-host reconciliation](docs/reviews/2026-10-11-four-host-wip-reconciliation.md).
Il registro canonico è allineato dopo DP-235 (162 ticket: 90 DONE,
52 IN PROGRESS, 6 BLOCKED, 14 FUTURE); la suite Python corrente ha
2792/2792 PASS, benchmark 5/5 e restore drill PASS. Nessuna nuova
autorizzazione di fonte, pubblicazione, push o deploy; release NO-GO/49.
Le evidenze della tranche precedente riportate sotto rimangono storiche.

**Checkpoint operativo aggiornato:** 11 ottobre 2026. Questo documento è la porta di ingresso operativa,
non una seconda fonte di verità per i ticket o una certificazione di release.

**Ottava tranche locale 2026-10-11 (no push/deploy):**
DP-238 `4e6a465`: born-digital PDF reale in worker isolato opzionale,
versioned private page/Passage selectors, **nessun OCR/VERBATIM automatico**,
19 test PDF/documentali PASS. DP-429 `cf70a4f`: stato Explore con zero
record pubblicati riconoscibile da tecnologie assistive, Chrome locale
tastiera/movimento ridotto/zoom 200% PASS, screen reader reale ancora aperto.
DP-436 `352cb78`: confronto source-only v3 API/JSON-LD/RDF con documento,
quote hash, linguaggio e revoca, **32** regressioni selezionate PASS; non è
una route pubblica né una licenza. AC-238, -429 accessibilità manuale e
-436 restano aperte. Nuovo opt-in `document-pdf` mantiene il profilo
stdlib-only invariato. **DP-519 integrazione Studio** non ha prodotto
un'implementazione verificabile in questa tranche. Nessun record reale,
diritto qualificato, MiniPC/canary, pubblicazione o deploy.

Suite Python integrata finale dopo tutti i commit sorgente/test: **2789/2789
PASS (152.006 s)**, restore drill PASS. Benchmark 5/5 PASS, compileall,
Ruff, repository contract e controlli HTML/Chrome Explore PASS;
preflight **NO-GO / 49 blocker** previsto. Registro ticket invariato:
**162 total, 90 DONE, 51 IN PROGRESS, 6 BLOCKED, 15 FUTURE, 72 non DONE**.

**Settima tranche locale, 2026-10-11 (no push/deploy):** DP-518
`8bd5cc5` (audit su dodici superfici pubbliche/cache con DP-320 epoch;
anche un readback 404 sintetico non è autorità MiniPC/CDN), DP-516
`46628d1` (batch storico proposto SOLO DOPO gate DP-443/diritti/watch/budget,
mai dispatch), DP-317 `1aac45c` (diritti d'uso esatti per
fonte/Capture/rappresentazione/giurisdizione, sempre HELD fino a prove
qualificate), DP-519 `084a77a` (coda visiva privata, ore effettive vs
stimate, niente reviewer testuale/approvazione foto). Tutti i ticket restano
**IN PROGRESS** e le AC reali sono aperte. Benchmark locale 5/5, compileall,
Ruff, repo contract e launch-preflight **NO-GO 49** verificati. Il test Python
integrato della tranche ha un verbale separato nella review di implementazione.
Registro **162: 90 DONE, 51 IN PROGRESS, 6 BLOCKED, 15 FUTURE**; 72 non DONE,
file/PLAN coerenti. Fonte vera, firma DP307/443, gate su MiniPC/PostgreSQL,
riscontri host/edge, cost reservation e lavoro operatore reale restano assenti.
Verifica integrata finale della tranche: **2772/2772 test Python PASS
(159.267 s), restore drill PASS**, benchmark 5/5, compileall, Ruff,
repository contract e `git diff --check` PASS; **NO-GO / 49** confermato.

**Sesta tranche locale 2026-10-11, no push/deploy:** DP-242
`d2d1729` (Discovery/Candidate preflight con reread persistito, scope,
Capture hash e hold esplicito) e `74b5d56` (due route read-only
autenticate loopback; 34 test API/Studio PASS); DP-243 `4a586dd`
(piccolo manifest IT/DE storico *synthetic* e rights/version/repost/role
holds, non un archivio creato); DP-321 `12bfb5a` (denominatori di
errore/astensione/gold independence, output mai release-eligible);
DP-316 `fa647a9` (profilo/fence/materiali e challenger, nessuna
firma né migrazione human gate). Sono contratti implementati, non
accettazione completa dei quattro ticket. Le rispettive acceptance
rimangono aperte; registri `PLAN.md` e `docs/tickets/` sono canonici.
Mancano sorgenti/diritti autentici, verificatori esterni, off-DB authority,
DB write/reader fence MiniPC e DP-443; il rilascio rimane **NO-GO**.
Verifica finale post-fix: **2719/2719 test Python PASS (239.105 s)**,
restore drill PASS, benchmark **5/5 PASS**, compileall e repo contract PASS,
preflight **NO-GO / 49 blocker** come atteso. Registro **162 ticket:
90 DONE, 47 IN PROGRESS, 6 BLOCKED, 19 FUTURE**; 72 non DONE e PLAN coerente.

**Quinta tranche source-only 2026-10-11 (codice già committato, no push):**
DP-240 `cafe1e1` e test correttivo `100a1dd` (batch candidati privati
multi-Person, integrità plan e separazione dei Passage), DP-314 `adedac9`
(profili e preflight di requisiti di prova, nessun verdetto), DP-241 `2451869`
(piano di recupero della fonte originale con metodi distinti, tentativi
idempotenti e controllo lineage/diritti/costi, senza ricerche reali).
Test nuovi 15+10+16 PASS; suite Python integrata **2662/2662 PASS**
in due run (168.700 s e 166.154 s) con restore drill PASS, benchmark
5/5 PASS. `219592e` contiene solo normalizzazione di formattazione,
con lint/formatter verdi e test DP-240/314 riconfermati. La review
della wave registra prove e limiti dopo l'hardening finale DP-241.
Registro ticket **162: 90 DONE, 43 IN PROGRESS, 6 BLOCKED, 23 FUTURE**;
allineamento PLAN PASS, **NO-GO 49 blockers**. Restano non assolte tutte
le AC che chiedono prove autentiche, diritti, MiniPC, Studio e DP-443.

## Implementazione autorizzata il 2026-10-11 — source-only, NO-GO produzione

Il mandato precedente di pianificazione (Q19, 10 ottobre) è stato completato.
L'owner ha poi autorizzato **l'implementazione** dei ticket, senza conferire
licenze di sorgenti reali, diritti alle citazioni, spesa per provider, publish,
ingestione massiva o deployment. Partenza `573de7f`; le nuove modifiche
sono in commit locali su `main`, non pubblicati.

Prima e seconda ondata:

- Fonte/diritti: DP-236 `acf6541` (uso/rights exact-artifact fail-closed);
  DP-237 `6bd8532` (locator Source/Capture/Passage con hash/versioni);
- Contesto/relazioni: DP-312 `6404079` (speech-act semantico privato),
  DP-318 `d01fb22` (same-Person vs cross-Person, senza poteri pubblicativi);
- Verbatim: DP-435/437 `2405049` schema/proiezione v3 opt-in, DP-436
  `4a7afbf` serializzatori API/RDF/JSON-LD opt-in, componenti web isolati
  `caa5c5c`/`ce60baf`. I reader HTTP pubblici restano v2;
- Search UX: DP-429/439 `df6fa42`/`5c72563`/`f8b2b6e` (filtri
  Persona × Tema sulle membership già autorizzate nel v2; no parafrasi
  travestita da citazione), documentazione `2f2dba4`;
- Costo: DP-512 `c6d55c7` (non presentare stima come fatturato), DP-514
  `e2df061` (proposta cap mensile EUR **disabled**, nessun dispatch);
- `5b8edb7`: classificazione inventario privacy aggiornata per i 21 campi
  v3 condizionali, no public authorization, correzione test status ticket,
  PLAN e primi receipt implementativi. Il backlog è **162 ticket: 90 DONE,
  30 IN PROGRESS, 6 BLOCKED, 36 FUTURE**; 72 non DONE. Le nuove AC restano
  aperte dove mancano prove reali.

**Terza tranche source-only, 2026-10-11:** DP-238 `c366514` (testo
HTML/XML/UTF-8 page-aligned, OCR scan/PDF non ancora supportati), DP-313
`6afb00f` (ruoli/stati documenti processuali separati), DP-438 `7e8bbbb`
(Persona pubblica autonoma v3, opt-in senza rotta live) e DP-515 `3cb5d93`
(watch incrementale disattivato e bounded). Browser Esplora
`b4caa2a` ha superato QA in Chrome isolato su build vuota e demo,
inclusa intersezione Persona × Tema con URL. Il passaggio allo stato
`IN PROGRESS` non chiude le loro AC; il nuovo registro è **162 totali,
90 DONE, 34 IN PROGRESS, 6 BLOCKED, 32 FUTURE**, sempre 72 non DONE.

**Quarta tranche source-only:** DP-319 `6152dd0` (attempt ledger proposte finite),
DP-320 `7ed9eb3` (revocation epoch SQLite isolato), DP-315 `20c63eb`
(nega parole vs endorsement vs intento), DP-239 `aedced9`
(originale/de→it distinto e machine translation HELD), DP-440 `fbecfea`
(sintesi offline solo con frasi autonomamente revisionate, citazioni v3 e
source-lineage), DP-244 `10dd9af` (coverage osservata e version refresh).
Contratti privati/opzionali, non nuovi servizi attivi. Baseline verificata:
**2561/2561** suite Python post-Wave3; **2621/2621 PASS post-Wave4**
(154.305 s) e benchmark 5/5 PASS. Registro: **162 totali, 90 DONE, 40 IN PROGRESS,
6 BLOCKED, 26 FUTURE, 72 non DONE**. Nessun nuovo DONE è stato assegnato
senza diritti/authority/MiniPC, né alcun push o deploy. Preflight release
rimane **NO-GO con 49 blocker** (Q-306, fonte reale/diritti, release).

Test puntuali e web sono stati eseguiti: `check:search`, `check:statement`,
`check:design`, Astro check (88 file, 0 diagnostici),
`check:projection-boundary`, suite DP-236/237/312/318/435/436/512/514,
con le regressioni mirate dei worker. Prima suite Python integrata: 2492
test, 5 non PASS dovuti a inventario privacy v3 non rigenerato (4) e
conteggio ticket congelato a 125 (1); problemi corretti al sorgente e
17/17 test privacy mirati PASS. Il risultato **della ripetizione totale**
deve essere letto nella review di questa wave prima di chiamarla green.

Restano **NO-GO:** rights source-family e Q-306/DP-307/317 qualificati,
fonti/contesto autentici, attestazioni DB e dual control/machine
policy DP-316, gold reale DP-321, API/v3 web route e revoca cache,
inserimento `person_id` nei chiamanti legacy DP-318, CAS persistente
budget EUR DP-514, pilot integrato MiniPC DP-443, stable v1 DP-705.
Nessun daemon, chiave, worker host, DB di produzione, deploy, push o
provider pagato è stato usato da questa implementazione.

## Leggere nell’ordine

0. [**Prompt unico post-grilling — quattro subagenti nativi, solo backlog**](tasks/prompt2prompt/20261010-231757-backlog-post-grilling/lane-01-backlog-master/001-backlog-master.prompt.md) — **mandato eseguito nella nuova sessione**. Il risultato integrato è nel PLAN, nelle due review post-grilling e nel file di risposta adiacente al prompt. Nessuna implementazione; i prompt di audit/grilling precedenti restano storia.
1. [`FINAL-PENDING-GRILLING-2026-10-10.md`](FINAL-PENDING-GRILLING-2026-10-10.md) — stato completo dei pending e prompt per il grilling nella prossima chat.
2. [`MEGA-HANDOFF-2026-10-10.md`](MEGA-HANDOFF-2026-10-10.md) — dettaglio delle prove e dei limiti, tabella della pipeline e analisi del rallentamento.
3. [`LAUNCH.md`](LAUNCH.md) — pubblicazione informativa essenziale **distinta** dalla release editoriale stabile.
4. [`PLAN.md`](PLAN.md) e [`docs/tickets/`](docs/tickets/) — registro **canonico**; baseline storica 125 ticket, dopo rivalutazione 162 (37 FUTURE aggiunti), 35 originari non conclusi mantenuti e riconciliati.
5. [`PRODUCT.md`](PRODUCT.md), [`CONTEXT.md`](CONTEXT.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`AGENTS.md`](AGENTS.md) — invarianti, architettura e regole di lavoro.
6. [`docs/reviews/2026-10-10-open-ticket-reprioritization.md`](docs/reviews/2026-10-10-open-ticket-reprioritization.md) — decision queue 35/35: possibili accorpamenti e rinvii senza cancellare acceptance criterion.
7. [`docs/reviews/2026-10-10-ux-redesign-audit-and-brief.md`](docs/reviews/2026-10-10-ux-redesign-audit-and-brief.md) — critica verificata del frontend, quattro direzioni visuali alternative e redesign da decidere **solo dopo il grilling**.
8. [`docs/reviews/2026-10-10-post-grilling-coverage-and-sequencing.md`](docs/reviews/2026-10-10-post-grilling-coverage-and-sequencing.md) — matrice R01–R42, ID nuovi, gate di pilot/diritti/bulk e non-goal.
9. [`docs/reviews/2026-10-10-post-grilling-target-reconciliation.md`](docs/reviews/2026-10-10-post-grilling-target-reconciliation.md) — decisioni definitive su verbatim, Persona×Tema, automazione e limiti delle vecchie acceptance.

## Stato verificato al 10 ottobre (ricontrollare live)

- **Sorgente autorevole:** `/Users/domenico/Code/DichiarazioniPubbliche.it`; repo GitHub `domenicomassafra/DichiarazioniPubbliche.it`.
- **Git alla baseline pubblicata precedente:** `main` locale e `origin/main` al commit `a104f0f`; nessun altro branch/worktree/stash al controllo. I commit successivi di review/handoff sono documentali e richiedono nuova verifica con `git log -1`.
- **CI GitHub:** esecuzione `38073576869` sul commit `a104f0f`: **11/11 job PASS** (backend macOS/Linux, web, repository contract e clean clone).
- **Ticket al checkpoint:** 125 totali; 90 DONE, 20 IN PROGRESS, 6 BLOCKED, 9 FUTURE; 35 non DONE.
- **Test integrati già eseguiti:** Python 2390/2390 PASS; benchmark deterministico 5/5 PASS. Non equipararli al canary di un corpus reale.
- **Release v1:** `tools/check_launch_preflight.py --expect-no-go` segnala 49 blocker. Non pubblicare claim o dati di diritti non approvati.
- **HTTPS:** online, ma risposta verificata il 10 ottobre segnalava file datati 7 ottobre: GitHub push e deploy web **non sono la stessa cosa**.
- **Runtime autorevole:** MiniPC, mirror non-Git `/home/udodo/src/DichiarazioniPubbliche.it`; PostgreSQL `dichiarazioni_pubbliche`. Non inferire deploy MiniPC da un nuovo SHA Git.

## Storico: mandato iniziale post-grilling, solo documentazione (superato)

**Risposte definitive registrate:** dichiarazioni pubbliche con parole esatte,
mai parafrasi sostitutive; riassunti separati; vista Persona × Tema con filtri
incrociati e sintesi citate; forte automazione anche sui documenti processuali;
più persone e lingue; storico permanente; continuità di fonti/temi ed eventi.
L'owner sceglierà il redesign. Autonomia finale di fact-check e futura pubblicazione
è il target dopo validation, non un gate runtime già attivato. La decisione Q19
del 10 ottobre autorizzava **solo la documentazione**; tale limite è stato
esplicitamente sostituito il giorno successivo dall'ordine di implementare
i ticket non manuali. Rimangono separatamente non autorizzati quota trial,
bulk capture, automazione live, pubblicazione e deploy.

Quel prompt era un handoff documentale ormai eseguito; i worker che si
riutilizzano nelle tranche di codice hanno ownership limitata e i loro
risultati vanno sempre verificati sul repository prima di un commit.
Le note e i vecchi prompt pre-grilling sotto restano fotografie storiche e non
riaprono decisioni già risolte. Il checkpoint canonico è in PLAN.md.

**Ricognizione indipendente eseguita:** [verbale pre-grilling del 10 ottobre](docs/reviews/2026-10-10-independent-pre-grilling-reconnaissance.md) — baseline `ebdc4f8`, matrice35/35, readback runtime e gap. Il grilling ha riaffermato la missione integrata e registrato zero reviewer editoriali/EUR10 mensili indicativi. **Ripresa attiva:** GPT-6 in Codex/ChatGPT-web e corpus storico prima (Hitler/Mussolini proposti); grilling su corpus/prove, poi ticket/automazioni economiche. Misure Antigravity/audio/locale dopo che il percorso funziona. Seguire gli aggiornamenti owner in PLAN e il checkpoint del verbale; nessuna infallibilità, pubblicazione automatica, bulk capture o spesa è approvata per inferenza.

Il nuovo agente deve **prima leggere e valutare tutto il prodotto**, il codice, la roadmap, il runtime e l'interfaccia con prove; non deve iniziare chiedendo informazioni già presenti nel repository. Solo dopo questa ricognizione usa le skill realmente presenti `~/.agents/skills/plan-grilling`, `plan-grill-with-docs` e `plan-domain-modeling`: albero delle decisioni, round delle domande indipendenti con risposta consigliata, conseguenze e documentazione delle scelte. Il redesign completo richiesto dal proprietario non va confuso con il lavoro già eseguito: prima chiarire missione, target, scope, contenuti autorizzati e costo umano; poi quattro direzioni di design distinte, prototipi desktop/mobile, confronto e piano di migrazione misurabile. L'attuale UI è ritenuta troppo generica dal proprietario, ma questo non autorizza a introdurre falsi dati o aggirare privacy e diritti.

## Confini non negoziabili

**Ultime risposte del grilling:** storico permanente; prima completare il percorso
acquisizione→trascrizioni/testo→catalogo→immissione→frontend→verifica/test,
poi raccolta massiva. La persona proposta è **l'owner**, circa cinque ore settimanali
indicative di controllo rapido soprattutto visivo/non testuale (es. immagini).
Non convertirle in revisione editoriale di tutti i fact-check. Lavoro testuale
inteso come automatizzato; autorità futura scelta nelle Q14/Q17, con ricerca
attiva prima della coda eccezioni e controlli verificabili. Foto/testo/verdetti
restano decisioni distinte; il runtime corrente non è migrato.

- Il runtime attuale mantiene i gate di pubblicazione; il target autonomo è da
  specificare nei ticket. Nessuna biometria o classifica di attendibilità delle persone.
- Provenienza e diritti espliciti prima di riusare fonti/transcript, anche se pubblicamente visibili.
- Gli attuali gate di review umana non sono stati modificati; i ticket devono
  specificarne la migrazione verso autorità automatica auditabile, senza fingere
  che l'owner offra revisione editoriale ordinaria o che l'implementazione sia fatta.
- Studio privata e dati non approvati non devono entrare nel bundle statico pubblico.
- Il sito informativo con indice legittimamente vuoto può essere un obiettivo distinto; le decisioni su privacy, titolarità, contatti e testi legali non possono essere dichiarate approvate per decreto tecnico.

## Comandi rapidi di ripresa

```bash
cd /Users/domenico/Code/DichiarazioniPubbliche.it
git fetch origin main && git status -sb && git branch -avv && git worktree list --porcelain && git stash list
python3 tools/report_ticket_status.py --json
python3 tools/check_launch_preflight.py --expect-no-go
python3 tools/check_repository_contract.py
python3 tools/check_licensing_inventory.py --check-hashes
```

Le vecchie fotografie del **3 ottobre** che apparivano in questo file sono state
rimosse dal percorso operativo perché generavano contraddizioni con le prove del 10 ottobre.
Non sono state cancellate dalla storia Git: leggere i commit precedenti o i
receipt datati in `docs/reviews/` soltanto per ricostruire una decisione storica.
