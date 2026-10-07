# DP-223 — False-attribution and fabricated-quote adversarial benchmark

Status: DONE
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-216..DP-222, DP-224; coordinate with DP-602 and DP-704

## Problem

Individual happy-path tests do not answer the safety question that matters most for this
product: **can the pipeline ever publicly attribute words to the wrong person or publish
words that are not supported by the source?**

This failure class deserves its own versioned benchmark with explicit zero-tolerance
false-publication metrics. Recall is useful, but under-publication is preferable to one
known false attribution.

## Outcome

Build a deterministic adversarial corpus and release gate covering quote integrity,
speaker identity, context, reported speech, translation and source drift. The benchmark
measures public-output behavior, not only candidate extraction accuracy.

## Required adversarial cases

At minimum include:

- two different people with the same name;
- host/interviewer and guest alternating rapidly;
- narrator reading another person's quote;
- politician quoting an opponent;
- old embedded clip inside current commentary;
- verified account reposting third-party media;
- dropped negation, changed number/date/name and legal-term ASR errors;
- overlapping speech and off-camera speaker;
- sentence cut before/after a qualification;
- yes/no answer separated from its question;
- conditional/hypothetical statement flattened into assertion;
- paraphrase/headline represented as a quote;
- translation that changes modality/negation/number;
- syndicated articles repeating one upstream quote;
- source page updated after capture;
- stale speaker/context/quote review after source-version change;
- Finding rationale assertion backed only by unrelated/context/contradictory evidence;
- direct database/status/person/quote tampering;
- rights hold or unavailable source body;
- model output containing a plausible sentence absent from every source span.

## Metrics and gate

The primary release metric is:

`known false public attribution or fabricated public quote = 0`.

Also record:

- correct public occurrences;
- correct holds/abstentions;
- false holds;
- unresolved cases;
- quote-span exact-match rate;
- speaker-span coverage rate;
- context-review escape count;
- stale-provenance escape count.

Do not combine these into a single trust/quality score. A release cannot trade one false
public attribution for higher recall.

## Acceptance criteria

- [x] **AC-223.1:** The fixture corpus is versioned, independently hand-labeled and stores
  expected source/span/person/wording-type/publication state without deriving expectations
  from implementation code.
- [x] **AC-223.2:** Every required adversarial class has at least one positive and one
  negative/control example where meaningful.
- [x] **AC-223.3:** The full public-projection path produces **zero** known false-person
  attributions and **zero** fabricated direct quotes.
- [x] **AC-223.4:** A failure in quote, transcript, speaker, identity, context, rights or
  review provenance produces `HELD/OMITTED/UNRESOLVED`, never a guessed fallback.
- [x] **AC-223.4A:** A material Finding assertion without a compatible DP-224 approved
  citation is omitted/held and cannot borrow unrelated Finding-level evidence membership.
- [x] **AC-223.5:** Benchmark output reports separate counts, not one composite score.
- [x] **AC-223.6:** Direct persistence tampering is included; helper-layer validation alone
  is insufficient.
- [x] **AC-223.7:** Replay is deterministic and changing fixture/source hashes invalidates
  the expected approvals rather than reusing stale results.
- [x] **AC-223.8:** DP-602 can run the benchmark in CI without network/provider calls.
- [x] **AC-223.9:** DP-704 can rerun the same suite against the MiniPC release candidate and
  attach an actual projection/read-back receipt.

## Validation / proof

Provide a dedicated command/test entrypoint plus the standard full suite, deterministic
verification benchmark, `git diff --check`, and MiniPC release-candidate run. The fixture
corpus must use synthetic/cleared material or bounded metadata so it does not create a new
copyright/privacy risk.

## Documentation, data, and migration impact

Add fixture provenance/licensing rows to DP-603 inventory. Do not add raw third-party media
to Git solely for this benchmark. DP-602 owns CI wiring; DP-704 owns launch rehearsal.

## Completion receipt

2026-10-05 local/offline benchmark slice:

- `tests/fixtures/false-attribution-adversarial-v1.json` is a fully synthetic, versioned,
  hand-labeled corpus with 59 cases covering all required classes plus dedicated
  challenger-only adverse/control pair. Every required class has an
  adversarial example plus a positive/control example; the sensitive ASR, translation,
  citation and direct status/person/quote-tamper classes carry additional variants.
