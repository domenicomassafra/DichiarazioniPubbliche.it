# Dichiarazioni Pubbliche — Master Plan to Stable v1

Status: canonical  
Plan version: 1.2
Last updated: 2026-10-05

This is the single ordered execution map for the project. Detailed implementation specs
live in `docs/tickets/`. Historical roadmap files are evidence, not competing backlogs.

## Status vocabulary

- **DONE** — merged, tested, and runtime-proved where required.
- **IN PROGRESS** — currently being implemented.
- **READY** — no known prerequisite blocks execution.
- **BLOCKED** — cannot honestly complete because an explicit prerequisite is unavailable.
- **FUTURE** — intentionally sequenced after earlier milestones.

## Baseline entering this plan

The following capabilities already exist and are treated as the starting baseline, not
as work to redo:

- source registry, scheduler, PostgreSQL queue, worker leases/retries/blocked states;
- platform transcript/caption acquisition and canonical transcript runtime;
- remote-ASR adapter with credential-gated live execution;
- claim-window planning and schema-constrained claim extraction runtime;
- evidence source registry, safe fetch/cache, structured official queries;
- evidence observations and explicit approval ledger;
- deterministic verification and append-only finding drafts;
- non-biometric speaker provenance and review;
- relation candidates and re-analysis triggers;
- fail-closed finding-versioned JSON/JSON-LD/HTML public projection;
- append-only right-of-reply and correction publication lifecycle;
- adversarial provenance/security hardening and MiniPC runtime acceptance.

Current known external blockers remain explicit:

- live claim extraction: official OmniRoute tiered path must pass a meaningful canary;
- remote ASR: Groq credential must exist before a paid/live receipt can be produced.

## Coordination receipt — 2026-09-24

The Orca run `run_e13b22f040ce` delivered implementation-ready specification packets
for these ticket groups:

- M2: DP-205 through DP-208;
- M3: DP-301 through DP-307;
- M4: DP-402 through DP-410 and DP-412;
- M6: DP-601 through DP-607;
- M7: DP-701 through DP-705.

The table statuses below remain implementation/readiness statuses; delivering a
specification packet does not mark its ticket `DONE` or provide runtime proof. The
original S5 coordination packet for DP-501 through DP-508 was later superseded by the
implemented M5 control surfaces and receipts recorded in those ticket files. The
historical I1 claim-contract dispatch produced no result; its work was subsequently
implemented through the main repository flow rather than inferred from that failed
dispatch. No external or user-owned Orca terminal was released during this receipt.
A fresh read-only MiniPC check on 2026-09-24 confirmed
host `udodo`, the `/home/udodo/src/DichiarazioniPubbliche.it` mirror, and the
`dichiarazioni-pubbliche-source-poll`, `dichiarazioni-pubbliche-worker`, and `dichiarazioni-pubbliche-health` timers; this is
runtime availability evidence only, not a deployment or feature-completion claim.

## Milestone graph

```text
M0 Governance baseline
      |
      v
M1 Domain + schema convergence
      |
      v
M1R Research corpus + knowledge convergence ---> M2 Live pipeline readiness
      |                                               |
      +-----------------------+-----------------------+
                         v
                 M3 Editorial/legal policy
                         |
                         v
                 M4 Public product/API
                         |
                         v
                 M5 Reliability/security
                         |
                         v
                 M6 OSS/release hardening
                         |
                         v
                     M7 Stable v1
```

M1, additive M1R work, and the unblocked parts of M2 may proceed in parallel where their
contracts do not collide. M1R is the current product-architecture priority: do not start
mass ingestion or further broad Studio/public visual polishing until the research-corpus
tracer bullet is usable. M3 must settle publication and legal contracts before the public
product is considered launchable. Existing M4 public prototypes remain valid evidence,
but Studio implementation is downstream of M1R.

---

## M0 — Governance and architecture baseline

Goal: one source of truth for product, domain, architecture, contribution, and planning.

