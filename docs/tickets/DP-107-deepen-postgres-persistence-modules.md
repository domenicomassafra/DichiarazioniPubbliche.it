# DP-107 — Deepen PostgreSQL persistence modules

Status: IN PROGRESS
Milestone: M1
Depends on: DP-101..DP-106

## Problem

`QueueRuntimeStore` exposes unrelated queue, transcript, claim/evidence, verification,
review, correction, and publication mutations through one broad class.

## Outcome

Split the concrete PostgreSQL persistence surface into a small set of deep domain stores
sharing the existing execution primitive, without introducing speculative repository
interfaces or changing behavior.

## Acceptance criteria

- queue execution/cost operations have a narrow store;
- transcript/canonical-segment operations have a narrow store;
- claim/evidence/observation operations have a narrow store;
- review/finding/reanalysis/reply/correction operations have a narrow store;
- SQL transactions that enforce one invariant remain atomic and co-located;
- no generic repository/protocol layer is added without a second backend;
- existing test suite remains green plus focused store contract tests;
- schema/public behavior unchanged;
- MiniPC worker/review/runtime acceptance passes.

## Non-goals

Changing database technology, adding an ORM, rewriting SQL, or redesigning the domain.

## Progress — 2026-10-05

The first dependency-safe tranche establishes `QueueExecutionCostStore` as a concrete,
narrow PostgreSQL boundary for processing-job execution and provider-cost accounting. It
inherits the existing `PsqlRuntime` primitive and binds the current `QueueRuntimeStore`
method objects directly, so the SQL and behavior still have one definition while the
legacy file is under concurrent modification. Focused contract tests prove the narrow
surface, exact method/signature reuse, and execution through the inherited runtime seam.
Local proof on the shared checkout after four preparatory store boundaries:
`tests.test_queue_store` 14/14,
`tests.test_queue_runtime` 15/15, and `tests.test_worker_daemon` 21/21 pass; full
`compileall` over `poc`/`tests` and `git diff --check` also pass.

This is preparatory proof for the first acceptance criterion, not its final migration:
the SQL method bodies and production callers still live on/use `QueueRuntimeStore`. Once
that file is clean, the method bodies can move mechanically into `QueueExecutionCostStore`
and the legacy store can delegate to it before callers are migrated.

## Progress — 2026-10-06

The first real method-body migration is now complete for the clean queue-execution
lifecycle cluster. Source/AST comparison against `HEAD` proved that `reap_expired`,
`claim`, `renew`, `complete`, `retry`, `defer`, `block`, `enqueue_followup`,
`enqueue_jobs_bulk`, `unfinished_sibling_jobs`, and `state_counts` had no concurrent
changes. Their unchanged bodies and SQL now live in `QueueExecutionCostStore`, while the
same-signature `QueueRuntimeStore` entry points delegate to that narrow store for backward
compatibility. An AST body comparison against the pre-move methods is identical for all
11 methods, and the processing-job lifecycle SQL occurs only in `queue_store.py`.

The cost/operation-ledger side of `QueueExecutionCostStore` remains preparatory because
`cost_snapshot`, `operation_ledger_receipts`, `operation_ledger_summary`, and
`record_receipt` are concurrently modified by DP-230 work in the shared checkout. Those
four methods therefore still bind the live `QueueRuntimeStore` definitions, preserving a
single SQL definition without overwriting the in-flight ledger changes. Acceptance
criterion 1 and production-caller migration remain open until that cost/ledger ownership
move and MiniPC runtime acceptance are complete.

Local proof for this tranche: `tests.test_queue_store` 15/15,
`tests.test_queue_runtime` 15/15, and `tests.test_worker_daemon` 21/21 pass; full
`compileall` over `poc`/`tests` and `git diff --check` also pass.

The transcript/canonical tranche has now advanced from a preparatory binding to a real
method-body migration. A fresh zero-context diff against `HEAD` showed no concurrent
changes in `insert_transcript_variant`, `insert_transcript_segments`,
`transcript_segments`, `canonical_candidate_variant_ids`, `canonical_segments`, or
`upsert_canonical_segments`. Their unchanged bodies and SQL now live in
`TranscriptCanonicalStore`; the same-signature `QueueRuntimeStore` entry points delegate
to that store for compatibility. AST comparison reports identical pre/post move bodies for
all six methods. Transcript/canonical persistence SQL is owned by `queue_store.py`; the
remaining canonical-segment reads in `queue_runtime.py` belong to separate publication
preflight queries rather than duplicate implementations of this store contract.

