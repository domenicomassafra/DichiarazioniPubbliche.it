# DP-702/703/704 — local mechanical release audit (2026-10-10)

This is a dated **development checkout** audit of baseline Git commit
`e97dad1`. The checkout already contained 10 unrelated modified frontend
files and untracked `LAUNCH.md` before this lane started; they were left
untouched. No MiniPC candidate was deployed, no public dossier generated,
no release artifact signed, and no owner/counsel approval inferred.

## Executed checks

| Local check | Result | Scope |
|---|---|---|
| `PYTHONPATH=poc python3 -m unittest tests.test_launch_preflight tests.test_launch_set_candidate -q` | 29/29 PASS | Deterministic legal/launch gates and synthetic candidate manifest |
| `PYTHONPATH=poc python3 -m unittest tests.test_privacy_field_inventory -v` | 13/13 PASS | PostgreSQL/public projection plus opt-in account SQLite, account responses, runtime log inventory |
| `python3 -m compileall -q poc tests` | PASS | Source/test import syntax |
| `PYTHONPATH=poc python3 tools/check_launch_preflight.py` | **NO-GO; 49 blockers** | Canonical plan/register/artifact availability at observed baseline |

The `launch-preflight-v1` receipt on this baseline was
`96fb7b178b371dcaac129496ba3f436a803ca063557f1e6a28be0d6346070c3f`.
Of its 49 blockers, **16** were undecided/blocked qualified Q-306 items, **4**
were missing durable release artifacts (`prelaunch_closure`, `launch_set`,
`launch_rehearsal`, `release_authority`), and **29** were ticket-status gates.
This hash records a current local snapshot; another ticket/status edit requires
a fresh check and a new receipt. It does not describe current live MiniPC state.

## What is mechanically prepared and what still needs authority

**DP-702:** The legal register keeps all sixteen Q-306 statuses and source
links visible, with named reviewer/owner roles, safe defaults and re-review
triggers. Account/HTTP-log changes are explicitly included in Q-306-05/-08/-10.
The existing trust boundary, restore/retention and security tests remain
independently checked in their governing tickets. A complete accepted decision
index (AC-702.1), full failure matrix (AC-702.9), public notice approval
(AC-702.10), re-review of signed decisions (AC-702.11) and the DP-704 handoff
(AC-702.13) have **not** occurred. AC-702.12 remains correctly fail-closed.

**DP-703:** `launch-set-candidate-v1` and `launch-snapshot-candidate-v1`
already test bounded synthetic source identity and deny included rows with
blocked privacy, rights or provider gates. Fixture signatures and `NOT_EXECUTED`
rollback proposals do **not** create an approved three-family source set, a
production snapshot or an executed rollback. Source-family selection, rights
decisions, approved disclosures and MiniPC read-back are still required.

**DP-704:** Unit/benchmark checks and the isolated failure-path fixtures are
preparatory evidence. The original ACs require a single authorized MiniPC
rehearsal binding one selected candidate, all stage read-backs, failure
injections, correction/reanalysis, actual restore/hash read-back and an owner
decision. No existing fixture or local receipt supplies that authority.

**DP-301.8:** The register documents Q-306-01/-02 but no qualified reviewer
or product owner has entered the DP-307 decision. The intent-inference ban
remains effective and this AC remains open.

No M7 closure statuses were changed on the strength of a local audit. The
next truthful prerequisite is an owner-selected source set and the qualified
DP-307 review for the actual deployment/profile, followed by MiniPC rehearsal
and rollback on that exact candidate.
