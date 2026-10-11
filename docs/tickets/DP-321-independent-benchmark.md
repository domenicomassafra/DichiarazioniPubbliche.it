# DP-321 — Gold credibile e metriche indipendenti di errore, coverage e abstention

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-223, DP-226, DP-228, DP-229, DP-312, DP-314

## Problem
 Fixture deterministiche 5/5 e synthetic red-team provano regole, non la qualità autonoma su fonti reali multilingue, processuali e negazioni. Il medesimo model usato per generare una conclusione non può dichiararsi ground truth. Una accuracy che ignora le astensioni può mascherare pubblicazioni pericolose.

## Outcome
 Versioned `ReferenceCaseManifest` licito, rappresentativo e verificabile con etichette indipendenti, fonte originale locabile, adjudication/contestability, limiti di copertura e hold; metriche **separate** false-person, false-quote, false-endorsement, false-factual-verdict, false-denial, rights/privacy leak, unsupported publication, abstention, recall-by-claim/risk/language, latency/cost e drift.

## Traceability & constraints
 R39/R06/R13/R21/R34; zero reviewer testuale editoriale ordinario non equivale a nessuna verifica indipendente dei reference cases. Owner decide soglie release basate su costo del falso positivo e campione reale; non inventare gold, sample size o percentuali dai test correnti.

## Scope
 Stratificare lingua (IT/DE e lingue osservate), tipo di fonte (written/audio/OCR), factual vs opinion, quote/report/endorse, event/legal status/denial/numeric, primary vs derived, same-name, temporal supersession, ambiguous contested vs decidable. Le etichette verificabili si basano su documenti primari e annotatori/regole indipendenti dal sistema testato; doppia annotazione mirata in classi ad alto rischio o qualified decision reference, adjudication con livello di incertezza conservato. Corpus versione/bytes/license e split di calibration vs holdout, blind evaluation, no leakage tra famiglie e no approval from same generator. Casi senza verità esterna verificabile possono avere solo gold di *corretta astensione/attribuzione*; nessuna fabricated objective ground truth.

## Non-goals
 Nessuna promessa zero errori globali, no test attuale di provider a pagamento, no sample di contenuto inventato presentato come fonte reale.

## Dependencies and sequencing
 First create legal/allowed case manifest, lock test splits and adjudicator independence; machine-authority DP-316 references accepted threshold profile, D checks release and cost, A covers real source families with proof. Routine model updates invalidate comparability/approval until retest.

## Acceptance criteria

- [ ] `AC-321.1`: Every reference case has immutable source/locator/hash/rights, independent label origin, source/adjudication confidence and ambiguity status; leaked test labels or generator self-judging cannot pass.
- [ ] `AC-321.2`: Metrics report numerators/denominators and confidence/coverage for false attribution, false verdict, false endorsement, false denial, abstention and conditional publishability separately, stratified by language/source/claim/risk; no hidden exclusions.
- [ ] `AC-321.3`: Adversarial tests with wrong name, cropped negation, ironic reported speech, duplicate independent-source illusion, processual allegation, changed jurisdiction/time, revoked rights and new later evidence refuse unsafe public labels.
- [ ] `AC-321.4`: Genuine supported/refuted factual positives, legitimate non-factual Statement and licensed exact quote remain usable under accepted profiles, avoiding trivial 100% abstention as success.
- [ ] `AC-321.5`: Thresholds, minimum sample confidence and observed operating envelope are owner-accepted **after** pilot calibration, versioned by feature/scope; unseen risk/language stays held if uncovered, not green by default.
- [ ] `AC-321.6`: Reproducible offline eval and MiniPC held-out end-to-end pilot output compare exact claims, public source, rights/review, cost and corrections; D release fails on negative gate, no provider trial before authorization.

## Validation / proof
 Signed/controlled ground-truth manifest, cases metadata (private where necessary), fixture licenses and reference adjudication evidence, confusion matrices per category and CI repeatability; no threshold asserted here.
## Documentation, data, and migration impact
 Extend existing `false_attribution_benchmark` and deterministic benchmark only when they can represent the new independent labels; separate gold dataset and case provenance from training/research inputs, no public sensitive corpus.
## Completion receipt
**2026-10-11 local source-only benchmark contract — IN PROGRESS, NOT accepted gold.**
`independent_reference_benchmark_v1.py` requires versioned private reference
metadata, source/quote locator and rights identifiers, independent annotator
and adjudication proof handles, locked calibration versus holdout split and
same-root duplicate rejection; only abstention-scope labels are valid for
intrinsically contested cases. Output includes explicit numerators and
denominators, Wilson descriptive intervals, stratification, abstention,
coverage, conditional eligibility, cost/latency and bounded drift comparison.
The external verification seam is **not** trusted evidence by itself; outputs
stay `CONTRACT_ONLY` and `release_eligible=False`, without fabricated thresholds
or real independent source labels. Source/test commit `12bfb5a`: **15** focused
adversarial synthetic tests PASS and Ruff PASS. None of AC-321.1–.6 is closed:
genuine independently attested/licensed holdout, qualified gold, owner acceptance
and MiniPC end-to-end evidence remain absent.

**2026-10-11 local denominator regression — source-only, still IN PROGRESS.**
Prediction-only `abstention` counts explicit `ABSTAIN` and missing predictions
over the entire frozen manifest, including cases whose external reference
verification is unavailable or refused. These cases remain excluded from
semantic, rights and eligible-recall denominators. A synthetic three-case
regression (one admitted, one unverified abstention, one unverified missing)
previously reported `0/1` abstentions and now reports `2/3` while retaining
`BLOCKED_EXTERNAL_GOLD` and zero release/publication authority. This checks
accounting consistency only; the external verification callback in tests is
fake, and no independent human labels, actual source rights or MiniPC pilot
have been accepted. AC-321.1–.6 remain unchecked.

**2026-10-11 local drift-scope regression — source-only, still IN PROGRESS.**
`compare_reference_reports` now requires matching SHA-256 fingerprints of the
exact admitted case-ID set bound to the manifest, in addition to existing
manifest/count checks. Previously two different admitted subsets with equal
counts and identical metrics could be marked `CONTRACT_ONLY_COMPARABLE`.
A synthetic three-case RED→GREEN regression confirms swapped equal-count
subsets are `BLOCKED_INCOMPARABLE_REFERENCE_SCOPE`; existing reports lacking
the optional fingerprint also fail closed. Fingerprints are consistency
metadata, **not** independent signatures or accepted gold. All AC-321.1–.6
remain open pending independently attested real sources and MiniPC proof.
