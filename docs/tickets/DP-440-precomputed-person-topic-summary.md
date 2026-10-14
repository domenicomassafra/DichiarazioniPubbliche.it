# DP-440 — Sintesi Persona × Tema precomputata e citata

Status: IN PROGRESS
Milestone: M4 — public product/API
Depends on: DP-224, DP-303, DP-431, DP-435, DP-439

## Problem

Una lista di dichiarazioni non è sempre un riassunto utilizzabile, ma una sintesi generata senza confini potrebbe affermare cosa una persona «pensa veramente», trasformare citazioni storiche in endorsement, confondere epoche e omettere la copertura incompleta. Il brief approvato chiede testo sintetico **precomputato** e **citatamente collegato a originali**; non chatbot pubblico.

## Outcome

Per ogni intersezione PublicPerson×PublicTopic approvata, una breve sintesi versione/corpus-bound con claim circoscritti e pointer per frase a specifiche PublicStatements originali, datate e pubblicabili, eventualmente raggruppati per periodo/contesto. Resta distinta dai verbatim e sparisce quando le fonti sono insufficienti o stale.

## Traceability & constraints

R03/R16/R18/R19/R20/R24/R25, Q15–Q20, DP-224/303/431; la summary non è quoting text, non implica intenti, and does not convert nonfactual statements into factual verdicts. «Nelle dichiarazioni raccolte» non significa «in ogni occasione».

## Scope

Input exclusively approved public intersection DP-439 and public original Statement IDs from DP-437/02 with context/stance from B. Persist versioned synthesis draft/review metadata: person_id, topic_id, synopsis_text, period/scope, source corpus snapshot fingerprint, generation rule/model or deterministic method and version, created_at, explicit coverage/freshness note, set of cited Statement/version IDs with exact source date/locator, confidence/unsupported coverage flags private. Cited propositions must be claim-bound to original sources with allowed public citation markers, no fabricated quotes or implicit endorsement. Precomputation as governed offline job after statement batch changes; request path returns artifact only, no provider call. Generate or abstain/omit using explicit measured evidence/quality gates; under sparse/heterogeneous material prefer source-linked list with no synthesis and clear limits. Cross-period changes require **reviewed** same-person longitudinal relation B, not a model inference from words.

## Non-goals

Chatbot, personal preference or political profile, score/sentiment, auto-publication bypass, broad inferred worldview, conjectures about motive, generic media summary lacking source statement refs.

## Dependencies and sequencing

Hard existing DP-224/303/431; add DP-437/02/05 real IDs and B approved speech-act/relation contract once named. D background refresh budget, pipeline replay and owner restrictions; DP-429 only renders synthesis and DP-439 owns filters. Avoid adding DP-440 as a dependency of DP-437/05 to prevent cycle.

## Acceptance criteria

- [ ] `AC-440.1`: every substantive public synthesis sentence has >=1 valid published Statement/version citation and provenance/date; source link opens exact original quote/locator, verified hash and speaker.
- [ ] `AC-440.2`: original quote and summary are visually/semantically separate and translation not passed off as original; synopsis states collected-corpus limitation, snapshot date/version and language/scope coverage.
- [ ] `AC-440.3`: two eras or contrary positions are described separately by dates and conditions; claim of same-person position change only if approved relation, different-person contrary views never become same-person change.
- [ ] `AC-440.4`: historical reported/critical/ironic quote or insufficient context cannot populate «sostiene X»; no person ideology/reliability/intent inference.
- [ ] `AC-440.5`: zero/sparse sources, mixed contexts, disputed identity, absence of positive evidence, stale source/rights or incomplete citations → synthesis withheld or qualified with specific unproven boundary; no hallucinated zero coverage as certainty.
- [ ] `AC-440.6`: correction, reply, withdraw, source version or Topic membership change invalidates synthesis atomically and schedules bounded regeneration; stale public API/search/HTML cannot serve old cited claims, replay deterministic for pinned inputs/method.
- [ ] `AC-440.7`: request path works with provider offline, no LLM call or hidden stochastic reranking; cost/latency/attempt receipts separate from query analytics.

