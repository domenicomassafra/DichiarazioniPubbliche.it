# DP-439 — Filtri pubblici Persona × Tema e dati incrociati

Status: IN PROGRESS
Milestone: M4 — public product/API
Depends on: DP-105, DP-402, DP-430, DP-437, DP-438

## Problem

La UI attuale ricerca per tipo oggetto e faccette, ma non risponde direttamente a «quali dichiarazioni pubbliche ha espresso Persona X sul Tema Y?». Gli attuali topic memberships sono basati su finding_ids e una menzione nel testo non basta a rappresentare una posizione su un tema; serve la proiezione Statement/topic autonomi e il filtro con intersection sicuro.

## Outcome

Filtri pubblici separati e componibili Persona + Tema con URI condivisibile, dati di dichiarazioni originali datate e scope visibile, riuso dello static index/public projection; niente chatbot, interpretazione LLM al click, topic inferito, roster privato o person-level aggregate.

## Traceability & constraints

R16/R18/R19/R20/R36, Q15–Q20, DP-405/406/409/429/430. Nome e label di Topic appartengono a public Topic identity reviewed; speaker approval e speech act/stance semantici appartengono ad A/B. Persona×Tema è intersezione di due filtri, non una nuova homepage orientata a profili politici.

## Scope

Build-time materialization dell'indice di join pubblico: statement_id/version, public_person_id, public_topic_id, membership_decision_id, approved speech_act/stance_for_topic se espressamente disponibile, statement_date/source/locator, original quote ref, optional Finding ref. Una Statement può avere multipli Topic solo con membership approvate; caso di citazione critica può essere rilevante come discorso sul tema senza essere classificato come supporto: mostra context/role esatto, non dedurre adesione. API/static index possono includere indici invertiti limitati (person→IDs, topic→IDs) dalla **stessa** approved projection fingerprint; matching riproducibile, query URL ?persona=ID&tema=ID più sort/filter date/sources; no Personal-topic private existence hints. Explore ospita filters, e Person/Topic offrono deep links coerenti senza creare un nuovo motore server. Dataset freshness/coverage in intestazione.

## Non-goals

Stance detector client, personalized recommendation, search semantica nuova, vector store, chatbot, person scoring, automatic approval di Topic, calcolo di truth dalle opinioni. Sintesi in testo è DP-440.

## Dependencies and sequencing

Hard DP-105/402/430 e i nuovi DP-437/04/03 dopo real ID; B provides meaning preserving position/speech-act, A provides canonical sources. Attenzione al ciclo: DP-409 attualmente dipende DP-405..408 che probabilmente riceveranno DP-439 come nuova dipendenza; per evitare ciclo, qui DP-409 è un consumer in soft coordination, NON un hard parent. Preferire un contratto join indipendente, applicato a valle dai consumer DP-405/406/409/429. Soft DP-410.

## Acceptance criteria

- [ ] `AC-439.1`: public Person P e Topic T approved con due Statements eligible → solo intersection (P,T) ordinata per data+stable ID, ciascun risultato originale, fonte, context e canonical URI; altri Person e Topic esclusi senza record leakage.
- [ ] `AC-439.2`: statement opinion-only senza Finding compare; Finding non pubblicato non è requisito; cita/critica di altra persona non diventa automaticamente adesione di P.
- [ ] `AC-439.3`: label simili e omonimi non si fondono; chiavi public IDs, non name/token matching; membership multiple only if authorized.
- [ ] `AC-439.4`: filtro vuoto, no-match su un corpus populated, corpus totalmente senza Statement, index unavailable/stale e privately-held zero intersection hanno messaggi corretti e non rivelano private memberships/counts.
- [ ] `AC-439.5`: URL, back/forward/reload, keyboard/VoiceOver mobile, focus e annunci result-count funzionano su 320/375/390/430 e 200% zoom, zero provider/network requests beyond public static artifacts.
- [ ] `AC-439.6`: source/statement/topic/review revocation elimina membro dal join, API/static index/URL results convergono sulla nuova fingerprint, refresh/replay stable; un URL pre-revoca non rivela il vecchio private text.
- [ ] `AC-439.7`: filtro/relevance/sort è record-level deterministico, senza score Person/partito o ranking politico, e mostra last snapshot/coverage ambito.

## Validation / proof

Dataset fisico test con due omonimi, due Topic simili, statement opinion-only, un speaker quoting another, correction/revocation, no-match e zero-corpus. Assert exact intersection IDs, chronological tie-break, primary original/source fields, cache fingerprints, positive/negative rendered Page API/search. Future MiniPC approved public test with one actual Person×Topic intersection and evidence readback; size/latency budget DP-409 measured rather than adding infra.

