# Dichiarazioni Pubbliche — mega handoff dello stato e dei ticket

**Fotografia read-only: 8 ottobre 2026, ~14:45 CEST.** Documento unico per una nuova chat. Non è una dichiarazione di release GO.

## In una pagina: dove siamo davvero

- **125 ticket** canonici in PLAN.md, **125 file** docs/tickets/DP-*.md: **86 DONE, 24 IN PROGRESS, 6 BLOCKED, 9 FUTURE**. Sono **39 non-DONE**. Nessun ID mancante o duplicato.
- Stato Git Mac Studio: repo /Users/domenico/Code/DichiarazioniPubbliche.it, **main pulito**, un solo worktree locale, origin/main allineato a fcf7287bc480d2e8b25182f6f98934ba87300f2c (ultimo commit software prima di questo report).
- **CI ultimo software fcf7287: success**, run https://github.com/domenicomassafra/DichiarazioniPubbliche.it/actions/runs/37772074655, **11 job PASS** (8 backend su Linux/macOS e Python 3.11-3.14; frontend; repository contract; detached clean-clone). Attenzione: CI non contatta MiniPC, PostgreSQL o provider.
- Ultima suite locale (sul software fcf7287): **1.866/1.866 PASS**, benchmark deterministico **5/5**, JS Studio check PASS. Il verde dimostra codice/fixture, **non** corpus vero né diritti.
- MiniPC udodo: /home/udodo/src/DichiarazioniPubbliche.it è **mirror sorgenti, non Git checkout**; DB PostgreSQL dichiarazioni_pubbliche. Servizi web, worker, source poll e health attivi. API health **ok / DRAFT / 0 dossier**; https://dichiarazionipubbliche.it/ HTTP 200. Sito online **non significa v1 GO**.
- DB reale MiniPC verificato: 14 Source; **50 Content**; **30 Atomic Claim**; 28 claim_text_provenance; 9 Finding totali, 2 con status PUBLISH; **0 Capture, 0 Passage, 0 Statement Candidate, 0 Claim Candidate, 0 Discovery Manifest, 0 Discovery Hit, 0 Coverage Need**.
- Garlasco: research:garlasco **PAUSED**, **18/100 Content** membri (82 mancanti), tutti diritti UNKNOWN e processing REVIEW_REQUIRED, 10 Source ID, 30 Claim storici, 28 attribuzioni testuali approvate sul solo ledger hash (2 Claim senza tale attribuzione). **Queste approvazioni non sono licenza né autorizzazione pubblica**. Sei link candidati in config/garlasco-public-discovery-leads.v1.json non catturati.
- Gate M7: **NO-GO, 41 blockers**, SHA 890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399. Non fare auto-publication.
- Root HANDOFF.md del 2026-10-03 è **obsoleto** (977 test e vecchio conteggio dossier). In nuova chat usare questo documento, PLAN.md e ticket aggiornati.

**Diagnosi:** il software è molto avanti, ma abbiamo impiegato gli ultimi turni a sviluppare navigazione privata di ID, mentre il percorso Content→Capture→Passage→Candidate è ancora completamente vuoto nel DB reale. La prossima chat deve smettere di ottimizzare la parte sbagliata del prodotto e lavorare per batch multi-ticket sul cammino critico.

## Le quattro autorità da non confondere

1. **Stato ticket:** PLAN.md e dettaglio docs/tickets/DP-*.md. Un ticket non è DONE solo perché ha test verdi o checkbox verdi.
2. **Codice sorgente:** git main Mac Studio e GitHub origin (non il MiniPC mirror).
3. **Produzione reale:** MiniPC PostgreSQL e servizi, verificati in sola lettura con receipts; non confondere demo build Astro con proiezione pubblica approvata.
4. **Autorità di rilascio/diritti:** owner, revisore legale qualificato, diritti sulle fonti, gate privacy/reviewer e rollback. Nessuna chat o CI può inventarli.

## Sommario dei gate: 41 motivi

- 2 conditional surfaces da decidere: DP-507 (admin AuthN/AuthZ/CSRF), DP-508 (public intake anti-abuse). Se non si attivano tali superfici, serve decisione ufficiale, non cancellare il gate.
- 16 quesiti Q-306-01..16 di decisione legale: **14 OPEN + 2 BLOCKED** (Q-306-04 e Q-306-14).
- 4 artefatti mancanti: launch_rehearsal, launch_set, prelaunch_closure, release_authority.
- 19 ticket non-DONE elencati dal preflight: **DP-201, 202, 203, 204, 215, 301, 304, 307, 405, 406, 407, 408, 409, 410, 604, 701, 702, 703, 704**.

Il preflight verifica questi 19, non tutti i 39 aperti; i restanti 20 non possono essere ignorati se servono alla funzione o sono dipendenze di quelli critici.

## Il funnel che conta: perché abbiamo la sensazione di andare piano

Percorso effettivo voluto: **Discovery → Content → Content Capture immutabile → Passage/canonical transcript segment → Statement Candidate → Claim Candidate → Matching/cluster → promozione revisionata ad Atomic Claim → Evidence/Verification → Finding → proiezione pubblica revisionata**.

Il codice per molti di questi passaggi esiste ed è formalmente DONE. Ma nel PostgreSQL live:

| Oggetto | Righe |
|---|---:|
| source | 14 |
| content_item | 50 |
| research_collection | 1 |
| research_collection_content | 18 |
| atomic_claim | 30 |
| claim_text_provenance | 28 |
| finding | 9 |
| finding con publication_status = PUBLISH | 2 |
| content_capture | **0** |
| passage | **0** |
| statement_candidate | **0** |
| claim_candidate | **0** |
| research_discovery_manifest | **0** |
| research_discovery_hit | **0** |
| coverage_need | **0** |

Quindi i 30 Atomic Claim attuali sono un **baseline storico**, non la prova del nuovo ciclo completo. La raccolta Garlasco non può essere detta pronta: 18/100 logici, diritti sconosciuti, niente versioni immutabili, niente estrazione o review. I 28 record di attribuzione TEXT_QUOTE_HASH in stato APPROVED stabiliscono soltanto il loro **stato salvato**, non la verità, il diritto a riprodurre o la firma del reviewer attuale.

**KPIs da riportare SEMPRE nel primo paragrafo di ogni nuova tranche:** ticket DONE / aperti per stato, 41 blocker release (o nuovo valore comprovato), corpus pilot N/100, rights-cleared N/100, Captures N, Passages N, Candidates N, 30 claim invarianti, MiniPC/CI/commit. Questo impedisce di dichiarare «molto progresso» per un solo endpoint.

## Milestone: stato reale del piano

| Fase | DONE | IN PROGRESS | BLOCKED | FUTURE | Lettura |
|---|---:|---:|---:|---:|---|
| M0 governance | 4 | 0 | 0 | 0 | base terminata |
| M1 dominio/schema | 11 | 0 | 0 | 0 | dominio terminato |
| M1R Research Corpus | 7 | 0 | 0 | 0 | **contratti** software completi |
| M2 pipeline live | 24 | 5 | 4 | 1 | **collo reale**: dati/rights/provider/canary |
| M3 editoriale-legale | 8 | 2 | 0 | 1 | decisioni qualificate ancora aperte |
| M4 sito/API/Studio | 19 | 12 | 2 | 2 | molto codice pronto, accettazioni reali/AT da chiudere |
| M5 affidabilità/sicurezza | 9 | 0 | 0 | 2 | basi solide, due superfici condizionali |
| M6 OSS/release tooling | 4 | 3 | 0 | 0 | governance e scelta owner pendenti |
| M7 stable v1 | 0 | 2 | 0 | 3 | **lancio non concluso** |
| **Totale** | **86** | **24** | **6** | **9** | **125** |

