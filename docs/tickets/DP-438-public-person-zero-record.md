# DP-438 — Person pubblica autonoma, anche senza Statement

Status: IN PROGRESS
Milestone: M4 — public product/API
Depends on: DP-105, DP-222, DP-402, DP-437

## Problem

DP-405.3 descrive Person pubblicamente approvata ma ancora priva di record; la proiezione corrente e il client estraggono le Person solo da Dossier con Finding, quindi tale pagina non esiste. Una persona che esiste soltanto nel database privato deve invece continuare a essere indistinguibile da un identificativo ignoto.

## Outcome

Una risorsa PublicPerson autonoma, con identity/publication review e stable public URI, che può avere zero PublicStatements e fornisce a DP-405 una cronologia effettiva quando ci sono registrazioni approvate; mantiene ruolo temporalmente valido, no score, no private roster leak.

## Traceability & constraints

R16/R20/R25/R36, DP-105/222/405; il vecchio DONE DP-105 prova il person-derived-from-dossier model, non una persona approvata senza finding. Non pubblicare qualsiasi Person ricercata solo perché in DB o nominata in una fonte. Approved roles intervals non sono automaticamente biografia esaustiva.

## Scope

Progetto di record PublicPerson con stable ID/slug, approved display name e identity disambiguator pubblico quando autorizzato, approved role intervals con source refs/valid_from/valid_to, public identity decision, version/status, privacy/sensitive policy refs, bounded profile scope e membership di statement IDs autonomi. Join dei PublicStatements solo dopo gate source/context/attribution; la cronologia deve distinguere emission_date vs pubblicazione/verified dates. La proiezione possiede un first-class people collection, mentre il vecchio algoritmo derivato da dossier è compatibilità v2 dichiarata. API/read/static pages/index consumano lo stesso set; zero-record approved Person produce empty state del record pubblico e link a Esplora/Metodo. Gli unknown, private, revoked e non-public Identity ID non appaiono e restituiscono uguale 404/generic unavailable.

## Non-goals

Database di persone mondiali, scraping CV/biografia privata, score, immagini non approvate, verifica biometrica e person-level verdict; Topic membership è DP-439 e non si deduce da nome nel testo.

## Dependencies and sequencing

Hard DP-105/222/402 e DP-437 dopo assegnazione del vero ID; B/A confermano speaker identity and approved time/context; D owns dataset release/caches. Soft DP-405/409/422 e DP-430 taxonomy; il nuovo schema deve essere predecessore del positivo AC-405.3 e non viceversa.

## Acceptance criteria

- [ ] `AC-438.1`: Person first-class approved ma con zero Statements produce route, API entry e approved empty state senza check/score/placeholder.
- [ ] `AC-438.2`: unknown/private-only/held/revoked Person non compare né come search suggestion/facet/cursor/sitemap e restituisce stesso boundary osservabile di sconosciuta.
- [ ] `AC-438.3`: Person con Statement e senza Finding è navigabile con fonte, original quote e data; claim-only/titolo fonte che cita il nome non ne fa un'affermazione della Persona.
- [ ] `AC-438.4`: dated role label si applica solo agli intervalli approvati che coprono statement time e con provenance; gli intervalli assenti/contraddittori non generano ruolo corrente inferito.
- [ ] `AC-438.5`: multilingua e due omonimi hanno stable IDs distinti; merge/split identity o role review revocato propaga ricostruzione e mantiene history solo quando pubblicabile.
- [ ] `AC-438.6`: repeat build di una Person unchanged produce stesso fingerprint/route; private membership changes non incidono in modo osservabile sul set pubblico salvo nuova decisione pubblicata.

## Validation / proof

Fixture matrix approved-zero, approved-one-opinion-no-Finding, multiple dated roles, two homonyms, one private-only/unknown collision, revocation, source quotation of person without endorsement; tests validator/API/search/static routes + no-private counts; MiniPC isolated readback approved zero Person vs unknown same response, real approved populated Person once eligible.

## Documentation, data, and migration impact

Additive public people collection with approved-vs-private identity discriminant; update public projection/API OpenAPI compatibility, search generation and canonical Person route; no auto-exposing legacy private people. Existing DP-405.3 remains unchecked until runtime proof.

