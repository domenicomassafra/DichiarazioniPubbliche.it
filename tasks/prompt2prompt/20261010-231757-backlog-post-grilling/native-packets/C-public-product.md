# Lane C — pubblico, wording originale, ricerca, Persona×Tema, UX

**Tipo:** pacchetto di proposte integrabili per il coordinatore; solo pianificazione, 10 ottobre 2026. **Ownership:** C. **Stato:** proposte non implementate; nessuna AC futura superata. Questo file non sostituisce PLAN, PRODUCT, CONTEXT, ARCHITECTURE o i ticket canonici. ID `C-NEW-*` strettamente temporanei: il prime assegna gli ID DP reali, risolve dipendenze e aggiorna documenti canonici. Non marcare DONE dal presente pacchetto.

## Decisioni vincolanti e ricognizione del codice

- **R02 / Q15–Q20:** ogni campo/quote/card/result/Trace/metadata che mostra «la dichiarazione» mostra **parole esatte nella lingua originale**, fedeli, contestualizzate, con approvazione dell'attribuzione e titolo valido per la pubblicazione dell'estratto. Non sostituire con `normalized_claim`/`PARAPHRASE`, nemmeno quando il wording non è lecitamente esponibile: quel caso non diventa una Statement pubblica artificiale. **R03:** `summary` separata, chiaramente dichiarata come «Riassunto» e mai in `blockquote`, `quotation`, `headline` che abbia semantica di citazione. Traduzione etichettata e collegata all'originale; mai «ha detto» nella lingua tradotta.
- **R15:** `INSUFFICIENT_EVIDENCE` è un controllo concluso senza prove sufficienti, `UNVERIFIED/NOT_YET_CHECKED` è controllo non ancora svolto, `UNRESOLVED` segnala esiti inconcludenti appropriati; uno stato privato `HELD/BLOCKED/UNDER_REVIEW` non diventa un fatto pubblico. **R16:** opinioni, posizioni, citazioni e dichiarazioni attribuite sono entità pubblicabili *in quanto Statement* con gate di pubblicazione autonomo anche senza Finding; «un'opinione è falsa» non segue da una verifica fattuale.
- **R18 / R19:** same-take = proposizione/posizione veramente equivalente e scope, tempo e condizioni compatibili; le differenze **fra persone** sono confronti cross-person, il **cambio di posizione** richiede la medesima Persona con due periodi distinti. Divergenza non prova falsità, menzogna, intenzione o ideologia. Posizione espressa in speech-act di citazione, imitazione, ironia o critica non è adesione.
- **R20:** ricerca per intersezione Persona×Tema (non chatbot), sintesi **precomputata** versionata con citazioni a originali datati e limiti del corpus; nessuna chiamata AI nella request pubblica, invalidazione su revoca/correzione. **R35/R36:** alternative di redesign realmente differenti, nessun vincitore scelto in questa pianificazione, nessuna immagine ora; QA mobile, AT e stati vuoti realistici.
- `poc/dichiarazioni_pubbliche/public_projection.py` `_sanitize_public_wording` (circa righe 1598–1794) controlla hash, `VERBATIM_ORIGINAL` vs `REPORTED_QUOTE`, derivate, segmenti e omissioni, ma pubblica **solo metadati** per source/summary/translation; il profilo DP-305 corrente vieta i corpi. `public_schema.py` (`PROJECTION_BUNDLE_ALLOWED_KEYS`: dossiers/topics/contents) resta **finding-first**: `dossier.claim` è `normalized_claim` PARAPHRASE, la validazione ne vincola hash e tipo. `public_api.py` `summary`, `/findings`, `/people`, `/topics`, `/contents` derivano ancora i principali legami dai dossiers/`finding_ids`. `web/src/lib/searchIndex.ts` enumera kind `finding/content/person/topic`, assegna `wording_type: "PARAPHRASE"` ai finding, costruisce Person a partire dai dossiers e non possiede kind `statement` autonomo.
- `web/src/pages/dichiarazioni/[slug].astro` stampa `dossier.claim` in `h1`, `name` JSON-LD, title e testo, correttamente etichettato oggi «Formulazione normalizzata · paraphrase». `TraceRecord.astro` invece lo racchiude già in `<blockquote>`; `ContentRecord.astro` lo racchiude tra virgolette in lista e dettaglio, `PersonRecord`, `TopicRecord`, `ClaimRow` e `ExploreClient` lo trattano come Statement principale. Non basta correggere una pagina: occorre una migrazione atomica di schema/projection/read consumers. Il prodotto precedente è coerente con *il suo* contratto, ma viola il **nuovo target** Q15; non attribuirlo a una regressione già certificata.
- `web/src/lib/relations.ts` costruisce Trace da `dossier.relations` e indicizza per `claim_id` con partecipanti `PublicDossier` aventi Finding; `relation_runtime.py` propone POSITION_CHANGE da stance opposte/non-overlap senza Person identity nel contratto input: il gate semantico belongs to **B**. C deve pretendere `relation_scope`, speaker IDs, confronto di tempo/contesto come dati **approvati**, e non riclassificare nel frontend. `web/src/lib/types.ts`, `projection.ts`, `searchIndex.ts` e `web/src/pages/search-index.v1.json.ts` sono seam reali per migrazione/version read.
- `DP-430 DONE` consegna Topic e membership **basate su finding IDs**, preservati i review events; `DP-434 DONE` consegna Content pubblico anche senza finding. `DP-405.3` resta aperta poiché Person viene proiettata solo se esiste un dossier; DP-407.4 resta aperta perché proiettare un hold rivela la membership privata. Queste non sono due versioni di «manca un CSS».
- Baseline autorizzata: sito MiniPC con proiezione approvata `501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`, **0 dossier/Topic/Content/ricerca** al checkpoint; sei pagine informative servite, dynamic route pubbliche intenzionalmente 404. Browser/fixture e build green NON sono canary di dichiarazioni reali o rilascio del nuovo wording. Il live UX audit 10 ottobre riporta a 320 px overflow su Progetto (320 client, 333 scroll), vuoto sotto fold su Home, pagina Metodo con 11 link indice prima del contenuto; login/account/Studio 404 live. Preservare receipt storici e fissare verifiche future fresche.

## Matrice dei 10 ticket originari: proposta per il prime

La colonna AC preservati si riferisce alle **checkbox esistenti**: non riscrivere checkmark o prove datate per affermare il nuovo outcome. Le `C-DELTA-*` sono bozze di nuovi AC e NON checkmark. Gli hard Depends on nuovi sono proposte soggette a verifica DAG del coordinatore. Fasi: 0 schema/contratti, 1 prima ingestione, 2 prima catena pubblica, 3 release/QA, 4+ continuo/redesign.

