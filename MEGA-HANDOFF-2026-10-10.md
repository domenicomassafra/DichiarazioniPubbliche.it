# Dichiarazioni Pubbliche — checkpoint intermedio e mega-handoff

**Data:** 10 ottobre 2026 (Europe/Rome). **Consegna:** repository `main` integrato, non release stabile. **Destinatari:** prossimo agente tecnico, responsabile prodotto, reviewer privacy/editoriale e futuro confronto critico (*grilling*).

> Il documento congela **ciò che è dimostrato** e separa esperimenti, decisioni umane e condizioni di produzione. Non autorizza acquisizione di nuove fonti, utilizzo dei diritti di terzi, spese provider, migrazioni sul MiniPC, pubblicazione di claim o rilascio stable-v1. Per lo stato Git effettivo usare sempre `git status -sb && git log -1 --oneline`, non copiare un commit storico come HEAD perpetuo.

**Indice operativo aggiornato:** [FINAL-PENDING-GRILLING-2026-10-10.md](FINAL-PENDING-GRILLING-2026-10-10.md) contiene il censimento **di ciascuno dei 35 ticket residui**, albero di priorità/decisioni, audit donor approfondito, 12 domande e **un briefing unico copiabile nella nuova chat**. [HANDOFF.md](HANDOFF.md) è la porta d'ingresso attuale: le note obsolete del 3 ottobre sono state tolte da quell'indice operativo, preservate nella storia Git. I riferimenti a commit/runtime in questo documento sono ricevute datate: dopo ulteriori commit, deploy o decisioni umane ricontrollare le fonti canoniche.

## 1. Risposta immediata: che prodotto abbiamo?

**Dichiarazioni Pubbliche**, `dichiarazionipubbliche.it`, è un registro aperto e verificabile delle dichiarazioni di persone di rilevanza pubblica. Deve mostrare chi ha detto **cosa**, **quando**, **dove**, il testo/versione e la fonte primaria, l'evidenza verificata e la storia di modifiche, posizioni, contestazioni, risposte e correzioni. Include politica, giornalisti, opinionisti, creator e altri soggetti pubblici nei limiti della rilevanza pubblica. Non è un social di accuse, uno score di affidabilità delle persone o un verdetto automatico su chi mente. `PRODUCT.md` e `CONTEXT.md` prevalgono su ogni sintesi.

**I prodotti sono due superfici dello stesso sistema:**

- **Pubblico:** Home, Esplora, Dichiarazione, Persona, Tema, Contenuto, Traccia nel tempo, Metodo, Correzioni, Dati/API e Progetto, più utility Account separate. Mobile-first, ricerca su proiezione pubblica approvata, API read-only, JSON/JSON-LD, fonti verificabili; nessun LLM nella richiesta del lettore.
- **Studio privata:** Discovery, corpus/capture/passaggi, risoluzione entità, clustering, ricerca, annotazione/candidate review, fonti/evidenze, verifica, controllo umano, correzioni, promozione esplicita. Il candidato non è un claim pubblico; Studio non deve apparire come un asset di produzione accessibile anonimamente.

**Catena reale da completare e preservare:**

`Fonte/diritti → Discovery Run/Hit verificati → Content → Capture immutabile → Passage oppure Transcript versionato → Statement Candidate → Claim Candidate → review/cluster → promozione umana → Atomic Claim → evidenze e osservazioni approvate → verifica deterministica → Finding → controlli privacy/diritti/risposte/high-risk/review → proiezione pubblica → Astro/API → cronologia e rianalisi`.

La parte **tecnica** di quasi tutti questi componenti esiste. Manca la prova autorizzata, con **una fonte reale e una decisione umana completa**, che percorra l'intera catena senza SQL manuale, inferenze di identità o scorciatoie sulle licenze.

## 2. Stato verificato di questa tranche

