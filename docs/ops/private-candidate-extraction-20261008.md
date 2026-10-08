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
read-time revalidation does not amount to atomic SQL fencing against every
possible microsecond race. A separate transaction-level authorization fence
would be required for stronger concurrency guarantees.

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