Focused proof after this move remains green: `tests.test_queue_store` 15/15,
`tests.test_queue_runtime` 15/15, and `tests.test_worker_daemon` 21/21; full `compileall`
over `poc`/`tests` and `git diff --check` pass. Production callers still instantiate the
legacy aggregate store, so caller migration and MiniPC runtime acceptance remain open.

The third dependency-safe tranche establishes `ClaimEvidenceObservationStore` as a
concrete narrow boundary for Atomic Claim persistence/readback, evidence candidates,
evidence observations, evidence-set/source-intelligence assessment, and the resulting
Coverage Need lifecycle. The coverage methods remain in this domain because they persist
the explicit evidence sufficiency gaps emitted by source-intelligence assessment; in
particular, `satisfy_coverage_need` and its original-source preflight remain co-located.
The store inherits `PsqlRuntime` directly, binds the exact current `QueueRuntimeStore`
method objects, and exposes no queue, transcript, review, finding, verification-run,
reanalysis, reply, correction, or publication mutations.

This third boundary now has its first real production caller migration. The clean
`tools/coverage_need.py` operator CLI imports and instantiates
`ClaimEvidenceObservationStore` directly; its four store calls are exactly
`searchable_coverage_needs`, `record_coverage_need_attempt`, `satisfy_coverage_need`, and
`block_coverage_need`, all already exposed by the narrow claim/evidence boundary. The
original-source preflight used by satisfaction remains co-located on the same store. No SQL
was copied and the CLI arguments/output contract is unchanged. The underlying claim/evidence
method bodies remain bound to `QueueRuntimeStore` until a clean cluster can be moved safely,
so this advances caller adoption without claiming full ownership migration.

Focused proof for the caller move: `tests.test_queue_store` is 15/15 PASS,
`tests.test_coverage_needs` plus `tests.test_coverage_original_source_preflight` are 9/9 PASS,
the CLI `--help` path imports/constructs successfully, an AST caller scan shows only the four
claim/evidence coverage methods and no legacy `QueueRuntimeStore` import, and compileall plus
`git diff --check` pass.

That production caller now reaches a real narrow-store implementation rather than a
preparatory binding. A fresh AST comparison against `HEAD` proved the seven coherent
Coverage Need methods unchanged before migration:
`coverage_collection_ids_for_claim`, `upsert_coverage_need`,
`searchable_coverage_needs`, `record_coverage_need_attempt`,
`satisfy_coverage_need`, `coverage_need_original_source_preflight`, and
`block_coverage_need`. Their original method bodies and SQL, including the
`FOR UPDATE`/event-write transactions and original-source satisfaction preflight, now live
in `ClaimEvidenceObservationStore`. `QueueRuntimeStore` preserves the exact method
signatures through SQL-free compatibility delegation. AST body comparison against the
pre-move `HEAD` implementations reports `BODY_EQ` for all seven, and Coverage Need SQL is
present only in `queue_store.py`, so there is no duplicated SQL definition.

`tools/coverage_need.py` remains the clean production caller of the narrow store and calls
only `searchable_coverage_needs`, `record_coverage_need_attempt`,
`satisfy_coverage_need`, and `block_coverage_need`; an AST caller scan confirms it has no
`QueueRuntimeStore` import. Focused proof after the body move is green:
`tests.test_queue_store` **16/16**, Coverage Need/original-source tests **9/9**,
`tests.test_queue_runtime` **15/15**, and `tests.test_worker_daemon` **21/21**; the CLI
`--help` import path also passes. The remaining claim/evidence methods stay bound to the
legacy definitions for a later clean tranche. The four concurrent DP-230 cost/ledger
methods remain untouched.

A subsequent dependency-safe source-assessment tranche moves four additional unchanged
method bodies into `ClaimEvidenceObservationStore`: `claim_context`,
`approved_verification_evidence`, `source_intelligence_relations`, and
`insert_evidence_set_assessment`. These methods form the persisted input/readback and
assessment-write seam used together by `worker_daemon.verify_claim`; the worker keeps its
aggregate store at this point because the same object also participates in queue and review
operations outside this tranche. `QueueRuntimeStore` now preserves the exact signatures
through SQL-free compatibility delegation. AST comparison against the pre-move `HEAD`
implementations reports identical bodies for all four methods, and targeted SQL ownership
checks report zero matching definitions in `queue_runtime.py` and one in `queue_store.py`
for each moved query/write. Focused local proof is green: `tests.test_queue_store`,
`tests.test_queue_runtime`, and `tests.test_worker_daemon` pass **52/52** together. DP-107
remains in progress because the other claim/evidence bodies, cost/ledger ownership,
review/publication body migration, production caller convergence, and MiniPC acceptance are
still open.

