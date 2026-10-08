# DP-214 — persisted PAUSED Garlasco historical baseline

Date: 2026-10-08. Authority: local MiniPC `dichiarazioni_pubbliche`
PostgreSQL. This is **not a launch receipt** or a cleared 100-item
tracer. All rights, capture and publication gates remain unchanged.

## Bounded transactional method

Module `poc/dichiarazioni_pubbliche/garlasco_collection_seed.py`
accepts only the pinned exact historical read-only seed SHA-256:

`6b6ea81195c0c7278ad3452b7fb00735b4658d696e2fd9f950bed70365b373c0`

The operator must choose either read-only dry-run (default),
`--rollback-test` (an actual DB transaction that **ROLLBACK**s)
or `--apply` (the exact guarded transaction). The transaction
acquires a scope advisory lock, NOWAIT SHARE locks on claim/Content
identities, verifies 30 exact claim IDs and all 18 Content/Source/URL/
UNKNOWN-rights bindings against the private inventory, and refuses
existing conflicts. Its only writes are to
`research_collection` and `research_collection_content`. It may
add a single PAUSED row and 18 historical Content links. The
same-document status metadata explicitly states
`pilot_ready=false`, `review_required=true`,
`rights_clearance=false`, and `capture_authorized=false`.

A protected, mode-0600 data-only preimage export of just the two
collection tables was created before application at:

`/home/udodo/.local/state/dichiarazioni-pubbliche/garlasco-pilot/research-collection-before-paused-seed-20261008.sql`

No personal data/public source bodies are included in this receipt.
The export, its content and the private seed remain outside Git.

## Actual MiniPC result

| Operation | Result |
| --- | --- |
| Preflight dry-run | PASS, 18 Content / 30 linked claims, exact seed SHA |
| Database transaction with rollback | PASS, no persisted collection afterward |
| First apply | PASS, `research:garlasco` PAUSED |
| Second apply | PASS, idempotent, same 18 members |
| Unique current collection rows | 1 |
| Included distinct historical Content | 18 |
| Content with UNKNOWN rights | 18/18 |
| Existing historical Atomic Claims | 30 |
| Historic Captures/Passages | 0 / 0 |
| Discovery hits | 0 |
| Public PUBLISH findings | 2, unchanged |
| Existing operator collection reader | `research:garlasco`, `PAUSED`, count 18 |
| Unscoped Garlasco Recall@5 | 13/13 |
| Collection-scoped Recall@5 *before* fix | 11/13 (PERSON results missing) |
| Collection-scoped Recall@5 *after* fix | **13/13** |
| Attempt to persist a new DP-209 manifest while PAUSED | **BLOCKED**; manifest count 0 before and after |

The query fix in `corpus_search.py` allows a PERSON match only where
the person has a persisted historical Atomic Claim whose Content is
INCLUDED in this collection. It deliberately does not infer any
unreviewed speaker from candidate matching. Collection matches are
limited to the queried collection ID. Code-side regression asserts
exact positive joins and prevents arbitrary organization scope.

The local operator frontend can list this persisted metadata, but
there is **no authorized write UI**, capture/fetch, review/promotion,
source-to-passage chain or cleared excerpt. Real complete corpus
acceptance still needs the remaining 82 logical items, independently
verified discovery/source rights, immutable capture/passages, coverage
needs, dedupe review and safe replay. AC-214.3 remains DONE; DP-214
remains IN PROGRESS; release preflight stays NO-GO.
