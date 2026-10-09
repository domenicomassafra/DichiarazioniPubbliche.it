# Dichiarazioni Pubbliche — Master Plan to Stable v1

Status: canonical  
Plan version: 1.2
Last updated: 2026-10-07

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
| DP-106 | DONE | Migration from `*.v0` config/schema names completed; MiniPC cutover is v1-only with zero legacy fallback events | DP-101..105 |
| DP-107 | DONE | Deep PostgreSQL persistence converged into narrow domain stores; 92-table restore integration and MiniPC worker/review/runtime acceptance green | DP-101..106 |
| DP-108 | DONE | ProcessingWorker orchestration separated into three cohesive handler families; MiniPC queue/cost/block/review acceptance green | DP-107 |
| DP-109 | DONE | Governed collection-readiness report/CLI; fail-closed provider/capability blockers proven locally and on MiniPC | DP-101..108 |
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
| DP-207 | DONE | Timestamped claim acceptance across real content | DP-202 or deterministic fixture path |
| DP-208 | FUTURE | Diarization benchmark/go-no-go; local metric/safety harness implemented, real reference/model/MiniPC decision remains blocked on DP-204 and runtime gates | DP-204, DP-207 |
| DP-209 | DONE | Bounded research discovery runs + query manifests | DP-113, DP-205, DP-206 |
| DP-210 | DONE | Capture/preservation/parser pipeline | DP-113, DP-118, DP-209 |
| DP-211 | DONE | Passage -> statement/entity/claim candidate extraction | DP-114, DP-210 |
| DP-212 | DONE | Candidate dedupe, matching and proposition clustering runtime | DP-115, DP-116, DP-211 |
| DP-215 | IN PROGRESS | Source Intelligence + contextual evidence suitability/requirements is implemented; AC-215.9 remains blocked because the real reviewed 100-item Garlasco manifest and role/rights/lineage data do not exist; MiniPC read-only readiness (docs/ops/garlasco-research-readiness-20261008.md) confirms 0/5 source families with accepted discovery provenance | DP-102, DP-113, DP-115, DP-118, DP-209, DP-210 |
| DP-213 | DONE | Coverage-needs planner for missing primary/original/independent material | DP-211, DP-212, DP-215 |
| DP-214 | IN PROGRESS | AC-214.3 closed; research:garlasco PAUSED with 18 included, 82 missing, all 18 rights UNKNOWN, zero accepted discovery/capture/passage/candidates; 30/30 baseline claims and private 13/13 Recall@5. Six separate file-only leads are NOT persisted Discovery or authorized Content. Capture/Candidate preflight shares verified run->HEALTHY attempt->query->active manifest->exact-family provenance. Private Candidate commits add same-statement SQL authority fencing for rights, relevance, Capture, Passage and Discovery. Full production SQL CTE batch now verified on isolated MiniPC pg_temp with 4 negative zero-write cases + 1 synthetic full success, provider receipt and claim/statement children atomic, rollback proven; not a globally atomic concurrent-revocation lock (docs/ops/private-candidate-extraction-20261008.md). Real 100-item and remaining acceptance are blocked | DP-209..213, DP-215, DP-117 |
| DP-216 | DONE | Exact quote/source-span binding; human-review/source hashes and bounded discontinuous-span omission disclosure proven fail-closed locally and on MiniPC | DP-111, DP-210; coordinate DP-207/DP-305 |
| DP-217 | DONE | Transcript reliability tiers + persisted human/audio verbatim review gate bound to exact source/canonical hashes and reviewed range | DP-204/DP-207 where live; fixture lane independent |
| DP-218 | DONE | Speaker-attribution proof covers the exact quoted/claimed span; schema/benchmark/MiniPC acceptance complete | DP-114, DP-207, ADR 0003 |
| DP-219 | DONE | Reported speech/nested quotation + original-quote-origin separation, including adversarial release-gate coverage | DP-216, DP-218, DP-211 |
| DP-220 | DONE | Context-integrity / semantic-clipping guard for public statements, including discontinuous/montage fail-closed handling | DP-216, DP-217, DP-219 |
| DP-221 | DONE | Original wording vs paraphrase/summary/translation separation; public serializers/search + DP-305 no-body exact-copy guard proven locally and on MiniPC | DP-216 |
| DP-222 | DONE | Public-attribution Person identity + same-name/role-at-time gate; projection/read-time fail-closed identity/role proof + persisted tamper + MiniPC acceptance complete | DP-101, DP-114, DP-216, DP-218 |
| DP-223 | DONE | False-attribution/fabricated-quote adversarial benchmark; 59-case zero-tolerance gate, persisted full-corpus projection/serializer replay and isolated MiniPC release-candidate attribution-integrity read-back all pass with zero known false attribution/fabricated quote | DP-216..222, DP-224 |
| DP-224 | DONE | Material-assertion citation assurance over approved evidence/passages; exact Passage/source-hash binding + persisted tamper + MiniPC acceptance complete | DP-215, DP-210; coordinate DP-216/DP-308 |
| DP-225 | DONE | Reviewed original-source resolver over approved derivation families; persisted receipt + private Studio inspection proven on MiniPC | DP-115, DP-215 |
| DP-226 | DONE | Compound numerical verification: delta/ratio/percent change + unit/denominator policy; structured-provider fixture + MiniPC proof complete | DP-215 |
| DP-227 | DONE | Effective-time/validity/supersession verification; selectors + reviewed supersession -> persisted reanalysis consumer proven with law/policy/statistical MiniPC canary | DP-215, DP-210 |
| DP-228 | DONE | Claim-specific research-plan compiler with bounded specialist retrieval lanes and fail-closed narrowing query-suggestion seam | DP-213, DP-215, DP-209 |
| DP-229 | IN PROGRESS | Bounded adversarial challenger/counter-case packet | DP-228, DP-215 |
| DP-230 | DONE | Canonical provider-operation receipt + reconstructable cost ledger v2; MiniPC restart/replay canary green | DP-209, DP-211, DP-506 |
| DP-231 | DONE | Pender-style metadata/oEmbed/archive enrichment: private source metadata and archive receipts, optional provider-pinned Vimeo JSON lookup (disabled by default), bounded no-redirect network contract and isolated MiniPC test; no live source approval implied | DP-210, DP-118, DP-305 |
| DP-232 | DONE | Existing fact-check provider-neutral adapter complete: bounded DP-228→DP-209 runtime, append-only mirror lineage/replay, fail-closed UNKNOWN rights and metadata/link-only public surface proven; any future owner-selected live provider requires a separate authorized network/source canary | DP-228, DP-215 |
| DP-233 | IN PROGRESS | Parliamentary official speech/transcript/video adapter; fixture execution distinguishes NEW/REPLAY/AMENDED and delegates amended records to DP-511/DP-227 with DP-305 fail-closed rights; approved official source-family MiniPC canary pending | DP-206, DP-217, DP-218, DP-231 |
| DP-234 | IN PROGRESS | DVNS/read-only structured evidence adapter; strict offline normalization + explicit DP-215 role/authority/suitability bridge implemented, real approved provider/licensing + MiniPC source-family canary pending | DP-215, DP-228, external contract/API |

