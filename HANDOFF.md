# Dichiarazioni Pubbliche — handoff operativo attuale

**Checkpoint:** 10 ottobre 2026. Questo documento è la porta di ingresso operativa,
non una seconda fonte di verità per i ticket o una certificazione di release.

## Leggere nell’ordine

1. `FINAL-PENDING-GRILLING-2026-10-10.md` — stato dei pending, decisioni e domande per la prossima chat (quando presente).
2. [`MEGA-HANDOFF-2026-10-10.md`](MEGA-HANDOFF-2026-10-10.md) — dettaglio delle prove e dei limiti, tabella della pipeline e analisi del rallentamento.
3. [`LAUNCH.md`](LAUNCH.md) — pubblicazione informativa essenziale **distinta** dalla release editoriale stabile.
4. [`PLAN.md`](PLAN.md) e [`docs/tickets/`](docs/tickets/) — registro **canonico** dei 125 ticket e delle acceptance criterion; mai modificare stati per semplificare i numeri.
5. [`PRODUCT.md`](PRODUCT.md), [`CONTEXT.md`](CONTEXT.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`AGENTS.md`](AGENTS.md) — invarianti, architettura e regole di lavoro.

## Stato verificato al 10 ottobre (ricontrollare live)

- **Sorgente autorevole:** `/Users/domenico/Code/DichiarazioniPubbliche.it`; repo GitHub `domenicomassafra/DichiarazioniPubbliche.it`.
- **Git al checkpoint:** `main` locale e `origin/main` al commit `a66e987`; nessun altro branch/worktree/stash e working tree pulito. `git log -1` prevale sulla fotografia storica.
- **CI GitHub:** esecuzione `38072548106` sul commit `a66e987`: success.
- **Ticket al checkpoint:** 125 totali; 90 DONE, 20 IN PROGRESS, 6 BLOCKED, 9 FUTURE; 35 non DONE.
- **Test integrati già eseguiti:** Python 2390/2390 PASS; benchmark deterministico 5/5 PASS. Non equipararli al canary di un corpus reale.
- **Release v1:** `tools/check_launch_preflight.py --expect-no-go` segnala 49 blocker. Non pubblicare claim o dati di diritti non approvati.
- **HTTPS:** online, ma risposta verificata il 10 ottobre segnalava file datati 7 ottobre: GitHub push e deploy web **non sono la stessa cosa**.
- **Runtime autorevole:** MiniPC, mirror non-Git `/home/udodo/src/DichiarazioniPubbliche.it`; PostgreSQL `dichiarazioni_pubbliche`. Non inferire deploy MiniPC da un nuovo SHA Git.

## Confini non negoziabili

- Nessuna pubblicazione automatica, identificazione biometrica o classifica di attendibilità delle persone.
- Provenienza e diritti espliciti prima di riusare fonti/transcript, anche se pubblicamente visibili.
- Review e quote/autorialità/verifica umane **prima** di promuovere un candidato a pubblicazione.
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
