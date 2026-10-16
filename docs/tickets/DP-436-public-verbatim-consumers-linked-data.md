# DP-436 — Verbatim search, cards, relations and linked-data consumers

Status: IN PROGRESS
Milestone: M4 — public product/API
Depends on: DP-435, DP-402, DP-403, DP-433

## Problem

The current public consumers present normalized paraphrases as quotations in several cards, titles, Trace/Content views and search. A correct Statement detail does not make the whole product faithful to Q15–Q20.

## Outcome

Every authorized public representation of a Statement uses the same literal approved source words, separately labeled summary/translation, source context and version; withdrawing that record removes it from current public views.

## Traceability & constraints

R02, R03, R04, R15, R24, R36; Q15–Q20. Keep DP-305 no-private-body and rights gates, static no-LLM readers, historical v2 receipts. Implementation not authorized in this planning phase.

## Scope

Migrate Home, Explore, Person, Topic, Content, Trace, search index, metadata, HTML, JSON-LD, RDF, sitemap and API to the DP-435 first-class Statement contract. Distinguish original quote, identified Italian translation, normalized internal proposition and separate summary in every consumer. Preserve canonical/legacy URLs, version fingerprints and correction/retraction propagation. The projection explicitly bounds the approved excerpt and never publishes full captures/raw transcripts/private notes.

## Non-goals

No live public chatbot, new full-text copyright grant, fake source samples, or replacement of DP-435's provenance and rights decision.

## Dependencies and sequencing

Hard: DP-435, DP-402/403, DP-433. Coordinate DP-405..409, DP-422, DP-429, DP-431. Expand public schema then migrate all consumers before removing legacy wording behavior; reject mixed incompatible versions rather than silently defaulting to paraphrase.

## Acceptance criteria

- [ ] `AC-436.1`: Given one authorized original Statement, every surfaced quote is byte/meaning-faithful to its approved span and refers to the same source version/hash; translation and summary never appear as words the Person literally said.
- [ ] `AC-436.2`: Cards, page headings, API, search, JSON-LD, RDF and sitemap agree on public IDs, language, quote meaning, locator and dataset fingerprint; no operational body leaks.
- [ ] `AC-436.3`: Correction, rights expiry/revocation or stale capture removes/updates the affected current record in static HTML, API, index, linked data and cache without revealing held/private membership.
- [ ] `AC-436.4`: Identical safe replay generates byte-stable public data; incompatible legacy clients fail closed; real approved MiniPC URL/API readback proves version parity and no per-request LLM.

## Validation / proof

Future acceptance: cross-format snapshot/diff, spoofed paraphrase/translation negative tests, raw-body scanner, source rights revocation under cache race, original-versus-output hash checks and live authorized MiniPC consumer readback. Fixture and historical CI are not source approval.

## Documentation, data, and migration impact

Update schema/API consumer contracts and source map after implementation; incremental expand/migrate/contract of search and linked data with compatibility version and rollback, keeping previous signed receipts intact.

## Completion receipt

2026-10-10: planning only, **not implemented**; all new AC unchecked.

## 2026-10-11 — First implementation slice

Opt-in v3 Statement serializations in `public_api.py` and `linked_data.py` (commit `4a7afbf`) plus isolated web `statementV3.ts`/`VerbatimStatementRecord.astro` (commits `caa5c5c`, `ce60baf`). Original quote, locator/source, summary/translation and optional Finding have distinct types. 13 backend consumer tests and synthetic web statement test pass; existing v2 endpoints/routes unchanged. No real v3 HTTP route, public-host cache/revocation, source rights or MiniPC proof.

## 2026-10-11 — Cross-format source-only parity gate

Source/test commit `352cb78` adds opt-in
`public_v3_consumer_parity.py` which **independently compares** one already-
governed v3 projection to the existing API, JSON-LD and N-Triples serializers.
It requires exact dataset fingerprint, schema opt-in, Statement/Person/Content
and version IDs, source hash/version, quotation hash/original-language span,
speech-act and derived summary/translation separation. Reordered/extra RDF,
forged paraphrase-as-quote, changed API source/locator and stale pre-revocation
consumer outputs are rejected. The receipt exposes bounded metadata only and
grants **no** permission to publish. Nine focused adversarial tests and **32**
selected DP-435/436 regressions PASS, Ruff check+format PASS. Only serializer
parity is locally proven: it does not activate a v3 public route, homepage,
search, cards, sitemap or caches, certify real rights, or validate MiniPC
reader+withdrawal. AC-436.1–.4 remain OPEN and ticket IN PROGRESS.

