# DP-208 — Diarization benchmark and go/no-go decision

Status: FUTURE (blocked on DP-204 and real benchmark/runtime gates)
Milestone: M2  
Depends on: DP-204, DP-207, M0, and ADR 0003

## Problem

The real Giuliani ContentAudit contains an inserted Giorgia Meloni clip inside a
narrated video, and the project already requires speaker provenance for every claim
segment. The current pipeline can preserve manual or source-provided speaker labels,
but it has no reproducible evidence for whether automatic diarization would improve
speaker-turn boundaries. Adopting a model based on a demo or a model leaderboard
would risk misattributing a public statement and could accidentally turn speaker
separation into biometric identity matching.

This ticket is a benchmark and decision gate, not an adoption ticket.

## Outcome

Produce a bounded, reproducible Italian diarization benchmark and an explicit
`GO`, `GO_BOUNDED`, or `NO_GO` decision. A successful benchmark may recommend a
future adapter for anonymous speaker-turn segmentation; it may not resolve a
`Person`, publish a speaker identity, or use face/voice biometrics. The decision
must state what evidence was sufficient, what remained uncertain, and what would
change the decision.

## Dependencies and authority

The governing rules are [PRODUCT.md](../../PRODUCT.md), [CONTEXT.md](../../CONTEXT.md),
[ARCHITECTURE.md](../../ARCHITECTURE.md), [PLAN.md](../../PLAN.md), and
[ADR 0003](ADR-0003-non-biometric-speaker-attribution.md). Relevant existing
seams are `poc/dichiarazioni_pubbliche/transcript_contract.py`,
`poc/dichiarazioni_pubbliche/platform_transcript.py`,
`poc/dichiarazioni_pubbliche/speaker_runtime.py`,
`poc/content/raffagiulians-bollo-2026/content-audit.json`, and the tests under
`tests/`.

DP-204 must first establish the approved remote-ASR/fallback path and receipt
contract. DP-207 has established the timestamped segment/claim acceptance seam, but
DP-204 remains blocked. Until the remaining dependency and real benchmark gates are
complete, this ticket remains `FUTURE/BLOCKED`; no benchmark result may be fabricated
from an unproven transcript.

## Scope

### 1. Bounded sample and reference

Use already authorized real-content material and the existing checked-in audit as
the first benchmark set. The minimum set is:

- the full 444.84-second Giuliani fixture, including the 414–434-second inserted
  clip;
- at least two bounded excerpts from the existing Pulp long-form content or another
  already authorized transcript with a clear speaker turn; and
- at least one additional excerpt only if it is already approved under the source
  policy.

The reference set must contain at least two anonymous speakers, at least 10 minutes
of reviewed audio/transcript, and at least one speaker change, one overlap/turn
boundary, and one inserted or voice-over interval. Do not add a new political
source merely to improve the benchmark.

Create private, versioned reference annotations with anonymous labels such as
`TURN_00` and `TURN_01`, start/end milliseconds, and notes for inserted clips. The
reference may say "narrator" or "inserted clip" as a source role, but it must not
contain a biometric identity claim. Keep audio, full transcript, and reference
annotations outside Git in the private artifact store.

### 2. Candidate engines and execution boundary

Compare only explicitly approved, locally runnable candidates:

- a deterministic baseline using source/platform labels or the existing canonical
  segments;
- a candidate such as `pyannote.audio` only after model/license/cache approval; and
- a candidate such as `diarize` only as a benchmark candidate after its maintenance,
  license, and resource checks.

Do not download a model, call a hosted diarization service, use a new credential, or
train a model as an implicit part of this ticket. The benchmark harness must accept
an injected engine adapter so tests can use deterministic fixtures and can measure
boundaries without network access.

Each result must record engine ID/version, model ID/hash, configuration, input hash,
runtime, elapsed time, peak RSS, and the raw output reference/hash. Do not store
voice embeddings, face features, or an inferred person ID.

### 3. Metrics and pre-registered decision rule

Report diarization error rate (DER), missed speech, false alarm, confusion,
speaker-change precision/recall, boundary error, and overlap/inserted-clip detection.
Use a pre-registered 250 ms boundary collar and report results with and without the
collar. Evaluate only anonymous turn segmentation; do not score identity accuracy.

Use these decision gates:

- **GO:** all required samples have complete start/end provenance; DER is at most
  0.20 or improves by at least 20% relative to the baseline; speaker-change F1 is at
  least 0.90; the inserted clip is never merged into the narrator turn; and the
  MiniPC resource/cache budget and license are acceptable.