## Documentation, data, and migration impact

Version index materialization with join and membership provenance, URL filters/ARIA, static/API field specification, invalidation DP-431, compatibility of old search index. Do not add private Person roster or authorizations in public JSON. Prime resolves header DAG cycle note explicitly.

## Completion receipt

Non implementato; pianificazione soltanto. Future SHA, intersection IDs + source anchors, responsive AT receipt, corrections replay and MiniPC proof.

### 2026-10-11 — v2 public-index intersection slice (partial, local)

Code landed in `df6fa42` and `5c72563`. `web/src/lib/searchIndex.ts` now carries approved public-v2 Finding→Person and reviewed Topic-finding membership as bounded facet IDs; source rows absent from the verified public projection are not synthesized into results. The Explore dialog filters Person and Topic together with URL restoration, and `check-search-index.mjs` covers positive intersection, unrelated public Person, private/absent membership, malformed URLs and an invented public Topic facet even with recomputed index hash. `npm run check:search`, `npm run check` (0 diagnostics), design check and isolated projection-boundary check passed locally. Search remains browser-only with no per-request LLM.

**Scope limit:** v2 Finding membership is not the new first-class exact-wording PublicStatement membership: DP-435–438 and the additional typed public projection/reader upgrade still precede full AC-439.1/.2/.6. No approved real Person×Topic MiniPC runtime sample, original quote, precomputed synopsis, mobile screen-reader or revoked-v3 release readback is claimed. **All AC-439.1–.7 remain unchecked; ticket IN PROGRESS, contract migration and runtime proof pending.**

## 2026-10-11 — First implementation slice

The public-v2 static search-index now supports exact public Person×Topic Finding intersections without private candidates or inferred endorsement; React Explore exposes shareable URL filters, old normalized text is expressly not a quote (commits `df6fa42`, `5c72563`, `f8b2b6e`). Web search, design, Astro and isolated projection-boundary checks pass. First-class opinion-only v3 Statement membership, synopsis, source citation, real mobile AT and MiniPC approval remain outstanding, so none of AC-439.1–.7 is closed.

### 2026-10-11 — search-result route/identity gate hardening (local, partial)

The browser fetches a SHA-256 self-hashed public search-index and renders
`record.route` directly as an HTML link. Its validator previously accepted every
route beginning with `/`: an adversarial asset with an unchanged claimed approved
projection fingerprint and recomputed index hash could substitute
`//outside.example/collect` (a cross-origin link), a backslash variant, or
another public Person/Finding route, and pass validation. The digest proves
internal integrity against accidental mutation; it is **not** a signed proof that
the asset was derived from the authorized projection.

`web/src/lib/searchIndex.ts` now requires a kind-specific, strictly relative
canonical path and binds Finding and Person paths to their exact stable public
record IDs. Independently reviewed Topic and Content slugs retain their v2
canonical route grammar. `web/scripts/check-search-index.mjs` now rehashes
malicious index fixtures and checks cross-origin/backslash/encoded-path,
path traversal, query-string and wrong-resource-type redirects, plus a Person
ID substitution. The first adversarial route test was observed **RED** on
the original validator (accepted `//outside.example/collect`); after the fix
`npm run check:search` **PASS (7 indexed records)**, including the earlier
approved Person×Topic intersection and withheld Finding checks.
The independent high-risk search serializer check **PASS (2 records)**; the
existing demo and DP-407 fixture bundles also generate indexes accepted by
the tightened validator (**12 and 23 records** respectively). `node --check`
and `git diff --check` **PASS**. The Astro check could not run in this tranche:
the working copy has no `web/node_modules` (`astro: command not found`), so
there is no claim of a complete frontend build or live release regression.

This is a local defense of client-side route consumers, not a complete signed
index authorization mechanism or a new approved Person×Topic Statement join.
The current frontend remains public-v2 and does not expose the DP-437/438
opinion-only/approved-zero v3 membership. Source rights and publication
approval, real revocation readback, responsive VoiceOver/manual acceptance,
MiniPC release convergence and full original quotation/locator acceptance
remain external to this slice. **All AC-439.1–.7 stay unchecked; IN PROGRESS.**

## 2026-10-11 — First-class v3 Person × Topic original-opinion join (source-only)

New opt-in pure offline module `public_person_topic_v3.py` with adversarial
`tests/test_dp439_person_topic_v3.py` establishes a **functional**
first-class Statement join without inventing a Topic classification from
quotation text, source title, a matching Person name, or old v2
Finding memberships. It consumes three deliberately independent inputs:

1. A schema-validated published v3 original-Statement bundle, with an
   **independently supplied current public release SHA-256**;
