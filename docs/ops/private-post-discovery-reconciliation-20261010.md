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
