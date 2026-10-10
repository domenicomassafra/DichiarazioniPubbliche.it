# Ricognizione indipendente prima del grilling

Data: 10 ottobre 2026, verifiche live circa 18:15–18:22 UTC.
Baseline valutata: `ebdc4f83c8ab322bbad4529d0dca6b583409c912`.
Mandato owner: ricognizione prima del grilling. Nessuna modifica a codice, test,
ticket, database, servizi o proiezione; nessuna richiesta a provider, spesa o deploy.
Questo verbale è evidenza della ricognizione, non approvazione di un nuovo scope.
Autorità: PRODUCT, CONTEXT, ARCHITECTURE, PLAN e ticket originali; HANDOFF è indice.
`tasks/index.md` non esiste in questo repository: non sono stati importati task DStack
di altri progetti. Le proposte sotto rimangono aperte fino alle decisioni dell'owner.

**Correzione dopo il primo round, 10 ottobre:** l'owner ha riaffermato la missione
integrata già descritta in PRODUCT: dichiarazioni/fonti/verifiche, confronti nel
tempo e tra persone sulla stessa proposizione o posizione, pagine Persona/Tema
e posizioni pubblicamente espresse da politici, influencer, attori, conduttori e
altre figure pubbliche. Q1 aveva erroneamente presentato archivio, confronti e
fact-check come missioni alternative. Q1 e la raccomandazione di una prima release
popolata solo archivistica sono ritirate. Le prove tecniche restano valide; i gap
del contratto pubblico sono lavoro da allineare alla missione, non ragioni per
ridurla. Le proposte della matrice sono ancora ipotesi, non rescope approvati.

## 1. Giudizio indipendente

Il progetto è una piattaforma privata di ricerca/verifica e un sito informativo
pubblico funzionante. Non è ancora dimostrato un archivio editoriale utilizzabile:
la produzione ha zero Capture, Passage, Statement Candidate e Claim Candidate, e
la proiezione pubblica è vuota. Questo non significa che i moduli siano inesistenti.

I tre nodi dominanti sono:

1. **Il modello pubblico deve coprire la missione integrata.** La promessa comprende le parole
   originali; la proiezione attuale è centrata su Claim + Finding e consente una
   PARAPHRASE, con testo originale privato e profilo excerpt non approvato.
2. **Manca la catena di autorità su un caso reale.** Diritti specifici, attribuzione,
   reviewer persistente, eventuale challenger, privacy e pubblicazione non sono
   prodotti da parser, test o UI. Il registro privato dei diritti ha zero righe.
3. **La sostenibilità editoriale è ignota.** Non esiste una misura affidabile dei
   minuti umani/euro per caso. Cento item, video, più provider e molte superfici
   aumentano il lavoro prima che un singolo caso ne dimostri il valore.

È fattibile una preview informativa e, condizionatamente alle scelte editoriali e
ai permessi, un pilot di un caso testuale. Non è provata la fattibilità operativa
dell'intera piattaforma senza una capacità editoriale esplicitamente assegnata.

## 2. Fatti e qualità delle prove

