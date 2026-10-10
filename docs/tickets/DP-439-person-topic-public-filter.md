# DP-439 — Filtri pubblici Persona × Tema e dati incrociati

Status: FUTURE
Milestone: M4 — public product/API
Depends on: DP-105, DP-402, DP-430, DP-437, DP-438

## Problem

La UI attuale ricerca per tipo oggetto e faccette, ma non risponde direttamente a «quali dichiarazioni pubbliche ha espresso Persona X sul Tema Y?». Gli attuali topic memberships sono basati su finding_ids e una menzione nel testo non basta a rappresentare una posizione su un tema; serve la proiezione Statement/topic autonomi e il filtro con intersection sicuro.

## Outcome

Filtri pubblici separati e componibili Persona + Tema con URI condivisibile, dati di dichiarazioni originali datate e scope visibile, riuso dello static index/public projection; niente chatbot, interpretazione LLM al click, topic inferito, roster privato o person-level aggregate.

## Traceability & constraints

R16/R18/R19/R20/R36, Q15–Q20, DP-405/406/409/429/430. Nome e label di Topic appartengono a public Topic identity reviewed; speaker approval e speech act/stance semantici appartengono ad A/B. Persona×Tema è intersezione di due filtri, non una nuova homepage orientata a profili politici.

## Scope

Build-time materialization dell'indice di join pubblico: statement_id/version, public_person_id, public_topic_id, membership_decision_id, approved speech_act/stance_for_topic se espressamente disponibile, statement_date/source/locator, original quote ref, optional Finding ref. Una Statement può avere multipli Topic solo con membership approvate; caso di citazione critica può essere rilevante come discorso sul tema senza essere classificato come supporto: mostra context/role esatto, non dedurre adesione. API/static index possono includere indici invertiti limitati (person→IDs, topic→IDs) dalla **stessa** approved projection fingerprint; matching riproducibile, query URL ?persona=ID&tema=ID più sort/filter date/sources; no Personal-topic private existence hints. Explore ospita filters, e Person/Topic offrono deep links coerenti senza creare un nuovo motore server. Dataset freshness/coverage in intestazione.

## Non-goals

Stance detector client, personalized recommendation, search semantica nuova, vector store, chatbot, person scoring, automatic approval di Topic, calcolo di truth dalle opinioni. Sintesi in testo è DP-440.

## Dependencies and sequencing

Hard DP-105/402/430 e i nuovi DP-437/04/03 dopo real ID; B provides meaning preserving position/speech-act, A provides canonical sources. Attenzione al ciclo: DP-409 attualmente dipende DP-405..408 che probabilmente riceveranno DP-439 come nuova dipendenza; per evitare ciclo, qui DP-409 è un consumer in soft coordination, NON un hard parent. Preferire un contratto join indipendente, applicato a valle dai consumer DP-405/406/409/429. Soft DP-410.

## Acceptance criteria

- [ ] `AC-439.1`: public Person P e Topic T approved con due Statements eligible → solo intersection (P,T) ordinata per data+stable ID, ciascun risultato originale, fonte, context e canonical URI; altri Person e Topic esclusi senza record leakage.
- [ ] `AC-439.2`: statement opinion-only senza Finding compare; Finding non pubblicato non è requisito; cita/critica di altra persona non diventa automaticamente adesione di P.
- [ ] `AC-439.3`: label simili e omonimi non si fondono; chiavi public IDs, non name/token matching; membership multiple only if authorized.
- [ ] `AC-439.4`: filtro vuoto, no-match su un corpus populated, corpus totalmente senza Statement, index unavailable/stale e privately-held zero intersection hanno messaggi corretti e non rivelano private memberships/counts.
- [ ] `AC-439.5`: URL, back/forward/reload, keyboard/VoiceOver mobile, focus e annunci result-count funzionano su 320/375/390/430 e 200% zoom, zero provider/network requests beyond public static artifacts.
- [ ] `AC-439.6`: source/statement/topic/review revocation elimina membro dal join, API/static index/URL results convergono sulla nuova fingerprint, refresh/replay stable; un URL pre-revoca non rivela il vecchio private text.
- [ ] `AC-439.7`: filtro/relevance/sort è record-level deterministico, senza score Person/partito o ranking politico, e mostra last snapshot/coverage ambito.

## Validation / proof

Dataset fisico test con due omonimi, due Topic simili, statement opinion-only, un speaker quoting another, correction/revocation, no-match e zero-corpus. Assert exact intersection IDs, chronological tie-break, primary original/source fields, cache fingerprints, positive/negative rendered Page API/search. Future MiniPC approved public test with one actual Person×Topic intersection and evidence readback; size/latency budget DP-409 measured rather than adding infra.

## Documentation, data, and migration impact

Version index materialization with join and membership provenance, URL filters/ARIA, static/API field specification, invalidation DP-431, compatibility of old search index. Do not add private Person roster or authorizations in public JSON. Prime resolves header DAG cycle note explicitly.

## Completion receipt

Non implementato; pianificazione soltanto. Future SHA, intersection IDs + source anchors, responsive AT receipt, corrections replay and MiniPC proof.

### 2026-10-11 — v2 public-index intersection slice (partial, local)

Code landed in `df6fa42` and `5c72563`. `web/src/lib/searchIndex.ts` now carries approved public-v2 Finding→Person and reviewed Topic-finding membership as bounded facet IDs; source rows absent from the verified public projection are not synthesized into results. The Explore dialog filters Person and Topic together with URL restoration, and `check-search-index.mjs` covers positive intersection, unrelated public Person, private/absent membership, malformed URLs and an invented public Topic facet even with recomputed index hash. `npm run check:search`, `npm run check` (0 diagnostics), design check and isolated projection-boundary check passed locally. Search remains browser-only with no per-request LLM.

**Scope limit:** v2 Finding membership is not the new first-class exact-wording PublicStatement membership: DP-435–438 and the additional typed public projection/reader upgrade still precede full AC-439.1/.2/.6. No approved real Person×Topic MiniPC runtime sample, original quote, precomputed synopsis, mobile screen-reader or revoked-v3 release readback is claimed. **All AC-439.1–.7 remain unchecked; status FUTURE until contract migration and runtime proof.**