- `poc/dichiarazioni_pubbliche/false_attribution_benchmark.py` is a pure offline harness and
  CLI. It composes the existing quote binding, context integrity, wording/translation,
  public attribution, citation assurance, original-source resolution and excerpt/rights
  gates rather than implementing a second publication policy.
- The release metric remains two separate zero-tolerance counts. The current local run is 59/59
  cases passing with `known_false_public_attribution=0`, `fabricated_public_quote=0`,
  `false_holds=0`, `context_review_escape_count=0` and
  `stale_provenance_escape_count=0`. Other quality/coverage metrics remain separate.
- Fixture digest plus per-source/span hashes bind the authored approvals. Replay returns
  identical structured output; tests prove that source-text or expected-approval hash drift
  invalidates the fixture instead of reusing the prior expectation.
- `python -m dichiarazioni_pubbliche.false_attribution_benchmark` is the dedicated command
  entrypoint. The focused test runs it with network creation denied, proving the DP-602 CI
  seam requires neither network nor a provider.
- `python3 tools/check_contributor_acceptance.py`, the standard deterministic contributor/
  local release acceptance entrypoint, now runs that same benchmark CLI unconditionally.
  The CLI is the gate authority: a non-passing release gate, including either non-zero
  zero-tolerance metric, exits non-zero and fails the overall acceptance path.
- The fixture is registered as project-authored synthetic material in the DP-603 licensing
  inventory/generator.

2026-10-06 local persistence-tamper slice:

- `tests/test_public_projection_postgres_tamper.py` starts an isolated temporary PostgreSQL
  cluster, creates a disposable `dp223_tamper` database, loads the real `db/schema.v1.sql`
  contract and seeds one fully synthetic valid dossier through persisted rows.
- The acceptance path is the production projection read boundary itself:
  `PublicProjectionStore.projectable_findings()` followed by `build_public_projection()`.
  The baseline persisted dossier projects successfully before any tamper.
- Separate direct SQL updates then tamper Finding publication status, Claim speaker Person,
  persisted quote hash, approved text provenance and the DP-224 material-assertion citation
  relation. Every case produces zero public dossiers; the quote-hash case deliberately
  survives the SQL row selection and is rejected by projection sanitization, proving the
  second fail-closed boundary as well.
- The current local persistence suite is 10/10: in addition to the original six cases it
  directly tampers persisted `speech_mode` and context-review state and proves both are
  rejected before public attribution. These tests pass using only the disposable local
  cluster. No production or MiniPC database is contacted.

At this 2026-10-06 slice, AC-223.3/.9 remained open. The combined deterministic gate closed
AC-223.4: the 59-case
hand-labelled suite exercises quote, transcript, speaker, identity, context, rights,
source-drift and review-provenance failures with every adverse case ending
`HELD/OMITTED/UNRESOLVED`, while the persisted production-boundary suite exercises direct
SQL tampering and the DP-305 public-serializer boundary. The persisted suite also proves AC-223.4A:
changing the exact assertion citation relation from `SUPPORTS` to incompatible `CONTEXT`
removes the dossier instead of borrowing unrelated Finding-level membership. This slice does not
claim the full adversarial corpus through the public projection or a MiniPC
projection/read-back receipt.

2026-10-06 isolated MiniPC persistence canary:

- The current `poc/dichiarazioni_pubbliche` package, PostgreSQL tamper test and
  `db/schema.v1.sql` were copied only to a temporary `/tmp` bundle on the MiniPC. No deploy
  mirror, provider path, production database credential or production database service was
  used or inspected.
- The MiniPC provides PostgreSQL 18.6. The acceptance test now gives its ephemeral server a
  private Unix-socket directory under the test temporary root, allowing the same unprivileged
  test to run on Linux without relying on `/var/run/postgresql`.
- With production PostgreSQL environment variables explicitly removed, the then-current
  `tests.test_public_projection_postgres_tamper` suite passed 6/6 against its own temporary
  PostgreSQL cluster/database. The temporary bundle and cluster were removed afterward.
