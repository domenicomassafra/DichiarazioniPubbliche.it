# DP-240 — Bounded multi-person candidate batch with cross-source identity isolation

Status: IN PROGRESS
Milestone: M2 — live pipeline readiness and source coverage
Depends on: DP-211, DP-212, DP-218, DP-222

## Problem

Existing `private_candidate_batch` accepts 1–16 Passage items, but that is neither multi-person semantic acceptance nor an efficiency benchmark. Multi-speaker sessions, interviews, reported speeches and homonyms may contaminate outputs; a very large model window does not remove attribution risk.

## Outcome

Deterministic, budgeted batch planning and candidate extraction over several Contents, languages and Persons with per-span source identity, role and context intact, per-item replay/failures and independently observed precision/cost compared with bounded single-source baseline.

## Traceability & constraints

R07/R11/R26/Q12, DP-219/220 nested quote/context. No biometric identity, no automatic cluster equality by topic or lexical similarity. Source roles and languages are not person IDs.

## Scope

Reuse existing Capture/Passage Candidate batch rather than replace it. Partition by capture version, source family, context continuity, speaker/author candidate and language; preserve source→span→Person/role candidate mapping per output. Freeze batch fingerprint, per-item allocation, per-stage token/audio budget, cross-item leakage detectors, fallbacks, job retries, and per-item ledger. Compare baseline isolated runs against bounded mixed batch and do not impose an unsupported universal 1-person limit.

## Non-goals

Unlimited context windows, one-person-only policy, face/voice matching, direct publication and B's final machine reviewer authority.

## Dependencies and sequencing

Hard original extraction/matching/speaker contract. Soft DP-235 source set, DP-239 language, B semantic attribution, D quota measurement. Runtime provider access still explicit gate.

## Acceptance criteria


- [ ] `AC-240.1`: Versioned batch manifest contains at least two distinct approved Persons or unresolved speaker candidates, more than one Content and exact Passage selectors/source hashes; items cannot silently borrow another's source ID.
- [ ] `AC-240.2`: Explicit adversarial wrong-speaker/quoted-voice/homonym examples yield separate held candidates, with per-segment source/speaker/author context and no public attribution.
- [ ] `AC-240.3`: Each output Statement/Claim Candidate maps to its own source spans, extraction version and original wording; no stitched cross-source verbatim or forced speaker ID.
- [ ] `AC-240.4`: Duplicate items, reordered batch, partial provider failure, retry and same idempotency key preserve cardinality/lineage and do not convert failed items to success.
- [ ] `AC-240.5`: Source-level token/cost/latency/memory and false-attribution rates are measured against a preregistered isolated baseline; approve larger batch sizes only based on observed benefit and non-regression.
- [ ] `AC-240.6`: MiniPC persisted replay and Studio operator inspection prove each candidate's correct original Content, Person candidate and hold reason; unrelated corpus/public counts remain unchanged.

## Validation / proof

Attributed gold annotated independently; mixed Italian/German where permitted, official multi-speaker AKN fixture only as a *negative/candidate* baseline until rights clearance; per-item replay receipt, false attribution confusion matrix, D budget counters, MiniPC readback.

## Documentation, data, and migration impact

Reuse `private_candidate_batch`, candidate matching, DP-218/222; change only necessary per-item provenance keys, migration additive if needed; no second claim table.

## Completion receipt

**2026-10-11 — partial local implementation, NOT acceptance:** added
`poc/dichiarazioni_pubbliche/multi_person_batch_v1.py` and
`tests/test_dp240_multi_person_batch.py`. The private, no-provider planner
reuses the existing immutable candidate-batch manifest, enforces exact
Content/Capture/Passage/source SHA and selector context, distinct Passage
partitions, candidate speaker roles, rights/context holds, and bounded token
allocation. Reconciliation records per-item partial/failed/held observations
as private-only, never as a published attribution. Plan fingerprint, cardinality,
count consistency, per-item provenance and reserved authorization fields are
rechecked before replay; checksum is **not** a signature or evidence of
upstream approval. Adversarial cases cover quote vs endorsement, homonyms,
cross-source mismatches, held-item fabricated success, plan tampering, duplicate
and conflicting replay, unbounded input and retries. **15/15 focused tests PASS**;
**27/27 candidate-batch regression tests PASS**, `compileall` and `git diff
--check` PASS. Test contexts are synthetic; no actual candidate or provider
call, published Statement, measured cost/latency/false-attribution baseline,
independent gold, durable store or MiniPC/Studio operator readback exists.
**AC-240.1–.6 remain open** pending those corresponding end-to-end proofs.