| Ticket | Status | Description | Depends on |
|---|---|---|---|
| DP-001 | DONE | Establish canonical OSS/governance surface | baseline |
| DP-002 | DONE | Reconcile historical docs against canonical contracts | DP-001 |
| DP-003 | DONE | Architecture deepening review of current modules | DP-001 |
| DP-004 | DONE | Convert accepted architecture findings into ADRs/refactor tickets | DP-003 |

Exit criteria: a new contributor can determine product rules, architecture, setup,
current plan, and contribution/security process without reading chat history or the old
mega-handoff.

---

## M1 — Domain and schema convergence

Goal: stabilize the core temporal public-record model before public API/frontend work.

| Ticket | Status | Description | Depends on |
|---|---|---|---|
| DP-101 | DONE | Role intervals + organizations with provenance | M0 |
| DP-102 | DONE | Atomic Claim contract v1 and claim-type taxonomy convergence | M0 |
| DP-103 | DONE | Finding/assessment/publication vocabulary convergence | DP-102 |
| DP-104 | DONE | Longitudinal relation approval/publication policy | DP-102, DP-103 |
| DP-105 | DONE | Public schema v1 compatibility contract | DP-101..104 |
| DP-106 | IN PROGRESS | Migration strategy from `*.v0` schema/config names; v1 primary, v0 config fallback window through at least 2026-10-04 | DP-101..105 |
| DP-107 | FUTURE | Deepen concrete PostgreSQL persistence modules | DP-101..106 |
| DP-108 | FUTURE | Separate worker orchestration from domain job handlers | DP-107 |
| DP-110 | DONE | Evidence-based reasoned inference candidates, private/review-only | DP-102, DP-103 |
| DP-111 | DONE | First-class written-source claim provenance without fake timestamps | DP-102, DP-105 |

Exit criteria: domain vocabulary, SQL schema, runtime types, tests, and public projection
use one coherent set of concepts; no important public contract relies on a known
temporary field such as timeless `person.public_role`.

---

## M1R — Research corpus and knowledge convergence

Goal: make Dichiarazioni Pubbliche a provenance-first research corpus before it is a fact-check
pipeline, while preserving the existing Atomic Claim -> Evidence -> Finding boundary.

| Ticket | Status | Description | Depends on |
|---|---|---|---|
| DP-112 | DONE | First-class Research Corpus domain contract | M1 baseline |
| DP-113 | DONE | Additive persistence for captures, passages, collections and candidates | DP-112 |
| DP-114 | DONE | Entity, Topic and Event resolution with reviewable match candidates | DP-113 |
| DP-115 | DONE | Proposition clustering + source derivation/independence relations | DP-113, DP-114 |
| DP-116 | DONE | PostgreSQL-first corpus search and similarity contract | DP-113 |
| DP-117 | DONE | Explicit candidate -> Atomic Claim promotion contract | DP-113, DP-115 |
| DP-118 | DONE | Corpus rights, retention, replay and capture lifecycle | DP-113 |

Exit criteria: a private Research Collection can persist immutable captured versions and
passages, resolve entities without silent merges, triage statement/claim candidates,
deduplicate/cluster candidates, search the corpus, and promote a reviewed candidate into
the existing Atomic Claim model without any public side effect.

---

## M2 — Live pipeline readiness and source coverage

Goal: prove that real configured sources can traverse the full pre-publication pipeline
without manual DB surgery.

