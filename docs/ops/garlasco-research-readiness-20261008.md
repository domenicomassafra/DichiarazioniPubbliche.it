# DP-214/215 — MiniPC private corpus readiness and concrete work queue

**Date:** 2026-10-08. **Mode:** read-only SQL + repository-only unreviewed
URL manifest inspection. This is not source verification, copyright or
privacy approval, publication clearance, or evidence for a completed tracer.

## Reproducible private operator command

From the repository root, in the already-authorized PostgreSQL environment:

```bash
PGDATABASE=dichiarazioni_pubbliche PYTHONPATH=poc \
  python3 tools/report_research_pilot.py \
  --collection-id research:garlasco \
  --leads-file config/garlasco-public-discovery-leads.v1.json
```

Option `--include-ids` adds Content identifiers and per-item technical
blockers only; it never emits the source URLs, page titles, passage text,
private quotes, rights receipts, reviewer names or model credentials.
The default result is a bounded aggregate. Invalid collection IDs, incomplete
or changing membership counts, duplicate Content IDs, malformed counts,
inconsistent provenance and malformed leads fail closed. The script performs
no HTTP, provider call, migration or SQL write.

## Real MiniPC receipt

The current candidate was copied only under
`/tmp/dp-pilot-readiness-canary-20261008` and executed against the existing
MiniPC PostgreSQL `dichiarazioni_pubbliche` in read-only fashion.

| Observed field | Result |
|---|---:|
| Research Collection | research:garlasco, **PAUSED** |
| Existing included Content IDs | **18** |
| Missing toward proposed 100 logical items | **82** |
| Garlasco Atomic Claims baseline | **30/30** |
| Persisted Discovery Runs | **0** |
| Persisted unlinked Discovery Hits | **0** |
| Existing Contents with accepted valid Discovery provenance | **0/18** |
| Content with Capture authorization | **0/18** |
| Content with rights status CLEARED | **0/18** |
| Content with current matching private source rights record | **0/18** |
| Content with current privacy relevance record | **0/18** |
| Content with Capture | **0/18** |
| Content with Passage | **0/18** |
| Content with Statement or Claim Candidate | **0/18** |
| Required source families observed in accepted persisted discovery | **0/5** |
| Separate public URL candidate-only hints | **6** |
| Separate official source homepage locator, not case Content | **1** |
| Qualified capture/model rights proven from this report | **No** |
| Release status | **NO-GO** |

Candidate source URLs are from an *unreviewed, separate repository file*,
not a successful Discovery Run. They carry rights UNKNOWN, no capture
authorization and no inclusion in the accepted hundred. Those six do not
conflict with the correct database count of zero Discovery Runs/Hits.
The five missing families are DIRECT_INTERVIEW_ARTICLE, VIDEO_PODCAST,
OFFICIAL_PROCEDURAL, SECONDARY_REPORTING and DUPLICATE_DERIVATION.

Private snapshot fingerprint:
`f46058023c315dd560ac0e6a940c321f7e7b3ffe272440f7ac7609ec5a1e22cc`.
The fingerprint detects metadata drift in this operator inventory; it is
**not** an immutable capture receipt or approval signature.

## Work queue — earliest blockers, without fake closure

1. **Owner/legal:** actual Q-306/DP-307 decisions, source-specific privacy
   relevance, rights to fetch, retain, and separately send content to a
   named model. Do not derive these from approved text-attribution hashes.
2. **Source/provenance:** review six existing public leads, identify original
   source where possible, distinguish direct from mirror/derivation, and
   create versioned DP-209 manifests/runs with genuine valid Discovery Hits.
   Search for the remaining **82** real logical Content items across all
   five classes without substituting an institution homepage for a case
   document or introducing duplicates as new logical records.
3. **Collection:** only after actual owner decisions and cleared intake,
   reconsider `research:garlasco` PAUSED status and the 18 explicitly
   unauthorized memberships; do not silently update them.
4. **Capture:** use `tools/capture_research_batch.py` in its default
   no-network preflight, then the explicit operator-approved and
   source-authorized execution path for a minimal real Content subset.
   Validate exact Capture and Passage hashes and retain the body privately.
5. **Candidate:** separately approve model processing and budget. Use
   `tools/extract_research_candidates.py` preflight; a real, rights-cleared
   provider result must be persisted with receipts, not stubbed.
6. **Tracer/release:** advance only after duplicate/derivation review,
   clustering, Coverage Needs, 30-Claim linkage, 100-item proof, bounded
   replay, MiniPC read-back, privacy and publication isolation. DP-214/215
   remain IN PROGRESS; M7 remains NO-GO.

The report cannot mark a Content legally ready solely from one metadata
record. Only the individual, reread-first fail-closed operator preflight
validates exact subject scope, reviewer receipt, allowed use, unexpired
authority and current privacy relevance. A zero missing-prerequisite report
would **still not** authorize processing or publication.
