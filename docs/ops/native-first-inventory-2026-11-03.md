# DP #587 — inventario operativo native-first, 3 novembre 2026

Snapshot sorgenti: origin/main 903f19a552ed7a6ef6e8478d187859436ba55749; esecuzione sul worktree Studio fix/587-native-first.
Criterio: file Git tracciati che configurano strumenti, avviano operazioni, rappresentano hook/workflow/timer/patch, e adattatori esterni di primo livello. Esclusi i moduli di logica interna non esposti come wrapper e i documenti storici.
Perimetro esaminato: 200 entrypoint; NATIVE=22, REPLACE=2, GAP=176.

NATIVE = file conforme a funzionalita nativa; REPLACE = alternativa identica usata senza shim; GAP = il tool nativo lascia una invariante del dominio scoperta. Le classi GAP non sono autorizzazioni a nuove dipendenze.

## Sostituzione effettiva

- REPLACE: deploy/ops/provider_outage_drill.sh — eliminato; il modulo Python dichiarazioni_pubbliche.ops.provider_outage_drill gestisce direttamente opzioni, errori e verifica fail-closed. Chiamanti: tests/test_ops_provider_outage.py, docs/ops/cost-and-provider-outage.md e registro threats.py aggiornati. Il vecchio riferimento in docs/tickets/DP-506-* e storia, non un chiamante.
- Studio: test focalizzati su Python 3.14 via ControlCenter resource guard: 7/7 PASS. Il modulo ritorna exit 2 per URL vuoto/assente senza avviare psql; nessuna chiamata provider.

- REPLACE: tools/extract_passage_candidates.py — eliminato; era un alias che importava ed eseguiva soltanto main da tools/extract_research_candidates.py. Nessun chiamante attivo dipende dal nome storico; la guida operativa docs/ops/private-candidate-extraction-20261008.md ora invoca direttamente la CLI custodita. Le note storiche DP-211 restano documentazione delle decisioni precedenti.

## Dipendenze e comportamento dei quattro host

- Mac Studio: Orca 1.4.243, gh 2.103.3, checkout Git main pulito al preflight; worktree di questa issue creato sullo Studio; nessun gateway o servizio DP rilevato da launchctl.
- MiniPC: systemd 259, web user service active, HTTP loopback /api/v1/health status ok, timer source-poll/worker/health/daily attivi. Il servizio live legge host-release/current, senza uso del wrapper rimosso.
- MateBook Linux: checkout main pulito; servizi nativi DP non installati in questa sessione. Il suo gh su mise shim non ha restituito output utile: le operazioni GitHub usano gh sul MiniPC/Studio.
- MacBook Air Omarchy: nessun checkout DP e nessun servizio DP user installato. Nessuna installazione applicativa richiesta per il solo CLI del drill.
- Il MiniPC possiede anche edge-guard.service/.timer, ma la loro fonte tracciata e ControlCenter/config/systemd e fleet/policy/fleet.v1.json, non questo repository. Ogni sostituzione di quel guard richiede la modifica nel repository proprietario.

## Evidenza delle alternative native

- S-GH-ISSUE — GitHub Issue Forms, documentazione ufficiale verificata 2026-11-03: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository
- S-GHA — GitHub Actions workflow syntax, concurrency/cancel-in-progress e runner, verificata 2026-11-03: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- S-PROJECT — GitHub Projects Auto-add e GraphQL single-select, verificate 2026-11-03: https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/adding-items-automatically ; https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects
- S-SYSTEMD — systemd.timer(5) ufficiale, OnCalendar/OnUnitActiveSec/Persistent, verificato 2026-11-03 con systemd 259 sul MiniPC: https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html
- S-ASTRO — Astro integrations/hook e native build: https://docs.astro.build/en/reference/integrations-reference/ ; https://docs.astro.build/en/guides/deploy/ (consultate 2026-11-03).
- S-PY — Python -m CLI ufficiale (verificato 2026-11-03) e modulo argparse/test reale: https://docs.python.org/3.12/using/cmdline.html
- S-POSTGRES — strumenti nativi pg_dump/pg_restore v18 docs (consultati 2026-11-03): https://www.postgresql.org/docs/current/app-pgdump.html ; https://www.postgresql.org/docs/current/app-pgrestore.html
- S-PLAYWRIGHT — Playwright browserContext.offline limita solo le richieste del browser; non equivale a namespace OS: https://playwright.dev/python/docs/api/class-browsercontext (consultato 2026-11-03).
- S-ORCA — Orca 1.4.243, output nativo orca agent-context --help letto via SSH Studio il 2026-11-03.
- S-LOCAL — implementazione tracciata in origin/main (SHA sopra), lettura del comando/config e relativi chiamanti il 2026-11-03.