| Area | Osservazione fresca | Confidenza e limite |
|---|---|---|
| Git | Fetch origin/main; locale/remoto `ebdc4f8`; main pulita, una worktree, zero stash, nessuna PR aperta | Alta; baseline prima di questo verbale documentale |
| CI | Run [38074800874](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/actions/runs/38074800874), stesso SHA, 11/11 job success | Alta; lettura run remoto, suite non rieseguita localmente |
| Backlog | 125/90 DONE/20 IN PROGRESS/6 BLOCKED/9 FUTURE; 35 non DONE, PLAN e header concordi | Alta; `report_ticket_status.py --json` |
| Release | NO-GO/49: 16 Q-306, 4 artefatti, 29 gate ticket; receipt `96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f` | Alta; non 49 problemi indipendenti e non gate esclusivo della preview |
| Contract/inventory | Repository contract, licensing hashes (47 righe) e fixture inventory check passano | Alta sul controllo meccanico; nessuna licenza/decisione editoriale concessa |
| MiniPC | Alias minipc, home `/home/udodo`; mirror non-Git; web e tunnel active; cinque timer active/waiting | Alta; osservazione puntuale, nessuna restart/migrazione |
| Parità sorgenti | Su 627 path selezionati: 543 MATCH, 41 DRIFT, 43 MISSING, zero unsafe/stale-remote | Alta; solo prefix definiti da check_minipc_mirror_parity.py, non ogni file remoto |
| Build servita | HTML locale MiniPC e loopback SHA `60e76f42a138b8a5fde390cee1c21c8b2053ee3f661c7a3ef78f49aebe49a1b0`; uguale HTTPS browser | Alta; frontend precedente, non build di HEAD |
| Proiezione | File SHA `adffa37fcd7c3b85af33c9c09ce0cb8b3c37925ed529894473dd5621f769dc73`, generated_at 7 ottobre; zero dossiers/topics/contents | Alta; `/api/v1/index.json` e file letto direttamente |
| API/search | Health ok, schema public-v2 DRAFT, fingerprint `501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`; search records=[] | Alta; endpoint corretto è index.json, `/api/v1/index` restituisce 404 |
| Corpus produzione | Capture/Passage/Statement Candidate/Claim Candidate tutti zero; private_source_rights_record zero; source_profile 13 | Alta; SELECT in BEGIN READ ONLY/ROLLBACK. Tredici profili generici non sono tredici grant validi |
| Garlasco | PAUSED, 18 included, 18 UNKNOWN, capture_authorized=0, discovery_hits=0, 30 claim storici | Alta; SQL canonico read-only. I claim storici non costituiscono la nuova catena |
| Triage | Tabella research_discovery_triage_decision presente, zero righe | Alta; corregge il riepilogo che la descriveva non installata |
| Senato AKN | Ticket DP-233 documenta 104 Passage + 104 HELD Statement Candidate su temp store Mac/MiniPC, XML autentico pin bfac144eb5c54820971bc1020fece11aae56ec90 | Ricevuta storica letta oggi, non rerun; non corpus produttivo o approvazione fonte |
| Senato RDF | DP-234 documenta download indipendenti e 186 sedute; 12/14 AC, rights/provider ancora aperti | Ricevuta storica letta oggi; probe era in /tmp, non installato nel mirror corrente |
| Provider | Canary significativo OmniRoute/Groq non accettato nei ticket; nessuna nuova richiesta eseguita | Alta sullo stato del contratto, disponibilità upstream oggi non provata |
| Diritti/Q-306 | 16 questioni senza disposizione chiusa; excerpt profile non approvato | Alta sul registro; nessun nuovo parere giuridico |

## 3. Inventory dei prodotti e percorso minimo

| Funzione | Cosa esiste | Cosa non è dimostrato |
|---|---|---|
| Fonti/diritti/discovery | Registri, permit esatto Content/URL/famiglia, lineage e diagnosi fail-closed | Un grant corrente e una discovery autorizzata persistiti per il primo caso |
| Capture/Passage | Capture immutabile, hash, parsing, offsets nel testo canonico estratto, replay | Pipeline produttiva non vuota e revoca serializzata con tutti i writer |
| Candidate/matching | Validazione substring/hash, fake-provider tests, ricerca e classi distinte | Batch autentico con provider autorizzato; percorso manuale completo senza SQL non provato |
| Studio | Schermi corpus/inbox/candidate/provenance; submit può accodare review umana | Operatore completa task senza DB shell; QUEUED non significa REVIEWED o PUBLISHED |
| Promotion | Latest review persistita, lock candidato, parent/quote/identità/context checks | Linearizzazione contro writer esterno di revoca e acceptance operatore MiniPC |
| Evidenza/verifica/Finding | Evidence approval distinto da retrieval, sufficiency gate, cutoff e verifica deterministica | Primo caso autentico completo e challenger con autorità durevole per high-risk |
| Pubblico | Sei pagine HTTPS, API/search coerenti vuote; template Statement/Person/Topic/Content/Trace nel codice e fixture | Pagine popolate da record approvati e Statement pubblico indipendente da Finding |
| Correzioni/ritiro | Superseding Finding, storia append-only, revalidation e rimozione artefatti stale alla rigenerazione | Tempo di ritiro reale da static build/API/search/cache già distribuiti |
| Account/intake/admin | Account locale preparatorio, capability separate; intake/admin remoti disabilitati | OAuth/privacy/security acceptance; non necessari alla preview o al primo lettore |

I profili citizen/journalist/researcher/developer/public-figure/operator sono quelli
modellati da PRODUCT; non sono utenti acquisiti o intervistati. Non è emersa una
prova con utenti reali del beneficio entro 30 secondi.

Il primo caso dovrebbe usare un intervento testuale ufficiale stabile, autore
disambiguabile e una proposizione semplice. AKN Senato è un candidato concreto,
non una fonte già autorizzata. Riduce ASR e speaker diarization; non elimina da
solo provider extraction, reviewer o profilo di citazione.

