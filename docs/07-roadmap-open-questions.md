# Roadmap & Open Questions

> **Historical roadmap.** The canonical execution plan is now `PLAN.md`. Completed/open
> items here remain useful historical context but must not be treated as a competing
> backlog. In particular, the repository-code license question was resolved by ADR 0005
> as Apache-2.0.

## Fase 0 — Research

- [x] idea generale;
- [x] Italy-first;
- [x] figure pubbliche;
- [x] public read / no public LLM execution v1;
- [x] prima cernita GitHub;
- [x] prima analisi donor/licenze;
- [x] landscape audit esteso di donor, benchmark, monitoring, preservation, video, UX e programmabilità;
- [x] primo audit tecnico source-level di Loki, Claim Polygraph, Pender, Alegre e CIMPLE;
- [x] extraction map file-per-file dei moduli MIT che vale davvero riusare;
- [x] POC deterministico v0 con casi italiani reali e publication gate;
- [x] primo ContentAudit end-to-end su video di 7:24, con 84/84 segmenti classificati;
- [x] secondary-ASR safeguard provato su claim numerici ambigui;
- [x] benchmark MiniPC faster-whisper small su segmento numerico reale;
- [x] storage/retention/open-data strategy;
- [x] MiniPC-first + remote-scale architecture;
- [x] transcription routing policy v0 multi-provider + canonical transcript rules;
- [x] source registry config v0 con Pulp Podcast long-form proof/caption acquisition;
- [x] ASR router POC che applica health/quota/risk class alla policy v0;
- [x] canonical transcript POC con publication hold su disagreement sensibili;
- [x] source watcher POC con feed filtering + caption planning provato sul MiniPC;
- [x] podcast RSS parsing + audio-first fallback planning;
- [x] YouTube JSON3 caption adapter provato su Pulp #64;
- [x] schema PostgreSQL v0 validato sul runtime MiniPC;
- [x] scheduler POC con dedupe RSS/YouTube e job IDs deterministici;
- [x] queue PostgreSQL v0 con lease/SKIP LOCKED provata sul MiniPC;
- [x] scheduler daemon/timer one-shot + systemd, con cadence per-source, backoff e budget gate;
- [x] processing worker MiniPC con lease renew/reaper, retry/defer/dead-letter, BLOCKED e singleton lock;
- [x] RSS→YouTube resolver + caption acquisition privata senza media download;
- [x] canonical transcript runtime su 11 contenuti Pulp: 30.006 segmenti reali;
- [x] remote-ASR executor URL-first Groq Turbo implementato; runtime live bloccato finché manca la credenziale;
- [x] private health digest automatico con queue/blocker/cost/storage aggregates;
- [x] claim-window planner bounded/idempotente senza transcript text nella queue;
- [x] claim executor OmniRoute con schema validation, segment provenance, atomic_claim persistence, provider receipt e hard capability/cost gates;
- [x] compaction policy: nessun fan-out di child job quando il runtime downstream non è eseguibile;
- [x] evidence source registry v1 con host/path/method/MIME/rate/cache policy;
- [x] SSRF-safe content-addressed evidence fetch/cache runtime;
- [x] structured official query compiler per ISTAT/Eurostat/Normattiva/Parlamento;
- [x] pre-finding claim↔evidence candidate ledger;
- [x] deterministic evidence extractors v1 per JSON-stat, Normattiva metadata e HTML exact phrase;
- [x] evidence observation ledger + explicit approval/review events;
- [x] deterministic verification v1 con temporal cutoff, authoritative conflict handling e replayable verification rules;
- [x] append-only finding draft v1 ancorato a verification_run; nessun auto-PUBLISH;
- [x] structured temporal relation classifier v1 con position-change/contradiction candidate;
- [x] re-analysis trigger/runtime v1 per evidence, reply, correction, relation e manual review;
- [x] tre prototipi UX comparativi su dossier reali: editorial/newsroom, evidence graph, media timeline;
- [ ] benchmark claim extraction/check-worthiness con modelli reali contro le fixture v0 — harness pronto, run live bloccato dal path tiered dell'artefatto OmniRoute ufficiale 3.8.50;
- [ ] benchmark automatico del modello contro il ContentAudit Raffaele Giuliani — evaluator 36-claim implementato, nessuna metrica pubblicata finché il run live non riesce;
- [ ] ricerca completa normativa Italia/UE;
- [x] competitor/product-pattern audit preliminare;
- [x] prototipi UX comparativi v0; decisione sul pattern finale ancora aperta.
- [x] working brand v0: **Dichiarazioni Pubbliche**; clearance marchio/domain e rename tecnico restano pre-launch.

## Fase 1 — Domain design

