# Dichiarazioni Pubbliche — Master Plan to Stable v1

Status: canonical  
Plan version: 1.3 (post-grilling planning)
Last updated: 2026-10-12 (documentation authority clarification; ticket statuses unchanged)

This is the single ordered execution map for the project. Detailed implementation specs
live in `docs/tickets/`. Historical roadmap files are evidence, not competing backlogs.
Run `python3 tools/report_ticket_status.py --json` for the **current** counts and
PLAN/ticket consistency; dated counts below are checkpoints, not a live dispatch
queue. The post-grilling expansion introduced 37 ticket specifications, and the
canonical register at the 2026-10-12 `f92c1c5` checkpoint contained 162 tickets:
90 DONE, 52 IN PROGRESS, 6 BLOCKED, 14 FUTURE (72 not DONE).

## 2026-10-10 post-grilling integration — planning contract, not completion

The four actual native Chat On Steroids lanes are integrated into the **one** canonical PLAN. The master traceability matrix and gated execution path are in [post-grilling coverage and sequencing](docs/reviews/2026-10-10-post-grilling-coverage-and-sequencing.md); owner-facing semantics and superseded proposals are in [target reconciliation](docs/reviews/2026-10-10-post-grilling-target-reconciliation.md).

35 original non-DONE ticket files retain their statuses, historical acceptance checkmarks and proofs with explicit planning delta sections. 37 new FUTURE ticket specifications cover source/corpus DP-235..244, semantic/verification/authority DP-312..321, public Statement/search/Person×Topic/redesign DP-435..443, and operations/account/cost/release DP-512..519. **First complete approved end-to-end pilot DP-443 is the scaling gate** before historical bulk DP-243/516, and is not DP-214's 100-item Garlasco criterion, DP-703's three-family release set or stable-v1 release DP-705.

The existing fail-closed publication/review and no-body rules remain operative until a separately approved rights, policy, data and runtime cutover. Qualified external legal and owner decisions are not inferred from this plan. The owner alone selects visual redesign at DP-441; DP-442 is later implementation. This run changes no application or public data and authorizes no push/deploy.

## Owner clarification for the active grilling — 2026-10-10

The owner reaffirmed one integrated product: inspect public statements and their
sources; understand factual verification, refutation, insufficient evidence and
uncertainty; compare the same proposition or expressed position across people and
over time; browse Person and Topic pages to discover publicly expressed positions.
Scope includes politicians, influencers/creators, actors, hosts/presenters and
other public figures within their public-interest activity. These are complementary
core capabilities, not alternatives for the owner to choose between.

The initial grilling Q1 incorrectly proposed choosing an archive, chronology or
fact-checking as the mission. It is withdrawn, as is the recommendation to make
an archive-only product the first populated release. A one-case technical pilot
may validate the integrated path; it does not authorize reducing this mission.
No ticket status, acceptance criterion or release permission changes here.

Resume grilling on concrete behavior and unresolved implementation/editorial
boundaries under this mission: what each verification state means, how factual
propositions differ from opinions, what makes comparisons valid, how Person/Topic
pages preserve source/context/time, and operator capacity and budget. Record
answers before approving redesign or rescoping the backlog.

**Owner answers, active grilling, 2026-10-10:** editorial reviewer availability
is currently **zero**. The intended automated fact-checking must have rigorous
source/attribution/evidence checks and prevent unsupported conclusions. An
infallibility or zero-error guarantee is not established and must not be promised;
accuracy, abstention, false attribution and false verdicts require measured proof.
At that checkpoint, the existing human-review/no-auto-publication contract stayed
unchanged pending the authority answer. Q14 below now settles the autonomous
target; runtime gates remain unchanged pending explicit implementation/acceptance.

**Budget answer:** approximately **EUR10/month is a tentative target to estimate**,
not a verified bill, quota entitlement or authorization to incur charges. The
owner requires real daily consumption trials across Antigravity account/model
quotas, audio provider usage and local-model electricity. Resolve the audio
provider from the configured route (currently Groq in the project); do not assume
that the owner's spoken "Grok" names a new provider. Reuse existing receipts/cost
ledger and supported account usage interfaces. Measure before/after quota,
requests, input/output tokens or reported quota units, retries, reset time, audio
duration, elapsed time and incremental energy where observable. Keep measured,
estimated and unknown cost distinct; no automatic overage, account switching,
new subscription or paid call is approved by the tentative number.