**2026-10-11 — local replay lineage hardening, still partial:** Five new
regressions expose that the plan checksum originally omitted the upstream
manifest digest, the readback accepted a reordered plan with a recalculated
checksum, a `FAILED` provider observation overrode an explicit `HELD` item,
and a truthy non-boolean provider gate could propose private extraction.
The plan checksum now includes the original ordered manifest SHA, and
reconciliation rejects reordered plan items, failures reported for held rows,
and ready rows missing a nonempty speaker-candidate ID. The provider gate
requires an actual boolean. Retrying the **same** manifest has a stable plan
fingerprint; two manifests containing the same items in different orders
have identical canonical item partitions but **different** plan fingerprints
because their source manifest hashes differ. This explicitly binds the
replay identity to upstream manifest order; observation order remains
independent. These local SHA checks only detect inconsistent input; callers
must still obtain their manifest and review evidence from trusted storage.
No provider, external capture, public attribution or downstream dispatch was
performed. End-to-end acceptance criteria remain open.
Local validation: **20/20 DP-240 tests PASS**, **39/39 DP-240 plus
private-candidate-batch regression tests PASS**, targeted `compileall` and
`git diff --check` PASS. Five new tests reproduced failing behavior before
the source fix; the historical 15-test receipt above describes the earlier
snapshot.

**Integration validation reported by prime, 2026-10-11:** **74/74 combined
focused tests PASS**, including DP-240 alongside the other active M2 ticket
changes; **Ruff PASS**. Full repository suite was still running when this
receipt was written, so no full-suite result is asserted. This is local
source/test evidence only; the acceptance checks above remain open.

## 2026-10-11 — Per-item private durable-format receipt index and replay

New **functional read-only** interface in `multi_person_batch_v1.py`:
`PrivateBatchItemReceipt`, `PrivateBatchReceiptIndex`,
`build_private_batch_receipt_index`, `lookup_private_batch_item_receipt`,
`export_private_batch_receipt_index` and
`load_private_batch_receipt_index`. This extends, but does not replace,
the existing private candidate batch manifest and status-only reconciler.
Every proposed/held item now retains explicitly scoped immutable identity
fields—Content, Capture, source SHA-256, Passage and text SHA-256, selector
fingerprint, batch partition, candidate Person ID, language, source family,
identity review state, speech role/act, context review ID and rights state.
The added context also remains part of the deterministic plan fingerprint;
a rehashed ready item claiming revoked rights, unresolved speaker, reported
quotation or absent context review cannot pass plan validation.

The per-item receipt distinguishes **UNOBSERVED** from an explicit source/
identity/rights **HELD**, observed **FAILED**, and
`PRIVATE_CANDIDATE_UNVERIFIED`. Missing observations never become successes.
Receipt snapshots are immutable data objects with a canonical integrity hash
and exact plan binding; JSON export/import validates all fields, provenance,
per-item observation semantics, counts, ordering and unknown fields before
consumer readback. Read-only lookup requires matching Passage **and** Content,
Capture and source hash, not a shared Person name or topic. Repeat identical
observations are idempotent and observation ordering is irrelevant. A new
observation may fill an **UNOBSERVED** item in a later snapshot, but may not
rewrite a previously recorded failure/held/success outcome on the same plan;
a real new provider retry requires a separately authorized, durable execution
scope. No raw original text or model output is serialized into these receipts.