| Ticket / stato ora → proposto | Storico e AC ancora aperte (preservare) | Delta, owner e fase | Hard nuove proposte; soft / gate | Futuro readback |
|---|---|---|---|---|
| **DP-405 IN PROGRESS → IN PROGRESS** | 12 finding di una Person in fixture, correction/reply; private Person e unknown entrambi 404 su MiniPC. `AC-405.1/.2/.4/.5/.7/.8` pass; `.3` Person pubblica **zero record** non rappresentabile; `.6` AT/manuale. | C: cronologia di **Statement** verbatim anche senza Finding, ordinata per tempo dichiarazione con tie-break deterministico; filtro Persona×Tema senza sovrapporsi a C-NEW-05; no endorsement da `REPORTED_QUOTE`; provare zero-public Person solo con approvazione separata. Fase 2–3. | Hard C-NEW-01/02/03/04 e pubblicazione source B; soft DP-409/410/422; nessun hard link inverso con DP-409. | Person reale approvata + Statement con/senza Finding + approved-zero Person + held Person indistinguibile da unknown, URI canonical e HTML/AX, MiniPC fingerprint. |
| **DP-406 BLOCKED → BLOCKED** | `DP-430` Topic risolto in sorgente e fixture; `.1/.2/.3/.4/.5/.7/.8` pass; `.6` AT/manuale; **manca Topic + membership approvata in runtime**. | C: membership di Statement non limitate al Finding con topic review, scope, origine e data; Related Person senza «supporter/opponent» inferiti; connessione al filtro incrociato. Fase 2–3. | Hard C-NEW-01/02/05 per nuovo target; B attribution/speech-act; DP-430 già DONE. Soft DP-410. | Topic pubblico reale approvato con più Statement, una posizione opinion-only, un hold escluso, ambiguità slug e navigazione reale. |
| **DP-407 IN PROGRESS → IN PROGRESS** | Timed/written 12-moment fixture, zero-finding Content DP-434 e testo privato assente. `.1/.2/.3/.5/.6/.8/.9` pass; `.4` stato under-review/blocked pubblico contraddittorio col fail-closed; `.7` AT manuale. | C: moments of published **Statements**, original exact quote per moment, locator video timestamp o text-selector/hash senza sorgente inventata; Finding quando presente soltanto; rewriting `.4` come public **allowed states** senza leak di hold/review. Fase 2–3. | Hard C-NEW-01/02/03; DP-207 e DP-434 DONE; soft DP-410. | Timed/audio and written legally approved, no-Finding, zero moments, missing media, invalid/revoked moment, private ID inaccessible. |
| **DP-408 BLOCKED → BLOCKED** | Fixture relational UPDATE/CONTRADICTION/POSITION_CHANGE, suppression and corrections; `.1/.2/.3/.4/.6/.7/.8` pass. `.5` AT manuale e **real DP-104 reviewed relation canary** assente. | C: Trace può comparare Statement opinion-only; presentare originali + date + scope e relazione esplicita `SAME_TAKE_CROSS_PERSON` versus `POSITION_CHANGE_SAME_PERSON`, no inferenza client; caso «non ho mai detto X» visibile come relazione distinta dalla verifica di X. Fase 2–3. | Hard B new relation semantics/schema (`B-NEW-*` mappato dal prime), C-NEW-01/02/03; soft DP-410, DP-431. | Due persone stance opposte non sono position change; stessa persona tempi differenti idonei + inaccurate quote fail-closed; reviewed MiniPC relation reale. |
| **DP-409 IN PROGRESS → IN PROGRESS** | Static index e live approved-empty fingerprint convergenti, query bounded/diacritics/version/pagination-like filter; `.1–.7/.9` pass; `.8` AT/manuale. | C: search kind `statement` canonical; exact quote primaryTerms, `summary` secondaryTerms **identificati**, translations etichettate; Person pubbliche a zero Statement; fonte/topic/Content, risultati type e intersection coerenti, indexing safe revocation e match bounds. Fase 2–3. | Hard C-NEW-01/02/03; soft C-NEW-05, DP-402/403/429; **non** aggiungere DP-422 hard per evitare loop. | Due build same bytes, stale fingerprint blocked, no raw/transcript/search telemetry, live MiniPC search+API+site and 0 provider calls. |
| **DP-410 IN PROGRESS → IN PROGRESS** | `.3–.8` pass, `.1/.2` manual AT/contrast/interaction; lab CPU-throttle LCP/CLS/INP proxy e live empty evidence, no claim di field INP. | C: qualità su **tutte** le superfici nuove (verbatim/summary/translation, no Finding, Person×Tema, held/private/unknown, same-person/cross-person, redesign); affrontare viewport 320 e above-fold empty, links/404 live; non usare 100% automatismi al posto di VoiceOver + screen-reader mobile. Fase 3. | Hard C-NEW-03/04/05/06 e redesign implement solo quando scelto; DP-422 final. Soft D runtime deployment/correction. | Matrice 320/375/390/430/768/1440 + zoom browser reale 200%, keyboard, VoiceOver/mobile reader, contrast/focus, perf, SEO, production snapshot. |
| **DP-412 IN PROGRESS → IN PROGRESS** | Token/theme/design v1 e 42 primitive render assertions storico; `.1–.4/.6–.9` pass, `.5` screen reader + esatto 200% incompleti. | C: preservare vecchi token come baseline documentata, nuova direzione non selezionata; dopo owner choice aggiornare contratto componenti QuoteOriginal, TranslationLabel, Summary, SourceLocator, optionalFinding, RelationType, PersonaTopicFilter + states senza component zoo. Fase 0/3. | Hard futura C-NEW-07 scelta owner per **re-design**; non alterare dipendenza originale DP-411/413 DONE. Soft DP-425 DONE, DP-410. | Token/component meaning and keyboard/AX manual matrix, copy rights; match revised owner-approved design, no premature freeze. |
| **DP-421 FUTURE → FUTURE** | `.1/.2/.3` tutti aperti; DP-214/420 pilot/proof non raggiunto. Attuale header `Depends on: DP-214, DP-420, M3 policy` **non puro**: per checker proporre `DP-214, DP-420`; M3 legal/privacy gate nel prose. | C: GO/NO-GO **esplicito** sulla nuova entità public Case/Collection dopo real pilot; distinguere private Research Collection, Published Dossier, Topic e Content; se GO specificare model su public-safe IDs, rights, correction/withdrawal; se NO-GO motivare e mantenere routes. Fase 2–4. | Hard DP-214, DP-420 e solo DP token; soft B policy privacy/rights, owner decision e related DP-304/307. | ADR registrato, positive/negative source matrices; **nessun caso pubblicato** da una decisione. |
| **DP-422 IN PROGRESS → IN PROGRESS** | Structural clean-clone/demo route links/aliases e local v4 comparison pass; `.2–.9` pass; `.1` **riaperta** perché live reale 6 info pages, 0 routes dynamic. | C: cutover semantic Statement-first schema nuove route same IDs, canonical/legacy, RDF/JSON-LD/API/site links, search, corrections, no stale caches, real populated runtime; old v4 visual frozen is *historical*, redesign futuro separate new ticket. Fase 2–3. | Hard C-NEW-01/02/03/04/05 + existing route dependencies; soft D MiniPC parity/release and DP-410. | Real approved non-fixture canonical `/dichiarazioni/`, `/persone/`, `/temi/`, `/contenuti/`, `/tracce/`, source exact/link, redirects + same fingerprint; empty stays 6 info pages. |
| **DP-429 IN PROGRESS → IN PROGRESS** | 8/9 prose AC checked, AT/screen-reader AC unchecked; URL/back/focus, 200% Chrome and empty live pass. | C: distinguish corpus-size=0 versus filters yielded zero, unavailable index versus no authorized match; add bounded Persona and Topic intersected filters via C-NEW-05; cards never quote paraphrase; retain 200 char query and same deterministic search. Fase 2–3. | Hard C-NEW-03/05; soft DP-409/410, DP-422, C-NEW-08 for later redesign; protect DAG with cross-reference not reverse hard edges. | Search «bilancio» with 0 total record says archive currently empty, with populated index no-match says no result; 320px overflow-free, real VoiceOver/mobile AX. |

### Precise additional AC to add to pre-existing ticket (unchecked upon integration)

Per rispettare la stabilità degli identificativi esistenti, dare nuova numerazione **dopo** l'ultimo AC originale di ogni ticket. I riferimenti qui sotto sono proposte `C-DELTA-...`, non numeri definitivi; per DP-429 numerare tutte le nove acceptance storiche nella forma `AC-429.1..9` senza alterarne il significato e poi aggiungere le successive. Evitare di aggiungere doppie AC identiche a un ticket nuovo: la spec di contratto appartiene ai nuovi C-NEW, la prova del singolo **reader** al suo page owner.

| Ticket | Nuova AC negativa/positiva del suo consumer |
|---|---|
| DP-405 | C-DELTA-405-A: Person con Statement dichiarativa verificabile ma Finding assente appare con originale e «non verificato», senza badge di falsità; C-DELTA-405-B: Person zero-record *approvata* emette route esplicita, una privata/unknown no, equivalenza di 404 senza oracoli; C-DELTA-405-C: filtro Tema esclude menzioni/quote critiche non endorsate dalla sintesi. |
| DP-406 | C-DELTA-406-A: Topic ricostruisce solo membership approvate dei public Statement, anche opinion-only, senza Topic pseudo-label da claim_type; C-DELTA-406-B: Topic con zero public Statement mostra scope approvato e stato vuoto senza conteggio privato. |
| DP-407 | C-DELTA-407-A: timed/written selector corrisponde byte/hash/esatto original excerpt e localizzatore approvato; C-DELTA-407-B: privato/under-review/blocked non rivelato; solo status di verifica **già deliberatamente pubblicato** e permesso sullo Statement appare; Content con Statement no-Finding resta source-first. |
| DP-408 | C-DELTA-408-A: cross-person opposite stance rimane DIFFERENCE/DIVERGENCE, mai posizione mutata; C-DELTA-408-B: same-person after time/scope validation può essere POSITION_CHANGE solo se policy l'ha approvato; C-DELTA-408-C: ogni evento quote originale con source scope e selected-pair text equivalence, senza Finding obbligatorio. |
| DP-409 | C-DELTA-409-A: search result `statement` usa quote originale pubblicabile, duplicate `paraphrase` mai in title/primary_terms; C-DELTA-409-B: revoke quote updates index & API same fingerprint before reachability; C-DELTA-409-C: type/count/filters per authorized Statements, Person-zero only approved. |
| DP-410 | C-DELTA-410-A: Nuovo schema/version route matrix N→N+1, locale e MiniPC, 0 leak raw/private in DOM/ARIA, search/JSON-LD/RDF/API; C-DELTA-410-B: zero-corpus / zero-match / stale / denied indistinguishable where security requires; C-DELTA-410-C: VoiceOver desktop + screen reader mobile manual, viewport320/390 and exact zoom 200%. |
| DP-412 | C-DELTA-412-A: quote+summary+translation+optional Finding have distinct semantic typography, ARIA, screen-reader names, non-color states; C-DELTA-412-B: tokens change only after owner design decision, pass RTL/long German text and mobile zoom. |
| DP-421 | Conservare `.1–.3`; aggiungere C-DELTA-421-A: source pilot demonstrates GO/NO-GO against private-only collection, No-GO has no new public route; C-DELTA-421-B: if GO, old/held/missing public member causes fail-closed and no private graph leakage. |
| DP-422 | C-DELTA-422-A: populated first-class Statement/Person/topic/content/trace from one genuinely approved source and one non-factual Statement pass real MiniPC route/API/search/canonical+legacy, 0 fixture, 0 dead links; C-DELTA-422-B: version/retired content never remains current through page/search/sitemap/RDF/JSON-LD/cache. |
| DP-429 | C-DELTA-429-A: zero approved searchable total vs real no-match and index unavailable yield different honest UX; C-DELTA-429-B: Person+Topic URL filter restores back/forward, only safe intersection records, public synopsis clearly distinct. |

