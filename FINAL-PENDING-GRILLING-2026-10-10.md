# Dichiarazioni Pubbliche — pending definitivi e briefing per il grilling

**Checkpoint:** 10 ottobre 2026, Europe/Rome. **Scopo:** consegna critica a un agente nuovo, senza promuovere ticket o release. Questo documento è una fotografia ragionata; le autorità correnti sono [PRODUCT.md](PRODUCT.md), [CONTEXT.md](CONTEXT.md), [ARCHITECTURE.md](ARCHITECTURE.md), [PLAN.md](PLAN.md), [docs/tickets/](docs/tickets/), [AGENTS.md](AGENTS.md) e [LAUNCH.md](LAUNCH.md). Il contesto tecnico dettagliato sta in [MEGA-HANDOFF-2026-10-10.md](MEGA-HANDOFF-2026-10-10.md). I documenti storici sotto docs/reviews/ rimangono prove datate, non un backlog parallelo.

## 1. Stato accertato e limite delle prove

- **Contabilità verificata il 10/10 sul checkout locale:** 125 ticket, **90 DONE, 20 IN PROGRESS, 6 BLOCKED, 9 FUTURE, 0 READY**, quindi **35 aperti**. Il report macchina conferma corrispondenza tra PLAN e intestazioni di ciascun ticket. Non confondere DONE tecnico su alcune acceptance criterion con DONE del ticket.
- **Git al preflight documentale:** repository autorevole `/Users/domenico/Code/DichiarazioniPubbliche.it` su `main`; sorgente già su `origin/main` a `a66e987` prima dei nuovi commit esclusivamente documentali. Il coordinatore esegue il push finale e verifica SHA locale/remoto con `git ls-remote`: verificare sempre status e log, non trattare questo documento come un tag Git. Un push Git non distribuisce il backend.
- **Release editoriale stable-v1:** NO-GO, **49 blocker** da tools/check_launch_preflight.py --expect-no-go: **16** decisioni Q-306 (**14 OPEN, 2 BLOCKED**), **4** artifact owner mancanti (launch_set, launch_rehearsal, prelaunch_closure, release_authority), **29** gate di ticket non completati. Non sono 49 bug indipendenti né 49 dei 35 ticket.
- **Sito pubblico informativo:** LAUNCH.md definisce una via separata per sei route statiche, indice potenzialmente vuoto e zero dichiarazioni fittizie. I 30 ticket esterni al perimetro restano aperti; **cinque aree di signoff** ancora necessarie per la preview sono DP-304/307/410/701/702. Nessun documento equivale a firma del proprietario o a parere legale. Verifica read-only 10/10: Cloudflare Tunnel → MiniPC, sei route HTTPS 200, Studio 404, proiezione approvata **vuota**; l'HTML live ha SHA-256 `60e76f42a138b8a5fde390cee1c21c8b2053ee3f661c7a3ef78f49aebe49a1b0`, identico al file del MiniPC ma **non** alla nuova build Mac. Nessun deploy della nuova build è stato autorizzato; il sito precedente rimane funzionante.
- **Runtime e dati:** MiniPC /home/udodo/src/DichiarazioniPubbliche.it è mirror non-Git, PostgreSQL dichiarazioni_pubbliche. Nessuna prova attuale di deploy della tranche, delle migrazioni private DP-417 o di un percorso completo con fonte reale autorizzata. L'ultimo readback Garlasco documentato aveva 18 Content con rights UNKNOWN, 0 capture autorizzati, 0 nuove candidate, 30 claim preesistenti e 82/100 elementi non presenti; va verificato nuovamente sul runtime prima di prenderlo come misura attuale.
- **Prove storiche della tranche, non ripetute per questo documento:** Python **2390/2390** PASS, benchmark sintetico **5/5** PASS, web build/isolated browser e confine Studio/demo PASS. In questa tranche documentale sono stati rieseguiti report ticket, preflight e repository contract; i test integrati non misurano accuratezza reale, diritti, approvazioni o capacità del MiniPC di pubblicare.