## Validation / proof

Gold corpus of several approved exact quotes with timestamps, quotation-of-another-person, two periods, cross-person discrepancy, deleted source and none/sparse case; manually/auditably established source-to-sentence entailment sample (not generated self-judge). Check every citation reference and hash, required qualifications, no inaccurate endorsement and absence of stale cached synthesis after revoke. Future MiniPC isolated precomputed readback + renderer acceptance, no live model on public request; B/D define authority/cost gate.

## Documentation, data, and migration impact

New bounded immutable-ish materialized synthesis read model and version invalidation receipts; no separate vectorDB/chat frontend, reuse public static projection, DP-431 correction triggers and DP-224 citations. Data migrations additive and rollback to no-synthesis safe state.

## Completion receipt

Historical planning-only receipt; the limited offline contract below supersedes it, not the unfinished real acceptance.

## 2026-10-11 — Opt-in cited synopsis read model (partial)

New `public_synopsis_v3.py` with focused adversarial tests prepares a
precomputed **read model**, never a prompt or provider request. It only
accepts an externally approved Person×Topic membership and independent
source-lineage proof for already validated public-v3 exact original
Statements. Every independently reviewed sentence carries exact
Statement/version/quote SHA, source SHA, source date/locator and coverage
note; stale projection, changed quote, source repost mistaken for two
independent lineages, unapproved/quoted speech promoted to endorsement,
absent or sparse source, wrong Person or topic reference all WITHHOLD.
Original text remains a separate resource from synopsis and translation.
Synthetic tests PASS; no runtime LLM or live public route was activated.
**All AC-440.1–.7 remain unchecked** pending independent editorial semantic
entailment, real approved topic membership, atomic revoke/cache/served-build
proof, and MiniPC positive/negative canary before any public release.

## 2026-10-11 — Independent Content/locator citation regression

Local source-only review found that a purported two-source synopsis could
pass `min_independent_contents=2` with two separately labeled lineage IDs even
when the cited public Statements came from the exact same `content_id` or
source URL. That double-counted excerpts or versions of one source as separate
corroborating material, despite the externally reviewed lineage requirement.

`prepare_public_synopsis` now also counts distinct public Content identities
and source URLs alongside approved lineage IDs when enforcing the minimum.
Synthetic test `test_two_statements_on_same_content_or_locator_are_not_two_sources`
was **RED** before the change (both same-Content and same-URL subcases returned
`READY_READ_MODEL`) and **GREEN** after (both return
`SYNOPSIS_TOO_FEW_PUBLISHED_SOURCES`). Original wording and its citation
hash remain separate from synopsis text. No external approval is inferred.

DP-440 stays **IN PROGRESS**, AC-440.1–.7 unchecked. The check is an offline
contract guard only; real editorial entailment, current rights and membership,
atomic invalidation/served-cache proof, and MiniPC acceptance are still absent.

## 2026-10-11 — Rehosted-source, temporal-currentness and citation-alias guards

An independent adversarial review of the existing opt-in read model found
four further ways to return `READY_READ_MODEL` without adequate source
independence or as-of-date provenance:

- **Mirrored source bytes:** two public Statement rows with distinct Content
  IDs, HTTPS URLs and independently labelled lineages but an identical
  `source_sha256` were counted as two corroborating sources. A fourth
  independence dimension now requires distinct source-body hashes alongside
  the existing reviewed lineage, Content ID and URL checks.
- **Future evidence:** `now` previously only stamped the result and could
  predate the snapshot `generated_at` or a cited Statement's public
  `statement_date`. Snapshot generation now requires a timezone-aware,
  non-future timestamp; each cited date must precede or equal the UTC
  snapshot/assembly date. An invalid generation timestamp is withheld.
