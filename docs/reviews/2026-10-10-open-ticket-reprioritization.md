# Dichiarazioni Pubbliche — audit delle 35 aperture e proposta di riprioritizzazione

**Data:** 2026-10-10 · **Tipo:** revisione di prodotto/backlog, senza approvazioni o variazioni di status.
**Autorità:** `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`, `PLAN.md`, `LAUNCH.md` e le AC in `docs/tickets/`. Le azioni sotto sono **proposte**, non decisioni eseguite. Consultare anche `FINAL-PENDING-GRILLING-2026-10-10.md`, che conserva il dettaglio delle prove per singolo ticket.

## Fotografia verificabile e significato del WIP

Al controllo, checkout autorevole su `main` **`a104f0f`**, **una worktree**, nessun altro branch locale, stash vuoto e `git status --short --branch` pulito. `python3 tools/report_ticket_status.py --json` restituisce **125** ticket (**90 DONE, 20 IN PROGRESS, 6 BLOCKED, 9 FUTURE, 0 READY; 35 non DONE**) e `files_agree_with_plan=true`. `python3 tools/check_launch_preflight.py --expect-no-go` restituisce **NO-GO / 49** e receipt `96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f`: 16 questioni giuridiche Q-306 non disposte, quattro artefatti di release mancanti e 29 gate di ticket, che **non** equivalgono a 49 problemi indipendenti. Questa verifica non riesegue CI, test completi o accesso live al MiniPC.

**20 `IN PROGRESS` non significano 20 cambi Git incompiuti.** In gran parte rappresentano codice già integrato con una AC residua: prova su dati reali autorizzati, valutazione manuale di accessibilità, migrazione non distribuita oppure decisione legale/editoriale. Anche `BLOCKED` e `FUTURE` possono avere componenti implementati, ma senza prova d'accettazione. `DONE` implica la Definition of Done del rispettivo ticket; nessuno status viene cambiato perché un controllo sintetico è verde.

**Due prodotti e due soglie:** la preview informativa di `LAUNCH.md` contiene sei pagine statiche con proiezione approvata anche vuota, e richiede il profilo ristretto delle aree DP-304/307/410/701/702. L'archivio di claim reali e lo **stable-v1** chiedono fonti, diritti, reviewer, pubblicazione/correzione, rehearsal e release authority ulteriori. Il fatto che HTTPS sul MiniPC risponda non equivale a un deploy dell'ultimo codice né all'approvazione editoriale. La UX corrente può essere riprogettata **dopo audit indipendente e grilling**: la precedente implementazione v4 `DONE` attesta consegna del relativo contratto, non gradimento né qualità di design finale.

## Criterio di ordinamento

1. **Protezione e autorizzazioni del prodotto oggi visibile.** Decidere contenuto della preview, titolare, contatti, privacy e responsabilità; misurare la sua accessibilità reale.
2. **Provare il valore centrale con una fonte.** Una fonte primaria **autorizzata**, un Content, una Capture immutabile, un Passage attribuibile, una Candidate revisionabile, replay e zero pubblicazione automatica su MiniPC. Se Garlasco resta privo di diritti, decidere esplicitamente un pilota testuale più delimitato e l'impatto sul requisito 100 item/cinque famiglie; nessuna sostituzione tacita.
3. **Misurare tempo umano, costo ed errori.** L'esito del primo slice e poi di dieci item determina cosa scalare, quali UI servono e dove usare provider. Non impegnare capacità editoriale in un'ulteriore ondata di pagine demo prima di quel dato.
4. **Preparare la release con prove accettate.** Il percorso fino a DP-705 resta separato dal rilascio delle pagine informative.

`DO NOW` significa **prossima prova o decisione da aprire adesso**; può richiedere una persona autorizzata prima di qualunque operazione. `DEFER` significa sospendere lavoro e consumo finché non si verifica il trigger indicato. `MERGE CANDIDATE` è una **convergenza di campagna di test, owner o scope da valutare**: non accorpa AC o cancella ticket automaticamente. `DELETE ONLY AFTER OWNER DECISION` è una **proposta condizionale di non-adoption/ritiro di ambito**, da formalizzare in ADR mantenendo lo storico; non autorizza a cancellare file.

## Matrice esaustiva: 35 su 35