| Voce | Stato osservato al checkpoint | Interpretazione |
|---|---|---|
| Sorgente Git | `/Users/domenico/Code/DichiarazioniPubbliche.it`, `main`, codice integrato fino a `4a9f782` prima di questo documento | Il commit finale di handoff/push sarà successivo; verificare con Git |
| Remoto | `https://github.com/domenicomassafra/DichiarazioniPubbliche.it.git` | Nessun branch applicativo aggiuntivo nel checkout; un solo worktree registrato al controllo del 10/10 |
| Runtime autorevole | MiniPC `/home/udodo/src/DichiarazioniPubbliche.it`, mirror **non Git**; DB PostgreSQL `dichiarazioni_pubbliche` | Non confondere push remoto con deploy: il runtime **non è stato aggiornato** in questa tranche |
| Ticket originali | **125** totali, **90 DONE**, **20 IN PROGRESS**, **6 BLOCKED**, **9 FUTURE**, **0 READY**; **35 non DONE** | Nessun AC originariamente aperto è stato inventato come chiuso per migliorare il numero |
| Preflight release v1 | **NO-GO, 49 blocker** (16 Q-306, 4 artifact di release mancanti e 29 status gate al controllo datato) | È un gate di rilascio, non il risultato del build web |
| Suite Python integrata finale | **2390/2390 test OK in 244,841 s**, `PYTHONPATH=poc python3 -m unittest discover -s tests -v` | Include esercizi locali SQL/PostgreSQL e molti mock/fixture: **non** è un canary production/provider |
| Verifica deterministica | **5/5 benchmark PASS** | Casi sintetici, non accuracy del corpus reale |
| Igiene | `compileall`, contract repo, inventario fixture/licenze (47 righe), contributor acceptance e `git diff --check` PASS | Non equivalgono a revisione giuridica o deploy |
| Web CI/preflight | Test di build isolati vuoti e demo; reject demo rinominata; sei route pubbliche, due utility noindex, zero chunk Studio, fingerprint coerenti | Meccanicamente PASS ma `launch_authorized=false` nel controllo preview |
| HTTPS pubblico | In precedente read-only check, le sei route/robots/sitemap rispondevano HTTP 200 | Il **copy live è precedente** a quello locale; niente deploy eseguito qui |
| Materiale approvato | Preview locale verificata con proiezione **test-only vuota** | Non è prova di zero claim sulla produzione, né autorizzazione a pubblicare contenuti reali |
| Worktree/branch | `git worktree list --porcelain`: solo checkout principale; `git branch -avv`: solo `main`, `origin/main` | Non creare worktree a fini cosmetici; ricontrollare dopo handoff |

**Artefatti preservati:** `LAUNCH.md` (decisione di preview informativa separata) e questo handoff vanno versionati; i 15 commit di sviluppo accumulati dopo l'`origin/main` iniziale `3041aaa` devono essere integrati con push **non-force**. Nessuna scrittura al DB live, migrazione o rollout per completare il checkpoint. `web/dist` locale preesistente è **stale**: usarlo come sorgente di release sarebbe un errore; ricostruire in directory isolata.

### Commit di questa tranche da non perdere

| Commit | Riparazione/prova |
|---|---|
| `0805eea`, `03d4bc1` | Percorso opzionale privato Antigravity con limite quote e osservazione aggiornata; mai equivalenza con OmniRoute live |
| `8eefbae` | Cache dell'API invalida anche con sostituzione atomica mtime/dimensione invariati; 304 solo con ETag valido |
| `e546040` | Reconciliation privata conta solo Discovery lineage attuale e verificata |
| `9abe37c` | Inventory challenger vincolato al bersaglio esatto; AC-229.8 ancora aperto |
| `66cd5ee` | `CLEARED` per uso privato non basta per link pubblico: diritto `LINK_PUBLIC`, review valida e attuale |
| `fcd5236` | Scanner fail-closed delle sei pagine preview; la sola riuscita del bundle non è autorizzazione legale |
| `96ac1bc` | Blocca demo/proiezioni camuffate e asset Studio dalle build pubbliche |
| `7499949` | CI verifica in build isolata il confine public/demo |
| `ef46ed4` | Unicode invisibile non elude il controllo sulle accuse di intenzionalità e punteggi persone |
| `31161c9` | Manifest licensing riallineato al fixture SQL modificato, senza inventare diritti |
| `eb99a00` | Browser QA isolato empty + populated demo, tastiera/zoom/filter/accessibility come prove tecniche |
| `06091cc` | Parent Statement rifiutato e rights review futura non possono apparire come chain pronta |
| `71a99c7` | Catalogo/quota/provider receipt legato allo snapshot e modello servito; fallimenti non preservano quota |
| `4a9f782` | Promozione vincolata all'ultima review persistita, distingue `SAME_PROPOSITION` da `DUPLICATE_EXTRACTION` e valida replay |

