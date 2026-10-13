# DP-312 — Speech act, contesto adattivo e fedeltà semantica multilingue

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-216, DP-217, DP-218, DP-219, DP-220, DP-222

## Problem
 Il clipping v1 segnala pattern italiani e usa finestra fissa, ma non dimostra che una frase attribuita esprima adesione della Persona. Reported speech, autore citato, imitazione, una negazione oltre finestra, ironia documentata, domande/risposte, tagli e versioni linguistiche possono invertire senso. Output private esistente può classificare testo senza l'atto di parola.

## Outcome
 Produrre una `SpeechActContextDecision` privata/versionata sullo specifico source occurrence che separa `utterer_id`, `quoted_author_id` se noto, `speaker_role`, `speech_act` (`ASSERTION`, `OPINION`, `QUESTION`, `REPORT`, `QUOTE`, `DENIAL`, `CRITIQUE`, `PERFORMANCE`, `UNKNOWN` e varianti con policy), stance `ENDORSE/DISTANCE/REFUTE/NON_COMMITTAL/UNKNOWN`, polarity/modal/temporal qualifications, context selector/hash, language, attribution/correction readiness e limitations. Qualunque inference non provata rimane `UNKNOWN`, senza dedurre intent.

## Traceability & constraints
 R04/R06/R07/R16/R21; Q15–Q18, owner example solo *ipotetico*, no biometric; original wording mai normalizzato in quotation. No second corpus/search stack.

## Scope
 Canonical captured span+surrounding scene/thread/precedent question+source chain → bounded context expansion by coherence/discontinuity rather than seconds/characters fixed → structured speech-act hypothesis with evidence spans/counter-signals → independently reproducible acceptance criteria per class and private event → eligibility decision for B verifier/C public Statement. `TRANSLATION` derived from immutable original and language pair with explicit negation/numbers/names/dates/modal/procedural term parity check; failure flags rather than guessed translation correctness. Store immutable context/source byte hashes and distinct approval authority. Reuse `context_integrity`, `wording_contract`, `source_span_review`, DP-219/222.

## Non-goals
 No invented transcript, no certainty from sarcasm model confidence, no speaker voiceprint, no universal language promise.

## Dependencies and sequencing
 Hard above; link DP-313/04/07 consumers, C public projection. Real per-language calibration gold (DP-321) before autonomy cutover; source rights separately DP-317. Unknown language/mode is explicit capability gap and bounded attempt, not Italian-only fallback.

## Acceptance criteria

- [ ] `AC-312.1`: Direct assertion vs quotation/citation+critique vs recitation vs reporter claim produce different attributed speech acts and no false endorsement; authored by hand-checked, license-safe fixtures.
- [ ] `AC-312.2`: Negation, speaker-turn, question context, qualifier before/after and discontinuous montage materially change context fingerprint/readiness; omission fails closed, replay same bytes is idempotent.
- [ ] `AC-312.3`: Claim/Statement retains actual utterer distinct from quoted author/source; contradictory identity or unattributed fragment cannot publish as opinion/endorsement.
- [ ] `AC-312.4`: IT/DE + at least another observed source language fixtures check source words vs translation and preserve named entities, polarity, quantifiers, modal verbs, temporal and legal terms; unsupported pair = explicit pending/hold, not semantic pass.
- [ ] `AC-312.5`: Valid context from longer coherent scene may be accepted without arbitrary fixed seconds; deliberately cropped opposite-meaning scene fails; source and source-part boundaries retained.
- [ ] `AC-312.6`: Re-parse/retranslation/source revision stales dependent decision, Finding/relation/public summary; private tests+MiniPC authorized capture readback during implementation.

## Validation / proof
 Blind labeled contrast set (minimum adversarial categories above) with text, annotation provenance/source selector, expected outcome and negative controls; compare old/expanded bound results; show no assertion/endorsement leak in eventual C consumer. Actual thresholds calibrated through DP-321, not fabricated here.

## Documentation, data, and migration impact
 Additive `speech_act_context_decision`/serialized equivalent bound to Statement occurrence and revision (do not decide storage before inspecting stores). Preserve legacy `speech_mode` as v1 input, explicit version migration; no silent old approval carry-over.
## Completion receipt
 non implementato; pianificazione soltanto.

## 2026-10-11 — First implementation slice

Bounded private `SpeechActContextDecision` in `context_integrity.py` (commit `6404079`) distinguishes assertion, quote, criticism, denial, question and incomplete context; never grants publication. 22 focused and 14 legacy context cases pass; multilingual reference gold, German translation assurance, downstream source reanalysis and MiniPC receipt are still missing. No AC can be closed solely from lexical fixtures.

