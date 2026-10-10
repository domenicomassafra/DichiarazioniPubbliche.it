# Runtime Scheduler + OmniRoute Canary

Data: 2026-09-22.

## OmniRoute claim-extraction canary

Target mantenuto dall'handoff:

`antigravity/gemini-3.8-flash-tiered`

Diagnosi aggiornata sul MiniPC:

- `omniroute.service` è attivo come **user service**; il system service omonimo non è l'autorità corretta;
- produzione corrente: artefatto ufficiale OmniRoute **3.8.50**;
- `/healthz` risponde 200;
- il catalogo live contiene la route target;
- un canary minimale `Return exactly OK` sulla route tiered risponde 200;
- la stessa route rifiuta però richieste reali/non banali con 400 o timeout, anche con prompt neutri molto brevi;
- la route non-tiered `antigravity/gemini-3.8-flash` non è un sostituto: il path diretto osservato restituisce 400;
- i call-log storici sani mostrano richieste tiered anche molto grandi passate tramite `policy-antigravity-gemini-3.8-flash-primary`;
- i tentativi odierni falliti non mostrano quel combo step;
- il runbook ControlCenter documenta che il precedente runtime 3.8.51 conteneva una patch runtime-only per il tiered Flash quota path e classifica quel runtime come **LOCAL-FORK**;
- la policy corrente vieta di chiudere il gap tramite build/source fork: bisogna attendere/usare il primo artefatto ufficiale che contiene o supersede il fix.

È stato effettuato anche un cutover diagnostico **reversibile** verso il runtime 3.8.51 già presente sul MiniPC: la readiness è arrivata lentamente e la prima richiesta reale ha chiuso la connessione. Il symlink è stato quindi ripristinato automaticamente all'artefatto ufficiale 3.8.50; nessun sorgente vendor è stato modificato.

Conclusione: il benchmark claim-extraction rimane **OPEN/BLOCKED DAL RUNTIME UFFICIALE**. L'harness di benchmark esiste ora nel repository, ma non vengono inventate metriche finché la stessa route non completa una richiesta reale end-to-end.

## Scheduler daemon v0

Implementazione:

`poc/dichiarazioni_pubbliche/scheduler_daemon.py`

È volutamente un processo **one-shot**; la ricorrenza appartiene al timer di sistema.

Proprietà:

- legge il Source Registry;
- rispetta `poll_minutes` usando `source_health.checked_at`;
- applica backoff esponenziale fino a 16x dopo failure consecutive;
- discovery economica prima di ogni lavoro semantico;
- non scarica né sonda media nel processo scheduler;
- crea ContentItem e ContentLocator deterministici;
- enqueue idempotente tramite il contract PostgreSQL già esistente;
- limita i nuovi job per run;
- blocca nuovi enqueue quando il costo giornaliero globale o per-source ha già raggiunto il cap;
- aggiorna `source_health` in HEALTHY / DEGRADED / FAILED;
- una fonte non supportata viene saltata esplicitamente invece di essere trattata come successo.

Unit file:

- `deploy/systemd/dichiarazioni-pubbliche-source-poll.service`
- `deploy/systemd/dichiarazioni-pubbliche-source-poll.timer`

Il timer può girare ogni 5 minuti perché il daemon decide autonomamente quali fonti sono realmente in scadenza. Questo permette cadence diverse nel registry senza creare un timer per sorgente.

## Config runtime

Il service può leggere:

`~/.config/dichiarazioni-pubbliche/runtime.env`

Variabile prevista:

`DICHIARAZIONI_PUBBLICHE_DATABASE_URL`

Il file è runtime-only e non va committato.

Default applicativi correnti:

- max 20 nuovi job per run;
- max 5 USD di costo osservato al giorno;
- max 1 USD di costo osservato per source al giorno.

I cap sono circuit breaker, non target di spesa. Il budget viene misurato dai `provider_receipt`; se il cap è raggiunto, i contenuti possono ancora essere scoperti e persistiti ma il lavoro costoso resta fuori dalla queue.

## Runtime proof MiniPC

Runtime authority verificata il 2026-09-22:

- database PostgreSQL dedicato: `dichiarazioni_pubbliche`;
- owner locale: `udodo`, peer auth, nessuna password aggiuntiva nel progetto;
- schema applicato: 21 tabelle;
- primo poll forzato Pulp, limit 5: 5 discovered, 5 content upsert, 5 job nuovi;
- secondo poll identico: 5 discovered, 5 content upsert, **0 job nuovi**, 5 duplicate job riconosciute;
- stato DB dopo i due poll: 5 `content_item`, 5 `content_locator`, 5 `processing_job`;
- `source_health` Pulp: `HEALTHY`, 0 failure consecutive;
- timer user systemd `dichiarazioni-pubbliche-source-poll.timer`: enabled + active (waiting);
- `Linger=yes` per l'utente runtime, quindi il user manager non dipende da una sessione desktop interattiva;
- run service non-forzato: Pulp `SKIPPED_NOT_DUE`, source social Giuliani `SKIPPED_UNSUPPORTED`, exit 0.