- **Unbounded currentness ID:** the independently approved Person×Topic
  intersection previously carried a string attestation ID without a time
  range. Its opt-in read contract now requires an externally reviewed
  `currentness_attested_at` and `currentness_valid_until`, both aware
  timestamps. Attestation must occur no earlier than the snapshot, no later
  than assembly time, and the read model is withheld at/after expiry.
  These values join the deterministic synopsis fingerprint; no local code
  grants or renews rights, topic membership or source approval.
- **Mutable locator alias:** the serialized synopsis kept a reference to
  the mutable public bundle's original locator dictionary. A later change
  to private/source-driven data could alter the already emitted citation
  without changing the synopsis fingerprint. Locators are now snapshotted
  into independent dictionaries when preparing each citation.

Regression `tests/test_dp440_public_synopsis.py` reproduced the
mirrored-source and future-snapshot bugs (**RED: two failing assertions**)
and locator alias mutation (**RED: one failing assertion**); the new
attestation-contract test initially failed because the time fields were
absent. After the narrow source changes, **14/14 DP-440 tests PASS**;
combined DP-440/435/436 frontend-adjacent Python verification **39/39
PASS**, targeted Python compilation and `git diff --check` pass.
All proofs use synthetic fixture data and no public runtime/provider.

This is only an offline consumer/read-model fail-closed advance. An
attestation's issuer, authority and rights still require an independent
governed upstream integration; a caller-provided date cannot certify
renewal. Editorial per-sentence semantic entailment, real public
Person×Topic approval, atomic revoke/rebuild/cache invalidation, a
rights-authorized source corpus and MiniPC readback remain missing.
**DP-440 remains IN PROGRESS; AC-440.1–.7 remain unchecked.**

## 2026-10-12 — Pinned browser/SSR synopsis reader (source-only opt-in)

Added `web/src/lib/publicSynopsisV3.ts` and an independent Node/Astro
regression script `web/scripts/check-public-synopsis-v3.mjs`; no public route,
component, provider invocation or release activation was added. The reader
accepts the **actual `prepare_public_synopsis()` JSON fixture** from
`tests/test_dp440_public_synopsis.py` and enforces an independently issued
pin for the entire synopsis DTO, its opaque reviewed fingerprint, the
complete current public-v3 Statement dataset, Person/Topic identity, the
public projection `generated_at`, and finite membership/current-rights
expiry. The projection timestamp has a separate pin because Python's dataset
digest deliberately covers collections but not `generated_at`.

Each synopsis sentence is kept distinct from the original Statement text;
the reader rechecks every cited public Statement ID/version, quote hash,
source-body hash and URL, exact locator, language, date (within the as-of
snapshot), Person binding and compatible endorsement/speech-act. It returns
only safe citation metadata, a **prospective** canonical Statement route,
snapshot and bounded coverage note. It refuses unpinned or self-rehashed
material, private fields, a changed or withdrawn Statement, altered source
date/locator/wording, missing rights review, future/stale timestamps,
expired pins, unsupported endorsement and WITHHELD Python receipts. A test
for mutable input objects confirms that previously returned locators are
copied, not aliased. No review credential or approval is derived from an
input flag, and the result explicitly has `publicationAuthorized=false`.

The regression first failed RED because the consumer module was absent;
after implementation, Python's real fixture through Node/TypeScript and an
isolated, temporary **Astro static SSR build** both pass. That temporary
route renders safe text, coverage and Statement citation links; rebuilding
with an expired pin fails. `tests.test_dp440_public_synopsis` has **14/14
PASS** and `npm run check` validates the TypeScript code. These are local
synthetic fixture receipts, not fresh authenticated real-source approvals.

