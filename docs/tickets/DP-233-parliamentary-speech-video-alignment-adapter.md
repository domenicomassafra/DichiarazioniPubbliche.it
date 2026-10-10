# DP-233 — Parliamentary speech/transcript/video alignment adapter

Status: IN PROGRESS
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-206, DP-217, DP-218, DP-231

## Problem

Open Parliament-style systems demonstrate a valuable pattern for public-statement archives:
official parliamentary proceedings, speaker identity, agenda/context and media can be
aligned so a public statement has both institutional text provenance and a precise source
locator. The repository already has Camera/Senato structured query capability and generic
media/transcript provenance, but no first-class adapter that binds these records together.

## Outcome

Create an Italy-first parliamentary adapter that can ingest approved Camera/Senato
proceedings, preserve official speaker/role/session metadata, and align transcript passages
with available media locators without biometric identity.

## Acceptance criteria

- [x] Pure intervention contract preserves official session/intervention/speaker refs,
  source URL/version and source transcript hash.
- [x] Speaker identity is emitted only when an external DP-114/DP-218-style resolution is
  explicitly approved; the alignment module performs no
  face/voice matching.
- [x] Official transcript wording remains a source version and does not overwrite platform
  captions/ASR variants.
- [x] Official media timing becomes a direct official locator; without it, exact normalized
  transcript alignment creates only a REVIEW_CANDIDATE.
- [x] Missing or ambiguous text alignment never invents a timestamp.
- [x] Agenda/item/session context is preserved separately from the quoted statement.
- [x] Corrections or amended parliamentary records create new versions/supersession and
  trigger DP-227/DP-511 revalidation.
- [x] Source terms/rights and public excerpt behavior remain governed by DP-305.
- [x] A deterministic fixture proves multi-speaker session alignment with zero cross-person
  attribution.
- [ ] MiniPC canary exercises at least one approved official source family before DONE.

## Non-goals

- No biometric diarization identity.
- No scraping around authentication/access controls.
- No claim that an official transcript proves the factual truth of what a member said.
- No separate parliamentary database/service when the existing corpus model is sufficient.

## Completion receipt

Local official-intervention/alignment contract + focused tests added 2026-10-05. Camera/
Senato ingestion, persistence, source-version/reanalysis integration and MiniPC canary
remain open.

### Official source normalizer follow-up — 2026-10-05

Added `poc/dichiarazioni_pubbliche/parliamentary_official_adapter.py`, a pure/offline
normalizer for already-fetched official Camera/Senato records. It performs no network I/O,
speaker inference, biometric matching, review action, verification, or publication action.

The adapter requires and preserves explicit official chamber, sitting, speaker and
statement identifiers. Sitting date and statement date must match; statement speaker ID
must exactly match the official speaker record; all chamber-owned IDs must carry the
matching `camera:` / `senato:` namespace. Official transcript and video URLs must be HTTPS,
credential-free, default/443-port URLs under the matching chamber domain.

Statement alignment is source-span based and fail closed: the caller supplies
`start_char`/`end_char`, and the exact slice of the supplied official transcript version
must equal the supplied statement text. Video alignment is emitted only when an explicit
complete `start_ms`/`end_ms` range is supplied; no timestamp is inferred when it is absent.

Official transcript wording is retained as its own source version/hash/span. Platform
caption/ASR IDs are preserved only as `variant_refs` and cannot overwrite official text.
Likewise, agenda/item/session metadata is stored in a separate session-context object, not
concatenated into the quoted statement.

Provenance and replay identity are deterministic SHA-256 identities over official IDs,
source versions/hashes, transcript span and explicit video locator. Exact replays dedupe;
the same chamber+statement ID with changed material fails closed as
`PARLIAMENTARY_REPLAY_CONFLICT` instead of silently replacing history.

Offline synthetic fixture `tests/parliamentary_official_fixture.py` contains two
different official speakers in the same Camera sitting. The second row intentionally has
a misleading `platform_author`; normalization still emits only the explicit official
speaker ID/name. Missing official speaker metadata fails even when a platform account name
is present.

Focused proof in `tests/test_parliamentary_official_adapter.py` covers the multi-speaker
fixture, account/platform non-inference, explicit video timing, transcript-variant
separation, separate agenda context, deterministic replay/dedupe, replay conflicts,
HTTPS/chamber URL gates, chamber/date/speaker/span mismatch fail-closed behavior, and the
absence of publication/review/assessment authority from the record contract.

ACs for amended-record supersession/revalidation, DP-305 rights/excerpt enforcement and
the MiniPC canary remain open because this pure adapter does not persist, publish, fetch or
mutate source versions.

### Reviewed amended-record revalidation integration — 2026-10-06

