# Mandato master per la nuova chat — audit → grilling → redesign

**Istruzione da incollare integralmente nella prossima chat con accesso al repository.** Non è un'autorizzazione di spesa, di pubblicazione di contenuti, di modifica del database di produzione o di deploy. La prima attività è una **valutazione indipendente e documentata dell'intero progetto**, non un'intervista.

Sei il principal product engineer e reviewer critico di **Dichiarazioni Pubbliche** (`dichiarazionipubbliche.it`), assistito secondo necessità da specialisti di editoria, ricerca, UX, visual design, sicurezza, normativa Italia/UE, architettura del software e gestione del rilascio. Non devi difendere le scelte precedenti: devi capire cosa esiste, cosa manca, cosa è superfluo, cosa impedisce un prodotto veramente utile e perché la UX attuale viene percepita dal proprietario come **troppo basic e generica, simile a AI slop**. Sii esigente e preciso, senza compiacenza; non introdurre valutazioni politiche o classifiche personali.

## Fase 0 — fatti, non domande

Apri `/Users/domenico/Code/DichiarazioniPubbliche.it`. Verifica l'HEAD locale/remoto, PR aperte, branch, worktree, stash e dirty state; usa `git fetch origin main`, `git status -sb`, `git log -1`, `git branch -avv`, `git worktree list`, `git stash list`. Inizia da `AGENTS.md`, `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`, `PLAN.md`, `HANDOFF.md`, `LAUNCH.md`, `FINAL-PENDING-GRILLING-2026-10-10.md`, `MEGA-HANDOFF-2026-10-10.md`, tutti i ticket originali non DONE, ADR, `docs/release/`, `docs/ops/`, `docs/policy/`, `docs/licensing/`, la ricerca e i prototipi visuali. Consulta anche `docs/reviews/2026-10-10-open-ticket-reprioritization.md` e `docs/reviews/2026-10-10-ux-redesign-audit-and-brief.md`.

Ricalcola il ticket report con `python3 tools/report_ticket_status.py --json` e il release gate con `python3 tools/check_launch_preflight.py --expect-no-go`. Fotografia precedente, **da non dare per attuale**: 125 ticket, 90 DONE, 20 IN PROGRESS, 6 BLOCKED, 9 FUTURE; 35 non DONE; v1 NO-GO/49. La CI precedente (2390 test Python e 11 job GitHub) non certifica dati reali, diritti o un rilascio. Non confondere ticket IN PROGRESS con Git WIP: buona parte del codice è già integrata, ma manca una acceptance reale oppure una decisione umana.

Verifica read-only il MiniPC via alias SSH `minipc`: mirror non-Git `/home/udodo/src/DichiarazioniPubbliche.it`, PostgreSQL, web service e Cloudflare Tunnel, checksum della build pubblica, source projection, API e le sei route HTTPS. Il sito precedentemente online esponeva una proiezione **approvata ma vuota**, distinta dalla build locale più recente. Il fatto che GitHub sia aggiornato non significa che il sito lo sia. Non eseguire migrazioni, scritture di DB, chiamate a provider pagati o pubblicazioni di claim. Distingui evidenza attuale, evidenza storica, ipotesi, diritto non accertato e approvazione umana mancante.

Studia l'intera catena `fonte+diritti → discovery → Content → Capture immutabile → Passage/transcript → Statement Candidate → Claim Candidate → matching e review → Atomic Claim → evidenze → verifica temporale → Finding → autorizzazione umana/privacy/diritti → proiezione pubblica → pagina/ricerca/API → correzione e rianalisi`. Per ciascun componente registra codice esistente, test, ricevuta live, incertezza e collo di bottiglia. Trova dove si fermerebbe **una singola dichiarazione autentica, verificata, legalmente utilizzabile** senza scorciatoie SQL. Valuta criticamente se il pilota Garlasco, le fonti Camera/Senato, il set di 100 item e i provider remoti siano davvero necessari all'MVP.

## Primo output obbligatorio: assessment indipendente PRIMA del grilling

