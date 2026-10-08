# DP-211/214/215 — Private Passage-to-Candidate operator lane, 2026-10-08

## Implementation and authority

This receipt describes a new guarded *operator* entrypoint for the existing
certified DP-211 extractor. It is **not** evidence of a completed live
provider call, source-processing permission, human attribution approval or
legal release authorization.

tools/extract_research_candidates.py provides read-only preflight by default.
Its manifest binds 1–16 existing Passage IDs and hashes to persisted Content,
exact Capture IDs, canonical URLs, source families and rights-record IDs in
one Research Collection. The manifest SHA-256 is returned; source bodies,
prompts and credentials are not returned. The historical
tools/extract_passage_candidates.py command delegates to the same guarded
path. Unbound --passage-id no longer invokes a provider.

Every Passage must pass before a model can see text:

- ACTIVE Collection, INCLUDED member with explicit capture_authorized=true,
  exact persisted Content URL and accepted Discovery Hit for that Collection;
- an independently revalidated **current privacy ingestion relevance**
  authority for the Content/URL; the historical capture permit does not grant
  perpetual privacy permission for downstream model processing;
- a current, qualified-reviewed, unexpired rights record for the exact
  Content/URL/source family, granting both RESEARCH_CAPTURE_PRIVATE and the
  additional OMNIROUTE_MODEL_EXTRACTION_PRIVATE use;
- Content rights CLEARED, no other PAUSED collection or capture-forbidden
  included membership for this Content;
- Passage SHA-256, Capture ID, Capture status CAPTURED, hold NONE, capture
  rights CLEARED, private retention policy and available body reference;
- configured model, credentials, cost rate and explicit *aggregate* cost
  cap. Missing prerequisites yield BLOCKED, never manufactured success.

The operator always supplies an authorization guard to the core extractor,
which revalidates rights before the model call and before candidate commit.
If a right is revoked before the provider call, the run records BLOCKED with
zero provider calls and cost. After a provider call, revocation records BLOCKED,
reserves its conservative upper cost, and persists **no Candidate**. This
read-time revalidation is supplemented by a same-SQL-statement commit fence
as documented below; it is not a global guarantee against an uncoordinated,
concurrent append-only rights/authority revocation.

## Transaction-snapshot Candidate commit fence (additional hardening)

The operator-only `--execute` path now passes an explicit
`PrivateCandidateCommitFence`, derived exclusively from the reviewed
manifest's exact Collection ID, Content/Passage/Capture IDs, Passage SHA-256,
canonical URL, source family and current private rights-record ID. The
persisted privacy relevance binding SHA-256 is deterministically derived
from Content and URL, not supplied by the model.

Inside the **same PostgreSQL statement** that inserts candidate Passages,
Statement Candidates, Claim Candidates, entity mentions/resolutions, the
private provider receipt and `COMPLETED` extraction-run state, the new
`commit_authority` CTE must find a valid current-snapshot authorization:

- ACTIVE Collection, INCLUDED and capture-authorized membership, no
  explicitly forbidden/inactive alternate Collection;
- exact Content, Capture and parent Passage IDs/hash, Capture not held or
  purged, CLEARED Content/Capture rights and private retention class;
- exact current private rights record with receipt, reviewer, unexpired
  review, source family/URL binding and **both** specific private permitted
  uses; no superseding rights record;
- current Content/URL-bound privacy relevance authority with expected
  policy/binding versions and no successor;
- valid source-family-matched Discovery Hit, with healthy attempt, exact
  query/adapter/manifest lineage and accepted disposition.

If the row vanishes from that database snapshot, the insert and
`COMPLETED` mutation have no eligible `locked` run, so **no candidate or
success receipt is inserted**. The application subsequently writes a
terminal BLOCKED run receipt, preserving the provider call and conservative
cost upper bound when the model call has already occurred.

This fence is used by `tools/extract_research_candidates.py` and the
legacy operator command that delegates to it. The DP-211 internal
extraction adapter remains available *without* this operator fence only
for its independently certified legacy/isolated test routes. No public
write or claim promotion was added.

**Race limitation:** the SQL snapshot prevents a stale application-side
approval from authorizing a later *observably revoked* commit. It does
**not** fully serialize against a concurrently inserted append-only
supersession that does not coordinate locks; such global atomicity would
require compatible locking/write-side governance. The independently
replayed Python relevance and rights checks remain mandatory, including
integrity and lineage validation. This is defense in depth, not a legal
or concurrency certification.

### MiniPC acceptance

`tools/check_private_candidate_commit_fence.py --database-url
dichiarazioni_pubbliche` creates **only temporary shadow tables inside one
transaction ending in ROLLBACK**, invokes the actual CTE on one synthetic
positive fixture and tests 15 revoked/mismatched cases. MiniPC result:
**1 synthetic acceptance + 15 fail-closed cases PASS; 0 private Candidate
writes; protected real production counters unchanged**. The synthetic
positive source and reviewer labels are test-only, not Garlasco content,
permissions, providers or real rights receipts. Neither the service mirror
nor production schema/data are updated.

## Manifest and procedure

Keep the operator manifest outside Git with restrictive permissions. Exact
top-level fields: version, collection_id, items. The version must be
private-research-candidate-batch-v1. Each item must have passage_id, content_id,
capture_id, passage_sha256, canonical_url, source_family and rights_record_id,
all matching the real persisted database.

Read-only preflight (no writes/model):

    python3 tools/extract_research_candidates.py --manifest /private/operator/passage-batch.json

Run only after actual approved source/provider rights, legal review, valid
credentials and an owner-approved positive total budget:

    python3 tools/extract_research_candidates.py --manifest /private/operator/passage-batch.json --execute --max-cost-usd 0.10

The amount above is only a CLI syntax example, **not** spending authority.
A partially completed batch does not roll back earlier private Candidates.
The existing DP-211 operation identity is replay-safe. No automatic
Claim promotion, verification, Finding or public projection occurs.

## MiniPC read-only negative-path proof

An isolated copy of the new Python package was staged under
/tmp/dp-private-candidate-canary-20261008. Production source files,
services and PostgreSQL data were not modified. Actual read-only
PostgreSQL inspection confirmed:

- research:garlasco PAUSED; sampled included member capture_authorized=false,
  0 accepted persisted Discovery Hits.
- 0 Passage rows in production, so no legitimate candidate extraction.
- Actual collection/provenance preflight returned
  PRIVATE_CAPTURE_COLLECTION_NOT_ACTIVE.
- Before/after protected counts: 30 Atomic Claims, 2 PUBLISH Findings,
  0 Statement Candidates, 0 Claim Candidates.

Controlled offline fixtures test the approved operation, precall revocation
(zero calls/cost), postcall revocation (cost reserved, no Candidate), source
holds, expired rights, absent discovery, absent model and all-batch preflight.
None are counted as real corpus material.

## Remaining product gates

DP-214.1/.2/.4/.5/.6/.7/.8 and DP-215.9 remain OPEN. There are still 18
historical Garlasco Content rows rather than an accepted 100-item corpus.
The remaining 82 genuine items, provenance, qualified rights decisions,
verified provider setup, actual Capture/Passage/Candidate rows, replay and
coverage/protection receipts are not present. Legal Q-306, DP-307 and M7
release gates remain **NO-GO**.
