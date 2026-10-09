# GOAL INFINITO — Wave 6: Candidate, matching and private triage consistency

Date: 2026-10-09 Europe/Rome. Source-only safety improvements.

## Grounded starting state

- Wave 5 source commit `82f4c2b877a8fedb2f9bcad4e9d6bb0868a1e98b`
  pushed by the sole integrator to `origin/main`.
- GitHub CI **run 37948202895: 11/11 SUCCESS** (Linux/macOS backends,
  repository, detached clone, web). The Wave 5 full Python suite was
  2,016/2,016 PASS, benchmark 5/5 PASS.
- Owner-provided prior handoff
  `docs/reviews/2026-10-09-goal-infinito-tutti-ticket.md` remains untracked
  and untouched. Two independent worker chats were reused for this wave.

## Changes and verification scope

1. DP-211/214: `private_candidate_batch` now rejects repeated JSON object
   keys and ambiguous Passage/Content/canonical-URL identities; direct and
   file-loaded candidate batches share strict bounds and manifest SHA-256
   validation. A second current-rights read must pass the full private
   capture authorization for the exact item, in addition to private model
   processing use; a substituted same-ID but wrong-locator record is refused.
2. DP-212: matching replay rederives ranked classes, method, scores,
   dispositions, cluster proposals and supporting/contradicting features
   from the exact fingerprint-bound inputs. Tampered persisted match decisions
   no longer count as a successful replay.
3. DP-417: private triage history reads max revision and total ledger count
   together, refuses missing revisions or short/mismatched pages, and checks
   a contiguous page sequence from the cursor without returning the private
   count in its response. An ephemeral local PostgreSQL test proves read
   refusal for a deliberately corrupted fixture ledger; production append-only
   triggers and database are untouched.

Worker-1 and worker-2 changed only their assigned source/test pairs; the sole
integrator owns matching, docs, Git and CI. Unit fixtures and ephemeral DB
tests prove source behavior, **not** production migration or a real source
Capture/Passage/Claim Candidate tracer. No provider call, capture, promotion,
publication, production migration or schema mutation is authorized.

## Release and external dependencies

Backlog remains **125 total, 86 DONE, 24 IN PROGRESS, 6 BLOCKED, 9 FUTURE;
39 open**. Launch gate remains **NO-GO/41 blockers** until independently
rechecked. `research:garlasco` in the authoritative MiniPC remains PAUSED,
with 18 historical included Content and 30 previous Garlasco Atomic Claims;
no genuine accepted Discovery Hit/Capture/Passage/Candidate pipeline has been
observed. DP-214.1/.2/.4-.8, DP-215.9 and DP-417.1-.4 remain open.

External requirements remain qualified Q-306 legal dispositions, a real
rights-processable source with provenance and private processing permission,
100-item/five-family corpus, provider credentials and budget where relevant,
manual assistive QA and owner release authority. Test fixtures cannot
substitute for these prerequisites.

## Final integration evidence

Combined focused Candidate/matching/Studio reader tests: **35/35 PASS**.
The first full-suite run identified one old authenticated Studio API test
fixture missing the new private `ledger_count`; production code correctly
rejected it (422). Updating only that fixture and asserting the count stays
redacted produced **8/8 focused PASS** (Studio API + reader).
The second complete Python run passed **2,025/2,025 PASS** in 112.94 seconds;
the restore drill and technical privacy schema inventory (100 tables,
1,248 fields) also passed. Deterministic benchmark 5/5 PASS, compileall,
repository ticket contract, launch NO-GO expectation and diff --check PASS.
Source commit SHA and corresponding GitHub CI must be recorded separately
after the actual Git operation/runner outcome; prior CI does not certify
Wave 6 until observed.