2. The separately reviewed v3 `PublicPerson` read collection, with its
   own independently supplied current release SHA-256, exact stable
   Person ID and a matching *published* Statement/version/source/locator
   membership;
3. A private upstream manifest of per-(Statement ID, version, Topic ID)
   `ReviewedTopicMembership` decisions, with its own independently
   supplied **current manifest SHA-256**, immutable membership ID and
   revision, status, independent review event, exact public
   source/quote/Content/Person/dataset hashes, reviewed Topic identity
   version, plus time-bounded approval and currentness.

The Topic identity must be present in the public first-class `topics`
collection already validated in the **same pinned Statement bundle**.
Its existing v2 Finding-based memberships do not grant v3 Statement
membership. The upstream review issuer, release manifest publication,
signature/authenticity, and independent topic semantic determination
**do not exist within this module**: locally computed hashes never
assert or renew rights. They are compared against expected digests
which a real authenticated operator must obtain out-of-band. A
misleading or self-minted approval is not a real publication receipt.

The materializer emits a deterministic precomputed DTO of **endorsed
OPINION** Statement intersections with stable Person/Topic/Statement
routes, chronological date, exact original wording, language, quote
SHA, source SHA/version, literal source locator, nullable `finding_id`,
plus a disclosed limited-corpus coverage note. It never includes
private review events, nonpublic membership counts, or person-level
scores/verdicts. An independently approved membership can attach
multiple Topics to one Statement, but reported/critical/ironic speech,
unendorsed opinions, unknown Person identities, withheld original
Statements and held/revoked/expired topic decisions produce **no**
endorsed intersection. A later revision with `HELD`/`REVOKED` wins;
duplicated/conflicting revisions and reused approval events fail
closed, including reuse of a Statement source gate or Topic identity
review for the distinct Topic-membership decision.

`filter_public_person_topic_v3` implements exact, composable
Person+Topic ID intersection over the immutable pinned read model,
without a per-request provider/semantic query. The materialization
fingerprint binds its source/Person release hashes, public rows,
coverage and observable status/count; query requires an independent
expected read-model hash. It distinguishes `READY`,
`EMPTY_PUBLIC_CORPUS`, `EMPTY_PUBLIC_INTERSECTION`, and `NO_MATCH`
without revealing whether a private record or membership exists.
Revocation or Topic/identity withdrawal on an approved rebuilt public
snapshot omits affected entries; an old source/current-fingerprint
mismatch refuses reuse instead of serving stale text.

Synthetic TDD: initial module absence was **RED**; 8 new integrated
tests **GREEN** cover two homonymous approved people with distinct
stable IDs, similar Topic labels/IDs, one-to-many reviewed membership,
two dated opinion-only Statements for the same intersection,
no Finding or false verdict, exact original source and route,
reordered replay stability, reviewed revision and source rights
withdrawal, missing Topic or Person, changed quote/source/version,
forged self-rehashed public bundle, expired/old/duplicate review,
private/unendorsed speech, and observable empty-state/hash tampering.
Adjacent DP-435/436/437/438/440 backend suites: **73/73 PASS**;
deterministic benchmark: **5/5 PASS**; Ruff, targeted compileall
and `git diff --check`: **PASS**. No provider, HTTP route, writer,
frontend, MiniPC, production, commit or push was invoked.

**DP-439 stays IN PROGRESS; original AC-439.1–.7 all remain
unchecked.** The above is partial local source-level evidence
for AC-439.1/.2/.3/.4/.6/.7, not production acceptance.
Real independently authorized Topic classifications and release
currentness issuer, public Person/Topic versioned storage, cross-format
HTML/API/search/index/URL parity, atomic revoke-cache invalidation,
mobile VoiceOver/keyboard/zoom, realistic coverage measurements and
MiniPC positive/negative readback are still required. AC-439.5 has
no completion evidence in this source-only tranche.

Broader full-repository `python3 -m unittest discover -s tests -q`
was also attempted but **not completed**: after over two minutes it
remained in an unrelated PostgreSQL rights-complaint persistence test
(`tests/test_reply_governance_postgres.py`) awaiting a subprocess;
the specific test process was interrupted to avoid contention with
parallel workers. Its incidental resource warnings and interruption
are not reported as DP-439 test failures or as a full-suite PASS.
The focused and adjacent suite results above are the actual verified
success criteria for this isolated tranche.

## 2026-10-12 — Private pinned Person × Topic reader and isolated Astro SSR (partial)