## 2026-10-11 — Negated criticism fail-closed regression

Three synthetic contrast pairs in Italian, English and German reproduced an unsafe private semantic classification: `Non critico questa misura.` (and equivalent negated critical predicates) previously returned `CRITIQUE / DISTANCE / CANDIDATE_PRIVATE`, falsely attributing dissent to the utterer. The lexical preflight now returns `UNKNOWN / UNKNOWN / HOLD_FOR_CONTEXT` with `CRITIQUE_NEGATION_SCOPE_UNRESOLVED` whenever a criticism cue co-occurs with negation whose scope has not been independently established. Positive direct criticism remains a private candidate; source revision changes the fingerprint and metadata replays deterministically. RED: three failing language subtests. GREEN: 23/23 focused speech-act cases, 14/14 legacy context cases. This is a bounded conservative rule, not multilingual semantic calibration, quote/source clearance, downstream invalidation, or MiniPC runtime proof; all original AC-312.1–312.6 remain pending.

## 2026-10-11 — German reversed-quotation fail-closed regression

A synthetic, complete German turn quoted as `»Ich unterstütze diese Maßnahme.«` or `›Ich unterstütze diese Maßnahme.‹` was incorrectly labeled `ASSERTION / ENDORSE / CANDIDATE_PRIVATE` by the private lexical classifier: reversed German quotation delimiters were excluded from quote detection. This could conflate a quotation with the reader's own endorsement. Both cases failed a new regression before the patch and now produce `QUOTE / NON_COMMITTAL` with no publication authority. The same delimiter check holds an incomplete `›` quotation as `HOLD_FOR_CONTEXT / UNKNOWN` with `UNBALANCED_QUOTATION`. A minimal extension to the quote parser and its balancing check fixes the source-level defect. Focused DP-312 plus legacy context tests: 38/38 passing; Ruff passing. These are synthetic local tests only. No independent language gold, authorized source/use rights, actual capture, persisted dependent invalidation, MiniPC replay or publication gate was exercised, and none of AC-312.1–312.6 is marked DONE.


## 2026-10-13 — Curly single-quote integrity regression (bounded private preflight)

Local synthetic contrast cases found a new false endorsement: the complete-turn strings `‘I support the policy.` and `’I support the policy.` yielded `ASSERTION / ENDORSE / CANDIDATE_PRIVATE` despite a dangling typographic quotation delimiter. A new focused test reproduced both failures RED. The repair validates alternating `‘…’` delimiters while excluding apostrophes embedded within words. It also holds reversed or nested delimiters and allows balanced quotes containing contractions, e.g. `‘I’m certain I support the policy.’`, without attributing the quoted words to the utterer. Positive direct support remains `ASSERTION / ENDORSE / CANDIDATE_PRIVATE`. The existing `UNBALANCED_QUOTATION` signal forces `HOLD_FOR_CONTEXT / UNKNOWN` and deterministic metadata replay for affected fragments. This is lexical private preflight only: it grants no publication authority, proves no real source/speaker/usage rights, and does not establish independent multilingual gold, downstream invalidation or MiniPC acceptance. All manual AC-312.1–312.6 remain open.


## 2026-10-13 — Curly apostrophe false-HOLD P2 regression

Independent review of the initial incomplete-curly-quote protection identified legitimate English U+2019 apostrophes incorrectly treated as unmatched quotation marks. The private parser returned `HOLD_FOR_CONTEXT / UNKNOWN` for `I support workers’ rights.`, `I support James’ plan.`, `I support the ’90s policy.`, and even `“I support workers’ rights.”`; the initial single-curly quote matcher also truncated valid quotes containing an s-possessive or decade elision. A new test first failed nine contrast subcases on the same source. The bounded repair uses one orthographic apostrophe recognizer for both quote matching and delimiter balancing: internal contractions, s-possessives before another word, and leading numeric decade elisions do not count as quote closers. Complete straight/direct support remains a private candidate, balanced complete quotations remain non-committal, and dangling, nested or reversed quotation delimiters still fail closed. Where an s-final word plus adjacent reported-speech text is inherently ambiguous as a quote boundary, conservative HOLD may remain; this lexical preflight is not a general syntactic parser. Focused 25/25 DP-312 tests PASS with the P2 regression included. No independent language calibration, source-use grant, editorial decision, production publication authority, downstream revocation, or MiniPC capture proof is implied. All AC-312.1–312.6 stay OPEN.
