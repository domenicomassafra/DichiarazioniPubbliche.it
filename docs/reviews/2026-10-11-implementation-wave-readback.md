# 2026-10-11 — source-only implementation wave, evidence and remaining gates

Status: **partial source implementation verified locally, NOT a runtime/release acceptance**.
The owner separately authorized actual ticket implementation after closing the
2026-10-10 planning-only mandate. Source branch is `main`; production mirror,
providers, real source acquisition, public publication, DB migrations and push
were not authorized or performed in this run.

## Commits and bounded implementation

| Contract | Commit(s) | Narrow change delivered |
|---|---|---|
| DP-236 | `acf6541` | Exact reviewed source-family/private use/expiry/revocation guard, opt-in capture seam |
| DP-237 | `6bd8532` | Exact pinned written/page/media Capture/Passage locators, immutable source hash/version checks |
| DP-312 | `6404079` | Conservative private speech-act/context/quoted-speaker assessment without publication authority |
| DP-318 | `d01fb22` | Pure same-Person versus cross-Person relation scope/temporal/endorsement preflight |
| DP-435/437 | `2405049` | Optional public-v3 original-quote-only Statement projection, independent gates, nullable Finding |
| DP-436 | `4a7afbf`, `caa5c5c`, `ce60baf`, `d6fb004` | Optional JSON/RDF/JSON-LD plus isolated Astro verbatim renderer and backend→client parity |
| DP-429/439 | `df6fa42`, `5c72563`, `f8b2b6e`, `2f2dba4` | Public-v2-only verified Person × Topic intersection, no private facet or paraphrase-as-quote |
| DP-512 | `c6d55c7` | Cost estimate no longer falsely recorded as measured; local energy UNKNOWN preserved |
| DP-514 | `e2df061` | Owner-versioned EUR/month reservation preflight with DST/FX; disabled, no dispatch |
| DP-238 | `c366514` | Opt-in bounded native-document text/XML/HTML source/parser/Passage candidates; scanned PDF/OCR explicitly held |
| DP-313 | `6afb00f` | Private procedural role/jurisdiction/negation/status guard; no allegation→fact or legal approval |
| DP-438 | `7e8bbbb` | Isolated v3 PublicPerson read model with separately approved zero-Statement identity |
| DP-515 | `3cb5d93` | Source-version, conditional 304, outage/backoff and gate-checked incremental watch proposals, disabled |
| DP-319 | `6152dd0` | Bounded private investigation plan over existing reviewed ResearchAssignments; no invented URLs or infinite/paid actions |
| DP-320 | `7ed9eb3` | Isolated SQLite epoch/CAS source-vs-artifact revocation and read fence with durable outbox, NO production Postgres/edge claims |
| DP-315 | `20c63eb` | Private three-track denial: uttered vs endorsed vs meant, scope/source/currentness, no universal-absence proof |
| DP-239 | `aedced9`, `45167d2` | Original-language immutable text and separately versioned, always-held machine translation risk contract |
| DP-440 | `fbecfea` | Opt-in offline sentence-level pre-reviewed synopsis with exact v3 Statement citations, conservative abstention |
| DP-244 | `10dd9af` | Bounded source coverage status and version delta with no fabricated global completeness or dispatch |
| Inventory/status | `5b8edb7` | Versioned privacy allowlist extended conditionally, historical test count unfrozen, ten ticket statuses reconciled |

## Verifications (local Mac, not MiniPC production)