Added opt-in **consumer-only** `web/src/lib/privatePersonTopicV3.ts` and
`web/scripts/check-private-person-topic-v3.mjs`. The Node test executes the
**actual Python** `tests/test_dp439_person_topic_v3.py` source fixture and
`make()` production join code to obtain distinct public Person identities,
homonymous Topic labels, a Statement with two reviewed memberships, an
opinion-only Statement without a Finding, and corrected/rights-withdrawn
releases. The fixture's synthetic review IDs and locally issued test pins
are not evidence of a real editorial authorization.

The TypeScript reader uses the existing authoritative
`validatePublicStatementSearchV3` / `searchPublicStatementsV3` index gates,
`readApprovedPersonV3` collection validator, plus the current independently
pinned public-v3 source collection and each versioned public Topic identity
(whose hash is checked separately). The caller must supply independently
authenticated current Statement/Person/Topic/index/intersection pins,
source `generated_at` and a finite expiry. Self-rehash of a downloaded
index/source is insufficient. Before filtering or pagination, all indexed
Statement IDs/versions must still exist in the current public Statement and
Person collections and agree on original exact wording/quote SHA, Content,
source URL/version/SHA, date, Person, public route and locator. The original
Statement validator checks its rights, attribution, wording, context and
publication review fields, with no permission granted by this reader.

The private preview returns only currently pinned publicly eligible records
and limited corpus coverage, along with exact source citations, dates and
locators; `publicationAuthorized=false`, `providerCalls=0`. Its strict
shareable `?persona=&tema=&ordine=&q=&pagina=&dal=&al=&fonte=` query
parser/serializer preserves exact IDs (including homonyms), deterministic
date/order/source filtering, bounded pagination and safe previous/next URLs.
Reload, back and forward can recompute from those URLs against the CURRENT
release, without a stored private query session. Missing/previously removed
private identities, phantom memberships, stale index/source/Topic, current
rights withdrawal and malformed URLs never reappear as public hits. Negative
cases also cover mutable source original/date/hash/version/locator/rights,
Person alias conflict, a revoked Topic membership and asset expiry.

**Validation:** TDD RED with a missing consumer module, then genuine Python
fixture → TypeScript GREEN; `tests.test_dp439_person_topic_v3` **8/8 PASS**;
`npm run check` **106 files, zero diagnostics**, Node script and `node --check`
PASS, `git diff --check` PASS. An actual **temporary isolated Astro static
SSR build** renders the approved fixture's original quotation, dated
versioned source link and coverage; SSR rejects an expired authority and
an old pinned release after withdrawal. No production route, provider call,
production dataset, deployment, commit or push was introduced.

**Status stays IN PROGRESS; all original AC-439.1–.7 remain unchecked.**
The precomputed Python join, published Person/Topic and source gates are
independent external inputs; their real signatures/currentness/rights and
semantic Topic approvals were not established by synthetic tests. This
reader cannot observe a privately revoked membership before its authenticated
index/current release pins rotate or expire. Required real MiniPC canary,
atomic HTML/API/search invalidation, mobile keyboard/VoiceOver/focus/zoom
acceptance and actual public deployment remain external to this slice.

## 2026-10-12 — Sessione operatore privata v3, composizione con epoch coerente

Nuovi `web/src/lib/privateV3OperatorSession.ts` e
`web/scripts/check-private-v3-operator-session.mjs`, senza route né modifica
dei consumer esistenti. La mancanza di una composizione atomica fra filtro
DP-439 e synopsis DP-440 costituiva un confine concreto: separati, entrambi
verificavano fonti e pin, ma una pagina che li accostasse non garantiva
identità Person/Topic, `generated_at`, versione sorgente e release epoch
**comuni**, né una lettura `CURRENT` dopo la costruzione dell'HTML. Il test
iniziale era RED (`ERR_MODULE_NOT_FOUND`); è quindi una nuova integrazione
fail-closed, non la pretesa di un exploit riprodotto su una route esistente.

La sessione opt-in richiede un solo set di pin emessi indipendentemente
(`statement`, Person, Topic, join, index, synopsis, fonte, epoch e scadenza);
controlla la coerenza delle copie della stessa release e il vincolo esatto
dell'URL condivisibile `?persona=…&tema=…&ordine=…&pagina=…` con Person/Topic
autorizzati. Fa una copia della fixture prima degli `await`, riusa il reader
DP-439 per originali e ordinamento, riusa il browser DP-440 per testo
precomputato, citazioni originali separate e noindex. Le letture indipendenti
`CURRENT` avvengono prima, fra i due lettori, dentro il browser synopsis
(prima/dopo la verifica delle fonti e dopo il suo rendering) e **ancora dopo**
l'assemblaggio finale della sessione. Un cambiamento della membership,
della versione fonte, del Topic, dei pin, dell'epoch o della scadenza
rifiuta l'intera risposta. Navigazione precedente/successiva per pagina,
anchor per singola dichiarazione, target focalizzabili e conteggio risultati
sono deterministici; HTML di fonte e synopsis è escapato, senza stance
inferito, chiamate provider o autorizzazione di pubblicazione.

