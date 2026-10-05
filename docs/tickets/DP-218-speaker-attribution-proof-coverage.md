# DP-218 — Speaker-attribution proof coverage for the exact quoted/claimed span

Status: READY
Milestone: M2 — Live pipeline readiness and source coverage
Depends on: DP-114, DP-207; ADR 0003; coordinate with DP-216 and DP-217

## Problem

The repository already has non-biometric `speaker_identity_candidate` records and review,
but the publication risk is not merely "do we have a candidate for this person?" The
proof must cover the **exact source span being attributed** and its method must actually be
capable of establishing identity in that source context.

Examples of dangerous shortcuts include assigning an entire interview to the guest even
when the host, clips and voice-over are present, inheriting the account owner's identity
to every embedded clip, or treating diarization cluster labels as real-world identity.

## Outcome

Strengthen the speaker-attribution contract so every public attributed span has explicit,
reviewed, non-biometric identity evidence whose temporal/source coverage contains the
entire quoted/claimed span. Ambiguity produces `HOLD`, never a guessed person.

## Scope

- Reuse `speaker_identity_candidate`, review ledger and DP-114 Person resolution.
- Version attribution methods and document what each can establish. Candidate methods may
  include reviewed official transcript labels, official event/program metadata, source
  metadata for a genuinely single-speaker source, reviewed moderator introduction,
  reviewed on-screen identification, or manual editorial mapping with a source receipt.
- Explicitly prohibit `DIARIZATION_CLUSTER`, face match, voiceprint, model guess, account
  owner alone for embedded media, or name similarity from becoming identity proof.
- Require interval containment: every Claim Segment / DP-216 verbatim span must be covered
  by compatible approved attribution evidence for the same Person and Content/version.
- Multi-speaker, inserted-clip, dub/voice-over and off-camera cases require separate
  attribution records; identity may not bleed across segment boundaries.
- Attribution review records supporting and contradicting provenance and can be
  superseded without destroying history.

## Non-goals

- No biometric identity.
- No political/person reliability score.
- No assumption that appearing visually on screen means the visible person is speaking.
- No publication based on a numeric confidence threshold.

## Acceptance criteria

- [ ] **AC-218.1:** Every public media attribution has approved evidence covering the
  exact full span; partial coverage blocks the claim/quote.
- [ ] **AC-218.2:** Diarization labels may segment audio but cannot populate a real Person
  identity without a separately approved attribution method.
- [ ] **AC-218.3:** Host + guest + inserted clip + voice-over fixtures cannot inherit one
  speaker identity across boundaries.
- [ ] **AC-218.4:** Account-owner/source-owner metadata alone cannot attribute an embedded
  third-party clip or quoted audio.
- [ ] **AC-218.5:** Conflicting identity evidence becomes `UNRESOLVED`/held; model score,
  majority vote or source prestige cannot silently resolve it.
- [ ] **AC-218.6:** Same-name/different-person evidence must resolve through DP-114 stable
  identity, not display-name equality.
- [ ] **AC-218.7:** Changed source/transcript/segment boundaries stale affected approvals.
- [ ] **AC-218.8:** Public projection exposes only bounded attribution method/provenance
  metadata and never biometric/template data or private reviewer notes.
- [ ] **AC-218.9:** Tamper tests prove that directly changing `speaker_person_id` or
  candidate status without the matching review/provenance cannot create public output.
- [ ] **AC-218.10:** Full suite, benchmark, schema replay and MiniPC canary pass.

## Validation / proof

Create deterministic multi-speaker fixtures including narrator, guest, embedded clip,
off-screen speaker and ambiguous label. Exercise direct-database/status tampering as well
as normal APIs. Run standard checks plus MiniPC read-back of interval coverage and review
events.

## Documentation, data, and migration impact

Update ADR 0003 only if the accepted method taxonomy materially changes its decision.
Otherwise update `CONTEXT.md`/`ARCHITECTURE.md` and the existing speaker provenance docs.
Prefer additive method/version fields and compatibility with existing approved candidates.

## Completion receipt

Pending implementation and MiniPC proof.
