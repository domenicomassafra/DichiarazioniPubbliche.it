# DP-103 — Finding and assessment vocabulary convergence

Status: DONE
Milestone: M1  
Depends on: DP-102

## Problem

Historical taxonomy docs contain more verdict labels than the deterministic runtime
currently supports. Public semantics must not drift by documentation alone.

## Outcome

Separate claim type, verification assessment, publication status, and longitudinal
relation vocabulary into explicit versioned contracts.

## Acceptance criteria

- each label has exactly one layer/meaning;
- deterministic verifier only emits assessments it can prove by a versioned rule;
- unsupported nuanced labels remain future/candidate rather than decorative public text;
- migration/backward compatibility for existing findings is explicit;
- ClaimReview mapping remains non-numeric and person-score-free.

## Implementation receipt

- Added `poc/dichiarazioni_pubbliche/domain_vocabulary.py` as the single versioned
  registry for claim type, verification assessment, finding publication status,
  and relation candidate vocabularies.
- Migrated runtime, benchmark fixtures, public projection, ClaimReview mapping,
  and web types/demo data to the canonical closed vocabularies.
- Kept `OUTDATED_DATA` as a backward-readable assessment; deterministic
  verification v2 does not emit it. `NO_CONTRADICTION_ESTABLISHED` remains a
  benchmark evaluation outcome, not a claim assessment.
- Added replay-safe migration
  `db/migrations/20260925-add-finding-assessment-vocabulary.sql`; it adds
  explicit version columns and strict checks without rewriting existing rows.
- MiniPC proof (2026-09-25): compileall PASS; 241 tests PASS; benchmark 5/5;
  migration applied twice with `ON_ERROR_STOP=1`; four constraints present;
  invalid `COMPARATIVE_STATISTIC` and `PARTIALLY_SUPPORTED` inserts rejected;
  canary residue 0/0/0; source-poll and health timers active. Web `astro check`
  passed on Mac; MiniPC web check was not runnable because its mirror lacks the
  platform-specific optional Rolldown native binding.