**GREEN locale:** fixture reale `prepare_public_synopsis()` Python con
Person/Topic DP-438/439 → TypeScript → Astro SSR isolato, con pagine condivisibili,
replay/reload, focus anchor, revoca Topic ricalcolata, diritti mancanti,
Person/Topic fuori scope, sorgenti/pin misti, pin scaduti e deriva di epoch
prima, durante e dopo gli `await`. Il build SSR per una revoca o per la deriva
di epoch dopo il rendering fallisce chiuso. Script Node **PASS**;
`npm run check --prefix web` **117 file, zero errori/warning/hints**;
suite Python DP-439/440 **22/22 PASS**, `git diff --check` PASS.

**DP-439 resta IN PROGRESS, AC-439.1–.7 ancora tutti aperti.** Il test
simula revisioni/diritti approvati; non autentica un vero release issuer, non
aggiunge route operatore con autenticazione e `Cache-Control: private,
no-store`, non prova fonte licenziata né cancellazione cache/API/sitemap,
accessibilità VoiceOver/schermi reali o MiniPC. Nessun commit/push/deploy o
pubblicazione. Un'ipotetica revoca non ancora ricevuta dal release issuer
rimane fuori dalla capacità di rilevazione di questo consumer offline.

## 2026-10-14 — Source-pinned v3 Explore read model, no public activation

New opt-in `web/src/lib/publicPersonTopicExploreV3.ts` produces a bounded
**offline/public-data-only preview** for the actual DP-439 Person×Topic
join. One asynchronously snapshotted input includes published Person-v3,
reviewed intersection, immutable searchable original index and separately
issued current release pins. It reuses the full cross-reader preflight
to reject independently valid but mutually inconsistent Person/index/source
artifacts, then executes the real signed-index search. A second expiry check
prevents returning an out-of-date result after cryptographic awaits.

The view-model supports strict sharable URL `persona`/`tema`/`ordine` filters
and bounded `pagina=1..500` pagination with `pageSize=1..25`, native original
Statement date ordering, exact original text **distinct from summary**,
source title/URL/version/quote SHA and literal locator, Person/Topic routes,
current-corpus generated timestamp and explicit coverage note. Unknown,
unpublished or withdrawn Person/Topic URL filters yield generic `NO_MATCH`
without echoing the caller's private ID in returned labels/share URLs; facet
options are sourced only from the already approved Person collection and
Topic memberships actually present in the pinned search index. It has no
ranking of persons, source retrieval, provider call or publication authority.

Test `web/scripts/check-public-person-topic-explore-v3.mjs` was initially
**RED** because this new consumer did not exist. It is now **GREEN** using
the real synthetic Python DP-439 `published()/make()` generator, with two
approved People, three dated exact original Statements and four Topic
memberships. It proves Person×Topic selection, exact original/locator, page
1/2 ordering and share URL replay, detached output, invalid/private facet
non-disclosure, malformed/duplicate pagination refusal, separately revoked
Topic memberships, stale mixed source pins and late SHA expiry refusal.
Existing Python→TS public index, v3 cross-reader and private Person×Topic
Astro SSR regressions PASS. `npm run check` validates the new module with
**0 errors/0 warnings** (one preexisting DP-429 unused-import hint).

The new module is **not wired to a public Astro route**, and there is no live
pin-issuer, source-rights authorization, real editorial Topic membership,
cache-invalidation readback, provider-offline hosting acceptance or MiniPC
pilot in this release. Original DP-439 **IN PROGRESS**, AC-439.1–7 all
unchanged and open. All fixtures are artificial and publication remains off.

Independent read-only review exposed a **P2 filter-choice ambiguity**: two
independently approved homonymous People yielded identical display labels,
and two independently distinguishable Topic route IDs both appeared as the
same generic "Tema pubblico approvato". This prevented an accessible filter
reader from selecting an exact person/Topic despite distinct pinned IDs.
The new duplicate-label assertions reproduced RED. The Person option now
includes its **approved** disambiguator and validated canonical public route;
Topic options use the only public distinguishing information available in
this v3 search artifact (their already pinned public route), without deriving
unreviewed semantic names from private records. Same fixture now GREEN.
No new identity inference, additional public attribution, or URL/source
permissions are granted. The reporter's final re-review is tracked separately.