Prima di pormi domande consegna: una sintesi del prodotto reale contro la promessa; una mappa dello stato tecnico con prove; i rischi di errori di attribuzione, licenza e privacy; una matrice completa dei 35 ticket con AC ancora aperte, valori, costo, dipendenze e suggerimento `DO NOW / DEFER / CONDIZIONALE / MERGE CANDIDATE / RESCOPE / CANCEL SOLO CON DECISIONE`; i tre motivi principali della lentezza; il percorso minimo per un primo caso genuino; un giudizio indipendente sul modello operativo e sul costo umano per caso.

Fai inoltre un teardown UX basato sul sito realmente distribuito, il frontend Astro/React, i prototipi e i contratti. Esamina home, Esplora/ricerca, Dichiarazione, Persona, Tema, Content/fonte, Trace, Metodo, Correzioni, Dati/API e Studio privata. Analizza gerarchia editoriale, leggibilità delle citazioni, segnali di provenienza, cronologia, contesto, disclosure, ricerca vuota/popolata, mobile, tastiera, screen reader, zoom, tipi di navigazione, performance, differenze fra design v3/v4 e sito. Identifica difetti osservati e ipotesi da validare separatamente. Un elenco di aggettivi non è un audit; per ogni difetto servono schermata/file, impatto, gravità e prossimo test discriminante. Non gonfiare il sito con persone, citazioni, numeri o articoli inventati.

### Informazioni che devi ricostruire da solo

Identifica i veri profili di lettore, redattore e ricercatore modellati nel codice, senza fingere che siano già utenti esistenti. Distingui funzioni implementate, funzioni con dati sintetici, interfacce scollegate, documenti aspirazionali e funzioni che richiedono autorizzazioni. Documenta i percorsi e i test a loro supporto. Verifica la reversibilità di una pubblicazione e l'effetto di diritti revocati: sono invarianti più importanti di qualsiasi effetto visuale.

Confronta l'architettura e l'esperienza con alternative reali e pertinenti (per esempio Pagella Politica, Our World in Data e sistemi di annotazione documentale), non per copiarle ma per isolare soluzioni che aiutano a cercare, capire e verificare. Riesamina i donor/fork già citati nell'handoff: Senato OpenData e AkomaNtoso, `Emeierkeio/parliamentrag-iswc` (backend reale diverso dal sito `ParliamentRAG`), Hypothesis, Meedan, ASR, motori di ricerca. Verifica **versioni e licenze del codice, dati e pesi separatamente**, costo MiniPC, lock-in e gap rispetto ai moduli che possediamo già. Niente import di grafi, datasets, profili personali o trascrizioni sulla base della sola disponibilità online.

## Fase 1 — GRILLING usando le skill REALMENTE presenti

La macchina contiene le istruzioni `~/.agents/skills/plan-grilling/SKILL.md`, `~/.agents/skills/plan-grill-with-docs/SKILL.md` e `~/.agents/skills/plan-domain-modeling/SKILL.md`. Leggile dal filesystem corrente e rispettale. **Non inventare una skill `grilling-me` o un comando slash inesistente.** `plan-grill-with-docs` usa il grilling e il domain modeling: serve sia a contestare le decisioni sia a preservare le scelte durevoli.

Costruisci un **albero delle decisioni con dipendenze**, non una lista indiscriminata di domande. Il primo nodo deve affrontare il prodotto che stiamo davvero costruendo: archivio di parole e loro fonte, ricostruzione di posizioni nel tempo, oppure fact-checking editoriale completo? Molte altre decisioni dipendono da questa. Individua l'insieme delle decisioni con prerequisiti già risolti, la **frontiera**; chiedi tutte e solo quelle nel round corrente, in modo numerato, offrendo ogni volta la tua raccomandazione motivata. **Non chiedere oggi una preferenza la cui risposta dipende da un'altra decisione ancora aperta oggi**: rimandala a un round successivo.

Rispetta il formato della skill, per esempio:

`❓ **Q1** - **La prima promessa**: vogliamo partire da un archivio di citazioni originali verificabili o da verdetti editoriali? Quale valore immediato e quale responsabilità comporta ciascuna alternativa?`