## 2026-10-11 — Opt-in frontend detail API → exact-wording Astro consumer

The follow-up cross-review caught a previously accepted API record whose
source URL and SHA-256 changed without changing the claimed dataset digest.
The frontend now requires an independently pinned canonical API-record digest
as well as the separately pinned dataset digest. This new negative test was
RED before the change and GREEN after; real isolated Astro rendering and
type checking pass. A caller must derive both pins from trusted material,
not from the response under inspection. Neither digest alone is a signature
or permission to publish. All four original AC remain open.

Source-only frontend slice adds `web/src/lib/statementV3Api.ts` to consume the
existing backend's **separately opted-in** `get_public_statement_v3`
`{meta,data}` detail. The validator requires `allowStatementV3: true`, an
**externally supplied** 64-hex dataset fingerprint matching the payload and
the exact v3 schema; it checks a strict field allowlist, exact original
`VERBATIM_ORIGINAL` text SHA-256, public HTTPS source URL/version/hash,
written or timed locator length/shape, speech-act/endorsement constraints,
and summary/translation type, language and source-quote linkage. Any v2,
unknown, mixed or operational field fails closed. It does not manufacture
the backend's intentionally private review IDs or interpret paraphrase as
source text.

`VerbatimStatementRecord.astro` now accepts this payload as a separate
`apiDetail` prop, requiring an explicit opt-in and independently pinned
`expectedDatasetSha256` and a separate `expectedRecordSha256` pinned from an
independently verified approved bundle. Its existing governed source-record input remains
supported but simultaneous or missing inputs are rejected. A new isolated
`web/scripts/check-statement-v3-api.mjs` pulls synthetic-only data directly
through the existing Python v3 API serializer, then proves the exact quote,
source locator, distinct translated/summary panels, and absent Finding in
the **real Astro-rendered HTML** built in a disposable directory. It also
rejects no opt-in, stale fingerprint, v2/mixed shape, spoofed paraphrase,
source URL/locator/hash tampering, illicit endorsements, private fields,
and summary/translation source swaps. It tests rejected render builds
without adding any public site route or copying a synthetic fixture into
the deployment tree.

Focused backend-to-Astro, original Statement, v3 API adversarial validation
and Astro type check pass locally. The production public-v2 projection,
`/dichiarazioni/` route, API, search-index, static data/RDF publisher and
the independently disabled v3 writer remain unchanged. This proves only
a functional, opt-in frontend consumer seam; **AC-436.1–.4 stay unchecked**
until genuine source-specific rights/provenance, complete approved v3
consumer/index/search/linked-data cutover, revocation/cache race and MiniPC
same-fingerprint readback pass.

## 2026-10-13 — Direct Astro v3 source input requires explicit opt-in and exact external pin

An independent RED regression caught a source-admission bypass in the
unrouted `VerbatimStatementRecord.astro`: unlike its `apiDetail` path, a
direct `statement` prop previously rendered otherwise structurally valid
words even with `allowStatementV3=false` and no independently selected
record fingerprint. Synthetic isolated Astro rendering exited successfully
before the fix. A copied review-provenance identifier and self-reported quote
SHA-256 do not prove publication authority.

The direct mode now requires explicit `allowStatementV3=true`, well-formed
externally selected dataset/record pins, and an actual SHA-256 of a stable,
validated source-record snapshot matching the supplied record pin. It displays
the pinned dataset identifier and refuses mismatched pins without falling back
to v2 text. The existing API-detail admission remains unchanged.
Independent source-to-dataset membership/rights approval is **not** inferred
merely from a syntactically valid caller-provided dataset pin.

