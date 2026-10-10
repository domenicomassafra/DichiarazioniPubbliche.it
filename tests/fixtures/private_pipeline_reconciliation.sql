-- Isolated synthetic-only PostgreSQL read-back fixture.
-- Execute with PGOPTIONS=-c\ search_path=<disposable_schema>,public,pg_catalog.
-- Never run without the explicit disposable schema; no real persons/sources.
DO $$ BEGIN
    IF current_schema() IS NULL OR current_schema() !~ '^dp_chain_accept_[a-z0-9_]+$' THEN
        RAISE EXCEPTION 'PRIVATE_CHAIN_DISPOSABLE_SCHEMA_REQUIRED';
    END IF;
END $$;
CREATE TABLE source (LIKE public.source INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE research_collection (LIKE public.research_collection INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE content_item (LIKE public.content_item INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE research_collection_content (LIKE public.research_collection_content INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE research_discovery_manifest (LIKE public.research_discovery_manifest INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE research_discovery_run (LIKE public.research_discovery_run INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE research_discovery_query (LIKE public.research_discovery_query INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE research_discovery_attempt (LIKE public.research_discovery_attempt INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE research_discovery_hit (LIKE public.research_discovery_hit INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE content_capture (LIKE public.content_capture INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE passage (LIKE public.passage INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE statement_candidate (LIKE public.statement_candidate INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE statement_candidate_passage (LIKE public.statement_candidate_passage INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE claim_candidate (LIKE public.claim_candidate INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE private_source_rights_record (LIKE public.private_source_rights_record INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE candidate_match_run (LIKE public.candidate_match_run INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE candidate_match_result (LIKE public.candidate_match_result INCLUDING CONSTRAINTS INCLUDING DEFAULTS);
CREATE TABLE atomic_claim (LIKE public.atomic_claim INCLUDING CONSTRAINTS INCLUDING DEFAULTS);

INSERT INTO source (id,canonical_name,source_type) VALUES
  ('synthetic:source-1','Synthetic origin alpha','OTHER'),
  ('synthetic:source-2','Synthetic origin beta','OTHER');
INSERT INTO research_collection (id,slug,name,scope_text,policy_version)
VALUES ('synthetic:collection','synthetic-collection','Synthetic acceptance','Private fixtures','synthetic-v1');
INSERT INTO content_item (id,source_id,canonical_url,rights_status) VALUES
  ('synthetic:content-1','synthetic:source-1','https://synthetic.example.test/one','CLEARED'),
  ('synthetic:content-2','synthetic:source-2','https://synthetic.example.test/two','UNKNOWN'),
  ('synthetic:content-3','synthetic:source-1','https://synthetic.example.test/three','UNKNOWN');
INSERT INTO research_collection_content
  (collection_id,content_id,inclusion_method,inclusion_version,metadata)
SELECT 'synthetic:collection',id,'MANUAL','fixture-v1','{"capture_authorized":true}'::jsonb FROM content_item;
-- Required source-to-Content lineage: an orphan Hit cannot qualify for
-- private review or unlock its family-matched rights record.
INSERT INTO research_discovery_manifest
  (id,collection_id,manifest_sha256,max_results,max_results_per_host,cost_cap_usd,source_families)
VALUES ('synthetic:manifest-1','synthetic:collection',repeat('d',64),10,10,0,
        '["synthetic-family"]'::jsonb);
INSERT INTO research_discovery_run (id,manifest_id,manifest_sha256,status)
VALUES ('synthetic:run-1','synthetic:manifest-1',repeat('d',64),'COMPLETED');
INSERT INTO research_discovery_query
  (id,manifest_id,ordinal,query_text,source_families,adapter_ids,max_results)
VALUES ('synthetic:query-1','synthetic:manifest-1',0,'Synthetic-only local test',
        '["synthetic-family"]'::jsonb,'["synthetic-adapter"]'::jsonb,10);
INSERT INTO research_discovery_attempt
  (id,run_id,query_id,adapter_id,adapter_version,status)
VALUES ('synthetic:attempt-1','synthetic:run-1','synthetic:query-1',
        'synthetic-adapter','fixture-v1','HEALTHY');
INSERT INTO research_discovery_hit
  (id,run_id,attempt_id,query_id,hit_key,ordinal,canonical_url,source_host,
   source_family,source_id,content_id,disposition)
VALUES
  ('synthetic:hit-1','synthetic:run-1','synthetic:attempt-1','synthetic:query-1',repeat('1',64),0,
   'https://synthetic.example.test/one','synthetic.example.test','synthetic-family','synthetic:source-1','synthetic:content-1','NEW_CONTENT'),
  ('synthetic:hit-2','synthetic:run-1','synthetic:attempt-1','synthetic:query-1',repeat('2',64),1,
   'https://synthetic.example.test/two','synthetic.example.test','synthetic-family','synthetic:source-2','synthetic:content-2','NEW_CONTENT'),
  ('synthetic:hit-3','synthetic:run-1','synthetic:attempt-1','synthetic:query-1',repeat('3',64),2,
   'https://synthetic.example.test/three','synthetic.example.test','synthetic-family','synthetic:source-1','synthetic:content-3','NEW_CONTENT');
INSERT INTO content_capture
  (id,content_id,observed_at,final_url,content_sha256,body_ref,
   retrieval_method,retrieval_version,rights_status,retention_class,hold_status,status)
VALUES
  ('synthetic:capture-1','synthetic:content-1',now(),'https://synthetic.example.test/one',repeat('b',64),
   'private:synthetic-only','HTTP_FETCH','fixture-v1','CLEARED','DURABLE_PRIVATE','NONE','CAPTURED'),
  ('synthetic:capture-2','synthetic:content-2',now(),'https://synthetic.example.test/two',repeat('c',64),
   'private:synthetic-only','HTTP_FETCH','fixture-v1','RIGHTS_HOLD','DURABLE_PRIVATE','RIGHTS_HOLD','CAPTURED');
INSERT INTO passage
  (id,content_id,capture_id,selector_type,start_char,end_char,
   text_sha256,extraction_method,extraction_version)
VALUES
  ('synthetic:passage-1','synthetic:content-1','synthetic:capture-1','TEXT_POSITION',0,16,
   repeat('a',64),'STDLIB_VISIBLE_TEXT','fixture-v1'),
  ('synthetic:passage-2','synthetic:content-2','synthetic:capture-2','TEXT_POSITION',0,16,
   repeat('a',64),'STDLIB_VISIBLE_TEXT','fixture-v1');
INSERT INTO statement_candidate
  (id,content_id,statement_text_hash,normalized_statement,extraction_version,status)
VALUES
  ('synthetic:statement-1','synthetic:content-1',repeat('a',64),'Synthetic neutral test phrase','fixture-v1','CANDIDATE'),
  ('synthetic:statement-2','synthetic:content-2',repeat('a',64),'Synthetic neutral test phrase','fixture-v1','CANDIDATE');
INSERT INTO statement_candidate_passage (statement_candidate_id,passage_id,content_id) VALUES
  ('synthetic:statement-1','synthetic:passage-1','synthetic:content-1'),
  ('synthetic:statement-2','synthetic:passage-2','synthetic:content-2');
INSERT INTO claim_candidate
  (id,statement_candidate_id,content_id,normalized_claim,
   proposed_claim_type,extraction_version,metadata)
VALUES
  ('synthetic:candidate-1','synthetic:statement-1','synthetic:content-1',
   'Synthetic neutral test phrase','HISTORICAL_CLAIM','fixture-v1',
   '{"parent_passage_id":"synthetic:passage-1"}'::jsonb),
  ('synthetic:candidate-2','synthetic:statement-2','synthetic:content-2',
   'Synthetic neutral test phrase','HISTORICAL_CLAIM','fixture-v1',
   '{"parent_passage_id":"synthetic:passage-2"}'::jsonb);
-- This sole CLEARED record exists *only* in the disposable fixture schema.
INSERT INTO private_source_rights_record
  (id,subject_fingerprint,source_family,locator_kind,locator_value,content_id,
   rights_status,rights_receipt_ref,permitted_uses,reviewed_at,reviewer_ref,policy_version)
VALUES
  ('synthetic:rights-1',repeat('f',64),'synthetic-family','URL',
   'https://synthetic.example.test/one','synthetic:content-1',
   'CLEARED','synthetic:fixture-only',
   ARRAY['RESEARCH_CAPTURE_PRIVATE','OMNIROUTE_MODEL_EXTRACTION_PRIVATE']::text[],
   now(),'synthetic:reviewer-fixture-only','synthetic-fixture-v1');
INSERT INTO candidate_match_run
  (id,claim_candidate_id,input_fingerprint,status,result_count)
VALUES ('synthetic:match-1','synthetic:candidate-1',repeat('e',64),'COMPLETED',1);
INSERT INTO candidate_match_result
  (id,run_id,target_type,target_claim_candidate_id,rank,match_class,method,
   lexical_score,disposition,status)
VALUES
  ('synthetic:result-1','synthetic:match-1','CLAIM_CANDIDATE','synthetic:candidate-2',
   1,'RELATED','LEXICAL_TRIGRAM',0.780000,'NO_CLUSTER','CANDIDATE');
