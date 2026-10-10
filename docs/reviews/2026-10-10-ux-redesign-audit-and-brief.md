# Dichiarazioni Pubbliche — audit UX critico e brief per un redesign completo

**Data:** 10 ottobre 2026 · **Tipo:** valutazione preliminare per l'agente successivo, **non** approvazione del redesign · **Ambito:** sito pubblico, non Studio privata.

## Esito senza diplomazia di facciata

Il frontend è tecnicamente più disciplinato di quanto la sua impressione visiva suggerisca: tipografia coerente, componenti semantici, proiezione pubblica controllata, stati vuoti onesti. Ma oggi comunica soprattutto **«un progetto che spiega come funzionerà»**. Manca ancora una riconoscibile esperienza editoriale: il percorso *parole originali → fonte → verifica → evoluzione nel tempo* è descritto ripetutamente, ma non è dimostrabile in una pagina pubblica. Molti schermi seguono lo stesso schema «titolo serif grande + descrizione + righe divisorie + collegamenti», senza una scelta compositiva che renda memorabile l'oggetto specifico della pagina. È comprensibile che l'utente lo percepisca come **basic/slop**, pur non essendo un sito fatto di generiche card SaaS.

Il redesign va **valutato dall'agente nuovo prima di fare grilling al proprietario, e deciso solo dopo**: le proposte sotto sono alternative da mettere alla prova, non il design selezionato. Occorre un cambiamento reale di linguaggio, gerarchia, narrazione e comportamento, non solo un'altra passata di CSS, un nuovo slogan o ulteriori micro-componenti.

## Perimetro e qualità delle prove

- **Live osservato, 10 ottobre ~19:47 CEST:** `https://dichiarazionipubbliche.it/` risponde HTTP 200, HTML SHA-256 `60e76f42a138b8a5fde390cee1c21c8b2053ee3f661c7a3ef78f49aebe49a1b0`, `Last-Modified` 7 ottobre. Le sei route `/`, `/esplora/`, `/metodo/`, `/correzioni/`, `/dati/`, `/progetto/` rispondono 200; `/studio/`, `/accedi/`, `/account/` rispondono 404. L'API `/api/v1/health` è `ok`, schema pubblico v2 in stato `DRAFT`, **zero dossier**; indice pubblico con `records=[]` e fingerprint `501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`. Il tunnel Cloudflare inoltra al servizio statico/API del MiniPC su `127.0.0.1:18090`.
- **Fonte di implementazione valutata:** `web/src/pages/{index,esplora,metodo,correzioni,dati,progetto}.astro`, `web/src/layouts/BaseLayout.astro`, `web/src/components/{SiteHeader,UtilityDocument,ExploreClient}`, `web/src/styles/{tokens,base,primitives,legacy,global}.css`, `web/src/lib/tokens.ts`. `main` e sito distribuito **non coincidono**: la valutazione del frontend aggiornato è di codice e artefatti precedentemente osservati, non un collaudo visivo della nuova produzione.
- **Riferimenti visuali ispezionati:** `prototypes/final-hybrid/{home,explore}.png`, `prototypes/v4-ledger-spine/home-desktop.png`, `prototypes/v4-implementation/dp426/{home-desktop,home-mobile}.png`, `dp427/statement-mobile.png`, `dp428/{metodo-mobile,correzioni-desktop}.png`. Contengono anche **fixture chiaramente dimostrative**; non vanno presentati come screenshot del sito live o come pubblicazioni reali.
- **Contratti:** `PRODUCT.md`, `DESIGN.md`, `docs/35-public-product-architecture-v3.md`, `docs/ux/{design-system-v1,design-system-v2,evaluation-rubric}.md`, `docs/38-public-visual-redesign-v4-selection.md`, `LAUNCH.md`. Il browser live è stato verificato per URL, HTTP, contenuti e hash; **nessuna sessione osservata con utenti reali, nessun audit screen-reader completo e nessuno screenshot live mobile nuovo**. I giudizi percettivi sono ipotesi motivate dai sorgenti e dai mockup, da confermare su dispositivo.

## Pagella diagnostica (1 scarso, 5 eccellente)

I numeri giudicano **l'efficacia UX oggi**, non la qualità del codice o l'impegno di implementazione. `N/V` significa che non sarebbe serio attribuire un voto senza dati pubblicabili.