## Nuovi ticket proposti (ID temporanei; il prime attribuisce gli ID DP)

### C-NEW-01 — First-class Public Statement indipendente da Finding

Status: FUTURE
Milestone: M1 — Domain and schema convergence, con acceptance reader M4
Depends on: DP-105, DP-117, DP-221, DP-222, DP-430, DP-434

#### Problem

Oggi la risorsa pubblica nasce da Finding su Atomic Claim e diventa un dossier. Una dichiarazione documentata, una posizione non-fattuale o un'opinione senza factual Finding non ha un oggetto pubblico autonomo. Dossier.claim è formulazione normalizzata in PARAPHRASE, non il testo originale pronunciato e non un'identità affidabile di Statement.

#### Outcome

Un PublicStatement/version autonomo, pubblicabile con prova di attribuzione, contesto e diritti, riferibile a Person, Topic e Content, che esponga il riferimento all'eventuale Finding senza richiederne uno. La nuova proiezione rimane fail-closed e la pubblicazione della dichiarazione non costituisce un giudizio sulla verità del contenuto.

#### Traceability & constraints

R01, R15, R16, R18, R19; Q9–Q20, DP-105/117/221/222/430/434. La pubblicazione richiede provenance e policy ammesse, non il solo status private Candidate. Speech-act/endorsement sono distinti: citare, imitare o criticare un'affermazione non costituisce adesione. Il cutover dell'autorità pubblicativa è proprietà B; l'attuale runtime non è autorizzato per magia dal nuovo modello.

#### Scope

Input: Statement Candidate autorevole con occurrence di fonte approvata, speaker attribution, context/speech act, rights eligibility e pubblicazione versionata secondo gate B. Persistenza/proiezione: stable statement_id e version_id, source_occurrence_id, person_id, content_id, language, statement_time con precisione o unknown, public source locator, public wording binding, speech_act/stance semantics, publication decision ref, approved Topic membership refs e Finding refs opzionali. Correzioni e revoche append-only con supersession e materialization fingerprints; gli identifier non si ricavano da Finding. Output: primo livello PublicStatement in schema/API/HTML, con membership Person/Topic/Content, typed no-Finding state e route canonical. È consentita la migrazione dei dossier storicamente pubblicati solo quando nuovi gate esatto testo/rights/attribution lo dimostrano; non si fanno backfill automatici di false citazioni.

#### Non-goals

Nuova pipeline acquisizione, verifica autonoma, classificazione ideologica, inference di intenti, score Persona, promozione di candidati private, UI token/pagina o diritti acquisiti per deduzione.

#### Dependencies and sequencing

Hard preesistenti nel Depends on. Hard futuri: contratti B su review authority, attribution/context e quote rights, poi C-NEW-02 per corpo publishable e C-NEW-03 per consumers. Coordinamento soft con DP-402/403, DP-431, A source provenance e D MiniPC release. Non aggiungere DP-409 o DP-422 come hard parent, perché migrano a valle. Un denied record non blocca progettazione, schema e test per altri record autorizzati.

#### Acceptance criteria

- [ ] AC-C01.1: fonte e speaker riconosciuti, diritti/contesto/policy validi e published Statement con Finding nullo → stable public route, versione, data/tempo con precisione esplicita, Person/Content public refs e assenza di verdict inventato.
- [ ] AC-C01.2: un Finding fattuale valido si collega alla Statement giusta e alla sua specifica versione; un Finding non approvato/non pubblicabile è assente anche da indicatori e conteggi.
- [ ] AC-C01.3: atto di citazione/critica/ironia può essere annotato come parole pronunciate, ma non alimenta membership di adesione o sintesi di posizione quando il contesto non la supporta.
- [ ] AC-C01.4: private/held/revoked, rights unknown/expired, attribuzione non provata, contesto troncato, source/span mancanti e Topic membership private non producono Statement né oracoli attraverso IDs, routes, search, cursors, payload o error copy.
- [ ] AC-C01.5: replay immutato genera stessi ID/bytes/sha; correzione/retract muta solo la versione corrente e la storia approvata, rimuove current links; publication races escludono stale decisions.
- [ ] AC-C01.6: opinione non-fattuale, fatto non ancora verificato, prova insufficiente dopo controllo e unresolved hanno significati e campi distinti; nessun assessment della Persona.
- [ ] AC-C01.7: versioni legacy dei Dossier non vengono rietichettate con testo inventato; incompatibilità è esplicita e il periodo di doppia lettura ha una policy verificabile.

#### Validation / proof

Fixtures deterministiche: una posizione opinion-only senza Finding, un factual Statement con Finding, citazione critica, omonimia, quote revocata, rights expired, correction e replay. Schema/projection/API tests su record e referential integrity, negative private IDs, no score/intent. Future MiniPC isolated authorized source canary + new projection sha, API/static/readback e prova dell'assenza di leakage; acceptance dal consumer finale oltre alle suite.

#### Documentation, data, and migration impact

Definire Statement pubblico separato da Candidate/Atomic Claim/Finding in CONTEXT, PRODUCT e ARCHITECTURE; API/public schema versionate, expand→migrate→contract, version map e rollback; usare DP-430/434 senza duplicarne la semantica.

#### Completion receipt

Non implementato; pianificazione soltanto. In futuro registrare commit, migration+replay receipts, policy/review provenance, MiniPC authoritative accepted record, projected SHA, API and route readback, negativi e rollback.

### C-NEW-02 — Citazione originale pubblicabile, summary e traduzione separati

Status: FUTURE
Milestone: M3 — Editorial, correction, privacy, and legal policy, con consumer M4
Depends on: DP-216, DP-217, DP-220, DP-221, DP-222, DP-224, DP-305

#### Problem

Il metadata contract distingue SOURCE_OCCURRENCE/DERIVED_REPRESENTATION ma la proiezione corrente non emette i corpi esatti dei testi per il no-body profile DP-305. Le route usano normalized PARAPHRASE al posto della dichiarazione. La fonte autentica può comunque contenere errori di OCR/ASR; una citazione senza context e rights eligibility non è un oggetto pubblicabile.

#### Outcome

Rendere proiettabile un solo bounded original excerpt testualmente fedele e autorizzato, con source hash, binding, speaker e locator; eventuali summary e traduzione italiana sono elementi distinti, con label e derivation/version proof. Se originale non pubblicabile, la Statement non appare con parafrasi spacciata per parole pronunciate; la domanda concreta su diritti, fonte alternativa e contesto resta nella workflow privata A/B.

#### Traceability & constraints

R02, R03 e interfacce R04/R05/R06/R08, Q15–Q20; DP-216/217/220/221/224/305. Parole originali non sono universalmente prive di copyright: licenze, pubblico dominio verificato e limiti/eccezioni applicabili dipendono dal singolo uso, medium e source family. Nessun word-count safe harbor inventato.

#### Scope

Convalidare per ogni occurrence un typed public_original: bounded text, original language, text/source SHA-256, occurrence_id, source/version, immutable span/segment selectors (timed start/end o written char/paragraph), attribution review ref, contextual window/speech-act validity, quote rights decision/version/effectivity, omission markers e source direct-link. Resegmentation e whitespace policy sono versionate e non cambiano negazioni, numeri, modalità, nomi, date, legal states o punteggiatura significativa. Un estratto discontinuo include tutti gli span ordinati con visibile omission marker e prova di contiguous speaker/source boundaries. Summary possiede body/type/label/derivation, permission e source_ref separati; traduzione ha source_language, target_language, review/meaning assurance e original pointer. Consumatore JSON/HTML/API pubblica solo campi esplicitamente allowlisted.

#### Non-goals

Dump di full raw transcript/capture, invocazione live del provider per user request, traduzione attributiva, licenza autoapprovata, pubblicare un'opinione come fact verified, body di qualsiasi source acquisita, generare quote a partire da claim normalizzato.

#### Dependencies and sequencing

Hard DP preesistenti, C-NEW-01 per Statement entity; il prime aggancia i futuri ticket B su rights family e context+attribution e A per faithful source extraction, facendo attenzione al DAG. C-NEW-03 è consumer della nuova contract version. B rimane owner del gate legale/rights e speaker; questo ticket emette soltanto le rappresentazioni che abbiano superato quei gate.

