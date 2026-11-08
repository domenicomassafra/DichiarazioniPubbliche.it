# DP-468 — Senato source → Statement v3 producer, held until real authority

This code adds an opt-in, read-only adapter; it does not activate a public
release or issue rights, model completions, agent decisions, or release pins.

## Exact source under investigation (31 October 2026)

The selected real candidate is the Senato XIX legislature, sitting 310
(29 May 2025), XML Akoma Ntoso at
`SenatoDellaRepubblica/AkomaNtosoBulkData` commit
`bfac144eb5c54820971bc1020fece11aae56ec90`,
`Leg19/Atto00055187/resaula/01457617-ra.akn.xml`.
The source XML SHA-256 is
`1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`
and Git blob SHA-1
`bec30c067a1a79e8b377af483cfc4bfb44d13896`.
The current candidate for Gisella Naturale is a **private HELD candidate**;
these hashes verify provenance, **not** publication rights or identity approval.
The canonical text SHA-256 and corresponding exact Content ID must come from
an independently verified current Capture readback; the builder never
derives authority by trusting the candidate's own pins.

## Wiring

Construct `PinnedSenatoV3Source` with the exact current Content ID,
commit-pinned raw URL, XML SHA-256, Git blob SHA-1 and independently verified
canonical text SHA-256. Give `CurrentSenatoCaptureBytes` the existing
`CapturePipelineStore`, `CaptureBodyStore.open_existing_readonly(...)`, and
`SourceFamilyUseGuard` using the current revocable private rights registry.
It checks `PARSE_TEXT` before and after a bounded body read and checks
the Capture record again, rejecting purged, quarantined, held, changed or
rights-unknown captures. Before reading, it also binds the private-use
guard to the exact Senato source family, Content ID and pinned source URL;
a PARSE_TEXT grant for another artifact must never read these bytes.
This permits an internal integrity read only.

Pass this callable to `SenatoPublicV3Source(read_original_bytes=...)`.
For real candidate consumption, `read_current_candidates` must independently
replay durable candidate status, speaker identity and revision. The adapter
accepts only `APPROVED` candidates whose content version, AKN speech ID,
official Person URI and exact character range match the verified document.
It never invents a media timestamp, opinion, public Person approval, or ASR
confidence. Source spans are taken from the normalized canonical written
representation; they are **not XML byte offsets**.

`read_current_attestations`, `read_current_autonomous_evidence` and
`read_current_challenge_hold` must independently replay current persistent
rights/privacy/wording/identity/publication reviews, two real different
authorized-model completion receipts and the challenge status. The autonomous
receipt reader `JournalReviewPacketReader` is now available as a component,
but still requires a separately authenticated current-candidate source and
genuine OmniRoute completion receipts. The attestation and challenge readers
remain unconnected. The receipt reader additionally requires an independently
authenticated provider execution witness, because append-only journal entries
alone can be fabricated by a local writer; none of these lanes defaults to approval.
For the first reader, `CurrentSenatoPostgresCandidates(pins, store=...)`
replays the native PostgreSQL `statement_candidate`/`passage`/`content_capture`
records with the exact pinned source, official speech metadata, approved
identity/quotation status and current Capture status. It requires a stored
`public_version_id` assigned by the separate review process, and verifies the
private passage's literal-text SHA-256. Supply the existing authenticated
`CapturePipelineStore` as `store` and use the reader as
`read_current_candidates=...`; it never mutates rows or upgrades a HELD
candidate. Existing Senato corpus candidates are HELD, so this returns an
empty list until they have real approval receipts. Merely changing database
status or metadata cannot satisfy the later independent publication gates.
The reader also carries the persisted private passage SHA-256 to the producer:
the independently reconstructed canonical span must have that exact hash.
If approved corpus wording and immutable source wording differ, the candidate
is omitted rather than silently replaced during projection.
`senato_v3_binding.bind_senato_public_v3(...)` now composes the existing
Capture, PostgreSQL candidate, private authority/challenge and persisted
two-model-review readers into one `SenatoPublicV3Source`. It requires the
independently authenticated `read_current_candidate`,
`verify_provider_execution`, `verify_authority_review`, and
`processing_family_approved` callbacks. Missing callbacks fail at construction;
missing or stale attestations fail during projection. A local journal entry or
an approved database status alone never makes a Statement public.