### Prove finali da ripetere solo quando si modifica davvero il codice

```bash
cd /Users/domenico/Code/DichiarazioniPubbliche.it
git fetch origin main
git status -sb && git worktree list --porcelain && git branch -avv
python3 tools/report_ticket_status.py --json
python3 tools/check_launch_preflight.py --expect-no-go
python3 tools/check_repository_contract.py
python3 tools/generate_fixture_inventory.py --check
python3 tools/check_licensing_inventory.py --check-hashes
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
cd web && npm run check && npm run check:projection-boundary && npm run check:browser:isolated
```

Attenzione: l'ultimo browser check richiede un browser reale con profilo/test isolato; gli strumenti di release/preview devono verificare **una proiezione non-demo ammessa dall'owner**, non riusare i fixture. Un `--bundle-only` dimostra la forma del pacchetto, non l'autorità di lancio. Evitare suite complete concorrenti sullo stesso checkout: hanno prodotto precedentemente falsi segnali transitori mentre altri worker stavano editando test. La suite finale qui è stata eseguita su tree sorgente stabile.

## 3. Tutti i 35 ticket residui: cluster, dipendenze e realtà

**A. Fonti e provider, 10** — `DP-201/202/203/204/208/214/215/229/233/234`.

- **DP-214/215:** prima un Content/Source realmente approvato e attualmente raggiungibile, con diritti separati di accesso, archiviazione, analisi da LLM, link/citazione/riuso e provenienza originale-vs-derivata; poi un `Discovery Run → Capture → Passage → Candidate` su PostgreSQL MiniPC con ricevuta. Ultimo snapshot Garlasco letto dal documento `docs/reviews/2026-10-10-goal-infinito-wave21-critical-dependencies.md`: 18 Content storici, 18 rights UNKNOWN, 0 capture autorizzati, 0 current rights/source profiles, 0 Discovery manifestrun/hit, 0 Capture/Passage/Statement/Claim Candidate; 30 Atomic Claim preesistenti, 82/100 elementi logici ancora necessari, sei lead non revisionati. È un **readback documentato**: riconvalidare, non presumerlo ancora live. Il recente `06091cc` non crea record reali.
- **Verifica puntuale DP-214/215 a fine tranche:** il worker della fonte ha chiuso tecnicamente la prova **AC-214.3** sul diagnostico privato, non il ticket; `AC-214.1/.2/.4-.8` e `AC-215.9` restano aperti. L'attuale SQL revisionato **non** è stato read-back sul database di produzione MiniPC.
- **DP-201 → 202 → 203:** il canary `OmniRoute` **ufficiale** sul modello tiered deve produrre output strutturato, receipt modello/quote/costo e superare il parent benchmark prima di fanout. La health/catalog non bastano. Le opzioni Antigravity/Gemini o locali sono private candidate alternative, **non** una sostituzione fraudolenta del canary ufficiale. Niente chiamate a pagamento senza consent/quotas.
- **DP-204 → 208:** live Groq ASR richiede credenziale autorizzata e prova audio, costo, fallback e privacy; il benchmark diarizzazione con veri speaker/time reference resta distinto dalla pura corretta segmentazione. Vietato attribuire persone dalla voce o dal volto.
- **DP-229:** 8/9 AC verificati, l'ultimo AC-229.8 richiede challenger materialmente indipendente e attestato o eccezione qualificata: non può essere sintetizzato dalla UI.
- **DP-233/234:** adapter Camera/Senato e structured-evidence già testati; il Senato `OpenData` RDF/metadata e i resoconti Akoma Ntoso sono famiglie/licenze **diverse**. Le sonde Senato hanno verificato a livello tecnico un metadata dataset, ma non autorizzano Fonte speech, DVNS reale, trascrizioni né pubblicazione. Fonte, schema, licenza e permesso specifico ancora da deliberare.

**B. Giuridico, privacy ed editoriale, 3** — `DP-301/304/307`.

