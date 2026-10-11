# Four-agent M2 private pipeline hardening — 11 October 2026

## Frozen scope and truth boundaries

Canonical Mac Studio main baseline: `306fe73bd1c12af218bc64cb9d77b304d84ceb5a`.
Four independently assigned, mutually exclusive source/test/ticket write sets:
DP-238 (PDF), DP-239 (translation), DP-240 (private multi-person batch),
DP-241 (original-source recovery). No new Git worktree/branch was needed.
This wave patches specific falsifiable fail-closed defects; it is **not**
the real-source, rights, independent-gold, MiniPC or editorial acceptance
of any of these tickets.

| Ticket | Verified defect before fix | Bounded correction |
| --- | --- | --- |
| DP-238 | A PDF mixing extractable text with an inline `BI/ID/EI` image could be misclassified as fully native text; an untrusted worker-success page could contain a formfeed that synthesizes an extra selector. | Parse page content operators to detect raster inline images and return `DOCUMENT_PDF_OCR_REQUIRED`; reject embedded formfeeds in individual pages and invalid worker payload. |
| DP-239 | `recheck_private_translation` could report STALE before checking a rebinding to another valid original locator; numeric normalization silently lost minus signs and decimal magnitude. | Compare exact original binding first; report BLOCKED for a changed source/locator, and preserve numeric signs/decimal magnitude with ambiguous-number holds for German→Italian lexical risk. |
| DP-240 | A private batch plan checksum omitted the upstream manifest SHA and accepted a rehashed out-of-order replay, a truthy non-boolean provider-ready value, or a FAILED observation on an already HELD item. | Digest binds manifest SHA and canonical item order; enforce boolean provider gate, ready speaker-candidate binding, and no failed-provider override of held items. |
| DP-241 | Reused discovery receipt SHA could count for two separate lookup methods, and reconciliation allowed distinct receipt attempts above the plan's `max_attempts`. | Reject cross-attempt reused discovery receipt and refuse over-cap unique attempts before deriving a candidate outcome. |

## Validation receipts

The original combined five test modules passed **63/63** before the wave.
New adversarial tests were shown RED against the prior behavior and GREEN after
the respective narrow source changes. The same five test modules now pass
**74/74**:

```shell
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -B -m unittest \
  tests.test_dp238_born_digital_pdf tests.test_dp238_document_extraction \
  tests.test_dp239_multilingual_derivation tests.test_dp240_multi_person_batch \
  tests.test_dp241_original_source_investigation -q
```

Per-ticket counts: DP-238 native/PDF **21**, DP-239 **15**, DP-240 **20**,
DP-241 **18**. Touched Python files pass Ruff, `git diff --check`
passes, the canonical repository contract passes, and the deterministic
benchmark returns **5/5 PASS** (synthetic regression, not independent gold).

The entire Python suite/restore drill and GitHub CI are independent final
integration gates; record their final output once observed, never assume
green from the targeted tests alone.

## Review: standards and ticket-specific specs

All four patches work through existing stdlib/local modules, optional
isolated PDF parsing and private read models. No external provider or live
source was called by the new regression tests; no DB migration, public
route, rights upgrade, fake human signer, downstream dispatch, service
restart or production deployment was introduced. Preserve prior test
assertions and fail-closed gates: no new `# noqa`, `type: ignore`,
skips or loosened quality thresholds were added.

The exact checksum in a local test object proves only local consistency,
**not** source origin, legal permission or an independently verified
review. PDF OCR fidelity and legally approved source rights, German→Italian
external gold, actual multi-person false-attribution/provider-cost baseline,
and real persisted source-investigation receipts remain outside this
source-only tranche.

All four tickets therefore remain **IN PROGRESS**, their original
external MiniPC/qualified-approval acceptance checks **unchecked**.
The editorial release gate is still **NO-GO / 49 blockers**. Do not
convert these local regressions into claims of a production rollout.