**All original AC-440.1–.7 remain OPEN.** No independent production pin
issuer, actual editorial entailment approval, rights-authorized published
Statement corpus, live source-locator route, atomic cache/revoke proof,
provider-offline production request measurement or MiniPC acceptance exists
from this slice. An offline consumer can only detect corrections/withdrawals
when the separately authenticated release pins are refreshed or expire;
atomic invalidation must be proven at the future serving boundary.

## 2026-10-12 — Independent private cross-reader / isolated SSR preview

New **opt-in private-only** `web/src/lib/privateSynopsisCrossPreviewV3.ts`
composes the existing Python DP-440 synopsis, approved DP-438 Person archive,
DP-439 reviewed Person×Topic join/search index, and DP-437 public original
Statement. The caller supplies **independently authenticated CURRENT release
pins** binding the entire published Statement dataset, its separately pinned
generation timestamp, Person collection, Topic intersection, search index,
Person sitemap, synopsis DTO/fingerprint, exact Person/Topic IDs and finite
expiry. A versioned release ID/epoch is read independently **before and after**
assembly; observed drift or unavailable authority refuses the result.
Neither the Python `READY_READ_MODEL` flag nor the frontend computes a grant.

Every synopsis citation is compared against the exact current Person archive,
public source record and DP-439 Topic-index entry: Statement/version, Person,
original quote, SHA, date, language, Content and source URL/title/version,
source kind, locator and eligible endorsed OPINION speech act must all agree.
The displayed original wording is a **separate** bounded, dated quotation
with its prospective Statement route; each precomputed synopsis sentence stays
in its own field, with corpus coverage/snapshot visible and no truth score,
private reviewer receipt or automatic publication. This narrower integration
currently handles the DP-439 **opinion subset**; other statement acts remain
outside this reader rather than being relabeled.

`web/scripts/check-private-synopsis-cross-preview-v3.mjs` first reproduced
RED (consumer import absent), then passed GREEN. It builds a real synthetic
Python v3 Person/Topic/Statement fixture and calls
`prepare_public_synopsis()` with distinct synthetic source identities and
caller-supplied review attestations, validating its `READY_READ_MODEL` and
REVOKED/WITHHELD variants. Node consumes these exact JSON outputs through
the new consumer, followed by a temporary **Astro SSR build that executes
the consumer inside the server build** and renders original quotes separately
from synopsis text under `noindex,nofollow`. Negative tests reject a
re-pinned DP-439 membership withdrawal with otherwise unchanged synopsis,
source/quote/locator/rights/date changes, unapproved synopsis, missing opt-in,
wrong Person, stale release epoch, a second-read epoch race, expired issuer,
and attempts to introduce private review fields. Independently verified:
script PASS; `npm run check` **113 files, 0 errors/warnings**;
DP-439+DP-440 Python **22/22 PASS**; existing public synopsis SSR script
PASS. No public route or production artifact was created.

**Status remains IN PROGRESS, original AC-440.1–.7 unchecked.** These are
only synthesized authorized fixture states, not real legal source clearance,
genuine editorial entailment or rights approval. A future current-pin issuer,
atomic correction/reply/withdrawal cache and serving boundary, real original
locator navigation, provider-offline production proof and MiniPC runtime
canary remain required. The preview can reject an invalidated release once
the authority rotates its pins; it cannot discover unseen revocations by itself.

## 2026-10-12 — Private operator synopsis browser, source-only

The isolated `web/src/lib/privateSynopsisBrowserV3.ts` composes the existing
`privateSynopsisCrossPreviewV3.ts` without changing its independent release
pin, public-original quotation, Person or Topic contracts. It produces a
bounded, escaped HTML fragment for an **opt-in private operator** Astro SSR
surface, with an explicit `noindex,nofollow,noarchive` directive. Its numbered
synopses and separate source-original blockquotes expose native previous,
next, source-focus and return links using accessible fragment targets and
`tabindex=-1`; prospective original Statement links preserve source dates,
Person attribution and pinned quote/source hashes. No client provider or
online synopsis generation is introduced.

