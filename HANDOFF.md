# Dichiarazioni Pubbliche — handoff operativo attuale

**Checkpoint:** 10 ottobre 2026. Questo documento è la porta di ingresso operativa,
non una seconda fonte di verità per i ticket o una certificazione di release.

## Leggere nell’ordine

0. [**Prompt unico post-grilling — quattro subagenti nativi, solo backlog**](tasks/prompt2prompt/20261010-231757-backlog-post-grilling/lane-01-backlog-master/001-backlog-master.prompt.md) — **mandato corrente per la nuova chat Chat On Steroids**. Grilling concluso; crea/aggiorna ticket e piano senza implementazione. Il precedente prompt audit/grilling/redesign resta storia del mandato precedente.
1. [`FINAL-PENDING-GRILLING-2026-10-10.md`](FINAL-PENDING-GRILLING-2026-10-10.md) — stato completo dei pending e prompt per il grilling nella prossima chat.
2. [`MEGA-HANDOFF-2026-10-10.md`](MEGA-HANDOFF-2026-10-10.md) — dettaglio delle prove e dei limiti, tabella della pipeline e analisi del rallentamento.
3. [`LAUNCH.md`](LAUNCH.md) — pubblicazione informativa essenziale **distinta** dalla release editoriale stabile.
4. [`PLAN.md`](PLAN.md) e [`docs/tickets/`](docs/tickets/) — registro **canonico** dei 125 ticket e delle acceptance criterion; mai modificare stati per semplificare i numeri.
5. [`PRODUCT.md`](PRODUCT.md), [`CONTEXT.md`](CONTEXT.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`AGENTS.md`](AGENTS.md) — invarianti, architettura e regole di lavoro.
6. [`docs/reviews/2026-10-10-open-ticket-reprioritization.md`](docs/reviews/2026-10-10-open-ticket-reprioritization.md) — decision queue 35/35: possibili accorpamenti e rinvii senza cancellare acceptance criterion.
7. [`docs/reviews/2026-10-10-ux-redesign-audit-and-brief.md`](docs/reviews/2026-10-10-ux-redesign-audit-and-brief.md) — critica verificata del frontend, quattro direzioni visuali alternative e redesign da decidere **solo dopo il grilling**.

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