| Ticket | Status | Description | Depends on |
|---|---|---|---|
| DP-201 | BLOCKED | Official OmniRoute meaningful canary + cost gate | official provider path |
| DP-202 | BLOCKED | One parent claim canary + Giuliani benchmark | DP-201 |
| DP-203 | BLOCKED | Controlled claim-extraction fan-out | DP-202 |
| DP-204 | BLOCKED | First live remote-ASR receipt and fallback acceptance | Groq credential |
| DP-205 | DONE | Daily/full-source polling mode with bounded coverage | M0 |
| DP-206 | DONE | Add second and third source families without code duplication | DP-205 |
| DP-207 | READY | Timestamped claim acceptance across real content | DP-202 or deterministic fixture path |
| DP-208 | FUTURE | Diarization benchmark and go/no-go decision | DP-204, DP-207 |
| DP-209 | DONE | Bounded research discovery runs + query manifests | DP-113, DP-205, DP-206 |
| DP-210 | DONE | Capture/preservation/parser pipeline | DP-113, DP-118, DP-209 |
| DP-211 | DONE | Passage -> statement/entity/claim candidate extraction | DP-114, DP-210 |
| DP-212 | DONE | Candidate dedupe, matching and proposition clustering runtime | DP-115, DP-116, DP-211 |
| DP-215 | IN_PROGRESS | Source Intelligence + contextual evidence suitability/requirements; no global source scores | DP-102, DP-113, DP-115, DP-118, DP-209, DP-210 |
| DP-213 | DONE | Coverage-needs planner for missing primary/original/independent material | DP-211, DP-212, DP-215 |
| DP-214 | FUTURE | Garlasco Research Collection tracer-bullet corpus | DP-209..213, DP-215, DP-117 |
| DP-216 | READY | Exact quote/source-span binding; model output can never be quotation authority | DP-111, DP-210; coordinate DP-207/DP-305 |
| DP-217 | READY | Transcript reliability tiers + human/audio verbatim review gate | DP-204/DP-207 where live; fixture lane independent |
| DP-218 | READY | Speaker-attribution proof must cover the exact quoted/claimed span | DP-114, DP-207, ADR 0003 |
| DP-219 | FUTURE | Reported speech/nested quotation + original-quote-origin separation | DP-216, DP-218, DP-211 |
| DP-220 | FUTURE | Context-integrity / semantic-clipping guard for public statements | DP-216, DP-217, DP-219 |
| DP-221 | FUTURE | Original wording vs paraphrase/summary/translation separation | DP-216 |
| DP-222 | FUTURE | Public-attribution Person identity + same-name/role-at-time gate | DP-101, DP-114, DP-216, DP-218 |
| DP-223 | FUTURE | False-attribution/fabricated-quote adversarial benchmark; zero known public escapes | DP-216..222 |

Exit criteria: at least three source families run through the same contracts; provider
failure remains a blocked state; any diarization adoption is evidence-driven and never
used as biometric identity; evidence suitability is contextual and inspectable rather than
a global source score; direct quotations are source-span bound rather than model-authored;
speaker/person/context/wording derivation are fail-closed and reviewable; the adversarial
attribution benchmark has zero known public false-attribution/fabricated-quote escapes; and
the corpus-native path has one real bounded collection that can be replayed without
duplicate records or public side effects.

---

## M3 — Editorial, correction, privacy, and legal policy

Goal: settle the rules that determine what may become public and how challenges are
handled before opening the product to users.

| Ticket | Status | Description | Depends on |
|---|---|---|---|
| DP-301 | IN PROGRESS | Intentionality/"lie" policy: default no-intent assessment | M0 |
| DP-302 | IN PROGRESS | Right-of-reply public intake threat model + abuse controls | M0 |
| DP-303 | IN PROGRESS | Correction/takedown/appeal public workflow | DP-302 |
| DP-304 | IN PROGRESS | Privacy/minimization and sensitive-person policy | M0 |
| DP-305 | IN PROGRESS | Copyright/transcript excerpt publication policy | M0 |
| DP-306 | READY | Legal research closure checklist for Italy/EU launch | DP-301..305 |
| DP-307 | FUTURE | Qualified legal review and resulting ADR/policy changes | DP-306 |
| DP-308 | FUTURE | Publication evidence invariants + fail-closed safety profile; no confidence score | DP-215, DP-216..223, DP-301..305 |
| DP-309 | FUTURE | High-risk assertion/legal-status escalation gate | DP-215, DP-304, DP-306, DP-308; DP-307 for launch |
| DP-310 | FUTURE | Independent/dual-control publication review for HIGH/LEGAL records | DP-308, DP-309 |

Exit criteria: public submission and publication behavior have explicit policy, abuse,
privacy, retention, appeal and evidence-safety rules; high-risk assertions cannot bypass
stronger evidence/review gates; publication eligibility is an inspectable conjunction of
required proofs rather than model confidence; unresolved legal questions are either closed
or documented as launch blockers.