**Independent final review:** worker-7, read-only, inspected the final new
source/test diff and independently validated distinct pinned Person routes,
approved disambiguators, Topic canonical-route uniqueness, malformed/page
limit refusal, private URL normalization, source detach before SHA and expiry
after SHA. Real Python→TypeScript fixture and adjacent v3 search/cross-reader
tests PASS; **no additional P1/P2** within source-only scope. The reviewer
performed no edits, publication, provider or Git writes. This adds no physical
browser VoiceOver/200% public-v3 route, rights approval or real-source AC.

## 2026-10-14 — Offline temporal Explore facets from pinned public originals

New isolated opt-in private `private_person_topic_temporal_v1.py` with
adversarial real-Python DP-439 Person×Topic membership fixtures. It produces
month-bucket summaries from the date **printed on each public original
Statement**, carefully labelled `ORIGINAL_STATEMENT_DATE_NOT_INGESTION_OR_ARCHIVE`.
The model distinguishes count of public Person×Topic intersections from the
number of unique Statement/version originals, so a Statement linked to two
approved topics never becomes two independent original records. Exact
public Person/Topic filters combine with bounded first/last month, a
deterministic descending timeline and counts of distinct public persons and
topics. Unknown or private-looking facet identifiers return generic
`NO_MATCH` with **no ID, label, text, quote or private roster echoed**.

The source refuses absent opt-in, wrong independently supplied join/source/
person release SHA, mutated joined Person ID after digest, impossible or
future month or source dates, and deliberately does not infer that an empty
corpus means no historical statement exists. A real revised DP-439 membership
manifest with all memberships REVOKED changes the release SHA and fails
against the old independent join pin; the new pin yields a neutral empty
preview. Initial module-import **RED**, then new and adjacent bounded Python
tests **GREEN**; no network, provider, routing, editorial or DB operation.

This is an **offline reference read model, not published Explore UI**, and
does not renew issuer/membership/rights permission. Manual VoiceOver/200%
public-route checks, current authenticated pin issuer, source licensing and
physical MiniPC remain **OPEN**. No original DP-439 Status/AC was changed.
Independent *review of this new diff* remains **PENDING** because no reviewer
worker was operable; prior independent PASS on earlier DP-439 source must not
be misrepresented as a review of this new temporal code.

**Post-source-audit adversarial RED→GREEN:** even when all original
Statement dates were in the past, an as-of timeline could previously
consume a fully valid pinned *future-created* public join, misrepresenting
when that corpus was available. A new test at a date preceding the real
synthetic projection timestamp reproduced this before the fix; the reader
now refuses with `TEMPORAL_SNAPSHOT_IN_FUTURE`, after verifying the join's
immutable release SHA and parsing its timezone-aware UTC snapshot instant.
This does not invent an archive-added time and changes no editorial or
factual determination. Source-only review by prime, not independent PASS.

**Final bounded validation:** 14/14 combined private temporal facet and
original DP-439 Python tests PASS. A single completed full Python suite
on a byte-identical detached main overlay containing the new feature plus
the updated DP-320/DP-440 code returned **3,476/3,476 PASS**, exit 0 in
330.917 s; Ruff/format/compile and deterministic benchmark 5/5 PASS.
The published DP-439 opt-in SSR still passes real Python→reader→Astro
noindex, XSS, empty/unknown/revoked, and Astro `npm run check` reports
129 files, zero errors, zero warnings, one preexisting hint. Manual/physical
accessibility, current issuer/rights and independent reviewer approval remain
PENDING. All original DP-439 Status/AC preserved.

**Independent P2 after SHA validation:** worker-9 reproduced a noncooperative
Python `dict` subclass that replaces the public join's `data` on the fourth
access, *after* the canonical DP-439 filter SHA check but *before* returned
rows are copied. The original temporal reader could therefore count a forged
`PRIVATE_PERSON_SENTINEL` while the independently pinned digest remained
unchanged. Synthetic RED reproduced `READY_PRIVATE_PREVIEW` for that ID.
The repaired private temporal reader now makes a bounded detached JSON
snapshot **before all pin checks**, validates exact source, Person and join
SHA on that snapshot and passes only the detached plain dict to the
canonical filter. The former RED is GREEN: unknown private-looking Person
produces `NO_MATCH` without echo; 15/15 new and adjacent DP-439 tests PASS.
This was an in-memory source contract finding, not an observed historical
real private identity disclosure. Final independent re-review requested.