## Completion receipt

Non implementato; pianificazione soltanto. Future schema replay, identity approval refs, public projection SHA, zero-record live Person and private/unknown negative evidence, rollback.

## 2026-10-11 — First implementation slice

Commit `7e8bbbb`. Added standalone opt-in `public_person_v3.py` and 10 tests PASS: an independently approved public Person can have zero Statement members, with source-reviewed dated roles, disambiguation and fail-closed private/unknown records. v2 and public router are unchanged. No authentic approved Person, v3 public route/API/search integration or MiniPC positive readback exists. **All original AC remain unchecked**; this is a local source-only test receipt, not permission for live publication.

## 2026-10-11 — Identity lookup collision hardening (source-only)

The v3 getter accepts both stable `person_id` and human-readable `slug` in one lookup namespace. Previously, a separately approved Person could use as their stable ID the public slug of another approved Person. Both records were emitted; looking up that identifier then silently resolved whichever Person happened to occur first in display-name order, potentially returning the wrong identity or archive. The existing duplicate-slug guard did not catch this case.

The isolated projection now checks *both* identifier kinds for collisions across distinct approved identities. It withholds every affected Person regardless of private roster order and leaves unrelated, independently approved identities visible. Synthetic RED regression `test_stable_id_matching_another_person_slug_holds_both_public_identifiers` failed before the guard (three records emitted instead of just the unaffected Person), then passed with the correction for both roster orders. The regression also checks deterministic `dataset_sha256`, stable ID/slug lookup for the unaffected Person, and identical public output after an unapproved private Person adopts the same slug. Focused `PYTHONPATH=poc python3 -m unittest tests.test_dp438_public_person -v`: **11/11 PASS**; `python3 -m compileall -q poc tests`, `git diff --check` and deterministic `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`: **5/5 PASS**.

This strengthens the AC-438.2/5 local identity/lookup boundary only; the cross-surface API/search/sitemap, real approval, merge/split propagation and MiniPC revocation readback remain unproved. Source-time role, overlap and revocation synthetic checks continue to pass for AC-438.4. **Ticket remains IN PROGRESS; all AC checkboxes remain unchecked.**

## 2026-10-11 — Opinion card source-span provenance and current-replay guard

An independent follow-up found that the opt-in v3 Person membership already
included an approved original quote and quote/source hashes, but **omitted**
the canonical Statement URL, original Content identity, immutable source
version, and approved written/timed locator. Replacing just the approved
source version or moving a valid same-length quote locator produced the
**same Person read-model `dataset_sha256`**. Such a card could not direct
the reader to the exact source span, and a changed source record was invisible
to Person fingerprint-based consumers. Tests for both changes were **RED**.

The Person Statement row now includes a canonical
`/dichiarazioni/{statement-slug}/` deep link using the same validated
v3 Statement slug grammar, original `content_id`, `source_version`,
`source_kind`, and an independently copied public locator. Consequently
source-version or locator-only corrections change the Person read-model
fingerprint. Synthetic tests additionally exercise timed segment/millisecond
locators, an approved opinion without Finding, and a withdrawn Statement
returning its independently approved Person to a genuine public zero-record
empty state, with no private membership count or inferred verdict.

A second replay/currentness defect was reproduced. The Person join accepted
an internally valid **historical** Statement v3 bundle, even if the
currently approved published bundle had since withdrawn the original
Statement. `build_public_people_v3` now *requires* an externally supplied
`current_public_dataset_sha256`; a missing, malformed, or mismatching
current fingerprint rejects the entire build, without revealing held/private
membership. The local fixture passes an explicit synthetic fingerprint;
the real owner must obtain it from an independent current publication
authority, never derive it from the stale input bundle.

Finally, the existing validated input bundle was read again **after**
iterating private roster/role inputs. A lazy roster generator could mutate
the bundle's original words between validation and membership assembly,
emitting forged text paired with the previously valid quote hash. The
adversarial test was **RED** and became **GREEN** after making an isolated
bundle snapshot *before* validating and joining. No raw transcripts,
source permission decisions or unapproved bodies are projected by this
change.