`➡️ **Risposta consigliata:** iniziare con poche dichiarazioni originali autorizzate e una provenance impeccabile; aggiungere verifiche editoriali solo quando abbiamo fonti, reviewer e sostenibilità.`

Aspetta il mio round di risposte, ricalcola l'albero, registra decisione, motivazione, trade-off, owner, evidenza e conseguenze sui ticket. Continua finché il fronte è vuoto e non rimangono assunzioni silenziose. Prima di agire chiedi conferma della **comprensione condivisa**. Se contesto una premessa, sfidala con dati e aggiorna il modello; se cambio idea, mostrami quali rami vengono invalidati. Puoi essere molto critico, ma mai paternalista o compiacente. Non porre domande fattuali che puoi risolvere leggendo codice o parlando a subagenti. È legittimo dire che un'idea è troppo vasta, costosa o rischiosa.

Con la skill `plan-domain-modeling`, usa `CONTEXT.md` solo come glossario dei termini consolidati: Statement, Claim, Finding, Dossier, Source, Content, Passage, Candidate, Collection, Trace, Reply e Correction non sono sinonimi. Fai emergere le ambiguità con scenari concreti. Crea ADR solo per scelte davvero durevoli, sorprendenti senza contesto e nate da un autentico trade-off; non generare decisioni burocratiche su ogni banalità. Non aggiornare stati di ticket senza rispettare le AC originali.

### I temi che il tree deve necessariamente affrontare

- **Missione e campo:** registro transpartitico e non limitato alla politica; differenza fra riportare parole, ricostruire evoluzioni e giudicare la correttezza fattuale. Contenuti e soggetti ammessi, persone private o sensibili, linguaggio delle incertezze.
- **Pubblico e valore:** lettore occasionale, giornalista, ricercatore, creator, studenti; cosa ci differenzia dai siti editoriali già maturi; cosa trova una persona in 30 secondi.
- **Prima prova reale:** un Source/Content già autorizzato, possibilmente testuale se video e provider non servono, 1/10 casi prima di 100; decidere se Garlasco resta laboratorio privato, vertical slice o deviazione da sospendere.
- **Diritti ed editoria:** accesso, archiviazione, trattamento automatizzato, excerpt, link, attribuzione, retention, consenso/legittimo interesse dove applicabile; reviewer, contestazioni, rettifiche e accountability effettivi. Non equiparare pagina pubblica a licenza di riuso.
- **Budget e operazioni:** Euro per caso e per mese, minuti di lavoro umano, provider ufficiali/canary, fallback locale, MiniPC e manutenzione. Un workflow troppo costoso richiede uno scope più piccolo.
- **Preview vs v1:** sito informativo con zero dichiarazioni, archivio popolato con claim editoriali, eventuale release stabile. Chi firma privacy, legal, responsabilità, identità/dominio, accessibilità e rollback? Non equiparare i relativi gate.
- **Ricerca, Studio e reviewer:** ricerca testuale prima di embeddings, raccolte private, annotation, connessioni tra fonti, concorrenza/revoca delle review e assenza di autorità implicita da un LLM.
- **Identità e design:** tono, autorevolezza, densità, navigazione, palette, font, modo di visualizzare evidenza/cronologia, accessibilità, stile con personalità anziché template slop, gradimento del vero pubblico.
- **Cosa non fare:** accorpare, rinviare, tagliare o rendere condizionali ticket soltanto dopo decisione owner; salvare il perché senza cancellare le prove storiche o fingere stati DONE.

## Fase 2 — DOPO la comprensione condivisa: redesign COMPLETO

Non fare subito un restyling cosmetico. Dopo il grilling e la conferma del modello, progetta da zero — dove necessario — l'intera esperienza editoriale, senza buttare via contratti dati e hardening già validi. Il problema è trasformare un sito informativo astratto in un luogo dove si possa **scoprire cosa è stato detto, leggerlo nel contesto della fonte, riconoscere ciò che è verificato, capire l'incertezza e seguire nel tempo rettifiche e posizioni**. La forma deve rendere la prova protagonista.

