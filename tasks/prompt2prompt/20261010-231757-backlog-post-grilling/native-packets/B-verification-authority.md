# Lane B — verifica, autorità, contesto, diritti e correzioni

Status pacchetto: proposta documentale per integrazione seriale del coordinatore, **nessuna implementazione né nuova acceptance**.
Mandato: Task B del master prompt (righe 666–696), decisioni Q9–Q20, R04/R06–R08/R11–R19/R21–R25/R39/R41; confini C e D esplicitati sotto. Repository letto su `main` il 2026-10-10; nessuna mutazione runtime, provider o DB. Le chiavi `B-NEW-##` e `AC-B-NEW-##.N` sono temporanee: solo il prime assegna ID DP e aggiorna ticket, PLAN, canonici e commit.

## Decisioni vincolanti da assorbire

1. L'unità pubblica è uno **Statement attribuito alle parole originali**, con una o più proposizioni fattuali verificabili *eventuali*. Dire/fare una citazione, riportare un'accusa, negare, criticare, simulare o esprimere un'opinione sono atti distinti. La traduzione italiana è derivazione visibile, non testo pronunciato nella lingua italiana; parafrasi soltanto nel campo separato `summary`. La decisione sull'esposizione di Statement/schema/superfici è di C, l'interpretazione semantica e le proof conditions sono di B.
2. Un controllo fattuale può terminare `SUPPORTED`, `FACTUALLY_FALSE`, `INSUFFICIENT_EVIDENCE`, `UNRESOLVED` o altro stato canonico opportunamente mappato: **check completato con prove insufficienti ≠ controllo mai tentato**. Opinioni, previsioni, citazioni riportate e prese di posizione non diventano `FACTUALLY_FALSE` perché discordano o perché non è disponibile un Finding.
3. Il target è ricerca, attribuzione, verifica, stesura e futura eligibility per risultato **automatizzate**, anche sui documenti processuali. `DP-309/310/311` sono gate runtime reali già DONE per il precedente contratto e vanno migrati con prova e policy/ADR/versione; non convertirli nominalmente in due approvazioni umane fittizie di agenti. Un eventuale signoff qualificato di diritti/privacy/legale (`DP-307`) non si autoapprova e resta diverso dalla machine verification.
4. Parole esatte e base giuridica di riuso sono condizioni indipendenti. Nessuna licenza implicita perché il parlante è morto o l'URL è pubblico; nessun limite generico di 5/20/100 parole, nessuna parafrasi usata come dichiarazione se non si possono pubblicare le parole originali. Source-family license, eccezione/uso qualificato, attribuzione, trascrizione/traduzione/edizione, foto/media/embed hanno basi e ambiti separati.
5. Indagine attiva e limitata dei casi dubbi prima della coda: tentativi eterogenei deduplicati, passaggio all'originale, versione completa, metadata/archivio, seconda trascrizione, record primario, fonte realmente indipendente, tempi e limiti; il risultato negativo conserva coverage e causa dell'incertezza. La coda non è una finta produzione umana senza owner.
6. Mai dedurre dolo, menzogna intenzionale o falsità di una proposizione solo da negazioni, contraddizioni o variazioni nel tempo. Persona×Tema e cross-person possono mostrare posizioni documentate; `POSITION_CHANGE` vale soltanto per la **stessa persona** e uno scope confrontabile. Il rifiuto di attribuzione/interpretazione o verifica non autorizza pubblicazione, e non autorizza inventare dati dimostrativi.

## Baseline tecnica e prove da conservare

| Seam/ticket già esistente | Stato/prova consolidati e limite per il nuovo target |
|---|---|
| `DP-104` DONE; `relation_runtime.py`, `relation_policy.py` | Relazioni reviewate, nessuna inferenza di intento. `StructuredClaimRelationInput` ha claim/date/proposition/topic/stance/scope ma **non ha `person_id`**: posizioni opposte tra persone possono essere scambiate per `POSITION_CHANGE_CANDIDATE`. `RelationPublicationInput.both_claims_have_published_finding` esclude Statement di opinione. Follow-up B-NEW-07 e C pubblico; non annullare vecchie prove. |
| `DP-110/111/117` DONE | Inferenze motivate private, provenienza testuale, promozione candidate→claim già esistenti. `DP-117` ha correzioni 2026-10-10 a latest approval, distinzione duplicate extraction/same proposition e receipt replay: nuova machine authority e semantic statement non devono aggirarle. |
| `DP-216..222` DONE | Exact quote/span, tier ASR, copertura speaker, nested quotations, clipping/context, tipi `ORIGINAL/PARAPHRASE/SUMMARY/TRANSLATION`, omonimia/prova identità. È proof del contratto **precedente**, non di speech-act multilingue pieno o del verbatim pubblico target. `context_integrity.py` usa regex/finestre italiane e `window_radius=240` con limiti 32–2000: segnale, non autorità semantica universale. `wording_contract.py` ha regole mirate it/en/fr/es, non copertura universale/tedesco. |
| `DP-223` DONE | Suite di false-attribution con casi adversarial e MiniPC proven, AC-223 originali chiusi; target semantic/false-verdict reali richiede gold **nuovo** B-NEW-10 e D release. Non asserire che 51/59 fixture o 5/5 benchmark sintetici misurino recall/veridicità nel mondo. |
| `DP-224..228` DONE | Citation/material assertions, resolver dell'originale, verifiche numeriche composte, effective-time/supersession, bounded research plan compiler e source-role/requirements. Riutilizzare anziché creare una pipeline parallela. `verification_runtime.verify()` attualmente gestisce `numeric_exact/range/delta/ratio/percent_change`, `historical_minimum/peak`, `legal_status_exact/text_exact`; **non è verificatore fattuale generalista**. |
| `DP-302/303` DONE | Right-of-reply/correction/takedown/appeal privati append-only, retry e canary MiniPC del vecchio contratto. Nessun rilascio legale implicito, né prova di propagazione immediata con concorrente revoke. |
| `DP-305` DONE | `rights_registry.py`, policy excerpt no-body, complaint→hold bridge, expiry/cleanup canary e AC-305.1–.8 tecnici chiusi; source-specific qualified rights reali ancora da acquisire. Il nuovo requisito di **verbatim pubblico** amplia il vecchio scopo, senza falsificare DONE. |
| `DP-306` DONE strutturale; `DP-307` FUTURE | Register `Q-306-01..16` esiste, nessuna disposizione qualificata: 14 OPEN e 2 BLOCKED nel checkpoint; nessun legal release. `DP-307` AC-307.1–.9 sono tutti aperti. |
| `DP-308/309/310/311` DONE | Publication safety, high-risk/legal classification, review separation e identity authority off-DB con receipt/replay/attestation; gate attuale richiede reviewer umano anche in `high_risk_assertion.py`. Prove esistenti restano valide; target machine migration separata B-NEW-05, con transizione controllata e readback MiniPC futuro. |
| `DP-431`, `DP-510`, `DP-511` DONE | Correzione verso proiezioni, emergency hold/provenance quarantine, watch source drift/supersession. Regen elimina stale; non prova latency bounded across live HTML/API/CDN/search/cache/sitemap durante una revoca concorrente. B-NEW-09 + D release fence necessari. |
| `DP-229` IN PROGRESS | Pure countercase v2 ed inventario live v2 private read-only; numerose prove PostgreSQL e MiniPC sintetiche nel receipt. `evaluate_publication_eligibility` **rifiuta** readiness/waiver caller-supplied; mancano source-set current authority, ricerca conclusa, incorporation e review/waiver attestate. AC-229.8 (high-risk integration, scritto come ottavo checkbox) aperto. |
| `DP-418` IN PROGRESS | Studio persisted match-read, readiness/blockers e handoff privato metadata-only, latest event, duplicate-vs-same-proposition; quattro AC-418.1–.4 **ancora aperti**. `currentness=UNVERIFIED`, `review_authority=false`, `publication_authority=false`; nessun vero UI decision/replay/keyboard acceptance. |
| `DP-301` IN PROGRESS | AC-301.1–.7 tecnici chiusi e no-intent enforce; AC-301.8 ancora dipende da decisioni Q-306/DP-307. No lie/person ranking. |
| `DP-304` IN PROGRESS | AC-304.2–.8 macchina chiusi; AC-304.1 campo/purpose/retention/privacy end-to-end e qualifiche aperti. Inventario locale e MiniPC 100 tabelle/1248 colonne con 0 unclassified **per lo scope censito** e log campionati, non prova di payload JSON dinamici/provider logs/off-host o lawful purpose. |