I ticket restano ordinati per catena di valore, con status **originale** e priorità relativa all'iniziativa. `P0` ha valore decisionale o release-preview immediato; `P1` segue la scelta di fonte; `P2` è accettazione su corpus/risultati veri; `P3` è un'opzione futura o v1 finale. I casi di sovrapposizione sono discussi dopo la tabella.

| Ticket / status | Priorità e azione proposta | Prossima prova, condizione o criterio di rinvio |
|---|---|---|
| **DP-304 · IN PROGRESS** | **P0 · DO NOW** | Owner/privacy reviewer: finalità, basi, retention, inventario JSON/log/account e contatto del profilo informativo; evidenza distinta per il corpus editoriale. |
| **DP-307 · FUTURE** | **P0 · DO NOW** | Identificare reviewer Italia/UE, aprire le 16 Q-306 con owner/scope ed evidenza; prima separare quelle necessarie per la preview da quelle per claim/intake. Il legale deve davvero decidere. |
| **DP-410 · IN PROGRESS** | **P0 · DO NOW** | Un solo ciclo manuale reale telefono/tastiera/screen reader/focus/contrasto, con verbale, screenshot e difetti tracciati; coprire AC di DP-405/407/409/412/422/429 senza dichiararli chiusi per associazione. |
| **DP-701 · IN PROGRESS** | **P0 · DO NOW** | Owner prova identità, controllo dominio/contatto/handles, eventuale collisione e rollback; clearance marchio professionale ancora esterna. |
| **DP-702 · FUTURE** | **P0 · DO NOW** | Preparare e richiedere **decisione circoscritta sulla preview informativa**; ticket v1 completo resta dipendente dalle approvazioni e dalla review futura del dataset. |
| **DP-214 · IN PROGRESS** | **P1 · DO NOW** | Decisione esplicita sul pilota Garlasco (18 Content, rights UNKNOWN nell'ultimo readback storico) o cambio di scope tramite ADR; quindi una catena vera Discovery→Capture→Passage→Candidate su MiniPC, non pg_temp sintetico. |
| **DP-215 · IN PROGRESS** | **P1 · DO NOW** | Per il pilota, ogni Source deve avere ruolo, autorità contestuale, rights e derivazione revisionati; AC-215.9/100 item non si chiude col solo motore già scritto. |
| **DP-233 · IN PROGRESS** | **P1 · DO NOW** | Valutare *una* fonte parlamentare testuale ufficiale come prima alternativa economica: testo, licenza/uso, quote span/versione e canary MiniPC; l'adapter non autorizza la fonte. |
| **DP-703 · IN PROGRESS** | **P1 · DO NOW** | Far decidere owner e source reviewer un primo source set e manifest con diritti, divulgazione e costo; il ticket di **launch set completo** resta aperto finché mancano 3 famiglie e snapshot accettato. |
| **DP-301 · IN PROGRESS** | **P1 · MERGE CANDIDATE** | Consolidare *solo la sessione decisionale* AC-301.8 con Q-306/DP-307, mantenendo la policy anti-intenzionalità e la sua prova come AC autonoma. |
| **DP-405 · IN PROGRESS** | **P1 · MERGE CANDIDATE** | Sessione DP-410: stato Person con zero record pubblici + test AT specifico; evitare campagna screen reader separata. |
| **DP-407 · IN PROGRESS** | **P1 · MERGE CANDIDATE** | Sessione DP-410: wording per stati irrisolti/bloccati e accessibilità Content con provenienza; tracciare entrambi gli esiti individuali. |
| **DP-409 · IN PROGRESS** | **P1 · MERGE CANDIDATE** | Sessione DP-410: AT per ricerca/indice e pubblica convergenza con API; dipendenza di DP-408 resta aperta. |
| **DP-412 · IN PROGRESS** | **P1 · MERGE CANDIDATE** | Token/componenti valutati nello stesso campione manuale DP-410, incluse modalità zoom/contrasto/focus. |
| **DP-422 · IN PROGRESS** | **P1 · MERGE CANDIDATE** | Congelare il confronto delle route correnti e includere v4 desktop/mobile nel report UX indipendente e in DP-410; futura architettura del redesign richiede nuova decisione owner, non riscrittura preventiva. |
| **DP-429 · IN PROGRESS** | **P1 · MERGE CANDIDATE** | Sessione DP-410: Explore con screen reader/reflow e contenuti pubblici reali o stato vuoto veritiero; AC propria resta distinta. |
| **DP-416 · IN PROGRESS** | **P2 · MERGE CANDIDATE** | Raggruppare con DP-420 la prova operatore Collection→Capture/Passage→Candidate e AT su dati autorizzati; il runtime oggi è limitato a dati preesistenti. |
| **DP-417 · IN PROGRESS** | **P2 · DEFER** | Nessuna promozione di schema/mutazione verso MiniPC finché diritti, owner operatore e governance del ledger non siano certificati; poi Inbox non vuota, CAS, bulk e leak test. |
| **DP-418 · IN PROGRESS** | **P2 · DEFER** | Serve reviewer autenticato, decisione persistita e race revoca/promozione sicura in DB, oltre a workflow UI; sola vista read-only/matching fixture insufficiente. |
| **DP-419 · IN PROGRESS** | **P2 · DEFER** | Prima Capture reale autorizzata, poi playback/seek media, confronto versioni e controlli privacy/AT su device; non costruire player sopra Capture assenti. |
| **DP-420 · FUTURE** | **P2 · DEFER** | Dopo DP-214 e Studio 415..419: task operatore veri, tempo/click, Recall@K e accessibilità; alimenta la scelta di Case pubblico. |
| **DP-406 · BLOCKED** | **P2 · DEFER** | Topic dossier da verificare su Topic/membership revisionati, oggi non disponibili nella proiezione approvata; fixture UI non chiude AC-406.6. |
| **DP-408 · BLOCKED** | **P2 · DEFER** | Trace soltanto con relazione longitudinale umanamente revisionata e test AT; nessuna inferenza su intenzione/menzogna. |
| **DP-229 · IN PROGRESS** | **P2 · DEFER** | Prima un caso ad alto rischio legalmente attivabile: reviewer/challenger indipendente **persistente**, waiver qualificato e attestazione AC-229.8; il runtime ora tiene correttamente il blocco. |
| **DP-234 · IN PROGRESS** | **P2 · DEFER** | Chiedere contratto di accesso/licenza DVNS e valore incrementale rispetto a fonte parlamentare prima di un canary; no secondo adapter live in parallelo per completare il numero. |
| **DP-201 · BLOCKED** | **P2 · DEFER** | Solo credenziale, quota, esecuzione ufficiale OmniRoute significativa e ricevuta costo/modello, senza sostituzione opportunistica del provider. |
| **DP-202 · BLOCKED** | **P2 · DEFER** | Conseguenza di DP-201: parent live e benchmark Giuliani sul percorso ufficiale, prima dei child. |
| **DP-203 · BLOCKED** | **P2 · MERGE CANDIDATE** | Pianificare unica campagna DP-201→202→203 di accettazione, conservando gate autonomo di costi/fanout/replay. Zero child dopo parent fallito. |
| **DP-204 · BLOCKED** | **P2 · DEFER** | Solo audio e Groq ASR con credenziale, dati/trasferimento autorizzati, costi e risultato reale. Non è prerequisito per il primo source testuale. |
| **DP-208 · FUTURE** | **P3 · DELETE ONLY AFTER OWNER DECISION** | Opzione diarizzazione: se il prodotto sceglie esplicitamente di non adottarla, discutere ritiro tramite ADR **dopo** prova di accettabilità di alternative non biometriche; altrimenti tornare al benchmark dopo DP-204. |
| **DP-421 · FUTURE** | **P3 · DELETE ONLY AFTER OWNER DECISION** | Vista pubblica Case/Collection opzionale: decisione GO/NO-GO solo dopo DP-420. NO-GO è un esito valido dell'AC; eventuale pensionamento del relativo **scope futuro**, non cancellazione della decisione storica. |
| **DP-507 · FUTURE** | **P3 · DEFER** | Riattivare *prima* di un'eventuale mutazione admin HTTP esposta in rete. Gli account lettore Google OIDC non danno privilegi Studio/editoriali. |
| **DP-508 · FUTURE** | **P3 · DEFER** | Riattivare *prima* dell'intake pubblico di rettifiche/segnalazioni: abuse/rate/privacy/retention/rollback su MiniPC. Senza intake attivo è corretto restare FUTURE. |
| **DP-704 · FUTURE** | **P3 · DEFER** | Solo su source set e legal gate accettati: rehearsal su MiniPC fonte→correzione, fallimenti, rollback, replay e owner signoff. |
| **DP-705 · FUTURE** | **P3 · DEFER** | Ultimo nodo: release stable-v1 soltanto con DP-701..704, manifest/autorità di release, candidata pulita, smoke e rollback verificato. |

**Contabilità della proposta:** 9 `DO NOW`, 9 `MERGE CANDIDATE`, 15 `DEFER`, 2 `DELETE ONLY AFTER OWNER DECISION` = **35**. Le 35 righe coprono esattamente i 35 ID dell'output di `report_ticket_status.py` (nessuno status canonico cambia). I ticket legali/di prova possono progredire in parallelo per raccolta **dell'evidenza**, non per auto-approvazione.

## Duplicazioni, obsolescenza, scope e rischio di cancellare la cosa sbagliata

- **Campagna AT pubblica duplicata nella pianificazione:** DP-405/407/409/412/422/429 ripetono criteri manuali/test di flusso già coordinabili da DP-410. **Un'unica sessione, verbale con righe per ciascuna AC**, correzioni nel rispettivo ticket. DP-406/408 richiedono in più dati approvati che tale sessione non può inventare. Nessun ticket è duplicato 1:1.
- **Campagna Studio vs ticket feature:** DP-416/417/418/419 dipendono da Content/Capture/Candidate reali, DP-420 può diventare prova d'insieme. Non unire le loro responsabilità di sicurezza o DB; consolidare scenari di operatore dopo DP-214. DP-417 richiede ancora una vera decisione su migrazione e owner, e la mitigazione read-only non è accettazione di mutate.
- **Provider e fonti concorrenti:** DP-201/202/203 sono tre gate dello stesso esperimento ufficiale; DP-204/208 è altra catena audio; DP-233 e DP-234 sono adapter complementari con diritti indipendenti. Consolidare il calendario dei canary, non spacciare uno per prova dell'altro. L'obiettivo editoriale potrebbe essere raggiunto prima con testo originale autorizzato.
- **Signoff distinti:** DP-301 e DP-307 si incontrano nello stesso tavolo Q-306; DP-304 tratta dati/retention; DP-702 è la review di lancio; DP-701 è identità/brand. Una persona può essere owner di più decisioni, ma la firma su una decisione non chiude automaticamente le altre AC.
- **FUTURE deliberati:** DP-507/508 devono restare dormienti finché manca la rispettiva superficie; DP-208 e DP-421 sono le opzioni più adatte a un eventuale **NO-BUILD** esplicito. Solo dopo una scelta scritta si può considerare chiusura per non-adozione, supersessione o archiviazione: preservare storico, identificativi e criteri verificabili.
- **Storia non corrente:** le sezioni Wave 9–19 di `PLAN.md` conservano contatori storici **86/24/6/9**, **NO-GO/41** e note di WIP Mac-only. Non sono il checkpoint attuale **90/20/6/9**, **NO-GO/49**. Il checkpoint alto in PLAN e il report macchina hanno precedenza, senza cancellare le ricevute passate. `DONE` di v4 non risolve la richiesta dell'owner di una futura **riprogettazione completa**: prima review critica indipendente di route/sorgenti/UX, poi grilling e nuovo brief/ADR.

## Albero delle dipendenze e prove discriminanti

```text
Scelta owner A: preview informativa / primo record reale / stable-v1
  ├─ preview → DP-304 + DP-307 + DP-410 + DP-701 + DP-702
  │              → decisioni/ricevute specifiche → build/proiezione approvate → smoke HTTPS
  └─ record reale → proprietario fonte + diritti + reviewer + budget
                   → DP-233 (eventuale fonte testuale) oppure DP-214/215 (pilot concordato)
                   → Discovery→Capture→Passage→Candidate→review/promotion (DP-417/418)
                   → DP-420 tempo/click/Recall@K → DP-421 decisione Case pubblico
                   → DP-703 set pubblicabile + DP-301/304/307/702 policy
                   → DP-704 replay, correction, rollback → DP-705 stable-v1

Esperimenti opzionali separati:
  OmniRoute DP-201 → DP-202 → DP-203       Groq DP-204 → DP-208
  DVNS DP-234 (licenza)                    Admin DP-507 / intake DP-508 (trigger)
```

**Tre tranche ordinate, senza inventare scadenze:** (1) *decisioni P0 + UX verificata* — owner/reviewer e permessi, prove della preview, audit UX indipendente prima del redesign; (2) *slice su una fonte vera* — no approvazioni in bianco, replay MiniPC e misura di qualità/costi; (3) *operatori + eventuale record pubblicato e scale-up* — review workflow, pubblicazione solo con firma, correzione e successiva scelta delle superfici v1. Il primo *kill/pivot gate* è l'assenza di **1 fonte autorizzata + 1 Capture/Passage + 1 Candidate revisionata** dopo due tranche editoriali: la decisione è dell'owner e va documentata, senza abbassare i requisiti di attribuzione e privacy.

## Probe che il prossimo agente può ripetere senza scritture in produzione

```bash
cd /Users/domenico/Code/DichiarazioniPubbliche.it
git status --short --branch
git worktree list --porcelain
git branch --list --verbose
git stash list
git log -1 --oneline
python3 tools/report_ticket_status.py --json
python3 tools/check_launch_preflight.py --expect-no-go
python3 tools/check_repository_contract.py
```

Per il MiniPC: prima identificare **SHA/mirror/schema effettivi** e leggere gli attuali `docs/ops/garlasco-research-readiness-20261008.md`, `docs/ops/private-candidate-extraction-20261008.md`, `docs/ops/dp201-official-shadow-preflight-wave26-20261010.md`, `docs/ops/informational-preview-bundle-preflight-20261010.md`. Un controllo SQL deve eseguire **solo SELECT** in transazione `default_transaction_read_only=on` con identità autorizzata; non dedurre diritti da `rights UNKNOWN`, non fare provider call senza budget/consenso e non usare dati demo come artefatti di release. Il report `tools/report_research_pilot.py` ha parametri e contesto nel runbook Garlasco. Ogni prova registri host, dataset, commit, data, reviewer, conteggi, hash e limiti osservati.

## Skill di grilling locale: reperita, nome effettivo e vincoli

- `/Users/domenico/.agents/skills/plan-grilling/SKILL.md` — trovato e letto (24 righe). Le copie sotto `/Users/domenico/.codex/skills/plan-grilling/` e `/Users/domenico/.claude/skills/plan-grilling/` hanno lo **stesso SHA-256** del file verificato (`f86f4716c4c2a2475aa1d578e76bd4b40351a2ff829384b4eecdec1a9947876d`).
- `/Users/domenico/.agents/skills/code-architecture-review/references/grilling-protocol.md` — trovato e letto: richiama `plan-grilling` per interrogare scelte e dipendenze architetturali.
- Nessuna skill con nome esatto `grilling-me` è risultata nella scansione degli usuali percorsi locali. **Non inventare un comando `/grilling-me` o un'invocazione runtime.** Se l'ambiente dell'agente espone quella skill, leggerne istruzioni e catalogo prima di usarla.

La skill reale **`plan-grilling`** impone un **albero di decisioni in round**: chiedere in ogni round l'intera *frontier* di decisioni con prerequisiti già soddisfatti, numerare le domande e offrire una risposta raccomandata (`❓ Qn`, `➡️`); attendere le risposte dell'owner, poi ricostruire la frontier. I fatti tecnici vanno accertati dall'agente, non delegati all'owner; decisioni senza prerequisiti soddisfatti restano al round successivo. La sessione termina quando l'albero è attraversato e condiviso, prima di agire sulle scelte. Questo differisce dal prompt già scritto in `FINAL-PENDING-GRILLING-2026-10-10.md` che chiedeva **12 domande una per volta**: chi condurrà il grilling dovrà scegliere **esplicitamente** il protocollo da applicare e aggiornare quel prompt, senza presentare le due modalità come identiche.

**Decisioni iniziali da sottoporre dopo assessment autonomo:** (A) promessa editoriale esatta, (B) preview con zero claim e chi firma, (C) primo dataset/fonte e diritto effettivo, (D) responsabile reviewer e costo umano, (E) criterio misurabile per rinviare provider, Case pubblico e redesign. I follow-up dipendono dalle risposte: non scrivere ADR di approvazione senza averle ottenute.
