# DP-440 — Sintesi Persona × Tema precomputata e citata

Status: FUTURE
Milestone: M4 — public product/API
Depends on: DP-224, DP-303, DP-431, DP-435, DP-439

## Problem

Una lista di dichiarazioni non è sempre un riassunto utilizzabile, ma una sintesi generata senza confini potrebbe affermare cosa una persona «pensa veramente», trasformare citazioni storiche in endorsement, confondere epoche e omettere la copertura incompleta. Il brief approvato chiede testo sintetico **precomputato** e **citatamente collegato a originali**; non chatbot pubblico.

## Outcome

Per ogni intersezione PublicPerson×PublicTopic approvata, una breve sintesi versione/corpus-bound con claim circoscritti e pointer per frase a specifiche PublicStatements originali, datate e pubblicabili, eventualmente raggruppati per periodo/contesto. Resta distinta dai verbatim e sparisce quando le fonti sono insufficienti o stale.

## Traceability & constraints

R03/R16/R18/R19/R20/R24/R25, Q15–Q20, DP-224/303/431; la summary non è quoting text, non implica intenti, and does not convert nonfactual statements into factual verdicts. «Nelle dichiarazioni raccolte» non significa «in ogni occasione».

## Scope

Input exclusively approved public intersection DP-439 and public original Statement IDs from DP-437/02 with context/stance from B. Persist versioned synthesis draft/review metadata: person_id, topic_id, synopsis_text, period/scope, source corpus snapshot fingerprint, generation rule/model or deterministic method and version, created_at, explicit coverage/freshness note, set of cited Statement/version IDs with exact source date/locator, confidence/unsupported coverage flags private. Cited propositions must be claim-bound to original sources with allowed public citation markers, no fabricated quotes or implicit endorsement. Precomputation as governed offline job after statement batch changes; request path returns artifact only, no provider call. Generate or abstain/omit using explicit measured evidence/quality gates; under sparse/heterogeneous material prefer source-linked list with no synthesis and clear limits. Cross-period changes require **reviewed** same-person longitudinal relation B, not a model inference from words.

## Non-goals

Chatbot, personal preference or political profile, score/sentiment, auto-publication bypass, broad inferred worldview, conjectures about motive, generic media summary lacking source statement refs.

## Dependencies and sequencing

Hard existing DP-224/303/431; add DP-437/02/05 real IDs and B approved speech-act/relation contract once named. D background refresh budget, pipeline replay and owner restrictions; DP-429 only renders synthesis and DP-439 owns filters. Avoid adding DP-440 as a dependency of DP-437/05 to prevent cycle.

## Acceptance criteria

- [ ] `AC-440.1`: every substantive public synthesis sentence has >=1 valid published Statement/version citation and provenance/date; source link opens exact original quote/locator, verified hash and speaker.
- [ ] `AC-440.2`: original quote and summary are visually/semantically separate and translation not passed off as original; synopsis states collected-corpus limitation, snapshot date/version and language/scope coverage.
- [ ] `AC-440.3`: two eras or contrary positions are described separately by dates and conditions; claim of same-person position change only if approved relation, different-person contrary views never become same-person change.
- [ ] `AC-440.4`: historical reported/critical/ironic quote or insufficient context cannot populate «sostiene X»; no person ideology/reliability/intent inference.
- [ ] `AC-440.5`: zero/sparse sources, mixed contexts, disputed identity, absence of positive evidence, stale source/rights or incomplete citations → synthesis withheld or qualified with specific unproven boundary; no hallucinated zero coverage as certainty.
- [ ] `AC-440.6`: correction, reply, withdraw, source version or Topic membership change invalidates synthesis atomically and schedules bounded regeneration; stale public API/search/HTML cannot serve old cited claims, replay deterministic for pinned inputs/method.
- [ ] `AC-440.7`: request path works with provider offline, no LLM call or hidden stochastic reranking; cost/latency/attempt receipts separate from query analytics.

## Validation / proof

Gold corpus of several approved exact quotes with timestamps, quotation-of-another-person, two periods, cross-person discrepancy, deleted source and none/sparse case; manually/auditably established source-to-sentence entailment sample (not generated self-judge). Check every citation reference and hash, required qualifications, no inaccurate endorsement and absence of stale cached synthesis after revoke. Future MiniPC isolated precomputed readback + renderer acceptance, no live model on public request; B/D define authority/cost gate.

## Documentation, data, and migration impact

New bounded immutable-ish materialized synthesis read model and version invalidation receipts; no separate vectorDB/chat frontend, reuse public static projection, DP-431 correction triggers and DP-224 citations. Data migrations additive and rollback to no-synthesis safe state.

## Completion receipt

Non implementato; pianificazione soltanto. Future cited statement IDs + source hashes + snapshot/quality receipt, negative redaction/reanalysis check, corpus coverage note, MiniPC projection and route proof.