- **DP-301:** le regole macchina anti-"bugiardo"/intento e anti-person-score sono presenti; **AC-301.8** vuole una decisione qualificata DP-306/307 non ancora ottenuta. Nessun modello può dedurre dolo da falsità/contraddizione.
- **DP-304:** minimizzazione, inventario campo, privacy/account, logging, retention, persone sensibili e ciclo diritti hanno implementazione ma **non** decisioni su base giuridica, termini, ruoli e testi pubblici; la presenza di fonti pubbliche non cancella GDPR/diritti.
- **DP-307:** revisione per Italia/UE e termini editoriali/legal notice è una decisione owner+counsel, non un ticket risolvibile inventando un parere. Il registro Q-306 contiene **16 questioni** ancora OPEN/BLOCKED (vedere `docs/policy/` e `tools/check_launch_preflight.py`). Il codice fail-closed rimane.

**C. Public product, contenuti e accessibilità, 9** — `DP-405/406/407/408/409/410/412/422/429`.

- Routing e layout pubblico esistono; browser matrix vuota/demo e sicurezza proiezione sono provati. **Non** chiudere un'AC che chiede veri dossier/person/Topic/Content/Trace approvati mostrando pagine fixture.
- Ricerca reale, data API e cross-linking devono coincidere con la **stessa** versione/fingerprint della public projection; storico correzioni e ritiro devono propagarsi senza asset rimasti su CDN/cache.
- DP-429 richiede ancora judgment manuale screen reader/dispositivo, oltre ai check automatici 200%, tastiera, reduced-motion e componenti caricati.
- **DP-410** è anche un vincolo sulla preview informativa; la homepage con contenuti vecchi in produzione deve essere distinta dalla build locale aggiornata.

**D. Studio privata e handoff umano, 6** — `DP-416/417/418/419/420/421`.

- L'interfaccia privata e gli adapter/handoff esistono, ma flussi reali con ruoli, provenienza, ragioni dei blocchi, revisione e replay non sono integralmente certificati.
- **DP-418**: dopo `4a9f782`, promozione non usa un'APPROVED storica revocata, non confonde equivalenza con duplicato e vincola i receipt di replay. Tuttavia **AC-418.1-.4 rimangono tutti aperti**: review umana persistente/autenticata, caso sorgente comparata/diritti, concurrency-proof, UI operativa e MiniPC E2E. Non propagare il falso DONE del puro DP-117.
- Rischio transazionale noto: i writer di `review_event` non hanno ancora un lock/attestazione della stessa transazione della promozione. La query di ultima review riduce il rischio ma **non prova** assenza di race contro una revoca concorrente.

**E. Funzioni condizionali, 2** — `DP-507/508`: lasciarle FUTURE/disabilitate finché owner, sicurezza e scope non ne giustifichino l'inclusione.

**F. Stabilità, titolarità, rilascio, 5** — `DP-701/702/703/704/705`.

- **DP-701:** dominio effettivo, titolare, privacy/contact e governance approvati; risolvere con ricevute reali.
- **DP-702:** revisione legal/security/privacy, signed decision register con scadenze/trigger; niente legale simulato.
- **DP-703:** decidere un source launch set con diritti e versioni coerenti; i manifest fixture NON sono selezione/attestazione del launch set.
- **DP-704:** rehearsal **MiniPC** sul set approvato, failover/backup/restore e rollback realmente eseguiti; fixture e `NOT_EXECUTED` non bastano.
- **DP-705:** finali owner authority, artifact/snapshot, smoke e release. No stable-v1 prima della chiusura a evidenza del grafo.

Il totale dei gruppi è **10 + 3 + 9 + 6 + 2 + 5 = 35**. La preview separata in `LAUNCH.md` differisce 30 ticket esterni allo scope e 5 condizioni residue applicabili alla preview (DP-304/307/410/701/702); ciò **non** modifica il piano dei 125.

## 4. Perché siamo rallentati: diagnosi, non giustificazioni