### Che cosa è già chiuso e non va rifatto

- **M0 4/4**: governance e scelte d'architettura. Non riscrivere ADR generici per dare impressione di movimento.
- **M1 11/11**: temporality, Claim/Finding, persistence, worker/domain. Regressioni sì, refactor broad no.
- **M1R 7/7**: Source/Content/Capture/Passage/Person/Topic/Event/Proposition, storage, DP-116 search, DP-117 explicit claim promotion, retention. Un motore disponibile NON è un corpus acquisito.
- **M2 24 ticket DONE**: polling/source adapters e contracts di ricerca, matching, coverage, attribution/source rights/verification/false-attribution hardening. Il DP-214 resta separatamente aperto.
- **M3 8 DONE**: publication safety, legal wording guards, correction/reply, high-risk, independent dual control. Owner/counsel non hanno completato DP-307, DP-301.8 e privacy composite.
- **M4 19 DONE**: API e pagine pubbliche static-first, layout/route e design v4, disclosure/fiducia/correzioni. Mancano persone/topic/trace su dati revisionati e AT manuale.
- **M5 9 DONE**: security, backup/restore, retention, operations, quarantine/hold, source supersession.
- **M6 4 DONE**: packaging, multi-version CI, fixture licensing, contributor/clean clone. DP-604/606/607 richiedono ancora owner/mutazioni mirate.
- **M7 0 DONE**: owner release, dataset/snapshot approvato, rehearsal e via libera v1 ancora mancanti.

## Ticket aperti: ordine di urgenza e un-blocker

### Gruppo P0-A — l'esperimento vero DP-214

**DP-214, IN PROGRESS, 1/8 AC**, segue DP-209..213, DP-215 e DP-117. È il *primo percorso critico*. La definizione nel ticket richiede 100 Content logici veri distribuiti su cinque famiglie, provenance/discovery, immutable Captures, Passages, entity/Statement/Claim Candidates, clusters/dedup, Coverage Needs, match su 30 Claim e replay senza effetti pubblici. La sola AC-214.3 (30 Claim unici e ricercabili) è spuntata. **18 Content storici + 6 candidate-only URL ≠ 100**.

**DP-215, IN PROGRESS, 8/9 AC**: Source Intelligence/evidence role/suitability già implementata; manca AC-215.9 su un corpus reale Garlasco completo con rights/roles/lineage. Può seguire la stessa tranche DP-214, non servono altri dieci turni di API Studio.

Proposta di *verticale reale* anziché un altro endpoint: scegliere fonti con diritto di processamento stabilito e provenance tracciabile; validare un unico DiscoveryHit vero → Content Capture immutabile → Passage con source selector → Candidate → matching/cluster review → replay, su canary isolato e con garanzie fail-closed; poi accumulare i 100 item in batch. Senza diritto verificato, segnalare BLOCKED e **non falsificare** ingressi. PAUSED deve rimanere tale fino a decisione/procedure di attivazione valide.

**DP-229, IN PROGRESS** challenger/counter-case: implementazione verificabile su corpus vero, attenzione a contenuto/speech polarizzato e false equivalenze.
**DP-233, IN PROGRESS** parliamentary official speech/video: adapter e replay fixture presenti, manca canary approved official-family MiniPC.
**DP-234, IN PROGRESS** DVNS: bridge offline pronto, mancano diritti/contratto API reale e canary fonte.
**DP-420, FUTURE** usability/Recall@K del vero corpus Garlasco, dopo DP-214 e DP-415..419.
**DP-421, FUTURE** decidere eventuale pagina pubblica caso/Collection dopo ricerca, review M3 e DP-420, non inventare ora.

### Gruppo P0-B — provider e credenziali, esterni

**DP-201 BLOCKED** OmniRoute official meaningful canary + cost/circuit break; **DP-202 BLOCKED** canary parent Claim e Giuliani benchmark dopo 201; **DP-203 BLOCKED** extraction fan-out dopo 202. **DP-204 BLOCKED** primo live remote-ASR receipt con credenziale Groq fuori Git, fallback/costi. **DP-208 FUTURE** benchmark diarization/go-no-go solo dopo DP-204 e riferimento reale.

Non trasformare questi ticket in DONE grazie a simulazioni, cambio provider non governato o segreti pubblicati. Servono credenziali/owner/provider effettivi. Possono essere sbloccati in parallelo al corpus purché senza collisioni dati.

### Gruppo P0-C — legale, privacy e autorizzazione

**DP-301 IN PROGRESS, 7/8 AC**: ultima approvazione della policy linguistica/intentionality su Q-306/DP-307.
**DP-304 IN PROGRESS, 7/8 AC**: privacy/minimization end-to-end con quarantena dati sensibili, access log e diritti di rettifica/minimizzazione; le prove isolate già verdi non certificano policy globale.
**DP-307 FUTURE, 0/9 AC**: revisore legale qualificato e decisioni Q-306. Il dossier di ricerca legale (DP-306) è implementato, ma le **16 decisioni legali sono ancora aperte/bloccate**. Non trasformare research in legal sign-off.
**DP-701 IN PROGRESS, 5/10 AC**: rename tecnico Dichiarazioni Pubbliche fatto, ma trademark/collisioni, DNS/handle, disposizioni qualificate e compatibilità/rollback esterni mancano.
**DP-702 FUTURE, 6/14 AC**: review prelaunch complessiva, richiede owner/revisore e confronto con real dataset, privacy, security.

### Gruppo P1 — UI pubblica e accessibilità, anche in parallelo

**DP-405 IN PROGRESS (6/8 AC)** Person archive; reale zero-public-record e test screen-reader/focus.
**DP-406 BLOCKED (6/8 AC)** Topic dossier: canary reale con Topic e membership APPROVED manca, nonostante codice verde.
**DP-407 IN PROGRESS (7/9 AC)** Content/locator: wording per stati irrisolti + screen reader.
**DP-408 BLOCKED (6/8 AC)** longitudinal trace: manca una relazione reale già revisionata e accettabile.
**DP-409 IN PROGRESS (8/9 AC)** static search/SEO: dipende da DP-408 e test assistivo manuale.
**DP-410 IN PROGRESS (6/8 AC)** accessibility/performance/SEO: test AT, focus/touch/contrast reali mancanti.
**DP-412 IN PROGRESS (8/9 AC)** design token/componenti: screen-reader/manual exact-200%-zoom da completare.
**DP-422 IN PROGRESS (8/9 AC)** v3 route migration: confronto v4 desktop/mobile umano e dipendenze DP-408/409/429.
**DP-429 IN PROGRESS** Explore v4: browser automatizzato verde, manual screen reader/visual non verificato; alcuni suoi AC non sono espressi come checkbox leggibili automaticamente.

**DP-415/416/417/418/419 IN PROGRESS, ciascuno 0/4 AC** Studio privato: ci sono runtime read-only per Corpus, Collections, Inbox, Matches, Captures, Claim provenance, ma nessun Garlasco Capture/Passage/Candidate vero, né approval UI autorizzata, UX AT completa. Nessun motivo per rifare ora tutta la UI Studio. Prima DP-214.

### Gruppo P2 — release e operazioni amministrative