The newly added tests demonstrated **RED** before implementation (missing
receipt-index interface) and **GREEN** after implementation: different
Contents and Italian/German language items, candidate homonyms separated by
source, quoted-speech and revoked-rights holds, partial failure with resumed
unobserved items, conflicting replay, forged result/provenance, reordered
items, exact source lookup, JSON roundtrip after simulated process reload,
bad counter type/extra private field, and rehashed ready plans contradicting
their own rights/role/identity context. **25/25 DP-240 focused tests PASS**;
DP-240 plus the existing candidate-batch and CLI suites **52/52 PASS**.
Ruff lint, targeted Python compilation and `git diff --check` pass.
No real provider, cost measurement, persistent DB, image/voice model, public
attribution or production MiniPC was involved.

This is a **persistable private receipt format**, not an implemented durable
store or an authenticated proof that extraction happened. SHA-256 is not a
signature; caller-supplied source rights, speaker candidates and receipt
content still require independent source/rights/runtime authority. The
original **AC-240.1–.6 remain unchecked**: approved multi-Person, original
Passage/role evidence and independently annotated wrong-attribution gold,
real candidate mapping, authenticated transactional persistence/idempotency,
measured isolated-vs-batch cost/latency/error rates, and MiniPC+Studio
consumer readback with no public contamination remain external gates.
**Status IN PROGRESS; release NO-GO.**

## 2026-10-12 — Local SQLite per-Passage observation ledger and restart

Added `poc/dichiarazioni_pubbliche/multi_person_batch_store_v1.py` and
`tests/test_dp240_durable_batch_next.py` as an **opt-in local-only operator
store**, without modifying the existing planner, pure reconciler, Candidate
pipeline or production schema. Each registered immutable plan binds the exact
ordered manifest fingerprint and Content/Capture/source SHA/Passage text SHA,
selector, isolated partition, candidate Person, language, role, contextual
review and rights status. SQLite stores source-bound metadata and one immutable
attempt observation per Passage, with a unique idempotency key. `BEGIN IMMEDIATE`
and a compare-and-swap revision ensure that concurrent writers cannot overwrite
or lose each other's updates. Duplicate same-key/same-result replay returns the
current receipt without mutating it. A different result/key cannot rewrite an
already observed `FAILED`, `HELD`, or private unverified candidate; other
`UNOBSERVED` items may be resumed independently, including after restart in
a **separate Python process** using only the durable plan fingerprint: `load_plan`
reconstructs the canonical immutable plan and `resume` rebuilds its receipts.
Malformed or rehashed Person context in the stored plan fails closed. A rollback
fault injected after an attempted
INSERT but before revision update proved both changes remain absent on failure.

SQLite readback reconstructs both the existing pure per-item receipt index and
the status-only reconciler; individual operator lookup requires the exact
Content, Capture, source hash, Passage hash, selector and candidate Person.
A RED regression caught an otherwise accepted mismatched item/observation pair
within the same plan; write-time checks and independently verified stored
readback now reject it. Further adversarial tests cover wrong source/segment/
candidate identity, a held quoted speaker or rights revocation, attempts to
change a committed failure to success, idempotency-key reuse, distinct plan
fingerprints, actual competing SQLite connections, tampered rows and accidental
free-form text in result metadata. Database files are mode 0600; readback opens
SQLite read-only and does not create an uninitialized database.

**Validation:** eleven new SQLite tests PASS, including process restart, injected
transaction rollback and two concurrent writers. Together with existing
DP-240 and CandidateBatch plus adjacent DP-242 Studio handoff coverage
**70/70 tests PASS**; Ruff, targeted
`compileall`, and `git diff --check` PASS. Test data and result observations
are synthetic and caller-supplied. The persisted hashes detect accidental
inconsistency, **not** authenticated provider execution or current upstream
source/rights approval. No actual model output, independently annotated gold,
live source revalidation, cost/accuracy benchmark, runtime MiniPC/Studio proof,
public attribution, reviewer or publication authority was established.
Consequently **AC-240.1–.6 remain unchecked, ticket IN PROGRESS, NO-GO**.

## 2026-10-13 — Local SQLite opened-file identity race, bounded P2 repair