- Initial integrated Python test run: **2492 tests**, 4 FAIL and 1 ERROR. All five were traced to the *known plan change* (one old hardcoded 125-ticket assertion) and *new v3 public schema allowlist* (four tests using stale privacy inventory).
- Regenerated the canonical `privacy-field-inventory.v1.json` with the provided `--generate` tool. Compared output: only one new `PUBLIC_STATEMENT_ALLOWED_KEYS` conditional group (21 fields), no DB schema change or public-authority grant. Targeted inventory tests **17/17 PASS**.
- Final integrated Python suite: **2499/2499 PASS** (`PYTHONPATH=poc python3 -m unittest discover -s tests -q`, **147.424 seconds**); deterministic benchmark **5/5 PASS**; compileall PASS.
- Wave 3 additions were checked independently: DP-238 11 new tests (plus 28 relevant baseline checks), DP-313 24 new tests, DP-438 10 new tests, DP-515 17 new tests (plus 33 selected regressions) PASS. The all-repository rerun including wave 3 is a **separate gate** and must not be inferred from the earlier 2499/2499 run.
- Wave 3 integrated backend suite: **2561/2561 PASS**. Wave 4 focused tests PASS for DP-319 (11), DP-320 (7), DP-315 (10), DP-239 (13), DP-440 (9), DP-244 (10). **Final Wave4 integrated Python suite: 2621/2621 PASS in 154.305 seconds**, directly rerun from the shared completed source state; benchmark deterministic **5/5 PASS**, compileall and repository contract PASS.
- Web: search-index and v3 statement synthetic tests PASS; **backend→Astro v3 parity PASS**; `npm run check:design` PASS; Astro check **89 files, 0 errors/warnings/hints**; isolated production projection boundary PASS (renamed demo excluded, private Studio absent, public-empty sitemap correct, legacy v2 compatibility and drift rejection).
- Browser QA on **both isolated approved-empty and opt-in populated demo** passes keyboard, automatic accessibility tree, zoom and the public Person × Topic URL intersection; no live device VoiceOver or v3 release implied (`b4caa2a`).
- Repository contract PASS and `report_ticket_status.py --json` reports exact file/PLAN agreement: **162 total, 90 DONE, 40 IN PROGRESS, 6 BLOCKED, 26 FUTURE (72 not DONE)**. `check_launch_preflight.py --expect-no-go` returned **NO-GO with 49 blockers**, mostly Q-306/legal/source/release artifacts; this is the expected safe stop, not evidence of an authorized release.

## Invariants / not yet achieved

These first source modules are **not connected to real authorized source data**.
The v3 schema, API serialization and Astro component are opt-in/isolated.
They do not make new records available over a public URL, automatically
promote a candidate or grant independent publication consent. The old public
v2 source is still default and its previous no-private-body protections remain.

Important dependencies still open:

1. DP-236/317 actual source-specific lawful fetch/excerpt permits, legal/privacy
   Q-306/DP-307 dispositions, effective policy and source use records;
2. DP-312/313/314/316/321 reference accuracy/gold on authentic multilingual
   texts and procedural documents; the old human authority never auto-migrates;
3. DP-318 legacy callers still need authenticated `person_id` and v3 relation
   currentness; a private comparison alone does not prove position change;
4. DP-435/436/437/438/439/440 real source/rights-attested Statement→Person×Topic
   read model, original-language quote in ALL public consumers, cite-per-sentence
   summary and atomic correction/revoke/cache handling;
5. DP-512/514 real billed EUR/energy and durable per-owner cap/CAS, not merely a
   correct offline estimate and synthetic concurrency;
6. DP-443 real, rights-cleared source→capture→candidate→eligible fact/opinion→
   source-cited public reader→correction/rollback MiniPC acceptance, prerequisite
   to any large historical backfill or stable v1.
7. DP-238 native text parsing is not yet validated PDF OCR; DP-313 document roles
   need authenticated real judicial source and independent semantic gold; DP-438
   requires true public-identity authorization plus reader/API route; DP-515
   needs persisted CAS/lease and source-family permissions before dispatch.
8. DP-319 source investigation requires a durable append-only attempt ledger,
   actual permissible adapter/credential receipts and private Studio inspection;
   DP-315 authentic denial/speech acts and independent completeness evidence
   remain held; DP-239 needs independent de→it meaning gold and rights.
9. DP-320 only has a local SQLite transaction reference: production Postgres
   CAS, material dependency graph, edge/CDN stale-response denial and measured
   MiniPC revocation latency are unproved. DP-440 accepts externally reviewed
   sentence/topic proofs only as an opt-in private contract; no real autonomous
   factual synthesis/public website route is live. DP-244 freshness is bounded
   to observed source/window, with no global-corpus completeness assertion.

