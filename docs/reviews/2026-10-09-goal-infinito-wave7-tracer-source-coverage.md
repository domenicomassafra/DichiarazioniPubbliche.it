# GOAL INFINITO — Wave 7: Garlasco manifest, source suitability, Coverage Needs

Date: 2026-10-09 Europe/Rome. Source-only deterministic safety tranche.

## Verified starting point

- Wave 5 Git commit `82f4c2b877a8fedb2f9bcad4e9d6bb0868a1e98b`;
  GitHub CI `37948202895` **11/11 SUCCESS**.
- Wave 6 Git commit `41c30febb5f2943e3ba7f6e137f09747439c5dfe`;
  GitHub CI `37949761666` **11/11 SUCCESS**. Complete source Python
  suite was **2,025/2,025 PASS**, benchmark **5/5 PASS**.
- Owner handoff `docs/reviews/2026-10-09-goal-infinito-tutti-ticket.md`
  remains untracked and untouched.

## Completed independent implementation tasks

1. **DP-214 structural tracer:** `evaluate_preflight` now checks URLs for
   exact canonical form, normalized collision, globally routable IP literal,
   HTTPS/default port policy and explicit Garlasco source-family taxonomy.
   Private-link IPs, malformed authorities and disguised duplicate logical
   sources return blockers even when manifest count equals 100. **This is a
   synthetic structural preflight test, not a real Garlasco 100-item proof.**
2. **DP-215 Source Intelligence:** strict ISO date/timestamp parsing prevents
   suffix garbage or invalid clock times from silently passing temporal
   suitability. Required Authority Scope fields, role binding and effective
   validity windows must be satisfied; expired, wrong-role and incomplete
   legal scope do not qualify. Missing statement date blocks required
   temporal cutoff and proposes an inspectable Coverage Need.
3. **DP-213 Coverage Needs:** typed and bounded attempt/independence values,
   roles/scopes and target identifiers, deterministic deduplication of repeated
   semantic needs by Collection, and fail-closed search hint for exhausted or
   corrupt attempts. Legacy opaque identifier compatibility remains intact.

Prime exclusively edited the tracer pair and canonical ticket docs. Two
reused worker chats independently edited Source Intelligence and Coverage
Need code/test pairs; no worker committed or pushed. Adversarial tests went
RED on the prior code for role/date/attempt/duplicate flaws then GREEN after
the fixes. Combined focused tracer/Source Intelligence/Coverage suites:
**66/66 PASS**, plus related Coverage Need/runtime combinations 95/95 PASS,
compileall and diff --check PASS.

## Limitations and required follow-through

`research:garlasco` remains PAUSED with only 18 historical included Contents,
30 earlier Garlasco Claims, and no genuine accepted Discovery Hit, Capture,
Passage or Candidate proof. No rights, credential, model budget, reviewer
approval, source authenticity or release authority can be derived from these
fixtures. DP-214.1/.2/.4-.8, DP-215.9 and M7 remain open/NO-GO.
Backlog reference: **125 total, 39 open (24 IN PROGRESS, 6 BLOCKED,
9 FUTURE), 41 release blockers**, verified again by canonical ticket count
and read-only launch preflight receipt
`890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`.
Complete Python suite **2,040/2,040 PASS** in 115.05 seconds, including the
restore drill `RESULT: PASS` and 100-table/1,248-field technical-only privacy
inventory; benchmark 5/5 PASS and ticket contract PASS. Final commit SHA and
CI can only be cited once actually observed. Production data/schema/site
were not changed.