## Inventario puntuale

I file sono raggruppati in quattro tabelle per rispettare il limite di dimensione dei file del repository. Tutte le 200 righe appartengono allo stesso audit e condividono le fonti S-... indicate sopra.

- Questa pagina: workflow, configurazione, deploy e runtime Python (54 righe).
- [Operator CLI e strumenti A](native-first-inventory-tools-a-2026-11-03.md) (44 righe).
- [Operator CLI e strumenti B](native-first-inventory-tools-b-2026-11-03.md) (44 righe).
- [Configurazione web e QA Astro](native-first-inventory-web-2026-11-03.md) (58 righe).

| Percorso | Funzione osservata | Tool o alternativa nativa | Classe | Evidenza e motivazione |
| --- | --- | --- | --- | --- |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | bug_report.yml | GitHub form/template | **NATIVE** | S-GH-ISSUE: schema di template supportato direttamente da GitHub |
| `.github/ISSUE_TEMPLATE/config.yml` | config.yml | GitHub form/template | **NATIVE** | S-GH-ISSUE: schema di template supportato direttamente da GitHub |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | feature_request.yml | GitHub form/template | **NATIVE** | S-GH-ISSUE: schema di template supportato direttamente da GitHub |
| `.github/labels.v1.json` | labels.v1.json | GitHub governance | **GAP** | S-PROJECT: snapshot/versionamento delle regole di dominio che il solo stato live GitHub non offre come file dichiarativo |
| `.github/pull_request_template.md` | pull_request_template.md | GitHub form/template | **NATIVE** | S-GH-ISSUE: schema di template supportato direttamente da GitHub |
| `.github/triage-policy.v1.json` | triage-policy.v1.json | GitHub governance | **GAP** | S-PROJECT: snapshot/versionamento delle regole di dominio che il solo stato live GitHub non offre come file dichiarativo |
| `.github/workflows/agent-file-size.yml` | agent-file-size.yml | GitHub Actions + checker | **GAP** | S-GHA: Actions orchestra nativamente, ma non fornisce il gate di dimensione file con questa policy |
| `.github/workflows/ci.yml` | ci.yml | GitHub Actions | **NATIVE** | S-GHA: workflow e concurrency native; i check proprietari restano test di dominio |
| `.github/workflows/owner-project-auto-add.yml` | owner-project-auto-add.yml | GitHub Projects | **GAP** | S-PROJECT: auto-add nativo copre inserimento, non il campo single-select Prodotto/Repo; GraphQL ne conserva il valore |
| `.gitignore` | .gitignore | Agent/Git file native | **NATIVE** | S-LOCAL: file di configurazione letto direttamente dal tool |
| `AGENTS.md` | AGENTS.md | Agent/Git file native | **NATIVE** | S-LOCAL: file di configurazione letto direttamente dal tool |
| `config/candidate-extraction.v1.json` | candidate-extraction.v1.json | DP domain policies | **GAP** | S-LOCAL: dati dichiarativi di policy e diritti del prodotto; nessun servizio esterno da riconfigurare |
| `config/claim-extraction.v1.json` | claim-extraction.v1.json | DP domain policies | **GAP** | S-LOCAL: dati dichiarativi di policy e diritti del prodotto; nessun servizio esterno da riconfigurare |
| `config/evidence-requirements.v1.json` | evidence-requirements.v1.json | DP domain policies | **GAP** | S-LOCAL: dati dichiarativi di policy e diritti del prodotto; nessun servizio esterno da riconfigurare |
| `config/evidence-sources.v1.json` | evidence-sources.v1.json | DP domain policies | **GAP** | S-LOCAL: dati dichiarativi di policy e diritti del prodotto; nessun servizio esterno da riconfigurare |
| `config/garlasco-public-discovery-leads.v1.json` | garlasco-public-discovery-leads.v1.json | DP domain policies | **GAP** | S-LOCAL: dati dichiarativi di policy e diritti del prodotto; nessun servizio esterno da riconfigurare |
| `config/garlasco-source-feasibility-wave22.v1.json` | garlasco-source-feasibility-wave22.v1.json | DP domain policies | **GAP** | S-LOCAL: dati dichiarativi di policy e diritti del prodotto; nessun servizio esterno da riconfigurare |
| `config/garlasco-source-governance-wave26.v1.json` | garlasco-source-governance-wave26.v1.json | DP domain policies | **GAP** | S-LOCAL: dati dichiarativi di policy e diritti del prodotto; nessun servizio esterno da riconfigurare |
| `config/privacy-field-inventory.v1.json` | privacy-field-inventory.v1.json | DP domain policies | **GAP** | S-LOCAL: dati dichiarativi di policy e diritti del prodotto; nessun servizio esterno da riconfigurare |
| `config/source-intelligence.v1.json` | source-intelligence.v1.json | DP domain policies | **GAP** | S-LOCAL: dati dichiarativi di policy e diritti del prodotto; nessun servizio esterno da riconfigurare |
| `config/source-registry.v1.json` | source-registry.v1.json | DP domain policies | **GAP** | S-LOCAL: dati dichiarativi di policy e diritti del prodotto; nessun servizio esterno da riconfigurare |
| `config/transcription-policy.v1.json` | transcription-policy.v1.json | DP domain policies | **GAP** | S-LOCAL: dati dichiarativi di policy e diritti del prodotto; nessun servizio esterno da riconfigurare |
| `deploy/apparmor/dp-browser-bwrap` | dp-browser-bwrap | AppArmor policy | **NATIVE** | S-LOCAL: profilo nativo AppArmor; non e un launcher proprietario |
| `deploy/ops/backup.sh` | backup.sh | PostgreSQL e verifica DP | **GAP** | S-POSTGRES: pg_dump/pg_restore nativi gia usati; manifest diritti, conteggi e restore DR sono invarianti propri |
| `deploy/ops/provider_outage_drill.sh` | provider_outage_drill.sh | Python -m | **REPLACE** | S-PY: shell shim duplicava una CLI Python che accetta gia gli argomenti e respinge DB non espliciti |
| `deploy/ops/restore_drill.sh` | restore_drill.sh | PostgreSQL e verifica DP | **GAP** | S-POSTGRES: pg_dump/pg_restore nativi gia usati; manifest diritti, conteggi e restore DR sono invarianti propri |
| `deploy/ops/verify_projection_bundle.py` | Verify a generated public projection bundle is internally consistent. Stdlib onl | PostgreSQL e verifica DP | **GAP** | S-POSTGRES: pg_dump/pg_restore nativi gia usati; manifest diritti, conteggi e restore DR sono invarianti propri |
| `deploy/systemd/dichiarazioni-pubbliche-health.service` | dichiarazioni-pubbliche-health.service | systemd user units | **NATIVE** | S-SYSTEMD: unit/service/timer nativi con scheduling gestito da systemd |
| `deploy/systemd/dichiarazioni-pubbliche-health.timer` | dichiarazioni-pubbliche-health.timer | systemd user units | **NATIVE** | S-SYSTEMD: unit/service/timer nativi con scheduling gestito da systemd |
| `deploy/systemd/dichiarazioni-pubbliche-source-poll-daily.service` | dichiarazioni-pubbliche-source-poll-daily.service | systemd user units | **NATIVE** | S-SYSTEMD: unit/service/timer nativi con scheduling gestito da systemd |
| `deploy/systemd/dichiarazioni-pubbliche-source-poll-daily.timer` | dichiarazioni-pubbliche-source-poll-daily.timer | systemd user units | **NATIVE** | S-SYSTEMD: unit/service/timer nativi con scheduling gestito da systemd |
| `deploy/systemd/dichiarazioni-pubbliche-source-poll.service` | dichiarazioni-pubbliche-source-poll.service | systemd user units | **NATIVE** | S-SYSTEMD: unit/service/timer nativi con scheduling gestito da systemd |
| `deploy/systemd/dichiarazioni-pubbliche-source-poll.timer` | dichiarazioni-pubbliche-source-poll.timer | systemd user units | **NATIVE** | S-SYSTEMD: unit/service/timer nativi con scheduling gestito da systemd |
| `deploy/systemd/dichiarazioni-pubbliche-web.service` | dichiarazioni-pubbliche-web.service | systemd user units | **NATIVE** | S-SYSTEMD: unit/service/timer nativi con scheduling gestito da systemd |
| `deploy/systemd/dichiarazioni-pubbliche-worker.service` | dichiarazioni-pubbliche-worker.service | systemd user units | **NATIVE** | S-SYSTEMD: unit/service/timer nativi con scheduling gestito da systemd |
| `deploy/systemd/dichiarazioni-pubbliche-worker.timer` | dichiarazioni-pubbliche-worker.timer | systemd user units | **NATIVE** | S-SYSTEMD: unit/service/timer nativi con scheduling gestito da systemd |
| `orca.yaml` | orca.yaml | Orca 1.4.243 | **NATIVE** | S-ORCA: config di setup supportata dal runtime Orca |
| `poc/dichiarazioni_pubbliche/asr_router.py` | asr_router.py | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/browser_renderer_netns.sh` | browser_renderer_netns.sh | Playwright + bubblewrap | **GAP** | S-PLAYWRIGHT: offline emulation non isola tutte le forme di rete e il filesystem come un namespace OS |
| `poc/dichiarazioni_pubbliche/caption_adapter.py` | caption_adapter.py | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/capture_archivebox_adapter.py` | Opt-in ArchiveBox v0.9.73 process adapter for rights-cleared HTML captures. Runs | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/capture_monolith_adapter.py` | Opt-in, private single-file HTML snapshot via the unmodified Monolith CLI. Monol | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/capture_trafilatura_adapter.py` | Opt-in, offline Trafilatura adapter for already authorized HTML captures. This m | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/diarization_candidate_adapter.py` | #166: opt-in, offline, *anonymous* diarization candidate adapter. No weights/dow | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/parliamentary_official_adapter.py` | DP-233 pure normalizer for official parliamentary speech records. The adapter co | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/public_api.py` | Static-first read-only HTTP API over validated public projections. DP-402/DP-105 | DP runtime | **GAP** | S-SYSTEMD: logica del servizio o scheduling applicativo distinta dal timer host |
| `poc/dichiarazioni_pubbliche/public_http_client.py` | public_http_client.py | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/scheduler.py` | scheduler.py | DP runtime | **GAP** | S-SYSTEMD: logica del servizio o scheduling applicativo distinta dal timer host |
| `poc/dichiarazioni_pubbliche/scheduler_daemon.py` | scheduler_daemon.py | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/source_watch_pg_queue_adapter.py` | DP-515 PostgreSQL watch CAS and atomic held-review canonical queue adapter. Opt- | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/wikidata_proposal_adapter.py` | Opt-in private Wikidata lookup: review proposals, never identity authority. Wiki | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/worker_daemon.py` | worker_daemon.py | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `poc/dichiarazioni_pubbliche/youtube_transcript_client.py` | Optional bounded public-caption client; no cookies or proxy bypass. | Python adapters/workers | **GAP** | S-PY: contratto applicativo tra fonti, provider, code e provenienza; non un launcher duplicato |
| `pyproject.toml` | pyproject.toml | Python packaging | **NATIVE** | S-PY: schema packaging nativo, wheel/sdist attraverso build standard |

## Controlli per la chiusura

- Il file censito va comparato con il commit effettivo della PR prima del merge; nuovi entrypoint aggiunti dopo questo SHA richiedono revisione della classificazione.
- I GAP di dominio devono mantenere controlli dei diritti e fail-closed. Il Project #1 richiede il campo Prodotto/Repo: il solo auto-add nativo perderebbe quell informazione.
- Merge consentito dopo CI richiesta verde; per host-config/deployment eventuali modifiche successive servono review indipendente e installazione verificata.