## 2. Inventario esaustivo: ciascuno dei 35 pending

Le colonne usano le intestazioni canoniche degli esatti ticket; l'azione proposta è la **prossima prova discriminante**, non una nuova acceptance criterion. Gli status di questo snapshot derivano da tools/report_ticket_status.py --json.

### A. Fonti, estrazione, modelli, indipendenza — 10 ticket

| Ticket e stato | Cosa esiste; cosa manca per chiudere davvero | Sblocco o decisione |
|---|---|---|
| [DP-201](docs/tickets/DP-201-omniroute-meaningful-canary.md) **BLOCKED** | Routing/quote e receipt locali non dimostrano un canary del provider ufficiale OmniRoute con risposta utile e costo reale. | Credenziale e quota autorizzate; canary ufficiale strutturato con log di costo/modello e verdetto. |
| [DP-202](docs/tickets/DP-202-parent-canary-giuliani-benchmark.md) **BLOCKED** | Benchmark parent/Giuliani da certificare sul medesimo percorso live del 201. | AC del parent, benchmark accurato, receipt e costo prima dei child job. |
| [DP-203](docs/tickets/DP-203-controlled-claim-fanout.md) **BLOCKED** | Guard per fanout presente; nessun fanout autorizzato finché parent live non supera gate. | DP-202 PASS, limiti economici, replay e zero child su parent fallito. |
| [DP-204](docs/tickets/DP-204-live-remote-asr-receipt.md) **BLOCKED** | Test/fallback locali non sono prova Groq ASR reale. | Credenziale, audio consentito, costo, privacy e risultato Groq tracciato. |
| [DP-208](docs/tickets/DP-208-diarization-benchmark-go-no-go.md) **FUTURE** | Harness metriche esiste; mancano audio/speaker/time reference reali e decisione GO/GO_BOUNDED/NO-GO. | DP-204 e benchmark su campione consentito, senza identificazione biometrica. |
| [DP-214](docs/tickets/DP-214-garlasco-research-collection-tracer-bullet.md) **IN PROGRESS** | AC-214.3 diagnosi privata completata, SQL sintetico in pg_temp; AC-214.1/.2/.4-.8 restano. Nessuna catena real source→Discovery→Capture→Passage→Candidate accettata. | Una fonte e manifest approvati, rights/lineage attuali, canary vero MiniPC con readback e revocation/concurrency review. |
| [DP-215](docs/tickets/DP-215-source-intelligence-evidence-suitability.md) **IN PROGRESS** | Source Intelligence e suitability tecnici; AC-215.9 non chiusa, pilot da 100/5 famiglie senza provenance accettata. | Record source/role/rights, manifest revisionato e ricevuta MiniPC; rinegoziare 100/5 via ADR solo se cambia esplicitamente scope. |
| [DP-229](docs/tickets/DP-229-adversarial-challenger-countercase.md) **IN PROGRESS** | 8/9 AC dimostrati; AC-229.8 priva di challenger indipendente firmato o eccezione qualificata. | Ricercatore/reviewer indipendente con attestazione durevole e verifica su caso reale. |
| [DP-233](docs/tickets/DP-233-parliamentary-speech-video-alignment-adapter.md) **IN PROGRESS** | Adapter e version replay fixtures, sonde Senato metadata; manca AC-233.10, famiglia parlamentare e diritti specifici approvati per speech/transcript/media. | Prova su testo originale di un singolo atto/resoconto, quote span+hash, owner source rights, MiniPC canary. |
| [DP-234](docs/tickets/DP-234-dvns-structured-evidence-adapter.md) **IN PROGRESS** | Adattatore di evidenza strutturata read-only in test; nessuna approvazione API/licenza/provenienza DVNS reale. | Contract legale e tecnico del provider, ruolo evidenza preciso, un canary MiniPC senza promuovere fonte a prova automaticamente. |

### B. Policy giuridica, privacy e linguaggio — 3 ticket