The browser consumer delegates to the cross-reader's **two independent CURRENT
release reads** and performs a **third issuer read after HTML assembly**. A
changed release epoch, source projection, Topic membership, expiry or
rights/quote/locator causes refusal; source/synopsis markup is escaped and
bounded before any HTML is returned. The caller must add private no-store and
robots response headers when a real authenticated operator route exists.

`web/scripts/check-private-synopsis-browser-v3.mjs` uses actual synthetic
Python `prepare_public_synopsis` data joined with DP-438/DP-439 Person/Topic
records; RED was the missing browser consumer import. The GREEN test covers
working hash-link target/keyboard-focus semantics, separate exact originals,
escaped adversarial HTML, current epoch at read 1 and read 3, revoked Topic,
modified original content and expired/withheld receipts. A temporary Astro
SSR build renders the private, noindexed HTML and rejects revoked/late-epoch
builds. Local proof: script PASS; `npm run check --prefix web` **115 files, 0
errors/warnings/hints**; targeted DP-439/DP-440 Python tests **22/22 PASS**;
`git diff --check` PASS. No route was added to the public app.

**Original AC-440.1–.7 remain unchecked; status IN PROGRESS.** Python and
frontend attestations here are synthetic; no independent production rights
issuer, qualified editorial entailment, real original source clearance,
authenticated operator endpoint, transactional cache invalidation, MiniPC
readback or public launch was proved. The browser view cannot detect a
withdrawal that its independent release authority has not yet recorded.

## 2026-10-13 — Synopsis source-snapshot timestamp is not reader assembly time

The private opt-in synopsis read model previously returned
`snapshot_at = now` even when the independently attested public-v3 projection
was generated earlier. Re-reading identical approved source/editorial inputs
an hour later produced a **different reported snapshot timestamp with the same
source-bound synopsis fingerprint**. A focused deterministic test was RED:
expected the exact source projection time `2026-10-11T12:00:00+00:00`, but
received the reader assembly time `2026-10-11T16:00:00+00:00`. This could
overstate corpus freshness and make an unchanged offline artifact appear to
have been snapshotted at a time when its source dataset had not changed.

The read DTO now emits the canonical UTC `generated_at` timestamp from the
**already validated and independently pinned public Statement projection**.
The function still evaluates the separate bounded attestation and time of
reading against the supplied current `now`, withholding stale and future
releases, and does not change corpus/source/content/speech-act eligibility.
Two distinct valid reader times over one immutable v3 projection now produce
byte-identical `snapshot_at`, synopsis metadata and fingerprint; no online
generation, source permission, publication or MiniPC route is activated.
Focused and adjacent source-only tests remain separately required.
**All AC-440.1–7 remain OPEN** pending real editorial entailment, rights,
current issuer/revocation and MiniPC readback.

## 2026-10-14 — Private source-linked synopsis regeneration planner

New source-only `public_synopsis_refresh_plan_v1.py` with deterministic
`tests/test_dp440_synopsis_refresh_plan_20261014.py`. The opt-in private
revalidation consumer compares two actual schema-validated v3 public
Statement projections against a previously prepared DP-440 synopsis and a
separately supplied current DP-439 Topic membership. It requires independently
obtained expected SHA-256 pins for **both** projections and the previous
synopsis and checks each old sentence's citation against the old actual
published Statement/version/quote hash/source locator/date/language. It
reports only changed or missing public Statement/version IDs and finite
remediation codes, never source bodies, sentence prose, editorial notes,
identity inference or any factual/rights/publication authority.

