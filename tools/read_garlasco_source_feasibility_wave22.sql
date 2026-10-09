-- DP-214 source feasibility baseline. Safe to feed to psql -X -qAt.
-- No updates, DDL, provider calls, or private text read. Single SQL snapshot.
BEGIN READ ONLY;
SELECT json_build_object(
    'collection_id', collection.id,
    'collection_status', collection.status,
    'included_members', (
        SELECT count(*) FROM research_collection_content m
        WHERE m.collection_id=collection.id AND m.status='INCLUDED'
    ),
    'rights_unknown_members', (
        SELECT count(*) FROM research_collection_content m
        JOIN content_item item ON item.id=m.content_id
        WHERE m.collection_id=collection.id AND m.status='INCLUDED'
          AND item.rights_status='UNKNOWN'
    ),
    'capture_authorized_members', (
        SELECT count(*) FROM research_collection_content m
        WHERE m.collection_id=collection.id AND m.status='INCLUDED'
          AND m.metadata->>'capture_authorized'='true'
    ),
    'discovery_hit_rows', (
        SELECT count(*) FROM research_discovery_hit h
        JOIN research_discovery_run run ON run.id=h.run_id
        JOIN research_discovery_manifest manifest ON manifest.id=run.manifest_id
        WHERE manifest.collection_id=collection.id
    ),
    'captures', (
        SELECT count(*) FROM content_capture capture
        JOIN research_collection_content m ON m.content_id=capture.content_id
        WHERE m.collection_id=collection.id AND m.status='INCLUDED'
    ),
    'passages', (
        SELECT count(*) FROM passage p
        JOIN research_collection_content m ON m.content_id=p.content_id
        WHERE m.collection_id=collection.id AND m.status='INCLUDED'
    ),
    'statement_candidates', (
        SELECT count(*) FROM statement_candidate s
        JOIN research_collection_content m ON m.content_id=s.content_id
        WHERE m.collection_id=collection.id AND m.status='INCLUDED'
    ),
    'claim_candidates', (
        SELECT count(*) FROM claim_candidate c
        JOIN research_collection_content m ON m.content_id=c.content_id
        WHERE m.collection_id=collection.id AND m.status='INCLUDED'
    ),
    'historical_claims', (
        SELECT count(*) FROM atomic_claim a WHERE a.id LIKE 'claim:garlasco:%'
    )
)::text
FROM research_collection collection WHERE collection.id='research:garlasco';
ROLLBACK;