#### Acceptance criteria

- [ ] AC-C02.1: original quote publishable da testo autentico scritto o media autentico coincide byte-per-byte secondo la dichiarata normalization policy con gli span di source immutable, hash e locator originali; niente editorial rewriting.
- [ ] AC-C02.2: ASR/OCR significant disagreement, perdita negazione/numeri/nomi/status legali, speaker change e alterazione di tempo/contesto sospendono la pubblicazione specifica; no paraphrase fallback.
- [ ] AC-C02.3: quote discontinue mostrano omissioni in testo, source spans e context/discontinuity proof; un montaggio o omissione che cambia significato fallisce.
- [ ] AC-C02.4: diritto UNKNOWN/EXPIRED/REVOKED/scope diverso dal medium o source occurrence non autorizzato → nessun original body pubblico e nessuna Statement apparentemente reale ricavata da summary.
- [ ] AC-C02.5: summary è solo secondary labelled narrative; traduzione non è verbatim, è identificata e linkata all'originale; una source tedesca resta in tedesco come citazione principale.
- [ ] AC-C02.6: body, lingua, hash, diritto e revoca sono coerenti tra schema/proiezione/API/search/HTML/JSON-LD/RDF; nessun full transcript, capture, private derived text o provider output in DOM/aria/OG/metadata.
- [ ] AC-C02.7: mutation di fonte, revoca quote rights o speaker/context reanalysis elimina stale quotation da ogni current artifact, lascia solo history pubblicamente autorizzata e registra fingerprint/versione.

#### Validation / proof

Reference snapshots: testo pubblico con selector ufficiale, audio con overlapping speaker, OCR con numero distorto, testo tedesco + translation, reported quote criticata, discontinuous excerpt, rights denied, quote tampering/replay e correggi/revoca. Compare exact text/hash/spans con accepted immutable source, rights authority receipt B e browser rendered content; future MiniPC isolated canary and simultaneous current artifact readback. Misurare false quotation/false attribution separatamente, non autovalutare con il generatore della quote.

#### Documentation, data, and migration impact

Additive versioned Public Wording schema body with bounded excerpt eligibility, summary and translation distinct; preserve metadata-only legacy and source hash lineage; privacy/retention and rights correction traces remain B. Non copiare source body wholesale in public schema. Niente runtime changes ora.

#### Completion receipt

Non implementato; pianificazione soltanto. Richiesti authority decision IDs, quote source/hash/span comparisons, positive/negative rights tests, MiniPC readback e rollback.

### C-NEW-03 — Migrazione coerente di pubblico, API, indice, markup e RDF

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-402, DP-403, DP-427, DP-431, DP-432

#### Problem

Anche ottenendo source quote e Statement nello schema, i consumers attuali ricostruiscono il loro universo da Dossier/Finding e stampano PARAPHRASE come headline/citazione. Pubblicare parzialmente cambierebbe il testo in una route ma lo lascerebbe sbagliato in ricerca, snippet, schema.org e Trace; la correzione non ritirerebbe necessariamente tutti i derivati.

#### Outcome

Tutti i lettori pubblici consumano lo stesso Statement versionato e approvato: frase esatta nella lingua originale quale quote primario, summary e traduzione soltanto se distinte e autorizzate, Finding opzionale; pagine, public API/OpenAPI, search JSON, HTML/JSON-LD, linked N-Triples/RDF, sitemaps e canonical links condividono identità e fingerprint e ritirano i contenuti revocati.

#### Traceability & constraints

R02/R03/R15/R16/R18/R19/R25/R36; Q15–Q20, DP-402/403/409/422/427/430/431/432/434. Nessun provider, live chatbot, public DB query o servizio search aggiuntivo nella request path. Un vecchio schema finding-only non diventa falsamente una Statement senza source proof.

#### Scope

Definire upgrade versionato PublicProjection/PublicAPI DTO e static index (kind statement; finding distinto e opzionale); enumerare tutti i consumers: pages Home, Explore, Statement, Person, Topic, Content, Trace, SourceRow/ClaimRow, search build/hydration, API/OpenAPI pagination, JSON-LD/OG/social, RDF/linked data, sitemap, robots, correction/reply and legacy redirects. Sostituire primary title/blockquote/text and terms con approved original quote; summary e traduzioni secondarie hanno label/lingua/source link. Preservation of stable statement ID e relation/version identifiers. Route Statement canonica e legacy mapping esplicito non duplicano semantiche. Integrare versione sha in build static/API/search/linked data e cleanup DP-431 per revoca transazionale e cache busting; enforce exact projection allowlist in text e accessibility tree.

#### Non-goals

Proporre nuovi rights grants, cambiare semantica relation in browser, pubblicare private source, scegliere visual design, nuovi provider, nuova search infra. C-NEW-02 governa la verità del testo, C-NEW-01 l'entità.

#### Dependencies and sequencing

Hard DP preesistenti; nuovi C-NEW-01 e C-NEW-02 hard una volta assegnati gli ID. DP-409, DP-422 e DP-429 consumano la migrazione, perciò vanno a valle o in soft coordination senza creare cicli. D è owner della promotion MiniPC/rollback. C gestisce compatibilità degli artifact pubblici e frontend.

#### Acceptance criteria

- [ ] AC-C03.1: ogni heading/quotation/lista/search/Trace/JSON-LD/OG pubblico stampa solo exact published original come testo della dichiarazione e non un normalized claim; un optional summary è nominato Summary, fuori dai quote roles.
- [ ] AC-C03.2: italiano tradotto non è quote attribuita se l'originale è tedesco/inglese; date/lang/version e locator sono coerenti su ogni route/API/structured data.
- [ ] AC-C03.3: Statement opinion-only con zero Finding appare come entità pubblica in Statement/Person/Topic/Content/search; niente fake factual assessment, required evidence path facoltativo per i non-fattuali ma provenance source imprescindibile.
- [ ] AC-C03.4: API version, OpenAPI, search index, HTML, JSON-LD/RDF/N-Triples, sitemap e redirects hanno ID, text hash, generated_at/version/fingerprint coerenti; cross-Version errors espliciti.
- [ ] AC-C03.5: private/held/retracted/rights revoked/invalid speaker/current version non emerge da route/metadata/cursor/index/count/hidden ARIA/search cache; invalid projection fails closed and no demo fallback.
- [ ] AC-C03.6: correction/retraction read model revoca simultaneamente artifacts current including search, canonical, sitemap, RDF, JSON-LD, API and caches; append-only approved history link mantiene l'originale solo se ancora lecitamente visibile.
- [ ] AC-C03.7: legacy URL redirects require exact ID mapping, 0 unreachable valid historic public links and 0 silent best-effort wrong Person; old clients get explicit version compatibility.
- [ ] AC-C03.8: two repeat builds of same approved projection have deterministic output bytes/hashes; render browser offline with zero provider calls.

#### Validation / proof

Source matrix: exact factual, quote in German with explicit IT translation, opinion no Finding, clipped quote, critique reported speech, disallowed rights, revoked source, approved correction/reply. For same SHA, inspect representative HTML/ARIA/JSON-LD/OG, API/OpenAPI, static index query, RDF N-Triples and sitemap; negative private text sentinel and stale cache. Run targeted Python+web source validators, real browser tests, clean clone and future pinned MiniPC authorized public projection and HTTPS readback. Release acceptance tied to C-NEW-01/02 and D.

#### Documentation, data, and migration impact

Update public schema/api/search artifact version, content types, RDF mapping, URL canonical and redirect contract, example fixtures explicitly fictional; expand→dual-read→contract only after consumer parity and rollback. Reuse existing DP-431 propagation instead of creating a duplicate retraction subsystem.

#### Completion receipt

Non implementato; pianificazione soltanto. Require source/rights provenance, frontend/API/search/RDF readback with immutable SHA, corrected/held negative proof, clean build and MiniPC rollback receipt.

### C-NEW-04 — Person pubblica autonoma, anche senza Statement

Status: FUTURE
Milestone: M1 — Domain and schema convergence, con acceptance reader M4
Depends on: DP-105, DP-222, DP-402

#### Problem

DP-405.3 descrive Person pubblicamente approvata ma ancora priva di record; la proiezione corrente e il client estraggono le Person solo da Dossier con Finding, quindi tale pagina non esiste. Una persona che esiste soltanto nel database privato deve invece continuare a essere indistinguibile da un identificativo ignoto.

#### Outcome

Una risorsa PublicPerson autonoma, con identity/publication review e stable public URI, che può avere zero PublicStatements e fornisce a DP-405 una cronologia effettiva quando ci sono registrazioni approvate; mantiene ruolo temporalmente valido, no score, no private roster leak.

#### Traceability & constraints

R16/R20/R25/R36, DP-105/222/405; il vecchio DONE DP-105 prova il person-derived-from-dossier model, non una persona approvata senza finding. Non pubblicare qualsiasi Person ricercata solo perché in DB o nominata in una fonte. Approved roles intervals non sono automaticamente biografia esaustiva.

