# DichiarazioniPubbliche.it — istruzioni del repository

Leggere prima `~/.dstack/contracts/shared-root/AGENTS.md` e la issue GitHub assegnata con tutti i commenti. GitHub Issues è la fonte per criteri e stato; `PLAN.md` e `docs/tickets/DP-*.md` documentano specifiche storiche. Non aggiornare i loro stati. Seguire anche `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md` e gli ADR pertinenti.

## Architettura e ambienti

- Backend Python: `poc/dichiarazioni_pubbliche/`; test: `tests/`; contratti/API: `docs/api/`; configurazione fonti: `config/`.
- Flusso: fonte → acquisizione/trascrizione → statement/claim → evidenze → verifica → revisione → proiezione pubblica.
- PostgreSQL conserva stato operativo e code quando previsto; il web Astro in `web/` legge solo una proiezione esplicitamente approvata.
- Git autorevole: `domenicomassafra/DichiarazioniPubbliche.it`, branch `main`. Lavorare sul Mac Studio in `~/Code/.worktrees/DichiarazioniPubbliche.it-<issue>` da `origin/main`; il checkout condiviso potrebbe contenere WIP di altri.
- Consumer MiniPC: mirror non-Git `/home/udodo/src/DichiarazioniPubbliche.it`; servizio `dichiarazioni-pubbliche-web.service` su `127.0.0.1:18090`. GitHub CI non installa il consumer.

## Comandi di verifica

Toolchain: Python 3.11–3.14 e Node 24. Eseguire `npm ci`, test e build solo sul Mac Studio, sempre tramite `python3 ~/.local/share/controlcenter/resource-guard/workload_launcher.py build -- <comando>`; il MiniPC è riservato a runtime Linux, servizi e verifiche di readback.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_repository_contract -v
python3 tools/check_repository_contract.py
PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q poc tests
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest discover -s tests
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_contributor_acceptance.py
cd web && npm run check && DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build && npm run check:projection-boundary
```

Per ogni modifica eseguire prima i test mirati dell'area, poi i gate pertinenti. Prima del push verificare `git diff --check`. Per pubblicare: diff, rebase su `origin/main`, push, SHA remoto riletto; installare con la procedura candidata → verifica → swap con rollback prevista dal runbook del consumer.

Readback runtime:

```bash
systemctl --user is-active dichiarazioni-pubbliche-web.service
curl -fsS --max-time 5 http://127.0.0.1:18090/api/v1/health
curl -fsS --max-time 10 -o /dev/null -w 'http=%{http_code}\n' https://dichiarazionipubbliche.it/
```

## Confini del prodotto

- Pubblicazione, provenienza, diritti, privacy e review sono gate obbligatori; un output AI è sempre candidato fino all'approvazione.
- Niente punteggi delle persone, identificazione biometrica, profili politici inferiti o contenuti privati esposti nel web.
- Niente proiezione demo in produzione, né modifica di DB live per passare i test.
- Riusare implementazioni esistenti e upstream compatibili; registrare licenze e provenienza dei donor.
- Decisioni owner e autorizzazioni specifiche sono nelle issue; non inventare permessi o costi. Il design visivo finale è riservato a un intervento successivo dell'owner.

## Modello LLM unico (decisione owner del 23/10/2026)
Per ora tutto funziona con **Gemini 3.8 Flash tramite Antigravity**, passando da OmniRoute. Nessuna API esterna: niente OpenRouter, Groq, Cerebras, Cloudflare AI, Cohere, Gemini Developer API o altri provider diretti, né a pagamento né free. Codice, config e documenti che prevedono altre route vanno allineati a questa scelta; un'eccezione richiede una nuova decisione esplicita dell'owner.

## Senato Akoma Ntoso: fonte aperta, sola Discovery privata (owner 24/10/2026)

Per il solo commit `bfac144eb5c54820971bc1020fece11aae56ec90`
di `SenatoDellaRepubblica/AkomaNtosoBulkData`, README/Licenza ufficiali
CC BY 4.0 e blob esatto verificati automaticamente bastano per registrare
`DISCOVER_METADATA` privato e attribuzione; non inventare un attestatore
umano o una nuova firma personale. Usare il registro versionato/revocabile,
le evidenze hash e il perimetro di `docs/ops/dp326-studio-discovery-metadata-rights-20261024.md`.
Questa decisione non concede capture del body, modelli, review o pubblicazione;
fonti differenti continuano a seguire i loro controlli specifici.