The production caller must still supply those *actual* external authorities,
registered model-scoped credentials, verified Senato Capture/body/rights state
and release pin. The nightly auditor and public consumer are not activated by
the composition function. No production consumer calls it yet, so the live
site remains on v2 until #413 and #98 complete their independent gates.
Call `build_public_projection(adapter, include_public_statements=True)`
only in a private verification context; the existing producer calls every
proof reader and silently omits an ineligible Statement. An empty bundle
is **HOLD**, not an eligible public release.

## Remaining blockers

- The existing private rights registry always denies `EXCERPT_PUBLIC`;
  source-specific, version-bound public quotation/privacy/retention/correction
  authority with legal citations and revocation readback is still required.
- Distinct authorized model identities, genuine completion IDs and independent
  review proof remain required. Synthetic test overrides are never usable here.
- Production candidate, current proof, challenge and correction adapters
  require authenticated durable implementations; the current system has
  only their boundaries. There is no public release pin issuer in this change.
- The independent #355/#98 release process must verify full Person/Statement
  hash coherence, private canary, atomic switch, API/HTML/search/sitemap/CDN,
  withdrawal and correction before any GO-PUBLIC.

Tests: `tests.test_dp468_senato_public_v3_source` checks real AKN XML parsing,
private Capture readback, source mutations, absent authorities and statement
omission without fake rights or reviews. `tests.test_dp468_senato_v3_binding`
checks the actual composition and refuses synthetic authority by omission.
No test issues a publication pin.

## First-batch source coverage readback (8 November 2026)

The pinned original Senate XML was fetched again from the exact immutable raw
URL above and passed through the existing `import_senato_akoma_stenographic`
parser with its Git blob SHA-1 check. The returned SHA-256 remained
`1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`:
121 source-linked speech turns, five unresolved speaker turns, and **35 distinct
official `TLCPerson` URI candidates**. The source carries a CC BY 4.0 notice;
the separate [Senato legal notice](https://www.senato.it/guida-al-sito/avviso-legale)
also requires correct attribution, source integrity, public-interest use and
respect for third-party rights. This is source coverage, not legal clearance.

The native `tools/dp331_senato_private_speech_readback.py` ran on the real
MiniPC Capture/PostgreSQL store in four read-only groups of three ordinals:
`0,3,5`; `6,7,8`; `13,16,31`; `33,41,42`. All twelve source speaker references
resolved to **twelve distinct official Person URIs** with the exact current
Capture hash; the private-use rights record was `CLEARED` through
`2026-11-23T21:53:43.934666+00:00`. Every returned observation had
`decision=HOLD`, `attribution_approved=false`, `publication_authorized=false`.
No public quote, Person resolution, fact, inconsistency or topic was approved.

The public 10/10/10/10 batch still requires independent identity and quotation
review, source-specific `EXCERPT_PUBLIC` authority, all six GDPR processing
decisions, genuine upstream model receipts from #413 and the deployed v3
consumer/correction/rollback proof from #98. Neither a count of speaker URIs
nor a private rights record satisfies those requirements.

## Official licence-scope reconciliation (8 November 2026)

Three live, official publication notices were fetched independently on Studio
on 8 November 2026. The immutable [README at the exact AKN commit](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/bfac144eb5c54820971bc1020fece11aae56ec90/README.MD)
states **CC BY 4.0** for that repository. The Senato's [open-data FAQ](https://dati.senato.it/sito/faq?testo_generico=16)
instead identifies **CC BY 3.0** for the general data portal; this is a
different licensing scope, not evidence that the pinned AKN repository has
silently changed licences. The Senato's [site legal notice](https://www.senato.it/guida-al-sito/avviso-legale)
conditions reuse on public-interest information, correct source attribution
and content integrity. It expressly reserves third-party/personality rights
and disallows modifications and derivative works without specific written
authorization. For a public quotation, the exact applicable content and
terms must be independently reconciled; neither a general FAQ nor a bare
CC BY badge overrides these conditions.

Byte hashes of the three HTTPS bodies, as read on that date (SHA-256):

| Official material | SHA-256 |
| --- | --- |
| Pinned AKN README `bfac144e` | `cd01c53874c63df20d18ea151b3e5528af329dbc64ee573be4d480368f5a34dc` |
| Senato site legal notice | `1ffd4233850eed86879ae01c973cd17d19f157338d48bd7b1c8ca8f222e88b89` |
| Senato open-data FAQ | `256c47893dc660d015ab213517be2b8f67e34a00852103b289d740128e39fc95` |

To reproduce, use `curl -fLsS --max-time 18 '<URL>' | shasum -a 256`
with each exact URL above; a changed hash requires a fresh review rather than
blindly trusting this dated snapshot. These hashes prove fetched body bytes,
not the applicability of a public licence to an individual passage.

**Disposition: PRIVATE_HOLD / NO-GO.** The independent rights reviewer must
identify the exact source/segment, original source link, author and third-party
rights, applicable licence version and attribution, publication purpose,
verbatim/no-derivatives constraints, renewal/revocation path and current
receipt. Separately confirm the six lawful processing decisions, identity,
wording, current Capture and distinct #413 execution reviews before issuing
any version-bound `EXCERPT_PUBLIC` authority. This evidence is a preparatory
source review; it issues no grant, changes no ledger record and cannot unlock
the consumer on its own.

## One-candidate independent rights assessment (8 November 2026)

On Studio, a separate read-only Codex GPT-6.1 Sol assessment examined the
existing **HELD** candidate attributed to Gisella Naturale, concerning the
sentence *«l'animale è stato definito essere senziente»* in the [pinned AKN
record of sitting 310, 29 May 2025](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/bfac144eb5c54820971bc1020fece11aae56ec90/Leg19/Atto00055187/resaula/01457617-ra.akn.xml).
This is a source-specific research assessment on Studio `main` at
`c0e33d4414cb0212484cd22451785d808385bf2d`, **not** an authenticated
release-authority review, approved speaker identity, or product-model execution
witness. The passage's current Capture offsets, two independent attribution
signals and current public grant have not been demonstrated by this review.
An additional read-only Studio fetch through
`import_senato_akoma_stenographic` confirmed the pinned XML SHA-256
`1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`:
the literal sentence occurs in speech ordinal **5**, with source speaker URI
`http://dati.senato.it/osr/Persona/32673`. This verifies the original wording
and its source-level speaker reference, not an independently approved identity
or a current private Capture/publication receipt.