The implementation was genuinely **RED** on absent new module. Focused
regressions verify immutable no-change review-pending output; changed
original/source SHA/version/date, missing citations or removed Topic
membership requiring review; revoked/held/pending/expired membership withholding;
forged or mismatched pins/metadata raising fixed refusals and zero provider
calls. A further test reproduced **RED** for changes only to public projection
`generated_at` because the canonical dataset SHA intentionally omits that
timestamp. The worklist now tracks exact `generated_at` separately and
requires a fresh review even when every corpus row fingerprint is unchanged.
An additional **RED→GREEN** case proved one legitimately reviewed public
Statement may support multiple separately reviewed synopsis sentences; the
planner now deduplicates changed/missing *source reference IDs* rather than
rejecting that lawful repeated citation or counting it as independent
corroboration.
The no-difference state is explicitly `NO_CHANGE_REVIEW_PENDING`, **never**
READY/PUBLISH: independently authenticated issuer status, source rights,
human semantic entailment and citation review remain external. This is
revalidation planning, not a summary generator or a cache eviction program.
Original DP-440 **IN PROGRESS, AC-440.1–7 unchanged and OPEN**; no editorial,
legal, physical MiniPC, provider or production serving acceptance.

**Review-status receipt:** the existing independent reviewer could not
restart, and the separately requested replacement worker failed to start
before any new file inspection. There is **NO genuine independent PASS** for
this new planner at this time. Prime source-only adversarial replay and
deterministic tests count as implementation validation, not independent or
qualified human/editorial review. PR and production-release gates remain
held and every original DP-440 AC stays open.

**Definitive local tests:** new+adjacent DP-440 Python **25/25 PASS**, genuine
RED→GREEN cases recorded above. The two new source/test files are byte-
identical to those used for the single combined full Python unittest run in
the disposable uncommitted test overlay of main with the disjoint DP-320
eight-surface source/test: **3,469/3,469 PASS, exit 0, 298.492 seconds**;
deterministic benchmark **5/5 PASS**, Ruff check/format and Python compileall
PASS. No PR CI, production data, provider calls or independent reviewer PASS
are implied. All original real editorial/source/rights/MiniPC gates stay OPEN.

## 2026-10-14 — Post-ship source-only P2: mutable synopsis read DTO

Prime source-only adversarial inspection (NOT an independent reviewer) found
that the original synopsis issuer fingerprint alone did not bind emitted
nested `PublicSynopsisRead.sentences` bytes. A caller could mutate an
already prepared sentence after the reader computed its digest, retain the
original issuer fingerprint, and obtain a no-change revalidation result.
Genuine **RED** fixture preceded the additional required exact-read pin;
now `synopsis_read_sha256` fingerprints the complete read DTO against an
**independently supplied owner receipt**, and mutated text is refused with
`REFRESH_READ_PIN_MISMATCH`. Self-rehashing the untrusted DTO does not prove
issuer identity or approval. Planner output never includes the sentence
body, so this is a pre-publication accuracy/freshness guard, not a proven
historical leak or actual live route exploit. Final independent review still
**PENDING**: worker sessions were unavailable. Original DP-440 Status and
AC remain unchanged, no rights/editorial/provider/MiniPC acceptance claimed.

**New independent reviewer P2 on source bundle mutation:** worker-9
reproduced a distinct post-validation time-of-check/use defect. The old
`dict(previous_bundle)`/`dict(current_bundle)` conversion was shallow:
nested original wording could change on later caller-controlled access
while stored `dataset_sha256` values remained unchanged. A specially
constructed in-memory dict subclass triggered the issue, producing a
misleading `NO_CHANGE_REVIEW_PENDING` despite mutated source material.
New deterministic regression first **RED** because the planner accepted
that untrusted post-validation mutation. The planner now refuses dynamic
Mapping/dict subclasses, makes a bounded **detached JSON snapshot of both
complete public bundles before ANY validation or later citation read**, and
performs every SHA/currentness/comparison operation on those snapshots.
Source-only new/adjacent DP-440 tests now **27/27 PASS**. The final
independent re-review of this second P2 is requested separately; this does
not establish authenticated issuer identity, real rights or publication.