Exit criteria: at least three source families run through the same contracts; provider
failure remains a blocked state; any diarization adoption is evidence-driven and never
used as biometric identity; evidence suitability is contextual and inspectable rather than
a global source score; direct quotations are source-span bound rather than model-authored;
speaker/person/context/wording derivation are fail-closed and reviewable; the adversarial
attribution benchmark has zero known public false-attribution/fabricated-quote escapes; and
material Finding assertions are citation-audited; original-source derivation and compound
numeric/effective-time verification are deterministic; research work compiles from evidence
requirements into bounded lanes rather than open-ended agents; and
the corpus-native path has one real bounded collection that can be replayed without
duplicate records or public side effects.

---

## M3 — Editorial, correction, privacy, and legal policy

Goal: settle the rules that determine what may become public and how challenges are
handled before opening the product to users.

| Ticket | Status | Description | Depends on |
|---|---|---|---|
| DP-301 | IN PROGRESS | Intentionality/"lie" engineering policy AC-301.1-.7 complete and fail-closed; AC-301.8 remains blocked on qualified Q-306/DP-307 owner/counsel dispositions | M0 |
| DP-302 | DONE | Right-of-reply engineering AC-302.1-.10 machine-proven, including durable abuse/retention ledgers and enabled MiniPC intake→private-review replay; public intake remains disabled pending separate Q-306/DP-307 launch/legal decisions | M0 |
| DP-303 | DONE | Typed append-only correction/takedown/appeal engineering AC-303.1-.10 machine-proven through full MiniPC submit→review→correction/reanalysis→public-projection canary; launch policy/legal decisions remain separate Q-306/DP-307 blockers | DP-302 |
| DP-304 | IN PROGRESS | Privacy/minimization policy, quarantine, private rights/access runtime and MiniPC canaries exist. Versioned DP-304 technical field inventory now covers 99 live PostgreSQL tables / 1,238 fields + 11 public allowlist groups / 89 named keys, with 0 live catalog gaps (docs/ops/privacy-field-inventory-20261008.md). This does NOT approve legal purpose/retention, deep JSON/log inventory or Q-306/DP-307 dispositions; release remains blocked | M0 |
| DP-305 | DONE | Copyright/transcript excerpt engineering AC-305.1-.8 machine-proven through rights registry, fail-closed no-body boundary, complaint→hold bridge and MiniPC excerpt/expiry/cleanup canary; real excerpt profile remains disabled pending source-specific Q-306/DP-307 legal clearance | M0 |
| DP-306 | DONE | Italy/EU legal closure-control register structurally complete; this is not legal clearance: all launch-sensitive Q-306 rows remain OPEN/BLOCKED with 0 qualified dispositions, handed off to DP-307 | DP-301..305 |
| DP-307 | FUTURE | Qualified legal review remains BLOCKED: no accepted reviewer/scope or owner/counsel dispositions; all DP-307 acceptance criteria remain open | DP-306 |
| DP-308 | DONE | Publication evidence invariants + fail-closed production revalidation complete; clean HEAD full suite 1720/1720, benchmark 5/5 and isolated MiniPC/PostgreSQL acceptance green; no Q-306/DP-307 legal conclusion implied | DP-215, DP-216..224, DP-301..305 |
| DP-309 | DONE | High-risk/legal-status engineering gate complete: current reviewed packet + DP-310/311 separation are mandatory before serialization; full local/MiniPC regression green, while missing DP-307 qualified authority still correctly holds public enablement | DP-215, DP-304, DP-306, DP-308; DP-307 for launch |
| DP-310 | DONE | Independent HIGH/LEGAL dual-control engineering complete with off-DB identity-attested durable replay, canonical production enforcement, clean full-suite/DP-223/MiniPC/PostgreSQL acceptance green; no claim of legal correctness | DP-308, DP-309 |
| DP-311 | DONE | Local/off-DB reviewer identity authority + exact-event attested receipts for DP-310; restart/tamper/revocation, private backup/restore, disposable-PostgreSQL replay and isolated MiniPC acceptance complete | DP-310; coordinate DP-303, DP-507 |

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
| DP-405 | IN PROGRESS | Person archive UI; populated 12-finding chronology plus correction/reply history are green; only deliberate zero-public-record Person state and real screen-reader/manual accessibility acceptance remain | DP-105, DP-425 |
| DP-406 | BLOCKED | Topic dossier UI implementation complete; real approved Topic/membership runtime canary still unavailable | DP-430, DP-425 |
| DP-407 | IN PROGRESS | Content/source-locator UI; populated timed/written, correction/reply, privacy/offline and zero-finding fallback matrices are green; only unresolved/blocked public-state wording and real screen-reader/manual accessibility acceptance remain | DP-207, DP-105, DP-425 |
| DP-408 | BLOCKED | Trace/longitudinal relation UI; implementation complete, real reviewed runtime canary unavailable | DP-104, DP-105, DP-425 |
| DP-409 | IN PROGRESS | Public search/indexing without new infra; deterministic static artifact/UI, browser/mobile/reduced-motion/exact-200%-zoom and live MiniPC approved-projection/search/API fingerprint convergence are green; actual screen-reader/manual accessibility and DP-408 dependency remain | DP-405..408, DP-425 |
| DP-410 | IN PROGRESS | Accessibility/performance/SEO acceptance; rendered quality, browser zoom, SEO/static metadata, cold MiniPC performance, live static/API convergence and dependency/bookkeeping audit are green; manual AT/focus/touch/contrast acceptance remains | DP-405..409, DP-422, DP-425..429 |
| DP-411 | DONE | Generate and compare five researched visual systems against UX v2 | DP-413 |
| DP-412 | IN PROGRESS | Design-token/component contract largely proven; real screen-reader + exact-200%-zoom component acceptance remains | DP-411 |
| DP-413 | DONE | Simplify Public/Studio IA to 5 + 2 templates before implementation | DP-400 |
| DP-414 | DONE | Studio IA v3 contract closed: four private workspaces + source-bound fixture view-model proven on MiniPC; persisted adapters/workflows remain owned by DP-415..419 | DP-112, DP-113 |
| DP-415 | IN PROGRESS | Authenticated on-demand loopback Studio UI + metadata-only DP-116 private search API; real Garlasco top-K, persisted browser UX/AT and operator runtime proof remain open | DP-116, DP-414 |
| DP-416 | IN PROGRESS | Authenticated loopback collection→18 Content→10 Source IDs→30 Claims→28 persisted TEXT_QUOTE_HASH attribution records (2 missing), scoped pagination and blockers, live MiniPC/HTTP; rights UNKNOWN, no captures/passages/candidates or full browser AT acceptance | DP-113, DP-114, DP-414 |
| DP-417 | IN PROGRESS | Discovery list/provenance inspector + new source-only scoped, paginated annotation history in authenticated read-only Studio. Append-only triage ledger replay/CAS, isolated PG writer/read tests and MiniPC pg_temp rollback canary; local domain-separated HMAC actor attestation added for explicit CLI annotations, not review action authority. Migration not deployed; real rights/reviewer governance actions, all other queues, safe bulk transitions and nonempty live Inbox still open (docs/tickets/DP-417-studio-discovery-inbox.md) | DP-209, DP-212, DP-414 |
| DP-418 | IN PROGRESS | Private loopback persisted match-run read-only inspector; currentness/reviewer authority unverified, no promotion until durable review + UI proof | DP-117, DP-212, DP-414 |
| DP-419 | IN PROGRESS | Private loopback persisted capture-version metadata compare; passage/media selector jump, rights-gated previews and live browser proof remain open | DP-210, DP-414 |
| DP-420 | FUTURE | Garlasco operator usability and search-recall acceptance | DP-214, DP-415..419 |
| DP-421 | FUTURE | Public case/collection view contract decision | DP-214, M3, DP-420 |
| DP-422 | IN PROGRESS | Public Product Architecture v3 route/template migration; canonical/legacy/internal-link contract and clean-clone acceptance green; AC-422.8 selected-v4 desktop/mobile manual comparison plus DP-408/409/429 completion gates remain | DP-405..409, DP-426..429 |
| DP-423 | DONE | Public product-marketing + brand context | DP-400, DP-413 |
| DP-424 | DONE | Public visual redesign v4 concept selection | DP-423, DP-412 |
| DP-425 | DONE | Public design system v2 + component contract | DP-424 |
| DP-426 | DONE | Home + public shell v4 | DP-425 |
| DP-427 | DONE | Canonical Statement page v4 | DP-425, DP-105 |
| DP-428 | DONE | Method + trust/utility document pages v4 | DP-425 |
| DP-429 | IN PROGRESS | Explore page v4; static-index UI, browser Back/URL restore, keyboard/dialog, reduced-motion, phone/reflow and exact 200% browser zoom automation green locally and on MiniPC; real screen-reader/manual visual acceptance remains | DP-409, DP-425 |
| DP-430 | DONE | First-class public Topic resource contract | DP-105, DP-114 |
| DP-431 | DONE | Correction/retraction propagation proven across pages/API/search/social+JSON-LD/history, fail-closed rebuild and private-history hold; final MiniPC promotion converges live API/search/RDF validation on the approved projection fingerprint | DP-303, DP-402/403, DP-405..409, DP-422, DP-427..429, DP-434 |
| DP-432 | DONE | Public trust/provenance disclosure and correction-history integration AC-432.1-.8 machine-proven; upstream DP-223 attribution-integrity release sub-gate is now closed, while real screen-reader/manual judgment remains owned by DP-410 | DP-216..223, DP-308, DP-427, DP-428 |
| DP-433 | DONE | Stable-URI + linked-data/RDF interoperability projection; deployed `/index.nt` read-back and discovery green | DP-105, DP-403, DP-430, DP-432, DP-434 |
| DP-434 | DONE | First-class reviewed public Content resource independent of published findings; projection/API/web/RDF + isolated MiniPC migration/same-origin canary complete | DP-105, DP-210, DP-401, DP-403 |

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
| DP-501 | DONE | Threat model/security regression matrix + exact-tree MiniPC focused/full-suite receipt complete | M0 |
| DP-502 | DONE | Backup/restore drill complete; post-migration MiniPC disposable restore verifies the current 94-table runtime state | DP-501 |
| DP-503 | DONE | Retention matrix + fail-closed hold/destructive guards + exact-tree MiniPC proof complete; legal periods remain DP-306/307 | DP-304, DP-305 |
| DP-504 | DONE | Operational SLO/taxonomy + real MiniPC private health read-back complete | M0 |
| DP-505 | DONE | Alert/digest runbook + MiniPC PAGE/NO_PAGE matrix complete | DP-504 |
| DP-506 | DONE | Cost budget policy + real isolated MiniPC provider-outage drill complete | DP-504 |
| DP-507 | FUTURE | AuthN/AuthZ/CSRF design for any future admin HTTP surface | only when such surface exists |
| DP-508 | FUTURE | Public intake rate limiting/spam controls runtime | DP-302, public intake implementation |
| DP-509 | DONE | Harden claim/ASR/verification provenance inputs | M0 baseline |
| DP-510 | DONE | Durable targeted provenance quarantine/hold + DP-431 cleanup + MiniPC restart/revalidation incident canary complete | DP-308; coordinate DP-501/504/505/431 |
| DP-511 | DONE | Source drift/supersession/rights-expiry revalidation watch + durable MiniPC canary complete | DP-210, DP-215, DP-308, DP-510 |

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
| DP-601 | DONE | Package/development environment cleanup beyond POC naming | M1 |
| DP-602 | DONE | CI matrix and deterministic contributor acceptance | DP-601 |
| DP-603 | DONE | Fixture/data licensing inventory and attribution | M3 |
| DP-604 | IN PROGRESS | Release/versioning/changelog policy and release checklist; reproducible local artifacts proven, external release authority still gated | DP-601, DP-602 |
| DP-605 | DONE | Maintainer/contributor documentation dry-run from clean clone | DP-001, DP-601 |
| DP-606 | IN PROGRESS | Public issue labels/project automation; remote/public owner/security facts + clean-clone/local contract proven, owner branch-protection/hosted mutation and export/rollback dry-run pending | GitHub remote |
| DP-607 | IN PROGRESS | Optional SDK/MCP/skill gate; stdlib read-only client contract, mock/deprecation and clean-clone proof green; owner surface/build-or-no-build decision pending | DP-403 |

