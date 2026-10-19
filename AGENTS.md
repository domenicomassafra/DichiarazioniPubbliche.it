# AGENTS.md

Carica prima `~/.dstack/contracts/shared-root/AGENTS.md`. Qui ci sono solo regole specifiche di Dichiarazioni Pubbliche.

## Prodotto e tracker

Dichiarazioni Pubbliche conserva dichiarazioni pubbliche con provenienza, evidenze, revisione, correzioni e output pubblico verificabile. Non è un ranking di persone e non pubblica automaticamente output di modelli.

Repository e tracker operativo: `https://github.com/domenicomassafra/DichiarazioniPubbliche.it`. Dal 17/10/2026 GitHub Issues è l'autorità per lavoro corrente, stato, acceptance e ricevute. Prima di modificare codice leggi body e commenti della issue assegnata. `PLAN.md` e `docs/tickets/DP-*.md` sono storia del backlog precedente: non aggiornarne stato o acceptance.

## Riuso prima di tutto (regola dell'owner, 15/10/2026)

Prima di scrivere codice per una funzione, cerca chi l'ha già fatto: repository GitHub/GitLab, pacchetti npm/PyPI/crates, issue e PR di altri progetti che risolvono lo stesso problema. Registra nella issue i candidati con link, licenza, ultimo rilascio e attività. Adotta il pacchetto, oppure forka/clona il repository e adattalo; scrivi codice proprio solo per la parte mancante e con il motivo scritto nella issue. Licenze: annota obblighi (MIT/Apache/BSD ok; LGPL/MPL/GPL/AGPL vanno segnalati all'orchestratore prima dell'adozione). Mantieni la provenienza (repo, commit, licenza) in un file di donor del progetto.

Ordine di lettura per ogni ticket:

1. issue GitHub assegnata, inclusi i commenti;
2. `PRODUCT.md`;
3. `CONTEXT.md`;
4. `ARCHITECTURE.md`;
5. `README.md`, ADR e documenti specifici dell'area toccata.

## Architettura in 5 righe

1. Backend Python in `poc/dichiarazioni_pubbliche`; PostgreSQL è store operativo e queue dove richiesto.
2. Flusso: source -> capture/transcript -> statement/claim -> evidence -> verifica -> review -> public projection.
3. Il web è Astro statico in `web/` e legge solo la proiezione pubblica approvata.
4. Il checkout Git autorevole è `/Users/domenico/Code/DichiarazioniPubbliche.it`; il runtime autorevole è il MiniPC.
5. Il MiniPC usa il mirror non-Git `/home/udodo/src/DichiarazioniPubbliche.it`; GitHub CI non fa deploy.

## Comandi

Toolchain supportata: Python 3.11, 3.12, 3.13 o 3.14; Node 24 + npm per `web/`. PostgreSQL serve solo ai ticket che richiedono esplicitamente un test DB isolato.

Setup locale sul Mac Studio:

```bash
python3 -V
. "$HOME/.nvm/nvm.sh" && nvm use 24
node -v && npm -v
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cd web && npm ci && cd ..
```

Build package e web di test:

```bash
. "$HOME/.nvm/nvm.sh" && nvm use 24
.venv/bin/python -m build --outdir /tmp/dichiarazioni-pubbliche-dist
cd web && DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build && cd ..
```

Test mirati per modifiche a contratto/repository/documentazione come questo file:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_repository_contract -v
python3 tools/check_repository_contract.py
```

Per codice applicativo esegui prima il modulo `tests.test_*` che copre il seam modificato; poi esegui sempre il gate finale completo:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q poc tests
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest discover -s tests
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_contributor_acceptance.py
. "$HOME/.nvm/nvm.sh" && nvm use 24
cd web && npm run check && DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build && npm run check:projection-boundary && cd ..
git diff --check
git status --short --branch
```

Esiti attesi: compile silenzioso; unittest termina `OK`; benchmark `5/5` e `100%`; contributor acceptance termina `OK: contributor acceptance satisfied.`; Astro check senza errori; build demo riuscita e non indicizzabile; projection-boundary verde; `git diff --check` senza output.

La demo è solo test. Una build pubblicabile richiede una proiezione approvata e usa `DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH=/percorso/assoluto/index.json`; `DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION` deve essere assente.

## Consegna e installazione

Sequenza obbligatoria: issue -> branch breve -> test -> push -> PR verso `main` -> required CI verde -> acceptance della issue -> merge -> readback di `origin/main` -> eventuale installazione -> prova reale -> ricevuta e chiusura issue. Una CI verde non installa nulla.

Il runtime si installa sul MiniPC nel mirror `/home/udodo/src/DichiarazioniPubbliche.it`. Non esiste un singolo comando canonico di deploy nel repository: usa la procedura candidata -> verifica -> swap con rollback prevista dal ticket/runbook, senza sincronizzare direttamente una working tree sporca. Dopo una promozione runtime, questi readback sono obbligatori:

```bash
ssh minipc 'systemctl --user is-active dichiarazioni-pubbliche-web.service'
ssh minipc 'curl -fsS --max-time 5 http://127.0.0.1:18090/api/v1/health'
curl -fsS --max-time 10 -o /dev/null -w 'public_http=%{http_code}\n' https://dichiarazionipubbliche.it/
```

Il servizio web usa `deploy/systemd/dichiarazioni-pubbliche-web.service`, serve `/home/udodo/src/DichiarazioniPubbliche.it/web/dist`, legge `/home/udodo/.local/share/dichiarazioni-pubbliche/public/v1/index.json` e ascolta su `127.0.0.1:18090`. Per una modifica solo documentale come `AGENTS.md`, il merge su `main` è l'installazione: il MiniPC non va mutato.

## Non toccare

- Non bypassare publication, provenance, rights, privacy o review gate.
- Non introdurre person score, ranking politico o identificazione biometrica.
- Non esporre transcript/evidence body, credenziali o dump operativi nel pubblico.
- Non usare una demo projection in produzione.
- Non modificare produzione o migrazioni live per far passare un test.
- Non aggiornare gli stati nei vecchi `PLAN.md` o `docs/tickets/DP-*.md`.
- Non rinominare `poc/`, `dichiarazioni_pubbliche` o gli identificatori package fuori da un ticket che lo autorizza.