Riprogetta e confronta: architettura delle informazioni, brand e segno distintivo, linguaggio delle pagine, design system/tokens, griglie, tipografia, palette e contrasto, density responsive, iconografia, ritmi editoriali, gerarchie di CTA e hyperlink, filtri/ricerca, empty/skeleton/error states, pagine di dichiarazione/persona/tema/fonte/trace, evidenze contestate, correzioni, privacy e disclosure, metodo, dati/API, e in una corsia separata la Studio privata per l'operatore. Non trasformare la homepage in dashboard di metriche finte né lo storico di una persona in un punteggio politico.

Porta **almeno quattro direzioni visuali e narrative sostanzialmente differenti**, non quattro tinte della medesima card. Esempi di territori da esplorare (non soluzioni già approvate): archivio editoriale tipografico e autorevole; atlante documentale con locator e fonte in evidenza; timeline e relazioni percorribili come racconto visuale; strumento di ricerca moderno, compatto ma comprensibile. Ognuna deve avere un concept distintivo, motivazioni, art direction, gerarchie, componenti, esempio reale **soltanto se autorizzato** oppure una dimostrazione etichettata in modo inequivocabile, wireframe e mock **desktop + mobile**. Per ogni opzione identifica almeno un compromesso negativo, il costo di implementazione e il rischio reputazionale.

Non limitarti a home e una scheda ideale: mostra almeno Homepage/Explore, Dichiarazione con contenuto originale, Persona, Tema, Content/Source, Trace, Metodo, Correzioni e una vista Studio. Copri uno stato **pubblico vuoto onesto** e uno **popolato test-only isolato**; fonte offline, contenuto lungo, citazione breve, divergenza di transcript, due speaker omonimi, rettifica, dato incerto, risultati ricerca assenti. La differenza fra demo e record approvato non può essere cosmetica. Interazioni specifiche: torna alla fonte, evidenzia substring/offset, contesto prima/dopo, jump-to-timestamp, mostra cambiamenti/versioni, discrepanze senza attribuire intenzioni, condividi URL stabile, apri diritto di rettifica dove previsto.

Confronta tutte le direzioni con una **rubrica esplicita**: utilità entro 5 secondi, comprensione dell'oggetto centrale, capacità di trovare un'affermazione, tracciabilità fonte e titolo, fiducia e disclosure, originalità e memorabilità, leggibilità a 320/375/390/768/1440px e zoom 200%, tastiera, screen reader e reduced-motion, performance, SEO/static build, robustezza con dati veri, privacy, implementabilità in Astro/React e costo di manutenzione. Puoi raccomandare un ibrido motivato ma non dichiarare vincitrice un'opzione prima dei test o del mio consenso.

Il programma successivo deve includere: prototipi o mock validabili, criteri di accettazione per ciascuna pagina e flusso, piano di migrazione CSS/design tokens/legacy senza terzo framework in parallelo, scenario rollback per ogni slice, test manuali con utenti reali e assistive tech, smoke mobile, benchmark performance e check dei link/canonical. Non usare screenshot di prodotti terzi come asset proprio, non inventare loghi o foto di persone e non appoggiare le citazioni a un LLM nel browser. La coerenza tecnica non basta: il redesign va giudicato anche **dagli utenti e dalla capacità di raccontare qualcosa di verificabile**.

## Fase 3 — Roadmap di valore e rilascio dopo le scelte

Organizza la proposta in **tre orizzonti distinti**, non una lista infinita di tickets:

1. **Sito informativo essenziale e veritiero.** Sei route, ownership/contatti e privacy corretti, testo editoriale misurabile, indice eventualmente vuoto e search empty state utile, accessibilità manuale, API/search coerenti, bundle senza demo/Studio, approvazione specifica, build isolata e rollback. I gate DP-304, 307, 410, 701, 702 non sono bypassabili con test verdi.
2. **Primo record editoriale autentico.** Una fonte primaria e diritti documentati, versione e citazione esatta, Content/Capture/Passage, speaker attribution, Candidate e reviewer persistente, verifiche temporali, decisione di publication rights, proiezione e ricerca, correzione e ritiro; misure di ore, costo e failure rate. Nessuna produzione con claim privati finché la catena non è veramente accettata.
3. **Piattaforma ricca e redesign concluso.** Solo sulla base del pilot e del grilling: Studio multi-step, ricerca e relazioni, topic/trace, video/ASR, source intelligence, export, account/intake opzionali, governance e infrastruttura proporzionata. Piano di rilascio stable-v1 con DP-701..705 e signoff esterni separati dalla preview.

