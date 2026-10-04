# DP-207 — Timestamped claim acceptance across real content

Status: READY  
Milestone: M2  
Depends on: DP-202 for the live extraction lane, or the approved deterministic fixture path; DP-205 is required only when the accepted real item is newly discovered through the full-source path

## Problem

The claim runtime can carry a model-provided `source_timestamp`, and the existing
ContentAudit fixture contains timestamped claims, but timestamp acceptance is not a
closed contract. A model can return a timestamp outside its window, a generic
`0:00`, or a timestamp that cannot be tied to a persisted segment. The current
benchmark loader also treats missing values as zero. That risks attaching a claim to
the wrong source location while still making extraction look successful.

Real content has three different clocks that must remain distinct: the content's
publication date, the media position of a transcript segment, and the observation
time of a provider receipt. This ticket accepts only claims whose media position is
reconstructible from immutable segment provenance.

## Outcome

Define and implement a fail-closed acceptance contract for atomic claims extracted
from timestamped canonical transcript segments. Every accepted claim must have:

- a stable `content_id`, transcript variant, window hash, and prompt/model version;
- one or more persisted canonical segment IDs;
- a validated, bounded `start_ms`/`end_ms` range and a parseable source timestamp;
- a source timestamp that maps to the claimed segments rather than being trusted as
  free-form model text;
- explicit numeric/sensitive and transcript-publication-blocked state; and
- an append-only/idempotent persistence result.

The deterministic fixture lane is the executable acceptance path for the existing
real Giuliani ContentAudit; after implementation it must pass without a provider call.
The live lane remains blocked until DP-202 completes; it must not call OmniRoute or
substitute a model in this ticket.

## Dependencies and authority

The governing sources are [PRODUCT.md](../../PRODUCT.md), [CONTEXT.md](../../CONTEXT.md),
[ARCHITECTURE.md](../../ARCHITECTURE.md), [PLAN.md](../../PLAN.md), and the
provenance rules in [ADR 0001](ADR-0001-provenance-first-fail-closed-publication.md)
and [ADR 0003](ADR-0003-non-biometric-speaker-attribution.md). The existing seams
are `poc/dichiarazioni_pubbliche/claim_runtime.py`,
`poc/dichiarazioni_pubbliche/claim_windows.py`, `poc/dichiarazioni_pubbliche/queue_runtime.py`,
`poc/dichiarazioni_pubbliche/content_audit.py`, `db/schema.v1.sql`,
`poc/content/raffagiulians-bollo-2026/content-audit.json`,
`poc/content/raffagiulians-bollo-2026/raw/transcript.json`, and the corresponding
tests under `tests/`.

DP-201 through DP-204 are externally blocked in the baseline. DP-207's fixture
path is intentionally independent of the blocked live provider; the live path
remains a later, explicitly gated lane.

## Scope

### 1. Timestamp provenance contract

Treat these values as separate fields and never overwrite one with another:

- `content_item.published_at`: the source's publication date, normalized to UTC;
- `transcript_segment.start_ms`/`end_ms`: the media range for a transcript
  candidate;
- `canonical_transcript_segment.start_ms`/`end_ms`: the range used by the claim
  window;
- `atomic_claim.temporal_scope.source_timestamp`: a bounded display/parse value;
  and
- provider receipt timestamps: observation/provider metadata, not media position.

For a claim, require at least one `claim_segment` edge. The edge set must resolve to
segments from the same content and the selected transcript variant. The union of
those segments must contain the parsed source timestamp, or the implementation must
mark the claim `TIMESTAMP_UNVERIFIED` and hold it from downstream material use.
Do not default a missing model timestamp to `0:00`.

The range must satisfy `0 <= start_ms <= end_ms`, remain within the known content
duration when duration is available, and be finite/bounded. A timestamp may use only
a documented precision tolerance (no more than 500 ms by default) to match a segment
boundary; the tolerance must be recorded in the claim metadata. If a claim spans
multiple segments, record the actual minimum start and maximum end rather than
inventing a point. A source timestamp is a pointer, not proof by itself.

### 2. Fixture acceptance path

Use the existing real-content fixture pair:

- `poc/content/raffagiulians-bollo-2026/raw/transcript.json` for timestamped
  transcript input; and
- `poc/content/raffagiulians-bollo-2026/content-audit.json` for the 84-segment,
  36-claim ground truth and inserted-clip annotation.

A deterministic fixture adapter may feed the existing claim contract without a
provider call. It must not treat the manually curated assessments as a model
result, copy evidence bodies into a queue payload, or publish a finding. The
fixture's claims are acceptance inputs, not an automatic truth source.

The existing `content_audit.py` validator remains the public fixture contract. It
must continue to reject unknown evidence IDs, missing secondary ASR for numeric
claims, incorrect inserted-clip speaker attribution, and aggregate person/creator
scores.

### 3. Persistence and replay

Persist accepted claims through the existing `Atomic Claim` and `Claim Segment`
ledger. The deterministic claim ID must include content identity, window/input
hash, prompt/model version, and the normalized claim fields. Replaying identical
input is a no-op for rows and edges. A changed transcript/window hash creates a new
claim candidate/version or explicit conflict; it must not silently broaden the
provenance of an existing claim.

Keep raw transcript text out of queue payloads. The worker may reconstruct a bounded
window from canonical segments at execution time, and every executed provider
operation must retain a provider receipt when the live lane is eventually enabled.

### 4. Sensitive and speaker holds

A claim that depends on a `TRANSCRIPT_UNCERTAIN` or otherwise
`publication_blocked` segment remains a candidate and cannot become a material
finding. Numeric-sensitive claims retain the existing secondary-ASR requirement.
An inserted clip must remain attributable to its own source/speaker candidate; a
claim spanning narrator and inserted-clip segments cannot receive a single guessed
speaker.

