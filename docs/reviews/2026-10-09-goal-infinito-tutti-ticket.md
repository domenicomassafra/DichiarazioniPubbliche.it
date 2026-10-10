# DICHIARAZIONI PUBBLICHE — GOAL INFINITO / MEGA HANDOFF

Snapshot verificato: 9 ottobre 2026 ~10:40, Europe/Rome.
Documento operativo per una NUOVA CHAT di coding. Non è un via libera al rilascio né una promessa di esecuzione asincrona.

## PROMPT DI AVVIO — da leggere e seguire integralmente

Sei il PRIME AUTONOMOUS INTEGRATOR di DichiarazioniPubbliche.it. La tua missione non è consegnare un altro audit, ma **implementare, testare, integrare, committare in modo controllato e portare alla chiusura reale TUTTI i ticket del backlog, per ondate successive, con due subagenti e un unico publisher**. Procedi automaticamente da una tranche alla prossima finché esiste lavoro realizzabile senza ulteriore intervento umano. NON fermarti dopo un solo endpoint o per chiedere genericamente «continuo?». Non mentire sugli stati e non promettere attività dopo la chiusura della sessione.

Percorso autorevole Mac Studio: /Users/domenico/Code/DichiarazioniPubbliche.it. Leggi prima AGENTS.md, PRODUCT.md, CONTEXT.md, ARCHITECTURE.md, PLAN.md e i ticket. Questo documento è il checkpoint più recente; docs/reviews/2026-10-08-mega-handoff-stato-e-piano.md è utile ma storico, non sostituisce l'HEAD attuale.

**Baseline verificata: 125 ticket, 86 DONE, 24 IN PROGRESS, 6 BLOCKED, 9 FUTURE, quindi 39 non-DONE. Release preflight: NO-GO con 41 blocchi. Git main/origin HEAD 774efdd, ma 25 file DP-417 e correlati dirty NON committati. NON cancellarli. Ultima suite locale 1.992/1.992 PASS, non su GitHub; CI GitHub di 774efdd 11/11 PASS run 37854704788. MiniPC: Garlasco PAUSED, 18/100 membri, nessun Capture, Passage, Candidate o Discovery Hit reali.** La nuova migrazione DP-417 non è in produzione.

**PRIMA mossa**: preserva, verifica e integra i file già dirty; rivedi la sicurezza del ledger/attestation DP-417, test/backup/privacy, poi crea un commit selettivo coerente come unico integratore solo se pronto. **IMMEDIATAMENTE DOPO dai la priorità alla catena di corpus reale DP-214 → DP-215**, non continuare a rifinire Studio mentre Capture/Passage/Candidate restano zero. Porta in parallelo provider/diritti, matrice legale Q-306, QA e release.

**REGOLA DI VERITÀ**: DONE richiede tutte le AC e le prove reali richieste. Un test sintetico, un commit, una CI verde, un mock, una UI, un reviewer HMAC o un sito HTTP 200 non certificano diritti, attribuzioni, autorità legale, deployment, qualità di un corpus o release. Non inventare fonti, credenziali, canary, 82 item mancanti, decisioni qualifiche, firma dell'owner, screen-reader manuale, capito? Se manca un atto umano, registralo una volta come blocker con owner esatto e passa a un ticket autonomo.

## 1. Autorità e status (non confonderli)

- Specifica: istruzioni attuali dell'utente, PRODUCT.md, CONTEXT.md, ARCHITECTURE.md, ADR, dettagli docs/tickets/DP-*.md.
- Piano unico: PLAN.md. Un ticket non è DONE solo perché ha le checkbox verdi; i test devono corrispondere all'acceptance.
- Codice: Mac Studio /Users/domenico/Code/DichiarazioniPubbliche.it, un solo main e origin GitHub. Il MiniPC /home/udodo/src/DichiarazioniPubbliche.it è un mirror runtime NON Git.
- Realtà: PostgreSQL dichiarazioni_pubbliche sul MiniPC, provider reali, fonti con diritti e autorizzazione, reviewer e release authority. Nessun agente può firmare al posto loro.
- Vecchio HANDOFF.md (3 ottobre) è obsoleto. Questo file è un handoff, NON un secondo backlog in competizione con PLAN.md.