Independent follow-on in detached, isolated `/tmp/dp240-20261013-worker-new`
from canonical `origin/main` `83588bdb5bbcb0e21f34d3935d504b8fad27bb3e`.
The private SQLite ledger validated the pathname and `0600` file mode before
calling `sqlite3.connect()`. A concurrent local pathname replacement could
redirect SQLite to an unrelated, world-readable database, then restore the
original secure path before the first transaction. The write path would
persist a source/Content/Person-scoped plan into the unintended file; a
second pathname check alone could miss the restored-file scenario.

A real-SQLite regression in `tests/test_dp240_durable_batch_next.py` temporarily
replaces the checked file with a symlink to an existing `0644` SQLite file
*only during* `sqlite3.connect()` and then restores the original inode.
**RED** on baseline: registration unexpectedly succeeded (`ValueError not
raised`). **GREEN** after the bounded fix: `_connect()` checks the actual
opened `main` database returned by SQLite against the verified device/inode,
current pathname identity and private file permissions, before any schema
write or receipt read; refusal closes the incorrect connection. The test
also verifies the exposed database gained no DP-240 table.

**Validation:** focused race regression PASS; 56/56 DP-240 durable, multi-
Person and `private_candidate_batch` neighbor tests PASS; Ruff for the two
owned Python paths PASS; targeted `compileall` and `git diff --check` PASS.
This is local private-ledger isolation only. There was no real source or
provider execution, no MiniPC/Studio readback, no independently annotated
multi-speaker acceptance or cost/false-attribution baseline. Original
**AC-240.1–.6 remain OPEN**, status **IN PROGRESS**, release **NO-GO**.

### 2026-10-13 — Independent P2: PRAGMA pathname does not identify SQLite's held inode

Independent GPT-6 high review of the first SQLite path-swap fix reproduced a
second **read-poisoning P2**, even after `PRAGMA database_list` and file `stat`
were checked. With one private `0600` trusted database at revision 0 and an
unrelated `0644` SQLite database containing an extra synthetic attempt at
revision 1, a concurrent local `rename()` moved the unrelated **regular**
file under the trusted pathname just for `sqlite3.connect`, then restored the
files immediately. SQLite retained the foreign open handle while
`PRAGMA database_list` reported the restored trusted *path*. Both subsequent
`Path.stat()` checks appeared valid, yet `read(plan)` returned the foreign
revision 1. A real SQLite regression reproduced this **RED**. The analogous
writer test raised SQLite `SQLITE_READONLY_DBMOVED`; that observation must not
be misreported as a confirmed cross-database private-row write.

Read-only opens now use a validated `os.open(O_RDONLY|O_NOFOLLOW)` descriptor,
compare its **actual `fstat()` device/inode and 0600 mode** with the initial
private source, and open SQLite through the pinned `file:/dev/fd/N?mode=ro`
path while the descriptor remains open. SQLite holds the original open file
rather than following any intervening pathname swap; the descriptor is closed
once the independent SQLite read handle exists. A previously accepted
rename-swap no longer redirects SQLite into the unrelated external plan, while
normal source snapshots and replay remain readable. The existing writable
path remains guarded by the original 0600 check, post-connect pathname check
and SQLite's moved-database write protection; this is **not** a general VFS
identity or cross-process hostile-writer security proof.

A second RED→GREEN negative covers external `WAL` journal mode. A pinned
read-only `/dev/fd` SQLite path does not identify the original WAL sidecar,
which can produce `disk I/O error` or a stale read; it now fails closed with
`MULTIPERSON_STORE_PATH_INVALID`, without serving partial receipts. The
reference private batch store still uses SQLite's default DELETE journal
mode and does not claim WAL compatibility. **58/58 local DP240 and neighboring
candidate-batch tests PASS**, scoped Ruff and diff check PASS. No real source,
provider, MiniPC, live database or publication action occurred. All original
AC-240.1–.6 stay OPEN, ticket IN PROGRESS, current release NO-GO.

### 2026-10-13 — authorized bounded DELETE-journal crash follow-up