No owner redesign has been chosen. No public feed, Google member account or
remote privileged administration has been enabled. The 2026-10-10 planning
packet response remains a separate untracked terminal file by design.

## Fifth local source-only tranche — 2026-10-11

Three bounded independent contracts, **none a complete ticket acceptance**:

| Ticket | Local commit | Bounded source behavior |
|---|---|---|
| DP-240 | `cafe1e1`, test correction `100a1dd` | Multi-Person, multi-Content private candidate plan with per-Passage source hash/context/person candidate partition, quotes/homonyms HELD, bounded token proposals and fail-closed result/plan replay; no provider dispatch or attribution approval |
| DP-314 | `adedac9` | Opt-in VerificationRequirementProfile preflight: source roots/roles/jurisdiction/cutoff and state separation for not-checked, nonfactual, unsupported, insufficient, conflicting and only pending verification; **never** a fact verdict |
| DP-241 | `2451869` | Source-only original recovery planner with two independent authorized-method families, DP-237 selector/hash and reviewed-root candidate binding, rights/cost/outage/not-found/insufficient reconciliation, attempts and stale-version holds; no actual research |

Local synthetic focused evidence: **DP-240 15/15** (plus existing private candidate batch **27/27**), **DP-314 10/10** (plus legacy verification **19/19**), **DP-241 16/16** (worker independently reported **58** related tests), `compileall` PASS. DP-241 result/plan checksum validation is a consistency check, not authentic review or upstream permission; the final reserved `dispatch_authorized=False` guard and adversarial test passed after the first integrated suite had already started.

The first full Python suite covering this tranche finished **2662/2662 PASS in 168.700 s**, including isolated restore drill PASS; benchmark **5/5 PASS**, source contract PASS. The **second full Python suite** (after the final DP-241 authorization/tamper guard) finished **2662/2662 PASS in 166.154 s**, isolated restore drill PASS. `ruff check` PASS; final source/test formatting normalized in `219592e`, `ruff format --check` PASS; focused DP-240 **15/15** and DP-314 **10/10** reconfirmed after formatting. No frontend sources changed in wave5, so earlier web QA remains a previous checkpoint, not a new run.

Ticket register/PLAN agree: **162 total, 90 DONE, 43 IN PROGRESS, 6 BLOCKED, 23 FUTURE, 72 not DONE**. Preflight correctly returned **NO-GO / 49 blockers**, dominated by legal/privacy Q-306, source rights/actual source pilot, reviewer and release artifacts. DP-443 remains an unperformed mandatory real, legally-cleared source→Capture→Passage→candidate→public read→correction/revocation MiniPC pilot. No actual source fetch, paid model, provider, DB mutation, owner redesign choice, public activation, push or deploy was performed. All new DP-240/241/314 acceptance boxes remain open awaiting real independently verified evidence.

## Sixth local implementation tranche — 2026-10-11

The Mac checkout acquired six **local** source/test commits (no push, deploy,
provider run, live source fetch, publication, production DB or remote changes):

| Ticket | Source/test commit | Real implemented boundary, not full acceptance |
|---|---|---|
| DP-242 | `d2d1729`, `74b5d56`, strict route inventory `b46e3d9` | Existing DP-417 persisted scoped Discovery Hit and DP-418 exact candidate-match reread drive bounded private held machine-intent/exception previews. Two **actual authenticated localhost HTTP routes** exist, strict body fields/token/Origin/no-store; source/Capture/revision changes and forged approval fields are refused. No authenticated B authority, persisted machine dispatch, public mutation or new human review |
| DP-243 | `4a586dd` | Small, versioned IT/DE and historical Person-scoped private synthetic manifest guard over original/derivative/translation/rights/repost/source-version data; **no actual historical corpus created** or archive rights assumed |
| DP-321 | `12bfb5a` | Reference-manifest and independently sourced-label **contract only**, guarded against same-model labeling, shared-root split leakage and ambiguous false gold; explicit metric denominators, stratification, Wilson descriptive intervals, abstention/coverage, cost/drift, no accepted gold/threshold/release |
| DP-316 | `fa647a9` | Offline profile/material/risk/DP-320 structural-fence/challenger preflight integrating DP-314 and DP-308/309 data; all machine signoff/publication/dispatch properties **false**. Human review legacy untouched, off-DB authority and qualified decisions absent |