Nota prove: il prompt master data altri checkpoint live (API/proiezione vuote, zero Capture/Passage/Candidate produttivi) e il vecchio canary AKN/DVNS; non promuoverli a campione fattuale o rights grant. Le prove dei DONE vanno lasciate intatte, segnando nuovi delta con ticket propri.

## Disposizione dei cinque ticket primari (integrazione a cura del prime)

### DP-229 — challenger durevole (R12/R13/R14/R23/R39)

**Vecchio scope/AC preservati.** Packet `countercase-v2`, material inventory `challenger-material-inventory-v2`; primi sette checkbox AC di pure policy e il nono benchmark sono spuntati nel ticket. Ottavo checkbox high-risk integration rimane aperto, e il ticket ha receipt datati 5–10 ottobre, incluso fixing retry review-evidence e impossibilità di autorizzare runtime tramite `READY` in memoria. **Stato proposto: IN PROGRESS**.

**Delta in DP-229:** definire authority del selettore di tutto il materiale challenger corrente (APPROVED/REJECTED/PENDING/CONTEXT/UPDATE; provenance, policy, material sequence), chiusura verificabile delle assignment DP-228 e degli exhaustion/coverage states, hash canonico per-evidence di versione+valutazione+independence, exact incorporation target in `verification_run`/Finding con review/attestation **indipendente dal chiamante**, waiver giuridico legato a decisione qualificata e scopo; integrità e idempotenza su nuovo materiale, diritti mutati, rettifiche, evidence role e modifica model/policy. Aggiungere AC numerati successivi senza alterare checkbox precedenti: `AC-229.10` durable snapshot/currentness sotto transazione; `.11` completion and incorporation attested; `.12` positive/negative/replay + waiver missing; `.13` MiniPC real-source-authorized high-risk only after source/rights/qualified decision. Dipendenza hard da DP-228, DP-215, DP-309/310/311 e B-NEW-05 se machine path; coordinamento D per release. **Proof:** falsificare `READY`, waiver, JSON, review row e snapshot, inserire nuovo contro-materiale tra verifica e render, mostrare HOLD; pass controllato solo con authority corretta, nessun real source ora.

### DP-301 — policy senza intenzionalità (R15/R17/R18/R19/R21)

**AC storici** `.1–.7` PASS; `.8` aperto. Ticket/policy leggono la falsità solo come proposizione circoscritta, non intenzione. **Stato proposto: IN PROGRESS** fino a Q-306/DP-307, conservare receipt e Unicode-format bypass fix.

**Delta:** collegare esplicitamente B-NEW-01/04/07 e C statement, affinché la classificazione semantica di opinione, speech-act e negazione non produca mai intent label, implicit lie né PERSON score; `FACTUALLY_FALSE` riguarda il contenuto proposizionale/negazione documentale e relativo scope, non endorsement o stato mentale. Distinguere *non verificato*, *verificato con prove insufficienti*, *opinione/non fattuale*, *stato in esame*. Qualsiasi wording pubblico revisionato rimane subordinato al qualified decision. Aggiungere `AC-301.9` controllo negativo trasversale Statement/relationship/denial/parliamentary allegation/API/search; `.10` public copy e policy-version stale. Dipendenze hard da B-NEW-01/04/07 e C reader contract per nuovi AC; qualified external DP-307 resta blocker di lancio, non della progettazione.

### DP-304 — minimizzazione e scope sensibili (R21/R22/R24/R25)

**AC storici** `.2–.8` macchina PASS (entro perimetro ricevuto); `.1` aperto. Receipt 7–10 ottobre preservati: ledger rights/ingestion e access, inventory PostgreSQL/SQLite/allowlist/sistema locali e MiniPC, limiti nested JSON, log/provider e retention. **Stato proposto: IN PROGRESS**.

**Delta:** census dinamico per documenti legali/scansioni, transcript e QA payload, errori/headers/log esterni, public verbatim, traduzioni e copie/cache; minimizzazione per vittime/minori/terzi incidentali, nomi e fatti contenuti *nel documento* rispetto alla Persona oggetto; account/provider/off-host classificati. I contenuti processuali non sono esclusi in blocco: pubblicabile solo una proposizione/documentary statement le cui identità, giurisdizione, efficacia, role e rights abbiano proof sufficiente. Aggiungere `AC-304.9` fixture court document contiene innocenti/minori/terzi: derivazioni private isolate e public projection minimale; `.10` pubblicazione source-wording non trascina raw Capture/PII/log; `.11` policy purpose/retention/version readback di ogni famiglia effettiva e gate legal. Hard B-NEW-02/06/09 + C public schema, soft D deploy logs/caches. `DP-307` deve decidere lawful bases/rights, mai autore del dato.

### DP-307 — review qualificata, no self-approval (R08/R14/R21/R24)

**AC-307.1–.9** tutti aperti; receipt del NO-GO, 14 OPEN/2 BLOCKED nel registro al checkpoint. **Stato proposto: FUTURE (external gating in M3), activation BLOCKED**, non trasformarlo in DONE da un aggiornamento planning.

**Delta:** aggiungere questioni circoscritte al deployment target: licenza/diritto della citazione esatta per source family e versione (testo vs audio/trascrizione/edit/traduzione/embed), GDPR e reputazione nei procedimenti, automation/public-copy obblighi e notice, revoca/restriction e temporal public caches, criteri di pubblicazione **autonoma** per classe di rischio, ruolo del legal signoff rispetto alle decisioni model, informativo preview vs verified factual publication. Ogni decisione Q-306 ha scope/profile/country/source/use, reviewer qualified e owner, conditions, expiry/re-review trigger e `decision_ref`; nessuna delibera implicita in schema o macchina. Aggiungere `AC-307.10` matrix tutte le route/source families e autonomation profiles; `.11` invalidazione per rights/source/legal/model/policy revision prima del release; `.12` reviewer qualification + owner acceptance e public hold se assenti. External trigger per il counsel/owner esatto; coordinarsi con D DP-702/704 e B-NEW-05/06; eseguire il lavoro tecnico indipendente prima della firma, mai fingere la firma.

### DP-418 — Studio candidate review/currentness (R11/R14/R23)

**AC-418.1–.4** tutti aperti; note e receipt 8–10 ottobre preservati, `readiness` e spool read-only non sono approvazione. **Stato proposto: IN PROGRESS**.

