# Backlog execution — multi-wave safety, consumers and runtime readiness

Date: 2026-10-11 (Europe/Rome). Starting Git authority:
`8b50e35531500e0ef41492db3d595501524f4f21` (`main`, clean, equal to
`origin/main`, previous GitHub CI 38170184713 11/11 PASS).

## Decision and actual ticket accounting

The owner requested substantive parallel implementations, four independent
workers, repeated task reassignment, consolidation to main and a conservative
four-host WIP/storage audit. Four workers were used repeatedly on independent
code and test lanes while prime handled two cross-cutting faults, reviewed
and integrated commits. New code cannot stand in for source licensing,
qualified legal/editorial approvals, external independent benchmark gold,
production MiniPC readback or browser accessibility certification.

All originally specified acceptance checkboxes for the source-hardening
tickets below remain unchecked unless separately proven elsewhere. The
canonical graph remained **162 total; 90 DONE, 52 IN PROGRESS, 6 BLOCKED,
14 FUTURE, zero READY: 72 not DONE** at the final checked preflight.

| Ticket | Concrete RED→GREEN or functional improvement | Material remaining acceptance |
| --- | --- | --- |
| DP-435 | A public v3 exact-quote authorization with `expires_at=None` was accepted as unlimited. Require a specified nonexpired timezone-aware rights expiry; no implied perpetual license. | Qualified source-specific legal/quotation rights and original-source, public reader/API and MiniPC proof. |
| DP-514 | Isolated SQLite monthly EUR reservation with `BEGIN IMMEDIATE`, policy/revision/record fingerprint CAS, concurrent-connection cap and retry/restart idempotency. Every returned dispatch authority stays false. | Canonical transactional PostgreSQL queue/USD/provider quota, invoice settlements/FX, owner-accepted monthly threshold and MiniPC. |
| DP-519 | Visual exception requests must reference attempts associated with the same work item; median is per-case total handling time, not event fragment. | Real licensed imagery/identity, measured owner minutes, persisted operator decisions and public withdrawal readback. |
| DP-436 | Opt-in backend API v3 detail → exact-wording Astro component with separate summary/translation; stricter shape/hash/locator/endorsement contract. Cross-review then showed altered source metadata passed unchanged claimed dataset SHA. Added *separately trusted* exact record digest requirement and negative SSR tests. | Trusted record pin distribution, genuine approved source, all HTML/search/JSON-LD/RDF/cache consumers, revocation and MiniPC approval; no new public route was enabled. |
| DP-416 | Persisted Collection→Content, Content→Claim and Claim→provenance cursors must be current INCLUDED members of the exact parent and scope; foreign/revoked cursors fail closed, not empty success. | Real Garlasco Capture/Passage/Candidate, full Studio workflow, accessibility and MiniPC. |
| DP-515 | Reject future upstream `Last-Modified` and poisoned persisted/retrodated conditional observations instead of caching an If-Modified-Since that could suppress newer evidence. | Authorized fetch rights, durable lease/fence, real source observation and public revalidation/withdrawal proof. |
| DP-516 | Historical batch resume/skip cannot bypass current source rights and version; pin changed uncommitted source, refuse skip when rights revoked. | Signed real-source batch, durable cross-worker CAS, licensed histories, MiniPC replay. |
| DP-440 | Byte-identical source mirrors do not satisfy two independent citation lineages. Bind synopsis to explicit valid current UTC attestation/snapshot and freeze source locator. | Independent real-source entailment, current rights/revocation, genuinely approved person/topic corpus and public cache acceptance. |
| DP-512 | Real local PostgreSQL failures in existing fact-check discovery: UNKNOWN billing with zero *adapter upper bound* violated SQL CHECK. Correct canonical constraint and add replay-safe migration dropping obsolete named check without inventing positive charges or ZERO_COST. | No production schema migration, provider invoice, owner cost authority or multi-host accounting evidence; keep unpriced dispatch held. |
| DP-518 | Revocation set spanning `rights:1` and `source:1` previously showed apparent consistency when public graph linked only one dependency. Require all revoked dependencies explicitly mapped. | Release/CDN cache epoch, signed revocation and MiniPC/public error readbacks. |
| DP-438 | First-class Person opinion records now bind canonical Statement route, source Content/version and immutable written/timed locator; refuse caller-supplied stale public snapshot fingerprint and mutable source data. | Real rights-approved Person records, production v3 consumers, current revocation/correction and MiniPC. |
| DP-418 | Studio match/review readiness now requires the persisted matching input and promotion context to belong to exact candidate and Content; foreign data cannot report CURRENT/review eligible. | Governed reviewer decisions, real source side-by-side, performance/accessibility and MiniPC. |
| DP-417 | Append-only private Discovery triage demands exact Run→Manifest digest; parent lineage is locked during append; a stale scope cannot reveal old revision/attestation. | Real review authority and source rights, all queue families/bulk actions, production migrations and MiniPC. |
| DP-320 | Concurrent revocation-epoch ticket mint and dependency reads need one atomic snapshot, not separately lockable SELECTs. | Production release/reader fences, distributed cache/public requests, approved authority and MiniPC. |