---

## M4 — Public product, API, and hosting

Goal: expose the public record through stable, accessible, cacheable surfaces with no
LLM in the request path.

| Ticket | Status | Description | Depends on |
|---|---|---|---|
| DP-400 | DONE | Competitive UX research + dual-surface design brief | M0 |
| DP-401 | DONE | Static-first hosting/deploy contract for public projection | DP-105 |
| DP-402 | DONE | Read-only HTTP API implementation over public schema v1 | DP-105, DP-401 |
| DP-403 | DONE | OpenAPI + examples + API versioning/deprecation policy | DP-402 |
| DP-404 | DONE | `llms.txt` and agent-oriented public data documentation | DP-403 |
| DP-405 | DONE | Person archive UI | DP-105, DP-425 |
| DP-406 | FUTURE | Topic dossier UI | DP-430, DP-425 |
| DP-407 | FUTURE | Content/source-locator UI | DP-207, DP-105, DP-425 |
| DP-408 | READY | Trace/longitudinal relation UI | DP-104, DP-105, DP-425 |
| DP-409 | FUTURE | Public search/indexing without new infra by default | DP-405..408, DP-425 |
| DP-410 | FUTURE | Accessibility/performance/SEO acceptance | DP-405..409, DP-422, DP-425..429 |
| DP-411 | DONE | Generate and compare five researched visual systems against UX v2 | DP-413 |
| DP-412 | DONE | Consolidate winning visual language into design tokens/components | DP-411 |
| DP-413 | DONE | Simplify Public/Studio IA to 5 + 2 templates before implementation | DP-400 |
| DP-414 | FUTURE | Studio IA v3: Corpus, Inbox, Collections and Verify workspaces | DP-112, DP-113 |
| DP-415 | FUTURE | Corpus search/filter/query workspace | DP-116, DP-414 |
| DP-416 | FUTURE | Research Collection workspace | DP-113, DP-114, DP-414 |
| DP-417 | FUTURE | Discovery Inbox triage and duplicate/coverage queues | DP-209, DP-212, DP-414 |
| DP-418 | FUTURE | Candidate promotion + proposition-cluster review UX | DP-117, DP-212, DP-414 |
| DP-419 | FUTURE | Source/capture/passage provenance inspector | DP-210, DP-414 |
| DP-420 | FUTURE | Garlasco operator usability and search-recall acceptance | DP-214, DP-415..419 |
| DP-421 | FUTURE | Public case/collection view contract decision | DP-214, M3, DP-420 |
| DP-422 | FUTURE | Public Product Architecture v3 route/template migration + legacy cutover integration | DP-405..409, DP-426..429 |
| DP-423 | DONE | Public product-marketing + brand context | DP-400, DP-413 |
| DP-424 | DONE | Public visual redesign v4 concept selection | DP-423, DP-412 |
| DP-425 | DONE | Public design system v2 + component contract | DP-424 |
| DP-426 | DONE | Home + public shell v4 | DP-425 |
| DP-427 | DONE | Canonical Statement page v4 | DP-425, DP-105 |
| DP-428 | DONE | Method + trust/utility document pages v4 | DP-425 |
| DP-429 | FUTURE | Explore page v4 | DP-409, DP-425 |
| DP-430 | READY | First-class public Topic resource contract | DP-105, DP-114 |
| DP-431 | FUTURE | Correction/retraction propagation across all public pages/API/search/metadata | DP-303, DP-402/403, DP-405..409, DP-422, DP-427..429 |
| DP-432 | FUTURE | Public trust/provenance disclosure integration for Statement + Method | DP-216..223, DP-308, DP-427, DP-428 |

Exit criteria: public pages and API read only approved projection data, are useful with
providers offline, expose provenance/correction history without private raw content, and
cannot serve stale attribution/wording from a derived page, index or metadata surface after
a correction/hold.
The Studio exit additionally requires the corpus/query/candidate workflow to operate on
persisted records rather than demo-only state.

---

## M5 — Reliability, security, operations, and data lifecycle

Goal: make unattended operation and recovery boring and measurable.