Sequenza proposta, subordinata al grilling:

1. Preservare la missione integrata e definirne l'acceptance sul primo caso;
   assegnare responsabilità editoriale, autorizzare una fonte/Content e
   gli usi distinti di capture, retention, model, link e excerpt.
2. Persistire manifest/lineage → una Capture → un Passage → un Candidate; usare il
   percorso supportato e autorizzato, oppure progettare esplicitamente il seam
   manuale se manca. Non assumere che sia già disponibile.
3. Reviewer autenticato: testo, speaker, contesto, matching e decisione persistita;
   promotion e replay con prova a due transazioni della revoca.
4. Per le proposizioni fattuali: evidenze/Observation APPROVED, cutoff,
   Finding e autorità editoriale; nei casi high-risk challenger indipendente.
5. Rights/privacy/publication per la versione esatta; proiezione isolata e readback
   sito/API/search; correzione/ritiro misurati prima di dichiarare il flusso accettato.

Il costo umano comprende decisioni iniziali per famiglia di fonti e attività per
ogni caso/versione. Misurare lavoro attivo, attese, reviewer handoff, costi
misurati/stimati/ignoti e tempo di ritiro separatamente. Nessuna stima oraria
retroattiva è giustificata. Il claim «low maintenance rather than a newsroom» è
ancora un'ipotesi operativa, non un risultato.

## 4. Matrice completa dei 35 ticket

Status: IP=IN PROGRESS, B=BLOCKED, F=FUTURE; nessuno viene cambiato.
Costo qualitativo residuo: b=check bounded, m=integrazione/acceptance,
a=più workflow/runtime; e=dipendenza umana/esterna non stimata.
Owner sono ruoli proposti da nominare, non persone già incaricate.
DO NOW su un profilo preview/fonte non chiude l'intero ticket stable-v1.