**Delta:** l'interfaccia può restare una capacità eccezionale di operator research, non prerequisito editoriale manuale di ogni record. Completare source/passage/exact span + persona/speech act + normalized proposition e candidate class, `DUPLICATE_EXTRACTION` vs `SAME_PROPOSITION` vs `RELATED/UNCERTAIN`, feature/code/provenance senza score pubblico, blocker di rights/context/match identity currentness *prima* di ogni azione, durable idempotent decision/replay e anti-stale/revoke fence verso DP-117. Integrare B-NEW-05 machine-approved path con audit distinto da fake human review: `promotion_enabled` soltanto se actual current authority e policy permettono l'azione. Aggiungere `AC-418.5` machine path con attested decision/refusal e stesso blocker-guard del manual path; `.6` negative concurrent revoke/re-review; `.7` mismatch candidate/run/version model + keyboard 200%/MiniPC real authorized input. Hard DP-117/212/414 e B-NEW-05/09 per nuovi machine/race AC; soft A source/passage, C frontend. Non cancellare AC operatore esistenti senza decisione esplicita dell'owner.

## Nuovi ticket proposti — template completo

### B-NEW-01 — Speech act, contesto adattivo e fedeltà semantica multilingue

Status: FUTURE. Milestone: M2 (semantica privata) → M3 per policy. Depends on (hard, da assegnare come DP puri): DP-216, DP-217, DP-218, DP-219, DP-220, DP-221, DP-222. Soft: A original/passages e language coverage; C Statement/public original-translation contract.

**Problem.** Il clipping v1 segnala pattern italiani e usa finestra fissa, ma non dimostra che una frase attribuita esprima adesione della Persona. Reported speech, autore citato, imitazione, una negazione oltre finestra, ironia documentata, domande/risposte, tagli e versioni linguistiche possono invertire senso. Output private esistente può classificare testo senza l'atto di parola.

**Outcome.** Produrre una `SpeechActContextDecision` privata/versionata sullo specifico source occurrence che separa `utterer_id`, `quoted_author_id` se noto, `speaker_role`, `speech_act` (`ASSERTION`, `OPINION`, `QUESTION`, `REPORT`, `QUOTE`, `DENIAL`, `CRITIQUE`, `PERFORMANCE`, `UNKNOWN` e varianti con policy), stance `ENDORSE/DISTANCE/REFUTE/NON_COMMITTAL/UNKNOWN`, polarity/modal/temporal qualifications, context selector/hash, language, attribution/correction readiness e limitations. Qualunque inference non provata rimane `UNKNOWN`, senza dedurre intent.

**Traceability & constraints.** R04/R06/R07/R16/R21; Q15–Q18, owner example solo *ipotetico*, no biometric; original wording mai normalizzato in quotation. No second corpus/search stack.

**Scope.** Canonical captured span+surrounding scene/thread/precedent question+source chain → bounded context expansion by coherence/discontinuity rather than seconds/characters fixed → structured speech-act hypothesis with evidence spans/counter-signals → independently reproducible acceptance criteria per class and private event → eligibility decision for B verifier/C public Statement. `TRANSLATION` derived from immutable original and language pair with explicit negation/numbers/names/dates/modal/procedural term parity check; failure flags rather than guessed translation correctness. Store immutable context/source byte hashes and distinct approval authority. Reuse `context_integrity`, `wording_contract`, `source_span_review`, DP-219/222.

**Non-goals.** No invented transcript, no certainty from sarcasm model confidence, no speaker voiceprint, no universal language promise.

**Dependencies/sequencing.** Hard above; link B-NEW-02/04/07 consumers, C public projection. Real per-language calibration gold (B-NEW-10) before autonomy cutover; source rights separately B-NEW-06. Unknown language/mode is explicit capability gap and bounded attempt, not Italian-only fallback.

**Acceptance criteria.**
- [ ] AC-B-NEW-01.1 Direct assertion vs quotation/citation+critique vs recitation vs reporter claim produce different attributed speech acts and no false endorsement; authored by hand-checked, license-safe fixtures.
- [ ] AC-B-NEW-01.2 Negation, speaker-turn, question context, qualifier before/after and discontinuous montage materially change context fingerprint/readiness; omission fails closed, replay same bytes is idempotent.
- [ ] AC-B-NEW-01.3 Claim/Statement retains actual utterer distinct from quoted author/source; contradictory identity or unattributed fragment cannot publish as opinion/endorsement.
- [ ] AC-B-NEW-01.4 IT/DE + at least another observed source language fixtures check source words vs translation and preserve named entities, polarity, quantifiers, modal verbs, temporal and legal terms; unsupported pair = explicit pending/hold, not semantic pass.
- [ ] AC-B-NEW-01.5 Valid context from longer coherent scene may be accepted without arbitrary fixed seconds; deliberately cropped opposite-meaning scene fails; source and source-part boundaries retained.
- [ ] AC-B-NEW-01.6 Re-parse/retranslation/source revision stales dependent decision, Finding/relation/public summary; private tests+MiniPC authorized capture readback during implementation.

**Validation/proof.** Blind labeled contrast set (minimum adversarial categories above) with text, annotation provenance/source selector, expected outcome and negative controls; compare old/expanded bound results; show no assertion/endorsement leak in eventual C consumer. Actual thresholds calibrated through B-NEW-10, not fabricated here.

**Documentation, data, migration impact.** Additive `speech_act_context_decision`/serialized equivalent bound to Statement occurrence and revision (do not decide storage before inspecting stores). Preserve legacy `speech_mode` as v1 input, explicit version migration; no silent old approval carry-over. **Completion receipt:** non implementato; pianificazione soltanto.

### B-NEW-02 — Documento processuale: persone, ruoli, affermazioni e stati

Status: FUTURE. Milestone: M2/M3. Depends on (hard): DP-111, DP-215, DP-219, DP-222, DP-227, DP-304, DP-309; B-NEW-01. Soft A OCR/capture and documented source-family rights, C presentation of attributed documentary wording, D legal/release gates.

**Problem.** OCR ufficiale o PDF leggibile non trasforma un'accusa, una citazione testimoniale o una decisione non definitiva in fatto accertato. `high-risk-assertion-v1` distingue alcuni status, ma manca un'analisi generalista affidabile di ruoli, dispositivi e versioni in atti complessi. Bloccare per principio tutti i processi tradirebbe Q18.

**Outcome.** Contratto di extraction/interpretation documentaria verificabile che conserva *chi è autore dell'atto, chi viene citato, chi sostiene l'affermazione, quale organo e stato, quale fatto viene allegato o accertato*, con locatori/versione e limiti; produce candidate private sicure per Statement e verifica mirata.

**Traceability & constraints.** R21/R22/R12/R24 e Q18. Nessuna deduzione di colpevolezza da indagine; nessuna divulgazione incidentale di minori/vittime/terzi o status sensitive senza policy.

**Scope.** Document original+OCR confidence/page/layout/version/publication/effective dates/jurisdiction → signed/authenticity source-role/evidence requirement check → identified text span to `document_author`, `reporting_body`, `quoted_person`, `subject_person`, `procedural_party`, `status_at_date` (investigato/imputato/condannato/assolto/archiviato e definizioni locali con versione) → `ALLEGATION/TESTIMONY/FINDING_ORDER/DECISION_REASONING/INSTITUTIONAL_FACT/QUOTED_TEXT` typology → private candidate with exact source hash, quote location, qualified policy/privacy/rights gates. Later appeal/supersession invalidation via DP-227/511.

**Non-goals.** Non giudica fatti extratestuali perché compare una testimonianza, non sostituisce consulenza legale, non crea nuovi documenti processuali.

**Dependencies/sequencing.** B-NEW-01 first for reported speech; A source text/OCR before real pilot; B-NEW-03 for independent factual outcome, B-NEW-05 for machine eligibility, DP-307 for public legal decision. No one-person batch constraint.