## 2. Snapshot tecnico verificato

Git:
- HEAD 774efdd; main...origin/main, ultimo commit «feat(studio): inspect scoped Discovery provenance and blockers».
- git status --porcelain: **25 file modificati/nuovi** di implementazione DP-417 ancora locali. Nessun commit/push/deploy della tranche.
- Python 1.992/1.992 PASS, test mirati Studio/triage 55/55, ulteriore test signed + PostgreSQL isolato PASS, compileall e diff --check PASS nella sessione precedente.
- Ultima CI pubblicata SHA 774efdd: success, 11 job PASS, https://github.com/domenicomassafra/DichiarazioniPubbliche.it/actions/runs/37854704788 — non include le modifiche dirty.

MiniPC live read-only al 9 ottobre:

| Oggetto | Stato |
| --- | ---: |
| source | 14 |
| content_item | 50 |
| atomic_claim storico | 30 |
| claim_text_provenance | 28 |
| research_collection_content Garlasco | 18 |
| research:garlasco | PAUSED |
| Mancanti al target 100 Content | 82 |
| Diritti dei 18 Content inclusi | UNKNOWN, non CLEARED |
| research_discovery_manifest | 0 |
| research_discovery_hit | 0 |
| coverage_need | 0 |
| content_capture | 0 |
| passage | 0 |
| statement_candidate | 0 |
| claim_candidate | 0 |
| research_discovery_triage_decision | NOT_DEPLOYED |

Non trasformare i 30 Claim storici in «30 claim generati dal nuovo funnel». I 28 record TEXT_QUOTE_HASH non costituiscono licenza, attribuzione indipendente o approvazione pubblica. Sei lead esterni Garlasco sono soltanto candidati.

Lancio: PYTHONPATH=poc python3 tools/check_launch_preflight.py --expect-no-go = NO-GO, 41 blocker, receipt SHA 890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399.
Composizione: 2 superfici DP-507/508 da decidere; 16 quesiti legali Q-306-01..16 (14 OPEN, Q-306-04/14 BLOCKED); 4 artefatti mancanti launch_rehearsal, launch_set, prelaunch_closure, release_authority; 19 ticket preflight non DONE (201,202,203,204,215,301,304,307,405,406,407,408,409,410,604,701,702,703,704). Il preflight controlla solo 19 dei 39 aperti: NON ignorare gli altri venti.

## 3. Prima integra la tranche DP-417 locale: NON PERDERE IL LAVORO