| Dimensione | Voto | Evidenza concreta e implicazione |
| --- | ---: | --- |
| Comprensibilità iniziale | **3/5** | Home: «Le parole contano. Le fonti anche.» + lede spiegano l'intenzione, ma il beneficio specifico richiede un secondo testo; manca una prova visiva dell'atto di risalire alla fonte. |
| Identità e memorabilità | **2/5** | Newsreader/IBM Plex, quadrato Segno e cobalt sono coerenti; le composizioni prototipali restano molto simili fra loro, con grande headline + righe. L'identità non è ancora abbastanza riconoscibile senza marchio. **Giudizio visivo da validare sul live aggiornato.** |
| Valore effettivamente fruibile con archivio vuoto | **2/5** | Home sostituisce correttamente la ricerca con lo stato «Nessuna dichiarazione ancora pubblicata»; Esplora mostra un secondo empty state e rimanda a Metodo/Progetto/Correzioni. Il lettore può capire le regole, ma non compiere la promessa di trovare una dichiarazione. |
| Gerarchia tra le sei pagine | **2/5** | `UtilityDocument` dà identica composizione a Metodo, Correzioni, Dati e Progetto; la diversità del compito si riduce principalmente al copy e alla lunghezza. Il metodo, per esempio, offre sia rail sia indice interno delle sezioni. |
| Navigazione e coerenza delle destinazioni | **2/5** | Live `/accedi/` è 404 mentre `BaseLayout.astro` include «Accedi» nel footer del sorgente; il frontend nuovo non è ancora live. `SiteHeader.astro` mette «Progetto» nella navigazione primaria, in disaccordo con la IA canonica («Esplora · Metodo · Cerca»). Il link Cerca porta a Esplora, oggi vuota. |
| Fiducia, trasparenza e sicurezza editoriale | **4/5** | Zero schede inventate, disclaimer di archivio vuoto, distinzione tra attribuzione e verità, correzioni append-only, assenza di punteggi alle persone. Il **quinto punto** richiede informazioni pubbliche accettate su titolarità, contatto, privacy e responsabilità, non un effetto grafico. |
| Orientamento e densità su telefono | **3/5 provvisorio** | Breakpoint a 40/56/60 rem, `details` per il menu, larghezza del testo e target da 44px sono definiti; sui mockup mobile i contenuti di fiducia diventano sequenze lunghe e un indice di 11 link può rubare gran parte del primo schermo. Va misurato su 320/375/390/428px e zoom 200%. |
| Accessibilità come progetto | **3/5 provvisorio** | Skip-link, `main`, `aria-current`, controlli nativi, focus e reduced-motion sono presenti. Nessuna conclusione WCAG end-to-end senza tastiera, VoiceOver/TalkBack, contrasto dei singoli stati reali, reflow e lettura dei messaggi vuoti. |
| Esperienza completa fonte/verifica/tempo | **N/V** | Esistono `SourcePath`, record e Trace nei prototipi/contratti, ma in pubblico risultano zero record. Va valutata su fixture **segregate** e poi sui primi contenuti revisionati; nessun successo di demo prova un flusso editoriale reale. |

### Problemi di prodotto da affrontare per primi

**P0 — La promessa non è ancora esperibile.** Non simulare esempi, valutazioni, protagonisti o cronologie. In fase informativa, il compito primario è capire **cosa sarà consultabile, con quali garanzie e cosa esiste davvero oggi**; l'esperienza di ricerca ricca verrà quando il dataset pubblico sarà autorizzato. Il redesign deve avere due stati ufficiali distinti: **preview vuota** e **archivio popolato**.

**P1 — Quattro trust page appaiono come un solo template replicato.** Un metodo leggibile per passi verificabili, un registro correzioni per eventi/versioni, dati/API come utilità tecnica e progetto come accountability richiedono capitoli, esempi e azioni differenti. Il loro riuso di `UtilityDocument` può restare tecnico, ma non deve appiattire l'esperienza.

**P1 — Troppa ripetizione della missione e scarsa prova.** «Fonti, contesto, verifica, niente punteggi» ricorrono in masthead, hero, trust path, Metodo e Progetto. Serve un'unica definizione efficace in alto, poi una sequenza visiva **dimostrativa del processo** rigorosamente etichettata come *schema del metodo* e non come caso reale. Ogni frase deve rispondere a una domanda diversa.

**P1 — Il design registrato in `DESIGN.md` è più forte della sua resa pubblica.** La tesi «civic ledger, non dashboard» e il Segno come attenzione/selection sono ben formulati; nella preview vuota il Segno non può attivarsi attorno ai record, perciò restano fondamentalmente una testata tipografica e separatori. Aggiungere barre cobalt finte aggraverebbe il problema.

