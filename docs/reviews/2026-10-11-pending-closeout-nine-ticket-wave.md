# Pending-ticket closeout audit — nine material regressions, 11 October 2026

## Governing result and status

Mac Studio baseline `main` was `6242d0dcf9a573b9775be39dd14358132140f0a8`,
clean and identical to `origin/main`. The owner requested as many pending
closures as honestly possible. We audited acceptance criteria, then fixed
falsifiable safety/integrity defects with isolated regression tests in
**DP-314, DP-320, DP-435, DP-438, DP-440, DP-512, DP-515, DP-516 and DP-518**.

**Fully closed tickets: zero.** All nine remain **IN PROGRESS**. Their
unfulfilled criteria require actual approved sources and rights, independent
meaning/identity review, durable production-safe billing/epochs, real
MiniPC reader and rollback readbacks, and/or external owner acceptance.
No synthetic gate/receipt or self-declared provider usage proves those facts.
Ticket totals therefore remain **90 DONE, 52 IN PROGRESS, 6 BLOCKED,
14 FUTURE (72 not DONE)**; original checkbox statuses are preserved.

| Ticket | Pre-fix falsifiable defect | New fail-closed behavior |
| --- | --- | --- |
| DP-314 | Distinct source-root IDs and bytes from one publisher/source family met a two-family verification proposal. | Verify independent source-family cardinality as well as root cardinality; withhold proposal with `INDEPENDENT_SOURCE_FAMILY_MISSING`. |
| DP-320 | A revoked source could commit between epoch validation and public artifact-reference lookup in isolated SQLite reference serving. | One `BEGIN IMMEDIATE` read fence spans both lookups; rollback after a rejected read; late revoke produces stale/held read. A live CDN/HTTP delivery fence is still absent. |
| DP-435 | A mutable source candidate's locator could be changed during attestation or after public projection while approval/quote hash remained unchanged. | Snapshot the exact locator before the gate callback, reject mutation during the callback and do not leak mutable locator references into public bundles. |
| DP-438 | One Person's stable public ID could equal another approved Person's slug in the shared getter namespace, returning the wrong archive. | Withhold both conflicted public identities independent of record ordering; leave unaffected and private-only Persons nonleaking. |
| DP-440 | Two citations of the same Content/URL could pass an independence threshold merely with different caller-provided lineage labels. | Require distinct Content and source URL counts as well as lineage counts before a precomputed Person×Topic synopsis is eligible even as an untrusted offline read model. |
| DP-512 | Discovery-adapter cost quotes were labeled as measured provider billing, and zero configured upper bounds were treated as proof of free usage. In-process budget could underreserve if adapter quoted below maximum. | Classify unverified adapter quotes as estimated/unknown, preserve sanitized quote metadata separately, reserve bounded maximum per attempted call and restore reservation across retries/restart. External invoices and historical receipts are still unavailable. |
| DP-515 | A caller-modified source-watch plan could reuse the last attempt ID, move its clock backward, remove timezone awareness or bypass a retry deadline. | Revalidate attempt identity, monotonic timestamp and source backoff before accepting an HTTP observation. |
| DP-516 | Restart from a completed primary archival source did not seed its dedupe key before skipping it; an identical archive copy could be re-proposed and charged. | Seed lineage dedupe for trusted completed originals before examining subsequent archived copies. |
| DP-518 | A supplied release manifest lacked a matching independently observed release-reference comparison; global revoke-set checks wrongly rejected unrelated entities' disjoint dependencies. | Require exact caller-supplied release metadata/inventory digest and per-entity dependency coverage, retain stale edge-cache denial. Consistency does **not** authenticate the caller or permit release. |

## Test and review boundary

Adversarial RED→GREEN was proven for the distinct bugs on the owned
public/private seams. Local focused test receipts are retained in each
ticket and in the source changes. Selected independent cross-module tests
passed for DP-314/320/435/438/440/515/516/518, along with the
pre-existing verification/projection/budget/regression behavior. The
real publication gate remains **NO-GO / 49 blockers**. No public
endorsement, factual finding or legal grant is produced by these tests.

The full Python suite, backup/restore drill, deterministic benchmark,
repository/format-quality checks and GitHub CI are **separate final gates**;
their outcome must be recorded from terminal evidence rather than presumed
from targeted green tests. A competing early agent suite ran against
in-flight RED tests and therefore must not be used as acceptance proof.

## Deployment and acceptance boundary

No production database, source-licensing record, provider invoice,
publication eligibility, CDNs, MiniPC deploy mirror or independent
human decision was mutated. Runtime-facing changes, especially
DP-512 budgeting and DP-320 epoch reads, require isolated transactional
replay and real operator-approved MiniPC/HTTP/CDN readback before any
production enablement. Frozen artificial source IDs, URLs, speaker names,
roles, quoted words and modeled costs remain fixtures only. The existing
public informational site is not a receipt for first-class v3 content.