| Ticket e stato | Cosa manca | Sblocco o decisione |
|---|---|---|
| [DP-301](docs/tickets/DP-301-intentionality-lie-policy.md) **IN PROGRESS** | Guard anti-intenzionalità/menzogna e person score in codice; **AC-301.8** resta aperta. | Disposizioni DP-306/307 firmate sui testi/limiti editoriali, senza inferire dolo. |
| [DP-304](docs/tickets/DP-304-privacy-minimization-sensitive-person-policy.md) **IN PROGRESS** | Inventario tecnico documentato e diversi runtime guard; AC-304.1, JSON/log profondi, basi giuridiche, ruoli, retention, account e dati sensibili non chiusi. | Titolare/DPO-counsel decidono finalità, campo, retention, contatti e policy; prova sul MiniPC. |
| [DP-307](docs/tickets/DP-307-qualified-legal-review-adr-policy-changes.md) **FUTURE** | Nessuna revisione qualificata delle **16** questioni Q-306 con owner/reviewer ed evidenza firmata. | Parere mirato Italia/UE, decision register e ADR per ogni change di policy; nessuna finzione di legal signoff. |

### C. Lettura pubblica, proiezione, UX e accessibilità — 9 ticket

| Ticket e stato | Cosa manca | Sblocco o decisione |
|---|---|---|
| [DP-405](docs/tickets/DP-405-person-record-ui.md) **IN PROGRESS** | Cronologia e correzioni in fixture/browser; AC-405.3 stato persona senza record pubblici approvati, AC-405.6 test manuale assistivo. | Canario public-safe vuoto e sessione screen reader su dispositivo reale. |
| [DP-406](docs/tickets/DP-406-topic-record-ui.md) **BLOCKED** | Pagina Topic pronta e visual test locale, manca AC-406.6. | Topic/membership reali già revisionati in proiezione MiniPC e controllo filtri/attribution. |
| [DP-407](docs/tickets/DP-407-contentaudit-timestamped-evidence-ui.md) **IN PROGRESS** | Scritti, media, correzioni, fallback testati; AC-407.4 wording unresolved/blocked e AC-407.7 judgment assistivo/manuale. | Caso pubblico autorizzato con locator e stato non risolto, test screen reader. |
| [DP-408](docs/tickets/DP-408-discrepancy-position-change-comparison-ui.md) **BLOCKED** | UI longitudinale e layout fixture; manca AC-408.5. | Relazione temporale/attribuzione originale revisionata nel MiniPC, niente deduzioni d'intento. |
| [DP-409](docs/tickets/DP-409-public-search-static-indexing.md) **IN PROGRESS** | Ricerca statica/API coherence e prove zoom/browser ampie; AC-409.8 manual screen reader e dipendenza DP-408. | Manual AT e dataset pubblico reale coerente tra indice/API/cache. |
| [DP-410](docs/tickets/DP-410-accessibility-performance-seo-acceptance.md) **IN PROGRESS** | Check automatizzati, cold perf e SEO; AC-410.1/.2 richiedono valutazione manuale AT, focus, touch e contrasto. | Accettazione umana della preview su telefono e screen reader, con owner/risultati e fix evidenziati. |
| [DP-412](docs/tickets/DP-412-design-tokens-component-contract.md) **IN PROGRESS** | Token/component contract largamente verificato; AC-412.5 richiede prova manuale assistiva/zoom tracciata. | Una sessione manuale ripetibile sui componenti selezionati, senza nuova migrazione framework preventiva. |
| [DP-422](docs/tickets/DP-422-public-product-architecture-v3-route-migration.md) **IN PROGRESS** | Route e clean clone ok, AC-422.1 riesaminata e AC-422.8 comparison manual v4, dipendenze DP-408/409/429 pendenti. | QA su route pubbliche correnti, desktop/mobile v4 con approvazione umana e confine demo/Studio. |
| [DP-429](docs/tickets/DP-429-explore-page-v4.md) **IN PROGRESS** | Browser URL restore, filtri, tastiera, reflow/200% in harness; serve giudizio screen reader/manuale. | Test manuale Browse/Explore con proiezione non-demo, chiusura dipendenze DP-409/425. |