The next clean claim/evidence tranche moves the Atomic Claim persistence/readback pair,
`insert_atomic_claims` and `claim_count`, into `ClaimEvidenceObservationStore`. A fresh
comparison against the current shared tree and `HEAD` showed both methods unchanged before
the move. Their original bodies, including deterministic replay rejection and claim-segment
linking in the same `insert_atomic_claims` statement, are preserved in the narrow store
while `QueueRuntimeStore` exposes same-signature SQL-free delegates. AST proof reports
`BODY_EQ_HEAD=True` and `SIG_EQ_LEGACY=True` for both methods; targeted ownership checks
find the Atomic Claim insert/count SQL zero times in `queue_runtime.py` and once in
`queue_store.py`. The focused queue-store/runtime/worker suite remains **52/52 PASS**. No
caller split is introduced because `worker_daemon` still needs the aggregate store across
multiple persistence domains. DP-107 remains in progress pending the remaining
evidence/observation lifecycle bodies, cost/ledger ownership, review/publication body
migration, broader caller convergence, and MiniPC acceptance.

The final clean claim/evidence tranche moves the six remaining non-review
evidence/observation lifecycle methods into `ClaimEvidenceObservationStore`:
`upsert_evidence`, `link_claim_evidence`, `claim_evidence_count`,
`insert_evidence_observation`, `update_evidence_observation_status`, and
`update_claim_evidence_status`. A fresh diff and AST comparison against the current shared
tree and `HEAD` showed all six signatures and bodies unchanged before the move. Their exact
implementations now live in the narrow store, including the fail-closed guards that refuse
`APPROVED` status outside the review-ledger methods; `QueueRuntimeStore` keeps same-signature
SQL-free delegates. The separate `approve_claim_evidence_with_review` and
`approve_evidence_observation_with_review` methods remain outside this store because their
status change and review-event write must stay atomic and co-located.

Post-move AST proof reports `BODY_EQ_HEAD=True`, `SIG_EQ=True`, and SQL-free legacy
delegates for all six methods. Targeted ownership checks find each migrated insert/read or
parameterized non-review status update zero times in `queue_runtime.py` and once in
`queue_store.py`; the remaining approval SQL in the legacy store is intentionally distinct.
The focused `tests.test_queue_store`, `tests.test_queue_runtime`, and
`tests.test_worker_daemon` matrix remains **52/52 PASS**. All methods declared on the
`ClaimEvidenceObservationStore` contract now have real narrow-store bodies rather than
legacy method bindings. DP-107 remains in progress because cost/ledger ownership,
review/publication body migration, broader production caller convergence, and final MiniPC
acceptance are still open.

A fresh production-caller audit found no additional safe `QueueRuntimeStore` caller to
converge after `tools/coverage_need.py`. The five direct construction sites are all
intentionally aggregate workflows:

- `worker_daemon.py` spans queue execution/cost, transcript/canonical, claim/evidence,
  content state, verification/finding and reanalysis methods on one runtime object;
- `review_admin.py` spans claim context, queue enqueueing, identity/provenance review and
  finding/reply/correction publication-review operations;
- `tools/ingest_curated_written_claims.py` passes its store into
  `curated_written_intake.py`, which performs direct source/content/Atomic Claim SQL plus
  text-provenance persistence and optional review-ledger approval;
- `timestamp_acceptance.py` uses direct source/content/transcript/canonical SQL together
  with `insert_atomic_claims` and invariant reads over findings/provider receipts;
- `ops/provider_outage_drill.py` seeds source/content/transcript/queue state, reads claim,
  provider-receipt and finding state, and passes the same store into `ProcessingWorker`.

Replacing any of those constructors with one existing narrow store would therefore retain
cross-domain work behind inherited raw `run`/`run_literal` calls or remove methods the
workflow requires. No caller was changed. A repository scan confirms
`tools/coverage_need.py` remains the only production caller that both instantiates a narrow
store and uses only that store's declared domain methods. Further caller convergence needs
a separately justified workflow split or additional domain store ownership; it is not a
mechanical DP-107 caller substitution.

