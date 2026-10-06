# DP-232 — Existing fact-check lookup adapter

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-228, DP-215

## Problem

The research ecosystem selected Google Fact Check Tools and existing ClaimReview corpora
as cheap external lookup sources, but the current evidence planner has no dedicated adapter.

## Outcome

Add a provider-neutral EXISTING_FACT_CHECK research adapter, with Google Fact Check Tools
as one possible implementation and CIMPLE/other ClaimReview corpora as replaceable sources.
Existing fact-checks are secondary/context evidence and discovery aids, not automatic truth
authority.

## Acceptance criteria

- [x] Google response normalizer returns reviewed-claim text, publisher, review URL/date,
  textual rating and original claim metadata when available.
- [x] Fixed-endpoint Google adapter supports bounded query, language, publisher, max-age,
  page-size and page-token parameters with injected transport for deterministic tests.
- [x] Provider receipt omits API key/full URL/raw query and retains a query hash.
- [x] Persist normalized lookup results and retrieval receipt through the DP-228/DP-209
  research lane.
- [x] Result preserves provider/source identity and bounded retrieval receipt.
- [x] Existing fact-check verdict/rating has no field/path mapping directly to our Finding
  assessment.
- [x] Same upstream ClaimReview mirrored by several services counts as one derivation
  lineage when identified.
- [x] Missing API key fails explicitly before any network request; DP-228 integration must
  map this to its BLOCKED/not-configured state rather than empty success.
- [x] Query/result/cost limits are inherited from persisted DP-228 assignments; the local
  client already enforces a bounded page size/max-age request contract.
- [ ] Rights/public projection expose only allowed metadata/links.
- [x] Pure outward ClaimReview interoperability accepts only an already-public `PUBLISH`
  dossier with publication/evidence/speaker review provenance and a publishable canonical
  assessment; held/private/unapproved inputs fail closed and the adapter has no network or
  publication-authority path.
- [x] Outward ClaimReview preserves exact finding/claim identity, supersession lineage,
  policy/verification ids and canonical assessment/vocabulary versions without remapping
  the assessment to an invented verdict scale.
- [x] ClaimReview interoperability creates no person score/rank/reliability field and no
  numeric rating scale or intent inference; the schema.org `reviewRating` is claim-scoped
  and carries only the exact canonical assessment as `alternateName`.

## Completion receipt

Google Fact Check Tools normalizer + bounded client contract added locally 2026-10-05.
No live API call or key was used. A separate pure `claimreview_interop` export adapter now
operates only on the validated public-dossier contract, preserves exact finding/assessment
identity and fails closed on held/private/unapproved input without granting publication
authority. Live-provider credential/receipt proof remains open; no live provider is needed
for the local runtime/persistence acceptance below.

### Persisted mirror-lineage follow-up — 2026-10-06

Added an additive private persistence seam in
`poc/dichiarazioni_pubbliche/existing_factcheck_persistence.py` plus migration
`20261006-add-existing-factcheck-mirror-lineage.sql`. It reuses the existing DP-228 ->
DP-209 research contract rather than creating a second discovery lane: a mirror can be
persisted only when its DP-209 hit belongs to a `HEALTHY` attempt, the hit is accepted,
the provider matches the attempt adapter, the URL/external identity matches the hit, and
the persisted DP-209 query metadata carries the same DP-228 `research_assignment_id` with
lane `EXISTING_FACT_CHECK`. The bounded provider receipt already persisted by DP-209 is
retained by deterministic SHA-256 reference; no API key, raw request URL or provider body
is introduced here.

Mirror history is append-only and versioned. The explicit upstream ClaimReview record ID
defines one deterministic lineage across providers. Source version and caller-supplied
source content SHA-256 define immutable version rows; a new version must explicitly
supersede the current leaf, so the prior version becomes derived `HISTORICAL` and the new
leaf `CURRENT` without rewriting old observations. Exact replay of the same
provider/external-ID/version/material is idempotent. Reusing that same provider external
ID/version with changed normalized material, or reusing the same upstream source version
with a different content hash, fails closed. Two synthetic provider mirrors of the same
identified upstream ClaimReview persisted as two mirror observations but exactly one
lineage and one source-version row, closing the mirrored-upstream derivation AC without
claiming evidence independence or truth authority.