**Acceptance criteria.**
- [ ] AC-B-NEW-02.1 Testo attribuito a testimone riportato da giudice e accusa di una parte mantengono autori/ruoli separati; nessun `FACTUALLY_FALSE/SUPPORTED` sui fatti sottostanti solo per mera citazione.
- [ ] AC-B-NEW-02.2 Confronti di status, giurisdizione, data-effetto, versione/impugnazione negano equivalenza errata (indagato ≠ imputato ≠ condannato; assolto ≠ archiviato).
- [ ] AC-B-NEW-02.3 Documento scansito con OCR errato in negazione/nome/data e omonimia è held, richiede confronto con originale/alternativa e conserva revisione.
- [ ] AC-B-NEW-02.4 Minori, vittime, terzi incidentali e dato sensibile vengono segregati/redatti, conservando citazione essenziale solo quando DP-304/307 e rights lo autorizzano.
- [ ] AC-B-NEW-02.5 Indipendenza: due siti che ripubblicano lo stesso atto formano una famiglia, non due conferme; versione aggiornata stales conclusioni con causale e replay.
- [ ] AC-B-NEW-02.6 Pilot futuro con almeno una fonte giudiziaria ufficiale realmente autorizzata attraversa original→passage→candidate→check→private/public conditional revalidation su MiniPC, includendo una negazione/allegazione; senza grant resta held.

**Validation/proof.** Test sintetici redatti come piccoli documenti con firme fittizie dichiarate, varianti e controtest, poi gold di documenti autentici con base di accesso/uso registrata; readback sui locator originali e output di ogni categoria. **Documentation, data, migration impact.** Nuovi role/act/status records/version links additivi solo se il domain model esistente non basta, retention/privacy audit e policy jurisdiction map. **Completion receipt:** non implementato; pianificazione soltanto.

### B-NEW-03 — Verificatore fattuale generalista per claim type e requirement profile

Status: FUTURE. Milestone: M2/M3. Depends on (hard): DP-215, DP-224, DP-226, DP-227, DP-228, DP-229 (per high risk); B-NEW-01. Soft A evidence acquisition/independence, B-NEW-10 calibration, C finding-copy, D quota.

**Problem.** `verification_runtime.verify` copre numeri, serie storiche e match testo/legal-status; proposizioni su eventi, sequenze, negazioni storiche e causalità circoscritta non sono trattate come classi fondate su evidenze con conclusioni autonomamente riproducibili. Un LLM che attribuisce un boolean non è una review.

**Outcome.** Un `VerificationRequirementProfile` versionato per classe di claim collega scope, validità temporale, evidence roles/independence, primary record e controprove a verifica autonoma e output strutturato, con no-check/insufficient/conflict/unsupported distinct e confidence/coverage solo interna calibrata.

**Traceability & constraints.** R12/R13/R15/R21/R23/R39; Q9, Q14, Q18. Factual check ≠ autenticità della citazione e ≠ publication approval. `OUTDATED_DATA` non è retroactive falsity; different opinion non è errore fattuale.

**Scope.** Claim type and adjudicable proposition/negation/time/location/jurisdiction -> select current DP-215 requirements -> bounded DP-228 research with primary/independent roles -> verify approved observations/contradictions and challenger material -> append-only decision with claims/evidence hashes, role, rule/model/prompt/requirement versions, source independence, cutoff and limits -> Finding candidate only if eligible, otherwise reasoned insufficiency/unknown. Distinguish `NOT_CHECKED` (no completed run), `CHECKED_INSUFFICIENT_EVIDENCE`, `UNRESOLVED_CONFLICT`, `NON_FACTUAL`, `CHECKABLE_PENDING`, `SUPPORTED`, `FACTUALLY_FALSE` mapping to canonical statuses without misrepresenting implemented enums. Deterministic computations remain the authority for exact arithmetic; model assists source interpretation with adversarial corroboration, not sole truth.

**Non-goals.** No universal verdict without evidence, no guarantee 100% across all domains, no person scoring or instant verdict on newly discovered sources.

**Dependencies/sequencing.** DP-215 roles and approved source-use prerequisite; B-NEW-02 process input; B-NEW-04 denial subtype; B-NEW-05 final machine authority; D budget/retry and C consumer. External primary material and qualified decisions block only relevant family/public outcome.

**Acceptance criteria.**
- [ ] AC-B-NEW-03.1 Claim-type registry includes class→required evidence roles, scope/time compatibility and conflict rules; unsupported class yields explicit `NOT_CHECKABLE_PROFILE_UNAVAILABLE` with no verdict.
- [ ] AC-B-NEW-03.2 Event/sequence, documentary legal status, factual denial, numeric and factual text comparisons use independent proof paths; original date cutoff honored; later outcome explicitly separate.
- [ ] AC-B-NEW-03.3 One secondary article or duplicated wire copies cannot satisfy two-family threshold; unapproved source, wrong jurisdiction/time, missing primary record or contradictory evidence cannot yield SUPPORTED/FALSE.
- [ ] AC-B-NEW-03.4 No retrieval attempt vs attempted-and-insufficient vs conflicting vs purely expressive stance produce distinct persisted reason codes and public-safe labels downstream.
- [ ] AC-B-NEW-03.5 Exact replay over same immutable inputs yields same outcome; changed evidence/rule/model/source/policy hashes stales approvals, schedules bounded reanalysis and never silently overwrites Finding history.
- [ ] AC-B-NEW-03.6 False verdict, false attribution and abstention are counted separately in B-NEW-10; high-risk case must pass attested challenger B-229 and machine authority B-NEW-05 before future MiniPC public candidate readback.

**Validation/proof.** Blind heterogeneous annotated claims with supporting/refuting/ambiguous variants, source family derivations, temporal changes; checker receipt includes source locator and exact approving evidence, withheld checks are measured as abstentions. MiniPC isolated integration then qualified real-source pilot. **Documentation, data, migration impact.** Versioned requirement/rule registry; expand existing verification ledger with optional fields or new narrow attested result, retain old numeric-v1 runs and API compatibility with explicit migration. **Completion receipt:** non implementato; pianificazione soltanto.

### B-NEW-04 — «Non ho mai detto X»: tre verifiche e relazione storica

Status: FUTURE. Milestone: M2/M3. Depends on (hard): DP-216, DP-219, DP-220, DP-222, DP-227; B-NEW-01, B-NEW-03. Soft C trace and separate public Statement/Finding; B-NEW-07 longitudinal graph.

**Problem.** Trovare stringa X non prova che Persona avesse sostenuto X; non trovarla in corpus incompleto non prova la negazione universale. `non l'ho detto`, `non l'ho sostenuto`, `non l'ho mai voluto dire` hanno diversi predicati e scope temporali.

**Outcome.** Pacchetto auditabile che decide separatamente autenticità delle parole precedenti, speech-act/endorsement precedente, semantica/scope della successiva negazione, factual status della negazione sull'insieme coperto e relazione storica; la verità della proposizione X resta un'altra verifica opzionale.

**Traceability & constraints.** R17/R18/R19/Q11; esempi precedenti ipotetici con persone reali **non** testimoni reali. Nessun dolo/menzogna intenzionale.

**Scope.** Two source occurrences + identities and context + `denial_predicate=UTTERED/ENDORSED/MEANT/OTHER` + quantifier `NEVER`, start/end, public/private scope and content identity -> evidence of one counterexample within claimed universal scope or explicit incompleteness -> denial verification and separate relation candidate provenance. One authenticated prior utterance refutes `NEVER_UTTERED` only if same speaker, exact/semantically matching assertion and stated scope. Prior ironic quote **does not** refute `NEVER_ENDORSED` absent endorsement proof.

**Non-goals.** No proving a universal negative from incomplete archives, no inference speaker intent, no checking X's external factual content as part of denial verdict.

**Dependencies/sequencing.** Context/identity before match; source completeness inventory from A/DP-215; C displays each of the three tracks separately. B-NEW-07 consumes relation only after cross-person/temporal validation.