The fourth dependency-safe tranche establishes `ReviewPublicationDecisionStore` as the
review/publication decision persistence boundary. It groups verification-run persistence,
finding drafts/context/publication, relation/inference candidates and reviewed relation
approval, reanalysis state, generic review-ledger events, right-of-reply state/publication,
and correction state/publication. `publish_finding_with_review` and `finding_context` are
included even though they are physically separated in the legacy class because they are
part of this same decision lifecycle. Claim-evidence and observation approval methods are
not included; they remain owned by the claim/evidence domain.

This preparatory store inherits `PsqlRuntime` directly and binds the
exact current `QueueRuntimeStore` method objects, keeping SQL defined only once. Queue,
transcript, claim/evidence/observation, source-assessment, and coverage operations are not
exposed. Remaining domain method-body moves, cost/ledger ownership, additional production
caller migration, and MiniPC acceptance remain open before DP-107 can be considered complete.

A dependency-safe internal ownership tranche now advances that boundary without touching
the active DP-309/DP-310 finding-publication/review work. A fresh diff against the current
shared tree and `HEAD` showed `insert_relation_candidate`, `insert_inference_candidate`,
`insert_reanalysis_trigger`, and `advance_reanalysis_trigger` unchanged. Their exact method
bodies now live in `ReviewPublicationDecisionStore`; `QueueRuntimeStore` retains
same-signature SQL-free delegates. The relation-candidate insert and reanalysis insert/update
SQL are therefore defined only in `queue_store.py`. `insert_inference_candidate` continues to
use the single canonical `INSERT_INFERENCE_CANDIDATE_SQL_V1` constant from
`inference_repository.py`, with its method body owned only by the narrow store.

This tranche deliberately leaves `approve_relation_candidate_with_review`,
`public_relation_candidates`, `record_review_event`, all finding draft/context/publication
methods, and right-of-reply/correction publication methods on their existing legacy bindings.
`public_relation_candidates` is excluded because it derives eligibility from both the review
ledger and published endpoint findings. Post-move proof reports `BODY_EQ_HEAD=True`,
`SIG_EQ=True`, and SQL-free legacy delegates for all four migrated methods. Focused
queue/reanalysis/relation/inference tests pass **76/76**. DP-107 remains in progress; this
tranche makes no caller split, schema/public-projection change, DP-230 cost/ledger change, or
claim about the still-active publication/review ownership work.

## Local persistence convergence — 2026-10-06

The current shared tree has now converged all dependency-free DP-107 persistence ownership.
`QueueExecutionCostStore` owns the SQL and behavior for all 15 declared queue/cost methods:
the 11 queue lifecycle operations plus `cost_snapshot`, `operation_ledger_receipts`,
`operation_ledger_summary`, and `record_receipt`. The four cost/ledger bodies preserve the
current DP-230 operation-ledger fields, measured-versus-estimated accounting, attempt-scoped
receipts, filters, and validation. `QueueRuntimeStore` keeps same-signature compatibility
entry points that delegate to the narrow store and contain no duplicate queue/cost SQL.

The current store-contract inventory also confirms that the six transcript/canonical methods,
all declared claim/evidence/observation/source-assessment/Coverage Need methods, and all
declared review/finding/reanalysis/reply/correction methods are owned by their corresponding
narrow stores. Atomic claim-evidence and observation approval transactions remain co-located
with their review-ledger write because splitting those transactions would weaken the existing
invariant. The aggregate `QueueRuntimeStore` constructors in worker/review/acceptance workflows
remain appropriate because those callers cross persistence domains; `tools/coverage_need.py`
remains the production caller that can use only the narrow claim/evidence store.

Local proof after convergence: the DP-107/DP-108/operation-ledger/threat focused matrix passes
**83/83**, `python3 -m compileall -q poc tests` passes, the deterministic benchmark passes
**5/5**, and `git diff --check` passes. The repository-wide run executed **1705** tests and
initially exposed two integration failures: the operation-ledger source-owner assertion was
updated to the new narrow store and now passes; the other independently reproduces in
`tests.test_ops_restore_drill` because the concurrent schema contains
`transcript_verbatim_review_event` and `context_integrity_review_event` while the backup
inventory does not yet list them. That restore inventory belongs to the concurrent schema/ops
work and is not changed by DP-107.

DP-107 remains **IN PROGRESS** until the repository-wide restore-inventory integration is green
and the required MiniPC worker/review/runtime acceptance is executed. No Mac-only local proof
is treated as MiniPC acceptance.
