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