Added `poc/dichiarazioni_pubbliche/parliamentary_amendment_revalidation.py`, a pure bridge
that composes the existing parliamentary normalizer with canonical DP-511
`source_revalidation`, DP-511 -> DP-510 hold-request and DONE DP-227
`supersession_reanalysis` contracts. No Camera/Senato network fetch, provider call, database
write, Finding mutation or publication action is performed by this seam.

For the same chamber-owned official `statement_id`, a changed official transcript version
is normalized as a distinct immutable parliamentary record. The bridge requires the same
chamber, sitting and official speaker identity; uses the statement ID as the stable DP-511
source identity; binds the old/new transcript version and SHA-256; marks the current
snapshot as directly superseding the previous source version; and evaluates it as
load-bearing for quote, speaker and evidence. A real amendment therefore yields canonical
`HOLD_REQUIRED` + `OFFICIAL_VERSION_SUPERSEDED`, a deterministic targeted hold request for
the previous load-bearing source version, and — only after an `APPROVED` review of the exact
DP-511 `event_key` — the canonical DP-227 reanalysis request. That request preserves the
old/new version IDs, content hashes, caller-supplied effective `valid_from`/`valid_until`
dates and affected Claim/Finding IDs. It only returns deterministic reanalysis trigger/job
inputs; it has no publication side effect.

DP-305 remains a separate fail-closed prerequisite. The DP-511 snapshots intentionally keep
`rights_status=UNKNOWN`; an official parliamentary origin does not create quotation or
republication permission. If no `ExcerptRequest` is supplied, public-excerpt readiness is
false. If one is supplied, the bridge delegates unchanged to canonical `decide_excerpt()`:
`UNKNOWN` remains `PROHIBITED`, while only an explicit caller-supplied DP-305 clearance,
public-use grant, approved profile, review and exact provenance can satisfy the excerpt
prerequisite. Rights outcome does not alter or manufacture the DP-511/DP-227 supersession
identity or reanalysis request.

Focused local proof: `test_parliamentary_amendment_revalidation` **7/7 PASS**; combined
parliamentary adapter + DP-511 + DP-227 + DP-305 focused set **95/95 PASS**; `py_compile` and
`git diff --check` PASS. An isolated MiniPC `/tmp` bundle with production DB/provider/API
environment variables removed ran the same **95/95 PASS** and was deleted afterward. This
MiniPC proof exercises the pure integration against the synthetic Camera fixture only; it
does **not** close the final MiniPC AC requiring an approved official source-family canary,
and no live Camera/Senato fetch was attempted.

### Synthetic source-family execution tranche — 2026-10-06

Added `parliamentary-source-family-execution-v1`, a fixture-only Camera/Senato batch seam
over already-fetched records. It performs no network/provider call, production execution,
database/schema write, verification, public projection or publication action. The manifest
must be explicitly `fixture_only`; a non-fixture invocation fails closed.

The executor reuses the canonical DP-233 normalizer for deterministic exact-replay dedupe
and chamber-owned identifier/URL/span rules. It distinguishes `NEW`, exact `REPLAY`, and
materially changed `AMENDED` records. A changed previously seen statement cannot silently
replace the old source version: it requires an explicit reviewed-amendment input and then
delegates unchanged to the existing DP-511/DP-227 amendment bridge, preserving its targeted
hold and reviewed supersession/reanalysis identities.

DP-305 remains authoritative for excerpt readiness. The source-family manifest supplies the
resolved rights state; a caller-supplied `ExcerptRequest` cannot upgrade that state. Requests
must bind the exact normalized source URL, record/statement IDs, transcript source version,
source hash and, when official video timing exists, the exact video range. `UNKNOWN` remains
`PROHIBITED`; only an explicitly supplied synthetic `CLEARED` family state plus the existing
DP-305 gates can make the prerequisite true. The execution receipt contains no publication,
approval, verdict or assessment authority.

Synthetic proof now covers both Camera and Senato source-family shapes, exact replay,
cross-family/chamber refusal, amendment-without-review refusal, reviewed amendment
DP-511/DP-227 delegation, caller-rights upgrade refusal, exact excerpt binding and absence of
publication authority. Focused adapter + amendment + DP-305 + source-family execution tests
are **83/83 PASS**; `compileall`, Ruff and `git diff --check` pass.

No acceptance checkbox changes in this tranche: AC-233.1 through AC-233.9 were already
checked by prior local contracts, while AC-233.10 still requires a MiniPC canary against at
least one approved official source family. This synthetic executor intentionally does not
claim that production/source-approval proof.

### AC-233.10 approved-source-family audit blocker — 2026-10-06

