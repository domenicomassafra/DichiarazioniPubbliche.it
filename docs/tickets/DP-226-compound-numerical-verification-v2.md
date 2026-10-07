# DP-226 — Compound numerical verification v2

Status: DONE
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
- [x] Add explicit unit-conversion policy rather than implicit conversion; delta and
  percent-change rules may normalize mismatched comparable units only through a declared
  target unit plus per-input factors, while missing/invalid mappings fail closed.
- [x] Add rounding/significant-figure policy and denominator/population semantics.
- [x] Add structured ISTAT/Eurostat/DVNS fixture coverage and MiniPC proof.

## Implementation receipt

Local runtime and focused tests added 2026-10-05. Explicit rule-scoped unit conversion for
delta/percent-change was added without changing existing same-unit semantics. The 2026-10-06
follow-up adds explicit decimal-place/significant-figure comparison policy plus required
numerator/denominator population dimensions; invalid/missing dimensions and zero denominators
fail closed. The 2026-10-06 closure pass moves ISTAT/DVNS/Eurostat-style cases into the
versioned `numeric-structured-providers-v1.json` fixture and replays delta, percent-change and
ratio through the canonical deterministic verifier. Final focused acceptance is **19/19 PASS**
locally and **19/19 PASS** on an isolated MiniPC `/tmp` bundle. The fixture matrix exercises
ISTAT-, Eurostat- and DVNS-shaped structured observations through the real deterministic rules,
including unit conversion, denominator/population semantics, rounding and fail-closed conflict
cases. This closes the stated fixture+MiniPC AC; no live ISTAT/Eurostat/DVNS provider call,
credential, source-family approval or network receipt is claimed or required by this ticket.