**Acceptance criteria.**
- [ ] AC-B-NEW-04.1 Counterexample to exact universal `never uttered` within time/speaker/scope can refute denial, with approved original locator; altering speaker/scope/time yields hold.
- [ ] AC-B-NEW-04.2 Prior quoted criticism/re-enactment cannot refute `never endorsed`; original X's independent factual truth remains unchanged.
- [ ] AC-B-NEW-04.3 Partial archive absence yields `CHECKED_INSUFFICIENT_EVIDENCE` with coverage manifest and attempts, never `SUPPORTED` by absence.
- [ ] AC-B-NEW-04.4 Changed prior or later source, transcript correction or newly found context invalidates denial and related trace, not the immutable historical wording.
- [ ] AC-B-NEW-04.5 Replay/versioned result and public downstream show denial finding (if checkable), earlier Statement and longitudinal relation as separate linked objects; no intentionality language or wrong-person relation.

**Validation/proof.** Table of uttered/endorsed/meant, wrong person, quotation as criticism, universal scopes, incomplete corpus and corrected transcript; inspect exact evidence links and public omitted/private-held states on MiniPC future pilot. **Documentation, data, migration impact.** Add bounded typed denial target/quantifier/scope relation and lineage; preserve claim/projection v1 identifiers. **Completion receipt:** non implementato; pianificazione soltanto.

### B-NEW-05 — Machine verification authority, review migration e eligibility per risultato

Status: FUTURE. Milestone: M3. Depends on (hard): DP-308, DP-309, DP-310, DP-311, DP-229, DP-301, DP-304; B-NEW-03 and B-NEW-10. Soft D release/observer, C schema, A source authorization.

**Problem.** Attualmente HIGH/LEGAL richiede human_review/dual_control e per ogni classe publication replay attested reviewer. L'owner ha **zero editor testuali ordinari** e sceglie autonomia futura. Convertire `human_review_approved` in boolean machine, due bot names, o permettere `READY` caller-supplied invaliderebbe la sicurezza del DONE precedente.

**Outcome.** Un percorso *machine-authorized* versionato che distingue model generation, independent evidence gathering, challenge, verifier, bounded safety/privacy/rights/legal applicability, signing/persisted authority, final eligibility e publication trigger dopo acceptance; produce per record `ELIGIBLE`, `HOLD`, `NEEDS_EXTERNAL_DECISION`, `RECHECK` con prove riproducibili e conserva legacy review fino al cutover ufficiale.

**Traceability & constraints.** R11/R13/R14/R21/R25/R39; Q14/Q18. No routine text editor; **qualified counsel/owner decision** su source-family, policy e deployment non è machine approval. Nessuna auto-publication prima del rollout governato.

**Scope.** Versioned `MachineAuthorityProfile` per claim type/risk class/required evidence/challenger/gold gate/actor identity and key authority; immutable approved observation set, rule+model+prompt hashes, blind evidence independence, policy decision refs, rights, quote/source/context/person, challenger and correction state -> deterministic replay of attested machine decision in separate private ledger with signer, fencing token/sequence and exact record/material hash -> publication eligibility composed with DP-308/309/310/311 boundaries → future gated per-result trigger. Distinguish `machine_evidence_signoff`, `machine_verdict_signoff`, `eligibility`, `legal_owner_signoff`; two evaluations are *not* two human reviewers. Preserve audit of rejected alternative/support/counterevidence, no private leakage. Define migration policy ADR for replacing old human-only gate; dual-read old/new only when versioned profile explicitly authorized; no unreviewed legacy auto-upgrade.

**Non-goals.** No impersonated reviewers, magic confidence clearance, legal certification by model, privilege-bearing public accounts or arbitrary model prompt selecting release policy.

**Dependencies/sequencing.** Fase 0 policy/authority/schema and adjudication gold; fase 2 private full slice; fase 3 isolated MiniPC fence/canary and owner release acceptance in D; routine publication activation explicitly future. DP-307 independent external gate for affected public use and risk family.

**Acceptance criteria.**
- [ ] AC-B-NEW-05.1 No arbitrary model output, caller boolean, manual DB edit, forged signer/key/event ID or two responses from one model grants eligibility; missing exact off-DB authority or qualified decisions hold.
- [ ] AC-B-NEW-05.2 For each enabled claim/risk class, sealed machine receipt binds all load-bearing input versions, primary/independence set, completed challenger, procedure/rights/privacy, rule/model/prompt/policy and publication eligibility version.
- [ ] AC-B-NEW-05.3 Legacy human-path publication still behaves as proven until deliberate versioned cutover; after cutover old events cannot auto-authorize a new machine policy and vice versa. Replay/rollback prove holds on schema migration.
- [ ] AC-B-NEW-05.4 High-risk processual case with accepted jurisdictional/qualified policy, proper official source and no conflicting information can traverse autonomous pipeline in isolated acceptance; allegation-only, missing waiver, wrong identity, absent challenger or unresolved legal decision cannot.
- [ ] AC-B-NEW-05.5 Concurrent evidence update/rights revoke/correction/new challenger/corpus supersession invalidates readiness atomically at eligibility/write and publication read: no TOCTOU window accepted without formal fence B-NEW-09.
- [ ] AC-B-NEW-05.6 Versioned golden-reference and false-verdict/false-attribution/abstention gates and cost/health telemetry are satisfied on representative mixed claims before any feature flag eligible on MiniPC; absent gold remains NO-GO, no fabricated thresholds.
- [ ] AC-B-NEW-05.7 Release receipt records owner-authorized per-result activation scope; test source→public projection→correction/retraction readback and rollback at current MiniPC runtime; public reader never receives internal review/model/person scores.

**Validation/proof.** Red team direct SQL/status/signature replay, same-key reviews, participant correlation and shared evidence family; mixed automated procedural/legal, historical and numeric corpus; mandatory failure-mode table; actual MiniPC end-to-end rehearsal after policy/signoff. **Documentation, data, migration impact.** ADR explicitly superseding applicable human-only default in PRODUCT/AGENTS/ADR 0001 (prime owns), additive attestation/ledger or alternate existing authority reuse with verified signature sequence; external DP-307 register unchanged until duly decided. **Completion receipt:** non implementato; pianificazione soltanto.

### B-NEW-06 — Percorso lecito per citazione pubblica esatta per source family

Status: FUTURE. Milestone: M3 (rights contract), M2 first lawful pilot. Depends on (hard): DP-118, DP-216, DP-221, DP-305, DP-304, DP-306. Soft A source-family acquisition, C exact wording serializer, D release/privacy counsel `DP-307` external.

**Problem.** Il vecchio public boundary omette i corpi e può esporre PARAPHRASE; il nuovo prodotto richiede parole esatte. Non vi è licenza universale delle frasi e non è automatico che la licenza del *documento* autorizzi trascrizione, edizione/traduzione, screenshot o embed. `DP-305` previene violazioni sul contratto precedente ma non seleziona nuove lawful grants di repertorio.

**Outcome.** Versioned `PublicExactQuoteRightDecision` per `source_family + content/capture/version + permitted_public_use + representation_type + jurisdiction + effective_interval`, con owner/qualified decision refs, condizioni e scadenza; riusa diritti esistenti, alimenta una superficie pubblica di parole originali **solo** se binding semantico e rights sono correnti.

**Traceability & constraints.** R08/R02/R04/R24/Q15–Q16; riferimento CGUE *Infopaq* nel prompt come questione da considerare, non verdetto blanket. Nessuna parafrasi sostitutiva della dichiarazione. Verbatim conservato privatamente quando blocked, con tentativi concreti di fonte/permesso lecito e case reason.