Focused local verification reported **26 Studio/DP-242 tests PASS**, then
**34 API/Studio tests PASS** after HTTP integration; **99** combined selected
DP-236/237/241/243/244/515/321 tests PASS; **15** focused DP-316 synthetic
tests PASS and **56** combined wave6 tests PASS after the final DP-316
fixture. Ruff lint/formatter were checked for new files and direct regression
tests returned GREEN.

**Important genuine RED then fix:** the first concurrent full Python discovery
was started before the stricter private-Studio route allowlist changed. It
finished with **2718 tests, 3 errors**, *all three* isolated to the expected
`CONDITIONAL_PRIVATE_STUDIO_PATH_SCOPE_CHANGED` inventory divergence on
`test_conditional_surface_absence` and launch-preflight. The intentionally
fail-closed launch safety control correctly detected a route scope not yet
registered. We registered exactly the two new private, read-only preview paths
in `conditional_surface_absence.py`; negative tests reject arbitrary machine
approval, enqueue and publish paths. Post-fix focused tests **7/7 PASS**;
`check_launch_preflight.py --expect-no-go` again succeeds with the expected
release **NO-GO**, and repository contract PASS. This is not permission to
open Studio remotely or alter the DP-507/508 admin/intake exemptions.

**All four ticket states are IN PROGRESS; every ticket acceptance box remains
unchecked** pending real signed independent decisions, allowed source bodies,
persisted exception/replay/B machine authority, independent gold/reference
provenance and MiniPC transactional source→public reader→correction/rollback
DP-443 canary. No release/publication readiness follows from these contracts.
The initial untracked prompt-response handoff remains untouched.

**Final frozen post-fix verification:** `PYTHONPATH=poc python3 -m unittest
discover -s tests -q` finished **2719/2719 PASS** in **239.105 s**, exit 0,
including isolated restore drill PASS. The first 2718/3-error run above is
historical RED evidence, not the final state. `PYTHONPATH=poc python3 -m
dichiarazioni_pubbliche.benchmark` **5/5 PASS**, `python3 -m compileall -q
poc tests` PASS, `ruff check` on all changed Python source/tests PASS,
`check_repository_contract.py` PASS, `git diff --check` PASS. The versioned
release gate `check_launch_preflight.py --expect-no-go` passed with
**NO-GO / 49 blockers**, not GO. Ticket/PLAN status source agreement PASS:
**162 tickets, 90 DONE, 47 IN PROGRESS, 6 BLOCKED, 19 FUTURE, 72 not DONE**.
No independent evidence/authentic gold/owner legal decisions or production
MiniPC DB/reader cutover were performed.

## Seventh local source-only tranche — 2026-10-11

No push/deploy, production/mirror database mutation, signed archive permission,
real primary content acquisition, commercial model, public publication or
qualified policy decision. Four independently tested modules:

| Ticket | Local source commit | Safety and functionality actually implemented |
|---|---|---|
| DP-518 | `8bd5cc5` | Exact release/material-epoch/proposed generation hashes, exhaustive twelve public consumers including edge cache, explicit 404/410 vs unsafe old 200/readback, no missing Consumer as green. Even structurally consistent caller-supplied readback returns `CONSISTENT_UNATTESTED`, never real MiniPC/CDN clearance. Isolated DP-320 SQLite revoked-rights read-fence integration test |
| DP-516 | `46628d1` | Bounded private historical batch plan from DP-243 rights/role/version, DP-514 EUR budget and legacy USD guard, DP-515 watch, an explicit independently verifiable *claim* of signed DP-443 acceptance, replayable no-duplicate checkpoint and changed-source holds; no jobs, durable reservation or real approval |
| DP-317 | `1aac45c` | Per-source-version/representation/public-use/quote/context/selector/expiry/region scope over DP-236 private rights and DP-224 exact binding; translation distinct from original, unknown/revoked/copy/film rights held. No legal signoff or public words activated |
| DP-519 | `084a77a` | Metadata-only private visual queue with append-only input receipts/replay/currentness, image identity/rights/age/expiry, ISO-week split of actual minutes, separate forecast, capacity deferral and no-image fallback. No human fact-review/image-publish authority, no real owner-time claim |

