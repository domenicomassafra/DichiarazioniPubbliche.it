# DP-214/215 — Garlasco candidate-lead identity and provenance checkpoint

Date: 2026-10-10. Source: authoritative MiniPC PostgreSQL, read-only
`BEGIN READ ONLY`/`ROLLBACK`, plus local deterministic tests. This is an
operator-safety receipt, not a reviewed source or approved corpus receipt.

## Current MiniPC state

| Measured condition | Read-back |
|---|---:|
| `research:garlasco` status | `PAUSED` |
| Included historical Content | 18 |
| Those Contents with rights `UNKNOWN` | 18 |
| Those memberships with `capture_authorized=true` | 0 |
| Current private source-rights records for those Contents | 0 |
| Active Source Intelligence profiles for those Contents | 0 |
| Historical `claim:garlasco:*` Atomic Claims | 30 |
| Discovery manifests / runs / hits | 0 / 0 / 0 |
| Captures / Passages / Statement Candidates / Claim Candidates | 0 / 0 / 0 / 0 |
| Collection Coverage Needs | 0 |

The six external public URL hints in
`config/garlasco-public-discovery-leads.v1.json` are still candidate-only;
the institution homepage is still a source locator, not a case Content item.
There are 82 missing real logical Content items toward the required 100,
without assuming that the existing 18 qualify as approved captures.

## Isolated RED→GREEN

`load_unreviewed_public_leads` previously accepted a repeated canonical URL
with different lead IDs, including a URL simultaneously classified as a
candidate and source-only locator. It also silently accepted duplicate JSON
keys and used the last value. New focused regressions were RED in three
cases and now pass; the real six-hint file remains accepted but unauthoritative.

Changed: `poc/dichiarazioni_pubbliche/research_pilot_readiness.py`; new focused
tests: `tests/test_garlasco_lead_identity_guard.py`.

To turn any lead into a recorded DP-209 Discovery Hit, an operator still needs
real source identification and family assignment, an authentic versioned
Discovery manifest/query/run with eligible hit/attempt lineage, and an
independent review decision. Before private Capture, each exact Content URL
also needs current source-specific reviewed rights (including private fetch,
retention, and separately model processing where relevant), privacy relevance,
capture authorization and an ACTIVE collection. DP-215.9 further requires
actual role/scope/time/derivation explanations for the selected real corpus.
Neither ticket gains an acceptance criterion from this safety check.
