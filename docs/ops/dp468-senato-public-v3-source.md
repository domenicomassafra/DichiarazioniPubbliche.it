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
authorized-model completion receipts and the challenge status. These
readers are deliberately **not implemented or defaulted to approval**.
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
Production wiring for the remaining three independently authenticated
authorities and the release pin remains pending.
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
omission without fake rights or reviews. No test issues a publication pin.
