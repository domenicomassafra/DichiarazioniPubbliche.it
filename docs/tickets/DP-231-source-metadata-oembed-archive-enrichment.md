# DP-231 — Pender-style source metadata, oEmbed and archive enrichment

Status: DONE (optional provider contract; production provider lookup disabled)
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-210, DP-118, DP-305

## Problem

DP-210 implemented safe capture, visible-text parsing and an archive adapter state machine,
but the Pender audit also identified high-value metadata/provider behavior not yet ported:
canonical link metadata, OpenGraph/Twitter cards, schema.org/JSON-LD, oEmbed/provider
metadata and asynchronous archive completion receipts.

## Outcome

Enrich Capture metadata with bounded parser outputs and concrete replaceable archive
adapters without running Pender, Rails or Redis as another service.

## Acceptance criteria

- [x] HTML metadata parser extracts bounded canonical URL candidates, OpenGraph/Twitter
  meta fields and bounded schema.org/JSON-LD identity fields without executing scripts.
- [x] oEmbed endpoint candidates are extracted only as bounded HTTPS metadata candidates;
  no external request is made by the parser.
- [x] Map title/description/author/publisher candidates into an explicit metadata contract
  and detect conflicts with source-registry/Content identity.
- [x] Conflicting page/canonical/source-registry identity is explicit and cannot silently
  rewrite Content identity.
- [x] oEmbed/provider network lookups are allowlisted, bounded and optional.
- [x] Extracted metadata is stored as private Capture provenance/context and does not
  independently alter speaker identity, Content identity or factual findings.
- [x] Archive adapters preserve async REQUESTED/PENDING/SUCCEEDED/FAILED semantics and a
  durable archive URL/receipt.
- [x] Rights/access policy can disable metadata/archive operations per source.
- [x] Parser/archive failures preserve the primary Capture.
- [x] No Rails/Redis/Sidekiq runtime dependency is introduced.

## Completion receipt

Local metadata extraction is wired into Capture metadata with focused tests as of
2026-10-05. A pure `source_metadata_enrichment` contract now maps bounded title,
description, author and publisher candidates, validates canonical/oEmbed candidate URLs,
and emits explicit page/Content/source-registry conflicts while keeping both publication
authority and identity mutation disabled. Unsafe/private/credentialed candidate URLs are
discarded and represented only by a digest in conflict metadata. Existing DP-210 tests
also prove parser/archive failure preserves the primary Capture. Provider network lookup remains
open; no oEmbed/provider fetch seam was added by this block.

### Capture enrichment policy + archive receipt follow-up — 2026-10-06

The existing Capture/archive lifecycle already persisted the asynchronous
`REQUESTED -> PENDING -> SUCCEEDED|FAILED` transitions and their completion receipt. The
capture seam now makes the remaining source policy boundary explicit with
`CaptureEnrichmentPolicy`: source `content_policy` can independently disable metadata
enrichment and archive work before either optional operation runs. Metadata-disabled HTML is
still captured and parsed into private Passages, but the default parser does not extract
OpenGraph/oEmbed/JSON-LD metadata and any custom parser metadata is discarded at the Capture
boundary. Archive-disabled sources never invoke the configured archive adapter; the Capture
records `source_archive_policy=DISABLED` while its canonical durable archive state remains
`NOT_REQUESTED`.

A terminal archive `SUCCEEDED` result now additionally requires a credential-free HTTPS
`archive_url` on the default TLS port in its persisted completion receipt. A missing or
unsafe locator is converted to `FAILED` with `ARCHIVE_SUCCESS_LOCATOR_INVALID`, so success
cannot mean only an opaque provider dictionary. Existing request/pending/failure semantics
and primary-Capture preservation remain unchanged.

Focused proof: Capture pipeline + retention + metadata enrichment are **35/35 PASS**;
`python3 -m compileall -q poc tests` and scoped `git diff --check` pass. A repository runtime
dependency search across `pyproject.toml`, `poc/` and `tests/` finds no Rails, Redis or
Sidekiq dependency. The only remaining acceptance item is the optional bounded/allowlisted
oEmbed/provider network lookup; this tranche intentionally does not invent a provider or
network contract.

Final dependency-free acceptance on 2026-10-06 runs Capture + metadata enrichment as **24/24
PASS** locally and **24/24 PASS** in an isolated MiniPC `/tmp` bundle. That proves the parser,
policy-disable, conflict, unsafe-URL and archive-state contracts on the runtime authority without
network access. The remaining AC stays open because the repository still has no owner-selected
oEmbed/provider endpoint, provider-specific allowlist/request budget or approved network lookup
contract; adding a synthetic fetch would not prove that external prerequisite.