#### Scope

Progetto di record PublicPerson con stable ID/slug, approved display name e identity disambiguator pubblico quando autorizzato, approved role intervals con source refs/valid_from/valid_to, public identity decision, version/status, privacy/sensitive policy refs, bounded profile scope e membership di statement IDs autonomi. Join dei PublicStatements solo dopo gate source/context/attribution; la cronologia deve distinguere emission_date vs pubblicazione/verified dates. La proiezione possiede un first-class people collection, mentre il vecchio algoritmo derivato da dossier è compatibilità v2 dichiarata. API/read/static pages/index consumano lo stesso set; zero-record approved Person produce empty state del record pubblico e link a Esplora/Metodo. Gli unknown, private, revoked e non-public Identity ID non appaiono e restituiscono uguale 404/generic unavailable.

#### Non-goals

Database di persone mondiali, scraping CV/biografia privata, score, immagini non approvate, verifica biometrica e person-level verdict; Topic membership è C-NEW-05 e non si deduce da nome nel testo.

#### Dependencies and sequencing

Hard DP-105/222/402 e C-NEW-01 dopo assegnazione del vero ID; B/A confermano speaker identity and approved time/context; D owns dataset release/caches. Soft DP-405/409/422 e DP-430 taxonomy; il nuovo schema deve essere predecessore del positivo AC-405.3 e non viceversa.

#### Acceptance criteria

- [ ] AC-C04.1: Person first-class approved ma con zero Statements produce route, API entry e approved empty state senza check/score/placeholder.
- [ ] AC-C04.2: unknown/private-only/held/revoked Person non compare né come search suggestion/facet/cursor/sitemap e restituisce stesso boundary osservabile di sconosciuta.
- [ ] AC-C04.3: Person con Statement e senza Finding è navigabile con fonte, original quote e data; claim-only/titolo fonte che cita il nome non ne fa un'affermazione della Persona.
- [ ] AC-C04.4: dated role label si applica solo agli intervalli approvati che coprono statement time e con provenance; gli intervalli assenti/contraddittori non generano ruolo corrente inferito.
- [ ] AC-C04.5: multilingua e due omonimi hanno stable IDs distinti; merge/split identity o role review revocato propaga ricostruzione e mantiene history solo quando pubblicabile.
- [ ] AC-C04.6: repeat build di una Person unchanged produce stesso fingerprint/route; private membership changes non incidono in modo osservabile sul set pubblico salvo nuova decisione pubblicata.

#### Validation / proof

Fixture matrix approved-zero, approved-one-opinion-no-Finding, multiple dated roles, two homonyms, one private-only/unknown collision, revocation, source quotation of person without endorsement; tests validator/API/search/static routes + no-private counts; MiniPC isolated readback approved zero Person vs unknown same response, real approved populated Person once eligible.

#### Documentation, data, and migration impact

Additive public people collection with approved-vs-private identity discriminant; update public projection/API OpenAPI compatibility, search generation and canonical Person route; no auto-exposing legacy private people. Existing DP-405.3 remains unchecked until runtime proof.

#### Completion receipt

Non implementato; pianificazione soltanto. Future schema replay, identity approval refs, public projection SHA, zero-record live Person and private/unknown negative evidence, rollback.

### C-NEW-05 — Filtri pubblici Persona × Tema e dati incrociati

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-105, DP-402, DP-430

#### Problem

La UI attuale ricerca per tipo oggetto e faccette, ma non risponde direttamente a «quali dichiarazioni pubbliche ha espresso Persona X sul Tema Y?». Gli attuali topic memberships sono basati su finding_ids e una menzione nel testo non basta a rappresentare una posizione su un tema; serve la proiezione Statement/topic autonomi e il filtro con intersection sicuro.

#### Outcome

Filtri pubblici separati e componibili Persona + Tema con URI condivisibile, dati di dichiarazioni originali datate e scope visibile, riuso dello static index/public projection; niente chatbot, interpretazione LLM al click, topic inferito, roster privato o person-level aggregate.

#### Traceability & constraints

R16/R18/R19/R20/R36, Q15–Q20, DP-405/406/409/429/430. Nome e label di Topic appartengono a public Topic identity reviewed; speaker approval e speech act/stance semantici appartengono ad A/B. Persona×Tema è intersezione di due filtri, non una nuova homepage orientata a profili politici.

#### Scope

Build-time materialization dell'indice di join pubblico: statement_id/version, public_person_id, public_topic_id, membership_decision_id, approved speech_act/stance_for_topic se espressamente disponibile, statement_date/source/locator, original quote ref, optional Finding ref. Una Statement può avere multipli Topic solo con membership approvate; caso di citazione critica può essere rilevante come discorso sul tema senza essere classificato come supporto: mostra context/role esatto, non dedurre adesione. API/static index possono includere indici invertiti limitati (person→IDs, topic→IDs) dalla **stessa** approved projection fingerprint; matching riproducibile, query URL ?persona=ID&tema=ID più sort/filter date/sources; no Personal-topic private existence hints. Explore ospita filters, e Person/Topic offrono deep links coerenti senza creare un nuovo motore server. Dataset freshness/coverage in intestazione.

#### Non-goals

Stance detector client, personalized recommendation, search semantica nuova, vector store, chatbot, person scoring, automatic approval di Topic, calcolo di truth dalle opinioni. Sintesi in testo è C-NEW-06.

#### Dependencies and sequencing

Hard DP-105/402/430 e i nuovi C-NEW-01/04/03 dopo real ID; B provides meaning preserving position/speech-act, A provides canonical sources. Attenzione al ciclo: DP-409 attualmente dipende DP-405..408 che probabilmente riceveranno C-NEW-05 come nuova dipendenza; per evitare ciclo, qui DP-409 è un consumer in soft coordination, NON un hard parent. Preferire un contratto join indipendente, applicato a valle dai consumer DP-405/406/409/429. Soft DP-410.

#### Acceptance criteria

- [ ] AC-C05.1: public Person P e Topic T approved con due Statements eligible → solo intersection (P,T) ordinata per data+stable ID, ciascun risultato originale, fonte, context e canonical URI; altri Person e Topic esclusi senza record leakage.
- [ ] AC-C05.2: statement opinion-only senza Finding compare; Finding non pubblicato non è requisito; cita/critica di altra persona non diventa automaticamente adesione di P.
- [ ] AC-C05.3: label simili e omonimi non si fondono; chiavi public IDs, non name/token matching; membership multiple only if authorized.
- [ ] AC-C05.4: filtro vuoto, no-match su un corpus populated, corpus totalmente senza Statement, index unavailable/stale e privately-held zero intersection hanno messaggi corretti e non rivelano private memberships/counts.
- [ ] AC-C05.5: URL, back/forward/reload, keyboard/VoiceOver mobile, focus e annunci result-count funzionano su 320/375/390/430 e 200% zoom, zero provider/network requests beyond public static artifacts.
- [ ] AC-C05.6: source/statement/topic/review revocation elimina membro dal join, API/static index/URL results convergono sulla nuova fingerprint, refresh/replay stable; un URL pre-revoca non rivela il vecchio private text.
- [ ] AC-C05.7: filtro/relevance/sort è record-level deterministico, senza score Person/partito o ranking politico, e mostra last snapshot/coverage ambito.

#### Validation / proof

Dataset fisico test con due omonimi, due Topic simili, statement opinion-only, un speaker quoting another, correction/revocation, no-match e zero-corpus. Assert exact intersection IDs, chronological tie-break, primary original/source fields, cache fingerprints, positive/negative rendered Page API/search. Future MiniPC approved public test with one actual Person×Topic intersection and evidence readback; size/latency budget DP-409 measured rather than adding infra.

#### Documentation, data, and migration impact

Version index materialization with join and membership provenance, URL filters/ARIA, static/API field specification, invalidation DP-431, compatibility of old search index. Do not add private Person roster or authorizations in public JSON. Prime resolves header DAG cycle note explicitly.

#### Completion receipt

Non implementato; pianificazione soltanto. Future SHA, intersection IDs + source anchors, responsive AT receipt, corrections replay and MiniPC proof.

### C-NEW-06 — Sintesi Persona × Tema precomputata e citata

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-224, DP-303, DP-431

#### Problem

Una lista di dichiarazioni non è sempre un riassunto utilizzabile, ma una sintesi generata senza confini potrebbe affermare cosa una persona «pensa veramente», trasformare citazioni storiche in endorsement, confondere epoche e omettere la copertura incompleta. Il brief approvato chiede testo sintetico **precomputato** e **citatamente collegato a originali**; non chatbot pubblico.

#### Outcome

Per ogni intersezione PublicPerson×PublicTopic approvata, una breve sintesi versione/corpus-bound con claim circoscritti e pointer per frase a specifiche PublicStatements originali, datate e pubblicabili, eventualmente raggruppati per periodo/contesto. Resta distinta dai verbatim e sparisce quando le fonti sono insufficienti o stale.

