# GOAL INFINITO — Wave 12: official excerpt and private capture metadata

Source baseline: `4f0812e` (Wave 11 GitHub CI
`37975948272` **SUCCESS**). No production deploy or public release.
Original untracked owner handoff and legacy ContentAuditClient draft
are intentionally excluded from this wave.

## Reproduced RED → GREEN

**DP-233:** Official source-family execution previously checked
source URL/hash, transcript/version, statement ID and video timing
but not that the submitted excerpt was contained in the exact official
statement. With synthetically CLEARED rights, invented or
wrong-speaker text incorrectly passed as ALLOWED. The executor now
demands a nonempty literal contiguous substring of the current official
statement before DP-305 eligibility; tests cover whitespace/case
alterations, disjoint phrases, NEW/REPLAY/AMENDED and permission holds.
No real Camera/Senato rights were assigned.

**DP-419:** The metadata-only inspector could claim archive success
with no completion receipt/time or a purged body on an internally
contradictory Capture status. It now enforces the canonical
`ContentCaptureRecord` archive/purge prerequisites without exposing
private receipt bodies or source URLs. Nine adversarial variations
were RED, then GREEN, while valid purged versions still display.

**DP-215:** `EvidenceItem` and `evidence_item_from_row` previously
defaulted missing or whitespace-only observation status to `APPROVED`,
allowing an unreviewed known-source observation to count towards
requirements. The adapter now defaults to `UNREVIEWED`; assessment
excludes and records `EVIDENCE_NOT_APPROVED`. An explicitly approved
SQL observation still qualifies. No source rights were granted.

Focused source-family/inspector/Studio API suite:
`PYTHONPATH=poc python3 -m unittest
tests.test_parliamentary_source_family_execution
tests.test_studio_capture_inspector tests.test_studio_local_api -q`
**32/32 PASS**, compileall and diff check PASS. Final integrated
suite, deterministic benchmark, commit SHA and new CI are required
before claiming this wave published.

Additional DP-215 regression coverage brought the three-lane
focused aggregate to **46/46 PASS**, before the global suite.

## Frozen source-wide validation

- `PYTHONPATH=poc python3 -m unittest discover -s tests -q`:
  **2083/2083 PASS** (142.381 s). Expected fixture HTTP/socket
  `ResourceWarning` observations were not test failures.
- Restore drill **PASS**, 100 tables/1,248 recorded fields;
  deterministic verification benchmark **5/5 PASS**.
- `python3 tools/check_repository_contract.py --only tickets`:
  **PASS**. `compileall -q poc tests` and `git diff --check`:
  **PASS**.
- `PYTHONPATH=poc python3 tools/check_launch_preflight.py
  --expect-no-go`: **NO-GO/41**; receipt SHA-256 unchanged:
  `890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`.

This suite is local deterministic/fake-provider proof only, not a
new MiniPC production canary, legal closure, source rights review or
approval of the pending DP-417 migration. Git SHA and matching CI
must be recorded after selective publication.

## Remaining acceptance and authority

DP-233.10 requires owner-approved official parliamentary source-family
scope, terms/rights and real MiniPC canary. DP-419 still requires real
Capture/Passage/version browsing, private rights-gated preview,
selector jump and manual/device acceptance. Garlasco is PAUSED,
18 historical INCLUDED, zero rights-cleared and zero authentic
Discovery/Capture/Passage/Candidate rows. No data or schema write was
performed. **125 tickets: 86 DONE, 24 IN PROGRESS, 6 BLOCKED,
9 FUTURE = 39 open; release NO-GO/41**.