**DP-604 IN PROGRESS, 12/12 AC spuntate**: release/versioning policy e pacchetti riproducibili, ma owner release/autorità esterna non conclusi. **Non segnare DONE automaticamente**.
**DP-606 IN PROGRESS, 10/11 AC**: GitHub Issue labels/automation: contratto e local/remote read-only verdi, owner mutation/branch protection/export-rollback mancano; **gh issue list adesso riporta zero issue**, il backlog vive nel repo.
**DP-607 IN PROGRESS, 10/12 AC**: SDK/MCP/skill opzionali; non costruire una nuova piattaforma fino a decisione build/no-build.
**DP-703 IN PROGRESS, 2/12 AC**: vero launch set/snapshot e disclosure, almeno 3 source families autorizzate, rights/privacy/retraction/rollback.
**DP-704 FUTURE, 0/13 AC**: rehearsal end-to-end reale + failure/rollback/correction.
**DP-705 FUTURE, 1/12 AC**: release v1.0.0 solo con authority e passaggio di DP-701..704.
**DP-507/508 FUTURE**: superficie admin e intake pubblici condizionali. Evitarli in v1 solo con decisione documentata; mai esporli senza AuthN/AuthZ/CSRF/abuse controls.

## Piano di esecuzione accelerato: niente più un endpoint per turno

### Work allocation se funzionano due subagenti

**PRIME integratore:** gestisce PLAN, commit/merge/push, DB migration/deploy (se autorizzato), scelta delle AC, CI, qualità finale, progress board e rapporti precisi. Solo prime modifica PLAN.md. Nessun subagente deve fare commit contemporaneo sugli stessi file o sincronizzare il MiniPC senza coordinamento.

**WORKER 1 — Corpus / DP-214+215.** Scrive solo nei moduli e test di corpus/discovery/ingestion specifici concordati; prima assessment read-only di 100-slot corpus da sorgenti reali, provenance/rights, 5 source families, dedup/derivation, idempotent Capture/Passage/Candidate e failure matrix; non inventa item e non cambia PAUSED in ACTIVE senza prova/decisione. Dimostra un vero end-to-end isolato e propone piccoli batch successivi.

**WORKER 2 — QA legale/UX/release indipendente.** Inizialmente SOLO ricognizione e materiali di accettazione: DP-301/304/307 owner-decision matrix e/o DP-405/407/409/410/412/422/429 browser/manual QA, tenendo separata l'autorità qualificata. Niente modifica ai moduli che worker 1 sta usando. Se il lavoro è bloccato da revisore umano, registra esattamente documenti/risposte richiesti invece di inventarle.

**PRIME — Provider e programma:** controlla credenziali disponibilità, cost cap e source-family approvate per DP-201/204/233/234; esegue il release preflight e seleziona ticket che la squadra può chiudere davvero. Raggruppa 3–5 ticket tecnicamente correlati in un batch e chiude solo le AC comprovate.

**Oggi i due worker NON hanno lavorato.** Chiamata agents status aveva 2 free slots, spawn di worker-1 (ticket audit) e worker-2 (runtime audit), ma entrambi hanno fallito la startup della chat browser e non hanno inviato risultati. Non attribuire loro questo rapporto. Diagnostica modello app: il default '5.6' salvato in Settings → Agents & automation non è offerto dall'account; il tool ha tentato modello corrente, poi le finestre chat non si sono aperte. Risolvere UI/sessione/modello o proseguire prime, NON spammare spawn.

### Ondata 0: decisioni e un primo percorso realistico

- Consolidare un **owner decision register**: proprietario/revisore di Q-306-01..16; credenziali e budget ufficiali per OmniRoute/Groq; fonti e diritti ammissibili al pilot; se admin/intake restano definitivamente disabilitati in v1; criterio di release scope e marca/DNS. Questi sono input umani obbligatori per sbloccare gran parte dei 41 impedimenti.
- Confermare per ogni DP-214 item: Content reale, source, provenance, rights, capture capability, duplicate/derivation, source family, reviewer authority. **Manifest incompleto resta privato e non processato**.
- Separare le 6 piste pubbliche candidate-only dall'approved collection. Nessuna fonte giornalistica secondaria assume automaticamente ruolo di verbale/trascrizione ufficiale.
- In parallelo, elaborare *un solo* pacchetto di QA UI manuale indipendente per DP-405/407/409/410/412/422/429, invece di nuovi redesign.

### Ondata 1: demo vera, piccola e completa, poi batch a 100

Sequenza dimostrativa richiesta: **1 fonte con diritto/consenso adeguato → DiscoveryRun+Hit → Content→ Capture immutabile → Passage/selector → candidate + reviewer decision → matching, dedup e replay, nessun Finding pubblicabile generato**. Tutti gli hash/rights/policy+retention in receipt privato. Una volta stabile, aumentare per lotti strutturati e cinque famiglie, fino a 100 solo con dati autentici.

**Stop:** se mancano diritti o accesso, si produce un NO-GO motivato, non un dataset fittizio, e si passa a un'altra lane compatibile.

### Ondata 2: chiudere ciò che sblocca davvero il rilascio

- DP-215.9 appena corpus reale accettato.
- DP-201→202→203 e DP-204 appena provider ufficiale/credenziale pronti, con canary cost-bounded.
- DP-301.8, DP-304, DP-307, Q-306 x16 appena owner/revisore qualificato rispondono.
- DP-406/408 appena esistono Topic e timeline pubblicamente approvate; DP-405/407/409/410 manual assistive acceptance in un unico ciclo.
- DP-604/606/607 con decisioni owner mirate, senza inventare SDK/issue bot.
- DP-701 brand/legal/DNS/rollback e DP-703 manifest di lancio.

### Ondata 3: release vera o NO-GO onesto

**DP-701 + DP-702 + DP-703 → DP-704 → DP-705**. Eseguire preflight a ogni cambio significativo e non promuovere dataset prima di diritti/legal. Richiedere receipt rollback, failure injection, source/provenance replay e approved projection. Nessun deploy pubblico v1.0.0 con gate aperti.

### Regole per evitare lentezza strutturale

1. Prima di codificare, scrivere *a quale AC e quale ticket* contribuisce la modifica; se non produce una AC più vicina o sblocca un collo di bottiglia, non farla.
2. Chiudere batch in una sola suite completa e una CI, non 90 secondi di regression dopo ogni file (test focalizzati durante iterazione).
3. Una dashboard di 6 metriche a fine tranche: closed/open breakdown, Garlasco N/100 e corpus stage counts, blocker count, CI SHA, prova MiniPC, prossime tre AC sbloccabili.
4. Documentare il *singolo blocker esterno* una volta, non ripetere più turni che non possono risolverlo.
5. Seguire un percorso verticale end-to-end reale prima di progettare altre 20 schermate.
6. Il release blocker count può rimanere a 41 anche dopo implementazioni utili: esplicitare cosa è realmente avanzato, evitando falsa sensazione di stagnazione o false verdi.
7. Se l'utente decide di restringere lo scope v1, creare una **decisione formale di scope** e aggiornare requisiti e checker in modo reviewable; non togliere gate legal/public safety opportunisticamente.

## Comandi e procedure di ripartenza (nessun segreto)

**Git e CI**

```bash
cd /Users/domenico/Code/DichiarazioniPubbliche.it
git status --short --branch
git worktree list --porcelain
git log -5 --oneline --decorate
gh run list --repo domenicomassafra/DichiarazioniPubbliche.it --branch main --limit 3 \
  --json databaseId,status,conclusion,headSha,url
python3 tools/check_launch_preflight.py --expect-no-go
python3 tools/check_repository_contract.py --only tickets
python3 tools/check_contributor_acceptance.py
python3 tools/check_licensing_inventory.py
```