**Final independent source-only re-review:** worker-9 separately replayed the original noncooperative `SwitchAfterDigest` fake public join. The detached-snapshot reader returns `NO_MATCH`, record count 0, never dereferencing the caller's mutable `data` after snapshot. Reviewer Python DP-439 subset **15/15 PASS**, no further reproduced P1/P2 within this offline count-only model. No actual private identity data, published route, manual accessibility, issuer entitlement, legal/rights or MiniPC acceptance is asserted.

**Final codefreeze validation:** combined Python unittest discovery over byte-identical final DP-320/DP-440/DP-439/DP-314 source-only changes **3,503/3,503 PASS, exit 0, 306.597 s**; deterministic benchmark **5/5 PASS**; DP-439 private timeline+canonical join **15/15 PASS**, independent reviewer reverified `SwitchAfterDigest` private-ID injection now returns `NO_MATCH`. Astro SSR 129 files 0 errors, 0 warnings and one preexisting hint; offline route only, no public serving. Interrupted prefinal Python attempt exit143 excluded from acceptance.

## 2026-10-14 — Private month-to-month source-date change inspection (new isolated slice)

`private_person_topic_trend_v1.py` adds an opt-in, count-only **private**
comparison of two independently pinned DP-439 read-model releases. Each release
requires externally authenticated Join / public Statement / public Person SHA
pins **and two independently attested actual JOIN-created UTC timestamps**;
both read models are detached before any validation or comparison. The
existing temporal validator checks all original Statement dates and refuses
historical `as_of` dates before its immutable UTC *source* projection day.
The additional JOIN creation receipts prevent a newer Topic membership join
from being backdated merely because the source projection existed earlier;
legitimate later joins of an older source snapshot remain possible.
Monthly rows separate Person×Topic *intersection counts* from distinct
Statement/version originals and report newly visible and no-longer-visible
intersections/originals between the two snapshots. A second approved Topic
membership for the same original changes an intersection count but does not
create a second original. A stable Statement/version whose date, Person, source
or quote fingerprint drifts is rejected. Bounds are at most 120 calendar months.

**Time semantics:** the buckets are the dates printed on the original
Statements. Newly visible/removed are **comparison results between snapshots**,
not proof of when a Statement was uttered, published, withdrawn or independently
fact-checked. Unknown private-looking filters return generic `NO_MATCH` without
IDs, text, quotes, URLs, identity labels or private roster. Results never claim
absence of historical statements, license, current rights or publication
authority. No public v3 route or provider call is introduced.

`test_dp439_temporal_trends_20261014.py` reproduces actual approved synthetic
source / Person / Topic releases with August retirement, September duplicate
Topic membership and October newly visible original, plus independently pinned
cross-snapshot date drift, wrong SHA, future source/JOIN `as_of`, invalid dates,
UTC creation receipt ordering and legitimate earlier-source rollback, mutable
Mapping after digest and private-ID no-echo. Missing module first reproduced
**RED** (8 test cases), then implemented **GREEN**. Dedicated and
adjacent DP-437/438/439 Python tests **50/50 PASS**, Ruff lint/format and
Python compile **PASS**. This is source-only; source licensing, current release
issuer, real MiniPC data, public UI/accessibility, independent reviewer and all
original `AC-439.1`–`.7` remain **OPEN**. `Status: IN PROGRESS` unchanged.

**2026-10-14 — Independent final monthly-readmodel review and codefreeze.**
Actual strict READONLY reviewer `worker-9` audited exact pre-receipt code
commit `e19c1d41c018591d8f9267d6e65e0b437eddcaec` against its temporal
parent: **9/9** new and **24/24** adjacent tests PASS, plus independent
approved join replays for Aug/Sep/Oct unique originals vs intersections,
JOIN-created UTC receipt future/rollback/naive and source-date drift denial,
distinct Topic membership, revoked visibility and detached-dict adversaries;
**no reproducible new P1/P2 in this bounded private source-only scope**.
The same byte-identical source/test took part in one final 30-file local
Python suite **3,572/3,572 PASS, exit 0, 384.450 seconds**, deterministic
benchmark **5/5**, scoped Ruff and format PASS. Manifest SHA-256:
`15badae206c51cfda9976c86d8eaf6fce10b0e8ccc3ff12480a376db21d3320f`.
The separate offline SSR Astro check had **129 files, 0 errors, 0 warnings,
1 hint**; opt-in/noindex SSR and browser empty/demo automation passed on
their own published code lanes. One inherited DP-314 test F401 remains a
global-overlay lint limitation and does not change source behavior. No
authenticated source issuer/right, qualified review, real MiniPC, live v3
routes, full assistive technology manual acceptance, PR CI or editorial
publication can be inferred. **Status IN PROGRESS, AC-439.1–7 unchecked**.

## 2026-10-14 — Private multi-release Persona×Tema continuity cohort