A fresh repository audit found **no explicitly approved Camera/Senato source family** that
can satisfy the prerequisite for the final MiniPC canary. `config/source-registry.v1.json`
contains only the current Pulp YouTube/RSS and Giuliani social rows; it contains no Camera or
Senato launch/source-family entry. `config/evidence-sources.v1.json` does list
`camera-linked-data`, `camera-publications`, `senato-linked-data` and
`senato-publications` as official/authoritative evidence endpoints, and
`config/source-intelligence.v1.json` supplies their bounded authority scopes, but those
contracts do not contain an owner launch decision, `INCLUDED` launch state, source-family
rights clearance or equivalent production approval.

DP-703 is the explicit launch authority and remains blocked: its baseline says the project
does not yet have an owner-approved production launch set and calls the current source
registry provisional, while B-703-03 states `No approved source set exists` and B-703-04
keeps source-specific terms/rights unresolved. A repository-wide search found no separate
Camera/Senato `INCLUDED`, `launch_authorized=true`, approved-use decision, or licensing
closure that overrides those blockers.

Therefore **no MiniPC canary was run in this follow-up**. Running even a read-only canary
against Camera/Senato and calling it AC-233.10 proof would invent the missing approval
prerequisite. AC-233.10 remains open until an owner-approved official parliamentary source
family with resolved source/rights disposition exists; once that exact decision is present,
the existing fixture-only execution contract can be exercised on MiniPC without production
DB/provider mutation.

The final machine-only tranche does run the offline adapter/amendment/source-family contracts on
MiniPC, using the existing synthetic Camera/Senato fixtures only: **32/32 PASS** in an isolated
`/tmp` bundle with production DB/provider credentials removed. This is useful runtime proof of
the code path but deliberately does not change AC-233.10: the prerequisite remains an explicitly
owner-approved official Camera/Senato source family with resolved rights/source disposition,
which is still absent from the repository contracts audited above.

### 2026-10-09 strict verbatim official-statement excerpt binding (Wave 12)

The source-family adapter previously bound a requested public excerpt to
official URL, version, transcript variant/hash, statement ID and video range,
but did **not** compare the caller-supplied `excerpt_text` with the actual
normalized statement span. Invented text or another speaker's words could
therefore produce `ALLOWED` under synthetically `CLEARED` rights.
The validator now additionally requires a nonempty **literal contiguous
substring** of that official statement, without case/whitespace normalization
or cross-speaker stitching, before DP-305 eligibility. Adversarial RED→GREEN
tests cover invented/empty/disjoint quotes, wrong speaker, exact replay and
amended source versions. This remains a **synthetic fixture** gate:
no live Camera/Senato rights, owner approval, publication permission,
or approved-source MiniPC canary is inferred. AC-233.10 stays open.

### 2026-10-10 — Official Senato Akoma Ntoso stenographic candidate import