**P1 — IA e link verificabili.** Chiarire e allineare il peso di Progetto nel menu, il destino di Cerca quando l'indice è vuoto, e l'assenza di `Accedi` sul server effettivo. Ogni link visibile deve aprire una destinazione valida e pubblicabile; non costruire nuove schermate di login prima delle verifiche sulla privacy.

**P2 — CSS compatibilità che ostacola il cambio di linguaggio.** `global.css` include uno strato `legacy.css` lungo circa tremila righe; la sezione v4 sovrappone vecchie classi, anche se il contratto parla di sistema congelato e compositi. È debito di manutenzione verificabile, **non prova automatica di un difetto visivo**. Il nuovo agente deve decidere un piano di migrazione per template senza creare un terzo design system parallelo.

**P2 — Documenti di progetto contrastanti.** `docs/35-public-product-architecture-v3.md` prevede solo Esplora/Metodo/Cerca in header, ma `SiteHeader.astro` include Progetto; `docs/ux/evaluation-rubric.md` parla ancora di «fact-checking product» come oggetto primario, mentre la v3 dichiara le *dichiarazioni* oggetto canonico. Prima di realizzare il nuovo design va aggiornata **l'autorità concettuale** tramite decisione esplicita, non applicando contemporaneamente regole incompatibili.

## Principi non negoziabili per qualunque direzione

1. **Partire dall'oggetto, non dall'effetto:** un documento pubblico riconoscibile, navigabile e citabile, con provenienza, date, limiti e versione; il caso reale emerge solo dopo approvazione.
2. **Originale → interpretazione:** parole testuali/parafrasi/traduzioni marcate correttamente; sorgente e suo localizzatore accessibili; separare prova che sia stato detto da prova che il contenuto sia corretto.
3. **Due esperienze vere, zero finzione:** se vuoto, raccontare stato e metodo con artefatti astratti etichettati; se popolato, accesso immediato a ricerca, fonti e cronologie. Non usare le fixture come notizie vere.
4. **Un gesto grafico funzionale:** interazioni, selezione, cronologia o un meccanismo tipografico distintivo. Niente sfumature/shadow/KPI/AI-chat falsa/seal istituzionale o card universali usati come riempitivo.
5. **Mobile con regia propria:** la prima schermata deve dire stato attuale + azione onesta; rail diventa indice compatto; fonti e correzioni restano sempre leggibili e raggiungibili, senza dipendere da hover.
6. **Tono pubblico comprensibile:** italiano concreto e preciso; scrivere «Da dove viene la frase», «Che cosa sappiamo», «Cosa manca» prima del gergo di pipeline, `schema_version` o valutazioni interne.
7. **Performance e responsabilità:** HTML statico leggero, font self-hosted, poche isole React dove servono; focus visibile, 44px target, zoom 200%, 320px senza overflow, riduzione del movimento, stampa e contrasto dimostrati con test reali.

## Quattro vere direzioni da prototipare dopo il grilling

| Direzione | Idea riconoscibile | Home / pagina dichiarazione / mobile | Forza | Rischio da confutare |
| --- | --- | --- | --- | --- |
| **A. Atlante delle parole** | Editoriale contemporaneo con titoli a grande scala e «frase originale» come fulcro; sezioni quasi da atlante stampato, variazioni intenzionali del ritmo tra pagine. | Preview: status editoriale + piccolo diagramma *come si arriva a una scheda*. Record: testo della dichiarazione, poi percorso leggibile verso fonte e revisione; su telefono ogni pagina inizia da una sola domanda. | Identità memorabile e alta accessibilità per non esperti. | Rischio «rivista elegante ma vuota»; servono azioni e un esempio metodologico dichiaratamente astratto. |
| **B. Biblioteca delle fonti** | Visivamente centrata sulla provenienza: codici/etichette sobri, scaffale di fonti autorizzate, un «passaporto della dichiarazione» con provenienza e versione. | Preview: mostra il metodo in termini di documenti accettabili; record: fonte primaria e localizzatore chiarissimi; telefono: fonte in vista dopo la frase, con disclosure per dettaglio tecnico. | Dimostra la differenza rispetto a un newsfeed e rafforza verificabilità. | Può diventare archivio burocratico e sovraccaricare metadata; non scavalcare la dichiarazione come oggetto primario. |
| **C. Linea del tempo leggibile** | Il brand mette in scena la memoria: ogni dichiarazione è un evento con un prima/dopo, non un pallino giudicante. Navigazione cronologica controllabile, nessuna freccia causale inventata. | Preview: diagramma astratto di versioni e correzioni; record: frase, fonte, stato alla data e cambi approvati; su telefono indice cronologico con dettaglio inline e ancore condivisibili. | Firma originale per Trace e correzioni, utile quando il dataset cresce. | Senza più eventi reali può essere decorazione; non suggerire che cambiare opinione equivalga a mentire. |
| **D. Indice radicale** | Interfaccia più funzionale e audace: potente tipografia, ricerca centrale e righe quasi bibliografiche; una grammatica densa ma rigorosa, una sola colorazione di focus. | Preview: dichiara subito «0 schede» e offre Metodo/Progetto/trasparenza; archivio: ricerca, filtri contestuali e risultati immediati; mobile: record-first con filtri in sheet, niente pannelli finti. | Velocità, costo contenuto, leggibilità e lunga vita. | È vicino alla direzione «Ledger Spine» già selezionata: da solo potrebbe riprodurre esattamente il basic contestato. |