**Scope.** Separare acquisition vs private storage vs quote display, text originally authored vs official transcript vs OCR/ASR vs editorial translation vs excerpt of creative document vs image/audio/film/embed; formalize exact original offsets/segment hash/coverage context + attribution obligation + source-license/exception/permission receipt + allowed length/necessity **solo** nei singoli decision scopes; read-time revocation/version revalidation to C projection; link complaint to DP-303/510 and D cache purge. Document research attempts to alternate primary licensed source if current one cannot authorize the exact quotation.

**Non-goals.** No universal word-count ceiling, no blanket public-domain from death, no published raw transcript; no agent-created legal opinion.

**Dependencies/sequencing.** DP-307 must accept relevant per-source legal basis for public activation, not for writing specs. Pilot source grant and rights version precede C public exact quote acceptance. A source accessibility cannot stand in for rights decision.

**Acceptance criteria.**
- [ ] AC-B-NEW-06.1 For same source/wording, one lawful approved use may allow a bounded exact quote while different representation (translation/footage/edition) stays held; grant never generalizes to neighboring source families.
- [ ] AC-B-NEW-06.2 Rights record binds exact immutable hash/locator/wording context and source terms; unknown, expired, withdrawn, conflicting, jurisdiction changed or revoked approval prevents all public quote-consuming surfaces.
- [ ] AC-B-NEW-06.3 Source-only metadata may appear if authorized, but original public declaration **is not** replaced with normalized/paraphrase; explicit private ineligibility + repair attempts recorded.
- [ ] AC-B-NEW-06.4 Translated Italian quotation is visibly translation, never source original; edition/copy/transcript source versions distinguish authority and verify meaning-sensitive terms.
- [ ] AC-B-NEW-06.5 Complaint/revocation fences all public caches/routes through B-NEW-09/D consumer and leaves append-only correction/public notice history without protected body leakage.
- [ ] AC-B-NEW-06.6 Authorized real source-family pilot demonstrates exact words on Statement, list, comparison, search, API, HTML/RDF/JSON-LD; unauthorised negative pilot omits them everywhere. MiniPC future readback and qualified register attached.

**Validation/proof.** Source-family matrix with underlying basis/version/approved use; positive licensed/approved synthetic fixture plus negative missing/expires; do not ingest protected media merely as QA. Legal evidence in controlled store, stable minimal refs in code. **Documentation, data, migration impact.** Add narrow rights-use/version mapping atop `rights_registry`, no broad replacement; public schema migration owned C, source ACL owned A, cache D. **Completion receipt:** non implementato; pianificazione soltanto.

### B-NEW-07 — Same-take e relazioni corrette tra e dentro le Persone

Status: FUTURE. Milestone: M2/M4. Depends on (hard): DP-104, DP-114, DP-219, DP-222, DP-227; B-NEW-01. Soft C trace/search/Persona×Tema; B-NEW-04 denial relation.

**Problem.** `relation_runtime` non ha `person_id`; stance opposte su stesso topic/proposition possono produrre position change anche fra persone distinte. `relation_policy` chiede due Finding pubblicati, impedendo confronto di opinioni in Statement non-fattuali.

**Outcome.** Versioned semantic relation classifier che usa identità, stessa proposizione/presa di posizione, speech act, polarità, tempo, luogo, condizioni e scope; distingue `CROSS_PERSON_AGREEMENT/DIVERGENCE` da `SAME_PERSON_POSITION_CHANGE/CLARIFICATION/CONTRADICTION_CANDIDATE` e permette **opinion Statement** senza Finding.

**Traceability & constraints.** R16/R18/R19; Q9–Q15. Contradizione non prova bugia, errore fattuale né intento, no score politico.

**Scope.** Inputs Statement IDs/person IDs+approved source/contexthashes, normalized proposition as *internal matching aid only*, stance polarity/modality, proposition object/entity/time/conditions/counterexample; relation candidate with rationale/conflicts, chronology/person cardinality and public eligibility on published Statement or Finding as appropriate. Review authority versioned/append-only; C graph/trace displays original quotes, corrected provenance and labels without false sameness.

**Non-goals.** No equivalence by keywords/topic or embedding score, no false opinion verdict, no ranking cross-person alignment.

**Dependencies/sequencing.** B-NEW-01 verified speech act, public Statement target from C; no hard dependency on public Finding for non-factual opinion. Link corrected/cancelled statement events from B-NEW-09; no need to create a chatbot.

**Acceptance criteria.**
- [ ] AC-B-NEW-07.1 Opposite stances by **different** persons same proposition/scope yield only cross-person divergence; same persons across times may yield position change if endorsement/scope supported.
- [ ] AC-B-NEW-07.2 Topic match, homonym, reported citation, conditional statement, different jurisdiction/period or question cannot generate an asserted same-take/contradiction.
- [ ] AC-B-NEW-07.3 Approved non-factual Statement A and B can appear in relation without any factual Finding; unverifiable opinion does not receive `FACTUALLY_FALSE`.
- [ ] AC-B-NEW-07.4 Explicit relation review/attestation, stable version/hash/identity and output privacy gating; new correction, source hash, person merge/split or context invalidates edge and read model.
- [ ] AC-B-NEW-07.5 Deterministic negative/positive fixture matrix and MiniPC public Persona/Topic/Trace readback with correct relation labels and original words after C implementation.

**Validation/proof.** Pair matrix same/different person, same/different scope, report/quote/endorse, non-factual, denial, corrections and cross-language match; inspect both store and C consumer. **Documentation, data, migration impact.** Existing relation schema may need additive subject/person-context bindings and upgraded relation policy instead of duplicate graph; preserve v1 edges under explicit compatibility/migration. **Completion receipt:** non implementato; pianificazione soltanto.

### B-NEW-08 — Indagine attiva dei casi dubbi con coda minima

Status: FUTURE. Milestone: M2. Depends on (hard): DP-213, DP-215, DP-225, DP-228. Soft A discovery/source resolver execution, D budget/cap/reset, B-NEW-03 verification, DP-418 exception view.

**Problem.** Mettere `PENDING` o `QUEUED_FOR_HUMAN_REVIEW` non risolve dubbi su originalità, speaker, quote, chronology, evidence. Niente review testuale umana ordinaria e nessun budget infinito; un'assenza di risultati da corpus incompleto non è una prova negativa.

**Outcome.** Per ogni blocker preciso, un `InvestigationAttemptLedger` privato e deduplicato pianifica/risolve ricerche ammesse per fonte, stop condition e budget e produce `RESOLVED`, `CHECKED_INSUFFICIENT`, `CONFLICT`, `EXHAUSTED`, `WAIT_EXTERNAL` + residual reason, escalation piccola/rapida solo se deve decidere un owner/qualified authority.

**Traceability & constraints.** R23/R12/R13/Q9/Q14, forte autonomia. Nessun provider switch/paid canary automatico fuori policy.

**Scope.** Typed question (speaker, original, date, rights, contextual speech, primary evidence, jurisdiction, version) → ordered plan using DP-228, DP-225, archive alternative, long-form scene, official metadata, captions/ASR alternatives where permitted → approved source/resolution and refusal receipts → dedup/version+attempt budget → terminal outcome, read-only Studio oversight and reopen signal on new source. Research success alone **non** grants review/rights/publication. Collapsing dependent source copies prevents false independent corroboration.

**Non-goals.** Endless scraping, collecting unauthorised corpora, empty queue success, blocking every case until owner edits every paragraph.

**Dependencies/sequencing.** Source access permits from A and measured cost/cap from D; negative unavailable authority gets external question to owner/legal with exact scope, no retry loop. Existing DP-228 research-plan compiler reused.