- [x] schema Finding v1 append-only + verification provenance; publication/legal schema finale resta pre-launch;
- [x] schema Person v1 + speaker identity provenance non-biometrica; role intervals/organizations finali restano open;
- [ ] schema Claim;
- [x] source/evidence policy v1; legal/editorial review finale ancora pre-launch;
- [x] contradiction/position-change **candidate** taxonomy v1; publication taxonomy finale resta aperta;
- [ ] intentionality policy;
- [x] right-of-reply reanalysis core; public submission/abuse workflow resta da progettare;
- [x] correction/right-of-reply publication policy v1; public intake, anti-abuse e retention legale finale restano pre-launch.

## Fase 2 — Prototype

- [x] ingestion/preparazione transcript-first di fonti italiane reali: Giuliani + Pulp #64;
- [ ] person timeline;
- [ ] claim extraction live — executor/persistence pronti; runtime ufficiale OmniRoute fallisce il canary significativo e quindi i parent restano BLOCKED;
- [x] evidence retrieval v1 source-first: safe acquisition + structured query + candidate ledger;
- [x] deterministic verification/reanalysis prototype; evidence deve essere explicitamente APPROVED e i finding restano POLICY_HOLD/NEEDS_MORE_EVIDENCE/UNRESOLVED;
- [x] contradiction prototype strutturato: produce solo candidate relation, mai verdict automatico;
- [x] static publication read-model v1 fail-closed (JSON + HTML); hosting/CDN finale resta open;
- [x] JSON-LD ClaimReview sopra la public projection fail-closed, senza rating numerici/person score.

## Fase 3 — Monitoring

- [x] source registry schema/config v0;
- [x] scheduler/queue persistence contract v0;
- [x] discovery dedupe POC;
- [x] scheduler daemon/timer;
- [ ] daily scan;
- [x] cost accounting runtime tramite provider receipts + budget preflight; primo paid-provider receipt ancora dipende dalla credenziale ASR;
- [ ] model tiering;
- [x] re-analysis triggers + replay dell'ultima verification rule.
- [x] source health/degraded state nel scheduler runtime;
- [x] automated private operations digest (15 min);
- [x] hard cost circuit breakers global/source/job + singleton worker.

## Fase 4 — Video

- [x] ingest YouTube caption-first per copie pubbliche;
- [x] transcript/caption piattaforma ove disponibile;
- [ ] fallback STT — executor remoto implementato, runtime bloccato da GROQ_API_KEY_MISSING;
- [ ] diarization;
- [ ] timestamped claims;
- [ ] pre-analyzed content pages.

## Fase 5 — Agent/API

- [ ] OpenAPI;
- [ ] stable JSON;
- [ ] llms.txt;
- [ ] agent docs;
- [ ] optional skill;
- [ ] optional MCP.

## Fase 6 — Monetization

- [ ] BYOK;
- [ ] quota plan;
- [ ] paid API;
- [ ] trial;
- [ ] token/spend caps;
- [ ] abuse controls.

## Domande aperte

### Nome

Working brand v0: **Dichiarazioni Pubbliche**.

Razionale: italiano, memorabile e coerente con il posizionamento "on the record": conserva dichiarazioni, fonti, contesto, cambi, repliche e correzioni senza promettere un verdetto politico globale.

Tagline v0: **Memoria verificabile delle dichiarazioni pubbliche.**

Il codename tecnico `DichiarazioniPubbliche.it` resta temporaneamente in repo/package per evitare un rename trasversale prematuro. Prima del lancio pubblico servono clearance marchio, verifica definitiva dei domini/handle e decisione sul rename tecnico.

Vedi `docs/21-brand-naming-v0.md`.

### Licenza nostra

MIT/Apache, open-core, dual-license o source-available?

### Frontend

Generare 2-4 prototipi diversi prima di decidere. Metafore: GitHub delle affermazioni, timeline investigativa, knowledge graph, newsroom/fact-check, public record explorer.

### Database

PostgreSQL + vectors, PostgreSQL + RDF projection, graph DB dedicato o hybrid: decidere dopo query design.

### Ranking

Evitare ranking globale delle persone politiche. Possibili invece conteggi descrittivi, cronologia, severity del singolo finding, source coverage ed evidence strength.

### Bugia

Definire standard probatorio esplicito prima di usare il termine.

### Richieste utenti

Account? rate limit? voto? priorità trasparente? anti-abuse? richieste pubbliche o private?

### Integrazione PA

Il progetto è stato identificato e auditato:

Italian-Builders-Org/DoveVannoINostriSoldi

Decisione preliminare: progettare Dichiarazioni Pubbliche come sister-platform indipendente ma interoperabile. Vedi 13-dvns-sister-platform-integration.md.

Prima di implementare integrazioni strette:

- proporre il progetto alla community/team DVNS;
- concordare eventuali shared contracts;
- mantenere boundary di licenza e deploy indipendente;
- preferire API/MCP/linking rispetto a copie del codice.