- This is isolated MiniPC persistence proof for AC-223.6. It does **not** satisfy AC-223.9:
  that criterion still requires DP-704 to rerun the same release suite against the MiniPC
  release candidate and attach an actual projection/read-back receipt.

2026-10-06 final evidence-core run reconstructs `df8cdcc` plus only the evidence-core patch
in an isolated candidate. `compileall`, **1765/1765** unittests, deterministic benchmark
**5/5**, DP-223 **59/59** and `git diff --check` pass; PostgreSQL 17.11 applies/replays all
**41/41** migrations. The production-boundary tamper test now also seeds a machine ASR
variant whose direct-quote authority comes only from a persisted current human-verbatim
review; changing the source-segment bytes immediately removes the dossier until the exact
reviewed bytes return.

That exact candidate was copied only to a temporary MiniPC directory and run with production
database variables removed. On Python 3.14.4/PostgreSQL 18.6, **213/213** focused
evidence-core tests pass with no skips using temporary local clusters; benchmark **5/5** and
DP-223 **59/59** also pass. This current canary supersedes the older 6-test MiniPC receipt
for deterministic evidence-core behavior, but it is deliberately **not** AC-223.9: no
release candidate was deployed or read back through DP-704.

2026-10-07 AC-223.3 persisted full-corpus closure:

- `tests.test_public_projection_postgres_tamper` now replays all **59** authored cases through
  a disposable PostgreSQL 17.11 database and the real `PublicProjectionStore ->
  build_public_projection -> write_public_bundle` final-output path. The harness persists
  each case's **actual** production-gate result plus the exact authored source/span/person
  identifiers; it never copies the authored expected publication label into PostgreSQL to
  force a pass.
- All 59 case records are present in persistence. The final public projection contains **21**
  dossiers and the serializer writes exactly 21 JSON, 21 JSON-LD and 21 HTML claim outputs,
  plus the projection JSON/JSON-LD/N-Triples/linked-data receipt. Every emitted speaker ID
  matches the hand-labelled person and every direct-quote source hash matches the authored
  span hash: `known_false_public_attribution=0`, `fabricated_public_quote=0` at the serialized
  boundary.
- Three positive transcript-verbatim controls are deliberately under-published at the final
  boundary because the hand-labelled corpus contains no `person_id` for those cases. The
  replay keeps `speaker_person_id=NULL` and therefore records three false holds rather than
  inventing an attribution solely to make the acceptance green. This is consistent with the
  DP-223 zero-tolerance rule that under-publication is preferable to one known false
  attribution.
- Focused validation is **17/17** for `tests.test_false_attribution_benchmark` plus
  `tests.test_public_projection_postgres_tamper`; the dedicated deterministic corpus remains
  **59/59** with zero false-attribution/fabricated-quote counts, and `git diff --check` passes.

AC-223.9 remains open and DP-704-bound. This disposable local persistence/serializer receipt
is not a MiniPC release-candidate deployment or projection/read-back receipt.

### DP-704 attribution-integrity sub-rehearsal — 2026-10-07

The CI-green candidate `cdad363e8dff97b1465891e47f00b51fbbbadb0d` was materialized
from Git into an isolated `/tmp` workspace on the authoritative MiniPC `udodo`. With the
PostgreSQL 18 binary directory supplied explicitly from `pg_config --bindir`, the exact
DP-223 benchmark plus persisted public-projection/tamper suite ran against disposable
PostgreSQL: **17/17 PASS**. The full authored corpus again reported **59/59 PASS**,
`known_false_public_attribution=0`, `fabricated_public_quote=0`; the persisted replay
executed `PublicProjectionStore -> build_public_projection -> write_public_bundle`, including
the 59-case persisted boundary and serialized bundle read-back. The isolated candidate
workspace and ephemeral database were removed after the run.

This closes AC-223.9 and therefore DP-223. It is deliberately only the DP-704
attribution-integrity sub-gate: DP-704 itself remains FUTURE/BLOCKED because its full
source-to-correction rehearsal, provider/legal/public-contract prerequisites, rollback
receipt and owner disposition are still missing. No production database or public dataset
was mutated to obtain this pass.