Independent review of PR23 SHA `c98ba7e4a15e9f4567e97e5fb345a4d029950bff` reproduced a native SQLite crash leaving an uncommitted, spilled revision1 and a valid hot DELETE-journal. The FD-only reader served revision1; canonical SQLite recovery rolled it back to revision0. Owner authorizes a bounded data-integrity repair retaining FD/inode isolation: fail closed while the canonical journal exists, and recheck before returning readback while the SQLite read transaction is still held. Recovery remains SQLite-native, not a custom journal parser or blind automatic reopen on a replaceable pathname. Official source reuse: https://www.sqlite.org/lockingv3.html sections4/4.1; nearby store already uses SQLite transactions and pathlib identity checks. Native recovery is adequate for the journal but an automatic swappable-path open does not meet existing inode authority; smallest residual is an explicit bounded HOLD. Source/test/ticket only, no release, production or original AC closure.

**Result — bounded source repair, not release:** the read-only FD path now refuses any canonical `-journal` sidecar with `MULTIPERSON_STORE_RECOVERY_REQUIRED`; dangling/inaccessible objects also fail closed. It checks before opening and after the actual SQLite read transaction, before returning `read` or `load_plan` output; `resume` uses those same paths. Existing FD/fstat/path permissions and WAL refusal are unchanged. Presence-based HOLD intentionally also covers a live or stale journal: no journal contents are parsed, deleted or replayed by owner code. Authorized recovery must use SQLite itself on the verified canonical store; automatic recovery on a merely swappable pathname is not introduced.

Two actual crash regressions were **RED** on source `c98ba7e`: `ValueError not raised`. A temporary child uses real SQLite, cache spill and an uncommitted source-valid attempt, then `os._exit(0)`, leaving a valid hot journal; fixed `read`/`load_plan`/`resume` HOLD instead of serving phantom revision1. After native SQLite rollback, positive read/restart returns committed revision0 and zero attempts. A second test crashes after the connection preflight and proves read and plan-load refuse before returning results. The rename regression now actually swaps the pathname during the FD URI connect, preserving the trusted revision0 and foreign revision1; its former hook only targeted the old pathname URI. Fresh `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_dp240_durable_batch_next tests.test_dp240_multi_person_batch tests.test_private_candidate_batch -q`: **60/60 PASS**; scoped Ruff and diff-check PASS. This fresh run is macOS local synthetic evidence. Linux proof requires the updated PR CI; the prior 12-success/3-skip CI is for the predecessor SHA and is not reused as proof for this dirty delta. No host, service, real private DB, provider or public source touched; temporary children exited and fixtures cleaned. Root integrates/reviews/pushes this same PR. Original AC-240.1–.6 remain OPEN and release NO-GO.

### 2026-10-13 — same-PR Linux pre-SELECT HOLD correction

CI on `44f15eb2e5ebfa900fb4a26aa7cfda8a59f6a8fd` exposed a consequence of the preceding repair: after a crash between connection preflight and first SELECT, SQLite on Linux/macOS Python3.11 attempted its own read-only journal recovery before the post-read check, raising `OperationalError: attempt to write a readonly database` instead of the explicit HOLD. Reproduced **RED** on native MiniPC Linux in a disposable copy of this exact committed source/tests: both read and load_plan failed that existing regression (exit1, errors2). Minimal correction reuses `_assert_read_recovery_not_pending()` immediately after `BEGIN` and before the first SELECT in both public readers; the existing post-read check remains to cover later changes while the read transaction holds its lock. No test expectation was loosened, parser or abstraction added. Fresh same 60-test focused suite **PASS on Mac Studio and native MiniPC Linux**, including process-crash, native recovery, exact FD rename attack, positive replay and WAL HOLD; Ruff/diff-check PASS. Isolated Linux source/test fixtures were created under unique `/tmp/dp240-linux-crash.*` and removed by the same command exit trap; no production DB/services/install touched. Root owns same-PR commit/push/CI/merge. All original AC remain OPEN.

### 2026-10-14 — Source/Person partition binding on rehashed private plan

A bounded independent local review reproduced an integrity gap in the
existing plan replay validator. Planning derived `partition_id` from the
exact Passage, Capture, Content, source digest, selector, context version,
language and speaker candidate/role/act. However, replay validated only the
*uniqueness* of the partition and the caller-recomputable whole-plan SHA.
Swapping two partition IDs between distinct synthetic Person/source items,
then recomputing that SHA, passed both the pure private reconciler and the
real local SQLite `register()` path. It could therefore bind a receipt's
partition reference to another source/speaker without a corresponding
source-context change; SHA alone is not source or review authority.

