# DP-203 — controlled claim fan-out (private operator)

Parent `CLAIM_PREPARE`/`CLAIM_EXTRACT` work is **HOLD by default**, including
work that was already in the queue. The worker refuses preparation and window
extraction until `--claim-fanout-gates-verified` is explicitly supplied. This
flag is an operator assertion; it is not itself evidence that the prerequisites
have passed. Never set it before all of the following have verifiable receipts:

- [#327](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/327):
  dedicated DP OmniRoute credential scoped to the approved 12 Google Antigravity
  Pro accounts, exact Gemini route, no auto fallback, stop on exhausted quota,
  meaningful schema-constrained single call with request ID and usage.
- [#34](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/34):
  successful single authorized Giuliani parent with quality, provenance,
  current source rights, latency, and usage receipt.
- Current source permission and attribution verified privately; queue state,
  provider/usage ledger and account quota inspected before the first batch.

Once those gates are satisfied, run the **existing** one-shot worker with the
normal credential and private data environment, adding
`--claim-fanout-gates-verified --claim-window-batch-size 2`. Only 1, 2 or 3
windows may be admitted per batch (default 2). Further preparation jobs are
created only after all currently admitted windows for that content complete.
Every child carries a hash of the ordered manifest, variant, model, prompt
version and batch size: if any change between batches, the continuation is
blocked. Child job IDs
remain deterministic for replay. A blocked, deferred or dead-lettered child
holds the next batch. Existing per-job, source/day and global/day budget
reservations, provider outages and lease handling are unchanged.

Verify the before/after `processing_job` states for each claim job family,
provider receipts (`request_id`, model, token usage, cost if returned), actual
quota and number of newly inserted children. Reconcile interruptions between
the last window completion and its follow-up enqueue before resuming: a
failure here leaves progress held and must not be bypassed by bulk requeue.
Keep claim candidates private pending provenance, verification and editorial
review. This runbook grants no live provider usage or public publication.