## Non-goals

- live OmniRoute, Groq, evidence, or publication calls in the fixture lane;
- changing the 36-claim ground truth or inventing new claims/evidence URLs;
- accepting a timestamp from a model without segment-level verification;
- treating publication date, media offset, and receipt time as interchangeable;
- automatic finding creation, approval, or publication;
- biometric speaker identification or voice matching; and
- a general semantic claim evaluator unrelated to timestamp acceptance.

## Acceptance criteria

- **AC-207.1 — Real fixture shape:** The Giuliani fixture loads with exactly 84
  classified segments and 36 atomic claims, and the existing audit validator returns
  no errors.
- **AC-207.2 — Segment mapping:** Every accepted fixture claim has at least one
  `claim_segment` edge; every edge belongs to the same content and selected
  transcript variant; the mapped range is non-negative, ordered, and within the
  444.84-second fixture duration.
- **AC-207.3 — Timestamp parsing:** Valid `M:SS` and `H:MM:SS[.mmm]` values map to
  the expected segment range. Missing, malformed, negative, out-of-window, or
  ambiguous timestamps are rejected or held, never silently converted to `0:00`.
- **AC-207.4 — Distinct clocks:** A receipt observation timestamp, content
  `published_at`, and media `start_ms`/`end_ms` survive persistence as distinct
  values; re-running with a changed publication date does not rewrite media
  provenance.
- **AC-207.5 — Real inserted clip:** Segment coverage from 414–434 seconds remains
  labeled as the inserted Giorgia Meloni clip rather than the narrator, and claims
  in that range cannot be assigned a guessed narrator identity.
- **AC-207.6 — Sensitive holds:** Numeric claims C07, C08, and C09 retain confirmed
  secondary-ASR provenance; a claim that depends on a blocked transcript segment is
  not treated as publishable.
- **AC-207.7 — Idempotence:** Replaying the same transcript/window/model/prompt
  produces the same claim IDs, no duplicate edges, and no new provider operation.
  Changing the input hash cannot mutate the old claim's segment set.
- **AC-207.8 — No publication side effect:** Fixture acceptance creates only claims,
  segment edges, and private receipts; it creates no approved evidence, finding
  publication, person score, or public raw transcript.
- **AC-207.9 — Failure behavior:** Provider absence, invalid schema, source drift,
  and database failure remain explicit blocked/deferred/error states; no fabricated
  timestamp or fallback verdict is accepted.
- **AC-207.10 — Regression:** Focused claim/window/transcript tests, the full test
  suite, deterministic benchmark, compile check, and `git diff --check` pass.

## Test-first seams

Use the public claim/parser and persistence seams:

1. `OmniRouteClaimClient` response parsing and a deterministic fixture extractor for
   schema and timestamp validation;
2. `ClaimWindow` segment/index/hash construction for range containment;
3. `QueueRuntimeStore.insert_atomic_claims()` and `claim_segment` persistence for
   replay and content identity;
4. `content_audit.validate_audit()` for the real fixture and inserted-clip safety;
   and
5. the worker claim-preparation/execution boundary for blocked provider and
   publication-hold behavior.

Add vertical red/green slices for valid mapping, missing timestamp, out-of-window
timestamp, segment drift, duplicate replay, changed hash, inserted clip, numeric
sensitive hold, and provider absence. Expected values should be independent literals
or the checked-in fixture contract, not recomputation of the implementation.

## Runtime proof

The fixture lane can be exercised without a provider call. First run:

```text
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
git diff --check
```

Then use an isolated PostgreSQL canary schema/database to prove content, transcript
variant, canonical segment, atomic claim, and claim-segment persistence/replay. Read
back the actual rows and assert the distinct publication/media/receipt timestamps,
36 claim IDs, 84 segment mappings, inserted-clip attribution, and zero residue after
cleanup.

The MiniPC deployment mirror must run the same fixture and database canary and
retain a receipt with the mirror hash, fixture hashes, schema/migration result,
row counts, replay counts, and test output. A Mac-only fixture pass proves the
parser, not the runtime. Live claim extraction remains unproved until DP-202 and is
not part of this ticket's fixture completion.

## Blocked conditions

Keep the live lane blocked and the ticket incomplete for runtime extraction if:

- DP-202 has not passed on the official route;
- the canonical transcript lacks segment IDs or bounded start/end ranges;
- the source timestamp cannot be mapped to persisted segments;
- the transcript variant/hash changes during execution;
- speaker provenance for every claim segment is missing or ambiguous;
- the numeric-sensitive secondary-ASR requirement is unmet; or
- the database cannot persist/replay claims atomically.

The existing deterministic fixture may still be accepted for the fixture lane if it
meets AC-207.1 through AC-207.10. A provider failure must not be converted into a
successful extraction or a fabricated timestamp.

## Documentation, data, and migration impact

- Update `docs/23-claim-extraction-benchmark-and-pulp-scaffold.md` with the
  timestamp-acceptance fixture result and the explicit live blocker.
- Keep the existing `atomic_claim`, `claim_segment`, transcript, and receipt schema;
  add only a versioned metadata field or ordered migration if timestamp precision or
  validation status cannot be represented without ambiguity.
- Do not add public transcript text, raw queue bodies, or a public timestamp field
  before the public schema contract is settled.
- No change to evidence approval, verification, or publication tables is in scope.

## Completion receipt

To be filled only after implementation and proof:

- implementation commit and MiniPC mirror hash:
- fixture and transcript SHA-256 values:
- accepted/rejected/held claim and segment counts:
- timestamp-clock and replay proof:
- provider/live-lane blocker status:
- focused/full tests, benchmark, and `git diff --check`:
- MiniPC database canary receipt and residual risks:
