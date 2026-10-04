# DP-110 — Evidence-based reasoned inference candidates

Status: DONE
Milestone: M1
Depends on: DP-102, DP-103

## Problem

Some useful conclusions are not copied verbatim from one source. They follow from a
combination of observations, exclusions, timing, and competing explanations. Treating
those conclusions as direct evidence loses epistemic provenance; refusing all derived
reasoning makes the product mechanically literal and less useful.

## Outcome

Add a private `InferenceCandidate` layer between evidence/observations and any later
verification or editorial finding. It may represent deductive, statistical, exclusion,
abductive, or composite reasoning while preserving what the conclusion depends on.

## Acceptance criteria

- every inference has explicit premise references;
- non-deductive reasoning records alternative hypotheses;
- high-risk identity/criminal/intent reasoning records disconfirmers;
- high-risk reasoning records countervailing facts, including facts that can support
  both the preferred explanation and an innocent/alternative mechanism;
- support is qualitative, not a fabricated numeric probability;
- new inference candidates are always `CANDIDATE` and `publication_blocked = true`;
- inference candidates never insert findings, approve evidence, or enter the public
  projection merely because a model or operator created them;
- replay is deterministic through a content-derived inference ID;
- PostgreSQL and Python contracts reject malformed or publication-enabled records.

## Garlasco motivating case

The 2025 court-appointed genetic work reported a Y-chromosome profile compatible with
the Sempio paternal line while explicitly stating that the available material did not
permit identification of one individual contributor and had scientific limitations.

The correct data model therefore needs two separate propositions:

1. **lineage-level inference:** the observed profile supports a male contributor from
   the Sempio paternal line more than a generic unrelated-male hypothesis, subject to
   the stated quality limitations;
2. **individual-source hypothesis:** `Andrea Sempio was the contributor` is a distinct
   identity hypothesis and cannot be upgraded to an identified fact from paternal-line
   Y data alone. It must retain alternatives such as another patrilineal male,
   transfer/contamination, or artefact, plus any independent evidence that later narrows
   those alternatives.

This distinction is not a ban on common-sense reasoning. It is what lets the system
reason beyond quotations without silently converting a hypothesis into evidence.

## Implementation receipt — 2026-09-27

- Added `InferenceKind`, `InferenceSupportLevel`, `InferenceRiskClass`, and the
  `reasoned-inference-v1` vocabulary.
- Added `poc/dichiarazioni_pubbliche/inference_repository.py` with deterministic IDs,
  validation, JSON-to-SQL parameters, and private candidate persistence.
- Added `QueueRuntimeStore.insert_inference_candidate()`.
- Added the `inference_candidate` table to `db/schema.v1.sql` and the idempotent
  migration `db/migrations/20260927-add-reasoned-inference-candidates.sql`.
- New records are constrained to `publication_blocked = true`; the public projection
  does not consume this table.
- Python contract rejects numeric confidence fields, requires alternatives for
  non-deductive inference, and requires both countervailing factors and disconfirmers
  for identity/criminal/intent risk classes.
- Local proof: full suite 686/686, deterministic benchmark 5/5, repository contract
  check green, and `git diff --check` green.
- MiniPC proof: both inference migrations applied; focused tests 43/43 and full suite
  686/686 pass; benchmark 5/5 passes.
- Production DB contains two private Garlasco inference candidates tied to the Bruzzone
  DNA claim: a `MODERATE/SENSITIVE_PERSON` lineage-level inference and an
  `INDETERMINATE/IDENTITY_ATTRIBUTION` individual-source hypothesis. Both are
  publication-blocked and carry explicit countervailing factors.
- Fresh production projection remains `dossier_count = 0`, `omitted_count = 0`.