## Source, QA and rollout boundaries

Changes are scope-isolated and have adversarial RED and GREEN control cases;
several run disposable SQLite or temporary PostgreSQL concurrently under
their own owners, not production. The frontend checks exercise actual Astro
static rendering from synthetic private-api input, never a public licensed
quote. The prior unsafe local full-suite failures in
`tests.test_existing_factcheck_persistence` were independently reproduced as
**three PostgreSQL exceptions** under the canonical billing constraint and
corrected with the DP-512 schema/source compatibility change. Targeted
PostgreSQL + ledger/schema/billing regressions subsequently passed **39/39**.
This does **not** mean a production MiniPC schema was changed. The migration
must be verified on any target schema, including existing named/legacy checks,
before a separate qualified deployment decision. A zero expected provider
charge is never authoritative zero billed cost; UNKNOWN must still hold any
unpriced paid dispatch.

The standalone DP-436 client pin is an *independent-consumer integrity gate*,
not cryptographic signing or a trusted delivery channel. The test fixture
pins its digest before simulating hostile API rebindings. A public caller
must obtain it independently from the accepted release artifact, not from
the very untrusted API response being validated.

After integrating the 15 source commits, targeted privacy, billing,
discovery, candidate review, currentness, public Statement/Person and
revocation suites, repository contract, static field inventory, scoped Ruff
`F821`, deterministic benchmark **5/5**, Astro's type check (zero errors,
warnings or hints), opt-in v3 API→Astro rendering and public-search tests
passed locally. An unconfigured `npm run build` correctly failed closed
because no release projection path was provided. A separate explicitly
fictional `DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build`
then succeeded for 34 demo pages; this is **not** production publication.
A single unrestricted local Python discovery suite on the integrated worktree
finished **2,906/2,906 PASS in 146.051 seconds**, including the isolated
backup/restore drill (**PASS**) and previously failing fact-check PostgreSQL
tests. The run overlapped the final DP-320 worker integration, so it is not
by itself independent certification of the subsequent exact final Git SHA.
Earlier interrupted or failing suites are not relabeled PASS. GitHub CI for
the exact post-push SHA is the independent full-suite checkpoint and must
be inspected after pushing. Do not infer CI success from this document.

## Four-host read-only Git/WIP and storage reconciliation

- **Mac Studio**: canonical Git checkout only `main`, one worktree, zero
  local task branches or stashes, clean before new work. Unreachable objects
  included a superseded amendment; no `git gc --prune` or history deletion.
- **MiniPC `udodo`**: authenticated SSH works; the 34 MiB
  `/home/udodo/src/DichiarazioniPubbliche.it` is the **non-Git deployment
  mirror**, not a second source checkout. No mutations/restarts/migrations.
- **MacBook Air**: authenticated SSH works. No project Git checkout found in
  the bounded expected `Code`, `src`, Codex or temporary worktree paths
  inspected. This does not prove absence outside those paths.
- **MateBook Linux**: SSH connectivity timed out; cannot certify its hidden
  worktrees/WIP or safely delete them. No inferred reconciliation or cleanup.
- Local bounded search found no other DichiarazioniPubbliche Git clone under
  checked Code/Codex/tmp roots. Other unrelated Git repositories and
  `~/tmp/orca-204` (~1.6 GiB, another project) were deliberately preserved.

The only proven selective cleanup removed **four obsolete, generated, unused
Astro preview directories** after a process/reader/ownership/symlink check.
Operator-reported available storage rose by **3,516 KiB = 3,600,384 bytes
(~3.43 MiB)** over the bounded targeted before/after observation. Concurrent
system activity prevents claiming unrelated whole-host volume changes as
reclaimed space. QA receipts, credential stores, runtime data, backups,
rollback state and active `web/node_modules` were preserved. No invented GB.

## Acceptance and further work

All public launch eligibility remains **NO-GO/49**. No authenticated source
clearance, fabricated human signoff or actual Finding was created. No
deployment, bulk fetch, paid calls, MiniPC production DB change or public
artifact release occurred. Original ticket AC and unresolved qualified
legal/editorial decisions take precedence over this engineering note.

The next highest-value closure paths are: a real bounded, rights-reviewed
source/corpus record with provenance from original to Passage and Candidate;
an approved public exact-quote reader/withdrawal end-to-end canary; a
transactionally integrated cost/permission ledger; and independent original
review/false-positive gold plus responsive/accessibility proof. Each needs its
own valid actor, licensing and readback receipt, not a synthetic test label.
