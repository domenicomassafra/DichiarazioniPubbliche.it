# Master Plan Autoplan Review — 2026-09-22

Scope: `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md`, `PLAN.md`, OSS/governance surface.  
Mode: single-agent adaptation of the autoplan review sequence. No independent subagents
were used in this pass; findings are therefore not represented as multi-model consensus.

## Phase 1 — Product / premise challenge

### Premise 1: "We need to rewrite the system from scratch"

**Rejected.** The implemented pipeline already has strong provenance, replay, review, and
publication invariants with 185 regression tests and MiniPC receipts. A greenfield rewrite
would destroy validated behavior without proving a better product.

Decision: preserve the working baseline; refactor only where module depth/locality review
found real friction (ADR 0006, DP-107/108).

### Premise 2: "Automation means no human gates"

**Rejected.** Routine operation should be automatic, but required review/policy decisions
cannot be bypassed. If the gate cannot be satisfied, the product under-publishes.

Decision: `PRODUCT.md` explicitly defines automation as low-maintenance operation, not
permission to auto-publish.

### Premise 3: "Fact-checking is the whole product"

**Rejected.** The durable differentiator is a temporal public-record system with
provenance, corrections, longitudinal relations, and machine-readable output. Atomic
fact-checking is one capability inside that record.

Decision: product surfaces and domain model are centered on the record, not an LLM verdict.

### Premise 4: "All historical open questions belong in the current backlog"

**Rejected.** Monetization, MCP, dedicated graph/vector infrastructure, broad web crawling,
and international expansion are post-v1 unless evidence changes priority.

Decision: `PLAN.md` explicitly separates v1 from post-v1 scope.

### Error & rescue registry

| Failure | Unsafe rescue | Safe behavior |
|---|---|---|
| Claim provider route unavailable | switch model/runtime silently | BLOCKED ticket/job; wait for approved path |
| ASR credential missing | fabricate/local-substitute acceptance | BLOCKED; bounded canary after credential |
| Speaker ambiguous | infer identity from face/voice | hold publication |
| Evidence incomplete/conflicting | lower threshold | unresolved / needs more evidence |
| Review stale after provenance change | keep old public dossier | omit until re-reviewed |
| Budget exhausted | use cheaper unsupported verdict | defer/block work |
| Source adapter breaks | stop all ingestion | mark source degraded, isolate failure |
| Legal/public intake unresolved | launch anyway | treat as launch blocker |

## Phase 2 — Product/design review

UI implementation is not yet the active milestone, but the product surfaces are now
clear enough to prevent backend-first drift.

### Design decisions

- Person, Topic, ContentAudit, and Discrepancy are distinct views over the same public
  schema, not separate data silos.
- Evidence/provenance must be inspectable without dumping raw operational content.
- Corrections/replies must be visible as history, not replacement text.
- No numeric person rating is allowed in UI or Schema.org mapping.
- UI prototypes may proceed against fixtures before legal closure, but public launch may
  not bypass M3.

### Remaining design work

The final visual pattern is intentionally deferred to DP-405..DP-410. Existing comparative
prototypes remain research inputs, not an accidental design system.

## Phase 3 — Engineering review

### Architecture

```text
external sources
   -> ingestion/transcript/identity
   -> claims/evidence/observations
   -> deterministic verification
   -> finding + explicit review
   -> fail-closed public projection
   -> static/read-only public product
```

The plan correctly stabilizes domain/schema contracts before structural refactors. This
avoids changing persistence boundaries twice.

### Test map

```text
source/discovery       -> test_source_watcher, test_scheduler*
transcript/ASR         -> test_caption_adapter, test_platform_transcript,
                          test_remote_asr, test_transcript_contract
claims                 -> test_claim_windows, test_claim_runtime,
                          test_claim_extraction_benchmark
evidence               -> test_evidence_runtime/query/extract
verification/findings  -> test_verification_runtime, test_finding_runtime
review/publication     -> test_review_admin, test_public_projection,
                          test_correction_runtime
queue/worker/ops       -> test_queue_runtime, test_worker_daemon,
                          test_health_digest, test_retention
cross-boundary attacks -> test_adversarial_ingestion, schema contract tests
```