Local focused tests: **18/18 PASS** (previously 11), including the
new source correction, written/timed locator, withdrawal, stale-fingerprint
and mutable-source callbacks. Deterministic benchmark **5/5 PASS**;
`git diff --check` passes. No new v3 public route/API/search/sitemap
or publication path has been activated. **DP-438 remains IN PROGRESS and
all AC-438.1–.6 stay unchecked:** independent real Person publication and
current-rights attestations, atomic cross-format withdrawal/rebuild,
stable owner-controlled aliases, the integrated v3 frontend/API/index,
and MiniPC positive/negative acceptance remain external gates. No
commit, push or deploy was performed in this worker tranche.

## 2026-10-12 — Private pinned zero-Person SSR reader (local, partial)

Added **only** `web/src/lib/privatePublicPersonEmptyV3.ts` and
`web/scripts/check-private-person-empty-v3.mjs` as opt-in **private/isolated
preview** artifacts; no public route, API, sitemap publisher or production
activation. The Node test executes the **actual Python DP-438 and DP-439
fixtures/builders**, producing an independently synthetically reviewed
zero-Statement Person, two same-name approved People with distinct public
disambiguators, source-linked opinion Statements without Findings, dated
approved role intervals, a held/private Person, identity withdrawal and
source-rights revocation. These local fixture approvals are **not** real
human/editorial/source-rights attestations.

The SSR-safe reader requires separately supplied current public Person,
Statement, Person×Topic join and indexed search release SHA pins, a finite
expiry and the exact source publication timestamp (not covered by the
collection digest). It invokes `readApprovedPersonV3`, the existing v3
search index validator and `preflightPublicV3CrossReaderRelease`, validates
every public original Statement/rights provenance against the pinned v3
source bundle, and cross-checks Person history against source ID, version,
Content identity, source URL/SHA/version, exact original quote/SHA, date,
locator, speech act and Finding-nullability. Source-time roles are checked
against approved intervals, including missing/ambiguous roles. A
Statement still published for an approved Person may not silently disappear
from their archive and create a **false approved-zero state**, even when a
malicious disconnected no-Topic archive and join have internally consistent
recomputed hashes.

An independently pinned candidate Person sitemap-route set is compared with
**all and only** the approved Person routes, including approved empty People;
phantom private/held/withdrawn identities, duplicate paths and missing
routes are refused. This is a *prepublication route-set consistency test*,
not a claim that production sitemap/search or Person URLs serve v3.
Unknown, private/held, revoked and invalid identifiers return the exact
same generic `UNAVAILABLE` projection without ID, route or private count.
Approved zero Person instead returns a distinguishable public empty state;
approved opinion Person retains original source/date and does not acquire
a factual verdict. Output snapshots prevent later source mutation from
rewriting an already returned quote/role/locator.

TDD began **RED** because the new consumer did not exist, then reached
**GREEN** with genuine Python→TypeScript fixtures and temporary Astro static
SSR builds: approved zero profile, source-linked opinion page, identical
private/unknown HTML, expired release and stale post-revocation build
failures. Tests also reject cross-reader source mutations, Person/source
split-brain, timestamp drift, missing/forged sitemap routes, stale identity,
withdrawn source rights, and an independently self-rehashed missing-archive
Statement. Python DP-438 focused test suite **18/18 PASS**; `npm run check`
**109 files, 0 errors/warnings/hints**; Node/SSR regression PASS.

**DP-438 remains IN PROGRESS: original AC-438.1–.6 all unchecked.** There
is no independently issued live release pin, genuine qualified identity or
rights authorization, deployed first-class API/route/search/sitemap,
atomic revoke/cache invalidation or MiniPC positive/negative canary.
Local synthetic SSR is not proof of a production/public v3 cutover.

## 2026-10-13 — Withheld alias collision cannot hide an unrelated approved Person

The opt-in first-class Person projection had a false negative at the public
identity boundary: it computed same-display-name ambiguity before withholding
two independently approved records with a cross-person stable-ID/slug alias
collision. Consequently, an otherwise approved third Person sharing one of
those display names disappeared, even though the conflicting namesakes could
not be published. The unrelated Person could have zero Statements; the
projection silently discarded its legitimate approved empty state.