**Suite solo a fine tranche** (spesso 90–105 secondi per il Python integrale):

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
git diff --check
cd web
npm run check
npm run check:design
DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build
```

**MiniPC, letture e servizi**:

```bash
ssh minipc 'systemctl --user is-active dichiarazioni-pubbliche-web.service'
ssh minipc 'systemctl --user is-active dichiarazioni-pubbliche-source-poll.timer'
ssh minipc 'systemctl --user is-active dichiarazioni-pubbliche-worker.timer'
ssh minipc 'curl -fsS --max-time 5 http://127.0.0.1:18090/api/v1/health'
ssh minipc 'psql -XqAt -d dichiarazioni_pubbliche -v ON_ERROR_STOP=1 -c "BEGIN READ ONLY; SELECT count(*) FROM content_capture; COMMIT;"'
curl -sS --max-time 10 -o /dev/null -w 'public_http=%{http_code}\n' https://dichiarazionipubbliche.it/
```

La CI usa il flag demo solo per verificare la build fittizia; per la proiezione reale il path invalido **deve fallire**. Il sito statico 200 non dimostra che un dossier sia approvato; l'health attuale dice 0 dossier e contract DRAFT.

**Files importanti:** PRODUCT.md, CONTEXT.md, ARCHITECTURE.md, AGENTS.md, PLAN.md; docs/34-research-corpus-knowledge-architecture-v1.md; docs/35-public-product-architecture-v3.md; docs/ops/garlasco-pilot-seed-readback-20261008.md; docs/ops/garlasco-paused-baseline-20261008.md; docs/ops/studio-local-readonly.md; docs/reviews/2026-10-08-studio-garlasco-text-provenance.md; docs/release/checklist.md; docs/tickets/DP-214*.md, DP-215*.md, DP-301*.md, DP-304*.md, DP-307*.md e DP-701..705*.md.

**Comportamenti di sicurezza non negoziabili:** no auto-publication; no persona truth/reliability score; no accuse/attribuzioni falsamente verificate; niente trascrizioni/testi privati proiettati sul sito; non confondere original/translation/paraphrase; no riconoscimento biometrico della voce; correzioni e right-of-reply append-only; revisioni, rights, source provenance e temporalità separati; stop fail-closed su provider/offline/credits/diritti; output pubblico solo da proiezione approvata; nessun nuovo remote-admin HTTP senza DP-507; nessun public intake senza DP-508; niente credenziali/log privati in Git. Non fare merge/push o MiniPC sync da due worker concorrenti senza integratore.

## Nuova chat: prompt operativo da incollare integralmente

> Riparti da DichiarazioniPubbliche.it seguendo come fonte primaria **docs/reviews/2026-10-08-mega-handoff-stato-e-piano.md** (questo documento) e **PLAN.md** nel repo Mac Studio /Users/domenico/Code/DichiarazioniPubbliche.it. All'8 ottobre 2026: 125 ticket (86 DONE, 24 IN PROGRESS, 6 BLOCKED, 9 FUTURE), 41 release blockers; database MiniPC 50 Content, 30 Claim ma **0 Capture/Passage/StatementCandidate/ClaimCandidate**; Garlasco PAUSED con 18/100 item, 28 text-hash attribution, 82 item mancanti. Verifica HEAD/CI e DB read-only prima di agire; il precedente ultimo commit software era fcf7287 con CI verde. La priorità è implementare/validare il **percorso end-to-end corpus reale DP-214→215**, affrontando in parallelo input legali/provider/QA che sbloccano il preflight. NON spendere un altro ciclo su sola UI Studio. Prova ad avviare **due subagenti** se operativi (controlla status e browser; gli ultimi due spawn non si sono aperti); separa scope e file, uno sul corpus/rights/provenance reale, uno su legal/QA/release indipendente, tu integri e aggiorni PLAN. Batch da 3–5 ticket; test mirati durante coding, suite completa+CI una sola volta a fine batch. Prima di chiudere un ticket mostra AC verificata, prove MiniPC e zero side effect pubblici. Non falsificare legal review, licenze, provider canary, dati Garlasco, diritti o promozione pubblica. Se input umano manca, registralo una volta come blocker vero. Alla fine di ogni tranche mostra i delta delle metriche e i prossimi due task concreti, non promesse generiche.

## Inventario integrale automatico: tutti i 125 ticket

Righe derivate da PLAN.md e file corrispondenti docs/tickets/DP-*.md, senza reinterpretarne lo status. I valori AC indicano quante checkbox di acceptance sono spuntate nel file rispetto alle checkbox presenti; **0/0 può significare requisiti narrativi** non assenza di criteri. Distingue gli 86 DONE dai 39 aperti e lascia rintracciabile ogni dipendenza.

### M0 — Governance and architecture baseline

| Ticket | Stato | AC checked | Descrizione canonica PLAN.md | Dipendenze |
|---|---|---:|---|---|
| [DP-001](../tickets/DP-001-oss-governance-baseline.md) | **DONE** | 0/0 | Establish canonical OSS/governance surface | baseline |
| [DP-002](../tickets/DP-002-historical-doc-reconciliation.md) | **DONE** | 0/0 | Reconcile historical docs against canonical contracts | DP-001 |
| [DP-003](../tickets/DP-003-architecture-deepening-review.md) | **DONE** | 0/0 | Architecture deepening review of current modules | DP-001 |
| [DP-004](../tickets/DP-004-architecture-decisions-to-tickets.md) | **DONE** | 0/0 | Convert accepted architecture findings into ADRs/refactor tickets | DP-003 |

### M1 — Domain and schema convergence

| Ticket | Stato | AC checked | Descrizione canonica PLAN.md | Dipendenze |
|---|---|---:|---|---|
| [DP-101](../tickets/DP-101-role-intervals-organizations.md) | **DONE** | 0/0 | Role intervals + organizations with provenance | M0 |
| [DP-102](../tickets/DP-102-atomic-claim-contract-v1.md) | **DONE** | 0/0 | Atomic Claim contract v1 and claim-type taxonomy convergence | M0 |
| [DP-103](../tickets/DP-103-finding-vocabulary-convergence.md) | **DONE** | 0/0 | Finding/assessment/publication vocabulary convergence | DP-102 |
| [DP-104](../tickets/DP-104-relation-publication-policy.md) | **DONE** | 0/0 | Longitudinal relation approval/publication policy | DP-102, DP-103 |
| [DP-105](../tickets/DP-105-public-schema-v1.md) | **DONE** | 0/0 | Public schema v1 compatibility contract | DP-101..104 |
| [DP-106](../tickets/DP-106-v0-name-migration-strategy.md) | **DONE** | 0/0 | Migration from `*.v0` config/schema names completed; MiniPC cutover is v1-only with zero legacy fallback events | DP-101..105 |
| [DP-107](../tickets/DP-107-deepen-postgres-persistence-modules.md) | **DONE** | 0/0 | Deep PostgreSQL persistence converged into narrow domain stores; 92-table restore integration and MiniPC worker/review/runtime acceptance green | DP-101..106 |
| [DP-108](../tickets/DP-108-deepen-worker-job-handlers.md) | **DONE** | 0/0 | ProcessingWorker orchestration separated into three cohesive handler families; MiniPC queue/cost/block/review acceptance green | DP-107 |
| [DP-109](../tickets/DP-109-collection-readiness.md) | **DONE** | 0/0 | Governed collection-readiness report/CLI; fail-closed provider/capability blockers proven locally and on MiniPC | DP-101..108 |
| [DP-110](../tickets/DP-110-reasoned-inference-candidates.md) | **DONE** | 0/0 | Evidence-based reasoned inference candidates, private/review-only | DP-102, DP-103 |
| [DP-111](../tickets/DP-111-written-source-claim-provenance.md) | **DONE** | 0/0 | First-class written-source claim provenance without fake timestamps | DP-102, DP-105 |

### M1R — Research corpus and knowledge convergence

| Ticket | Stato | AC checked | Descrizione canonica PLAN.md | Dipendenze |
|---|---|---:|---|---|
| [DP-112](../tickets/DP-112-first-class-research-corpus-domain-contract.md) | **DONE** | 6/6 | First-class Research Corpus domain contract | M1 baseline |
| [DP-113](../tickets/DP-113-research-corpus-persistence.md) | **DONE** | 6/6 | Additive persistence for captures, passages, collections and candidates | DP-112 |
| [DP-114](../tickets/DP-114-entity-topic-event-resolution.md) | **DONE** | 5/5 | Entity, Topic and Event resolution with reviewable match candidates | DP-113 |
| [DP-115](../tickets/DP-115-proposition-clusters-source-derivation.md) | **DONE** | 4/4 | Proposition clustering + source derivation/independence relations | DP-113, DP-114 |
| [DP-116](../tickets/DP-116-postgres-corpus-search-benchmark.md) | **DONE** | 5/5 | PostgreSQL-first corpus search and similarity contract | DP-113 |
| [DP-117](../tickets/DP-117-candidate-atomic-claim-promotion.md) | **DONE** | 5/5 | Explicit candidate -> Atomic Claim promotion contract | DP-113, DP-115 |
| [DP-118](../tickets/DP-118-corpus-rights-retention-replay.md) | **DONE** | 5/5 | Corpus rights, retention, replay and capture lifecycle | DP-113 |

### M2 — Live pipeline readiness and source coverage

| Ticket | Stato | AC checked | Descrizione canonica PLAN.md | Dipendenze |
|---|---|---:|---|---|
| [DP-201](../tickets/DP-201-omniroute-meaningful-canary.md) | **BLOCKED** | 0/0 | Official OmniRoute meaningful canary + cost gate | official provider path |
| [DP-202](../tickets/DP-202-parent-canary-giuliani-benchmark.md) | **BLOCKED** | 0/0 | One parent claim canary + Giuliani benchmark | DP-201 |
| [DP-203](../tickets/DP-203-controlled-claim-fanout.md) | **BLOCKED** | 0/0 | Controlled claim-extraction fan-out | DP-202 |
| [DP-204](../tickets/DP-204-live-remote-asr-receipt.md) | **BLOCKED** | 0/0 | First live remote-ASR receipt and fallback acceptance | Groq credential |
| [DP-205](../tickets/DP-205-daily-full-source-polling.md) | **DONE** | 0/0 | Daily/full-source polling mode with bounded coverage | M0 |
| [DP-206](../tickets/DP-206-second-third-source-families.md) | **DONE** | 0/0 | Add second and third source families without code duplication | DP-205 |
| [DP-207](../tickets/DP-207-timestamped-claim-acceptance.md) | **DONE** | 0/0 | Timestamped claim acceptance across real content | DP-202 or deterministic fixture path |
| [DP-208](../tickets/DP-208-diarization-benchmark-go-no-go.md) | **FUTURE** | 0/0 | Diarization benchmark/go-no-go; local metric/safety harness implemented, real reference/model/MiniPC decision remains blocked on DP-204 and runtime gates | DP-204, DP-207 |
| [DP-209](../tickets/DP-209-bounded-research-discovery-runs.md) | **DONE** | 4/4 | Bounded research discovery runs + query manifests | DP-113, DP-205, DP-206 |
| [DP-210](../tickets/DP-210-capture-preservation-parser-pipeline.md) | **DONE** | 5/5 | Capture/preservation/parser pipeline | DP-113, DP-118, DP-209 |
| [DP-211](../tickets/DP-211-passage-candidate-extraction.md) | **DONE** | 5/5 | Passage -> statement/entity/claim candidate extraction | DP-114, DP-210 |
| [DP-212](../tickets/DP-212-candidate-matching-clustering-runtime.md) | **DONE** | 4/4 | Candidate dedupe, matching and proposition clustering runtime | DP-115, DP-116, DP-211 |
| [DP-215](../tickets/DP-215-source-intelligence-evidence-suitability.md) | **IN PROGRESS** | 8/9 | Source Intelligence + contextual evidence suitability/requirements is implemented; only AC-215.9 remains blocked because the real 100-item Garlasco tracer collection/manifest and its role/rights/lineage data do not exist | DP-102, DP-113, DP-115, DP-118, DP-209, DP-210 |
| [DP-213](../tickets/DP-213-coverage-needs-planner.md) | **DONE** | 4/4 | Coverage-needs planner for missing primary/original/independent material | DP-211, DP-212, DP-215 |
| [DP-214](../tickets/DP-214-garlasco-research-collection-tracer-bullet.md) | **IN PROGRESS** | 1/8 | AC-214.3 closed; real research:garlasco PAUSED collection with 18 pre-existing Content members, replay-safe and all 18 rights UNKNOWN; collection-scoped 13/13 Recall@5 after PERSON binding fix; 6 unreviewed leads, no capture or automatic publication; 100-item/rights/provenance/candidate acceptance still absent | DP-209..213, DP-215, DP-117 |
| [DP-216](../tickets/DP-216-exact-quote-source-span-binding.md) | **DONE** | 10/10 | Exact quote/source-span binding; human-review/source hashes and bounded discontinuous-span omission disclosure proven fail-closed locally and on MiniPC | DP-111, DP-210; coordinate DP-207/DP-305 |
| [DP-217](../tickets/DP-217-transcript-verbatim-reliability-audio-review.md) | **DONE** | 8/8 | Transcript reliability tiers + persisted human/audio verbatim review gate bound to exact source/canonical hashes and reviewed range | DP-204/DP-207 where live; fixture lane independent |
| [DP-218](../tickets/DP-218-speaker-attribution-proof-coverage.md) | **DONE** | 10/10 | Speaker-attribution proof covers the exact quoted/claimed span; schema/benchmark/MiniPC acceptance complete | DP-114, DP-207, ADR 0003 |
| [DP-219](../tickets/DP-219-reported-speech-nested-quotation-origin.md) | **DONE** | 8/8 | Reported speech/nested quotation + original-quote-origin separation, including adversarial release-gate coverage | DP-216, DP-218, DP-211 |
| [DP-220](../tickets/DP-220-context-integrity-semantic-clipping-guard.md) | **DONE** | 10/10 | Context-integrity / semantic-clipping guard for public statements, including discontinuous/montage fail-closed handling | DP-216, DP-217, DP-219 |
| [DP-221](../tickets/DP-221-original-paraphrase-translation-separation.md) | **DONE** | 8/8 | Original wording vs paraphrase/summary/translation separation; public serializers/search + DP-305 no-body exact-copy guard proven locally and on MiniPC | DP-216 |
| [DP-222](../tickets/DP-222-public-attribution-person-identity-gate.md) | **DONE** | 8/8 | Public-attribution Person identity + same-name/role-at-time gate; projection/read-time fail-closed identity/role proof + persisted tamper + MiniPC acceptance complete | DP-101, DP-114, DP-216, DP-218 |
| [DP-223](../tickets/DP-223-false-attribution-adversarial-benchmark.md) | **DONE** | 10/10 | False-attribution/fabricated-quote adversarial benchmark; 59-case zero-tolerance gate, persisted full-corpus projection/serializer replay and isolated MiniPC release-candidate attribution-integrity read-back all pass with zero known false attribution/fabricated quote | DP-216..222, DP-224 |
| [DP-224](../tickets/DP-224-material-assertion-citation-assurance.md) | **DONE** | 0/0 | Material-assertion citation assurance over approved evidence/passages; exact Passage/source-hash binding + persisted tamper + MiniPC acceptance complete | DP-215, DP-210; coordinate DP-216/DP-308 |
| [DP-225](../tickets/DP-225-original-source-resolver.md) | **DONE** | 0/0 | Reviewed original-source resolver over approved derivation families; persisted receipt + private Studio inspection proven on MiniPC | DP-115, DP-215 |
| [DP-226](../tickets/DP-226-compound-numerical-verification-v2.md) | **DONE** | 0/0 | Compound numerical verification: delta/ratio/percent change + unit/denominator policy; structured-provider fixture + MiniPC proof complete | DP-215 |
| [DP-227](../tickets/DP-227-effective-time-supersession-verification.md) | **DONE** | 0/0 | Effective-time/validity/supersession verification; selectors + reviewed supersession -> persisted reanalysis consumer proven with law/policy/statistical MiniPC canary | DP-215, DP-210 |
| [DP-228](../tickets/DP-228-claim-specific-research-plan-compiler.md) | **DONE** | 0/0 | Claim-specific research-plan compiler with bounded specialist retrieval lanes and fail-closed narrowing query-suggestion seam | DP-213, DP-215, DP-209 |
| [DP-229](../tickets/DP-229-adversarial-challenger-countercase.md) | **IN PROGRESS** | 0/0 | Bounded adversarial challenger/counter-case packet | DP-228, DP-215 |
| [DP-230](../tickets/DP-230-canonical-provider-operation-cost-ledger.md) | **DONE** | 0/0 | Canonical provider-operation receipt + reconstructable cost ledger v2; MiniPC restart/replay canary green | DP-209, DP-211, DP-506 |
| [DP-231](../tickets/DP-231-source-metadata-oembed-archive-enrichment.md) | **DONE** | 0/0 | Pender-style metadata/oEmbed/archive enrichment: private source metadata and archive receipts, optional provider-pinned Vimeo JSON lookup (disabled by default), bounded no-redirect network contract and isolated MiniPC test; no live source approval implied | DP-210, DP-118, DP-305 |
| [DP-232](../tickets/DP-232-existing-factcheck-lookup-adapter.md) | **DONE** | 0/0 | Existing fact-check provider-neutral adapter complete: bounded DP-228→DP-209 runtime, append-only mirror lineage/replay, fail-closed UNKNOWN rights and metadata/link-only public surface proven; any future owner-selected live provider requires a separate authorized network/source canary | DP-228, DP-215 |
| [DP-233](../tickets/DP-233-parliamentary-speech-video-alignment-adapter.md) | **IN PROGRESS** | 0/0 | Parliamentary official speech/transcript/video adapter; fixture execution distinguishes NEW/REPLAY/AMENDED and delegates amended records to DP-511/DP-227 with DP-305 fail-closed rights; approved official source-family MiniPC canary pending | DP-206, DP-217, DP-218, DP-231 |
| [DP-234](../tickets/DP-234-dvns-structured-evidence-adapter.md) | **IN PROGRESS** | 0/0 | DVNS/read-only structured evidence adapter; strict offline normalization + explicit DP-215 role/authority/suitability bridge implemented, real approved provider/licensing + MiniPC source-family canary pending | DP-215, DP-228, external contract/API |

### M3 — Editorial, correction, privacy, and legal policy

| Ticket | Stato | AC checked | Descrizione canonica PLAN.md | Dipendenze |
|---|---|---:|---|---|
| [DP-301](../tickets/DP-301-intentionality-lie-policy.md) | **IN PROGRESS** | 7/8 | Intentionality/"lie" engineering policy AC-301.1-.7 complete and fail-closed; AC-301.8 remains blocked on qualified Q-306/DP-307 owner/counsel dispositions | M0 |
| [DP-302](../tickets/DP-302-right-of-reply-intake-threat-model.md) | **DONE** | 10/10 | Right-of-reply engineering AC-302.1-.10 machine-proven, including durable abuse/retention ledgers and enabled MiniPC intake→private-review replay; public intake remains disabled pending separate Q-306/DP-307 launch/legal decisions | M0 |
| [DP-303](../tickets/DP-303-correction-takedown-appeal-workflow.md) | **DONE** | 10/10 | Typed append-only correction/takedown/appeal engineering AC-303.1-.10 machine-proven through full MiniPC submit→review→correction/reanalysis→public-projection canary; launch policy/legal decisions remain separate Q-306/DP-307 blockers | DP-302 |
| [DP-304](../tickets/DP-304-privacy-minimization-sensitive-person-policy.md) | **IN PROGRESS** | 7/8 | Privacy/minimization policy has sensitive-data quarantine and fail-closed retention dry-runs proven (AC-304.3/.6); complete field inventory, ingestion-wide relevance, all-surface privacy/log proof, persisted rights-request cases, wired private-access runtime and composite MiniPC canary remain, with Q-306/DP-307 legal decisions unresolved | M0 |
| [DP-305](../tickets/DP-305-copyright-transcript-excerpt-policy.md) | **DONE** | 8/8 | Copyright/transcript excerpt engineering AC-305.1-.8 machine-proven through rights registry, fail-closed no-body boundary, complaint→hold bridge and MiniPC excerpt/expiry/cleanup canary; real excerpt profile remains disabled pending source-specific Q-306/DP-307 legal clearance | M0 |
| [DP-306](../tickets/DP-306-italy-eu-legal-research-closure-checklist.md) | **DONE** | 7/7 | Italy/EU legal closure-control register structurally complete; this is not legal clearance: all launch-sensitive Q-306 rows remain OPEN/BLOCKED with 0 qualified dispositions, handed off to DP-307 | DP-301..305 |
| [DP-307](../tickets/DP-307-qualified-legal-review-adr-policy-changes.md) | **FUTURE** | 0/9 | Qualified legal review remains BLOCKED: no accepted reviewer/scope or owner/counsel dispositions; all DP-307 acceptance criteria remain open | DP-306 |
| [DP-308](../tickets/DP-308-publication-evidence-invariants-safety-profile.md) | **DONE** | 10/10 | Publication evidence invariants + fail-closed production revalidation complete; clean HEAD full suite 1720/1720, benchmark 5/5 and isolated MiniPC/PostgreSQL acceptance green; no Q-306/DP-307 legal conclusion implied | DP-215, DP-216..224, DP-301..305 |
| [DP-309](../tickets/DP-309-high-risk-assertion-legal-status-gate.md) | **DONE** | 10/10 | High-risk/legal-status engineering gate complete: current reviewed packet + DP-310/311 separation are mandatory before serialization; full local/MiniPC regression green, while missing DP-307 qualified authority still correctly holds public enablement | DP-215, DP-304, DP-306, DP-308; DP-307 for launch |
| [DP-310](../tickets/DP-310-independent-publication-review-dual-control.md) | **DONE** | 9/9 | Independent HIGH/LEGAL dual-control engineering complete with off-DB identity-attested durable replay, canonical production enforcement, clean full-suite/DP-223/MiniPC/PostgreSQL acceptance green; no claim of legal correctness | DP-308, DP-309 |
| [DP-311](../tickets/DP-311-local-reviewer-identity-authority.md) | **DONE** | 8/8 | Local/off-DB reviewer identity authority + exact-event attested receipts for DP-310; restart/tamper/revocation, private backup/restore, disposable-PostgreSQL replay and isolated MiniPC acceptance complete | DP-310; coordinate DP-303, DP-507 |

### M4 — Public product, API, and hosting

| Ticket | Stato | AC checked | Descrizione canonica PLAN.md | Dipendenze |
|---|---|---:|---|---|
| [DP-400](../tickets/DP-400-competitive-ux-research.md) | **DONE** | 0/0 | Competitive UX research + dual-surface design brief | M0 |
| [DP-401](../tickets/DP-401-static-first-hosting.md) | **DONE** | 0/0 | Static-first hosting/deploy contract for public projection | DP-105 |
| [DP-402](../tickets/DP-402-stable-read-only-http-api.md) | **DONE** | 10/10 | Read-only HTTP API implementation over public schema v1 | DP-105, DP-401 |
| [DP-403](../tickets/DP-403-openapi-examples-versioning.md) | **DONE** | 8/8 | OpenAPI + examples + API versioning/deprecation policy | DP-402 |
| [DP-404](../tickets/DP-404-llms-txt-agent-data-documentation.md) | **DONE** | 8/8 | `llms.txt` and agent-oriented public data documentation | DP-403 |
| [DP-405](../tickets/DP-405-person-record-ui.md) | **IN PROGRESS** | 6/8 | Person archive UI; populated 12-finding chronology plus correction/reply history are green; only deliberate zero-public-record Person state and real screen-reader/manual accessibility acceptance remain | DP-105, DP-425 |
| [DP-406](../tickets/DP-406-topic-record-ui.md) | **BLOCKED** | 6/8 | Topic dossier UI implementation complete; real approved Topic/membership runtime canary still unavailable | DP-430, DP-425 |
| [DP-407](../tickets/DP-407-contentaudit-timestamped-evidence-ui.md) | **IN PROGRESS** | 7/9 | Content/source-locator UI; populated timed/written, correction/reply, privacy/offline and zero-finding fallback matrices are green; only unresolved/blocked public-state wording and real screen-reader/manual accessibility acceptance remain | DP-207, DP-105, DP-425 |
| [DP-408](../tickets/DP-408-discrepancy-position-change-comparison-ui.md) | **BLOCKED** | 6/8 | Trace/longitudinal relation UI; implementation complete, real reviewed runtime canary unavailable | DP-104, DP-105, DP-425 |
| [DP-409](../tickets/DP-409-public-search-static-indexing.md) | **IN PROGRESS** | 8/9 | Public search/indexing without new infra; deterministic static artifact/UI, browser/mobile/reduced-motion/exact-200%-zoom and live MiniPC approved-projection/search/API fingerprint convergence are green; actual screen-reader/manual accessibility and DP-408 dependency remain | DP-405..408, DP-425 |
| [DP-410](../tickets/DP-410-accessibility-performance-seo-acceptance.md) | **IN PROGRESS** | 6/8 | Accessibility/performance/SEO acceptance; rendered quality, browser zoom, SEO/static metadata, cold MiniPC performance, live static/API convergence and dependency/bookkeeping audit are green; manual AT/focus/touch/contrast acceptance remains | DP-405..409, DP-422, DP-425..429 |
| [DP-411](../tickets/DP-411-visual-concept-comparison.md) | **DONE** | 0/0 | Generate and compare five researched visual systems against UX v2 | DP-413 |
| [DP-412](../tickets/DP-412-design-tokens-component-contract.md) | **IN PROGRESS** | 8/9 | Design-token/component contract largely proven; real screen-reader + exact-200%-zoom component acceptance remains | DP-411 |
| [DP-413](../tickets/DP-413-public-ux-architecture-v2.md) | **DONE** | 0/0 | Simplify Public/Studio IA to 5 + 2 templates before implementation | DP-400 |
| [DP-414](../tickets/DP-414-studio-ia-v3-corpus-inbox-collections-verify.md) | **DONE** | 4/4 | Studio IA v3 contract closed: four private workspaces + source-bound fixture view-model proven on MiniPC; persisted adapters/workflows remain owned by DP-415..419 | DP-112, DP-113 |
| [DP-415](../tickets/DP-415-studio-corpus-search-workspace.md) | **IN PROGRESS** | 0/4 | Authenticated on-demand loopback Studio UI + metadata-only DP-116 private search API; real Garlasco top-K, persisted browser UX/AT and operator runtime proof remain open | DP-116, DP-414 |
| [DP-416](../tickets/DP-416-studio-research-collection-workspace.md) | **IN PROGRESS** | 0/4 | Authenticated loopback collection→18 Content→10 Source IDs→30 Claims→28 persisted TEXT_QUOTE_HASH attribution records (2 missing), scoped pagination and blockers, live MiniPC/HTTP; rights UNKNOWN, no captures/passages/candidates or full browser AT acceptance | DP-113, DP-114, DP-414 |
| [DP-417](../tickets/DP-417-studio-discovery-inbox.md) | **IN PROGRESS** | 0/4 | Private loopback paged discovery-hit IDs/disposition/reason listing + fixture inspector; persisted review queue/actions and safe replay/transition proof remain open | DP-209, DP-212, DP-414 |
| [DP-418](../tickets/DP-418-studio-candidate-promotion-cluster-review.md) | **IN PROGRESS** | 0/4 | Private loopback persisted match-run read-only inspector; currentness/reviewer authority unverified, no promotion until durable review + UI proof | DP-117, DP-212, DP-414 |
| [DP-419](../tickets/DP-419-studio-source-capture-passage-inspector.md) | **IN PROGRESS** | 0/4 | Private loopback persisted capture-version metadata compare; passage/media selector jump, rights-gated previews and live browser proof remain open | DP-210, DP-414 |
| [DP-420](../tickets/DP-420-garlasco-studio-usability-search-acceptance.md) | **FUTURE** | 0/5 | Garlasco operator usability and search-recall acceptance | DP-214, DP-415..419 |
| [DP-421](../tickets/DP-421-public-case-collection-contract-decision.md) | **FUTURE** | 0/3 | Public case/collection view contract decision | DP-214, M3, DP-420 |
| [DP-422](../tickets/DP-422-public-product-architecture-v3-route-migration.md) | **IN PROGRESS** | 8/9 | Public Product Architecture v3 route/template migration; canonical/legacy/internal-link contract and clean-clone acceptance green; AC-422.8 selected-v4 desktop/mobile manual comparison plus DP-408/409/429 completion gates remain | DP-405..409, DP-426..429 |
| [DP-423](../tickets/DP-423-public-marketing-brand-context.md) | **DONE** | 0/0 | Public product-marketing + brand context | DP-400, DP-413 |
| [DP-424](../tickets/DP-424-public-visual-redesign-v4.md) | **DONE** | 0/0 | Public visual redesign v4 concept selection | DP-423, DP-412 |
| [DP-425](../tickets/DP-425-public-design-system-v2.md) | **DONE** | 0/0 | Public design system v2 + component contract | DP-424 |
| [DP-426](../tickets/DP-426-home-public-shell-v4.md) | **DONE** | 0/0 | Home + public shell v4 | DP-425 |
| [DP-427](../tickets/DP-427-statement-page-v4.md) | **DONE** | 0/0 | Canonical Statement page v4 | DP-425, DP-105 |
| [DP-428](../tickets/DP-428-method-utility-pages-v4.md) | **DONE** | 0/0 | Method + trust/utility document pages v4 | DP-425 |
| [DP-429](../tickets/DP-429-explore-page-v4.md) | **IN PROGRESS** | 0/0 | Explore page v4; static-index UI, browser Back/URL restore, keyboard/dialog, reduced-motion, phone/reflow and exact 200% browser zoom automation green locally and on MiniPC; real screen-reader/manual visual acceptance remains | DP-409, DP-425 |
| [DP-430](../tickets/DP-430-public-topic-resource-contract.md) | **DONE** | 7/7 | First-class public Topic resource contract | DP-105, DP-114 |
| [DP-431](../tickets/DP-431-correction-propagation-public-surface-consistency.md) | **DONE** | 8/8 | Correction/retraction propagation proven across pages/API/search/social+JSON-LD/history, fail-closed rebuild and private-history hold; final MiniPC promotion converges live API/search/RDF validation on the approved projection fingerprint | DP-303, DP-402/403, DP-405..409, DP-422, DP-427..429, DP-434 |
| [DP-432](../tickets/DP-432-public-trust-provenance-disclosure-integration.md) | **DONE** | 8/8 | Public trust/provenance disclosure and correction-history integration AC-432.1-.8 machine-proven; upstream DP-223 attribution-integrity release sub-gate is now closed, while real screen-reader/manual judgment remains owned by DP-410 | DP-216..223, DP-308, DP-427, DP-428 |
| [DP-433](../tickets/DP-433-linked-data-rdf-interoperability-projection.md) | **DONE** | 0/0 | Stable-URI + linked-data/RDF interoperability projection; deployed `/index.nt` read-back and discovery green | DP-105, DP-403, DP-430, DP-432, DP-434 |
| [DP-434](../tickets/DP-434-public-content-resource-contract.md) | **DONE** | 8/8 | First-class reviewed public Content resource independent of published findings; projection/API/web/RDF + isolated MiniPC migration/same-origin canary complete | DP-105, DP-210, DP-401, DP-403 |

### M5 — Reliability, security, operations, and data lifecycle

| Ticket | Stato | AC checked | Descrizione canonica PLAN.md | Dipendenze |
|---|---|---:|---|---|
| [DP-501](../tickets/DP-501-threat-model-security-regression.md) | **DONE** | 0/0 | Threat model/security regression matrix + exact-tree MiniPC focused/full-suite receipt complete | M0 |
| [DP-502](../tickets/DP-502-backup-restore-drill.md) | **DONE** | 0/0 | Backup/restore drill complete; post-migration MiniPC disposable restore verifies the current 94-table runtime state | DP-501 |
| [DP-503](../tickets/DP-503-retention-matrix.md) | **DONE** | 0/0 | Retention matrix + fail-closed hold/destructive guards + exact-tree MiniPC proof complete; legal periods remain DP-306/307 | DP-304, DP-305 |
| [DP-504](../tickets/DP-504-operational-slos-taxonomy.md) | **DONE** | 0/0 | Operational SLO/taxonomy + real MiniPC private health read-back complete | M0 |
| [DP-505](../tickets/DP-505-alert-digest-runbook.md) | **DONE** | 0/0 | Alert/digest runbook + MiniPC PAGE/NO_PAGE matrix complete | DP-504 |
| [DP-506](../tickets/DP-506-cost-provider-outage-drills.md) | **DONE** | 0/0 | Cost budget policy + real isolated MiniPC provider-outage drill complete | DP-504 |
| [DP-507](../tickets/DP-507-admin-auth-surface.md) | **FUTURE** | 0/0 | AuthN/AuthZ/CSRF design for any future admin HTTP surface | only when such surface exists |
| [DP-508](../tickets/DP-508-public-intake-abuse-controls.md) | **FUTURE** | 0/0 | Public intake rate limiting/spam controls runtime | DP-302, public intake implementation |
| [DP-509](../tickets/DP-509-provenance-input-hardening.md) | **DONE** | 0/0 | Harden claim/ASR/verification provenance inputs | M0 baseline |
| [DP-510](../tickets/DP-510-provenance-quarantine-emergency-publication-hold.md) | **DONE** | 9/9 | Durable targeted provenance quarantine/hold + DP-431 cleanup + MiniPC restart/revalidation incident canary complete | DP-308; coordinate DP-501/504/505/431 |
| [DP-511](../tickets/DP-511-source-drift-supersession-revalidation-watch.md) | **DONE** | 9/9 | Source drift/supersession/rights-expiry revalidation watch + durable MiniPC canary complete | DP-210, DP-215, DP-308, DP-510 |

### M6 — Open-source and release hardening

| Ticket | Stato | AC checked | Descrizione canonica PLAN.md | Dipendenze |
|---|---|---:|---|---|
| [DP-601](../tickets/DP-601-package-development-environment.md) | **DONE** | 11/11 | Package/development environment cleanup beyond POC naming | M1 |
| [DP-602](../tickets/DP-602-ci-matrix-contributor-acceptance.md) | **DONE** | 12/12 | CI matrix and deterministic contributor acceptance | DP-601 |
| [DP-603](../tickets/DP-603-fixture-data-licensing-inventory.md) | **DONE** | 12/12 | Fixture/data licensing inventory and attribution | M3 |
| [DP-604](../tickets/DP-604-release-versioning-changelog.md) | **IN PROGRESS** | 12/12 | Release/versioning/changelog policy and release checklist; reproducible local artifacts proven, external release authority still gated | DP-601, DP-602 |
| [DP-605](../tickets/DP-605-maintainer-contributor-clean-clone.md) | **DONE** | 12/12 | Maintainer/contributor documentation dry-run from clean clone | DP-001, DP-601 |
| [DP-606](../tickets/DP-606-public-issue-labels-automation.md) | **IN PROGRESS** | 10/11 | Public issue labels/project automation; remote/public owner/security facts + clean-clone/local contract proven, owner branch-protection/hosted mutation and export/rollback dry-run pending | GitHub remote |
| [DP-607](../tickets/DP-607-optional-sdk-mcp-skill.md) | **IN PROGRESS** | 10/12 | Optional SDK/MCP/skill gate; stdlib read-only client contract, mock/deprecation and clean-clone proof green; owner surface/build-or-no-build decision pending | DP-403 |

### M7 — Stable v1 launch

| Ticket | Stato | AC checked | Descrizione canonica PLAN.md | Dipendenze |
|---|---|---:|---|---|
| [DP-701](../tickets/DP-701-brand-domain-handle-clearance.md) | **IN PROGRESS** | 5/10 | Owner identity + technical rename/MiniPC cutover complete; trademark, DNS/handles, external collision/legal and rollback evidence open | M4 |
| [DP-702](../tickets/DP-702-prelaunch-legal-security-privacy-review.md) | **FUTURE** | 6/14 | Pre-launch legal/security/privacy/evidence-safety review closure | DP-301..310, DP-501..511 |
| [DP-703](../tickets/DP-703-production-dataset-source-launch-set.md) | **IN PROGRESS** | 2/12 | Production dataset/source launch set and disclosure; launch set/rights/provider/snapshot gates remain blocked | M2, M3 |
| [DP-704](../tickets/DP-704-end-to-end-launch-rehearsal.md) | **FUTURE** | 0/13 | End-to-end launch rehearsal from source to correction | M2..M6 |
| [DP-705](../tickets/DP-705-v1-release-public-deployment.md) | **FUTURE** | 1/12 | v1.0.0 release and public deployment | DP-701..704 |

**Controllo automatico dell'inventario:** 125 righe, 125 file, DONE=86, IN PROGRESS=24, BLOCKED=6, FUTURE=9. Nessun file ticket mancante o ID duplicato.

### Fonte/stato e altri segnali di attenzione

- Il campo Status di **DP-208** nel file è «FUTURE (blocked on DP-204 and real benchmark/runtime gates)», allineato semanticamente al PLAN FUTURE.
- Il campo Status di **DP-231** nel file è «DONE (optional provider contract; production provider lookup disabled)», allineato semanticamente al PLAN DONE, ma provider non attivato.
- **DP-604** risulta IN PROGRESS pur avendo 12/12 acceptance checkbox spuntate: status governa, non promuoverlo con un conteggio automatico.
- **Root HANDOFF.md** è storico e non aggiornato: non usarlo come baseline delle 1866 prove o delle 0 catture correnti.
- Check GitHub Issues restituisce **0** issue; non dedurre che i 39 ticket non-DONE siano stati aperti/chiusi automaticamente come issue remoti.
- Il terminale agent ha restituito due errori di spawn/starter browser per i due worker richiesti. Non ci sono loro report da integrare; tutto ciò che è marcato «verificato» deriva dai comandi di ricognizione qui descritti.

**Fine handoff — fotografa la data indicata, non sostituisce le verifiche live dopo il prossimo commit.**