### Optional provider-pinned network adapter — 2026-10-08

The first optional network adapter is now implemented in
`poc/dichiarazioni_pubbliche/source_oembed_lookup.py`, using the published
Vimeo `https://vimeo.com/api/oembed.json?url=...` JSON contract. This is an
**engineering-contract completion**, not permission to activate a production
source, proof of a live successful remote response, or approval of any rights.

- `CaptureEnrichmentPolicy.oembed_lookup_enabled` defaults to **false** and
  `capture_enrichment_policy_from_source()` accepts only a source-policy
  Boolean opt-in; disabling metadata disables oEmbed even if the flag is set.
- Only public, exact-host Vimeo numeric-video URLs qualify. The code constructs
  the fixed endpoint itself rather than fetching any HTML-discovered
  `<link rel="alternate">` URL, credentialed URL, unrelated host or raw
  provider-supplied locator. The request is HTTPS, DNS-public-checked,
  redirect-denied, proxy-disabled, 3-second-limited and 8192-byte-capped, with
  JSON-only response acceptance. Future providers need separate review.
- Only bounded title/author/provider candidates and the response digest are
  stored in a **private append-only capture lifecycle event**; HTML embed
  markup, private metadata, arbitrary JSON fields and the raw response are not
  copied. Every candidate explicitly lacks publication or identity authority.
  The original Content Capture and its Passages are immutable across lookup
  success/failure. Replay of an existing Capture skips the network operation.
- A current acquisition permit is revalidated before the optional request.
  If the provider is down, returns an error, changes schema, redirects, or
  returns an oversized/non-JSON response, enrichment fails closed and the
  original successfully captured body/Passages remain intact.
- Focused local suite: **35/35 PASS**; isolated MiniPC `/tmp` canary:
  **35/35 PASS**, cleaned up without production service/DB/provider changes;
  full Mac suite **1822/1822 PASS**, benchmark **5/5 PASS**, compileall and
  `git diff --check` PASS.

The independently published example video `https://vimeo.com/286898202`
returned HTTP 404 from the API when checked on 2026-10-08. That result is
**not** misrepresented as a successful live-provider acceptance: production
source profiles remain unconfigured for this optional lookup. A future real
source activation must pass the source-owner rights/permission and live
endpoint receipt gates separately; `DP-231` does not grant them.

### 2026-10-14 — Source-only private metadata recheck (post-DONE hardening)

An **additive, offline** `private_source_metadata_review_v1.py` now compares
two actual Python capture-parser/metadata-enrichment outputs against
separately expected private SHA-256 receipts and one current validated,
independently SHA-and-generation-pinned public-v2 projection. It never
performs capture, oEmbed/provider lookup, archive operation, network I/O,
Content mutation, source-role selection or editorial publication.

It produces a deterministic bounded owner-only manual review worklist with
field-level changes (title, description, author, publisher, canonical URL,
oEmbed endpoint), newly introduced/resolved typed metadata conflicts, source
use/review holds and a separate `PUBLIC_CONTENT_LOCATOR_MISMATCH` hold.
**No raw URLs, candidate names, titles, private notes or HTML are returned**.
Unchanged input remains `UNCHANGED_REVIEW_PENDING`, never approved or
published. A metadata change does NOT establish source correctness, while an
empty metadata capture does NOT establish absence of original source.

Real Python fixtures run the existing `extract_source_metadata` HTML
parser, `build_metadata_enrichment`, `build_public_projection`, and
`validate_public_bundle`; no fake official-source identity or permission is
introduced. Initial new-module **RED** reproduced on eight tests, followed
by implementation and targeted GREEN. An independent source-only reviewer
identified two important P2 source-identity omissions: a schema-valid,
reviewed standalone public Content with `finding_ids=[]` was overlooked,
and a published canonical Content with the *same* ID but a different URL
from a dossier was silently ignored. Two explicit **RED→GREEN** tests now
require checking both `contents` and dossier source identities within one
identically pinned public release. Valid standalone Content is reconcilable;
ambiguous Content/dossier URL identity refuses fail-closed.