#### Traceability & constraints

R03/R16/R18/R19/R20/R24/R25, Q15–Q20, DP-224/303/431; la summary non è quoting text, non implica intenti, and does not convert nonfactual statements into factual verdicts. «Nelle dichiarazioni raccolte» non significa «in ogni occasione».

#### Scope

Input exclusively approved public intersection C-NEW-05 and public original Statement IDs from C-NEW-01/02 with context/stance from B. Persist versioned synthesis draft/review metadata: person_id, topic_id, synopsis_text, period/scope, source corpus snapshot fingerprint, generation rule/model or deterministic method and version, created_at, explicit coverage/freshness note, set of cited Statement/version IDs with exact source date/locator, confidence/unsupported coverage flags private. Cited propositions must be claim-bound to original sources with allowed public citation markers, no fabricated quotes or implicit endorsement. Precomputation as governed offline job after statement batch changes; request path returns artifact only, no provider call. Generate or abstain/omit using explicit measured evidence/quality gates; under sparse/heterogeneous material prefer source-linked list with no synthesis and clear limits. Cross-period changes require **reviewed** same-person longitudinal relation B, not a model inference from words.

#### Non-goals

Chatbot, personal preference or political profile, score/sentiment, auto-publication bypass, broad inferred worldview, conjectures about motive, generic media summary lacking source statement refs.

#### Dependencies and sequencing

Hard existing DP-224/303/431; add C-NEW-01/02/05 real IDs and B approved speech-act/relation contract once named. D background refresh budget, pipeline replay and owner restrictions; DP-429 only renders synthesis and C-NEW-05 owns filters. Avoid adding C-NEW-06 as a dependency of C-NEW-01/05 to prevent cycle.

#### Acceptance criteria

- [ ] AC-C06.1: every substantive public synthesis sentence has >=1 valid published Statement/version citation and provenance/date; source link opens exact original quote/locator, verified hash and speaker.
- [ ] AC-C06.2: original quote and summary are visually/semantically separate and translation not passed off as original; synopsis states collected-corpus limitation, snapshot date/version and language/scope coverage.
- [ ] AC-C06.3: two eras or contrary positions are described separately by dates and conditions; claim of same-person position change only if approved relation, different-person contrary views never become same-person change.
- [ ] AC-C06.4: historical reported/critical/ironic quote or insufficient context cannot populate «sostiene X»; no person ideology/reliability/intent inference.
- [ ] AC-C06.5: zero/sparse sources, mixed contexts, disputed identity, absence of positive evidence, stale source/rights or incomplete citations → synthesis withheld or qualified with specific unproven boundary; no hallucinated zero coverage as certainty.
- [ ] AC-C06.6: correction, reply, withdraw, source version or Topic membership change invalidates synthesis atomically and schedules bounded regeneration; stale public API/search/HTML cannot serve old cited claims, replay deterministic for pinned inputs/method.
- [ ] AC-C06.7: request path works with provider offline, no LLM call or hidden stochastic reranking; cost/latency/attempt receipts separate from query analytics.

#### Validation / proof

Gold corpus of several approved exact quotes with timestamps, quotation-of-another-person, two periods, cross-person discrepancy, deleted source and none/sparse case; manually/auditably established source-to-sentence entailment sample (not generated self-judge). Check every citation reference and hash, required qualifications, no inaccurate endorsement and absence of stale cached synthesis after revoke. Future MiniPC isolated precomputed readback + renderer acceptance, no live model on public request; B/D define authority/cost gate.

#### Documentation, data, and migration impact

New bounded immutable-ish materialized synthesis read model and version invalidation receipts; no separate vectorDB/chat frontend, reuse public static projection, DP-431 correction triggers and DP-224 citations. Data migrations additive and rollback to no-synthesis safe state.

#### Completion receipt

Non implementato; pianificazione soltanto. Future cited statement IDs + source hashes + snapshot/quality receipt, negative redaction/reanalysis check, corpus coverage note, MiniPC projection and route proof.

### C-NEW-07 — Brief e alternative comparabili del redesign, decisione owner

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-413, DP-423

#### Problem

Il sito pubblico ha una grammatica v4 storicamente implementata, con tre composizioni corrette il 10 ottobre e check locali/MiniPC su approved-empty, ma l'owner valuta ancora l'insieme troppo generico. La scelta visiva v4 dei DONE DP-411/424 è fatto storico, non approvazione della **nuova** richiesta di redesign completo. L'audit indipendente segnala gerarchie simili tra pagine, vuoto sotto fold su telefono, copy disallineato e un problema di overflow a 320px. Senza decisione esplicita si rischia una ripetizione cosmetica del design corrente.

#### Outcome

Consegnare brief e **almeno due alternative realmente divergenti** che risolvono gli stessi compiti/record/stati, con matrice comparativa e decisione formale del proprietario su una direzione o revisione ulteriore. Nessuna immagine o implementazione nel mandato corrente; i mockup/visuali sono un artefatto futuro dopo questa pianificazione.

#### Traceability & constraints

R35/R36, Q18/Q20, audit 2026-10-10 UX, DP-411/412/413/423/424/425; proprietà editoriale della dichiarazione originale, source path, statuses, finding optional e correction links non si possono togliere per estetica. Non scegliere il vincitore dal vecchio Done DP-424. Designer/operator review non sostituisce privacy/rights approval.

#### Scope

Una design brief con inventory reader jobs: 5-second current-public-state understanding; ricerca nel corpus zero e pieno; aprire un PublicStatement originale fino a source locator/context/summary/optional Finding; confrontare same-take cross-person e same-person nel tempo; esplorare Persona×Tema con sintesi; esaminare correction/reply. Ogni alternativa applica stessa terminologia/identici input public-safe e copre Home, Esplora, Statement, Person, Topic, Content, Trace, Method e utility, su mobile/desktop e la matrice empty/approved/populated/unavailable/held-safe. Territori candidati **da valutare**: Atlante delle parole, Biblioteca delle fonti, Linea del tempo leggibile, Indice radicale, senza dichiararne uno selezionato. Scrivere scelta/ADR finale a cura owner dopo confronti, con nuova token direction o preservazione ragionata, rischio di legacy CSS migration e condizioni di manutenzione. Assenza di immagini oppure uso di un asset corretto/licenziato; nessun volto ricostruito dall'AI.

#### Non-goals

Scegliere concept per delega, generare immagini oggi, copiare componenti/framework grandi o mockup-candidate come dati reali, creare chatbot/feeds/bookmarks, cambiare la pubblicazione e le politiche.

#### Dependencies and sequencing

Hard DP-413/423 per naming/brand context già approvato, C-NEW-01/02/03 come contratti **input di target**, non prerequisiti alla stesura del brief; il prime decide se hard o soft per l'ultima fase. Soft DP-410/412/425, DP-426/427/428 e audit UX. Owner è l'unico soggetto che decide la direzione visiva; registrare decision pending come EXTERNAL/PENDING-OWNER senza bloccare i ticket source/review indipendenti.

#### Acceptance criteria

- [ ] AC-C07.1: brief specifica tutti gli reader jobs in termini di domanda→dati autorizzati→azione→stato; include same screenshots input e no simulated publication, senza ridurre prodotto a una sola funzione.
- [ ] AC-C07.2: almeno due alternative differiscono concretamente per hierarchy/flow/composizione, non solo palette, font o radius, e usano le stesse identiche pubbliche quote/summary/source/optional Finding.
- [ ] AC-C07.3: per entrambe esistono comparabili **specifiche future** di Home/Esplora con corpus zero, una Statement/populated **fixture etichettata**, Persona×Tema, Content/Trace, desktop 1440 e mobile 390/320, con test del primo viewport; niente screenshot spacciato per live.
- [ ] AC-C07.4: ogni alternative ha outcome misurabili: comprensione entro primo viewport, tempo/click verso fonte, distinguibilità di stato, 320 reflow, 200% zoom, keyboard/AX, costi performance e source/rights evidence trace.
- [ ] AC-C07.5: criteri, pro/contro e decisione finale dell'owner sono registrati in ADR/spec con data e outcome; senza decisione C-NEW-08 resta solo pianificato, nessun token freeze.
- [ ] AC-C07.6: se il proprietario seleziona un concetto già vicino al v4 attuale, la decisione dimostra quale funzione/esperienza cambia, quale difetto misurato corregge e perché la modifica è sufficiente.

#### Validation / proof

Prima futura valutazione: screenshot/stati/viewport/source fingerprint allineati, verifica 5-second task con criteri concordati, matrice touch/keyboard/reader/contrast e 320/390/1440, quota di false promises (zero). Confronti fra almeno 2 alternative e schermate equivalenti, link verso la reale public schema version; design decision owner firmata per passaggio a C-NEW-08. Nessun mockup nel task documentale corrente.

#### Documentation, data, and migration impact