Exit criteria: clean clone -> tests -> local demo is documented and reproducible; code,
fixtures, and third-party attributions are publishable under explicit terms.

---

## M7 — Stable v1 launch

Goal: first release that can be operated publicly without calling the code a prototype.

| Ticket | Status | Description | Depends on |
|---|---|---|---|
| DP-701 | IN PROGRESS | Owner identity + technical rename/MiniPC cutover complete; trademark, DNS/handles, external collision/legal and rollback evidence open | M4 |
| DP-702 | FUTURE | Pre-launch legal/security/privacy/evidence-safety review closure | DP-301..310, DP-501..511 |
| DP-703 | IN PROGRESS | Production dataset/source launch set and disclosure; launch set/rights/provider/snapshot gates remain blocked | M2, M3 |
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

## Implementation checkpoint — 2026-10-09 source safety waves

This checkpoint records **verified implementation progress only**. It does
not close an acceptance criterion, authorize a source/rights decision or
change the M7 **NO-GO / 41 release blockers** disposition. The canonical
backlog still contains **125 tickets: 86 DONE, 24 IN PROGRESS, 6 BLOCKED,
9 FUTURE (39 open)**.

- `82f4c2b`: research Discovery and Capture provenance, Candidate matching
  contradictory-scope HOLD, Source Intelligence rights/readiness and DP-417
  private HMAC attestation race guards; full suite **2,016/2,016 PASS**,
  GitHub CI `37948202895` **11/11 SUCCESS**.