**Owner sequencing update, 2026-10-10:** use the owner's temporarily abundant
existing GPT-6 entitlement through Codex/ChatGPT-web first, to acquire and validate
a bounded historical corpus and the integrated product path. Model preference is
recorded, not proof of a model switch or an API entitlement. Historical public
figures Hitler and Mussolini are proposed initial cases; breadth, periods, themes
and source permissions remain to be decided. This pilot must exercise source,
attribution, factual assessment, Person/Topic and longitudinal/cross-person
comparisons, not reduce the mission to quotation storage.

The owner wants economical background automation and an organized future backlog,
with grilling first and future tickets after decisions. Do not start recurring
jobs, bulk captures or paid experiments merely from this planning request. Reuse
existing source/discovery/capture/ledger paths when the source and run are approved.
Historical backfill and future incremental ingestion are separate workloads.
Death ends new statements by the person, not new discoveries, digitizations,
source revisions or corrections. No claim of collecting "all sources" or automatic
rights clearance follows from choosing historical figures.

Defer Antigravity/audio/local-key comparison until the corpus/model path works;
then measure sustainable daily consumption, reset cycles, retries and energy.
EUR10/month is a tentative future operating target, distinct from the temporarily
available entitlement; allocation and numeric limits depend on observations.

**Owner answers Q4/Q5 and capacity refinement, 2026-10-10:** historical content is
intended to be **permanent product content**. First finish the complete bounded
source acquisition → transcription/text → catalog → ingestion → frontend →
verification/test path; only after acceptance begin the large historical
collection. Do not mistake approval of permanent content for permission to publish
unreviewed records. The owner subsequently clarified that **he is the person**
offering roughly five hours weekly, provisionally, for quick non-textual checks
such as whether a person's image is correct. This is owner visual/asset review,
not an offer to validate every factual verdict, source interpretation or textual
comparison. Full editorial fact-check reviewer capacity remains unavailable.

The acceptance slice must prove real source/rights/identity/text lineage, exact
locators and hashes, catalog deduplication/versioning, verification and uncertainty,
frontend source navigation/Person/Topic/comparisons, private/public isolation and
correction/withdrawal on the authoritative runtime. Reuse original ticket AC;
this is sequencing, not a declaration that every historical/future feature is
required before testing one coherent bounded slice. No bulk or background service
is started during the grilling.

**Q7 clarification:** do not reassign the owner's visual-check time to full
pre-publication editorial approval. Treat visual asset approval, textual
attribution and factual assessment as distinct decisions; approving a photograph
must not approve statements, verdicts or source rights. Avoid biometric matching;
an absent/unapproved image must not be filled with an invented portrait. The
owner intends automated textual work. The target authority is subsequently
settled in Q14 below; the existing runtime contract has not yet been migrated.

**Owner context clarification and grilling cadence, 2026-10-10:** ask multiple
independent frontier decisions per round, with concrete scenarios; do not continue
one-question turns or reopen settled mission requirements. The owner's hypothetical
historian/edited-clip example is not evidence of an actual quotation by Barbero.
It establishes that spoken words and endorsed positions differ: historical
quotation, reported speech, impersonation, irony and repudiation must retain their
context and must not populate a Person/Topic stance as endorsement. Attribution
and context integrity precede factual assessment and comparisons.

Context is sufficient meaning-preserving material, not a universal seconds count
or a requirement to watch every complete source. A clear scene may provide relevant
context; an apparently clear hidden-camera recording still needs authentic source,
speaker attribution and edit/sequence checks. Do not infer lack of context from
brevity alone, or correctness/intent from vivid footage alone. Retain original
locator, exact passage and the surrounding material necessary to interpret it.
User emphasis was context/attribution; Q9/Q10 below subsequently accept abstention
and explicit insufficient-evidence results for correctly attributed statements.

The preceding frontier has now received answers Q9–Q14 below; do not ask these
settled choices again. Implementation, thresholds and visual design follow the
remaining central decisions and final shared-understanding confirmation. The
proposed five-hour availability and visual-review workload remain approximate
and must be measured.
Future daily workload and account scheduling follow pipeline acceptance. Preserve
all existing ticket AC and their proof history; Q19 below authorizes their planned
revision and new tickets, not implementation or artificial completion.

