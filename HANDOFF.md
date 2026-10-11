# Dichiarazioni Pubbliche — handoff operativo attuale

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