- `41c30fe`: Candidate manifest/second-rights-read and deterministic
  matching replay semantic integrity, private Studio triage ledger continuity;
  full suite **2,025/2,025 PASS**, GitHub CI `37949761666` **11/11 SUCCESS**.
- `3025370`: Garlasco manifest canonical HTTPS/global-address and family
  safety, DP-215 temporal/role suitability and DP-213 Coverage Need bounded
  retry/identity integrity; full suite **2,040/2,040 PASS**, GitHub CI
  `37951300010` **11/11 SUCCESS**.

All three waves retained deterministic benchmark **5/5 PASS**, restore-drill
PASS and unchanged NO-GO preflight receipt
`890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`.
Real MiniPC PostgreSQL was queried read-only: `research:garlasco` remains
PAUSED, with 18 included Content and 30 historical Claims, zero accepted
Discovery Hits, Capture/Passage/Candidate records, and no current qualifying
Source Intelligence profile/role/scope on the 18 Content. The pending DP-417
production migration was not installed. See the three dated wave receipts
in `docs/reviews/`. DP-214, DP-215 and DP-417 remain IN PROGRESS pending
source rights, operator approvals and real canary/acceptance evidence.

### 2026-10-09 next private operator safety batch (source-only)

Following `31e78cb`, local RED→GREEN regressions tightened the actual
DP-214/DP-215 intake boundary: private Capture batch rejects statically
unsafe destinations before DB preflight, bounds operator JSON file bytes,
and private Candidate analysis requires exact persisted Content/rights URL
canonicality before provider use and upon guard replay. DP-304's Capture
authorization rejects absent/malformed aggregate safety counts rather than
silently coercing them to zero. DP-307's launch preflight refuses duplicate
PLAN ticket rows regardless of status equality. These controls are local
engineering evidence only; the MiniPC corpus is still PAUSED (18/100
Content, 30 historical Claims, zero Discovery Hit/Capture/Passage/Candidate
and Garlasco Coverage Need). **No additional AC or ticket marked DONE: 86
DONE, 24 IN PROGRESS, 6 BLOCKED, 9 FUTURE / 39 open**. Release stays
**NO-GO / 41 blockers**, including 16 unresolved legal questions, four
unaccepted launch artifacts and missing owner decisions. The pending
DP-417 production migration is not authorized by these code changes.