- **Applicable rights scope:** The [commit-pinned AKN README](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/bfac144eb5c54820971bc1020fece11aae56ec90/README.MD)
  credits the Senato's Servizio dell'Informatica and states CC BY 4.0.
  [CC BY 4.0, sections 2–3](https://creativecommons.org/licenses/by/4.0/legalcode.it)
  grants reuse of rights held by the licensor; it does not supply third-party
  rights or personality/privacy clearance. The separate [Senato site legal
  notice](https://www.senato.it/guida-al-sito/avviso-legale) is recorded with its
  SHA-256 above, but its live page blocked the independent reviewer, so this
  assessment does not claim a fresh retrieval of its terms. The repository
  grant and the site notice must be reconciled for the *exact* passage: a
  third-party reservation is neither proof of permission nor an automatic ban.
- **Attribution if eventually approved:** Gisella Naturale is the proposed
  *speaker*; the Senato is the source/publisher of the stenographic record.
  Cite both roles, sitting 310, 29 May 2025, the exact pinned document link,
  CC BY 4.0 and a verbatim quote with sufficient context. Do not turn this
  sentence into a verified factual claim, a motive, or an accusation.
- **Privacy and independent review:** The candidate concerns parliamentary
  activity; the quoted sentence itself does not appear to identify a third
  party or disclose sensitive information. That observation does not decide
  necessity, Article 6 balancing, source-person rights or retention. All six
  required processing families remain `BLOCKED` in
  `docs/policy/privacy-processing-decisions-v1.json`. The existing
  `licence_excerpt_decision_v1` may permit **private** quotation only; a public
  `EXCERPT_PUBLIC` authority still needs its own current, revocable decision.
  Product review also requires separately authenticated upstream execution
  receipts, rather than the fact that a Codex reviewer ran on this document.

**Disposition for this candidate: `PRIVATE_HOLD / NO-GO`.** Next verifiable
steps are current Capture/wording/offset readback; two independently sourced,
non-biometric identity signals; a dated, source-and-passage-bound rights
decision with revocation and attribution; actual per-family GDPR necessity,
notice, access, retention and independent-review receipts; then the genuine
three distinct model executions (#413) and public v3 release/correction
readback (#98). None was minted by the read-only assessment.