Private projection fixtures and optional-source parser remain separate from
the live owner/source-role authorization: an input `APPROVED` status or a
synthetic SHA does **not** acquire rights or constitute factual verification.
The original DP-231 status remains DONE and **all original AC/status text
is untouched**. This is additional bounded source-contract hardening, not
a new provider, MiniPC or legal/editorial acceptance; independent final
post-fix reviewer and completed full-suite results are separately recorded.

**Definitive combined source-only validation (2026-10-14):** exactly one completed `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc:tests python3 -B -m unittest discover -s tests -q` on detached main with **15 verified byte-identical source/test files** across the new DP-231 feature and published DP-314/DP-320/DP-439/DP-440 worktrees: **3,517/3,517 PASS, exit 0 in 299.292 seconds**. DP-231+adjacent local scope **67/67 PASS**, Ruff check/format PASS, deterministic benchmark **5/5 PASS**. The reviewer independently reproduced the two Content identity P2 cases before these RED→GREEN corrections; the review's bounded post-fix decision is recorded separately, not inferred from implementer test outcomes. No new actual legal rights or oEmbed/provider lookup, no production capture/DB/launch, no MiniPC acceptance, and no Status/AC changes.

**Further independent reviewer P2 after first commit `29feec67`:** worker-9
reproduced a false-clean manual review when two *different* unsafe canonical
URL observations have the same `UNSAFE_CANONICAL_CANDIDATE` conflict code.
The old comparator reduced conflicts to code-only sets, so exact old/new
independently pinned metadata SHA differed while the planner returned
`UNCHANGED_REVIEW_PENDING` and no changed fields. A new deterministic REAL
metadata parser fixture first went **RED**, then the planner began comparing
**full bounded private typed conflict identities** before emitting only the
code `METADATA_CONFLICT_EVIDENCE_CHANGED` and generic
`metadata_conflict_evidence` change flag. No raw conflicting URLs, names,
provider metadata or private notes leave the review-plan DTO. New and
adjacent DP-231 tests now **68/68 PASS**, Ruff/format PASS. The historical
3,517-test run above validated the *previous* SHA, not this newly changed
source: a separate completed full-suite receipt is mandatory before treating
this follow-up as final. Independent post-fix re-review is requested and
its result must be recorded honestly, never inferred from the test count.

**Post-review multiplicity follow-up (2026-10-14):** a separate real
adversarial fixture showed another false-clean case in the same conflict
identity comparison: one blocked private canonical candidate versus **two
identical** blocked candidates changed the exact independently pinned
metadata snapshot but a `set` comparison lost the duplicate row. The
`test_duplicate_same_private_conflict_changes_evidence_cardinality` test
was genuinely **RED**, then changed the comparison to a deterministically
sorted **multiset** (tuple with multiplicity) of validated private typed
conflicts; the review output still contains only generic changed-field and
reason codes, no raw candidate URL or title. DP-231 new+adjacent local
regression **69/69 GREEN**. A full Python run started before this last
source fix was deliberately interrupted by TERM (not counted as PASS), and
will be replaced by one completed full-suite receipt on the final bytes.
Reviewer independent re-execution of this last exact duplicate case is
required before claiming a final source-only PASS.

**Final source freeze after both same-code P2 fixes, 2026-10-14:** the
multiset comparison preserves identical private conflict cardinality and
an independent reviewer (worker-9, strict read-only, no Git/source changes)
replayed (a) same conflict code / different private observed URL hashes,
(b) duplicate identical unsafe candidate one vs two, and (c) reordering
of distinct observations. Both real SHA-pinned changed-evidence cases now
require human review, whereas reordering remains unchanged; no raw private
URL, hostname, private fingerprint, candidate title or source body leaks in
output. Its independent new+adjacent **101/101 tests PASS** and bounded
**no remaining P1/P2 reproduced** apply to this code-only source contract,
not source rights/provider/CDN/public deployment acceptance.

The **single final completed** five-lane full Python suite on exact
byte-identical code/tests is **3,519/3,519 PASS (exit 0, 293.855 s)**,
`python3 -m dichiarazioni_pubbliche.benchmark` is **5/5 PASS**,
Ruff/formatted-check PASS. The earlier **3,517/3,517** full run was on
pre-P2 bytes; another pre-final run was interrupted by TERM after the
same-root duplicate finding and is **NOT** counted as a completed result.
This post-DONE receipt changes no original DP-231 Status/AC and does not
claim approved official source selection, capture, provider access,
MiniPC, legal/editorial authority or publication.

### 2026-10-14 — Private multi-Content source metadata cohort (post-DONE product extension)

