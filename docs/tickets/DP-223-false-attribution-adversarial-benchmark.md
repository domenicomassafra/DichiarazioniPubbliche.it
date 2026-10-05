# DP-223 — False-attribution and fabricated-quote adversarial benchmark

Status: FUTURE
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

- [ ] **AC-223.1:** The fixture corpus is versioned, independently hand-labeled and stores
  expected source/span/person/wording-type/publication state without deriving expectations
  from implementation code.
- [ ] **AC-223.2:** Every required adversarial class has at least one positive and one
  negative/control example where meaningful.
- [ ] **AC-223.3:** The full public-projection path produces **zero** known false-person
  attributions and **zero** fabricated direct quotes.
- [ ] **AC-223.4:** A failure in quote, transcript, speaker, identity, context, rights or
  review provenance produces `HELD/OMITTED/UNRESOLVED`, never a guessed fallback.
- [ ] **AC-223.4A:** A material Finding assertion without a compatible DP-224 approved
  citation is omitted/held and cannot borrow unrelated Finding-level evidence membership.
- [ ] **AC-223.5:** Benchmark output reports separate counts, not one composite score.
- [ ] **AC-223.6:** Direct persistence tampering is included; helper-layer validation alone
  is insufficient.
- [ ] **AC-223.7:** Replay is deterministic and changing fixture/source hashes invalidates
  the expected approvals rather than reusing stale results.
- [ ] **AC-223.8:** DP-602 can run the benchmark in CI without network/provider calls.
- [ ] **AC-223.9:** DP-704 can rerun the same suite against the MiniPC release candidate and
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

Pending DP-216..DP-222 and implementation.