**Post-patch regression:** the original read-model mutation probe is now
RED→GREEN, and **26/26** new and adjacent DP-440 tests PASS. The exact
source and test bytes used in the detached aggregate overlay produced one
complete **3,476/3,476 Python PASS**, exit 0 in 330.917 s, and benchmark
**5/5 PASS**. Ruff and format PASS. This is source-only author review;
independent reviewer proof remains outstanding, so no PR or public route.

**Independent final source-only re-review:** worker-9 replayed the prior malicious dynamic `SwappingCurrent(dict)` after the new full `_frozen_public_bundle` snapshot and observed `REFRESH_PUBLIC_BUNDLE_INVALID` before any callback could mutate citation rows. A plain-dict source tamper before validation without a matching SHA was also refused; a mutation after full detach had no effect on the pinned snapshot. Reviewed new+adjacent DP-440 **27/27 PASS**. No additional reproduced P1/P2 within this bounded private planning contract; reviewer wrote no source/Git/provider data. This PASS is not an authenticated issuer, rights, editorial, semantic, PR-CI or physical MiniPC acceptance.

**Final codefreeze test receipt:** one completed combined Python unittest discovery on detached main plus byte-identical new DP-320/DP-440/DP-439/DP-314 source and tests returned **3,503/3,503 PASS, exit 0 in 306.597 s**, benchmark **5/5 PASS**, Ruff check/format PASS. Post-source-detachment DP-440 new+adjacent **27/27 PASS** and independent reviewer confirmed malicious post-shallow-copy mutation now refused. A previous prefinal full test was interrupted **exit 143** after source changes and never counted as PASS. This records local source checks only, no reviewer rights, editorial conclusion, PR CI, provider or production acceptance.

## 2026-10-14 — Private cross-release multi-synopsis refresh cohort

New *offline, private* `private_synopsis_refresh_cohort_v1.py` adds a
bounded cohort reconciliation layer over the existing
`public_synopsis_refresh_plan_v1.py`, using actual
`PublicSynopsisRead` and `ApprovedTopicIntersection` types and two
validated public-v3 Statement releases. Every prior/current release has an
owner-managed full-material SHA pin; each individual read model and Topic
membership also requires its own separately retained SHA pin. Each read
envelope binds a strictly increasing, source-specific issuer epoch. An
old-epoch read cannot be relabeled as a new issuer result; same-epoch
release replay is refused. Pins must originate from an independently
trusted issuer store; locally computed hashes alone confer no authority.

Before validating or comparing any release, the planner detaches every
complete public bundle, read model, citation array and membership map into
plain bounded structures, and rejects dynamic subclasses, unexpected
typed fields, duplicate/replayed issuer periods and mismatched read/policy
pins. It checks the canonical v3 public source contract and existing
per-synopsis citation/material/currentness planner, including a separate
**current-read versus current-membership** pass so that a newly asserted
`READY_READ_MODEL` cannot silently retain citations no longer in the
approved-shaped Topic membership. Source rights/review declarations,
source version and quotation hashes are retained only inside the input
snapshot and its digest; changed dependencies schedule human recheck.

The deterministic, sorted private review items distinguish `ADDED`,
`RETIRED`, `CHANGED` and `HELD`, with explicit external source-rights,
editorial entailment and publication gates. Opaque item references are
HMAC-SHA256 over the Person×Topic key with an independent owner-provided
private key. **No** Person/Topic/Statement IDs, original text, source URL,
synopsis prose or private review tokens are emitted in output. No
automatic source approval, fact verification, regeneration, published
Finding, public route, provider calls, DB writes or publication permission.