Il repository runtime sincronizzato sul MiniPC è:

`/home/udodo/src/DichiarazioniPubbliche.it`

Questa prova copre discovery, persistenza, idempotenza queue, cadence e installazione timer. Non implica che i worker downstream di transcript/claim extraction siano già automatizzati end-to-end.

## Research Discovery Runs v1 — 2026-09-29

DP-209 adds a second, intentionally different orchestration contract above ordinary source
polling. Source polling answers “what is new on configured sources?”; a Research Discovery
Run answers a **saved bounded research question**. It persists the manifest and every query
before execution, then records one run receipt, one attempt receipt per query/adapter and a
disposition for every returned hit.

Current executable adapter `configured_registry` reuses the existing Source Registry and
DP-206 adapters. It does not download arbitrary media or launch browser sessions. Missing
future adapters are recorded `BLOCKED/ADAPTER_UNAVAILABLE`; provider errors, rate limits
and budget gates stay explicit rather than becoming a clean empty result.

Operational entry point:

```text
PYTHONPATH=poc python3 tools/run_research_discovery.py \
  --database-url postgresql:///dichiarazioni_pubbliche \
  --manifest <research-discovery-manifest.json>
```

Manifest v1 bounds queries, seeds, source families, date window, total/per-host results and
USD cost. Every adapter declares a pre-call cost upper bound. A RUNNING attempt found after
a crash is not automatically retried because the external call/cost may already have
happened; it is reconciled to `ATTEMPT_RECONCILIATION_REQUIRED`.

MiniPC acceptance on 2026-09-29 proved two distinct runs of one creator-metadata manifest:
first run 2 NEW Content, second run the same 2 as EXISTING, with separate run receipts and
zero downstream jobs/claims/evidence/findings. A second canary proved HOST_LIMIT,
RESULT_LIMIT, RATE_LIMITED and pre-call cost blocking; a crash canary proved zero repeated
provider calls. Production migration/replay preserved the baseline digest and the
production canary was fully removed afterward. Post-rollout suite 846/846, verification
benchmark 5/5 and corpus-search benchmark 13/13 Recall@5 passed.

## Capture / preservation / parser v1 — 2026-09-29

DP-210 turns an accepted Content URL into a private immutable observed representation.
The normal written path is: bounded safe HTTPS fetch -> per-Capture private body object ->
`content_capture` hash receipt -> deterministic visible-text parse -> bounded `Passage`
selectors/hash. No claim extraction happens in this stage.

Operational entry point:

```text
PYTHONPATH=poc python3 tools/capture_content.py \
  --database-url postgresql:///dichiarazioni_pubbliche \
  --content-id <existing-content-id> \
  --url https://... \
  --storage-root ~/.local/share/dichiarazioni-pubbliche-captures \
  --retention-class EPHEMERAL
```

`EPHEMERAL` is the CLI default for raw body bytes. Lifecycle/rights policy from DP-118
still governs deletion; the pipeline does not invent a legal retention period. Browser and
archive integrations are adapter seams only. Browser fallback runs only after an HTML parse
failure; archive failure cannot invalidate a successfully captured/parsed page.

Changed bytes produce a new Capture hash; unchanged observation reuses the Capture and
appends `CAPTURE_REOBSERVED`. Parser failures append `PARSE_FAILED`; browser failure
appends `BROWSER_FALLBACK_FAILED`. Passage offsets are defined over deterministic canonical
text reproducible from the captured bytes/parser version and can be checked with
`verify_passage_roundtrip()`.

## Official RSS discovery-only extension — 2026-10-10 (Mac source proof)

The existing source-due and daily full-source timers now recognize `public_rss`
for bounded public RSS 2.0, Atom and RSS 1.0/RDF metadata discovery. The registry
adds official Camera dei deputati and Council of the EU feeds, with verifiable
publisher-directory links recorded in `endpoint_proof`. The entries use
`poll_minutes` (720/1440) and `max_items_per_poll` (8/12); the hard per-source
cap remains 20. The scheduler preserves adapter omitted-item counts and uses
the existing deterministic daily run ID and replay contract.

For `public_rss`, `RIGHTS_HOLD` is the fail-closed default irrespective of what
the public endpoint exposes. A successful feed parse records a private
`source_poll_run_source` receipt with the bounded `discovered` count, omitted
count, source ID and `BLOCKED`/`RIGHTS_HOLD`, while `content_upserts`,
`jobs_enqueued`, and downstream Capture/Passage/Candidate work remain zero.
It does not persist individual titles, excerpts or full article bodies. The
existing source-health poll time still advances on a successful fetch; rights
HOLD is not treated as an HTTP failure. A successful daily timer invocation
therefore does **not** imply accepted source material or substantial ingestion.

The feed directories establish endpoint provenance, not permission to reuse
article bodies, transcripts or images. Actual Content ingestion needs a
separate reviewed rights/acquisition path and current privacy relevance permit;
changing `rights_status` in registry alone never unlocks it. No changes to
the MiniPC runtime, provider configuration or existing DP-214 100-item
research acceptance are implied by these Mac changes.