The separate **source-only/offline** `private_source_metadata_cohort_v1.py`
consumes two owner-supplied, independently pinned public-v2 projections
(previous/current dataset SHA-256 and generated-at) plus two independently
SHA-pinned private metadata inventories. It returns one stable **opaque
SHA-256 Content reference** per in-scope Content, deterministic counts and
reason codes for manual review. It runs existing DP-231 single-Content
reconciliation on records present in both inventories. It NEVER includes
raw Content IDs, candidate titles, unsafe canonical URLs, source bodies,
private reviewer notes, oEmbed network responses or identities in the DTO.
No source/Content mutation, web request, capture, provider, DB write,
automated source approval, factual verdict or editorial publication occurs.

The product explicitly handles public Content without Findings, source
URL disagreements between dossier and public Content representations,
private metadata inventory arrival/absence vs *actual public Content*
addition/retirement, rights/review holds, canonical-source changes across
a pair of releases, and changed same-code private conflicts (including
duplicate evidence cardinality). Every public dataset, metadata read model,
release generated-at and per-source review/use policy is validated before
classifying; generation time rollback and reused generation timestamp for a
different dataset SHA fail closed. Identical content with reordered private
inventory entries is deterministic. `UNCHANGED` still means only
**manual review pending**, never approved source or factual acceptance.

An initial **RED** proved the module was not implemented. Three additional
saved adversarial **RED→GREEN** tests prevented mislabeling missing/new
private metadata as retired/new public Content, and prevented same-time
changed-dataset release identity from masquerading as an ordinary update.
New and adjacent Python **83/83 PASS** with Ruff/format PASS at initial
code freeze. An independent reviewer, complete full suite, and final exact
Git SHA are recorded in a subsequent receipt; until that evidence exists
**review/final release remains PENDING**. This extension does not change
DP-231's original Status/AC or resolve the owner/legal/physical/production
provider permissions associated with source capture and publication.

**Adversarial DP-231 cohort follow-up:** independent reviewer worker-9
identified the material risk that a newly published first-class Content
may be absent from BOTH private metadata inventories while still appearing
in the pinned public-v2 projection. The first implementation counted only
inventory IDs and falsely returned `IDLE_PRIVATE_REVIEW_PENDING`. Two real
Python public projection fixtures proved this **RED**: (1) newly published
standalone Content with no metadata, and (2) all current public Content
with neither private metadata entry. The planner now reconciles the
**complete bounded union of public dossier and first-class Content IDs**
from both pinned releases together with inventory IDs. Such items yield a
specific `UNSCOPED_PUBLIC_CONTENT_REVIEW`, contribute to `held_count`,
and force `MANUAL_COHORT_RECHECK_REQUIRED` without inventing source-policy
approval. The public scope is capped at 256 IDs; larger input refuses
rather than showing a misleading clean summary. Both RED tests are GREEN.
Separately, three earlier RED→GREEN tests distinguish missing/new private
metadata from retired/new public Content and reject two different public
datasets sharing an identical owner-issued generation timestamp. All status
and output values remain private, opaque and non-authoritative. At this
last source freeze, **85/85 new+adjacent tests PASS**, Ruff/check/format PASS.
The independent reviewer has been asked to re-review this complete post-fix
diff; the completed full Python suite and exact branch SHA must be added
only after actual final execution/readback. No Status/AC change or new
owner/legal/physical/provider acceptance follows from this local artifact.

**Final code-frozen six-lane integration, 2026-10-14:** one Python
`unittest discover -s tests -q` on a detached main checkout containing
**17 byte-identical source/test files** from DP-231 base, this new DP-231
cohort, DP-314 private research wave, DP-320 RDF/SEARCH, DP-439 temporal
and DP-440 cited synopsis branches completed **3,535/3,535 PASS, exit 0
in 296.985 s**. The deterministic benchmark passed **5/5**; DP-231 cohort
plus prior DP-231/source-enrichment/public-projection adjacent subset
**85/85 PASS**; Ruff lint and format checks PASS. Astro `npm run check` on
the new branch reported **123 files, 0 errors, 0 warnings and 1 preexisting
hint**. Isolated empty/demo Chrome keyboard/AX/reflow/200% zoom and the
production projection boundary all PASS, with DP-429 public suggestions
contract PASS. These are local offline/isolated source tests, not PR CI,
production release, source-rights grants, editorial sign-off or MiniPC.
The repository's original DP-231 status and AC remain untouched.