Nuovo ADR di direzione dopo decisione, append alla storia v4 senza riscrivere DP-411/424 DONE; aggiorna DESIGN/tokens *solo* a scelta avvenuta. Nessun DB/API in questo ticket; eventuali nuovi componenti si mappano alla grammatica DP-412/425 in C-NEW-08.

#### Completion receipt

Non implementato; pianificazione soltanto. Future brief, alternatives comparison, owner-decision signature, visual check receipts, current/proposed schema and final option.

### C-NEW-08 — Implementazione futura del redesign scelto e migrazione controllata

Status: FUTURE
Milestone: M4 — Public product, API, and hosting
Depends on: DP-425

#### Problem

Un brief e una direzione approvati restano inerti se l'attuale frontend continua ad avere altezza, gerarchie, stati e classi legacy non coerenti. La presenza di stili v4 e circa 3.000 righe legacy CSS è un debito verificabile, ma la rimozione indiscriminata rischia regressioni e va giustificata da consumer reali.

#### Outcome

Dopo **scelta owner C-NEW-07**, applicare la nuova grammatica nelle nove famiglie pubbliche con differenze visibili/operative misurate, riutilizzando componenti locali e garantendo source-first, exact original quote, summary/translation separati, optional Finding, corrected chronology, Story Person/Topic e Persona×Tema. Ogni pagina resta leggibile nel legittimo empty live e nei popolati approved records.

#### Traceability & constraints

R02/R03/R16/R20/R35/R36, DP-412/425 e page-owners DP-405..410/422/426..429. Il redesign è visual/reader architecture downstream delle scelte; privacy/rights non cambiano, nessun fake person/quote/media/verified badge. Un'immagine assente resta assente, non viene inventata.

#### Scope

Dal design owner-approved creare route-level migration map, tokens/type hierarchy/responsive density spec, compositi SourcePath/OriginalQuote/OptionalFinding/Summary/Translation/Chronology/IntersectionFilter/EmptyState, piano di progressiva sostituzione per classi duplicate legacy solo dove actual readers migrano, with deletion audit e bundle-budget control. Page owners implementano il layout specifico, DP-412/425 la shared grammar; questo ticket controlla convergenza e QA artefact, versioned prototypes/visual proofs e final routes. Mobile 320/375/390/430 prima-class; per 200% true browser zoom controllare 640 CSS rendered e non solo viewport emulation. Le pagine con corpus zero non usano finti timeline/placeholders/quote; i link disponibili si allineano a feature realmente servite sul MiniPC (account, Studio, API, footer).

#### Non-goals

Selezione owner, rewriting DB/public projection, importare un framework, generare foto non autorizzate, sostituire AT con check CSS, pubblicare fixture; il gate release appartiene a D/DP-702.

#### Dependencies and sequencing

Hard DP-425 come baseline riutilizzabile; **C-NEW-07 owner-selection è hard gate**, da aggiungere al Depends on solo dopo ID reale, come C-NEW-03/05 se un component dipende da nuovi public records. DP-412 può ricevere delta token ma non diventare dipendenza circolare; DP-405/406/407/408/429 sono page owners e non hard parent, con milestone QA DP-410 finale. Soft coord D MiniPC release, DP-422 routes e DP-401 hosting.

#### Acceptance criteria

- [ ] AC-C08.1: implementazione copia fedelmente **decisione owner** con checklist dei component contracts/tokens/page jobs; almeno un cambiamento di UX misurabile oltre alle differenze cromatiche, comparabile al baseline.
- [ ] AC-C08.2: Home/Esplora live empty mostrano stato vero e invito utile above fold a 320/390, non «modifica la ricerca» quando totale indice è zero; Metodo non satura il primo schermo con indice e Progetto non ha overflow.
- [ ] AC-C08.3: popolato approvato su Statement/Person/Topic/Content/Trace e filter Persona×Tema mantiene quote originale prioritario, fonte precisa, summary/translation separate, optional Finding, correction/version and no-intent rule.
- [ ] AC-C08.4: 320/375/390/430/768/1440, exact 200% zoom, VoiceOver desktop + mobile screen reader, contrast and keyboard focus/reading order, reduced motion/touch 44px pass documented QA; no horizontal scroll regressions.
- [ ] AC-C08.5: CSS/components removed only after route consumers migrate and screenshot/behavior diff confirms no break; no new large deps, measured JS/perf budgets DP-410, no fake external network calls.
- [ ] AC-C08.6: approved empty vs no-match/stale/private omitted are distinct where safe; navigation, canonical/meta/sitemap/search do not advertise non-existent account/intake, Studio or demo routes.
- [ ] AC-C08.7: clean clone QA, pinned MiniPC actual release-mirror readback and rollback artifact link compare same projection fingerprint across APIs/search/HTML; no fixture shipped public.

#### Validation / proof

Before/after screenshots with input provenance at each viewport for nine public families and empty/populated/partial/revoked states; real browser DOM and focus, AT human receipt, responsive pixel overflow, Lighthouse/lab perf and JavaScript bundles; test source/citation path and source rights during redesign; D MiniPC immutable release and authoritative HTTP/API/search readback. Defer aesthetic subjective final sign-off until owner choice and review.

#### Documentation, data, and migration impact

Update only chosen design tokens, style/semantic component contract, migration map, versioned docs/UX and route screenshots; preserve old DP-411/424/425 historically correct receipts. No schema/data migration in redesign, only consumer field changes governed by C-NEW-03.

#### Completion receipt

Non implementato; pianificazione soltanto. Future design decision, commit/visual/perf/AT checks, removed legacy diff, source unchanged proof, MiniPC public readback and rollback.

## DONE storici: preservare la prova, definire solo il delta richiesto

Questa matrice **non richiede** riaprire automaticamente un DONE: ogni precedente receipt resta valido per lo scopo accettato allora; il target nuovo si copre con C-NEW e i delta AC sui ticket non-DONE. Se un criterio DONE era già letteralmente falso nel contratto di allora, il prime lo rivaluta separatamente con prova, senza trasformare il nuovo requisito in una retroactive failure per convenienza. I ticket M1R/M2/M3 tecnici di A/B sono considerati qui solo come dipendenze della vista pubblica.

| Ticket DONE / historical asset | Contratto realmente riutilizzabile | Delta per nuovo target, owner e comportamento vietato |
|---|---|---|
| **DP-105** Public schema-v2, first Dossier | stable IDs, projection only, fail-closed public fields, versioning | **C-NEW-01/02/03/04** introduce Statement/Person first-class e quote body autorizzato; non fingere che il vecchio dossier derivato da Finding contenesse opinioni senza Finding. |
| **DP-104** relation publication policy | reviewed-only relation, no intent/lie inference e source/time scope | **B** aggiunge Person identity, same-take cross-person vs change same-person e nonfactual Statement support; **DP-408** consumer; non trasformare relation runtime opposite stance in factual false. |
| **DP-216/217/220/221/222/224** exact quote, transcript/speaker/context/wording/citation | source span/hash, transcription confidence, context checks, wording role separation, public identity and material citation assurance | **A/B** robust original/rights/context/licence, **C-NEW-02** bounded original read. DP-221 DONE significa metadata-only boundary, non prova quote pubblicate. |
| **DP-305** transcript/excerpt rights policy | no-body current profile e fail-closed for unlicensed material | **B** aggiornamento policy/rights source-family con qualified review dove dovuta, **C-NEW-02** consuma rights decision; il nuovo requisito non concede automaticamente riuso. |
| **DP-402/403** stable read-only API/OpenAPI | deterministic public resources, no writes, version/cursor/metadata, false-private negative | **C-NEW-03** schema/version per first-class Statement, approved Person even zero, quote/translation and RDF consistency; legacy Finding stays distinct. |
| **DP-411/413** visual exploration + IA v2 | criterio di visione storico, IA/template jobs già documentati | **C-NEW-07** re-evaluation from latest owner dissatisfaction; non rifare i ticket storici come se non fossero mai accettati. |
| **DP-423/424/425** brand/v4 selected design + component system | selected-v4 historical receipts, frozen references, focus/tokens, no-score primitives | **C-NEW-07** owner chooses redesign, **C-NEW-08** future new iteration; old design selection non decide new winner. |
| **DP-426** Home/shell v4 | reusable shell/navigation, empty state source, static path | **C-NEW-08** fixes first-viewport real zero-data messaging, nav links and false promises; **DP-410** QA. |
| **DP-427** Statement page v4 | canonical Statement route shell, source link, correction/reply, separate explicit «Formulazione normalizzata · paraphrase» label in actual Astro | Ticket title/outcome says «exact wording», receipt claims exact wording, but code h1 is dossier.claim and explicitly PARAPHRASE; **prime must reconcile literal historical AC** (possible mismatch) and link new **C-NEW-01/02/03**. Non mantenere check mark come prova di verbatim originale che codice non pubblica. |
| **DP-428** Method/utility | source-first trust copy and bounded method sections | **C-NEW-08** future ux + DP-410 accessibility, accurate descriptions of policy/current public corpus, links only to live pages. |
| **DP-430** public Topic first class | stable Topic identity, review events, multi-topic membership, hard privacy omission | **C-NEW-01/05** Statement membership anche senza Finding; old DP-430 finding_ids membership remains historical proof, no guessing from claim_type. |
| **DP-434** public Content first class | Content approved separately from Finding, zero-finding Content, rights-gated playable media, written/timed source metadata | **DP-407 + C-NEW-01/03** Content moments from independent Statement, no raw transcript and no fake player. |
| **DP-431** correction/retraction public propagation | suppress stale current artifacts, append-only allowed history, search/API/static+linked data path | **C-NEW-01/02/03/04/05/06** extend invalidation to statement body, quote rights, Person roster, Topic join and synthesis; preserve existing tested cleanup and concurrency negative probes. |
| **DP-432** trust provenance presentation | clear source/review and no-score disclosure | **C-NEW-02/03** quote source/hash/rights context as distinct entity, summary not source quote. |
| **Other DONE among 90** | Current receipts remain in their ticket history, unaffected without a demonstrated R02/03/15–20/35/36 seam | Prime should preserve status and mark «no Lane C delta» unless A/B/D reveal concrete invalidity; no mass reopen or editorial note pretending runtime change. |

