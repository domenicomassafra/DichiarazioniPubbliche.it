# DP-104 — Longitudinal relation approval and publication policy

Status: DONE
Milestone: M1  
Depends on: DP-102, DP-103

## Problem

Relation candidates exist, but a stable product needs explicit rules for when same-
proposition, update, clarification, position change, or contradiction relations may be
made public.

## Outcome

Define review/provenance/publication state for claim relations without turning them into
intent or political judgments.

## Acceptance criteria

- candidate and published relation states are distinct;
- relation publication requires explicit review provenance;
- statement-time/context compatibility is checked;
- `contradiction` never implies `deliberate falsehood`;
- public projection can omit stale relation reviews fail-closed;
- re-analysis is triggered when a relevant approved relation changes.

## Implementation receipt

- Added `poc/dichiarazioni_pubbliche/relation_policy.py`: pure, side-effect-free, zero-I/O module
  exposing `RELATION_PUBLICATION_POLICY_VERSION = "relation-publication-v1"`,
  `RelationCandidateStatus` (`CANDIDATE`, `APPROVED`, `REJECTED`, `SUPERSEDED`),
  `RelationPublicationEligibility` (`CANDIDATE`, `REJECTED`, `PUBLIC_ELIGIBLE`),
  and pure decision functions `evaluate_relation_publication_eligibility` and
  `decide_relation_publication_eligibility`.
- Enforced core publication rules in `relation_policy.py`:
  - Candidate states never publish (`CANDIDATE` storable status yields `CANDIDATE` eligibility).
  - Terminal non-publishable statuses (`REJECTED`, `SUPERSEDED`) yield `REJECTED`.
  - Public eligibility requires explicit review provenance (`has_approved_review_event=True`).
  - A relation referencing an unpublished finding is never public-eligible (yields `CANDIDATE`).
  - A relation missing proposition keys can never be a contradiction (yields `REJECTED`).
  - Statement-time and context compatibility is checked (incompatible contexts yield `REJECTED`).
  - Public projection omits stale relation reviews fail-closed (`review_is_stale=True` yields `CANDIDATE`).
  - Corrections involved must be approved (`correction_approved=False` yields `CANDIDATE`).
  - Contradiction never implies deliberate falsehood: prohibited intent terms (`intent`,
    `intentionality`, `lie`, `deception`, `deliberate_falsehood`, `dishonesty`, `bad_faith`,
    `motive`) cannot be passed or encoded in the policy input or output schemas.
- Added replay-safe migration `db/migrations/20260926-add-relation-approval-policy.sql`:
  - Adds `policy_version text NOT NULL DEFAULT 'relation-publication-v1'` to `claim_relation_candidate`.
  - Uses only `IF NOT EXISTS` / `DROP CONSTRAINT IF EXISTS` / `ADD CONSTRAINT`.
  - Enforces storable states strictly as `('CANDIDATE', 'APPROVED', 'REJECTED', 'SUPERSEDED')`,
    with no mutable `PUBLISHED` status on the table to ensure public visibility stays derived
    from the append-only `review_event` ledger.
  - Constrains `relation_type`, `relation_version`, `policy_version`, distinct claims, and review event actions.
  - Never rewrites or updates existing database rows.
- Added 13 focused tests in `tests/test_relation_policy.py`, verifying all five policy acceptance criteria:
  - `test_candidate_and_published_relation_states_are_distinct` (Criterion 1)
  - `test_relation_publication_requires_explicit_review_provenance` (Criterion 2)
  - `test_statement_time_and_context_compatibility_checked` (Criterion 3)
  - `test_contradiction_never_implies_deliberate_falsehood_no_intent_fields` (Criterion 4)
  - `test_public_projection_omits_stale_relation_reviews_fail_closed` (Criterion 5)
  - Additional tests covering unpublished findings, missing proposition keys, unapproved corrections,
    invalid inputs, and dataclass input compatibility. All tests pass with zero warnings/errors.

## Closure receipt — 2026-09-27

The two integration gaps previously recorded here are now closed on `main`:

1. `review_admin.approve_relation_candidate()` records an explicit
   `RELATION_CANDIDATE/APPROVED` review event through
   `QueueRuntimeStore.approve_relation_candidate_with_review()` and schedules
   re-analysis for both endpoint claims.
2. `public_projection.PublicProjectionStore.projectable_findings()` joins approved
   relation candidates to the append-only review ledger, requires the related endpoint
   to have a published finding, and omits later rejected/superseded approvals.

The MiniPC runtime schema already has `policy_version =
relation-publication-v1` and the bounded status/relation-type constraints. Focused
MiniPC validation on `test_relation_policy`, `test_review_admin`, and
`test_public_projection` passes 48/48. The production relation table currently has
zero rows, so no production relation was fabricated merely to obtain a green receipt.