**Independent postcommit P2 follow-up on first cohort SHA `04ca313`:**
Worker-9 (strictly read-only) reproduced a false clean rights-policy outcome
using a mutable caller-owned policy dictionary: after `REVOKED/PENDING`
validated, a downstream canonical-URL read changed that dict to
`APPROVED/APPROVED` before the planner reread it, producing an erroneous
`IDLE_PRIVATE_REVIEW_PENDING`. The new saved **RED→GREEN** fixture mutates
policy at exactly this boundary. The planner now builds an exact typed
validated policy snapshot before ANY such URL calculation and reads only
this detached snapshot; the revoked source returns `WITHHELD_SOURCE_POLICY`
with held count 1. This is a private source contract preflight, not a live
issuer or legal permission guarantee.

The same independent reviewer reproduced a separate P2 on real public
lifecycle: metadata for a newly published standalone Content may predate
its public release, or private metadata may survive Content retirement.
The first cohort implementation eagerly resolved every private record
against BOTH public releases and raised `COHORT_PRIVATE_METADATA_NOT_PUBLIC`
rather than returning a typed new/retired review. Two true saved RED fixtures
now pass: the planner derives public membership from each complete pinned
release first, validates locators **only where the Content was public in
that release**, and classifies actual public additions/retirements before
private metadata arrival/absence. Metadata that was NEVER public on either
side gets an explicit `PRIVATE_CONTENT_NOT_PUBLIC_HOLD`, with no raw ID leak.
The complete public Content union still catches unscoped new Content and
all same-ID canonical URL contradictions. Targeted new/adjacent tests
**88/88 PASS**, Ruff and format checks PASS. The previous completed full
suite **3,535/3,535** applies to **pre-fix SHA `04ca313` only**, not this
subsequent source. An independent final re-review of BOTH P2 patches and
one new final full suite are required before claiming final PASS on the
follow-up commit. No original Status or AC were changed.

**Final independent reviewer re-check of both postcommit cohort P2 fixes:**
worker-9 executed a strictly read-only, source-only audit on the exact
final owned source/test diff. Genuine independently pinned public-v2
release fixtures prove a new standalone Content absent both metadata
inventories yields a held `UNSCOPED_PUBLIC_CONTENT_REVIEW`; newly
published/retired Content with already-present private metadata gives
`NEW_CONTENT_METADATA_REVIEW`/`RETIRED_CONTENT_REVIEW` rather than an
exception. In-memory `source_policies` deliberately changed from
`REVOKED/PENDING` to `APPROVED/APPROVED` during the later canonical-URL
operation now cannot change its validated private policy snapshot: the
source stays `WITHHELD_SOURCE_POLICY`, held count 1. Never-published
private-only Content returns a hold without ID or URL echo; stale private
SHA refuses. Reviewer independently ran **72/72 bounded tests PASS**
(cohort19, single-Content DP231 15, enrichment6, schema32) and reported
**NO additional reproducible P1/P2 in that scope**. The reviewer wrote no
code, tests, docs, Git, host, DB or provider state. This finding does
NOT establish authenticated owner-issued permit, production HTTP/CDN
withdrawal, MiniPC, rights, legal/editorial or publication acceptance.

**Final post-P2 code-frozen six-lane proof (2026-10-14):** after the
rights-policy snapshot and actual public Content-lifecycle fixes, a detached
main worktree with the exact **17 byte-identical code/test paths** from the
six delivered source-only lanes completed
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc:tests python3 -B -m unittest discover -s tests -q`
**3,538/3,538 PASS, exit 0, in 289.038 seconds**. The earlier completed
3,535/3,535 suite verified the superseded 04ca313 source, NOT the present
patch. Focused new+adjacent owner tests **88/88 PASS**; independent source
reviewer tests **72/72 PASS** in the bounded described scope. Deterministic
benchmark **5/5 PASS**, Ruff and format checks PASS, Astro check **123 files,
zero errors/zero warnings, one existing hint**, and isolated empty/demo
keyboard/AX/mobile-reflow/200%-zoom + production boundary checks PASS.
These are LOCAL source-only, synthetic public-v2 and offline browser
contracts, NOT branch-PR CI, owner-issued source approval, live retrieval,
legal rights, real HTTP/CDN withdrawal, provider success, editorial
publication, production DB, deployment, or physical MiniPC acceptance.
Original DP-231 Status and all AC are intentionally unchanged.