**Source-only RED→GREEN:** the new tests initially failed on absent
`private_synopsis_refresh_cohort_v1` (`ModuleNotFoundError`); the first
implementation then exposed and corrected a retired-versus-held
classification gap. A later adversarial test identified **RED** where a
fresh review-event receipt replacing only the Topic membership attestation,
with byte-identical read-model text, silently returned no work. The
corrected comparison detects changed full Topic-review receipts and
schedules `CHANGED` with `TOPIC_REVIEW_RECEIPT_CHANGED` even without a
Statement/text drift. New tests **11/11 PASS** and combined
DP-440 new + canonical synopsis + earlier refresh planner **38/38 PASS**.
The real synthetic public-v3 fixture contains multiple independently
source-backed Statements for two public Person IDs and multiple topics.
Tests cover cross-release replay, immutable snapshot/dynamic subclass
denial, stale read/release/membership pins, time/currentness,
simultaneous changed/retired/held items, added synopsis without approval,
rights/review/source changes, Topic citation exclusion and no identifiers
or URLs in result objects. Ruff check/format, Python compile PASS. Full
repository integration and independent post-source review remain separate.
**DP-440 remains IN PROGRESS; AC-440.1–7 remain unchecked.** Real issuer
authentication, qualified source-rights/editorial approval, MiniPC
revalidation, revocation latency, and public HTML/API/cache readback
remain unproven.

## 2026-10-14 — Independent reviewer P2: malformed Topic authority and omitted cohort

Independent worker-11 identified two substantive fail-open gaps in the
**published** private cohort planner at exact commit
`375271a4550278f08b5dcdde6a95fe89f618a7b2`:

1. The new cohort release validator checked the Topic membership identity
   and dataset digest but did **not** validate full original-Statement
   lineage coverage or the reviewer/currentness authority fields. A genuine
   `ApprovedTopicIntersection` altered to have empty or duplicate
   `statement_lineages`, an empty `review_event_id`, or an empty
   `currentness_attestation_id`, then fully re-pinned, could be reported
   as an ordinary `CHANGED` item. The same malformed proof in **both**
   releases could silently yield `IDLE_NO_AUTHORITY` (zero review items).
   The canonical `prepare_public_synopsis` would WITHHOLD for missing
   lineage review or membership authority.
2. The cohort enumerated only prior and current synopsis read keys.
   A newly reviewed current Person×Topic membership without a synopsis
   read in **either** inventory was silently skipped, falsely returning
   `IDLE_NO_AUTHORITY`.

**Genuine local RED, before source patch:** two new focused tests exercised
actual two-Person public-v3 Statement bundles and real
`PublicSynopsisRead` fixtures. All release/read/membership SHA digests
were self-consistently regenerated to rule out incidental stale-pin
rejection. Four malformed current proofs were accepted instead of raising
`COHORT_MEMBERSHIP_INVALID`; a current-only membership with no read
returned `IDLE_NO_AUTHORITY` rather than a human review item
(five failing subcases across two tests).

**GREEN source fix:** membership validation now requires exact typed,
bounded, nonblank reviewer and currentness IDs, unique Statement/version
keys, full one-to-one original-source lineage coverage, no duplicate
lineage refs and a bounded known status. Invalid historical or current
proofs now refuse with a **generic** `COHORT_MEMBERSHIP_INVALID` (including
the malformed proof replayed in both releases), without publishing source
identities or leaking the invalid review fields. Cohort enumeration now
uses the union of all previous/current **read and membership** keys;
a current membership lacking a current read emits a deterministic,
HMAC-opaque `HELD` item with
`CURRENT_MEMBERSHIP_READ_MISSING` and
`NEW_SYNOPSIS_REVIEW_REQUIRED`. A genuinely retired read *and*
membership remains distinguishable from the missing-current-read hold.
No autoapproval, source capture, provider calls or public side effects.

Post-patch **new cohort tests 13/13**, DP-440 new+adjacent tests
**40/40 PASS**; Ruff lint/format and scoped Git diff checks PASS.
This records only an author-side local synthetic RED→GREEN remediation:
worker-11 independent **post-fix** review remains required, as do any
broader-suite integration or real issuer/rights/editorial/physical
revocation approvals. **Status remains IN PROGRESS; AC-440.1–7 remain
unchecked.**