The planner and validator now share the exact deterministic partition
function. After existing schema, status and integrity checks (preserving
their original refusal reasons), every replayed partition must equal the
source/Person-bound derived value. The two new tests were **RED before**
(`ValueError not raised` in both pure reconciliation and SQLite registration)
and **GREEN after**. Failed registration does not create a private SQLite
database. The adjacent DP-240 pure/durable, private-candidate-batch and
DP-242 Studio suites pass **77/77**. Scoped Ruff and `git diff --check` pass.
Existing synthetic sources, speaker/role holds, replay immutability and raw
wording are unchanged; no provider, billing, live source or public dispatch
was invoked. A deterministic hash still is **not** proof of upstream rights,
speaker identity or provider completion. All original **AC-240.1–.6 remain
OPEN**, status **IN PROGRESS**, release **NO-GO**, with real gold/baseline,
authenticated provenance and MiniPC/Studio evidence pending.

### 2026-10-15 — Multi-source family and context-partition replay binding

The versioned private DP-240 partition identity initially covered the exact
Content/Capture/Passage/source hash and speaker candidate, but omitted the
source family and two distinct reviewed-context identities. A caller could
exchange the `source_family` values of two otherwise source-exact items,
recalculate the **untrusted** outer plan SHA-256, and retain each item's old
partition. The pure readback and real isolated SQLite `register` accepted the
contradictory source-family partitions. This was a real local source-isolation
gap, not evidence that any provider generated an incorrect attribution.

The shared partition derivation now binds `source_family`, `context_review_id`,
`identity_review_status` and `rights_status` alongside the existing source,
selector, language, speaker candidate, speech role and act. Recomputed plan
checksums cannot conceal a change in those fields while retaining the old
partition. A legitimate new source-family manifest produces its **own**
partition, while an unchanged second source keeps its distinct partition.

The plan and private receipt format's logical `VERSION` is explicitly bumped
from `multi-person-candidate-isolation-v1` to
`multi-person-candidate-isolation-v2` because all canonical partition digests
change. This does **not** migrate old persisted v1 plans or delete their SQLite
bytes. Old v1 input is rejected at the version gate; the integrator/operator
must preserve existing immutable receipts, inventory any actual v1 state and
plan a reviewed compatibility/rehydration path before a runtime adoption.
The private SQLite table schema is unchanged. Neither a new source-rights
attestation nor a provider result can be inferred from a v2 checksum.

**RED → GREEN:** two focused tests initially failed (`ValueError not raised`)
when a source-family swap with a recalculated plan checksum was accepted by
both pure readback and actual disposable SQLite registration. A follow-on
adversarial test demonstrated two additional RED subcases: borrowing another
item's contextual review receipt and raising a candidate's identity-review
status while retaining its prior partition. All now fail closed; the SQLite
negative confirms no invalid ledger is created. Positive tests verify normal
v2 planning, independent family partition changes, same-key replay, held and
failed states, concurrent SQLite writers, crash recovery and the adjacent
private CandidateBatch and DP-242 Studio handoff contracts. Local focused
suite: **81/81 PASS**. Scoped Ruff lint, Python compile and
`git diff --check`: **PASS**. Tests use fabricated Persons, Contents, context
receipts and provider observations strictly as adversarial local inputs;
there were no paid/model calls, live capture, MiniPC or public changes.

**Original AC-240.1–AC-240.6 stay unchecked, IN PROGRESS, release NO-GO.**
The remaining A-Z proofs require genuinely approved distinct Person/speaker
and multiple-Content source/span gold; independent quoted-voice/homonym
annotation and correct candidate output/wording review; authenticated durable
per-item provider retries and downstream rights review; a preregistered
source-level isolated-vs-mixed batch precision, token, cost, latency and
memory measurement; and real MiniPC persisted replay plus Studio operator
readback proving correct hold/attribution and unchanged unrelated public and
corpus counts. None are supplied by synthetic fixtures or a local checksum.