### Engineering findings

1. **Strong:** stabilize public schema before HTTP API/frontend (`DP-105 -> M4`).
2. **Strong:** do not split the public projection; it is a deep security boundary.
3. **Strong:** narrow PostgreSQL/worker modules after M1, not before (`DP-107/108`).
4. **Strong:** package/POC naming cleanup belongs after domain contract convergence
   (`DP-106`, `DP-601`).
5. **Strong:** live provider benchmarks must not gate deterministic contributor CI.

### Failure-mode completeness

Critical classes are represented in tickets: provider outage, cost, source degradation,
stale review, private-data leak, unsafe fetch, restore/retention, public intake abuse,
legal uncertainty, and schema compatibility.

No new infrastructure requirement was found.

## Phase 3.5 — Developer experience review

### Contributor journey

| Stage | Current state | Planned improvement |
|---|---|---|
| Understand product | canonical README/PRODUCT | maintain with release changes |
| Understand domain | CONTEXT | converge M1 vocabulary |
| Understand architecture | ARCHITECTURE + ADRs | DP-003/004 complete |
| Pick work | PLAN + tickets | public issue sync later |
| Set up | Python commands documented | DP-601 package/dev cleanup |
| Test | deterministic no-key suite | DP-602 CI hardening |
| Review | spec + standards + PR template | retain |
| Runtime proof | AGENTS + ticket-specific MiniPC gate | retain |
| Release | currently pre-1.0 | DP-604 release checklist |

### DX findings

- No paid key is required for the default test suite: good.
- `PYTHONPATH=poc` and the `dichiarazioni_pubbliche` POC name are acceptable pre-1.0 but not a
  stable contributor experience: already ticketed.
- A public security contact and final repository URL cannot be truthfully documented
  before the remote/public launch exists: keep explicit placeholders/policy, close before
  M7.
- Clean-clone onboarding should be tested by someone/something other than the original
  working checkout at DP-605.

## Cross-phase themes

### Fail closed is both product and engineering architecture

It appears independently in provider handling, speaker attribution, evidence review,
publication, privacy, legal launch gates, and cost controls. This is the project's main
cross-cutting principle and should remain visible in code review.

### Stable contracts before scale

Domain/schema/public contracts precede refactor, HTTP API, frontend, and broad source
fan-out. This reduces expensive compatibility churn.

### Public record, not political scoring

Product, schema, JSON-LD, UI, and API all need the same constraint. It cannot be treated
as a copywriting rule applied at the end.

## Decision audit trail

| # | Phase | Decision | Rationale |
|---|---|---|---|
| 1 | Product | Reject greenfield rewrite | validated baseline has stronger evidence than aesthetic redesign |
| 2 | Product | Keep automation fail-closed | routine autonomy must not bypass publication policy |
| 3 | Product | Keep monetization/post-v1 extras out of v1 | reduce scope and maintenance burden |
| 4 | Eng | M1 contracts before DP-107/108 | avoid refactor/schema churn |
| 5 | Eng | Keep projection deep | one centralized publication boundary has better locality/security |
| 6 | Eng | Stable public schema before API/UI | one compatibility surface for all clients |
| 7 | DX | Deterministic tests require no paid providers | fork/contributor friendliness |
| 8 | DX | Defer package rename cleanup to contract convergence | avoid premature cross-cutting rename |

## Gate result

The plan is coherent enough to execute. There is no justification to resume feature-wave
development outside the ticket graph. The next active work after governance closure is
M1, beginning with DP-101/DP-102 unless the owner explicitly reprioritizes a READY ticket.
