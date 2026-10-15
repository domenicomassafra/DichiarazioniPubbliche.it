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


## 2026-10-13 — Reported-speech closing U+2019 P2 follow-up

An independent exact-PR review identified both directions of a second U+2019 scope bug: `He said ‘I support this’ yesterday.`, `‘I support this’ she said.` and the German `Er sagte ‘Ich unterstütze das’ gestern.` were incorrectly held, because the earlier generic s-ending possessive recognizer swallowed the quote closer. Conversely the orphan `I support this’ policy.` was falsely labeled `ASSERTION / ENDORSE / CANDIDATE_PRIVATE`. The new adversarial test reproduced six failing subcases (including uppercase `THIS` and `his`), before the repair. A bounded list of closed-class non-possessive words now prevents those quote closers from being consumed as s-possessive apostrophes. The same recognizer is used when matching explicit `‘…’` pairs and checking ordered delimiters: a paired quote with a reporter cue stays `REPORT / NON_COMMITTAL`, while an orphan closer holds with `UNBALANCED_QUOTATION / UNKNOWN`. Earlier `workers’ rights`, `James’ plan`, `’90s`, contraction, and fully balanced-quote controls remain valid.

Some s-ending nouns are intrinsically ambiguous in this bounded lexical preflight. For example, `He said ‘I support James’ yesterday.` and `He said ‘I support workers’ yesterday.` remain `HOLD_FOR_CONTEXT / UNKNOWN` because the same punctuation may denote a possessive with an omitted closing quote; they cannot be lexically endorsed or treated as proven reported speech. Manual/contextual review and multilingual evidence remain necessary. No source Capture, rights authorization, factual validation, downstream reanalysis, editorial approval, or MiniPC replay was performed; all AC-312.1–312.6 remain OPEN.

## 2026-10-13 — Replace finite s-ending word list with bounded curly quote pairing

Independent replay on the preceding opt-in classifier revealed that a finite
English/German non-possessive word blacklist cannot distinguish an s-final
closing U+2019 quotation mark from a plural/name possessive. Normal paired
reported quotations ending `us`, `yes`, `always` and German `uns` incorrectly
became `HOLD_FOR_CONTEXT`; in the opposite direction, orphan `us’`/`yes’`
could be treated as direct `ASSERTION / ENDORSE`. Eight synthetic adversarial
cases reproduced the errors **RED** on the preceding PR head.

The private preflight now uses one bounded left-to-right U+2018/U+2019
orthographic pairing function shared by both quotation extraction and
unbalanced-delimiter signals, replacing the finite blacklist. Internal
contractions and numeric elisions are not closers; plausible name/plural
possessives within a proposed quotation can require conservative HOLD when
there is no independently distinguishable closing delimiter. Natural paired
reported quotations remain `REPORT / NON_COMMITTAL`; dangling, reversed,
nested or orphaned delimiters still HOLD with no endorsement. Tests were
**GREEN** for all eight new contrasts and 90 neighboring source-only checks;
benchmark 5/5, Ruff and diff check pass. The classifier is not a full
language parser, qualified source reviewer, or publication permit: ambiguous
noun/quotation boundaries are intentionally held, and all AC-312.1–.6 stay
OPEN pending real multilingual annotated sources, protected runtime and
human acceptance. No source Capture, rights grant or MiniPC deploy occurred.

## 2026-10-13 — Ordered double-typographic quotation integrity (independent P2)

A separate native read-only review of the source-only PR reproduced a
false private endorsement for a reversed U+201D/U+201C pair: `”I support the
policy“` and analogous Italian/German support turns were treated as direct
`ASSERTION / ENDORSE` because the existing source parser checked only equal
open/close counts. A new focused negative regression was **RED in three
languages** before the change. The parser now also requires each complete
U+201C/U+201D sequence to alternate in source order; reversed or nested
non-pairs force `UNBALANCED_QUOTATION / HOLD_FOR_CONTEXT / UNKNOWN` before
lexical endorsement. Valid complete quotation, direct assertion and the new
U+2018/U+2019 orthographic scanner remain independently guarded. The
regression is GREEN and 91 related tests, Ruff, deterministic benchmark and
diff check pass. This is a private fail-closed preflight only, not a
multilingual grammar guarantee, attribution/rights approval or public route.
All original AC-312.1–6 remain OPEN.

## 2026-10-13 — German low-double, nested guillemet and ASCII single-quote holds

Independent source review of the preceding PR revision detected three
additional inherited **false endorsement** classes that were not captured by
old delimiter count checks: an unmatched German low-double opening
`„...` / unsupported U+201F mark; nested `«...«... »»` and `‹...‹...››`
with equal opener/closer totals; and a dangling U+0027 ASCII single quotation
mark (`'I support ...` or `... support.'`) mistaken for a direct endorsement.
Adversarial tests were RED in seven low-double/angle source cases (including
an authentic fully paired German `„...“` quotation not yet recognized) and
four dangling ASCII cases. New lexical safeguards independently require
adjacent ordered pairs for either supported guillemet orientation, ordered
`“...”` or German `„...“` double-typographic pairs, and balanced ASCII
quotation markers except in-word contractions and numeric elisions. Correct
German low-double pairs stay `QUOTE / NON_COMMITTAL`; unresolved/nested,
reversed or orphan marks become `UNBALANCED_QUOTATION / HOLD_FOR_CONTEXT`
instead of `ASSERTION / ENDORSE`. Both targeted regressions are GREEN,
with 93 related source-only unit tests and Ruff PASS. Genuine ambiguous
possessives may be held conservatively, not guessed as direct speech.
No real source rights, speaker, independent multilingual corpus, publisher,
MiniPC, or public release gate has been satisfied: all DP312.1–.6 remain OPEN.

## 2026-10-13 — German low-single typographic quote integrity

Independent read-only review of the preceding PR SHA identified a final
separate quotation family omitted by the lexical preflight: the German
U+201A low-single opening `‚` paired with high U+2018 `‘` and unsupported
U+201B `‛`/ornamental quotation symbols. Dangling sources
`‚Ich unterstütze die Maßnahme.` and `‛Ich unterstütze die Maßnahme.`
were incorrectly treated as `ASSERTION / ENDORSE / CANDIDATE_PRIVATE`.
Five focused negative/positive assertions were **RED** before the fix.
The bounded single-pass quotation scanner now recognizes a valid `‚...‘`
as `QUOTE / NON_COMMITTAL` while holding unbalanced low-single, nested
low-single or unsupported ornamental quotation markers with
`UNBALANCED_QUOTATION`. Existing high-single `‘...’` and contractions remain
separately handled. The focused regression and 94 related unit tests are
**GREEN**, Ruff/diff and deterministic benchmark 5/5 PASS; no human source
approval, source Capture, MiniPC readback or language-wide semantic gold is
implied. **All DP312 AC-312.1–.6 remain OPEN.**

## 2026-10-14 — CJK quotation delimiters around English source words

An independent local source-only test found that complete quoted turns framed by
the common corner/book/title delimiters U+300C/U+300D, U+300E/U+300F,
U+300A/U+300B or U+3010/U+3011 were misclassified as direct
`ASSERTION / ENDORSE / CANDIDATE_PRIVATE` even when their quoted English
words were identical to a properly attributed standalone assertion. A focused
test first failed four positive-quotation contrast cases (four RED failures).
The bounded lexical parser now recognizes each forward ordered pair and holds
orphan, reversed and nested marks with `UNBALANCED_QUOTATION`; the well-paired
complete quotation is `QUOTE / NON_COMMITTAL`, and genuinely direct words
remain a private candidate. Focused **32/32** DP-312, 15/15 legacy context,
26/26 relations and 7/7 independent opinion consumers PASS; deterministic
benchmark 5/5, Ruff, repository contract and diff-check PASS.

This classification is neither a source-use grant nor publication authority;
real source/identity review, multilingual gold, affected downstream replays and
MiniPC readback remain absent. **AC-312.1–6 stay OPEN** and the release is not
made GO by this source-only repair.

## 2026-10-15 — Negative quantifiers in private EN/DE support preflight

Five deterministic source-independent contrasts reproduced a consequential
false attribution in the existing classifier: `I support none of these
proposals.`, `I support neither proposal.`, `I support nobody.`, `Ich
unterstütze weder Vorschlag A noch Vorschlag B.` and `Ich unterstütze
niemanden.` were all `ASSERTION / ENDORSE / CANDIDATE_PRIVATE` before the
patch, despite their explicitly negative quantifiers. A new focused test
first failed all five cases (**RED**), against direct positive controls.
The minimal lexical extension recognizes EN `none/neither/nobody` and DE
`weder/niemand*` plus inflected `kein*` as negation cues, so the five negative
cases conservatively yield `HOLD_FOR_CONTEXT / UNKNOWN / UNKNOWN` with
`NEGATION_SCOPE_UNRESOLVED`. Positive controls remain private candidates;
each negative result is bound to its exact source hash, deterministic metadata
replay succeeds, and a changed source fails replay. Focused speech-act,
legacy-context and relation tests **81/81 PASS** after the fix.

This is an isolated local safety regression, **not** independent linguistic
gold or authorization to publish. It does not verify observed source identity,
source-use rights, translation correctness, real consumer invalidation,
MiniPC Capture or external editorial approval. **All six AC-312.1–6 remain
OPEN** until the original licensed-source, gold, downstream and runtime
acceptance receipts are available.