### D. Studio privata, review, ricerca — 6 ticket

| Ticket e stato | Cosa manca | Sblocco o decisione |
|---|---|---|
| [DP-416](docs/tickets/DP-416-studio-research-collection-workspace.md) **IN PROGRESS** | Ricerca autenticata e pagination su vecchi Content/Claim; rights UNKNOWN e 2/30 attribution missing, nessuna capture/candidate, flusso AT non completo. | Collezione real-content autorizzata e scenari operatori con blocker leggibili. |
| [DP-417](docs/tickets/DP-417-studio-discovery-inbox.md) **IN PROGRESS** | Inspector read-only, ledger append-only e pg_temp canary; migrazione non distribuita, AC-417.1-.4 aperte, triage reale non certificato. | Governance ruoli, migrazione sicura autorizzata, Inbox non vuota e prova browser/operator. |
| [DP-418](docs/tickets/DP-418-studio-candidate-promotion-cluster-review.md) **IN PROGRESS** | Matching persistito read-only e latest-review fence introdotti; AC-418.1-.4 ancora aperte; race revoca vs promozione non esclusa dalla query. | Persisted reviewer attested con lock transazionale, differenzia SAME_PROPOSITION vs DUPLICATE_EXTRACTION, MiniPC E2E e UI. |
| [DP-419](docs/tickets/DP-419-studio-source-capture-passage-inspector.md) **IN PROGRESS** | Inspector/selectors/version compare, locator segmento time-range; AC-419.3 richiede seek/player e source approvata, AT reale. | Capture originale consentita, sincronizzazione seek quote e revoca/diritti ripetibili. |
| [DP-420](docs/tickets/DP-420-garlasco-studio-usability-search-acceptance.md) **FUTURE** | Nessuna acceptance ricerca-usabilità con operatore sul pilot completo. | Dopo DP-214/415..419: task/tempi/click/recall, con errori e accessibility misurati. |
| [DP-421](docs/tickets/DP-421-public-case-collection-contract-decision.md) **FUTURE** | Decisione se serve vista pubblica Case/Collection, separata dalle collection private. | Dopo DP-420: ADR GO/NO-GO su input approvati; NO-GO mantiene le route pubbliche attuali. |

### E. Funzioni deliberatamente condizionali — 2 ticket

| Ticket e stato | Condizione futura |
|---|---|
| [DP-507](docs/tickets/DP-507-admin-auth-surface.md) **FUTURE** | Solo se nasce superficie HTTP amministrativa: authN/authZ/CSRF, audit e prova security. Gli account lettore non sono privilegi editoriali. |
| [DP-508](docs/tickets/DP-508-public-intake-abuse-controls.md) **FUTURE** | Solo quando si autorizzano input pubblici: rate limit, anti-spam, moderazione, cost control e abuse review. |

### F. Dominio, governance, lancio — 5 ticket

| Ticket e stato | Cosa manca | Sblocco o decisione |
|---|---|---|
| [DP-701](docs/tickets/DP-701-brand-domain-handle-clearance.md) **IN PROGRESS** | Rename tecnico e owner identity; clearance marchio/collisioni, DNS/handle/contact effettivi e rollback evidence non tutti chiusi. | Ricevute owner verificabili, contatto pubblico autorizzato, controllo dominio. |
| [DP-702](docs/tickets/DP-702-prelaunch-legal-security-privacy-review.md) **FUTURE** | Chiusura owner+counsel dei gate privacy/legal/security/retention e decisioni firmate, non una checklist self-approved. | Decision register per preview limitata e per launch editoriale con ambiti diversi. |
| [DP-703](docs/tickets/DP-703-production-dataset-source-launch-set.md) **IN PROGRESS** | AC-703.3 fallimento sicuro chiusa, il resto launch-set/diritti/source snapshot/versioni/provider proof non approvato. | Un approved source launch set versionato, prove MiniPC di ingresso e disclosure. |
| [DP-704](docs/tickets/DP-704-end-to-end-launch-rehearsal.md) **FUTURE** | Nessuna rehearsal completa fonte→claim→correzione/rollback su MiniPC. | Dopo set approvato, prove backup/restore, migrazione e decisione GO-CANARY esplicita. |
| [DP-705](docs/tickets/DP-705-v1-release-public-deployment.md) **FUTURE** | Nessuna autorità v1, chiusura gate o smoke/rollback di release vera. | Solo dopo DP-701..704 e artifacts firmati: candidate e deployment versionati, smoke pubblico. |