1. **Il collo di bottiglia è l'autorità sui dati reali, non il numero di test.** Le centinaia di tipi/constraint, refactor, guard e fixture non creano da soli una fonte autorizzata con retention, privacy, review e citazione; il MiniPC Garlasco documentato è praticamente vuoto sul nuovo corpus.
2. **Abbiamo sovra-parallelizzato un progetto editoriale prima di provare il vertical slice.** Code-first + molti ticket/worker produce integrazione continua ma poca evidenza del primo record completo. Non cancellare però invarianti necessari per evitare false attribuzioni.
3. **Sono stati mischiati due gate:** le sei pagine informative con indice vuoto e una release v1 con veri dossier. La seconda ha 49 blocker; non deve automaticamente sospendere ogni pagina onesta, ma i 5 signoff effettivi per la preview restano.
4. **Test sintetici ≠ utilità.** Un test di compatibilità/schema/PostgreSQL dimostra che un contratto è eseguibile, non che fonti primarie, diritti, speaker e tempi siano corretti su un caso reale.
5. **Vincoli provider e dati esterni non sono correggibili localmente.** Se OmniRoute tiered/Groq non hanno canary valido, aggiungere wrapper non produce accuracy o una ricevuta ufficiale.
6. **Troppa ricerca chiusa sul pilot Garlasco.** Il requisito di 100 elementi/5 famiglie può essere utile come benchmark, ma non è automaticamente il modo più economico di lanciare un archivio generalista. Una modifica allo scope richiede decisione owner+ADR/ticket, non bypass degli AC esistenti.
7. **Costo della governance alto prima della scelta editoriale:** rischi normativi e diritti sono genuini, ma vanno convertiti in *poche decisioni leggibili* sulla prima fonte, non in un ulteriore strato infinito di documentazione.

**Ipotesi falsificabile di recupero:** sospendere feature UI marginali e nuovi framework finché non sia completato **un** record fonte originale, diritti, capture, candidato, revisione e pubblicazione *solo dove autorizzata* con receipts e una persona responsabile. Se quel vertical slice richiede ancora più gate/test rispetto al valore, rivalutare ambito/prodotto e stack.

## 5. Donor/fork / riuso: audit da fare prima di riscrivere

Questi sono **candidati a due diligence**, non dipendenze già integrate, librerie pronte all'uso o autorizzazioni a copiare dataset. La compatibilità va verificata per singolo commit, versione, transitive dependency, pesi e dati; preferire **adapter/integration** a un fork che sostituisca l'architettura auditabile.