New isolated, private-only `private_person_topic_cohort_v1.py` audits a
chronological cohort of **2–12** independently pinned public Person×Topic
JOIN releases, rather than comparing just one pair. It reuses the actual
DP-439 canonical join, source-date temporal and monthly-trend validators.
Each release requires caller-supplied, **externally owner-authenticated**
Join/Statement/Person SHA-256 pins and an independently issued timezone-aware
JOIN creation receipt; a self-rehashed snapshot is not publisher authority.
All descriptors' primitive pins are frozen **before any** untrusted readmodel
serialization, and **every** bounded readmodel snapshot is detached before
SHA validation. The audit rejects malformed descriptors, source date in the
future, source/JOIN creation provenance violations, chronology regressions,
stale SHA, a previously seen JOIN digest recycled after an intervening
different release, and a stable Statement+version whose original date,
source SHA, quote SHA, or Person identity drifted across even nonadjacent
releases.

The new audit separates intersection changes from distinct Statement/version
originals, including a multi-Topic original whose surviving Topic never
vanished. A withdrawn intersection that reappears in a later independently
pinned join emits **MANUAL_VISIBILITY_RECHECK_REQUIRED** and generic
count-only transition rows; it **never** approves that revival or claims
when approval/revocation/publication actually happened. A private-looking
unknown Person filter yields neutral NO_MATCH without echoing IDs, names,
original text, quotes, locators or URLs. A 120-month source-date window
bound and complete-original cross-release integrity apply even when filters
would hide the offending original.

Real synthetic DP-439 approved Person/Topic fixture sequence: August
intersection present → removed on the second join → explicitly restored on
the third. It exercises original counts versus intersection counts,
nonconsecutive identity drift, release replay, double-Topic survival,
bad UTC receipt, SHA mismatch, noncooperative Mapping subclasses,
future `as_of`, wrong descriptor type, privacy of unknown identifiers,
and month-restricted queries. TDD baseline **RED 9/9** (module not yet
present), then initial **GREEN 12/12** dedicated tests. Independent
READONLY worker-1 identified a concrete P2 subclass-filter bypass:
an adversarial `str` subtype could compare unequal to its own public
Person ID, making a truly reappeared approved intersection produce false
`NO_MATCH` and suppress the mandatory hold despite valid source SHA pins.
The new regression reproduced RED, and the fix rejects non-plain
`person_id`/`topic_id` before release validation. **GREEN 13/13** dedicated
and **37/37** combined adjacent DP-439 source tests; Ruff and format PASS.
**Independent post-P2 re-review:** worker-1, STRICT READONLY, on exact
source SHA-256 `2b39cd4ddf255683d755fd1aa79c372c2445a05b1bfb7d36708f13aca975519c`
and test SHA-256
`a809fcfb51423b6ff4eb50c27ca8c3319220c018d008f5a1f60ce77a00e1989e`:
independent 13/13 cohort and 9/9 adjacent monthly trend tests PASS,
verified both Person and Topic malicious subclasses now reject,
replayed a recomputed-but-future original source date with no filter and
filtered Person variants (TEMPORAL_SOURCE_DATE_INVALID), and found
**no additional reproducible P1/P2 in this bounded offline source scope**.
Zero reviewer source/test/Git/provider writes. This is not an issuer or
editorial rights clearance.

Deterministic Python benchmark **5/5 PASS** on this worktree. Astro
`npm run check` completed **127 files, 0 errors, 0 warnings and one
pre-existing unused-import hint**; canonical installed `web/node_modules`
remained untouched, and the worktree-only temporary symlink was unlinked.
No public routes were changed. The new source/tests above were not changed
after the reviewer SHA pins.

This release is purely offline and **cannot attest real issuer signatures,
editorial topic decisions, legal/current rights, provider retrieval,
MiniPC, published v3 routes, CDN withdrawal or manual accessibility**.
No original DP-439 Status or AC-439.1–7 is modified. No provider calls,
publication, deploy, paid service or production DB access.

**Final codefreeze Python suite on this DP-439 worktree:** after the
independent reviewer checked the exact unchanged source/test SHA above,
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc:tests python3 -B -m unittest discover -s tests -q`
completed **3,469/3,469 PASS, exit 0, 620.072 seconds**. Full log:
`/tmp/dp439-cohort-continuity-20261014-final-python.log` (Mac).
This full run covers the DP-439 branch baseline plus this cohort change; it
is **not** claimed as a fresh combined run of every concurrent DP-231/314/
320/440 isolated branch. Temporary fixture ResourceWarnings do not change
the observed exit code. The pre-existing DP-439 status and acceptance
checklist remain untouched.