**Acceptance criteria.**
- [ ] AC-B-NEW-08.1 All actionable hold codes map to a concrete question, allowed source/attempt family, cap/time/stop reason; unresolved external legal authority never recast as completed factual check.
- [ ] AC-B-NEW-08.2 Replay of identical source and plan never repeats cost-bearing attempt; new relevant version can reopen one bounded attempt, old receipt preserved.
- [ ] AC-B-NEW-08.3 Failure after original/full-context/official/independent-source alternatives records coverage and `CHECKED_INSUFFICIENT` or `EXHAUSTED` distinct from `NOT_CHECKED`; never labels false by search absence.
- [ ] AC-B-NEW-08.4 Real closed case has source→hash→reason→downstream proof and leaves exception queue; genuine legal/visual/identity edge receives one limited owner task with evidence and no false reviewer availability.
- [ ] AC-B-NEW-08.5 Provider outage, cost cap, revoked rights and stale plan block new child tasks and mark resumable state; D ledger reconciles exact consumed work.

**Validation/proof.** Simulated retries, changed sources, sourced independently vs mirrors, budget exhaustion, qualified-owner blocking; future MiniPC replay receipts from real authorized sources. **Documentation, data, migration impact.** Append-only attempt/counter receipts referencing existing discovery/coverage source tables, no parallel scheduler. **Completion receipt:** non implementato; pianificazione soltanto.

### B-NEW-09 — Revoca e correzione transazionali fino all'ultimo lettore

Status: FUTURE. Milestone: M3/M5. Depends on (hard): DP-303, DP-308, DP-431, DP-510, DP-511, DP-117. Soft B-NEW-05 machine authority, B-NEW-06 rights, C public read model, D MiniPC/web/CDN deploy/rollback.

**Problem.** `private_candidate_commit_fence` non serializza tutte le revoche esterne; la regen public cleanup non prova assenza di stale version su build servita/search/API/cache e transaction races. Material update può arrivare fra last review, candidacy, artifact publish e URL read.

**Outcome.** `RevocationEpoch/PublicationFence` referenziato in tutti i write/promotion/projection steps per record e source lineage; revoca, complaint, rights expiry, new challenger, privacy hold, version correction e supersession invalidano tutte le approvals derivate, con ritiro pubblico verificabile entro bound operativo **misurato**.

**Traceability & constraints.** R24/R25, Q14/Q16, append-only history, no raw private exposure. Minimize destructive ops; tests isolated then no-live promotion until D cutover.

**Scope.** Per source/capture/passage/statement/candidate/claim/evidence/Finding/relation/public view map per-revision material hash + revocation state/epoch; transaction or advisory lock + compare-and-swap at commit/revalidation with durable outbox for invalidation; C projection and search artefact generation/read-time recheck; D cache/sitemap/live CDN purge/swap/host rollback, correction notice and reproducible previous version. Revocation has priority over auto-publish; fail closed under timeout/unknown ack.

**Non-goals.** Silent deletion of historical evidence/appeal, public leak of complaint body, assumption that static regeneration alone instantly clears caches.

**Dependencies/sequencing.** Requires B-NEW-05 for auto-approved records; can test old reviewer path independently. D owns release/ETAs/edge response, C owns public surfaces; B defines transaction authority and material dependencies.

**Acceptance criteria.**
- [ ] AC-B-NEW-09.1 Barrier races revoke vs Capture persist, Candidate, DP-117 promotion, evidence review, Finding, C generation and serving; after epoch increment no stale writer can create eligible public state.
- [ ] AC-B-NEW-09.2 Rights/relevance/reanalysis/reviewer reset and source version change invalidate all affected edges, latest public projection and stored approvals with reason ID, without erasing original lineage.
- [ ] AC-B-NEW-09.3 Bounded public data surfaces—HTML/JSON-LD/RDF/API/search/feeds/sitemap/linked card and cached served build—show authorized hold, omission or versioned correction after revocation; stale responses fail test; no hidden complaint/PII leak.
- [ ] AC-B-NEW-09.4 Exact repeat revoke and outbox retries idempotent; partition/crash/restart readback and rollback preserve hold; subsequent qualified restoration requires a fresh exact authority, not stale retry.
- [ ] AC-B-NEW-09.5 D MiniPC rehearsal logs measured end-to-end revocation latency with cache policy/projection version; threshold chosen by accepted risk/operational requirements before release, not fabricated by planning.

**Validation/proof.** Deterministic concurrent transactions with barriers on disposable PostgreSQL, frontend/edge simulated-cache stale fixture, isolated MiniPC fresh-source→publish→revocation→negative-readback, crash-restart/rollback. **Documentation, data, migration impact.** Additive epochs/queue/event link and component consumption contract; don't mutate existing DONE receipts. **Completion receipt:** non implementato; pianificazione soltanto.

### B-NEW-10 — Gold credibile e metriche indipendenti di errore, coverage e abstention

Status: FUTURE. Milestone: M2 private gold, M3 acceptance. Depends on (hard): DP-223, DP-226, DP-228, DP-229; B-NEW-01, B-NEW-03. Soft D release gates/provider budget, A source-family sample, C display regression.

**Problem.** Fixture deterministiche 5/5 e synthetic red-team provano regole, non la qualità autonoma su fonti reali multilingue, processuali e negazioni. Il medesimo model usato per generare una conclusione non può dichiararsi ground truth. Una accuracy che ignora le astensioni può mascherare pubblicazioni pericolose.

**Outcome.** Versioned `ReferenceCaseManifest` licito, rappresentativo e verificabile con etichette indipendenti, fonte originale locabile, adjudication/contestability, limiti di copertura e hold; metriche **separate** false-person, false-quote, false-endorsement, false-factual-verdict, false-denial, rights/privacy leak, unsupported publication, abstention, recall-by-claim/risk/language, latency/cost e drift.

**Traceability & constraints.** R39/R06/R13/R21/R34; zero reviewer testuale editoriale ordinario non equivale a nessuna verifica indipendente dei reference cases. Owner decide soglie release basate su costo del falso positivo e campione reale; non inventare gold, sample size o percentuali dai test correnti.

**Scope.** Stratificare lingua (IT/DE e lingue osservate), tipo di fonte (written/audio/OCR), factual vs opinion, quote/report/endorse, event/legal status/denial/numeric, primary vs derived, same-name, temporal supersession, ambiguous contested vs decidable. Le etichette verificabili si basano su documenti primari e annotatori/regole indipendenti dal sistema testato; doppia annotazione mirata in classi ad alto rischio o qualified decision reference, adjudication con livello di incertezza conservato. Corpus versione/bytes/license e split di calibration vs holdout, blind evaluation, no leakage tra famiglie e no approval from same generator. Casi senza verità esterna verificabile possono avere solo gold di *corretta astensione/attribuzione*; nessuna fabricated objective ground truth.

**Non-goals.** Nessuna promessa zero errori globali, no test attuale di provider a pagamento, no sample di contenuto inventato presentato come fonte reale.

**Dependencies/sequencing.** First create legal/allowed case manifest, lock test splits and adjudicator independence; machine-authority B-NEW-05 references accepted threshold profile, D checks release and cost, A covers real source families with proof. Routine model updates invalidate comparability/approval until retest.

