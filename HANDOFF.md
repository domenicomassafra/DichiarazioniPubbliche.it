# Dichiarazioni Pubbliche — handoff operativo attuale

**Checkpoint operativo aggiornato:** 11 ottobre 2026. Questo documento è la porta di ingresso operativa,
non una seconda fonte di verità per i ticket o una certificazione di release.

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

## Prossimo ciclo: backlog post-grilling, senza implementazione

**Risposte definitive registrate:** dichiarazioni pubbliche con parole esatte,
mai parafrasi sostitutive; riassunti separati; vista Persona × Tema con filtri
incrociati e sintesi citate; forte automazione anche sui documenti processuali;
più persone e lingue; storico permanente; continuità di fonti/temi ed eventi.
L'owner sceglierà il redesign. Autonomia finale di fact-check e futura pubblicazione
è il target dopo validation, non un gate runtime già attivato. L'ultima Q19
autorizza **solo creazione/modifica/aggiornamento dei ticket e documenti di piano**.
Nessuna implementazione, quota trial, bulk capture, automazione o deploy ora.

Il prompt corrente è un solo handoff esterno; il coordinatore avvierà quattro
worker tramite il tool nativo `agents`. Non sono quattro lanci manuali dell'owner.
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