Official [SenatoDellaRepubblica/AkomaNtosoBulkData](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData)
publishes assembly resoconti under `LegNUM/AttoNUM/resaula/*-ra.akn.xml` and labels
its bulk repository **CC BY 4.0**. This is a different licensed dataset from
the [Senato OpenData RDF dumps](https://github.com/SenatoDellaRepubblica/OpenData)
(CC BY 3.0), whose README explicitly says that they contain **no document text**.
The two licenses cannot be transferred to unrelated Senato webpages, WebTV footage,
ASR/model use, or a source-family approval without their own rights review.

`poc/dichiarazioni_pubbliche/senato_akoma_stenographic.py` is a bounded independent
read-only parser of **already obtained** AKN 3.0/CSD03 official XML. It requires an
immutable 40-character commit URL in the precise official GitHub raw-data tree and
checks the actual bytes against an independently obtained Git blob SHA-1. It binds
`FRBRWork` date/sitting to the debate title; resolves each `speech by` only through
a matching `TLCPerson` identifier and `from refersTo`; and returns explicit holds
for unresolved speakers or invalid review text. Review text is whitespace-normalized
for **private inspection only**, never passed off as an approved literal quote.
It cannot connect the senator to a public Person, synthesize video timing, perform
DP-305 excerpt clearance or assign publication authority. Source commit membership,
source-family rights, speaker-resolution and quotation signoff remain independent
operator responsibilities; SHA verification alone cannot authenticate a repository.

**Real source readback (Mac, read-only, no stored XML/media):** official
`Leg19/Atto00055187/resaula/01457617-ra.akn.xml`, commit beginning
`bfac144eb5c5`, blob SHA-1 beginning `bec30c067a1a`, 393,817 bytes;
`FRBRWork` identifies sitting **310, 2025-05-29**. The importer produced **121
private speech review candidates and 5 held turns**, no publicly attributable
speaker identity, quote authorization, or published statement. A new synthetic
regression suite exercises official-person mismatch, mutable branch/repository
impersonation, wrong sitting, XML DTD, exact blob replay/revision, and unknown
speaker holds. This is an authentic *source-format* smoke test on the Mac,
**not** the owner-approved source-family MiniPC canary required by AC-233.10.

To complete AC-233.10, an owner-approved Senato source-family/rights disposition
must explicitly scope the specific bulk-data reuse, then a bounded MiniPC run
must independently verify the pinned source/version and preserve operator review,
DP-305 rights and speaker approval. Until then DP-233 remains **IN PROGRESS**.

#### Canonical handoff and authentic isolated MiniPC readback — 2026-10-10

The separate `senato_akoma_corpus_handoff.py` now connects the parsed source to
the existing **canonical `ContentCaptureRecord`, `PassageRecord` and
`StatementCandidateRecord`** types without editing Studio/API code or issuing
a live DB write. Its `SenatoAkomaParser` plugs into the existing
`capture_content(parser=...)` seam **only after** the canonical discovery,
ingestion permit and rights checks. The offline preview is always
`QUARANTINED`, `RIGHTS_HOLD`, `rights_status=UNKNOWN`,
`retention_class=POLICY_PENDING` and `body_ref=None`, with each private
Statement Candidate `HELD`, no `speaker_person_id`, no inferred video time and
no provider/model extraction. Git commit, blob hash, source SHA-256 and CC BY
4.0 dataset license notice remain in the capture/parse receipts. The exact
byte-to-source, canonical text/spans and per-passage text hash are checked;
`verify_senato_handoff_roundtrip` rejects readback edits to selectors, text,
speaker attribution, rights and immutable source bytes.

The repeatable bounded command
`PYTHONPATH=poc python3 tools/senato_akoma_official_readonly_smoke.py --official-readonly-format-probe`
reads one authentic, pinned **official** XML document with zero credentials,
external paid calls or production DB/storage mutation, creates actual canonical
records, serializes them into a private temporary store and verifies readback
before automatic deletion. Both Mac and **MiniPC** were run using the same
source bytes (393,817), immutable commit
`bfac144eb5c54820971bc1020fece11aae56ec90`, Git blob
`bec30c067a1a79e8b377af483cfc4bfb44d13896` and SHA-256
`1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`.
Both produced 121 parsed private speech candidates, 5 unresolved original
speaker/text holds, then **104 bounded Passage records and 104 HELD Statement
Candidates**; the remaining 17 parsed speeches exceed canonical passage
limits, giving **22 total held/oversize speeches**. Both isolated persisted
readbacks passed and their temporary folders were deleted. Ten focused local
tests verify this bridge, tampering, replay, strict rights and identity;
Ruff passes. A baseline full suite before this follow-up passed 2,241 tests,
with deterministic benchmark 5/5; **that full suite predates the new bridge**.

This demonstrates real Senato format processing and MiniPC runtime only. It
**does not close AC-233.10** because no owner-approved parliamentary launch
source family / source-specific rights disposition exists and no production
source-family ingest, speaker approval or publication decision was authorized.

### 2026-10-10 — Immutable Senato license evidence, source approval unchanged

The canonical AKN adapter's license evidence URL previously pointed to the
**mutable** `master/LICENSE.MD`, even when XML source bytes were bound to a
40-character commit. It now points to the **same immutable commit**. The
repeatable official read-only smoke additionally checks that the exact commit
is accessible in the official GitHub repository and verifies the README's
`Licenza / CC BY 4.0` notice alongside the CC BY 4.0 text of `LICENSE.MD`
**at that same commit**. SHA-256 hashes and fixed URLs of both license-evidence
files are included in the metadata-only receipt; malformed/foreign commit,
missing/changed license or wrong-license text fail closed. These checks do not
create a private rights record, an operator decision, a verified speaker or
permission to publish excerpts.

**Observed official-source proof, Mac and MiniPC isolated:** commit
`bfac144eb5c54820971bc1020fece11aae56ec90`; XML Git blob
`bec30c067a1a79e8b377af483cfc4bfb44d13896` and source SHA-256
`1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`
(393,817 bytes); commit membership confirmed via official GitHub API;
README SHA-256 `cd01c53874c63df20d18ea151b3e5528af329dbc64ee573be4d480368f5a34dc`;
LICENSE SHA-256 `9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411`.
Actual isolated MiniPC execution produced 104 bounded Passages and
104 HELD Statement Candidates, 22 total held/oversize speeches, all
with `rights_status=UNKNOWN`, `RIGHTS_HOLD`, no Person attribution and no
public permit. Synthetic and negative focused tests **13/13 PASS** on
both Mac and MiniPC. No live database write or operational service restart.

The live MiniPC has **zero** private source-rights decisions and no
owner-approved Senato launch family under DP-703 B-703-03/04. The documented
CC BY 4.0 bulk-dataset license does not grant unrelated WebTV/media/ASR rights
or substitute for the required explicit source-family disposition. Therefore
**AC-233.10 remains unchecked and DP-233 stays IN PROGRESS**.