- **GO_BOUNDED:** ordinary turns pass, but sensitive numeric/negation spans or the
  inserted clip remain uncertain. Diarization may be retained as a candidate hint,
  while the affected segments stay `POLICY_HOLD` and require the existing
  non-biometric review path.
- **NO_GO:** a critical boundary is missed, provenance is incomplete, identity
  information is required, the result depends on an unapproved provider/model, or
  resource cost is not justified. Keep the existing source/manual-label path.

The thresholds and sample set must be written into the benchmark receipt before the
run. A result below a threshold is not a reason to relax the threshold within the
same run.

### 4. Safe integration decision

If the decision is `GO` or `GO_BOUNDED`, create a follow-up implementation ticket for
an adapter behind the existing transcript/speaker seam. The adapter may emit
anonymous `speaker_label`/turn ranges with engine/version provenance. It may create
a `SpeakerIdentityCandidate` only with an allowed non-biometric method such as
`SOURCE_METADATA`, `TRANSCRIPT_LABEL`, `PLATFORM_CREDIT`, `OFFICIAL_RECORD`, or
`MANUAL_REVIEW`, followed by the existing approval ledger. It may never directly
write a public `speaker_person_id`.

This ticket itself does not require a production schema migration or model download.
A benchmark receipt is sufficient to close it with a decision.

## Non-goals

- face recognition, voiceprint matching, speaker embeddings, or biometric identity;
- selecting or ranking political sources or people;
- automatic approval of a speaker candidate;
- treating a diarization label as a person's identity;
- downloading a large model or adding hosted-provider infrastructure;
- changing transcript text, claim extraction, evidence, verification, or publication
  policy;
- using future evidence or a future transcript to retroactively settle an earlier
  attribution; and
- publishing raw audio, full transcripts, or internal reference annotations.

## Acceptance criteria

- **AC-208.1 — Reference set:** The benchmark manifest identifies at least 10
  minutes of already authorized content, two anonymous speakers, a speaker change,
  overlap/turn boundary, and the 414–434-second inserted clip, with hashes and
  rights/retention classification.
- **AC-208.2 — Reproducibility:** Two runs with the same engine, model, config,
  input hash, and MiniPC image produce the same normalized turn intervals and the
  same metrics, subject only to a recorded runtime tolerance.
- **AC-208.3 — Complete timestamps:** Every candidate turn has finite,
  non-negative, ordered start/end milliseconds, a source timebase, and a reference
  to the input hash. Missing or drifted timestamps fail the run rather than being
  filled with zero.
- **AC-208.4 — Baseline comparison:** Baseline and candidate DER, speaker-change
  precision/recall, boundary error, missed speech, false alarm, and confusion are
  reported with the pre-registered collar and sample-level breakdown.
- **AC-208.5 — Critical boundary:** The inserted clip is detected as a separate
  speaker/turn interval; merging it with the narrator is an automatic `NO_GO` for
  publication-grade use.
- **AC-208.6 — Sensitive-span safety:** A diarization error around a numeric,
  negation, date, name, or direct-quote span causes a hold/unknown result; it does
  not cause a new claim, a guessed identity, or a publication decision.
- **AC-208.7 — Resource and license gate:** The receipt records peak RSS, elapsed
  time, model/cache size, license/entitlement decision, and the MiniPC budget
  check. Unapproved downloads or provider calls are not run.
- **AC-208.8 — No identity leakage:** Benchmark inputs, outputs, receipts, and
  follow-up recommendations contain no voiceprint, face feature, inferred person
  ID, or aggregate person score.
- **AC-208.9 — Decision:** A reviewer records exactly one of `GO`, `GO_BOUNDED`, or
  `NO_GO`, with rationale, failed gates, and a follow-up owner/condition. No
  production adoption is implied by a positive score alone.
- **AC-208.10 — Regression:** Focused metric/safety tests, the full suite,
  deterministic benchmark, compile check, and `git diff --check` pass.

## Test-first seams

Test the benchmark contract before running a model:

1. reference-annotation parsing and timebase normalization;
2. interval overlap, boundary, and DER metric functions with hand-worked literals;
3. the injected engine adapter and deterministic fixture runner;
4. sensitive-span and inserted-clip hold behavior;
5. receipt serialization, redaction, and hash/version stability; and
6. the decision gate, including one pass, one bounded-pass, and one no-go fixture.

Use red/green vertical slices: interval validation, metric correctness, critical
clip boundary, sensitive hold, resource receipt, and decision classification. Mock
only external model/runtime boundaries; do not mock the metric or policy code under
test.