**Controllo aritmetico:** 10 fonti + 3 policy + 9 public + 6 Studio + 2 future + 5 release = **35**. 30 non pertengono direttamente alla preview informativa, cinque toccano la preview (DP-304/307/410/701/702). Questo ordinamento operativo non rinomina né cancella ticket/AC.

## 3. Fasi e albero delle decisioni: eseguire in quest'ordine

**Bivio 0: cosa desideriamo rilasciare?**

- **Se solo le sei pagine oneste con ricerca pubblica eventualmente vuota:** attivare lo scope [LAUNCH.md](LAUNCH.md), ottenere i **cinque signoff di competenza** (DP-304/307/410/701/702) e fare build isolata su proiezione owner-approved non-demo, checksum/API/HTTPS/rollback. Il gate stable-v1 da 49 blocker continua NO-GO. Non assumere che una pagina HTTPS esistente sia la build richiesta.
- **Se un primo record editoriale autentico:** prima identificare una Source primaria e un Content con esatti diritti di raccolta, elaborazione, citazione/link, retention e public excerpt; specificare responsabile umano e audit. Se nessuna fonte soddisfa il contratto, fermare solo il flusso editoriale e formalizzare le decisioni mancanti: ulteriori test sintetici non creano i diritti.
- **Se l'obiettivo è stable-v1:** percorrere l'intero grafo con DP-307/702/703/704/705 e tutte le condizioni dell'attuale preflight; solo un nuovo calcolo a zero blocchi più ricevute owner permette considerazione del GO.

**Fase 1 — decisioni da poche ore di lavoro umano qualificato, senza scrivere infrastruttura.** Confermare promessa di prodotto (registro dichiarazioni oppure verifica editoriale), decidere primo source set con owner/counsel, finalità/retention/privacy e reviewer; cost-cap; criterio di scelta tra testo parlamentare e Garlasco. Preparare il test manuale AT della preview, assegnando responsabile e verbale.

**Fase 2 — primo vertical slice privato su MiniPC.** Un Source e un Content reali e autorizzati, Discovery Run/Hit verificati, Capture hash+version, Passage con quote span originale, Statement/Claim Candidate, reviewer persistente, atomic promotion e replay senza race, zero auto-publicazione. Richiedere readback DB e ricevuta regressione revoca; misurare minuti, euro, click, errori per item. Se il primo caso è testuale, non richiedere subito provider video/ASR.

**Fase 3 — primo record pubblico soltanto autorizzato.** Superare Q-306 applicabili e policy, verificare parola/attribution/rights/correction, firma reviewer/pubblicatore, dati minimizzati. Controllare che projection, search, API, JSON-LD, cache, sitemap, HTML corrispondano a medesimo snapshot e che hold/retraction rimuova tutti i riferimenti.

**Fase 4 — scala, provider e funzioni ricche.** Solo dopo costo reale del primo e dei successivi dieci record, decidere 100 item/5 famiglie, diarization e provider, real-topic/trace, Studio operator e UX completa. DP-507/508 restano disabilitati salvo trigger. Un nuovo obiettivo minore richiede ADR e aggiornamento esplicito dei ticket, non un'accettazione fittizia.

**Criterio stop/go osservabile dopo due sprint:** almeno **1 fonte primaria con permesso documentato, 1 Capture/Passage hashato, 1 Candidate revisionato e zero pubblicazioni non approvate**; poi 10 record con misura del lavoro umano/costi e falsi match. Se nessuna fonte o reviewer è autorizzabile, discutere cambiamento dell'ambito prima di implementare altre UI.

## 4. Donor/fork: verifica puntuale, cosa compra davvero tempo

**Fonti dei giudizi:** [audit source-level del 21 settembre](docs/12-source-level-donor-audit.md) per cinque cloni locali con SHA e decisione di non adottarli in blocco; [mega-handoff sezione 5](MEGA-HANDOFF-2026-10-10.md) per ulteriori candidati. README/licenze pubbliche ricontrollate il 10 ottobre 2026 per Senato, ParliamentRAG, Meedan Check, Hypothesis, faster-whisper/WhisperX, yente e ClaimBuster. È una **due diligence preliminare documentale**, non audit security/license di ogni versione o una benchmark integrativa.

| Donor e maturità della prova | Funzione che può accelerare | Scelta concreta e limite |
|---|---|---|
| [Senato OpenData](https://github.com/SenatoDellaRepubblica/OpenData), README ufficiale **CC BY 3.0** | RDF e identità/atti; senza ASR su fonti testuali. | **P1 fonte**, non presume che i dump metadata includano i testi: README dice che i testi degli atti vivono altrove. Dossier di attribution e versione necessario. |
| [Senato AkomaNtosoBulkData](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData), README **CC BY 4.0** | XML documenti/resaula/sommcomm con provenance e exact spans. | **P1 primo esperimento** su un resoconto limitato: distinguere testo parlamentare reale, locatore e condizioni d'uso, dai dati metadata del repo precedente. |
| [ParliamentRAG site](https://github.com/Emeierkeio/ParliamentRAG) + [codice effettivo iswc](https://github.com/Emeierkeio/parliamentrag-iswc) | **Scoperta concreta del 10/10:** il nome originale dal **6/10** punta al sito; il codice backend/build/MCP e citazioni verificabili vive nel secondo repo, **Apache-2.0**, con tag iswc2026-eval/demo. | **P1 audit selettivo** sulla pipeline ufficiale Camera XIX e exact-substring speaker/quote; non copiare ranking di autorevolezza di persone, ideological compass, generazione editoriale e Neo4j/LLM full stack. |
| [ParliamentRAG graph DOI](https://doi.org/10.5281/zenodo.21560331) / [dataset tabellare](https://huggingface.co/datasets/emeierkeio/parliamentrag-camera-leg19) | Grafo della Camera XIX, speaker/sessioni, metadata e citation spans già aggregati. | **Licenza dati CC BY-SA 4.0 separata da Apache-2.0 codice.** Valutare share-alike, attribuzione, provenienza fonti primarie e finalità prima di qualsiasi import. Non equiparare dataset terzo a nostra fonte/review approvata. |
| [Meedan Check](https://github.com/meedan/check), sviluppo OSS MIT | Triage, review, appeal e UI annotazione. | README dichiara esplicitamente **solo ambiente di sviluppo, non produzione**; copiare workflow/pattern selettivi, non stack Docker composito. |
| [Hypothesis client](https://github.com/hypothesis/client), BSD-2-Clause | Selezione precisa di passaggi e annotazioni. | **P2 prototype offline** con hash+offset e retention locale, valutare dipendenze; identità/server Hypothesis non sono consentiti automaticamente. |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper), MIT / [WhisperX](https://github.com/m-bain/whisperX), BSD-2-Clause | ASR locale con alignment e timestamps. | **P2 benchmark shadow** su 10 clip lecite, WER/tempi/costo/errori speaker; nessuna identità vocale né falsa chiusura di DP-204 Groq. Verificare licenze dei pesi. |
| [ClaimBuster API](https://claimbuster.org/api/) | Check-worthiness prima della ricerca. | **P3 solo shadow**, richiede API key e terms; il punteggio non è verità né giudizio finale. Misurare recall su 50 casi prima di eventuale uso. |
| [OpenSanctions yente](https://github.com/opensanctions/yente), MIT | Reconciliation e pattern entity matching. | **P3 reference**, search runtime Elastic/OpenSearch e dati OpenSanctions licenziati a parte; non importare profili AML/sanzioni in una banca dati politica. |
| [Loki/OpenFactVerification](https://github.com/Libr-AI/OpenFactVerification), clone 21/9 MIT | Boundary decomposition/checkworthy/query/retrieval. | **Reference**, evitare score di verità/persona e lanciare servizi aggiuntivi. |
| [Claim Polygraph NG](https://github.com/moshiur00/claim-polygraph-multi-agent-evidence-investigator), clone 21/9 MIT | Policy deterministica, citation assurance, evidence families, cost ledger, idempotenza. | **Miglior donor di pattern già auditato**, mappare prima implementazioni DP-224/229/201 esistenti; selezionare solo gap misurato, rispettare notice e transitive deps. |
| [Meedan Pender](https://github.com/meedan/pender) / [Alegre](https://github.com/meedan/alegre), cloni 21/9 MIT | URL normalization/metadata/archiver; similarity. | **Reference**: Rails/Redis e ricerca Elasticsearch/queues ampliano il runtime del MiniPC senza evidenza attuale di necessità. |
| [CIMPLE knowledge-base](https://github.com/CIMPLE-project/knowledge-base), clone 21/9 | RDF, ClaimReview, URI design. | **Interop**, non adottare Virtuoso come source of truth; controllare licenze di ciascun repository della costellazione. |

**Decisione di fork:** preferire **un adapter che produca il nostro contratto Source→Content→Capture→Passage**. Per ogni alternativa pretendere: versione e commit pin, licenza del **codice** e del **dataset** separati, data/coverage gap, test su 10 record con quote/offset corretti e rights notati, ore di integrazione/upgrade, costo MiniPC e piano rimozione. Fermare adozioni che aggiungono scorciatoie di pubblicazione o ranking vietati da PRODUCT.md. Il vantaggio di una repo esterna è un'ipotesi finché non misura ore/costo e reale riuso.

## 5. Grilling: 12 domande decisive, con output richiesto

1. **Promessa:** il primo sito deve far consultare parole citate e corrette, o produrre fact-check completi? Scrivere una promessa verificabile e le tre funzionalità indispensabili.
2. **Ambito:** chi autorizza la distinzione fra sei pagine informative e archivio v1? Firma owner, testi pubblici, timeline e rischio residuale.
3. **Prima fonte:** Garlasco 100/5, resoconto ufficiale Camera/Senato o un corpus già autorizzato? Mostrare il primo Content con URL, data, versione, speaker e rights.
4. **Licenza reale:** per quella singola fonte quali permessi di accesso, retention, elaborazione, citazione breve, link e ripubblicazione sono documentati? Quale azione è vietata?
5. **Costo umano:** chi assume responsabilità editoriale, indipendenza challenger e correzioni? Minuti effettivi per record, gestione contestazioni ed escalation.
6. **Collo di bottiglia tecnico:** provare in una sessione il vertical slice vero MiniPC. Dove si interrompe e perché: diritto, fonte, DB, reviewer, provider o projection?
7. **Race e attribuzione:** come garantire che una revoca concorrente blocchi una promotion? Quale test transazionale/rollback lo prova? Quale speaker proof esclude attribuzioni false?
8. **Provider:** quanto possiamo spendere al mese/100 record? Quali attività sono possibili da fonte testuale prima di OmniRoute/Groq e quale canary ufficiale rimane obbligatorio?
9. **Policy:** quali Q-306 effettivamente incidono sulla preview informativa e quali solo sulla release di claim? Chi firma e dove vengono versionate le risposte?
10. **Riuso:** il codice ParliamentRAG effettivo, l'adapter Senato o un pattern Claim Polygraph sostituiscono concretamente un pezzo già scritto? Tabella differenza/ore/diritti, niente nuovo framework per estetica.
11. **Esperienza:** tre cittadini riescono a trovare fonte originale, rettificare e capire ciò che è verificato in un minuto? Qual è la prova mobile/AT e il criterio di rinvio?
12. **Kill gate:** dopo due sprint con zero Content autorizzati oppure review troppo costosa, quali requisiti ridimensioniamo con ADR e quali sono invarianti non negoziabili? Chi decide go/pivot/stop?

## 6. Prompt unico pronto da incollare nella nuova chat

~~~text
Agisci come principal engineer, product editor e reviewer critico di Dichiarazioni Pubbliche. NON modificare codice/ticket o pubblicare prima del grilling. Leggi nell'ordine AGENTS.md, PRODUCT.md, CONTEXT.md, ARCHITECTURE.md, PLAN.md, LAUNCH.md, FINAL-PENDING-GRILLING-2026-10-10.md, MEGA-HANDOFF-2026-10-10.md, docs/12-source-level-donor-audit.md, poi i 35 docs/tickets/DP-*.md ancora non DONE. Repo autorevole /Users/domenico/Code/DichiarazioniPubbliche.it; runtime autorevole MiniPC mirror /home/udodo/src/DichiarazioniPubbliche.it (non Git).

Verifica con comandi in read-only il Git attuale, 125 ticket (90 DONE, 35 non DONE nella fotografia 10/10), preflight 49 blocker e differenza tra CI locale, HTTPS già online, preview informativa e stable-v1 NO-GO. Non presumere approvazioni Q-306, diritti su Garlasco o fonti Camera/Senato, modello/provider valido, migrations o deploy. L'HANDOFF.md operativo è stato aggiornato e le vecchie note del 3 ottobre rimosse dalla porta d'ingresso, NON cancellate dalla storia Git.

Fammi un GRILLING serrato con 12 domande in ordine, una alla volta, su promessa, primo source set, diritti, responsabilità editoriale, privacy, costo umano, provider, qualità MiniPC, fork/donor, valore per utente, confini preview-v1 e kill gates. Contestami se la scelta è troppo ampia o costosa. Per ogni risposta aggiorna una matrice decisione/owner/evidenza/scadenza, separa fatti, ipotesi e signoff necessari. Ripassa TUTTI i 35 ticket: chiudere solo AC con prove; per ogni ticket decidere DO-NOW, DEFER, MERGE/RE-SCOPE VIA ADR oppure CANCEL SOLO CON DECISIONE ESPLICITA, senza alterare la fotografia storica. Valuta concretamente repo ufficiali Senato e il VERO codice ParliamentRAG in Emeierkeio/parliamentrag-iswc (licenza Apache-2.0) e dati Camera CC BY-SA 4.0 separati; studia audit Claim Polygraph, Meedan, Hypothesis. Confronta costo/compatibilità e guardrail contro il codebase esistente.

Restituisci alla fine: proposta di MVP verificabile; matrice 35 ticket con verdict argomentato; DAG/3 sprint ordinati per valore; 5 decisioni umane realmente bloccanti; una prima fonte e un vertical slice MiniPC auditabile; piano manual AT; donor adopt/reject con prove, costi e rischi; una check-list release per preview informativa distinta da stable-v1. Nessun falso DONE, nessuna pubblicazione reale senza approvals, nessun ranking personale, niente biometria.
~~~

## 7. Readback e prove da conservare dopo il grilling

~~~bash
cd /Users/domenico/Code/DichiarazioniPubbliche.it
git status -sb
git log -1 --oneline
git branch -avv
git worktree list --porcelain
git stash list
python3 tools/report_ticket_status.py --json
python3 tools/check_launch_preflight.py --expect-no-go
python3 tools/check_repository_contract.py
python3 tools/generate_fixture_inventory.py --check
python3 tools/check_licensing_inventory.py --check-hashes
~~~

Full Python, 5-case benchmark, Playwright/browser, MiniPC production-readback e preview checker si ripetono **solo** quando il codice, il corpus autorizzato o il candidato release cambiano. Le ricevute storiche sono nel MEGA-HANDOFF e in docs/reviews/, l'autorità finale dei ticket resta in PLAN/ticket. I repository esterni richiedono pin e controlli security/license ulteriori prima di essere usati. **Nessun push o deploy è incluso nel lavoro di stesura di questo documento.**
