# Six-ticket pending safety hardening — 11 October 2026

## Scope and honest closure accounting

The owner asked to resolve as many open tickets as possible. Baseline
Mac Studio `main`: `a2865c4448282bce05e47c9d73452570baf37d51`,
clean and equal to GitHub `origin/main`. The starting and resulting
ticket graph remains **162 tickets: 90 DONE, 52 IN PROGRESS, 6 BLOCKED,
14 FUTURE (72 not DONE)**. The original criteria of the six selected
IN PROGRESS tickets require actual qualified source-use rights,
immutable MiniPC DB/readbacks, live Studio execution or authorized
independent source/context evidence. Synthetic tests cannot close those
gates, so **none of these tickets is reclassified as DONE**.

The six independent, bounded source-only improvements are:

| Ticket | Verified new behavior | What still prevents DONE |
| --- | --- | --- |
| DP-236 | The private source-use guard refuses malformed permission lists (including a substring confusion in `FETCH in NOT_FETCH`), and refuses an approval lacking explicit rights expiry before even attempting fetch or body persistence. | Qualified rights/actor scope, durable current permission and genuine approved/denied MiniPC capture readback. Perpetual-use legal approval is not inferred from missing expiry. |
| DP-237 | Media locators require an explicit nonblank speaker pin matching the original segment speaker; a missing pin or missing observed speaker must not resolve an attributed excerpt. | Authenticated original track, media-seek and versioned Studio/MiniPC source proof. |
| DP-242 | Studio machine preflight now refuses incomplete/wrong-kind passage/capture/Statement/Person attribution rather than suggesting machine eligibility, while keeping downstream B authority absent. | Credentialed B API/DB receipts, actual production-source collection and full Studio UI acceptance. |
| DP-244 | Catalog source coverage keeps changed/unreviewed material stale, revocations/outages blocking, and observation fingerprints bound to exact receipts/scopes while excluding elapsed wall time. | Reviewed real source enumeration, rights, persistent deltas and bounded MiniPC permitted-source proof. |
| DP-315 | Denial-receipt fingerprints bind the complete typed review, speaker/date window and occurrence metadata rather than merely a selected occurrence ID, so changed provenance cannot reuse a stale checksum. | Independent original/endorsement evidence, changed-source invalidation across relation/reader, and MiniPC acceptance. |
| DP-319 | Investigation preflight rejects non-Boolean budget/capability gate inputs, and binds exact research question, budget cap and max attempts into the proposal fingerprint. | Durable atomic financial/source worker receipts, observed research, exception workflow and MiniPC acceptance. |

## Proof and authorization boundary

- Test-first RED failures were reproduced before the respective fixes;
  targeted DP-236/237/242/244/315/319 integration validation on the
  combined worktree passed **75/75 tests**.
- Source-only code can refuse unsupported cases; it cannot attest the
  existence of a real approved permit, bill, original speaker, historical
  body, owner action or new public readout.
- Per-ticket receipts record their independent test and safety evidence.
  Do not conflate `IN PROGRESS` with `DONE`, or source checksum consistency
  with independent signing/identity authority.
- Repository-wide Python/backup-restore, deterministic benchmark, static
  repository checks, and GitHub Actions must be independently recorded
  on the final commit; this note makes no assumption that those gates pass
  until their actual receipts exist.

No provider or protected account was called, no public quote or factual
Finding was released, no live source/rights record or MiniPC deployment
was altered. The editorial release gate remains explicitly **NO-GO/49**.
