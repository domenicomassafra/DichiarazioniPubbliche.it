# DP-226 — Compound numerical verification v2

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-215; coordinate with structured-data providers

## Problem

The deterministic verifier already handles exact values, ranges and historical extrema.
Real political/economic claims also depend on deltas, ratios, percentage changes,
denominators, units, periods and rounding.

## Outcome

Port the useful numerical-verification architecture from Claim Polygraph into the existing
deterministic verifier without introducing a second judgment engine.

## Acceptance criteria

- [x] numeric_delta compares two independently selected suitable observations.
- [x] numeric_ratio checks numerator/denominator and fails closed on zero denominator.
- [x] numeric_percent_change uses explicit current/baseline selectors and rejects unit
  mismatch or zero baseline.
- [x] Compound rules keep the statement-time cutoff and DP-215 source-suitability gate.
- [x] Conflicting numeric inputs remain unresolved instead of choosing a preferred value.
- [ ] Add explicit unit-conversion policy rather than implicit conversion.
- [ ] Add rounding/significant-figure policy and denominator/population semantics.
- [ ] Add structured ISTAT/Eurostat/DVNS fixture coverage and MiniPC proof.

## Implementation receipt

Local runtime and focused tests added 2026-10-05. Structured-provider integration and
MiniPC proof remain open.
