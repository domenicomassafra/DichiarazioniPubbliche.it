# Historical Document Reconciliation — 2026-09-22

Ticket: DP-002

This matrix classifies the numbered documents that predate the canonical root contracts.
They remain useful evidence and should not be deleted simply because a decision evolved.

| Document | Classification | Current authority / next action |
|---|---|---|
| `00-product-vision.md` | Superseded product draft | `PRODUCT.md` |
| `01-research-ecosystem.md` | Research reference | Preserve; cite when evaluating ecosystem/donors |
| `02-architecture-hypotheses.md` | Superseded architecture draft | `ARCHITECTURE.md`, ADRs |
| `03-licensing-commercialization.md` | Research + partially superseded | Code license resolved by ADR 0005; business models remain post-v1 context |
| `04-legal-safety-research.md` | Active research input, not legal advice | DP-301..DP-307 |
| `05-agent-discoverability-and-access.md` | Future product/reference | DP-403, DP-404, DP-607 |
| `06-data-model-and-taxonomy.md` | Historical domain draft | `CONTEXT.md`, DP-101..DP-104 |
| `07-roadmap-open-questions.md` | Superseded backlog | `PLAN.md` |
| `08-deep-landscape-audit.md` | Research reference | Preserve; not architecture authority |
| `09-sideproject-operating-model.md` | Operational design input | Principles absorbed into `PRODUCT.md`/`ARCHITECTURE.md`; detailed reference remains useful |
| `10-adoption-matrix.md` | Donor/reference evidence | Preserve; apply license/provenance rules in `CONTRIBUTING.md` |
| `11-product-positioning-marketing.md` | Positioning/reference | Revisit near M7; not implementation authority |
| `12-source-level-donor-audit.md` | Donor/provenance research | Preserve for clean-room/license evidence |
| `13-dvns-sister-platform-integration.md` | Deferred integration design | Post-v1 unless promoted by `PLAN.md` |
| `14-donor-extraction-map.md` | Donor implementation research | Preserve; not a mandate to copy code |
| `15-poc-benchmark-v0.md` | Benchmark design/receipt | Current deterministic tests/benchmark are executable authority |
| `16-content-audit-raffagiulians-bollo.md` | Content-audit/benchmark receipt | Inputs DP-202 and future ContentAudit UI |
| `17-transcription-quality-and-routing.md` | Historical runtime design | Current config/runtime/tests; DP-204/DP-208 for live/future work |
| `18-storage-retention-and-open-data.md` | Historical design input | `ARCHITECTURE.md`, DP-503, DP-105 |
| `19-deployment-scaling-sources-and-ux.md` | Historical design input | `ARCHITECTURE.md`, DP-205/206, M4 |
| `20-canonical-transcript-and-postgres-v0.md` | Implementation receipt | Current schema/migrations/tests |
| `21-brand-naming-v0.md` | Current working-brand research | Working brand remains Dichiarazioni Pubbliche; clearance/rename DP-701 |
| `22-runtime-scheduler-and-omniroute-canary.md` | Operational receipt | Current blocker/ticket authority DP-201..DP-203 |
| `23-claim-extraction-benchmark-and-pulp-scaffold.md` | Operational/benchmark receipt | DP-201..DP-203 |
| `24-processing-worker-costs-and-health-v0.md` | Implementation/operations receipt | Current runtime/tests; future ops DP-504..DP-506 |
| `25-official-evidence-runtime-v1.md` | Implementation receipt | Current evidence runtime/tests |
| `26-deterministic-verification-reanalysis-v1.md` | Implementation receipt | Current verification/reanalysis runtime/tests |
| `27-speaker-provenance-public-projection-v1.md` | Implementation receipt | PRODUCT/ADR 0001/0003 + current runtime/tests |
| `28-claimreview-correction-reply-policy-v1.md` | Implementation/policy receipt | Current runtime/tests; public intake DP-302/303 |
| `29-data-provenance-security-hardening-v2.md` | Latest pre-governance runtime receipt | Current security/provenance baseline; `SECURITY.md`, DP-501+ |

## Open questions extracted into the canonical plan

The following previously scattered questions now have explicit tickets:

- role history / organizations -> DP-101;
- claim taxonomy -> DP-102;
- finding vocabulary -> DP-103;
- relation publication -> DP-104;
- stable public schema/API -> DP-105, DP-402/403;
- package/v0 naming -> DP-106/DP-601;
- live OmniRoute claim extraction -> DP-201..DP-203;
- live ASR/diarization -> DP-204/DP-208;
- public reply/correction intake and abuse -> DP-302/303/508;
- intentionality policy -> DP-301;
- privacy/copyright/legal launch work -> DP-304..DP-307;
- frontend/public surfaces -> DP-405..DP-410;
- backup/retention/ops/security -> DP-501..DP-508;
- OSS release hardening -> DP-601..DP-607;
- brand/legal/launch closure -> DP-701..DP-705.

No open item in the historical roadmap should now be worked directly without mapping it
to `PLAN.md` first.