Non dichiarare un vincitore per semplice preferenza. Fare almeno **due concept davvero divergenti** su Home vuota, Esplora vuota e una dichiarazione con *fixture* marcata; includere desktop 1440px e telefono 390px e valutare leggibilità a 320px. Chiunque proponga un'altra versione dell'attuale Ledger Spine deve spiegare **quale esperienza cambia** in termini falsificabili.

## Architettura dell'informazione e componenti da ripensare

**Ora, sei pagine.** Home = promessa chiara, stato osservabile, un processo spiegato con prova astratta, una scelta d'azione; Esplora = archivio vuoto come stato di sistema e non risultato «0» di una ricerca che pare fallita; Metodo = 4 passi principali (origine, attribuzione, verifica, pubblicazione/correzioni) con approfondimenti progressivi e distinzioni chiare; Correzioni = registro temporale vuoto con politica revisioni, non ulteriore manifesto; Dati/API = collegamenti a risorse che rispondono, formati, versione e limiti, in lingua umana; Progetto = identità, responsabilità, stato, governance e contatti **solo una volta approvati**. Footer come trust-navigation attiva e verificata. Nessuna scheda, numero di utenti, testimonial o evento inventato.

**Quando esistono schede approvate.** Esplora possiede tutte le categorie (Dichiarazioni, Persone, Temi, Contenuti); Dichiarazione è l'oggetto condivisibile; Persona è cronologia, mai scorecard; Tema è dossier, non duplicato di Persona; Contenuto collega media o testo ai momenti originali; Traccia mette in sequenza **solo** relazioni revisionate. Ogni componente deve rispondere al «perché devo vederlo?», non alla disponibilità di un nuovo token.

**Inventario compositi da riesaminare:** PublicHeader (navigazione e ricerca quando vuoto), EmptyState (stato vs invito), SearchStage/FilterSheet (solo quando utile), StatementHeader (formulazione originale e variante), SourcePath (link e punto esatto), FindingSummary (affermazione, evidenza, incertezza), CorrectionHistory (versioni/repliche), ChronologyIndex/EvidenceTape (navigazione nel tempo), UtilityDocument (quattro pagine con grammatica differenziata). Conservare la sicurezza di `components/design/*`, ma giudicare caso per caso se la resa è distintiva.

## Verifiche UX da pretendere dal prossimo agente

- **Percorsi:** persona nuova in 5 secondi identifica cosa c'è oggi; utente cerca una frase nell'archivio vuoto e capisce la ragione; lettore segue una dichiarazione fixture a fonte/localizzatore/correzione senza un clic morto; lettore confronta due eventi senza interpretazioni politiche.
- **Visivi reali, non mockup scambiati per produzione:** confronti fianco a fianco live attuale, main locale nuovo e almeno due direzioni; 1440px, 390px e 320px; no confondere banner/demo con contenuto pubblico. Registrare data/SHA/viewport in ogni screenshot.
- **Accessibilità:** solo tastiera, VoiceOver macOS e almeno un lettore di schermo mobile quando disponibile; ordine H1–Hn/DOM; menu, focus restoration, annunci di risultati, zoom 200%, reflow, link e target touch, riduzione movimento, contrasto reale, stampa. Misurare e registrare i fallimenti, non «WCAG pass» per deduzione dal CSS.
- **Microcopy:** nessuna promessa di archivio operativo con zero record; niente scorciatoie verso dati non approvati; verificare i link API/contatti/footer sul sito effettivamente distribuito.
- **Gate di prodotto:** zero leak Studio/demo/fixture; niente automatismo di pubblicazione; semantica delle valutazioni legata a una dichiarazione, mai a una persona. Designer e owner non possono da soli attestare review legale e privacy.

