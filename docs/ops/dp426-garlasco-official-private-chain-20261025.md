# DP-420A / #426 — original private Garlasco source chain

Date: 2026-10-25. Scope: **source-specific private research**, MiniPC PostgreSQL
`dichiarazioni_pubbliche`, collection `research:garlasco`. No public projection,
verification Finding, claim promotion, publisher authorization or model requests.

## Original evidence and scope of processing

| Parliamentary original | Dated sitting | Attribution in original | Persisted original HTML SHA-256 |
| --- | --- | --- | --- |
| [Camera, XIX legislatura, sitting 607](https://documenti.camera.it/leg19/resoconti/assemblea/html/sed0607/stenografico.htm) | 3 Feb 2026 | Vittoria Baldino, direct intervention | `2ab7a0739d6ffc766b45526023ab4bd878c0e996fa90aa7d6dec6a3e0cc7de6f` |
| [Camera, XIX legislatura, sitting 703](https://www.camera.it/leg19/410?idSeduta=0703&tipo=stenografico) | 4 Aug 2026 | Andrea Orsini, direct intervention | `09aa5d2b696722819ca44c978b0c4000094fc60152a64fe81e4fb7e41a5df53f` |

Both texts refer explicitly to the Garlasco case; they are **parliamentary
commentary**, not judicial findings or proof of the underlying allegations.
Each private Passage is the one exact short sentence verified against the
original source body, in the speaker's original sitting section. Candidate
attribution remains `HELD` with no approved Person binding. A separate
`INDEPENDENT_SOURCE` / `MIN_INDEPENDENT_LINEAGES` Coverage Need remains OPEN.

The second HTML endpoint varies presentation bytes between requests. The
operator checks exact sitting, original speaker and phrase on each fetch,
then hashes **the bytes actually observed** and stores those bytes; the
original observed Capture hash is never forged or substituted. The first
endpoint is pinned to the complete original HTML SHA as well.

## Automated rights and privacy disposition, with primary sources

- **Legal text**: [Italian Law 633/1941 art. 5, Ministry of Economy and
  Finance official reproduction](https://def.finanze.it/DocTribFrontend/getAttoNormativoDetail.do?ACTION=getArticolo&id=%7B012E634A-9F52-4452-B7F7-980D83EDE0C6%7D)
  excludes the *text of official acts of the State and public administrations*
  from the protection of that law. [Normattiva's current official text](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=041U0633&atto.dataPubblicazioneGazzetta=1941-07-16&tipoDettaglio=vigente)
  provides legislative context. The selected originals are the official
  stenographic accounts of Parliament, rather than publisher articles,
  broadcaster footage, or editorial interpretations.
- **Source-specific decision**: a machine-reviewed
  `private_source_rights_record` on each exact original URL, Content identity
  and source family permits only `FETCH`, `STORE_BODY`, `PARSE_TEXT`,
  `RESEARCH_CAPTURE_PRIVATE`, `EXTRACT_CANDIDATES` and metadata discovery.
  The receipt cites art. 5, attributes the Camera, expires after 30 days and
  can be superseded or revoked. No `EXCERPT_PUBLIC` or media licence was
  inferred. Original HTML presentation, third-party contributions and site
  conditions are outside any automatic downstream clearance.
- **Operational constraint**: even public parliamentary references to
  criminal allegations or individuals remain confined to the private,
  short-excerpt candidate workflow. No biometric speaker matching, judicial
  guilt inference, public statement, or release promotion was performed.
  Historical broadcaster and newspaper Content remain `UNKNOWN` and
  `capture_authorized=false`.

## Deterministic intake and storage boundaries

`tools/dp426_garlasco_private_pilot.py` defaults to a **zero-write**
original-version preflight. Its `--apply-private-intake` path:

1. Fetches and verifies exactly the two original Camera records; any changed
   quote, speaker, URL, wrong content type or unexpected first full SHA blocks.
2. Opens `research:garlasco` only with an exact check of its historical
   `PAUSED` state and 18 unapproved member guards; the historical
   `pilot_ready=false` and `capture_authorized=false` metadata stays
   false. The source-scoped opening is recorded separately as
   `dp426_source_scoped_intake=true`.
3. Creates source-specific Content/Included links and versioned private
   rights, records privacy ingestion relevance `OFFICIAL_RECORD`, and
   invokes the existing capture authorization and source-use guards.
4. Stores original bytes in the existing restricted Capture body store,
   with `DURABLE_PRIVATE` retention, no archive and immutable original-body
   hash. The pinned parser emits only one source-verifiable Passage per
   original; selectors index its explicit bounded projection, not arbitrary
   offsets into the complete HTML.
5. Re-reads and hashes the stored bytes, verifies exact Passage roundtrip,
   persists a private `HELD` Statement Candidate per Passage and opens one
   sourced research gap; failure of current rights or a changed original
   prevents any newly authorized Candidate.

Source files, full HTML and Passage text are absent from this Git commit
except the two bounded, pinned public phrases needed for deterministic
parsing. Capture bodies remain in the MiniPC private store. Source rights
expiry requires fresh rights review or retention/purge action before further
processing; this intake alone does **not** grant indefinite reuse.

## Real operational readback

MiniPC PostgreSQL readback, independent of the writing CLI:

| Count | Before | After |
| --- | ---: | ---: |
| Included Content | 18 | 20 |
| Original Capture | 0 | 2 |
| Linked Passage | 0 | 2 |
| `HELD` Statement Candidate | 0 | 2 |
| Collection Coverage Need | 0 | 1 |
| Source-specific rights record | 0 | 2 |
| Historical public research Atomic Claims | 30 | 30 |

The Studio `StudioLoopbackServer` was started **only on
`127.0.0.1`**, with an in-memory ephemeral bearer credential and
read-only PostgreSQL reader. An unauthenticated POST returned HTTP 401;
both source chains returned HTTP 200 from
`/v1/collections/captures` → `/v1/capture/passages` →
`/v1/collections/passage-candidates`. In each, Studio independently
returned one immutable capture SHA, one selector and one `HELD` candidate.
`/v1/discovery/coverage-queue` also returned HTTP 200 with the OPEN need.
All responses identify their surface as private and without publication
authority. No local token was written to Git or exposed in receipts.

The historical Garlasco inventory's 18 original Claim-linked Contents
remain incomplete, as do the 100-item full-pilot, official-procedural,
discovery-provenance and multi-family coverage gates. Its SQL is updated
to count Captures and Candidates across **all Included Content**, while
preserving baseline Claim/Content attribution statistics. This pilot is
a bounded first real chain, **not** full collection acceptance or launch GO.

The merge, installation of changed parser and inventory code, ongoing
real-use proof and issue closure belong to independent orchestration.