The original regression was RED (`direct source record bypassed explicit v3
opt-in`), then GREEN: no-opt-in and wrong-pin render builds fail, the pinned
synthetic direct original/translation/summary builds, and original API-detail
negative cases still fail. `node web/scripts/check-statement-v3-api.mjs`,
`npm run check`, `npm run check:search`, `node
web/scripts/check-statement-v3.mjs` and `git diff --check` PASS. No public v3
route, approved rights/attribution, live MiniPC reader, record release, new
Capture, provider or publication was activated. **AC-436.1–.4 remain OPEN.**

## 2026-10-13 — Immutable source snapshots for API and linked-data serializers

An independently reproduced post-validation mutation exposed a privacy and
integrity defect in the preparatory public-v3 consumers. The caller-owned
source dictionary was validated, but serializers subsequently read its same
mutable nested Statement objects. The reproducible RED modified the input
after the real schema validator returned: `list_public_statements_v3` and
`get_public_statement_v3` emitted synthetic private, unapproved transcript
text and changed source/identity metadata under stale quotation and dataset
hashes. The separately opted-in `projection_statement_v3_jsonld` and
`projection_statement_v3_ntriples` showed the same exposure.

Both consumers now detach a deep-copy of the complete input **before**
validation and use only that validated snapshot to serialize. New adversarial
regressions preserve original quote, source, identity, locator and fingerprint
even if caller-owned objects change after validation. Source-only local
green tests and broader proof are recorded in the implementation receipt;
none authorizes new public-v3 routes, real rights, provider calls, database
changes or deployment. The defect correction **does not close AC-436.1–.4**:
independent rights/source attestation, full public-v3 consumer cutover,
cache/revocation races and MiniPC same-fingerprint readback remain OPEN.

## 2026-10-13 — API-detail consumer asynchronous alias race

Independent review of the previous fixes found the same input-alias error
in `web/src/lib/statementV3Api.ts`: the TypeScript reader hashed and
validated a public-v3 API detail, but returned the caller's original mutable
object. A deterministic RED mutated nested `original.text`, source URL and
reviewed summary *after* the second SHA-256 digest had completed and before
its awaiting Promise resumed; the validated result nevertheless contained
unapproved synthetic wording under the earlier quote/record hashes. The
Astro `apiDetail` mode subsequently consumed that mutable result.

The reader now takes a detached `structuredClone` **before** asynchronous
validation and returns only that checked snapshot. New regression checks
both post-validation caller mutation and the interleaving during the final
digest; both must preserve the originally approved fields and dataset
metadata. The direct `statement` mode separately requires an explicit
opt-in and external record pin, as documented above. This source-only
release-gating privacy/integrity fix does **not** activate the currently
unrouted v3 public page or establish real publication rights, approved
source membership, host cache invalidation or MiniPC readback; all original
DP-436 acceptance criteria remain OPEN.

### Full verification and delivery guard — 2026-10-13

The combined source-only tranche was independently reviewed (PASS with no
remaining reproducible P1/P2 in the scoped diff) after the API, JSON-LD,
N-Triples, direct Astro source and asynchronous API-detail alias corrections.
API/linked-data adversarial checks **25/25 PASS**; independent worker's
backend/API/linked-data adjacent checks **129/129 PASS**; synthetic backend
to actual Astro rendering with no-opt-in, incorrect record pin, after-return
mutation and digest-interleaving negatives PASS. `npm run check` reports
zero errors and zero warnings (one pre-existing unused-require hint in the
unrelated DP-429 suggestion test). `compileall`, scoped Ruff, deterministic
domain benchmark **5/5 PASS**, and `git diff --check` PASS.

Final integrated Python suite **3,442/3,442 PASS** in **431.620 seconds**
(`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m unittest discover
-s tests -q`, exit 0). These are source-only synthetic/private safety tests,
not qualified fact-checking, approved source rights or MiniPC deployment.
The coherent eight-file correction is preserved on remote branch
`fix/dp436-direct-component-pin-20261013`; do not create a new GitHub PR
until linked Codex automatic-review personal/repository settings are actually
verified OFF or owner expressly approves possible review cost
(`PR_HELD_AUTOREVIEW_BILLING_GUARD`). Original AC-436.1–.4 remain OPEN.
