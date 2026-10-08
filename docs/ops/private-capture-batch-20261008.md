# DP-209/210/214/215/304/305 — Private operator Capture batch (2026-10-08)

This is an **engineering acceptance seam**, not a legal opinion, approved Garlasco
manifest, real ingestion receipt or release authorization. No public publication
is enabled or implied.

## Critical-path change

The prior single-item tools/capture_content.py accepted a caller-supplied
rights-status string. The operator path now requires a persisted CURRENT
private_source_rights_record, matching the exact Content, canonical URL and
source family with a reviewer, rights receipt reference, unexpired review,
and explicit RESEARCH_CAPTURE_PRIVATE permission. A record for linking,
quoting or an unknown right does not authorize private capture. Stored
metadata is not independent proof of legal correctness; qualified DP-307
dispositions and source permission remain the owner's responsibility.

The operator rechecks rights and Content authorization before network I/O,
after the HTTP fetch and before capture storage, and before browser rendering,
archiving or metadata enrichment. The separate existing persisted
privacy-ingestion relevance permit remains mandatory.

For collection ingestion tools/capture_research_batch.py provides a bounded,
**default-read-only** operator preflight: 1–25 items, existing ACTIVE
Research Collection, INCLUDED membership explicitly marked
capture_authorized=true, matching existing Content URL and persisted genuine
Discovery Hit from a completed/partial run with ACTIVE manifest. All entries
must pass *before* the first fetch. Each item is revalidated at execution.
The private Capture pipeline then persists immutable Captures and parsed
Passages, with a coarse assertion that Atomic Claim, PUBLISH Finding and
Statement/Claim Candidate counts remain unchanged. This is not a
transactional public mutation lock.

The manifest is canonically SHA-256 hashed, and the operator result reports
that hash without copying private bodies, rights receipts or approval metadata
into the output. The hash is a replay/audit identifier, not a legal receipt.

This batch deliberately stops at **private Passage**: no automated Claim
Candidate extraction, model/provider call, human review, claim promotion,
or public projection. Later DP-211/212/117 steps depend on their separate
gates. No dummy URL or rights record is created by this tool.

## Manifest and operator procedure

Use an operator-provided private JSON file outside Git with exactly these fields:

  version: private-research-capture-batch-v1
  collection_id: the pre-existing reviewed ACTIVE Research Collection ID
  items: an array of 1–25 dictionaries with content_id, canonical_url,
    source_family, rights_record_id

All four values per item must point to **existing, accurately documented**
persisted data. Do not paste credentials or a rights receipt body in the
manifest. The selected rights record must be CURRENT, CLEARED for the
specific RESEARCH_CAPTURE_PRIVATE use, and its Content/URL/source-family
binding must match. The Content rights field must independently be CLEARED;
the collection must not be PAUSED or explicitly capture-forbidden.

Read-only preflight, no fetch / no capture writes:

    python3 tools/capture_research_batch.py --manifest /private/operator/approved-batch.json

Actual private capture, only after source-processing rights and privacy
review are established by the appropriate authorities:

    python3 tools/capture_research_batch.py --manifest /private/operator/approved-batch.json --execute

The paused research:garlasco baseline must not be activated as a shortcut;
the six candidate-only URLs in config/garlasco-public-discovery-leads.v1.json
are not approved Discovery Hits or licenses.

## MiniPC/PostgreSQL read-only evidence, 2026-10-08

- private_source_rights_record: **0 total**, **0** approved for the
  RESEARCH_CAPTURE_PRIVATE use.
- privacy_ingestion_relevance_authority: **0**.
- research:garlasco: **PAUSED**. 18 historical included Content memberships
  with capture_authorized=false; one sampled member has **0** accepted
  persisted Discovery Hits in its collection.
- Globally **50 Content, 30 Atomic Claims, 0 Captures, 0 Passages,
  0 Statement/Claim Candidates**, 2 historic PUBLISH Findings.

Therefore **no real Garlasco Capture/Passage was attempted**, no production
data was modified and no right to capture was presumed.

An additional isolated MiniPC run used a temporary copy of the new Python
package under /tmp/dp-private-capture-canary-20261008, without updating or
restarting the production mirror/services. The new PostgreSQL read methods
successfully inspected the real research:garlasco membership: PAUSED,
capture_authorized=false, 0 accepted Discovery Hits and Content rights UNKNOWN.
The operator capture gate correctly returned
PRIVATE_CAPTURE_CONTENT_RIGHTS_NOT_CLEARED. Claim and public counters stayed
at 30 Atomic Claims and 2 published Findings; both candidate counts stayed 0.
The isolated run is **negative-path runtime proof only**, not proof of a
successful authorized real capture.

Final batch validation: 1,886 Python unit tests PASS; deterministic benchmark
5/5 PASS; false-attribution benchmark 59/59 PASS; contributor and licensing
inventory PASS; Astro check 81 files / 0 diagnostics; design system PASS;
demo-only web build 32 pages. Launch preflight remains NO-GO with 41 blockers.

## Status and remaining authority

- DP-214: only AC-214.3 remains satisfied. AC-214.1/.2/.4/.5/.6/.7/.8
  remain OPEN pending 100 genuine items, 5-source-family rights/roles/
  lineage, persisted discovery/captures/passages/candidates, coverage,
  idempotent replay and MiniPC privacy/public side-effect receipt.
- DP-215.9 remains OPEN until the accepted real corpus has rights, source
  roles, authority scope, lineage and applicability explained *per item*.
- DP-301/304/307, legal Q-306 and DP-703: these technical guards are
  **not** a legal sign-off or an end-to-end privacy acceptance.
- Provider/QA blockers and M7 stay **NO-GO**. No false authority, fake
  candidate, external receipt, secret or auto-publication was generated.

Next admissible real canary: owner/reviewer-approved private capture rights
and relevance tied to one original genuine source, in an authorized active
collection with a persisted real discovery hit. Validate one isolated
Capture→Passage and exact hash/read-back/replay before expanding to 100.