| Candidato da valutare (riferimento pubblico) | Potenziale risparmio | Perché non fare un fork diretto alla cieca | Prossimo esperimento |
|---|---|---|---|
| [Senato OpenData](https://github.com/SenatoDellaRepubblica/OpenData) e [AkomaNtosoBulkData](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData) | Metadati ufficiali e testi strutturati con speaker/sessioni, meno ASR e scraping | dataset distinti, notice CC BY 3.0 vs 4.0, attribution/scope/ripubblicazione da decidere; già esistono adapter locali | Un solo verbale approvato con locator, versione, hash, quote span e attribution |
| [ParliamentRAG — sito](https://github.com/Emeierkeio/ParliamentRAG), [vero codice ISWC](https://github.com/Emeierkeio/parliamentrag-iswc), [grafo RDF](https://doi.org/10.5281/zenodo.21560331) | **Correzione verificata 10/10:** dopo lo spostamento del **6 ottobre** il nome originale serve il sito; il codice di build/backend/estrazione Camera XIX e controllo citation exact-substring è nel secondo repository (Apache-2.0). Il grafo/dataset è dichiarato **CC BY-SA 4.0**, distinto dal codice | Ranking di autorevolezza per persona, bussola ideologica, generazione automatica e full stack Neo4j/LLM sono incompatibili o sproporzionati rispetto agli invarianti del nostro core; licenza e provenienza del grafo non costituiscono approvazione dell'utilizzo editoriale | Pin dei tag iswc2026-eval/demo e license, mini confronto su 10 citazioni/speaker/span contro adapter DP-233, stimare costo di riuso senza copiare score o dataset prima della valutazione owner/legal |
| [Meedan Check](https://github.com/meedan/check) | Idee per revisione collaborativa, newsroom triage, provenienza e annotazioni | repository è esplicitamente un **ambiente di sviluppo non produzione**, Docker multi-servizio, dipendenze/complessità; MIT per repo non autorizza contenuti Meedan o API | Confrontare 3 workflow review/appeal/annotation e importare solo pattern accettati con test |
| [Hypothesis client](https://github.com/hypothesis/client) | UI di annotazione su testo e passaggi per Studio | client BSD-2-Clause; backend/servizio/identità e diritti delle pagine non sono automaticamente risolti | Prototipo offline di selezione esatta offset+hash su Passage senza server esterno |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) / [WhisperX](https://github.com/m-bain/whisperX) | Trascrizione locale, VAD, timestamps/alignment, riduzione costo chiamate ASR remote | consumo GPU/Mac, accuratezza IT/dialetti, termini dei modelli e diarizzazione (speaker *label* ≠ identità); non sostituiscono il canary DP-204 del provider richiesto | 10 clip consentiti con WER, timestamp, falsi speaker ed energia/costo, candidate-only |
| [ClaimBuster](https://claimbuster.org/) | Segnalazione claim check-worthy, priorità coda di analisi | un classificatore non è fonte, evidenza né verdetto; API/terms/controllo qualità da verificare | Shadow-only su 50 frasi con recall e costo, confrontato col ranking locale |
| [OpenSanctions yente](https://github.com/opensanctions/yente) | Pattern di riconciliazione entità ambigue e API di matching | dominio AML/sanzioni diverso, infrastruttura aggiuntiva e dati OpenSanctions con licenze separate; può essere overkill | Solo audit degli algoritmi di match; nessuna importazione automatica di profili persone |

**Priorità donor:** 1) dati/contratti istituzionali già nel perimetro, 2) annotazione esatta di Passage, 3) ASR locale con prova di costo/qualità, 4) pattern editoriali. **No clone totale** di piattaforma esterna senza confronto delle responsabilità, licenze e manutenzione. Risparmio atteso è una **ipotesi**, non una cifra dimostrata.

**Audit già esistente da rileggere:** `docs/12-source-level-donor-audit.md`; per la UI sono già presenti `docs/ux/design-source-registry-v1.md`, `docs/38-public-visual-redesign-v4-selection.md`, `prototypes/final-hybrid/` e componenti propri `web/src/components/design/`. Una nuova migrazione a shadcn/Radix/TanStack/Vidstack va motivata da un difetto reale non già risolto dal design system Astro/React corrente. Non duplicare una ricerca donor già registrata senza una nuova versione o un criterio di adozione misurabile.

## 6. Grilling: domande che il prossimo agente deve porre *prima* del prossimo sprint

1. Il prodotto minimo di valore è un **registro delle parole con fonti** o un **fact-checking editoriale che valuta le affermazioni**? I due hanno costi e responsabilità differenti. Qual è la promessa su homepage che possiamo dimostrare con un solo record?
2. Voglio prima un esempio **Camera/Senato ufficiale** oppure pilot Garlasco con 100 item? Quale fonte ha davvero il pacchetto meno ambiguo di acquisizione, licenza, privacy e attribuzione? Chi firma il permesso e il diritto di uso pubblico?
3. Quale parte del percorso deve essere automatica: Discovery/capture/classificazione sì, approvazione e pubblicazione **no**? Quanto lavoro umano per record è sostenibile (minuti, budget)?
4. Possiamo lanciare senza valutazioni di vero/falso iniziali, esponendo solo citazioni e cronologia **esatta e revisionata**? Serve un ADR che cambia prodotto/ticket e un parere sul testo pubblico, non una scorciatoia ai gate.
5. Se OmniRoute/Groq restano indisponibili: aspettarli, approvare formalmente un adapter differente con ricevute isolate, oppure puntare su fonti testuali per non dipendere da ASR? Qual è il costo cap per 100 record?
6. Sono necessari fin da ora tre/gate dual control su ogni tipo di candidato? Quali rischi **concreti** mitigano e quali possono stare in un unico workflow umano senza perdere auditabilità?
7. Quanto dell'attuale Postgres+Astro+pure-Python è davvero da mantenere, e dove un'integrazione OSS riduce codice senza introdurre AGPL/servizi pesanti/lock-in? Richiedere matrice costo/fork/license.
8. Cosa significa concretamente "pubblicabile" per una **pagina vuota**: owner, dominio, contatto, privacy notice, accessibilità manuale, responsabilità e rollback approvati? Chi li firma e dove sono i receipt?
9. Come capire entro due sprint se dobbiamo fermarci? Proposta di kill/growth gate: almeno **1 Content reale autorizzato + 1 Passage verificato + 1 candidato revisionato + 0 pubblicazioni non approvate**; poi 10 fonti e misura tempi/costi.
10. Qual è il vero costo che vogliamo ottimizzare: GPU/LLM, licenze, tempo di QA, rischio legale, o settimane senza un prodotto leggibile dagli utenti? Stabilire una metrica singola per sprint.

## 7. Consegna e ordine operativo per il prossimo agente

**Non ripartire da zero.** Iniziare con `HANDOFF.md`, questo file, `PRODUCT.md`, `PLAN.md`, `AGENTS.md`, quindi gli ultimi ticket originali. Non rigenerare inventari di centinaia di componenti se nessuna evidenza è cambiata. Ricontrollare la fonte Git e le ricevute MiniPC per evitare conclusioni basate su un Mac più aggiornato del runtime.

**Sprint A — decisioni che sbloccano valore, non altro codice:** owner approva portata minima delle sei pagine e i 5 signoff della preview, avvia qualifica Italia/UE Q-306 con counsel, nomina responsabile revisione/raccolta, seleziona **una** famiglia di fonti con licenza/uso/purpose/relevance/versioni espliciti. Senza queste decisioni, continuare ad accumulare nuove guard/test non risolve il collo di bottiglia.

**Sprint B — vertical slice autorizzato privato:** su MiniPC e con permessi fonte, eseguire un solo Discovery→Capture→Passage→StatementCandidate→ClaimCandidate→review→AtomicClaim; prova idempotenza, errore, storia, exact quote e source hash; assicurare che nessun Finding pubblico cresca automaticamente. Per i contenuti media: tempo e speaker *reviewed*, no biometria. Riportare costo/tempo per elemento.

**Sprint C — prodotto pubblico realmente misurabile:** solo dopo privacy/diritti/owner review, proiezione approvata versionata, una dichiarazione/fonte reale, ricerca coerente, correzione/hold, stesso checksum attraverso API, Astro, sitemap/search e cache; miniPC read-back, backup+rollback verificati. Il successivo benchmark 10→100 può essere pianificato su evidenze, non desideri.

**Stop conditions per un nuovo agente:** se permesso fonte o legalità mancano, fermarsi esplicitando *quale autorizzazione/chi*; se un modello non restituisce receipt reale, non etichettare canary PASS; se un test è solo fixture non chiudere AC live; se c'è una race di revoca/publish, impedire promozione fino a sicurezza transazionale. Non cambiare modello/ticket per un conteggio cosmetico.

**Non introdurre nuove attività mentre si fa questo handoff.** Conservare gli status nei ticket finché i criteri originari non sono dimostrati. Questo è lo snapshot da far giudicare, non una richiesta di nuovo sviluppo asincrono.

### Addendum documentale del 10 ottobre — consegna al prossimo agente

Alla lettura prima della consegna risultavano **125/90/20/6/9 e 35 non-DONE**, **NO-GO/49** e repository contract PASS. Il checkout aveva poi ricevuto il commit documentale del coordinatore `de97080` relativo alla riconciliazione del PLAN e alle condizioni di attivazione dei nove FUTURE, mantenendo gli stessi conteggi; controllare sempre `git log -1` prima di citare uno SHA come corrente. La prova finale di rilascio riferita al coordinatore mantiene il nuovo build MiniPC **NO-GO**, pur con vecchio HTTPS sano: nessun aggiornamento del sito/corpus/release deriva dalla chiusura del presente handoff.

La tabella iniziale del checkpoint e i commit elencati restano evidenze storiche di tranche, senza implicare che siano l'ultimo HEAD dopo la documentazione finale. Per tutti i 35 record puntuali e gli unici 5 signoff ancora applicabili alla preview essenziale consultare **FINAL-PENDING-GRILLING-2026-10-10.md**. Le fonti esterne aggiornate sul donor ParliamentRAG sono il [README del progetto sito](https://github.com/Emeierkeio/ParliamentRAG), il [repository ISWC effettivo](https://github.com/Emeierkeio/parliamentrag-iswc) e il [dump dati con licenza separata](https://doi.org/10.5281/zenodo.21560331); i termini/diritti dei singoli input restano da valutare.
