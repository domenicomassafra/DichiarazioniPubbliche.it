# Private post-discovery reconciliation — 2026-10-10

Status: code and isolated MiniPC acceptance PASS; production intake HOLD.
This is an operator-only, metadata-only READ ONLY reconciliation over stored
private research lineage. It does not capture, call providers, authorize human
review, verify a speaker, promote a Claim, publish, or clear rights.

## Day-batch operating sequence

1. Discovery creates the Content, source ID, Discovery Hit, and collection
   membership. A missing source ID must never be guessed from a host/title.
2. The existing capture_research_batch.py operator command preflights
   a reviewed capture manifest; --execute requires its own rights grants and
   network/private-write authorization.
3. The existing extract_research_candidates.py operator command preflights
   Passage->private Candidate extraction; --execute additionally requires
   immutable source-byte verification, current private rights and provider
   cost authority. No model call occurs in reconciliation.
4. Existing match_claim_candidate.py writes DP-212 pairwise comparisons.
   Its persisted cross-source results remain unreviewed proposals.
5. Run the new private inspection command from the permitted operator host:

        python3 tools/inspect_private_pipeline.py --database-url dichiarazioni_pubbliche --collection-id COLLECTION_ID --summary

   Omit --summary for ID-only blockers and matched link IDs. Use --limit 1..25
   and --after-content-id for bounded keyset traversal. The script accesses
   private PostgreSQL credentials; never expose it on public HTTP.

## Source-to-review contract

Source IDs must match a persisted original Discovery Hit, its canonical URL
and Content. A current, not superseded private rights record must match the
same source family, exact URL and Content and permit both private uses.
The Source->Capture->Passage->StatementCandidate->ClaimCandidate chain is
traced through stored foreign keys, latest Capture freshness, exactly one
written Passage, matching parent ID, Statement/Passage hash equality, known
capture rights/retention/body reference, and explicit collection membership.
One stored DP-212 match may display a cross-source proposal only when its
source differs and its persisted result is pending, with currentness warnings.

The output contains IDs/status/counts only, never URLs, private text, speaker
identity, prompt, tokens, source bodies or provider responses. Private
review-ready is NOT reviewer approval, promotion rights, reliable attribution,
or permission to publish. Byte/selector proof remains delegated to the
existing DP-211/DP-216 preflight; human timed-speech proof remains DP-217/218.
More than 24 candidates in a Content is an explicit pagination HOLD.

## Authoritative MiniPC readback (2026-10-10)

Production read-only census: 1 collection, 18 INCLUDED members, 50 Contents,
0 Capture, 0 Passage, 0 StatementCandidate, 0 ClaimCandidate, 0 matching
runs/results, and 0 private source rights records. The scoped metadata reader
returned 18 HOLDS, 0 privately review-ready, 0 persisted cross-source links;
blockers include missing approved source/rights/capture/passage/candidate.
Production is not falsely marked complete.

The synthetic-only isolated PostgreSQL acceptance used the disposable fixture
at tests/fixtures/private_pipeline_reconciliation.sql and a scoped schema
on the MiniPC. It verified: a RIGHTS_CLEARED synthetic chain privately
review-ready, a rights-held synthetic chain still held, a discovery-only
Content held, an unreviewed persisted RELATED link across two synthetic
sources, idempotent readbacks and keyset pagination. Review/promotion/public
authority remained false. Two additional negative acceptance mutations inside
the synthetic schema proved that **revoked private rights immediately force a
HOLD**, and that an **additional newer Capture invalidates the old Passage
chain**. The schema was dropped after acceptance (zero schema remnants
verified); no production rows were changed.

Remaining real gates: source mapping, owner-reviewed rights, ingestion
relevance, capture, provider extraction/budget, independent source-byte
verification, review of match and speaker provenance. No new tickets or
legal/owner/provider grants were fabricated.

## 2026-10-10 local Discovery-lineage correction (pending MiniPC proof)

The initial private reconciliation counted bare `research_discovery_hit` rows
to infer Discovery presence and the source family eligible for current rights.
That count could include a failed attempt or superseded manifest with matching
Content/URL/Source, falsely labeling a synthetic complete chain as
`REVIEW_READY_PRIVATE_NOT_APPROVED`. The SQL now shares the exact verified
Discovery chain with private Capture: matching run/attempt/query/manifest,
`HEALTHY` adapter attempt, allowed family and adapter, successful run, active
manifest, bound manifest hash, matching collection/Content/URL and exact
persisted Source ID. The rights family must be among these verified hits.

The negative SQL-contract test was RED before correction and GREEN afterward;
the disposable PostgreSQL fixture includes matching manifest/run/query/attempt
records. This is local code and fixture proof only: the revised SQL has not
received a new MiniPC readback, no disposable schema was executed there, and
no real Discovery/Capture/Passage/Candidate rights or corpus were created.
DP-214's 100-item acceptance and DP-215.9 remain open.

## 2026-10-10 local PostgreSQL source-to-Candidate negative acceptance

`tests/test_private_pipeline_reconciliation_postgres.py` executes the real
read-only reconciliation query against an independently initialized, disposable
PostgreSQL server. The accepted synthetic Source→Discovery Hit→Capture→Passage→
Statement Candidate→Claim Candidate chain remains **private review-ready only**.
The same persisted chain becomes a HOLD if its attempt fails, the manifest is
superseded, the run digest changes, the adapter is outside the approved query
scope or the Hit's Source ID differs from the Content's Source ID. These five
negative cases verify the earlier shared-provenance correction at SQL level.

The SQL exercise exposed two more incorrect positive states, reproduced RED
before correction: `statement_candidate.status='REJECTED'` allowed a pending
Claim Candidate to appear review-ready, and a private rights record dated
*after the current transaction* counted as reviewed permission. The reader now
accepts only `CANDIDATE` or `APPROVED` parent Statement lifecycle status and
requires `rights.reviewed_at <= statement_timestamp()`. `HELD`, `REJECTED` and
`SUPERSEDED` parents require repair/review; the source or its old Capture is not
silently promoted. A still-pending Claim under an already-APPROVED Statement
may be reviewed privately but gains no publication authority.

The isolated SQL tests were **RED (2 of 4 failing)** before the targeted fix
and **GREEN (4/4 PASS)** afterward. The test server and synthetic contents
were deleted by teardown. Source-specific Senato OpenData CC BY 3.0 sitting
metadata and separately licensed CC BY 4.0 AKN speech corpus remain held:
their documented authentic format/readback proof cannot provide a Source
family/rights grant, model permission, Person attribution or quote approval.
No official/live fetch or MiniPC/production database write was performed.
DP-209..213 implementation statuses are unchanged, DP-214 original AC-214.3
remains the only closed 214 acceptance, DP-215.9 remains open, and this local
test does not replace the required current MiniPC SQL readback.