| Ticket | Status | Description | Depends on |
|---|---|---|---|
| DP-501 | IN PROGRESS | Threat model and security regression matrix | M0 |
| DP-502 | IN PROGRESS | Backup/restore drill for PostgreSQL + public projection | DP-501 |
| DP-503 | IN PROGRESS | Retention matrix for raw media/transcripts/evidence/cache | DP-304, DP-305 |
| DP-504 | IN PROGRESS | Operational SLOs and health/error taxonomy | M0 |
| DP-505 | IN PROGRESS | Alert/digest acceptance and operator runbook | DP-504 |
| DP-506 | IN PROGRESS | Cost budget policy + provider outage drills | DP-504 |
| DP-507 | FUTURE | AuthN/AuthZ/CSRF design for any future admin HTTP surface | only when such surface exists |
| DP-508 | FUTURE | Public intake rate limiting/spam controls runtime | DP-302, public intake implementation |
| DP-509 | DONE | Harden claim/ASR/verification provenance inputs | M0 baseline |
| DP-510 | FUTURE | Targeted provenance quarantine + emergency public hold/unhold | DP-308; coordinate DP-501/504/505/431 |
| DP-511 | FUTURE | Source drift/supersession/rights-expiry revalidation watch | DP-210, DP-215, DP-308, DP-510 |

Exit criteria: restore is tested, retention is explicit, source/provider failure is
observable, budget cannot explode, public/admin trust boundaries have tests, a known-bad
provenance dependency can be quarantined without destroying history, and material source
drift/supersession cannot silently leave stale public output online.

---

## M6 — Open-source and release hardening

Goal: make the repository genuinely forkable, reviewable, and releasable by people who
are not the original author.

| Ticket | Status | Description | Depends on |
|---|---|---|---|
| DP-601 | IN PROGRESS | Package/development environment cleanup beyond POC naming | M1 |
| DP-602 | IN PROGRESS | CI matrix and deterministic contributor acceptance | DP-601 |
| DP-603 | IN PROGRESS | Fixture/data licensing inventory and attribution | M3 |
| DP-604 | IN PROGRESS | Release/versioning/changelog policy and release checklist | DP-601, DP-602 |
| DP-605 | IN PROGRESS | Maintainer/contributor documentation dry-run from clean clone | DP-001, DP-601 |
| DP-606 | FUTURE | Public issue labels/project automation once remote exists | GitHub remote |
| DP-607 | FUTURE | Optional SDK/MCP/skill only after HTTP contract is stable | DP-403 |

Exit criteria: clean clone -> tests -> local demo is documented and reproducible; code,
fixtures, and third-party attributions are publishable under explicit terms.

---

## M7 — Stable v1 launch

Goal: first release that can be operated publicly without calling the code a prototype.

| Ticket | Status | Description | Depends on |
|---|---|---|---|
| DP-701 | IN PROGRESS | Dichiarazioni Pubbliche naming + technical rename approved locally; external clearance/runtime proof open | M4 |
| DP-702 | FUTURE | Pre-launch legal/security/privacy/evidence-safety review closure | DP-301..310, DP-501..511 |
| DP-703 | FUTURE | Production dataset/source launch set and disclosure | M2, M3 |
| DP-704 | FUTURE | End-to-end launch rehearsal from source to correction | M2..M6 |
| DP-705 | FUTURE | v1.0.0 release and public deployment | DP-701..704 |

Stable v1 requires all launch blockers closed; it does not require every FUTURE business
feature (BYOK, paid API, subscriptions, MCP, etc.).

---

## Explicitly post-v1 unless evidence changes priority

- BYOK and managed LLM quotas;
- paid/bulk/realtime API tiers;
- user accounts unrelated to reply/correction intake;
- MCP/agent skill beyond stable public API docs;
- dedicated graph/vector databases;
- generalized crawling of the whole web;
- international expansion beyond bounded high-value exceptions.

## Working rule

Do not select the next task by whichever file was most recently edited. Select the first
READY ticket whose dependencies are satisfied and whose milestone is currently active.
BLOCKED tickets stay blocked without workaround-by-quality-regression.