| Ticket/stato | AC o prova ancora aperta; valore | Proposta | Dipendenza, owner; costo |
|---|---|---|---|
| DP-201 B | Canary ufficiale significativo, schema/model/usage/costo; estrazione automatica | DEFER fino al percorso scelto | Credenziale/quota/budget/provider; operatore; m+e |
| DP-202 B | Parent live e gold benchmark errori/tempo/costo MiniPC; qualità | DEFER | 201; operatore/reviewer; m |
| DP-203 B | Fanout bounded, cap/outage/replay e queue reali; contenimento costo | MERGE CANDIDATE campagna 201→203, AC distinte | 202; operatore; m |
| DP-204 B | Groq live audio lecito, receipt/fallback/disaccordi; media | CONDIZIONALE | Diritti/key/budget; operatore; m+e |
| DP-208 F | .1–.10 reference/DER/F1/holds/licenze/runtime e decisione; diarizzazione | CONDIZIONALE, NO-GO valido | 204/207; reviewer/operatore; a+e |
| DP-214 IP | .1/.2/.4–.8 corpus100/discovery/recall/replay/MiniPC; corpus utile | RESCOPE proposto 1→10 prima di100 | Fonte/manifest/diritti; owner/ricercatore; a+e |
| DP-215 IP | .9 source role/lineage/scope/time/rights di tutte le fonti scelte; qualità fonte | DO NOW sul primo profilo | 214 e source review; ricercatore; m+e |
| DP-229 IP | .8 challenger durevole indipendente/waiver qualificato; rischio high-risk | CONDIZIONALE, mai bypass | 228/215/309; reviewer indipendente; a+e |
| DP-233 IP | .10 source family approvata e suo canary MiniPC; testo autentico | DO NOW come candidato prima fonte | Source rights/speaker/review; owner; m+e |
| DP-234 IP | DVNS provider approvato e schema/rights/licenza; dati strutturati | DEFER | 215/228/provider; source owner; m+e |
| DP-301 IP | .8 disposizione qualificata DP306/307; linguaggio sicuro | MERGE CANDIDATE sessione legale | Counsel/owner; e |
| DP-304 IP | .1 inventario completo incl. JSON/log/error/filesystem/provider/retention; privacy | DO NOW profilo preview | Deployment reale; privacy reviewer; a+e |
| DP-307 F | .1–.9 reviewer, Q306 disposte, policy/re-review; responsabilità | DO NOW decisioni qualificate | 306; owner/counsel; e |
| DP-405 IP | .3 Person pubblico vuoto non rappresentabile + .6 AT; archivio persone | RESCOPE .3; AT con410 | Contratto public-v2; product owner/tester; m+e |
| DP-406 B | .6 AT e Topic/membership reale approvata; browsing | DEFER | 430/425/corpus; editor/tester; m+e |
| DP-407 IP | .4 unresolved pubblico vs omissione privata + .7 AT; fonte/contesto | RESCOPE .4; AT con410 | Privacy/contratto; owner/tester; m+e |
| DP-408 B | .5 AT e relazione reviewed reale; evoluzione nel tempo | DEFER | 104/105/425; editor/tester; m+e |
| DP-409 IP | .8 manual SR/search/filter/result states; ricerca | MERGE CANDIDATE campagna410 | 402/403/405–408/425; tester; b+e |
| DP-410 IP | .1/.2 telefoni/keyboard/SR/contrast/touch; preview usabile | DO NOW profilo preview | M4 pieno resta distinto; tester/owner; m+e |
| DP-412 IP | .5 SR/zoom/grayscale/motion/focus/target/name; componenti | MERGE CANDIDATE campagna410 | 411/413; tester; b+e |
| DP-416 IP | .1–.4 Collection→Source→Passage→Candidate→Claim/corpus/acceptance; Studio | MERGE CANDIDATE campagna operatori420 | 113/114/414/corpus; operatore; m+e |
| DP-417 IP | .1–.4 vere queue/triage/replay/bulk, ledger vuoto; triage | CONDIZIONALE dopo fonte | 209/212/414; reviewer/operatore; a+e |
| DP-418 IP | .1–.4 review/blockers/decision/readback/AT e revoca concorrente; promotion | CONDIZIONALE, revoca prima di promotion | 117/212/414; reviewer/integratore; a+e |
| DP-419 IP | .1/.2/.4 live/operator, .3 player media lecito; ispezione | CONDIZIONALE, text-first richiede rescope | 210/414/capture rights; operatore; m/a+e |
| DP-420 F | .1–.5 no DB shell, recall/time/task/usability reali; costo umano | DEFER fino al slice | 214/415–419; operatore/tester; m+e |
| DP-421 F | ADR dopo420, GO projection-only o NO-GO motivato; Case opzionale | CONDIZIONALE | 214/420/M3; owner; b+e |
| DP-422 IP | .1 real populated route set riaperta; .8 v4 checked; coerenza | MERGE CANDIDATE campagna M4 | 405–409/426–429/corpus; editor/tester; m+e |
| DP-429 IP | Manual SR/keyboard/zoom/motion; Esplora | MERGE CANDIDATE campagna410 | 409/425; tester; b+e |
| DP-507 F | Auth/session/CSRF/roles/negative mutations se exposure; admin | CONDIZIONALE | Trigger admin remoto; security owner; a |
| DP-508 F | Abuse/SSRF/privacy/store/retention/escalation se intake; contribuzione | CONDIZIONALE | 302 e intake approvato; security/operator; a |
| DP-701 IP | .1/.2/.5 identity/collision, .7 rollback, .8 handoff; preview identity | DO NOW profilo minimo | Owner/counsel; m+e |
| DP-702 F | Decisions/notices/surfaces/failures/invalidation/authority; release trust | DO NOW profilo preview | M3/M5/223; owner/counsel/security; a+e |
| DP-703 IP | .1/.2/.4–.10/.12 launch set≥3 families/rights/snapshot/rollback; corpus | RESCOPE proposto primo record | M2/M3/603/604/701; editor/source owner; a+e |
| DP-704 F | .1–.13 real rehearsal/correction/failures/rollback/decision; sicurezza release | DEFER | M2–M6/701–703; operator/owner; a+e |
| DP-705 F | .2–.12 version/gates/candidate/runtime/authority/post-release; stable-v1 | DEFER | 701–704; owner/operator; a+e |

Tre orizzonti: **preview** con profili pertinenti DP304/307/410/701/702;
**primo record** con fonte/diritti/reviewer/flusso pubblico accettati;
**stable-v1** con gli AC originali, rehearsal e release authority.
100 item DP214 e ≥3 famiglie DP703 restano requisiti aperti fino a un rescope
esplicito. Accorpare campagne non cancella le prove di ogni AC. Nessuna
cancellazione viene proposta come già autorizzata.

## 5. Lentezza, riuso e limiti

Il vincolo dominante è autorità reale sui dati, non quantità di software. I commit
su account/local inference/Topic/Trace sono implementazioni effettive, ma non
dimostrano di aver ridotto il tempo al primo record. Non c'è evidenza per chiamarli
tutti spreco. Aumentano però la superficie da mantenere prima della prova economica.