A deterministic regression was RED on the original code and GREEN after the
minimal ordering correction: first withhold ID/slug-colliding identities,
then compute homonym disambiguation only from remaining publishable records.
Both private roster orders preserve the one unrelated Person, deny lookup of
the colliding identities, preserve its zero-Statement state and produce the
same release fingerprint as a build containing that Person alone. DP-437,
DP-438 and DP-439 adjacent focused tests **34/34 PASS**, deterministic
benchmark **5/5 PASS**; the main suite and delivery/CI are recorded separately.

This is an isolated source-only public identity correctness fix; it does not
add a public v3 Person route, search/sitemap activation, owner-approved source
rights, independent current release pins or MiniPC publication authority.
**DP-438 remains IN PROGRESS and AC-438.1–.6 stay unchecked.**

## 2026-10-13 — Immutable approved Person frontend readout

The opt-in `readApprovedPersonV3` consumer independently validated a
cryptographically pinned collection but returned the caller-owned nested
Person record. A deterministic synthetic RED showed that changing the caller
after validation replaced the returned approved display name, disambiguator,
role interval, original opinion quote and source URL/locator with private
unapproved values while the collection fingerprint stayed unchanged. The
same caller-controlled substitution can race an asynchronous digest.

The consumer now detaches the collection **before** its first asynchronous
digest, validates that snapshot and returns only its contained approved
Person. A new regression covers later and interleaved mutation, two approved
same-name but distinct-ID identities, an independently approved zero-Statement
Person, null Finding for a published opinion, and identical unknown/held
lookups. RED became GREEN with the original code/contract retained.

The combined first-class Person backend and frontend source branch passed
`node web/scripts/check-dp438-person-v3-immutable-20261013.mjs`,
`check-person-v3-archive.mjs`, `check-private-person-empty-v3.mjs`,
`check-private-person-topic-v3.mjs`, TypeScript/Astro `npm run check`
(0 errors, 0 warnings, one unrelated existing DP-429 unused-import hint),
and adjacent backend DP-437/438/439 tests **34/34 PASS**. No newly
qualified source, public route, private data read or production publication
was authorized; original **AC-438.1–.6 remain OPEN**.

## 2026-10-13 — Cross-reader and private wrapper snapshot hardening

Two additional, independently reproducible P2 consumer defects existed after
the direct Person reader fix. In `preflightPublicV3CrossReaderRelease`, a valid
SHA-pinned Person collection was checked but the validated snapshot was
discarded. The later route/history join read the original caller-owned
collection after an awaited digest. On an actual Python-generated bundle
containing **two separately approved zero-Statement People**, the preflight
returned `CONSISTENT_PREVIEW_ONLY` with a private/unreviewed Person URL
substituted during SHA under the previous approved hash (RED).

The cross-reader now snapshots Person, DP-439 join, search index **and release
pins together before its first asynchronous digest** and consumes only that
snapshot. A new executable Python→Node regression proves GREEN for late
Person identity/URL, join, index and independently issued pin mutations,
with the two approved stable Person routes unchanged. No route is activated.

The private `readPinnedPrivatePublicPersonV3` wrapper independently suffered
the same alias issue: immediately after the sitemap digest, a caller could
replace an already-approved zero-Person display name/route. The wrapper then
returned the changed private name in its result (deterministic RED). It now
snapshots source, Person, join, index, sitemap and pins before any `await`.
The existing Python→TypeScript private reader test includes the malicious
sitemap-digest interleave and checks that the previously approved zero-Person
identity survives unchanged (GREEN).

Independent read-only review then reproduced a second asynchronous integrity
gap: both consumers checked `validUntil` only before digest operations. A
previously valid release could expire during a digest and still return
`CONSISTENT_PREVIEW_ONLY` or `APPROVED_EMPTY` (two additional RED regressions,
the latter after the *last sitemap digest*). Both readers now check expiry
again immediately before their final success result, with the private reader
also guarding generic-unavailable responses after validation. The deterministic
clock-interleaving tests are GREEN without weakening the independently issued
pins or modifying Date.now in application source.

These checks are **local synthetic source-consumer proofs**, not an actual
publication, a new real identity/source/rights review or a MiniPC canary.
DP-438 remains `IN PROGRESS`; AC-438.1–.6 remain unchecked. Independent code
review, complete adjacent tests and exact remote-branch delivery are tracked
separately from original acceptance.
