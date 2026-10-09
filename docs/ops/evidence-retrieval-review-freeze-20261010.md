# DP-229 upstream evidence approval integrity — 2026-10-10

## Failure reproduced before patch

On disposable PostgreSQL, ClaimEvidenceObservationStore.link_claim_evidence
could unconditionally overwrite a reviewed candidate on retrieval retry:
CONTRADICT became SUPPORT, APPROVED became RETRIEVED, and score/metadata
were replaced. A rejected row could be resurrected without review.

## Corrected authority fence

For a conflicting retrieval version, the SQL now updates only a
never-reviewed RETRIEVED candidate. The canonical review_event ledger
must also have no event for the exact compound candidate identity.
This condition is checked inside the PostgreSQL conflict statement;
no race-prone Python read-before-write and no reviewer auto-approval.
An old review event freezes even an already demoted legacy candidate.

Run:

    PYTHONPATH=poc python3 -m unittest tests.test_claim_evidence_retrieval_replay -v

The real migration is replayed twice on a disposable PostgreSQL cluster.
The five test cases were GREEN after two original RED failures. No
production data or private source content was changed.

## Independent approval-event collision repair

The same disposable PostgreSQL harness exposed a second authority
defect: approve_claim_evidence_with_review updated a candidate to
APPROVED *before* trying to append the deterministic review event.
When event_id already belonged to another entity, ON CONFLICT DO
NOTHING suppressed the required event, but the candidate became
APPROVED and the method incorrectly returned true.

Approval now locks the candidate, appends the exact review event
and changes its status only if the event insert succeeded. Exact
same-event replays are idempotent only while the same candidate is
already APPROVED and entity, actor, action and reason match. An
old APPROVED event cannot reapprove an unexpectedly demoted row.

A RED PostgreSQL fixture confirmed unrelated-event ID reuse, which
the patched writer now rejects. This is not a replacement for the
independently attested DP-310 publication authority.

Any past production candidates affected by older unguarded replays
require independent, authorized read-only event-vs-row reconciliation;
this patch does not silently repair historical data, authorize rights,
review new evidence, create a Finding or complete DP-229.

## Actual MiniPC production readback — read-only, not deployment

Using the existing MiniPC PostgreSQL runtime with
default_transaction_read_only=on, a single aggregate join between
claim_evidence_candidate and the append-only review_event table returned:

| Count | Actual |
| --- | ---: |
| Total claim evidence candidates | 16 |
| Status APPROVED with corresponding APPROVED review event | 9 |
| Status APPROVED without corresponding APPROVED review event | 0 |
| Corresponding APPROVED review event, but current status not APPROVED | 0 |

No IDs, evidence URLs, text, reviewer identities or raw metadata were
selected or exported. No SQL write, service restart or migration occurred.
These counts show no current discrepancy of the specific approval form
queried; they do not prove that all historical retries were safe, nor
that every review state has a complete provenance/rights explanation.

The patched Mac source has not been promoted to the MiniPC production
mirror in this step. Runtime acceptance of the deployed implementation
remains distinct from a successful read-only database inventory.