I fix seriali di replay/rights/latest review/cache/demo boundary e la riapertura
DP422.1 dimostrano costo di integrazione: seam locale e fixture non equivalevano
all'acceptance end-to-end. Questi fix di sicurezza restano necessari. La proposta
è fermare nuove espansioni finché una sola fonte percorre la catena e il costo è
misurato; non eliminare le difese per accelerare.

Il confine preview/stable è già deliberato in LAUNCH: non va riaperto come domanda
fattuale, né usato per presumere i cinque signoff della preview.

Controllo official-first dei donor al 10 ottobre:

- [Senato OpenData](https://github.com/SenatoDellaRepubblica/OpenData): CC BY3.0,
  metadati RDF senza testo degli atti. [AKN](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData):
  CC BY4.0 e resoconti XML. AKN branch head osservato
  `df4ad2c0611e272eabde1deac59b7eb510e1b889`; il pilot locale usa il pin distinto
  sopra. Riusare prima l'adapter locale, senza trasferire licenze a WebTV/altre pagine.
- [ParliamentRAG backend](https://github.com/Emeierkeio/parliamentrag-iswc): Apache2.0,
  head osservato `6bf9f964361a0dda3b0aad219e3dffa77ff1976c`; non confondere repo sito,
  codice e dataset. I dati hanno licenza separata dichiarata nel README, da verificare
  sull'artefatto esatto prima di import. Nessun grafo importato o stack adottato.
- [Hypothesis client](https://github.com/hypothesis/client): BSD2 con componenti di
  terzi sotto licenze proprie; head `b4d085a2f893aa6de3b61d8b8bc3ae4d0f24fc1a`.
  Pattern selezione/annotazione utile per Studio; server/identità non automaticamente autorizzati.
- [Meedan Check](https://github.com/meedan/check): MIT, repo dichiaratamente ambiente
  di sviluppo non produzione. Workflow di review come riferimento, non nuovo runtime.
- faster-whisper/WhisperX/yente restano alternative condizionali: nessun benchmark
  hardware, pin/licenze transitive o licenze dei pesi/dataset completati qui; non
  possono sostenere una raccomandazione di installazione. L'audit donor locale ha
  già scelto un solo core PostgreSQL e riuso di pattern, non piattaforme parallele.

Confronti di prodotto: [Pagella Politica](https://pagellapolitica.it/progetto)
documenta scelta di fatti verificabili, citazione della fonte, due review oltre
all'autore e correzioni. Il suo costo editoriale non è sostituito da una UI.
[OWID](https://ourworldindata.org/about) distingue narrative, insight, topic e
strumenti dati, inclusi termini distinti dei provider terzi. La lezione proposta
è distinguere compiti e rendere ispezionabile la fonte; non copiare asset o stack.

## 6. Teardown UX basato su browser vero

Chrome/CDP già disponibile, riuso del driver QA esistente; nessuna installazione.
Sei route HTTPS HTTP200, Last-Modified 7 ottobre; account/accedi/studio404.
Screenshot diagnostici temporanei `/tmp/dp-recon-{1440,390}-{home,explore,method}.png`;
non sono asset del prodotto o screenshot di una nuova build locale.

| Problema | Prova e impatto | Gravità; prossimo test |
|---|---|---|
| Home promette ricerca ma corpus è vuoto | Live390: vuoto a y884;320 a y986, dopo input e «recenti». Il lettore cerca prima di conoscere il limite | Alta; utenti riconoscono stato/azione entro5s prima di digitare |
| Empty search attribuisce problema alla query | Home submit bilancio → /esplora/?q=bilancio → «Modifica ricerca o azzera filtri», records=[] | Alta; distinguere corpus vuoto da no-match su corpus popolato |
| Metodo rimanda troppo il contenuto | Live390 primo corpo y844,320 y902; indice11link prima della spiegazione | Media; trovare che cosa viene verificato entro30s su telefono |
| Progetto non rifluisce a320 | Ancora GitHub lunga: clientWidth320, scrollWidth333, right333.03 | Media;320px e zoom200 con URL lunghi, nessun overflow pagina |
| Header ha hit area piccola | Cerca/Menu live mobile altezza22.39px misurata | Media, non verdetto WCAG automatico; touch e verifica spazio/target effettivo |
| Parafrasi resa come citazione nella Trace | Source-only TraceRecord.astro69/75: virgolette/blockquote di dossier.claim; Statement route75/100 e contract dichiarano PARAPHRASE | Alta prima dei record; fixture originale diverso dalla parafrasi, controllo tutte le viste/metadata |
| Compiti editoriali con grammatica troppo uniforme | UtilityDocument/hero/righe nei mock v3/v4 e nel frontend; Metodo/Correzioni/Dati hanno scopi diversi | Ipotesi visuale, media; test riconoscimento senza titoli e task completion |

Non classificare il footer «Accedi» dell'HEAD come link rotto live: il sito attuale
non lo mostra. La pagina Dichiarazione completa, Person/Topic/Content/Trace popolati
e Studio sono letti nel codice/prototipi, non collaudati su record pubblici autentici.

Prove positive: primo Tab skip link corretto; ricerca cambia URL; dialog filtri
apre e Escape chiude, con focus ripristinato dopo onClose. Zoom browser200% sulle
sei route (viewport1280→inner640/DPR2) senza overflow in quel controllo. Questo non
annulla l'overflow Progetto a320. Nessun audit umano screen-reader, contrasto,
performance o utenti reali: DP410 e AC manuali restano aperti.

Quattro territori da confrontare dopo il grilling, senza vincitore approvato:

1. **Archivio editoriale:** testo/citazione, data e fonte protagonisti, composizione
   tipografica distinta per compito; rischio austero/giornale, costo medio.
2. **Atlante documentale:** documento originale, locator/selezione e pannello di
   contesto; rischio densità mobile e disponibilità excerpt, costo medio/alto.
3. **Racconto cronologico:** versioni e relazioni navigabili; rischio equiparare
   cambiamento a contraddizione/intent e alto costo review, costo alto.
4. **Strumento di ricerca:** query, risultati compatti, filtri progressivi e percorsi
   alla fonte; rischio diventare dashboard generica o privilegiare esperti, costo medio.

I mock devono comprendere vuoto onesto e populated test-only isolato, desktop/mobile,
fonte offline, rettifica, testo lungo e attribuzione ambigua. La tipografia non
risolve l'assenza di contenuto approvato o una parafrasi presentata come originale.

## 7. Albero del grilling e checkpoint

Skill lette: plan-grilling, plan-grill-with-docs e plan-domain-modeling nelle copie
locali. Si usa frontiera per round, non dodici domande sequenziali indipendenti.
Nessuna decisione editoriale è stata assunta o scritta come approvata.

```text
Missione integrata: fissata dall'owner, non alternativa da scegliere
  → significato degli stati di verifica e distinzione fatto/opinione
  → criteri di confronto cross-person e nel tempo, con contesto e fonti
  → percorsi Persona/Tema e valore misurabile per il lettore
Radici operative ancora aperte: capacità umana; budget operativo
  missione + capacità + budget → fonte/caso, permessi e via text/media/provider
  fonte + permessi → attribuzione, Candidate/review, contract Statement/Claim/Finding
  contract + responsabilità → pubblicazione/correzione/ritiro e costo per caso
  compito lettore + dati pubblicabili → IA, quattro direzioni e prototipi/test UX
  prove pilot → rescope/accorpamenti35, 1→10→eventuale100 e stable release
```

La preview a sei route resta separata secondo LAUNCH; profili legali/identity/AT
rimangono PENDING-OWNER/EXTERNAL o non provati. Le scelte fonte, design, provider
e rescope dipendono dai comportamenti e dalle risorse ancora da discutere.
Le contraddizioni Person vuoto, stato pubblico blocked e paraphrase/citazione
devono entrare nei round pertinenti; non saranno corrette tacitamente.

Checkpoint aggiornato: ricognizione consegnata, missione integrata riaffermata
dall'owner e Q1 ritirata. L'owner ha risposto a capacità/budget: **zero reviewer
editoriali disponibili**, circa **EUR10/mese come ipotesi da misurare**, prove
empiriche di quota quotidiana Antigravity, audio e consumo elettrico locale.
Nessuna promessa di infallibilità o nuova autorità di pubblicazione è approvata.
L'owner ha poi ordinato il lavoro: **GPT-6 in Codex/ChatGPT-web e corpus storico
prima**, Antigravity/audio/modelli locali dopo che il percorso funziona; prima
grilling, poi ticket futuri e automazioni economiche. Hitler/Mussolini sono casi
proposti, con periodo/temi/limiti ancora aperti. La quota temporaneamente abbondante
è un input dell'owner, non una misurazione o una disponibilità garantita futura.
**Risposte successive Q4/Q5:** storico permanente; finire prima acquisizione,
trascrizioni/testo, catalogo, immissione, frontend, verifica e test end-to-end,
poi mega raccolta. **Chiarimento Q7:** la persona è l'owner, con circa cinque ore
settimanali indicative per controlli rapidi soprattutto non testuali, per esempio
immagini corrette delle persone. Non è revisione editoriale completa del testo
o dei verdetti. L'intenzione è automatizzare il lavoro testuale; comportamento
nei casi incerti e autorità di pubblicazione restano aperti. Approvazione foto,
attribuzione e fact-check sono decisioni distinte. **Ultimo steering:** aumentare
le domande indipendenti per round; esempi concreti. Il caso ipotetico di uno storico
che cita e critica slogan chiarisce che estrarre parole senza contesto non
attribuisce una posizione. Citazione/imitazione/discorso riportato/confutazione
devono restare distinti dall'adesione; non si registra il caso come frase autentica
di Barbero. Contesto sufficiente e adattivo, non una finestra temporale universale;
anche un filmato apparentemente esplicito richiede autenticità/identità/sequenza.
Riprendere con un round multiplo su astensione, incertezza fattuale, eccezioni,
pilot storico, traduzioni e pubblicazione futura. Nessuna risposta è presunta.
Scheduling e soglie quantitative dipendono dalle misure.
Registrare le decisioni durevoli nei file canonici
appropriati e ricalcolare la frontiera. Nessun redesign o cambiamento di contratto
prima della comprensione condivisa confermata dall'owner.

### Ricognizione dei consumi, destinata alla fase successiva

Esistono receipt e ledger per provider/model/task, request/attempt, token,
audio-secondi e aggregazioni per data/source/content/claim/collection. Non sono
ancora una misura completa del costo operativo: candidate_extraction.py:1341
persistisce MEASURED_PROVIDER_COST anche quando :2415–2431 ha calcolato una stima
da token/rate o upper bound; Antigravity con rate zero può così apparire measured
zero. worker_handlers_transcript.py:584–606 conserva LOCAL_COMPUTE_UNMETERED nel
receipt locale ma il totale zero API può essere classificato ZERO_COST. Non esiste
misura Wh/kWh. Questi gap vanno corretti al seam canonico prima di usare i totali
per stimare il budget; non è stata apportata una patch durante il grilling.

Gli attuali cap USD5/day, USD1/source/day e USD0.25/job non impongono EUR10/month.
[Antigravity /usage](https://antigravity.google/docs/cli/commands/usage) e
[plans](https://www.antigravity.google/docs/plans) offrono quota/crediti e overage
Never; la quota non equivale a un numero di token convertibile in prezzo fisso.
[Groq ASR](https://console.groq.com/docs/speech-to-text), il provider audio già
configurato, documenta tariffe per durata e minimo10s/call; le stime locali
attuali non includono quel minimo. Nessun account/quota è stato interrogato,
nessuna inferenza o chiamata audio eseguita per questa ricognizione.

Fonti storiche primarie da valutare, non importate né licenziate per decreto:
[Archivio Luce — Mussolini](https://www.archivioluce.com/tag/benito-mussolini/)
e [Bundesarchiv — Hitler](https://www.bundesarchiv.de/im-archiv-recherchieren/archivgut-recherchieren/nach-themen/archivalien-zu-adolf-hitler/).
Il [programma di digitalizzazione del Bundesarchiv](https://www.bundesarchiv.de/das-bundesarchiv/aus-unserer-archivarbeit/digitalisierung-von-archivgut-zum-nationalsozialismus-1933-1945/)
mostra perché un corpus storico resta aggiornabile. Inventario/fonti/testi,
registrazioni ed edizioni/traduzioni richiedono provenienza e permessi distinti.

## Final-round code inspection and owner answers Q9–Q14

The authoritative current decision checkpoint is PLAN.md's active grilling
section. Earlier unresolved-authority/frontier statements above describe earlier
rounds: Q14 now selects autonomous final fact-checking and future per-result
publication after validation. Current gates, launch status and ticket AC have
not changed. Q9/Q10 accept abstention and distinct insufficient-evidence results;
Q11 requires active ambiguity investigation plus a small exception queue;
Q12/Q13 require multiple people and multilingual sources/originals/Italian
translations. Do not reduce this to one person or Italian-only coverage.

Fresh source inspection, without runtime execution, identifies these deltas for
the eventual prompt/backlog:

- `verification_runtime.py:903` supports numeric and exact-text/status rules,
  not general fact-checking of every claim type. `finding_runtime.py:37` still
  maps conclusive runs to POLICY_HOLD. Autonomous final review needs a versioned
  contract, not a model-confidence shortcut or fabricated human credentials.
- `relation_runtime.py:14` receives no Person identity; distinguish same-person
  position changes from cross-person divergence before classifying relations.
  Opposite opinions do not independently establish factual falsity or intent.
- `context_integrity.py:15` uses Italian lexical signals; `:211` uses a bounded
  character window. Neither constitutes multilingual semantic context assurance.
- `wording_contract.py:638` holds unsupported language rules and unreviewed
  machine translation. Public-v2 currently exposes wording metadata, not original
  or translated bodies; DP-221 DONE covers that baseline, not the new requirement.
- `relation_policy.py:44` requires both published Findings; `public_projection.py`
  projects finding-centered dossiers. Attributable opinions and documented
  statements without a factual verdict need an explicit public-record contract.
- DP-309/310/311 implement human HIGH/LEGAL review and credential separation.
  The new automated authority target must be reconciled explicitly, preserving
  auditability/rights/privacy and any separately qualified legal requirements.
- Denial of an earlier utterance is a check about a documented speech act; it
  differs from truth of its content, endorsement, position change and intent.
  Absence from the collected corpus cannot prove that something was never said.

The owner requests one final central-question round before one complete
Prompt2Prompt handoff for four native Chat On Steroids subagents. Prompt creation
and implementation remain subsequent deliverables; no such execution is claimed
by this read-only inspection. The prompt must preserve all 35 outstanding tickets
and explicitly reconcile any DONE baseline affected by the new requirements.

Native orchestration verification: Chat On Steroids is installed locally; its
current upstream [tool-surface reference](https://github.com/totec448-spec/chat-on-steroids/blob/main/docs/tool-surface.md)
documents the Core tool `agents` with `spawn`, `message`, `status` and `finish`.
Use the actually discovered schema in the target chat, not a fabricated
`spawn_agent` call or a substitute Orca workflow. One run creates its worker set
once and reuses sleeping workers via message. The documented worker context
ceiling is 400,000 app-accounted tokens, not an assumed 500,000–1,000,000.
This is documentation/capability evidence, not proof of four workers launched or
of live connector authorization in a future chat. The external master handoff
and native worker task/result channels must remain distinct.

## Risposte definitive Q15–Q20 e consegna del prompt

L'owner richiede parole esatte nella dichiarazione pubblica, mai una parafrasi
sostitutiva; riassunti separati sono ammessi. Originale e traduzione identificata
restano distinti. La sua affermazione universale sul copyright non costituisce
clearance: la [CGUE in Infopaq](https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:62008CJ0005)
riconosce che anche estratti brevi possono contenere espressione creativa protetta.
Specifica il percorso applicabile per citazioni esatte senza ripiego parafrastico
nella dichiarazione; non è un nuovo parere giuridico o un grant a una fonte.

Persona × Tema usa filtri incrociati e sintesi precomputate, datate e citate,
non richiede un chatbot. Automazione forte anche per documenti processuali;
verbatim documentario, allegazione e accertamento del fatto sono controlli diversi.
Continuità fonti/temi con eventi rilevanti accettata. Redesign scelto dall'owner
più avanti, senza immagini o implementazione in questo incarico.

**Q19 restringe il mandato precedente:** un solo prompt esterno per coordinatore
con quattro worker nativi, SOLO creazione/modifica/aggiornamento ticket e documenti
di piano; implementazione in un incarico separato. Prompt corrente indicizzato
in HANDOFF.md. Preparato non significa lanciato: nessun worker Chat On Steroids
o risposta esterna è dichiarato eseguito dalla preparazione del file.

## Riproducibilità e limiti

Eseguiti: git fetch/status/log/branch/worktree/stash, gh PR/run readback;
report_ticket_status, check_launch_preflight --expect-no-go,
check_repository_contract, check_licensing_inventory --check-hashes,
generate_fixture_inventory --check, check_minipc_mirror_parity --json;
SSH systemd/hash/API e SQL read-only; browser live e lettura sorgenti/ticket/ADR.
Non rieseguita la suite completa invariata, non eseguiti paid/live-provider canary,
promotion/correction production, migrazioni o deploy.

La query iniziale su una tabella denominata source_rights_review è fallita perché
inesistente; è stata corretta leggendo lo schema e interrogando
private_source_rights_record in una nuova transazione READ ONLY. I conteggi sopra
provengono dalla query corretta. Nessuno stato è dedotto dalla query fallita.
