# Read-only Studio real collection/member acceptance — 2026-10-08

## Implemented boundary

DP-416 now has a directly usable, explicitly launched,
127.0.0.1-only, bearer-authenticated operator path:
list Collections → select `research:garlasco` → paginate included
Content IDs → select one Content → inspect its persisted Source ID,
rights, processing, source existence, capture/passage/candidate counts,
bounded exact historic Claim IDs and speaker references.

No endpoint creates/reviews/approves/deletes Content or collections,
fetches new sources, mutates any production data, reveals private URLs,
titles, passages, quote bodies, unreviewed text, model explanations or
raw SQL, nor implies Source rights. PostgreSQL uses the previously
enforced read-only connection with timeout. Errors and out-of-scope
lookups fail closed. UI uses native buttons and DOM `textContent`.

## Live MiniPC PostgreSQL and HTTP

On the actual existing MiniPC `dichiarazioni_pubbliche` DB, against
an isolated temporary copy of the new Python modules:

| Proof | Result |
| --- | --- |
| `research:garlasco` state | PAUSED |
| Persisted included Content rows | 18/18 |
| Rights state | UNKNOWN for all 18 |
| Processing state | REVIEW_REQUIRED for all 18 |
| Distinct persisted Source IDs | 10 |
| Linked historical Claim IDs across all 18 | 30 |
| Persisted Captures/Passages for those Content | 0 / 0 |
| HTTP data-free local operator shell | GET / 200 |
| New members endpoint without token | HTTP 401 |
| New members endpoint with token | HTTP 200, 18 results |
| New selected member endpoint | HTTP 200, exact membership |
| Unlisted Content selected | HTTP 422 |
| Cross-origin browser attempt | HTTP 403 |
| Public data/authorizations | No approval/publish/capture authority |

The real HTTP canary used a disposable 0600 token and ephemeral
loopback port and was stopped afterwards. The temporary source tree
was deleted. No permanent Studio service, public route or
browser-profile token was created.

Regression tests cover exact scope, cursor ordering, bounded rows,
source ID matching, counts, missing/invalid rows and redaction. There
is **no claim of manual screen-reader/200%-zoom acceptance**.

## What cannot yet be proven

Full source→passage→candidate→promoted claim navigation is not possible
until rights-reviewed Captures, exact Passages and candidates exist.
The six public search leads remain unreviewed and are not in this
collection. The eventual 100-item discovery manifest/rights/coverage
review remains an independent DP-214 requirement; no release gate is
waived by these navigational readbacks.