## Runtime proof

No benchmark run is valid until DP-204 and DP-207 are closed. On the MiniPC:

1. synchronize the benchmark harness and approved private inputs to
   `/home/udodo/src/DichiarazioniPubbliche.it` or the owner-approved private artifact
   root; do not put media in Git;
2. run the focused benchmark tests and the standard repository checks:

   ```text
   python3 -m compileall -q poc tests
   PYTHONPATH=poc python3 -m unittest discover -s tests -v
   PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
   git diff --check
   ```

3. execute the pre-registered sample set with no network provider call, recording
   input/model/config hashes, engine receipts, elapsed time, peak RSS, and per-sample
   metrics;
4. inspect the resulting intervals, especially the inserted clip and sensitive
   numeric/negation spans, and read the actual decision receipt;
5. verify private artifact permissions, deletion/retention behavior, and that the
   public projection contains no audio, full transcript, reference annotation, or
   identity data; and
6. record the MiniPC mirror hash, benchmark receipt path, decision, failed gates,
   and follow-up ticket if any.

The Mac may validate the metric implementation and fixtures, but it cannot establish
MiniPC resource, model-cache, or runtime behavior.

## Blocked conditions

Remain `FUTURE/BLOCKED` if any of these are true:

- DP-204 has not passed its bounded live-ASR/fallback acceptance;
- DP-207 has not passed timestamped segment/claim acceptance;
- no approved, rights-cleared reference annotation exists;
- a candidate model or adapter has no license/entitlement decision;
- the benchmark would require a credential, hosted call, unapproved download, or
  unbounded media processing;
- the MiniPC cannot run the candidate within the recorded resource budget; or
- the owner has not named a reviewer for the go/no-go decision.

A failed benchmark is a valid `NO_GO` result, not a reason to bypass a dependency or
claim a runtime completion. `GO_BOUNDED` never authorizes publication without the
existing speaker approval and fail-closed gates.

## Documentation, data, and migration impact

- Add a private benchmark manifest/receipt under the owner-approved runtime artifact
  store and a concise, content-free decision in this ticket's completion section.
- Update `docs/17-transcription-quality-and-routing.md` and
  `docs/27-speaker-provenance-public-projection-v1.md` only after the decision is
  recorded; do not add an ADR that implies adoption before the evidence exists.
- No public schema or operational transcript migration is required for the
  benchmark-only slice. A `GO` follow-up may propose an additive diarization run/turn
  representation, but it must preserve the existing speaker candidate/review ledger.
- No model weights, audio, full transcript, or identity data belong in Git.

## Completion receipt

To be filled only after the benchmark decision and MiniPC proof:

- implementation commit and MiniPC mirror hash:
- reference/input/model/config hashes and license decisions:
- sample count, duration, speaker/turn/overlap composition:
- baseline and candidate metrics with collar and per-sample breakdown:
- inserted-clip and sensitive-span results:
- peak RSS, elapsed time, cache size, and budget outcome:
- final `GO`/`GO_BOUNDED`/`NO_GO` decision, rationale, and follow-up owner:
- focused/full tests, benchmark, and `git diff --check`:
- residual blockers and private artifact retention location:

### Local test-first harness receipt — 2026-10-05

The benchmark methodology is now executable in
`poc/dichiarazioni_pubbliche/diarization_benchmark.py` without a model, provider, network
call, audio artifact or identity feature. It validates anonymous `TURN_*` intervals and
input hashes/timebase, computes DER components separately (miss/false alarm/confusion),
speaker-change precision/recall/F1 and boundary error with the pre-registered 250 ms collar,
checks the inserted-clip separation and sensitive-span hold behavior, and evaluates the
pre-registered `GO`/`GO_BOUNDED`/`NO_GO` thresholds without a composite trust score.

This does **not** close AC-208.1..10 or record a benchmark decision: DP-204 remains blocked,
the ≥10 minute reviewed private reference set does not yet exist, no candidate engine/license
has been approved, and MiniPC resource/model-cache proof has not been run. The local harness
only freezes the test-first metric/policy seam required by this ticket before real results are
available.

## Checkpoint 2026-10-10 — future activation boundary

Keep FUTURE. Start only after an authorized DP-204 audio/ASR receipt plus labeled reference with reliable speaker-turn boundaries. Test non-biometric diarization with false-attribution guard, compare against manual baseline and record an explicit go/no-go; a fixture score cannot close it.