The same next safety wave additionally reviewed the preexisting
`source_watcher`/oEmbed local changes and closed the oEmbed socket-level
DNS-rebinding seam by reusing the verified, no-proxy, DNS-pinned HTTPS
handler. DP-211 Candidate extraction now holds impossible parent
`TEXT_POSITION` coordinates before any provider invocation or replay.
Both changes have isolated RED→GREEN regressions, **not** live source or
provider acceptance. The unresolved exact immutable Capture text
roundtrip (including equal-length shifted source spans) remains a
specific next engineering prerequisite, not an implicit approved match.

Full deterministic verification for this source tranche passed
**2069/2069 unit tests**, restore drill, **5/5** verification benchmark,
repository contract and `git diff --check`. Astro check reported
**0 diagnostics**; its **32-page demo-mode** build was successful,
while a normal public build properly requires the absent authorized
projection input. Release still **NO-GO/41**.

### 2026-10-09 next candidate operator preflight batch

After the published `90a154c` source wave, the real 16-item private
Candidate loader now bounds JSON reads to 1 MiB, and its independent
Capture body-ref availability gate accepts only the exact SQL/JSON
boolean `true` rather than any truthy value. Two local RED→GREEN
regressions and **55/55** focused tests pass; this remains a new
source-only follow-up pending its own full-suite, commit and CI proof.
The Garlasco corpus, qualified source rights, immutable selector
roundtrip and DP-417 production migration remain blocked/unchanged.

An independent DP-417 read-only triage-history lane reproduced a
stale-history privacy disclosure when a Hit's Attempt/Query lineage
turned inconsistent after annotations. The reader now returns no
decisions or head revision for the invalid Hit, with fail-closed SQL
and result validation; ephemeral PostgreSQL and injected-response
regressions are GREEN. No reviewer transition or release approval
is implied.

The integrated Candidate + DP-417 history Wave 10 finished **2072/2072
Python unit tests PASS**, restore drill PASS, benchmark **5/5 PASS**,
repository ticket contract PASS, `compileall` and `git diff --check`
PASS. Canonical preflight remained **NO-GO/41**, with no additional
AC marked complete.

### 2026-10-09 Wave 11 real public route and Studio match safety (source-only)

Two independent file-owned worker lanes, reviewed by PRIME:
**DP-407** gained a public-data-only descriptive accessible name
for timed Content marker buttons on the **mounted** `ContentRecord`
route, after real Chromium AX-tree RED proof showed only a timestamp;
its GREEN harness builds the 12-moment authorized fictional
projection fixture and verifies deep-link, Space keyboard activation,
detail, focus and URL state. **DP-418** read-only persisted
matching suggestions now validate deterministic run/result/target
binding, strict rank, known algorithms/feature codes and
scope-conflict `HOLD` semantics, blocking tampered cross-run
records. The isolated legacy `ContentAuditClient` URL-selection
experiment remains deliberately uncommitted because that
component is not in the production Content route.

Neither synthetic fixture nor browser automation fulfills
DP-407.7 manual assistive-technology acceptance, DP-418 real
reviewer/currentness/promotion decisions or DP-214/215's
authentic rights-gated Garlasco tracer. All statuses remain
**86 DONE / 24 IN PROGRESS / 6 BLOCKED / 9 FUTURE** and v1
remains **NO-GO/41** until authority and real acceptance gates.

Wave 11 integration was certified on the corrected frozen source:
**2078/2078 Python tests PASS**, restore drill, **5/5** benchmark,
Astro 0 diagnostics, real built Content route Chromium AX/keyboard,
web design/route/quality, repository contract and compileall PASS.
The first full run had correctly detected one outdated adjacent
HTTP API test fixture, repaired by PRIME; its second full rerun
is the cited PASS. No source license, live provider, reviewer approval,
manual screen-reader pass or DP-417 schema authority is inferred.

### 2026-10-09 Wave 12 source excerpts and Studio archive proof

**DP-233** now requires a requested official parliamentary excerpt to be a
literal contiguous nonempty portion of the *same* normalized statement,
in addition to exact source/version/hash/rights and amendment gates.
Invented, other-speaker and stale-version text is rejected before any
`ALLOWED` fixture response. **DP-419** private Capture comparison now
refuses archive `SUCCEEDED` or body `PURGED` states without their persisted
completion receipts and coherent lifecycle evidence, while never revealing
private receipt data or bodies. The combined focused source/inspector/Studio
loopback suite **32/32 PASS**, compileall and diff checks pass; a final
full-suite and CI gate is still required. No source license, real provider
permission, production migration or ticket status was changed.
**39 open, NO-GO/41**.

**DP-215** Source Intelligence now refuses to infer `APPROVED` from a
missing/blank observation review state: unreviewed rows are excluded and
reported, while explicitly approved canonical SQL observations remain
eligible. This is an additional local fail-closed boundary, not evidence
of rights approval or a real corpus. Combined three-lane focused
tests **46/46 PASS**; full-suite/commit/CI are separate requirements.

Wave 12's frozen full suite subsequently passed **2083/2083 tests**,
restore drill, 5/5 verification benchmark, compileall, ticket contract
and diff checks. Launch preflight remains **NO-GO/41** with unchanged
receipt. No new AC or ticket is declared DONE; code-only approval
does not replace real Camera/Senato rights or MiniPC corpus acceptance.