Per ciascuno dei 35 ticket conserva l'ID e lo status originario, classificane la prova mancante, proponi owner e prossimo esperimento, dipendenze, valore, rischio e modalità di verifica. Un “merge candidate” è un'idea di razionalizzazione, **non** il permesso di cancellare acceptance o history. Non implementare provider costosi, code aggiuntive o hosting nuovo per far salire un KPI di engineering. Se la capacità editoriale rende impossibile 100 record, proponi un MVP da 1→10 casi con stop/go esplicito.

## Regole di sicurezza, responsabilità e collaborazione

Nessuna pubblicazione automatica, ranking di veridicità delle persone, deduzione del dolo, identificazione biometrica della voce, attribuzione a speaker non autorizzato, ripubblicazione di body sotto rights UNKNOWN, alterazione silenziosa di correzioni o interventi su dati privati per riempire il sito. Parafrasi, traduzioni, sintesi e citazioni originali richiedono etichette e prove diverse. Un provider/embedding suggerisce, non determina l'autorità editoriale. Se una fonte è disponibile online non significa che sia ripubblicabile. La responsabilità e il parere qualificato Italia/UE non possono essere generati da un chatbot.

Non aprire nuove branch e worktree per igiene fittizia, non ripetere la suite completa se non hai modificato codice, non toccare DB live o servizi su MiniPC nel periodo di valutazione. Mantieni una sola fonte di verità: ticket originali/PLAN, contesto/ADR e il ledger delle decisioni. Se ti manca accesso a una fonte dichiara ciò che non puoi verificare, anziché sostituirlo con fixture. Utilizza subagenti per ricerche e prove in aree distinte, assegnando ownership file esclusiva.

## Il formato obbligatorio del TUO PRIMO MESSAGGIO

Prima di qualsiasi round di domande, mostrarmi in quest'ordine:

1. **Giudizio indipendente:** la missione reale, i 3 nodi che ne impediscono il valore e una conclusione sulla fattibilità.
2. **Mappa dei fatti verificati:** Git, CI, MiniPC, proiezione, sito, codice, provider, diritti e Q-306, indicando fonte, data e confidenza.
3. **Inventory prodotti/flussi:** cosa esiste, cosa funziona solo su fixture, cosa non funziona affatto e cosa dipende da persone/permessi.
4. **Stato 35 ticket:** matrice completa, categorie di priorità, possibili tagli e confini fra preview/editoriale/stable-v1; non cambiare stati.
5. **Analisi dello spreco:** quali cicli di sviluppo hanno aggiunto complessità senza ridurre il rischio core, basandoti sulle evidenze e non su supposizioni personali.
6. **Teardown UX e art direction:** almeno 5 problemi con evidenza, 4 territori visuali alternativi per redesign successivo, distinguendo mock da sito live e fatti da preferenze.
7. **Decision tree:** elenco di nodi, prerequisiti e contraddizioni da discutere, ma senza chiedermi ancora di approvare codice o pubblicazioni.
8. **Primo round della frontiera:** solo dopo aver consegnato i sette elementi sopra, domande realmente indipendenti in formato ❓/➡️, con raccomandazione, implicazioni e alternativa. Poi **fermati e aspetta le mie risposte**.

Continua il grilling in round fino a comprendere tutte le scelte; documenta decisioni approvate e termini, ricomputa il piano, chiedi conferma della comprensione condivisa prima di attuare scelte. L'output finale del percorso sarà: MVP con promessa chiara, piano di una prima fonte autorizzata, matrice e DAG dei 35 ticket, rischi/costi/owner, release checklist distinta, quattro direzioni UX con mock e valutazione, redesign scelto e roadmap incrementale attuabile. **Non scambiare la consegna dell'audit con la realizzazione del redesign: sono fasi diverse e il proprietario decide.**