DP-305 remains separate and fail closed. The persisted mirror defaults to `UNKNOWN`
rights and this seam never upgrades rights. `public_mirror_metadata()` exposes only
bounded lineage/version/provider/publisher/date/link metadata and omits the private
normalized claim text, textual rating, review title and claimant. `decide_mirror_excerpt()`
binds the exact persisted mirror URL/version/hash and replaces any caller-supplied rights
value with the persisted source rights before delegating to canonical DP-305
`decide_excerpt()`. Tests prove callers cannot turn `UNKNOWN` or `BLOCKED` mirror rights
into a public excerpt by passing `CLEARED`, and the metadata-only mirror object is rejected
by outward `claimreview_interop` because it is not an already-public reviewed dossier.
The generic public projection still reads none of the private mirror tables.

Disposable PostgreSQL acceptance: **8/8 PASS**. Related existing-factcheck,
ClaimReview-interop, DP-228 planner, DP-209 discovery and DP-305 rights regressions:
**107/107 PASS** (**115/115** combined). An isolated MiniPC `/tmp` bundle, with production
database and provider/API environment removed and its own PostgreSQL 18 temporary cluster,
also ran **115/115 PASS**; all temporary files/processes were removed afterward. No live
Google/provider request or production database mutation occurred.

The DP-305 boundary is proven locally, but the rights/public-projection AC stays open until
an approved mirror metadata/link surface is wired into the canonical Public projection.

### DP-228/DP-209 runtime wiring follow-up — 2026-10-06

Added `poc/dichiarazioni_pubbliche/existing_factcheck_runtime.py`, a provider-neutral
runtime bridge with **no built-in network client**. It accepts exactly one READY
`EXISTING_FACT_CHECK` `ResearchAssignment`, compiles that assignment through the existing
`discovery_manifest_from_assignments()` DP-228 -> DP-209 adapter, persists the manifest and
query through canonical `run_discovery_manifest()`, then appends only DP-209-accepted
normalized mirror records through the private `ExistingFactCheckMirrorStore` seam.

The runtime cannot widen the planner contract: supplied adapters must be a subset equal to
the assignment's permitted adapter IDs; the persisted DP-209 query ID remains the exact
`research_assignment_id`; query text is the exact assignment question; query
`max_results`, manifest `max_results_per_host`, manifest cost cap and
`remaining_attempts` are inherited unchanged from the assignment. The injected lookup
receives only that persisted query text, the exact query result cap as `page_size`, the
manifest date window, remaining DP-209 cost budget and assignment ID. Returning more
records than the query cap fails the attempt before any hit/mirror persistence; an adapter
whose declared cost upper bound exceeds the assignment/manifest cap is blocked by DP-209
before the lookup callable runs.

The canonical DP-209 path still owns manifest-before-call durability, attempt state,
accepted/rejected hit dispositions, provider receipt sanitization, operation cost receipt
and run receipt. The DP-232 bridge stores private normalized record material only after the
matching accepted hit is durable and bound to the same provider/URL/external ID and
assignment. Replaying an already-completed run ID performs no second lookup and returns
the existing mirror by durable hit identity, preserving idempotency.

Rights remain fail closed: this runtime always persists new mirror observations with
`rights_status=UNKNOWN`; the lookup result has no rights-grant field and the runtime receipt
has `publication_authority=false`. It creates no Evidence, Finding, verification result,
publication decision or public serializer output. Later excerpt/public use still requires
the separate DP-305 path described above.

Focused disposable-PostgreSQL proof now covers **13/13 PASS** in
`test_existing_factcheck_persistence`, including the five new runtime cases: exact
DP-228/DP-209 bound inheritance + persisted mirror/receipt; completed-run replay without a
second lookup; pre-call cost-cap blocking; over-bound result failure with zero mirrors; and
lane/adapter permission non-expansion before lookup. Existing fact-check normalizer,
DP-228 claim planner, research-plan compiler, DP-209 discovery and DP-305 excerpt
regressions bring the focused set to **123/123 PASS**. `py_compile` and `git diff --check`
PASS. All lookups in this proof are injected deterministic in-process fixtures; no Google
or other provider/network call, public projection/web edit, production DB mutation,
publication authority, commit or push occurred.