**Owner answers Q9–Q14 and final-round instruction, 2026-10-10:** the owner
accepts withholding unsupported attributions/verdicts and distinguishing a
completed check with insufficient evidence from a check not yet performed.
He accepts a small, fast exception queue, but requires active investigation of
who said what, when, why and in which context before escalation. Merely marking
cases pending/blocked does not resolve them. Current/future AI capability is not
proof of 100% accuracy or permission to fabricate missing evidence.

Analyze multiple people together where appropriate, with bounded replayable
batching; do not impose a one-person-at-a-time product restriction. Sources must
include other languages, preserving originals and explicitly identified Italian
translations. A large context window is a possible tool, not proof that unlimited
batch sizes are efficient, supported or correct.

The owner explicitly chooses autonomous final factual checking and accepts the
proposed future per-result publication autonomy after validation. This settles
the target authority decision: full human textual review is not a prerequisite
of the intended system. It does not switch the current runtime or erase current
publication safeguards during this interview. The final implementation plan must
explicitly reconcile AGENTS/PRODUCT/ADRs/tickets, distinguish machine review from
owner/legal approval and prove the new gates before any cutover.

The hypothetical denial-of-prior-utterance example establishes separate checks:
whether the earlier utterance is authenticated, whether a later denial is
refuted by that record, and whether there is a documented longitudinal relation.
It is not evidence about an actual named person's words, nor proof that the
content of the earlier utterance is true or that the speaker intended deception.

**Final owner answers Q15–Q20, 2026-10-10:** the public Statement must contain
the exact source words, never a paraphrase substituted for the declaration.
Paraphrases are permitted only in explicitly separate summaries. Preserve the
original and identify translations separately; do not call translated words the
verbatim original. The owner's claim of universal absence of copyright is not
an established legal clearance: do not substitute a paraphrase when quotation
rights cannot be established, and do not invent a rights grant. Research and
ticket the source-specific lawful exact-quotation path.

Person × Topic is an intersected filter/view with a dated, source-linked summary
of documented expressed positions, not a mandatory chatbot. The owner requires
strong automation including textual procedural/judicial documents and does not
choose a general high-risk exclusion or routine human textual review. Literal
documentary wording, what a document reports/alleges, and truth of the reported
event remain separate checks. Distinct procedural states and precise time,
jurisdiction, identity and source versions must survive automation.

Future incremental collection prioritizes continuity of followed sources/people/
topics, with room for relevant events/new people; disclose coverage and freshness
rather than using virality as the sole criterion. Redesign selection belongs to
the owner later; image generation or another model are possible future aids,
not tools authorized for this deliverable.

**Q19 overrides the earlier implementation request:** prepare one comprehensive
Prompt2Prompt master handoff for four native Chat On Steroids subagents, focused
ONLY on creating, modifying and updating the complete future/existing ticket
backlog and necessary planning documentation. No application source/test/schema
change, source ingestion, provider trial, scheduling, migration or deployment
is included. Implementation is a separate later task. The native tool is `agents`
(spawn/message/status/finish); discover its live schema in the target chat.
The external master uses one adjacent terminal response file; native workers use
native task/result channels, not separate Prompt2Prompt response files. Produce
one canonical ordered plan and requirement-to-ticket coverage without lost AC,
duplicate work, fake DONE or unsupported claims of agents launched.

**Historical pre-execution handoff (2026-10-10):** [one post-grilling master prompt](tasks/prompt2prompt/20261010-231757-backlog-post-grilling/lane-01-backlog-master/001-backlog-master.prompt.md)
was prepared for owner launch in Chat On Steroids. Subsequent reconciliation
did run and expanded the actual register to 162; use the live command above and
the original ticket files for present execution authority. The prompt remains
dated provenance, not an unexecuted instruction to repeat the expansion.

## Historical frozen checkpoint and explicit FUTURE queue — 2026-10-10 (125-ticket baseline)

**Repository state:** `main` at `a104f0f` at the 2026-10-10
reprioritization audit, with a single clean local worktree, no stash or other
local branch; `a66e987` was the preceding source/CI checkpoint, not proof of a
fresh CI run on the later documentation commits. **This is not MiniPC deployment
or editorial launch acceptance.** The canonical check
`python3 tools/report_ticket_status.py --json` gave **125 tickets: 90 DONE,
20 IN PROGRESS, 6 BLOCKED, 9 FUTURE; 35 not DONE**. The stable-v1 gate
`python3 tools/check_launch_preflight.py --expect-no-go` yielded **NO-GO / 49**
(16 unresolved qualified Q-306 dispositions + four missing release artifacts
+ 29 ticket gates). Acceptance criteria remain authoritative in their own files.

**Sequence for the nine FUTURE tickets (unchanged statuses):**

| Order | Tickets | Trigger for unblocking / deliberate deferral |
|---|---|---|
| 0: qualified decisions, not agent implementation | **DP-307**, **DP-702** | Name Italy/EU reviewer/owner authority, accept scoped legal/privacy/security/hosting decisions including informational-only preview vs public-source archive. No self-approval. |
| 1: only after real authorized corpus | **DP-208**, **DP-420** | Live remote-ASR/rights/profile prerequisite for an objective diarization benchmark; accepted Garlasco sources/candidates and operator tasks before Studio usability tests. |
| 2: separate product decision | **DP-421** | Decide NO-GO or contract for public Case/Collection based on reviewed pilot, never expose private Studio records to fill the UI. |
| 3: opt-in attack surfaces, otherwise remain dormant | **DP-507**, **DP-508** | Activate **only before** exposing remotely reachable admin mutations or user/public intake; no implementation sprint just to inflate completion. |
| 4: actual stable release | **DP-704**, **DP-705** | Owner-approved real source→correction MiniPC rehearsal, accepted rollback and immutable receipts, then explicit v1 cutover; failed or missing gate means no deployment. |

**Working backlog triage, not a status migration:**
[`docs/reviews/2026-10-10-open-ticket-reprioritization.md`](docs/reviews/2026-10-10-open-ticket-reprioritization.md)
maps **all 35 not-DONE tickets** to a proposed DO NOW / DEFER / MERGE CANDIDATE /
DELETE ONLY AFTER OWNER DECISION queue with evidence gates and a dependency tree.
Several `IN PROGRESS` tickets had integrated implementation and pending external
or manual acceptance; they were **not** evidence of 20 dirty Git WIP changes.
One AT/manual acceptance campaign can collect distinct DP-405/407/409/412/422/429
receipts under DP-410 without merging their AC. At this dated checkpoint there
were 125 canonical ticket statuses. The subsequent 37-ticket expansion supersedes
that count without closing any unmet acceptance or owner decision.
An independent product/UX audit and owner grilling must precede any newly approved
full redesign scope; historical v4 `DONE` tickets remain historical facts.

**Two independent scopes:** `LAUNCH.md` describes six truthful, static
informational pages (zero approved records is valid), not a full v1. Even the
informational refresh needs the specific privacy/identity/domain/contact/manual
accessibility/owner-signoff profile (DP-304/307/410/701/702) and an independently
approved projection; a synthetic empty-shape proof is not that approval.
The existing website is hosted via Cloudflare Tunnel → MiniPC and can be online
while serving an older build. Do not confuse GitHub CI/push with production rollout.
See `HANDOFF.md` and `MEGA-HANDOFF-2026-10-10.md` for verified details.


## Status vocabulary

- **DONE** — merged, tested, and runtime-proved where required.
- **IN PROGRESS** — implementation or ticket-specific acceptance still incomplete;
  the code may already be integrated and awaiting runtime/manual/external proof.
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
| DP-224 | DONE | Material-assertion citation assurance over approved evidence/passages; exact Passage/source-hash binding + persisted tamper + MiniPC acceptance complete | DP-215, DP-210 |
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
| DP-235 | IN PROGRESS | Bounded rights-authorized private source-to-candidate pilot | DP-209, DP-210, DP-211, DP-212, DP-213, DP-236 |
| DP-236 | IN PROGRESS | Source-family acquisition/use profile with real permission decisions | DP-210, DP-305 |
| DP-237 | IN PROGRESS | Versioned exact locator and cross-format provenance chain | DP-210, DP-216, DP-224, DP-225 |
| DP-238 | IN PROGRESS | Document, PDF/OCR and text extraction with role-preserving provenance | DP-210, DP-211 |
| DP-239 | IN PROGRESS | Multilingual original and translation derivation in the private corpus | DP-210, DP-211, DP-221 |
| DP-240 | IN PROGRESS | Bounded multi-person candidate batch with cross-source identity isolation | DP-211, DP-212, DP-218, DP-222 |
| DP-241 | IN PROGRESS | Active original-source recovery and finite investigation log | DP-209, DP-213, DP-225, DP-228 |
| DP-244 | IN PROGRESS | Source coverage inventory, version refresh and incremental catalog | DP-209, DP-213, DP-215, DP-511 |
| DP-312 | IN PROGRESS | Speech act, contesto adattivo e fedeltà semantica multilingue | DP-216, DP-217, DP-218, DP-219, DP-220, DP-222 |
| DP-313 | IN PROGRESS | Documento processuale: persone, ruoli, affermazioni e stati | DP-111, DP-215, DP-219, DP-222, DP-227, DP-304, DP-309, DP-312 |
| DP-314 | IN PROGRESS | Verificatore fattuale generalista per claim type e requirement profile | DP-215, DP-224, DP-226, DP-227, DP-228, DP-229, DP-312 |
| DP-315 | IN PROGRESS | «Non ho mai detto X»: tre verifiche e relazione storica | DP-216, DP-219, DP-220, DP-222, DP-227, DP-312, DP-314 |
| DP-318 | IN PROGRESS | Same-take e relazioni corrette tra e dentro le Persone | DP-104, DP-114, DP-219, DP-222, DP-227, DP-312 |
| DP-319 | IN PROGRESS | Indagine attiva dei casi dubbi con coda minima | DP-213, DP-215, DP-225, DP-228 |
| DP-321 | IN PROGRESS | Gold credibile e metriche indipendenti di errore, coverage e abstention | DP-223, DP-226, DP-228, DP-229, DP-312, DP-314 |

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
| DP-316 | IN PROGRESS | Machine verification authority, review migration e eligibility per risultato | DP-308, DP-309, DP-310, DP-311, DP-229, DP-301, DP-304, DP-314, DP-321 |
| DP-317 | IN PROGRESS | Percorso lecito per citazione pubblica esatta per source family | DP-118, DP-216, DP-221, DP-305, DP-304, DP-306 |
| DP-320 | IN PROGRESS | Revoca e correzione transazionali fino all'ultimo lettore | DP-303, DP-308, DP-431, DP-510, DP-511, DP-117 |

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
| DP-242 | IN PROGRESS | Studio source-to-candidate machine handoff and exception lifecycle; private Studio dependencies/acceptance in M4 | DP-416, DP-417, DP-418, DP-419 |
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
| DP-415 | DONE | Private loopback Corpus UI with full DP-116 search filters, keyboard inspection/source navigation, live MiniPC benchmark top-K 13/13, provider-offline proof and no public-body exposure | DP-116, DP-414 |
| DP-416 | IN PROGRESS | Authenticated loopback collection→18 Content→10 Source IDs→30 Claims→28 persisted TEXT_QUOTE_HASH attribution records (2 missing), scoped pagination and blockers, live MiniPC/HTTP; rights UNKNOWN, no captures/passages/candidates or full browser AT acceptance | DP-113, DP-114, DP-414 |
| DP-417 | IN PROGRESS | Discovery list/provenance inspector + new source-only scoped, paginated annotation history in authenticated read-only Studio. Append-only triage ledger replay/CAS, isolated PG writer/read tests and MiniPC pg_temp rollback canary; local domain-separated HMAC actor attestation added for explicit CLI annotations, not review action authority. Migration not deployed; real rights/reviewer governance actions, all other queues, safe bulk transitions and nonempty live Inbox still open (docs/tickets/DP-417-studio-discovery-inbox.md) | DP-209, DP-212, DP-414 |
| DP-418 | IN PROGRESS | Private loopback persisted match-run read-only inspector; currentness/reviewer authority unverified, no promotion until durable review + UI proof | DP-117, DP-212, DP-414 |
| DP-419 | IN PROGRESS | Private loopback Capture version compare + paginated written selectors; candidate→MEDIA_SEGMENT_REF→canonical Content segment/time-range metadata locator now joins persisted rows via authenticated read-only API (no media playback). Rights-gated previews, real player seeking, live MiniPC/browser AT acceptance remain open | DP-210, DP-414 |
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
| DP-435 | IN PROGRESS | Public Statement with exact original wording | DP-216, DP-221, DP-305, DP-312, DP-317 |
| DP-436 | IN PROGRESS | Verbatim search, cards, relations and linked-data consumers | DP-435, DP-402, DP-403, DP-433 |
| DP-437 | IN PROGRESS | Independent public Statements for opinions and positions | DP-435, DP-104, DP-111, DP-312 |
| DP-438 | IN PROGRESS | Person pubblica autonoma, anche senza Statement | DP-105, DP-222, DP-402, DP-437 |
| DP-439 | IN PROGRESS | Filtri pubblici Persona × Tema e dati incrociati | DP-105, DP-402, DP-430, DP-437, DP-438 |
| DP-440 | IN PROGRESS | Sintesi Persona × Tema precomputata e citata | DP-224, DP-303, DP-431, DP-435, DP-439 |
| DP-441 | FUTURE | Brief e alternative comparabili del redesign, decisione owner | DP-413, DP-423 |
| DP-442 | FUTURE | Implementazione futura del redesign scelto e migrazione controllata | DP-425, DP-441, DP-436 |
| DP-443 | FUTURE | First complete source-to-reader and correction pilot | DP-235, DP-312, DP-314, DP-316, DP-317, DP-318, DP-320, DP-321, DP-435, DP-436, DP-437, DP-438, DP-439, DP-440 |

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
| DP-512 | IN PROGRESS | Truthful operation billing classification and retrospective reconciliation | DP-230, DP-506 |
| DP-513 | FUTURE | Bounded empirical GPT-6/Antigravity/Groq/local-capacity pilot | DP-512, DP-506 |
| DP-514 | IN PROGRESS | EUR10-month planning envelope with atomic multi-interval dispatch caps | DP-512, DP-513, DP-506 |
| DP-515 | IN PROGRESS | Economical incremental source monitoring with coverage and safe backoff | DP-209, DP-210, DP-211, DP-511, DP-512, DP-514 |
| DP-517 | FUTURE | Reader Google sign-up/login/logout/delete MiniPC activation | DP-304, DP-307, DP-501, DP-502 |
| DP-518 | IN PROGRESS | Revocation/correction distribution and immutable MiniPC release readback | DP-303, DP-308, DP-431, DP-510, DP-511, DP-502 |
| DP-519 | IN PROGRESS | Operator visual-quality capacity and exception time budget | DP-417, DP-304 |

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
| DP-604 | DONE | Release/versioning/changelog POLICY and reproducible candidate checklist 12/12 AC complete; actual tag/release/signing/legal owner authority still blocked under DP-702..705 | DP-601, DP-602 |
| DP-605 | DONE | Maintainer/contributor documentation dry-run from clean clone | DP-001, DP-601 |
| DP-606 | DONE | Safe GitHub Issues label-only triage: 20 created/2 updated, verified hosted manifest/backup and real temporary-label rollback; Projects V2/hosted automation/branch protection not enabled, stable-release authority remains gated | GitHub remote |
| DP-607 | DONE | Optional SDK/MCP/skill decision CLOSED: NO-BUILD for v1; no extra product, client, MCP endpoint or skill; private read-only contract harness preserved, launch gates independent | DP-403 |

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
| DP-243 | IN PROGRESS | Initial permanent historical corpus from mixed Italian/German primary sources; gated historical expansion in M7 | DP-210, DP-215, DP-703, DP-443 |
| DP-516 | IN PROGRESS | Historical permanent corpus backfill with bounded batches and refresh | DP-210, DP-215, DP-703, DP-511, DP-514, DP-443 |

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

### 2026-10-09 Wave 13 — real operator source binding, countercase replay, archive chronology

The executable DP-214→DP-215 operator Candidate path no longer accepts
a merely present Capture body reference plus a self-consistent Passage
text/hash: with an approved **existing** storage root, preflight and
repeated model/replay/commit guards read bounded actual bytes, check
Capture SHA, exact persisted parent IDs, parser/version/decoding
policy and the literal canonical selector substring. The first
post-ingestion roundtrip is now a defensible source-bound *local*
operator implementation; historical bodies lacking enough metadata
block. DP-229 challenger packets moved to `countercase-v2` to
fingerprint each evidence→relation→rationale→lineage binding,
preventing stale reviewed packet replay after material reassignment.
DP-419 validates archive completion chronology across timezone
offsets before presenting a completed state. These local
regressions plus the unchanged isolated pure fixture controls
pass focused tests (**138/138** for the combined candidate,
Capture, challenger, Studio and API modules). None asserts
real Garlasco Discovery/rights/model approvals, reviewer
authority, a MiniPC production upgrade or v1 release.
**39 open, NO-GO/41**. The frozen Wave 13 source passed
**2093/2093** Python tests (slow disposable PostgreSQL fixtures),
100-table restore drill, benchmark **5/5**, ticket contract,
compileall and diff checks, with preflight still **NO-GO/41**.
Only the subsequent commit-specific GitHub CI remains to verify;
no source rights or release authority are inferred.

### 2026-10-09 Wave 14 — DVNS dates and persisted matching provenance

DP-234 no longer uses valid-looking date prefixes from invalid statement
dates, effective request dates or authority-scope intervals; the full ISO
date/timestamp, clock and offset must be valid. DP-418 read-only Studio
now verifies the actual stored run/result matching versions and result
lifecycle status rather than claiming the current algorithm version by
constant. Both are local RED→GREEN regression fixes; combined DVNS,
Studio API and matching focused tests **56/56 PASS**. Full suite,
restore, benchmark and new CI remain pending. No external DVNS rights,
approved matching decision, live Garlasco evidence or release authority
were created. **39 open, NO-GO/41**.

Wave 14's full frozen test matrix then passed **2097/2097 Python tests**,
100-table restore, 5/5 benchmark, repository contract, compileall and
diff checks. Launch preflight still reports unchanged **NO-GO/41**.
No additional DP-234/418 AC is declared DONE from these synthetic
proofs; commit-specific GitHub CI is the remaining source-only gate.

### 2026-10-09 Wave 18 — private Studio disconnect and true Capture order

DP-415/DP-419's authenticated, loopback-only browser now invalidates outstanding
read requests and removes cached-in-DOM private links/media locators when the
operator clears their token or changes workspace. A generation check blocks
late responses even when request cancellation loses a race; a Node harness
executes the real inline script with a deferred fetch and proved RED→GREEN.
DP-419 additionally requires timezone-aware persisted Content Capture
observation times to establish the earlier/later comparison labels. It refuses
reversed, equal, naive or missing instants, including offset-disguised reversals,
and presents only the validated timestamp alongside existing safe metadata.

Focused Studio Capture/HTTP/isolated PostgreSQL/JS tests: **31/31 PASS**;
benchmark **5/5 PASS**, repository ticket contract PASS, and launch preflight
unchanged at **NO-GO/41**. No runtime deployment, source rights approval,
media playback, manual screen-reader acceptance or additional ticket closure
is claimed. **86 DONE / 24 IN PROGRESS / 6 BLOCKED / 9 FUTURE**.
The complete Wave 18 test run then passed **2113/2113** Python tests
in **177.304s**, with 100-table backup/restore PASS, 1248 inventoried
technical fields and 89 public-schema fields. This remains Mac-only
verification, not MiniPC runtime or legal clearance.

### 2026-10-09 Wave 19 — persisted match explanation is a contract

DP-418 private read-only matching now validates the classifier's
canonical primary evidence codes for each class/method instead of
trusting a known class/method label with missing, duplicated or
contradictory supporting/contradicting features. Eight tampered rows
first passed improperly (RED); seven classifier-possible signatures
and the tamper rejects now pass (GREEN). The focused matching plus
local Studio HTTP tests passed **31/31**. This creates no reviewer
authority, currentness, match/equivalence approval or production
mutation. **39 open; NO-GO/41** remains unchanged.
The frozen Wave 19 full suite then passed **2115/2115 Python tests**
in **175.612s** with 100-table restore drill PASS; benchmark **5/5**,
ticket contract, compileall and diff checks PASS. No accepted MiniPC
canary, publication rights or review authority is inferred.


## Owner round aggiuntivo — 13 ottobre 2026

Round aggiuntivo13Oct acquisito (60/80 domande multi-progetto): suggerimenti ricerca; recenti per data; filtri cronologia/pertinenza/esiti documentati da affinare senza ranking persone; originale+traduzione; testo come base e audio/video/hosting da approfondire; sintesi+prove; mobile confronto verticale; corrente+storico consentito; copertura contestuale; gruppi eccezioni. Prima di implementare esposizione esiti, verificare semantica e stati del dominio. Per media, approfondire source-use/rights/embed/link/copia e hosting/costi/storage/availability/cancellation tramite ticket esistenti: nessuna scelta implicita del MiniPC. Non riaprire le20decisioni10Oct; nessuna nuova acquisizione/runtime/publish.

Decisione/ricerca futura registrata: nessuna implementazione o acceptance nuova, status e criteri originali invariati.
