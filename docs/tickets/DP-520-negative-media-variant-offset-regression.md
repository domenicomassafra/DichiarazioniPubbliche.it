# DP-520 — Negative media-variant end offset must fail closed

Status: DONE
Milestone: M5 — Reliability, security, operations, and data lifecycle
Depends on: DP-237

## Problem

The pure exact-source resolver for `MEDIA_SEGMENT_REF` accepted a negative
`variant_end_char` when Python's negative slice offset happened to select
the expected source segment. That can launder an invalid source-relative
coordinate into a `LOCATED` result even though the coordinate cannot be
persisted or replayed as a nonnegative exact source span. The bug was
reproduced against the existing immutable media fixture, not hypothetical.

## Outcome

Require a strictly increasing, nonnegative exact media variant span
before allowing a segment-level source locator to become `LOCATED`.
Reject invalid spans conservatively without changing any production
publication, source-rights, identity, role, or evidence authority.

## Scope

- `poc/dichiarazioni_pubbliche/original_source_resolver.py`: one bounded
  span invariant, `variant_end_char > variant_start_char`; existing
  `variant_start_char >= 0` and `variant_end_char <= len(text)` remain.
- `tests/test_dp237_exact_locator.py`: adversarial negative end offset
  that Python accepts and that selects identical bytes, plus a valid
  positive control on the same immutable media record.
- Keep DP-237's broader original end-to-end provenance/readback
  acceptance **open** and record this narrowly scoped defect there.

## Non-goals

- Approval or download of any media/source/rights material;
- new public routes, media seek policy, Studio/MiniPC rollout;
- closing or rewriting DP-237 AC-237.1–6;
- representing a source-level safety fix as production release acceptance.

## Dependencies

This regression fix depends on the existing pure DP-237 resolver and
fixtures, both present in the source repository. It does not depend on
live provider access or operator approval because it adds **only a
fail-closed source-side validation predicate**. The DP-237 product
deployment and real-source acceptance remain separate, open requirements.

## Acceptance criteria

- [x] **AC-520.1**: A negative `variant_end_char` capable of selecting
  the exact same bytes via `variant_text[start:-N]` is refused,
  returning `BLOCKED / LOCATOR_MEDIA_TEXT_MISMATCH` rather than
  `LOCATED`.
- [x] **AC-520.2**: The exact same media fixture with a nonnegative,
  increasing range remains `LOCATED`; existing other mismatch/hash/
  source-bound checks are not weakened.
- [x] **AC-520.3**: The regression is executable, RED against the
  parent implementation before the fix and GREEN on the patch; focused
  and adjacent source resolver tests, lint, compilation, and
  `git diff --check` pass.
- [x] **AC-520.4**: Only the owned pure resolver, regression tests and
  parent ticket are changed by the implementation commit. Source
  checkout/remote integration SHA match; no production operations,
  unauthorized rights, user data or unrelated WIP are touched.

## Validation / proof

The original failure accepted the bad signed media segment as `LOCATED`.
The negative aliasing regression in
`test_negative_variant_end_offset_must_not_alias_real_segment`
failed RED, then passed GREEN after the one-line non-increasing-range
check. The worker executed **68/68** focused/adjacent source,
derivation, and recovery tests, **59/59** public/contract controls,
**5/5** deterministic benchmark, scoped Ruff, compileall and diff
checks. The coordinator independently reran
`PYTHONPATH=poc python3 -B -m unittest tests.test_dp237_exact_locator
tests.test_original_source_resolver -q`: **24/24 PASS**, and also
the DP-237/DP-318 focused collection **63/63 PASS** with Ruff and
diff checks. An initial coordinator command mistakenly referred to a
nonexistent `tests.test_document_derivation` module and failed at
import; the correct existing modules above were rerun successfully,
so the invalid command is not counted as PASS.

## Documentation, data and migration impact

No schema, persistence, migration, source fetch, provider access,
production runtime or public output is modified by this bug fix.
DP-237's acceptance and any future MiniPC rollout stay separate.

## Completion receipt — 2026-10-15

- Scoped technical implementation commit:
  `e4dffdf33ee2e2a587ec89660bb5d39dea266de9`, branch
  `integrate/dp-20261014-all-lanes`; remote branch moved to this
  commit and later to `3d3c174c24aa582a3777891fc2c879a448defe79`
  with the independent DP-318 fix. No main push.
- Reviewed patch: exactly 1 resolver validation line, 22 test lines,
  and 28 lines of parent DP-237 evidence; no code of third parties.
- Subticket **DP-520 DONE (source-only)**. Parent **DP-237
  IN PROGRESS, AC-237.1–6 OPEN**; no claim to have reduced the
  original 72 open tickets.
- Git integration writer: lane 02 prime, no simultaneous staging of
  foreign DP-512 WIP.