## Requisito → proposta e ownership esterna precisa

| Requirement | Responsible proposed contract + consumer AC | Interfaccia con altre lane e qualified gate |
|---|---|---|
| R02 exact original quoted declaration | C-NEW-02 AC-C02.1–.4; C-NEW-03 AC-C03.1/.4, DP-405/407/408/409/422/429 deltas | **A** source immutable quote/locator; **B** rights/context/attribution authoritative decision. |
| R03 separate summary | C-NEW-02 AC-C02.5, C-NEW-03 AC-C03.1–.3, C-NEW-06 AC-C06.1/.2 | **B** meaning assurance for derived text; source original remains primary. |
| R15 published verification states | C-NEW-01 AC-C01.2/.6 and DP-407 C-DELTA-407-B | **B** verification authority and public state allowlist; private holds invisible. |
| R16 nonfactual Statement independent Finding | C-NEW-01 AC-C01.1–.3; C-NEW-03 AC-C03.3, C-NEW-05 AC-C05.2 | **B** speech act, nonfactual differentiation and machine review; **A** source identity. |
| R17 denial of prior utterance (consumer touch) | DP-408 C-DELTA-408-C, C-NEW-03 AC-C03.1 | **B** must distinguish denial truth vs prior quote authenticity vs truth of earlier claim; C renders separate public relations/claims. |
| R18 same-take / cross-person | DP-408 C-DELTA-408-A/.C, C-NEW-06 AC-C06.3 | **B** typed relation and scope policy, no inferred client relation. |
| R19 same Person temporal change | DP-408 C-DELTA-408-B, C-NEW-04 AC-C04.4/.5 and C-NEW-06 AC-C06.3 | **B** identity/time/stance comparability; **A** dated source chronology. |
| R20 Persona×Tema | C-NEW-05 AC-C05.1–.7 (join/filter), C-NEW-06 AC-C06.1–.7 (summary), DP-405/406/429 deltas | **B** endorsed source act/context; **D** precompute cost/refresh, **A** source coverage. |
| R24/R25 correction/private omission in C | C-NEW-01 AC-C01.4/.5, C-NEW-02 AC-C02.7, C-NEW-03 AC-C03.5/.6, C-NEW-06 AC-C06.6 | **B/D** concurrent revocation and cache/release authority; DP-431 reuse. |
| R35 redesign owner decision | C-NEW-07 AC-C07.1–.6, C-NEW-08 AC-C08.1/.3 | Owner chooses after comparative evidence; DP-411/424 prior selection retained historically. |
| R36 accessibility/live empty | DP-410 AC-410.1/.2 + C-DELTA-410, DP-429 C-DELTA, C-NEW-08 AC-C08.2/.4/.6 | **D** MiniPC runtime readback, no real AT pass fabricated. |

## Dependency order / concrete frontend acceptance campaign

**Fase 0:** A/B make source rights, attribution, semantic context, published-state vocabulary and publication authority specification concrete. C-NEW-01/02/04 specify versioned schema and migration without mutating code. C-NEW-07 can draft a design brief/contrast independently; **future choice by owner** is mandatory only before C-NEW-08 implementation. Preserve design-system historical receipts.

**Fase 1:** A produces authenticated written/timed source and safe exact locator; B reviews speaker, context, source-family use permission and factual/nonfactual statement authority under future migration gate. No direct public process from source intake.

**Fase 2:** first eligible exact Statement/quote and optional Finding → projection/API C-NEW-01/02 → C-NEW-03 all public readers → first approved public Person/Topic/Content memberships C-NEW-04/05 → C-NEW-06 precomputed cited synthesis → DP-405/406/407/408 reviewed relation and cross-person/same-person acceptance → DP-409/429 index/Explore → DP-422 route cutover/linked outputs → DP-421 decision only when DP-214/420 pilot real and GO/NO-GO justified. One complete MiniPC vertical including withdrawal **before** bulk.

**Fase 3:** one cross-surface DP-410 campaign gathers **distinct** AC receipts for DP-405/.6, 406/.6, 407/.7, 408/.5, 409/.8, 412/.5, 429/last AC; design change C-NEW-08 only if owner selected C-NEW-07. This is **one testing campaign**, not merging/replacing page tickets. D owns immutable release, actual linked static/API/readback and rollback, preserving source/domain gate authority.

**No cycle recommendation:** new contracts 01/02/04 → 03 → 05 → 06; 409 consumes 03/05 and 429 consumes 409/05, 405/406 consume 01/03/04/05, 422 consumes page routes, 410 measures downstream. Existing DP-409 currently hard-depends DP-405..408 while DP-405/406 new feature asks 05 and 05 would otherwise depend on 409. At integration, **keep DP-409 a soft dependency of C-NEW-05** and do not make consumer DP-409 hard-parent of 05. The prime must reconcile existing route dependency edges with real IDs and run cycle checker before writing PLAN. Avoid asserting DP-422 depends DP-410 and DP-410 depends DP-422 simultaneously; quality gate may be coordinated as terminal acceptance rather than DAG dependency. C-NEW-07 → C-NEW-08 after explicit owner selection, without joining a schema release cycle.

**Minimal authorized end-to-end acceptance corpus (later):** (1) genuine approved exact-source Statement in Italian with factual Finding, (2) source text in another language with original/labelled Italian translation and review provenance, (3) approved nonfactual opinion without Finding, (4) quoted opponent/irony that must **not** populate the speaker's endorsed position, (5) two different people with opposing stances, (6) one person with documented chronological changed stance with valid scope, (7) Source/Content with timed locator and separate written locator, (8) topic identity and membership distinct from free-text mention, (9) one legitimate approved-zero-record Person, (10) correction/revocation with same-origin frontend API/search/linked data current artifact no leak. Fixture data is explicitly fictional and **never** release acceptance; at least one real approved Statement, Topic, relation and Person route must be testable at MiniPC before declaring full public route family complete.

**Matrix UX future probes:** first viewport 320/390 shows actual archive state + honest next action; different messages for approved-global-zero, no-match in positive dataset, unavailable index, unauthorized/private omitted as generic unknown; keyboard from search→filter→result→quote→original source→history; focus restore and list announcements; VoiceOver on macOS and a mobile screen reader when available; reduced motion/true browser zoom 200%; contrast and tap 44px, DOM source order and live actual URL responses. Inspect rendered HTML and accessibility trees, not only CSS; preserve target 120 KiB gzip JS/route, LCP/CLS/performance acceptance measured and explain INP lab proxy vs field metric. Compare trace labels/source and test that original quote appears in all destinations but raw capture/transcript/model output appears nowhere.

**Current blockers explicitly owned elsewhere:** lawful rights for exact extracts (B/qualified policy); reviewer machine authority migration (B); source authenticity/identity, official texts, foreign-language assurance (A/B); real approved statements/topics/relations (A/B + governed MiniPC); private/public synchronized revocation (B/D); live authorized release and acceptance readback (D); owner redesign selection (owner after C-NEW-07). No claim that these are solved by having written specs. Owner's visual checks cannot be substituted for textual verdict approval, and a missing human ordinary reviewer does not justify auto-approving existing gates.

## Pacchetto consegnabile

**Path unico worker:** tasks/prompt2prompt/20261010-231757-backlog-post-grilling/native-packets/C-public-product.md. Pending prime integration into canonicals: map temporary C-NEW IDs, resolve overlaps across lanes and planned new docs already being created, cross-check dependency DAG and avoid double ownership of public quote/schema/Statement/synthesis, propagate existing ticket AC deltas while preserving dated receipts and statuses. Le nuove AC sono tutte NON dimostrate; nessuna modifica applicativa, DB, browser, test, deployment o push è conseguenza di questo file. Il pacchetto è assorbibile e non deve restare un secondo backlog attivo dopo l'integrazione.