## Grilling: domande da porre **dopo** l'assessment indipendente

1. In cinque secondi, che cosa deve capire una persona: **archivio storico**, **strumento per verificare una frase**, oppure **memoria dei cambiamenti**? Sceglierne una come promessa primaria.
2. Quali due pubblici vuoi servire per primi: lettore occasionale, giornalista, ricercatore, professionista, studente? Quale compito concreto devono completare?
3. Il sito con **zero dichiarazioni** deve apparire come anteprima editoriale, manifesto del metodo o un minimo portale utilitario? Quanto spazio dare esplicitamente allo stato «in preparazione»?
4. Cosa detesti negli screenshot attuali: font, spazi bianchi, gerarchia, composizione, ripetizione delle sezioni, vuoto di contenuto, troppo «istituzionale», mancanza di carattere? Mostrare tre punti precisi.
5. Quali 2–3 siti, riviste, archivi, brand o interfacce vorresti assomigliare per **sensazione**, e quali due vorresti assolutamente evitare? Le reference sono fonte di studio, non licenza di copia.
6. Vuoi una personalità più **editoriale e calda**, **grafica e audace**, **enciclopedica e rigorosa** o **tecnica e rapida**? Quanta sperimentazione tipografica accetti?
7. Quanto deve rimanere della decisione `Ledger Spine` e del contratto «paper/ink/cobalt, Newsreader/IBM Plex, niente shadow»? Il redesign completo può chiedere di **riaprire formalmente** quelle decisioni?
8. La fonte originale deve essere esibita subito oppure dopo una breve conclusione? Cosa conta di più: lettura lineare, confronto, o velocità di ricerca?
9. Quale gesto visivo dovrebbe essere il marchio di fabbrica: citazione originale, source window, cronologia, tipografia, navigazione per indici? Uno, non cinque decorazioni.
10. Su telefono cosa deve stare above-the-fold? Identità + stato del dataset, ricerca, prova del metodo, oppure un'introduzione?
11. Quali azioni del footer/header devono esistere già oggi, con contatti e titolarità realmente pronti? Che cosa resta assente finché mancano approvazioni?
12. Come giudicheremo la proposta: preferenza estetica personale, test di 5 secondi, scenario con fonte, accessibilità, prestazioni e confronto side-by-side? Concordare **criteri misurabili** prima di scegliere.

## Handoff eseguibile alla chat successiva

1. **Assessment prima del grilling:** leggere prodotto/architettura/design/questo audit; ispezionare live, `main`, prototipi e differenze; annotare eventuali nuove prove che smentiscono i voti. Non proporre la soluzione prima di avere compreso i compiti e le limitazioni.
2. **Grilling con proprietario:** usare le domande sopra con screenshot comparativi affidabili e un massimo di tre trade-off alla volta. Registrare decisioni, disaccordi e elementi da verificare.
3. **Brief definitivo dopo grilling:** scegliere 1 direzione + un'alternativa di riserva, definire IA, copy, componenti, motion, responsive, design tokens e criteri di qualità; decidere esplicitamente se revisionare i contratti DP-411/412/424/425. Non cambiare di nascosto le invarianti di `PRODUCT.md`.
4. **Prototipi confrontabili:** Home/Esplora vuote, Metodo, pagina Dichiarazione fixture con origine → verifica → correzione, un caso di Trace; varianti telefono e desktop con screenshot datati e descrizione delle interazioni.
5. **Solo dopo approvazione:** pianificare sviluppo e migrazione del layer `legacy.css`, QA accessibilità/mobile, test di contenuto e differenza GitHub vs MiniPC/Cloudflare. Deploy separato, con bundle verificato, titolarità, privacy, review e rollback autorizzati.

**Decisione al checkpoint:** redesign **richiesto**, diagnosi critica **preliminare**, direzione **da scegliere dopo valutazione completa e grilling**. Il documento non modifica software, stati dei ticket, diritti, pubblicazioni o autorizzazioni al rilascio.