**Acceptance criteria.**
- [ ] AC-B-NEW-10.1 Every reference case has immutable source/locator/hash/rights, independent label origin, source/adjudication confidence and ambiguity status; leaked test labels or generator self-judging cannot pass.
- [ ] AC-B-NEW-10.2 Metrics report numerators/denominators and confidence/coverage for false attribution, false verdict, false endorsement, false denial, abstention and conditional publishability separately, stratified by language/source/claim/risk; no hidden exclusions.
- [ ] AC-B-NEW-10.3 Adversarial tests with wrong name, cropped negation, ironic reported speech, duplicate independent-source illusion, processual allegation, changed jurisdiction/time, revoked rights and new later evidence refuse unsafe public labels.
- [ ] AC-B-NEW-10.4 Genuine supported/refuted factual positives, legitimate non-factual Statement and licensed exact quote remain usable under accepted profiles, avoiding trivial 100% abstention as success.
- [ ] AC-B-NEW-10.5 Thresholds, minimum sample confidence and observed operating envelope are owner-accepted **after** pilot calibration, versioned by feature/scope; unseen risk/language stays held if uncovered, not green by default.
- [ ] AC-B-NEW-10.6 Reproducible offline eval and MiniPC held-out end-to-end pilot output compare exact claims, public source, rights/review, cost and corrections; D release fails on negative gate, no provider trial before authorization.

**Validation/proof.** Signed/controlled ground-truth manifest, cases metadata (private where necessary), fixture licenses and reference adjudication evidence, confusion matrices per category and CI repeatability; no threshold asserted here. **Documentation, data, migration impact.** Extend existing `false_attribution_benchmark` and deterministic benchmark only when they can represent the new independent labels; separate gold dataset and case provenance from training/research inputs, no public sensitive corpus. **Completion receipt:** non implementato; pianificazione soltanto.

## Schema di interfaccia e responsabilità per C, D, A

| Boundary | Owner interfaccia | B consegna | Consumer/AC richiesto dall'altra lane |
|---|---|---|---|
| Original/capture/attribution | A | Necessary `source_occurrence`, `source_hash/version`, speaker/author/provenance/role, context/rights preconditions | A source/corpus extraction e grant autentici; niente invented written timestamp o source-family license. |
| Statement, Finding, relation, Persona×Tema | C | Speech-act/stance/polarity/context/denial result, nonfactual Statement `NOT_APPLICABLE` fact verdict, cited date/source, same-person flag; summary may be derivative | C proietta originale come declaration e translation/summary separati; opinioni/position senza Finding; cross-person non position change. |
| Rights exact quote → public schema | C con source family A, qualified `DP-307` | Per exact quote use/action/capture/span rights/version/expiry decision, revocation epoch, denial reasons | C mostra solo verbatim authorized; nessun fallback paraphrase nei quote fields/list/search e nessuna public raw capture. |
| Machine authority & dual control | D release; B policy/ledger | Explicit versioned replacement for current human reviewer chain, qualified owner/policy refs separate, no fake actor independence | D adotta solo dopo gold acceptance/rollback/cutover; `DP-309/310/311` legacy sempre fail closed fino alla migrazione. |
| Revoca/correction | B ledger; C public surfaces; D edge/runtime | Revocation epoch, material graph, append-only hold/correction, per-record invalidation and status | C all serializers/read model + caches; D actual serving/CDN invalidation, timing/readback and crash/rollback proof. |
| Gold/costi | B semantic eval; D release economics | False-attribution/verdict/abstention splits, case manifest and minimal sample/threshold calibration | D cost & cap per-stage, future model trials only after owner-approved profile; include held-out real authorized MiniPC acceptance. |

**Conflitti da risolvere nel prime (nessun edit ad altri packet):**

- `DP-309/310/311` hanno DONE e human-separation hard gate. Q14/Q18 scelgono machine target. Assorbire con un **nuovo ticket + ADR/cutover**, senza riaprire DONE né auto-approvare una macchina come reviewer umano. Le nuove machine credentials attestano integrità ma non sono fonti indipendenti.
- `DP-221/305` DONE dimostrano metadata/no-body; Q15 obbliga la citazione pubblica esatta: nuova rights-source-family decision B e schema/render C insieme. La policy privacy `DP-304` vieta raw transcript/capture pubblici, ma una citazione breve approvata richiede un nuovo campo `PUBLIC_EXACT_QUOTE` con allowlist/rights e nessun dump.
- `DP-104` DONE presuppone pubblicazione di due Finding e non conosce identity: B-NEW-07 cambia semantica, C deve rendere Statement/opinioni senza Finding. Non confondere «relazione su parole simili» con same-take o cambio di posizione.
- `DP-418` vuole review UI e action, mentre owner non ha revisori testuali ordinari. Fare UI eccezioni/review auditabile (AC precedenti preservati) e path machine autorizzato in B-NEW-05; non creare bottleneck umano comune.
- A `DP-215/225/228` gestiscono role/source resolution e tentativi. B-NEW-08 decide per domanda, esito, budget e evidence profile e riusa le loro assignment; niente secondo crawler.
- D possiede delivery/edge/caching e cost accounting: B-NEW-09 specifica authority e race; D deve validare ogni public surface e latency reale. `DP-431` DONE su regen non è prova dei contenuti ancora serviti da cache in presenza di revoca.
- `DP-307` resta un gate qualificato esterno: l'owner può scegliere un profilo informativo separato, ma nessuna source use/automated allegation/quote legale è DECIDED dal solo ticket. Non bloccare la scrittura degli altri ticket in attesa del counsel.

## Sequenza proposta al coordinatore e handoff

1. **Fase 0**: snapshot DAG e contratti per `SpeechActContextDecision`, Statement/Finding separation, requirement profiles, `MachineAuthorityProfile`, `PublicExactQuoteRightDecision`, revocation epoch. Aggiornare PRODUCT/CONTEXT/ARCHITECTURE via prime come target, ADR target macchina vs reviewer umano, precedenti receipts intatti.
2. **Fase 1 privata**: A source/Capture/Passage + B-NEW-01 contesto e B-NEW-08 ricerca dubbi; B-NEW-02 documenti quando source/OCR leciti. Id/quote/context prima di verifica; B-NEW-06 source-family rights per il primo verbatim.
3. **Fase 2 percorso completo**: B-NEW-03 factual claims, B-NEW-04 denial, B-NEW-07 relations, B-NEW-10 gold, C Statement verbatim/opinion/Persona×Tema; mostrare output leggibile su dataset vero autorizzato e limiti, non demo inventata.
4. **Fase 3 gate**: chiudere DP-229 durable reviewer + incorporation, B-NEW-05 machine approval, B-NEW-09 race-safe correction/revoke, qualified DP-307 per gli usi selezionati e D launch readiness/readback MiniPC. Poi D release owner-approved e metriche osservate.
5. **Fase 4+**: bulk storico permanente e refresh; B reanalysis quando cambiano versioni/scope/evidence/rights, gold drift e aggiornamenti source-family; no frozen corpus e no claim di copertura totale.

**Prove/check che deve programmare il prime nei ticket finali:** nessun test applicativo eseguito ora. Per ogni ticket runtime futuro: focused tests su positivo/negativo/replay/uncertainty, Python suite e deterministic benchmark, migrations idempotent + disposable PostgreSQL concurrency, `git diff --check`, candidate readback MiniPC autorizzato e consumer pubblico (incluse cache). Una suite verde solo su Mac non equivale ad acceptance MiniPC. Benchmark reali/gold devono sempre distinguere source entitlement e costo consumato. Alcuni gate richiedono qualified decision/rights/sorgenti reali ancora assenti: registrarli con artifact/campo/owner e HOLD esplicito, senza test fake pass.

**Inventario downstream sintetico per il prime:** 5 ticket B con status mantenuto, 10 proposte B-NEW da numerare, 28 DONE pertinenti riletti in sintesi, original AC dei primari preservati. Nessun vecchio ticket cancellato; nessuna autocorrezione runtime. Il pacchetto non sostituisce PLAN, canonical requirements matrix né i file individuali dei ticket: saranno prodotti e verificati solo dal prime.