Local source-focused RED→GREEN evidence: DP-518 **11** focused tests plus
existing DP-320 **7** PASS; DP-516 **15** focused and **49** selected
DP-516/243/515 PASS; DP-317 **10** focused and **39** selected DP-317,
quote binding, DP-236, DP-320 PASS; DP-519 **16** focused and **26** including
existing Studio operator queues PASS. Additional mixed new-contract run **59
PASS**. Ruff lint/format on all eight new source/test files PASS, compileall
PASS, benchmark **5/5 PASS**, repository contract PASS, release preflight
**NO-GO / 49 blockers** as expected. No new UI, public/Studio API routes or
production schema were changed in this tranche.

Ticket register and PLAN: **162 total, 90 DONE, 51 IN PROGRESS, 6 BLOCKED,
15 FUTURE, 72 not DONE**, with exact agreement. AC-317, -516, -518, -519
remain unchecked and require real independent qualified rights, authenticated
review/DP-443 first full pilot, MiniPC source→public→correction and distributed
revocation/rollback, durable budget/checkpoint, plus owner visual sample.
The original untracked post-grilling handoff response remains untouched.

**Seventh tranche final integrated proof (after all four source/test commits):**
`PYTHONPATH=poc python3 -m unittest discover -s tests -q` **2772/2772 PASS**
in **159.267 s**, process exit code 0, including the isolated SQL restore drill
**PASS**. `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`
**5/5 PASS**, `python3 -m compileall -q poc tests` PASS, Ruff lint and format
on the eight new Python source/test files PASS, `check_repository_contract.py`
PASS, `git diff --check` PASS. `check_launch_preflight.py --expect-no-go`
returned the expected **NO-GO with 49 blockers**; it is not an approval.
The full test suite demonstrates local source/test consistency only; no live
qualified rights, MiniPC/Cdn invalidation, actual historical batch or source
authorization, autonomous public assertion or owner-approved visual image.

## Eighth local implementation tranche — 2026-10-11

All actions stayed in the Mac checkout; no live MiniPC DB, paid provider,
actual source body acquisition, rights authorization, public route activation,
push or deploy. Tickets remain IN PROGRESS:

| Ticket | Commit | Actual implementation and local evidence |
|---|---|---|
| DP-238 | `4e6a465` | Optional pypdf born-digital page text extraction in bounded subprocess; exact source SHA and deterministic private Passage/page hash/selector replay; 19 combined native/PDF tests PASS; old parser unchanged by default, extraction never certifies source wording/OCR/rights; PDF fixtures synthetic |
| DP-429 | `cf70a4f` | `/esplora/` approved-empty projection displays `0 risultati pubblicati` via atomic ARIA status, truthful empty-index lede. Isolated real Astro build and fingerprint/index negatives PASS; local Chrome keyboard/reduced motion/actual 200%-zoom QA PASS. No user-verified real screen reader |
| DP-436 | `352cb78` | Opt-in v3 parity gate across existing authorized projection serializer to API, JSON-LD and canonical RDF, including source/quote IDs, original/derived representation and revocation; 9 focused and 32 selected related tests PASS. Not activated on the public v2 read path |

The separate DP-519 persisted Studio/operator endpoint did not produce a
verifiable implementation in this tranche and was left untouched. The earlier
untracked post-grilling handoff file was not modified. Product/user acceptance
still requires authentic source-specific legal grants, independent gold,
signed DP-443 real MiniPC first-full pilot, reader/revocation/rollback and
remaining DP-429 screen-reader/manual acceptance. No AC was silently marked.