I 25 file esistenti (preserva l'intero diff, non usare reset/clean/stash ciechi):

M PLAN.md
M config/privacy-field-inventory.v1.json
M db/schema.v1.sql
M deploy/ops/backup.sh
M docs/ops/privacy-field-inventory-20261008.md
M docs/ops/studio-local-readonly.md
M docs/tickets/DP-417-studio-discovery-inbox.md
M poc/dichiarazioni_pubbliche/ops/restore_verify.py
M poc/dichiarazioni_pubbliche/studio_local_api.py
M poc/dichiarazioni_pubbliche/studio_local_page.py
M poc/dichiarazioni_pubbliche/studio_operator_queues.py
M tests/test_studio_local_api.py
?? db/migrations/20261009-add-discovery-triage-decisions.sql
?? docs/ops/studio-discovery-triage-20261009.md
?? poc/dichiarazioni_pubbliche/studio_discovery_triage_authority.py
?? poc/dichiarazioni_pubbliche/studio_discovery_triage_contract.py
?? poc/dichiarazioni_pubbliche/studio_discovery_triage_reader.py
?? poc/dichiarazioni_pubbliche/studio_discovery_triage_store.py
?? tests/test_studio_discovery_triage_attested_pg.py
?? tests/test_studio_discovery_triage_authority.py
?? tests/test_studio_discovery_triage_contract.py
?? tests/test_studio_discovery_triage_reader.py
?? tests/test_studio_discovery_triage_schema.py
?? tests/test_studio_discovery_triage_store.py
?? tools/check_studio_discovery_triage_sql.py

Contenuto tranche: ledger append-only su Collection-scoped Discovery Hit con expected revision CAS e request-key globally unique, decisioni PRIVATE NEEDS_REVIEW/DEFERRED/REJECTED, fingerprint SHA256; nessuna approvazione/promozione/pubblicazione. SQL verifica Hit→Run→Attempt→Query→Manifest→Collection, concorrenza e replay. Revisore local file HMAC con dominio DP417_TRIAGE_V1, credential attiva, ricevuta 0700/0600 non sovrascrivibile, revoke fail-closed; record_attested prima verifica poi scrive una ANNOTAZIONE, mai approvazione. Primitiva record non-attestata resta presente per test/operator DB e segnala sempre actor_attested=false. Il loopback Studio ha lettura autenticata di Discovery provenance e history paginata; nessuna route write.

Schema, migrazione, nove campi privati nell'inventario privacy (100 tabelle/1247 campi), backup/restore coerenti; prove PostgreSQL ISOLATO + canary MiniPC pg_temp/ROLLBACK 7/7, produzione invariata. Mancano altre code, vere azioni governate, link durable HMAC→decision DB, responsabilità reviewer, diritti e nonempty live hit. DP-417 resta IN PROGRESS, 0/4 AC completate. Non applicare la migrazione al MiniPC senza authority/backup/rollback e piano sicuro.

Integra con una review security sul TOCTOU credenziale/revoca, scope/canonical fingerprint, dominio HMAC, cross-Collection redaction e connessione al database; poi test mirati, privacy/backup, suite completa una volta, commit selettivo del Prime. Se altri agenti hanno committato/edito, riconcilia prima. Non restare settimane su DP-417: subito dopo priorità corpus reale.

## 4. I 39 TICKET APERTI — priorità, funzione e dipendenze

Il dettaglio AC sta nel file individuale; leggere il ticket prima di dichiarare DONE.

### P0: corpus/provider

| ID | Stato | AC | Perché è aperto |
| --- | --- | --- | --- |
| DP-201 | BLOCKED | narrativi | Canary OmniRoute reale/costi/circuit-breaker |
| DP-202 | BLOCKED | narrativi | Parent Claim/Giuliani benchmark dopo 201 |
| DP-203 | BLOCKED | narrativi | Fan-out estrazione controllata dopo 202 |
| DP-204 | BLOCKED | narrativi | ASR live Groq, credenziale privata/costo/fallback |
| DP-208 | FUTURE | narrativi | Diarization benchmark reale dopo 204 |
| DP-214 | IN PROGRESS | 1/8 | Garlasco 100 Content autentici/5 famiglie, Capture/Passage/Candidate, coverage, review e replay |
| DP-215 | IN PROGRESS | 8/9 | Source Intelligence AC-215.9 su corpus genuino con rights/roles |
| DP-229 | IN PROGRESS | 8/9 | Challenger/counter-case sul corpus autentico |
| DP-233 | IN PROGRESS | 9/10 | Famiglia parlamentare ufficiale, canary MiniPC autorizzato |
| DP-234 | IN PROGRESS | 11/14 | DVNS contratto/diritti/API e prova autentica |

### P0: legale, privacy e public safety

| ID | Stato | AC | Perché è aperto |
| --- | --- | --- | --- |
| DP-301 | IN PROGRESS | 7/8 | Signoff policy intentionality/linguaggio Q-306/307 |
| DP-304 | IN PROGRESS | 7/8 | Privacy e minimizzazione end-to-end con policy/authority |
| DP-307 | FUTURE | 0/9 | Revisore qualificato e 16 decisioni Q-306 |

### P1: UI/accessibilità e Studio

| ID | Stato | AC | Perché è aperto |
| --- | --- | --- | --- |
| DP-405 | IN PROGRESS | 6/8 | Archivio Persona con dati approvati e AT manuale |
| DP-406 | BLOCKED | 6/8 | Topic con membership APPROVED reale |
| DP-407 | IN PROGRESS | 7/9 | Content locator, wording e screen reader |
| DP-408 | BLOCKED | 6/8 | Timeline su relazione approvata reale |
| DP-409 | IN PROGRESS | 8/9 | Search/SEO, dipendenze runtime e AT |
| DP-410 | IN PROGRESS | 6/8 | Accessibilità/performance/SEO e screen reader reale |
| DP-412 | IN PROGRESS | 8/9 | Design system, screen reader e zoom esatto 200% |
| DP-415 | IN PROGRESS | 0/4 | Corpus Studio, provenance, rights, AT reale |
| DP-416 | IN PROGRESS | 0/4 | Collections Studio, catture/diritti veri |
| DP-417 | IN PROGRESS | 0/4 | Tutte le code, blocker, azioni sicure, replay, bulk |
| DP-418 | IN PROGRESS | 0/4 | Matches Studio, attualità e review no auto-promote |
| DP-419 | IN PROGRESS | 0/4 | Capture inspector e selector jump autorizzati |
| DP-420 | FUTURE | 0/5 | Usabilità Garlasco/Recall@K sul corpus vero |
| DP-421 | FUTURE | 0/3 | Decisione sulla pagina pubblica Collection |
| DP-422 | IN PROGRESS | 8/9 | Route/template v3, confronto mobile/desktop umano |
| DP-429 | IN PROGRESS | 8/9 | Explore v4 e AT manuale |

### P2/M6-M7: operazioni, owner, release

| ID | Stato | AC | Perché è aperto |
| --- | --- | --- | --- |
| DP-507 | FUTURE | narrativi | Admin HTTP solo se autorizzato, AuthN/AuthZ/CSRF |
| DP-508 | FUTURE | narrativi | Intake pubblico solo se deciso, rate-limit/spam |
| DP-604 | IN PROGRESS | 12/12 | Owner release/authority non accettati malgrado checkbox |
| DP-606 | IN PROGRESS | 10/11 | GitHub issue/branch protection e owner mutation |
| DP-607 | IN PROGRESS | 10/12 | Decisione owner su SDK/MCP/skill |
| DP-701 | IN PROGRESS | 5/10 | Trademark, brand, DNS/handle, approvazioni/rollback |
| DP-702 | FUTURE | 6/14 | Prelaunch legal/privacy/security closure |
| DP-703 | IN PROGRESS | 2/12 | Dataset/snapshot launch_set approvato, 3 famiglie |
| DP-704 | FUTURE | 0/13 | Rehearsal end-to-end e rollback/correction |
| DP-705 | FUTURE | 1/12 | Release v1.0.0 solo dopo 701..704 e GO owner |

## 5. CRITICAL PATH, non nuovi mock

Fonte autentica e diritto/processabilità → Discovery Manifest/Query/Run/Attempt/Hit → Content e provenance → Capture immutabile/hashes/rights → Passage oppure canonical transcript segment → Entity/Statement/Claim Candidates → cluster/dedupe/matching con i 30 Claim storici → Coverage Needs → review del reviewer realmente autorizzato → Evidence/Verification/Finding → SOLO proiezione pubblica revisionata e approvata.

PRIMO tracer da sviluppare: **1 fonte reale idonea → DiscoveryHit → Content Capture → Passage/selector → Candidate → match/review → replay**, in canary isolato o con scope autorizzato e senza effetti pubblici. Poi batch per i 100 Content e cinque famiglie, MA non inventare righe o legal clearance. Se mancano diritti, registra il blocker e prepara tutti i contratti verificabili, quindi passa ad altre AC autonome.

I 18 membri attuali restano PAUSED, rights UNKNOWN. Non riscrivere una storia per far sembrare Live un fixture. DP-214.3 sui 30 Claim storici è una sola AC, non il funnel completo. DP-215.9 segue la vera acceptance del corpus.

## 6. DUE SUBAGENTI, UN SOLO INTEGRATORE E PUBLISHER

PRIME: orchestra, tutela dirty diff, assegna ownership disgiunta, integra, testa, aggiorna PLAN/ticket, commit selettivi, controlla CI, letture MiniPC e gate. NON lasciare a due subagenti la stessa migrazione/route o pubblicazione simultanea.

All'inizio chiama agents status. Riusa worker sleeping appropriati prima di spawn. Se non si avviano, annota limite e prosegui tu, non spammare nuove finestre o restare fermo.

WORKER A: Corpus DP-214/215, provenienza/diritti/source intelligence; può affrontare DP-229/233/234 se le fonti vere/permessi esistono. Own SOLO moduli/test esplicitamente assegnati, non PLAN, mai DB production write, commit o push.

WORKER B: legale/QA/release indipendente: DP-301/304/307 e matrice Q-306, browser/AT per DP-405/407/409/410/412/422/429, oppure DP-604/606/607/701..704. Non «firma» decisioni legal/owner. Own SOLO file indipendenti.

Per il primissimo batch è lecito assegnare a un worker la review SQL DP-417 e all'altro regression/QA, ma questo deve essere BREVE; poi A torna sul vero corpus e B sulle decisioni esterne/UX.

Prompt obbligatorio ai worker: «Shared repo, preserva tutte le modifiche preesistenti, own solo i file assegnati, no reset/clean/stash, no commit/push/deploy, no secret, no aggiornamento PLAN e no DONE autoattribuiti. Riferisci path, SHA se hai un commit già preesistente, test con risultati, prova reale vs fixture, blocker, prossima AC e stop del tuo scope».

## 7. IL CICLO «GOAL INFINITO» DA RIPETERE FINO AL COMPLETAMENTO

Ogni giro, DURANTE una sessione attiva:

1. OBSERVE: git status/HEAD/remote, altri agenti/worker, backlog e AC, preflight, CI, metriche MiniPC READ-ONLY. Se un altro agente sta scrivendo, delimita la proprietà.
2. PRIORITIZE: seleziona batch di 3–5 ticket/AC sinergiche, puntando alla chiusura dei blocker reali. Per ciascuno scrivi prova mancante e ruolo necessario. Una UI nuova senza corpus/rights non diventa prioritaria per default.
3. DELEGATE: due subagenti su file NON sovrapposti, Prime continua su integrazione o un terzo seam separato. Non perdere tempo in attesa se puoi lavorare.
4. IMPLEMENT: test mirati, patch piccole, contratti invarianti, SQL fail-closed, privacy, robustezza e idempotenza. No refactor estetico a tappeto.
5. VALIDATE: test focused durante coding, prove con PG isolato, browser/accessibility quando attinenti. Suite globale/benchmark/web/CI UNA VOLTA per batch. Mai classificare fixture come canary provider/live.
6. INTEGRATE: diff review, risolvi conflitti, receipt crittografici e scope, aggiorna test privacy/backup e ticket/PLAN se effettivamente soddisfatti, non prima.
7. PUBLISH SOURCE: un solo commit selettivo per tranche coerente, push GitHub solo come unico publisher quando il workflow è autorizzato e tutti i test previsti sono verificati. Un push software non è un deploy; niente promozione v1 o migrazione DB live senza condizioni legali/tecniche e owner.
8. MEASURE: conteggia DONE/IN PROGRESS/BLOCKED/FUTURE e relative AC, release blockers, MiniPC Content/100, Rights CLEARED, Capture, Passage, Candidate, Discovery Hit, Coverage Need, ultimo SHA/CI. Distingui test da runtime.
9. NEXT: scegli automaticamente il prossimo batch con progresso verificabile; ripeti dal punto 1. Non chiedere ogni volta «vuoi che continui?».

Quando sessione/context sta terminando, salva checkpoint nuovo in docs/reviews con SHA, dirty files/owner, AC chiuse, prove, blocker, comandi e PRIMO step per la prossima chat. L'assenza di tool di lavoro asincrono non va mascherata. Non produrre soltanto un altro handoff se c'è ancora lavoro tecnico che puoi eseguire.

STOP legittimo: 125 DONE con prove e rilascio GO firmato; oppure NESSUN task autonomo realmente eseguibile, solo dipendenze esterne documentate. In quest'ultimo caso stato NO-GO/BLOCKED, richieste all'owner precise, senza falsi DONE.

## 8. DEFINTION OF DONE E PRINCIPI DI SICUREZZA

- Nessuna auto-publication. Evidence retrieval != approval != verification != Finding publication.
- Mai score di veridicità/affidabilità delle persone, inferenza automatica di intenti, attribuzione senza voce/fonte provata, ranking politico o biometria voce/volto.
- Originale verbatim vs parafrasi vs traduzione distinti; autore/fonte/periodo e diritti delle citazioni sempre separati.
- Diritti COPYRIGHT/PRIVACY/source verificati; no leak di media, query, transcript, source private, token, log. Correzioni/right-of-reply append-only e privati per default.
- Provider e API: cost cap, official cred, retry/fallback, fail closed; non fingere un «canary ufficiale» usando una fixture.
- DB schema additivo e migrazioni replay-safe, CAS/concorrenza, batch/rollback, inventario privacy e backup; MiniPC prod solo con owner/autorità, monitoraggio e rollback. No mutate per far passare test.
- Ogni DONE: elenca AC, test, fixture vs live, runtime MiniPC se obbligatorio, reviewer/rights se necessario, doc/ADR, commit SHA, CI, zero side effects pubblici.
- Per UI: responsive, tastiera, touch, zoom 200%, focus, contrast, live screen reader se requisito esplicito; il browser automatico non simula l'accettazione assistiva umana.
- Release: detached clean clone, dataset approvato, licenze, preflight, security/privacy/legal, rehearsal/correction/rollback, release authority di un owner reale, poi DP-705.
- Non promuovere admin HTTP senza DP-507 e intake pubblico senza DP-508; alternativa disable in v1 SOLO su decisione formale owner, non cancellando i gate opportunisticamente.

## 9. ONDATE PROPOSTE (modificare secondo prove vere)

W0: preservazione/integratore della dirty tranche DP-417, security review + commit selettivo; non marcare DP-417 DONE né deployare migrazione.
W1: DP-214 e DP-215 — UN tracer completo di corpus reale legalmente idoneo; verso 100 fonti/5 famiglie per batch senza inventare diritti. In parallelo worker B prepara owner decision register legale/QA.
W2: DP-229/233/234 con source-family autentiche, DP-201→202→203 e 204→208 se credenziali/budget; DP-301/304/307 con signoff esterno reale.
W3: UI e AT reale DP-405..410, 412, 422, 429; Studio DP-415..419 sulle righe vere, DP-420/421 dopo dipendenze. Evita «nuovo endpoint» senza AC.
W4: DP-604/606/607 e DP-701/702/703 poi DP-704 rehearsal, infine DP-705 con GO formale.

## 10. COMANDI OPERATIVI (partire read-only)

    cd /Users/domenico/Code/DichiarazioniPubbliche.it
    git status --short --branch
    git rev-parse HEAD
    git log -5 --oneline
    git diff --check
    gh run list -R domenicomassafra/DichiarazioniPubbliche.it -L 5
    python3 tools/check_repository_contract.py --only tickets
    PYTHONPATH=poc python3 tools/check_launch_preflight.py --expect-no-go
    python3 -m compileall -q poc tests
    PYTHONPATH=poc python3 -m unittest tests.test_studio_discovery_triage_attested_pg tests.test_studio_discovery_triage_schema tests.test_studio_discovery_triage_authority -q
    PYTHONPATH=poc python3 -m unittest discover -s tests -q
    PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
    cd web && npm run check && npm run build && cd ..
    ssh minipc 'systemctl --user is-active dichiarazioni-pubbliche-web.service'
    ssh minipc 'systemctl --user is-active dichiarazioni-pubbliche-source-poll.timer'
    ssh minipc 'systemctl --user is-active dichiarazioni-pubbliche-worker.timer'
    ssh minipc 'curl -fsS --max-time 5 http://127.0.0.1:18090/api/v1/health'
    ssh minipc 'psql -XqAt -v ON_ERROR_STOP=1 -d dichiarazioni_pubbliche -c "BEGIN READ ONLY; SELECT count(*) FROM content_capture; ROLLBACK;"'

Non lanciare test globali ad ogni file; inizia con targeted e poi UNA suite/CI per tranche. Mai usare git reset --hard, git clean -fd, stash -u, migrazioni di produzione o push concorrenti senza controllo della working tree.

## 11. INPUT UMANI CONSOLIDATI (non ritardare gli altri task)

1. Revisore legale qualificato e decisioni Q-306-01..16, DP-307, policy intentionality/diritti/privacy/correzioni.
2. Fonti autentiche legalmente processabili con exact rights/retention, almeno 1 per primo tracer, poi 100 Content e 5 famiglie, successivamente dataset launch set approvato.
3. OmniRoute official meaningful canary/cost cap, Groq ASR cred, DVNS API e licenza/contract; tutte le credenziali PRIVATE fuori Git.
4. Owner release: DNS/brand/trademark/handles, branch policy, scope DP-507/508, SDK DP-607, autorizzazione migrazione/backups/rollback, decisioni M7 GO.
5. QA assistiva realmente manuale per le AC che la richiedono; non segnare PASS finto.

Registra una volta per ciascun input chi deve agire, quale specifico documento/decisione serve e che cosa sblocca. Se manca, scegli un task tecnico differente. Non chiedere all'utente 16 domande una alla volta.

## 12. REPORT OBBLIGATORIO DOPO OGNI WAVE

    GOAL INFINITO — Wave N — YYYY-MM-DD HH:mm Europe/Rome
    Git: HEAD, origin, dirty files, nuovo SHA, CI run/esito
    Ticket: DONE (+delta), IN PROGRESS, BLOCKED, FUTURE, aperti (-delta)
    AC realmente chiuse: elenco con test/receipts e diritti
    Rilascio: NO-GO/PENDING-OWNER; blocker N (-delta); Q-306 aperti N
    MiniPC: Garlasco PAUSED/ACTIVE, Content N/100, rights-cleared N,
            Capture N, Passage N, StatementCandidate N, ClaimCandidate N,
            DiscoveryHit N, CoverageNeed N, AtomicClaim storici N
    Test: focused N/N, full N/N o NON ESEGUITA, web/benchmark/CI
    Deliverables: file/route/schema, prova runtime, zero side effects pubblici
    Input esterni: solo richieste già consolidate e owner
    Prossimi 2 task autonomi: ticket, AC, owner files, prova richiesta

La differenza tra «software implementato» e «ticket DONE» è il centro di questo incarico. L'obiettivo è realmente ridurre i 39 ticket aperti, non produrre più report o schermate. **Finché esiste lavoro autonomo eseguibile, continua a implementare e integrare.**

---

NOTA DI BOOTSTRAP: se la nuova chat non ha accesso a questo path, incolla per intero il contenuto del documento; altrimenti chiedi di leggerlo e partire DIRETTAMENTE dal punto 3 e poi dalla W1. Il documento storico docs/reviews/2026-10-08-mega-handoff-stato-e-piano.md contiene l'inventario dei 125 ticket, ma lo stato aggiornato è sempre quello di PLAN.md verificato ad ogni ondata.
