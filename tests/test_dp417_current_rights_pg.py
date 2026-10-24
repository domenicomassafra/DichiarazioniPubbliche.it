"""DP-417: the private Inbox must read exact CURRENT rights, including revocation.

This is a synthetic rights decision in a disposable PostgreSQL schema, never
an operator attestation or rights clearance for the production corpus.
"""

import http.client
import json
import threading
import unittest

from dichiarazioni_pubbliche.studio_local_api import (
    StudioLocalReaders, StudioLoopbackServer, _StudioQueueReader,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject
from dichiarazioni_pubbliche.studio_discovery_inbox_workflow import DiscoveryInboxWorkflow
from tests import test_studio_discovery_triage_schema as pg_schema
from tools import dp244_refresh_cycle_canary as official


class CurrentRightsInboxPostgresTests(unittest.TestCase):
    def test_exact_metadata_rights_replay_and_revocation(self):
        pg = pg_schema.DiscoveryTriageSchemaTests
        pg.setUpClass()
        try:
            prefix = "dp326:rights"
            collection = prefix + ":collection"
            content = prefix + ":content"
            family = official.SOURCE_FAMILY
            url = official.CURRENT_URL
            pg.require_sql(f"""
                INSERT INTO source (id, canonical_name, source_type)
                VALUES ('{official.SOURCE_ID}','Senato fixture','OFFICIAL');
                INSERT INTO content_item
                    (id, source_id, canonical_url, title, rights_status)
                VALUES ('{content}','{official.SOURCE_ID}','{url}',
                        'Fixture only','CLEARED');
                INSERT INTO research_collection (id,slug,name,scope_text,policy_version)
                VALUES ('{collection}','dp326-private','Fixture','PRIVATE','v1');
                INSERT INTO research_collection_content
                    (collection_id,content_id,inclusion_method,inclusion_version)
                VALUES ('{collection}','{content}','MANUAL','v1');
                INSERT INTO research_discovery_manifest
                    (id,collection_id,manifest_sha256,max_results,
                     max_results_per_host,cost_cap_usd,source_families)
                VALUES ('{prefix}:manifest','{collection}',repeat('a',64),
                        2,2,0,'["{family}"]');
                INSERT INTO research_discovery_query
                    (id,manifest_id,ordinal,query_text,source_families,
                     adapter_ids,max_results)
                VALUES ('{prefix}:query','{prefix}:manifest',0,'Fixture query',
                        '["{family}"]','["official-pinned"]',2);
                INSERT INTO research_discovery_run
                    (id,manifest_id,manifest_sha256,status)
                VALUES ('{prefix}:run','{prefix}:manifest',repeat('a',64),'COMPLETED');
                INSERT INTO research_discovery_attempt
                    (id,run_id,query_id,adapter_id,adapter_version,status)
                VALUES ('{prefix}:attempt','{prefix}:run','{prefix}:query',
                        'official-pinned','fixture-v1','HEALTHY');
                INSERT INTO research_discovery_hit
                    (id,run_id,attempt_id,query_id,hit_key,ordinal,
                     canonical_url,source_host,source_family,source_id,
                     content_id,disposition)
                VALUES ('{prefix}:hit','{prefix}:run','{prefix}:attempt',
                        '{prefix}:query',repeat('b',64),0,'{url}',
                        'raw.githubusercontent.com','{family}',
                        '{official.SOURCE_ID}','{content}','EXISTING_CONTENT');
            """, database=pg.fresh_url)
            inbox = DiscoveryInboxWorkflow(PsqlRuntime(database_url=pg.fresh_url))
            registry = PrivateRightsRegistryStore(database_url=pg.fresh_url)
            subject = RightsSubject(
                source_family=family, locator_kind="URL",
                locator_value=url, content_id=content,
            )

            def read():
                return inbox.list_rows(collection_id=collection)["rows"][0]

            def studio_http(*, authorized=True):
                token = "a" * 64  # Test-only token; no privileged reviewer session.
                readers = StudioLocalReaders(None, None, None,
                                             queues=_StudioQueueReader(pg.fresh_url))
                server = StudioLoopbackServer(0, readers, token)
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    connection = http.client.HTTPConnection(
                        "127.0.0.1", server.server_port, timeout=8,
                    )
                    body = json.dumps({"collection_id": collection, "limit": 1})
                    headers = {"Content-Type": "application/json"}
                    if authorized:
                        headers["Authorization"] = f"Bearer {token}"
                    try:
                        connection.request("POST", "/v1/discovery/inbox", body, headers)
                        response = connection.getresponse()
                        return response.status, json.loads(response.read())
                    finally:
                        connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    worker.join(timeout=5)

            self.assertEqual(studio_http(authorized=False)[0], 401)
            empty = read()
            self.assertIn("PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED", empty["blockers"])
            rights_args = dict(
                subject=subject, policy_version="fixture-private-v1",
                rights_status="CLEARED",
                rights_receipt_ref="fixture:licensed-metadata",
                permitted_uses=("DISCOVER_METADATA",),
                reviewed_at="2026-10-24T09:00:00+00:00",
                expires_at="2027-01-24T09:00:00+00:00",
                reviewer_ref="fixture:non-operator",
            )
            current = registry.record_rights(**rights_args)
            self.assertEqual(registry.record_rights(**rights_args).id, current.id)
            approved = read()
            self.assertTrue(approved["source_metadata_rights_current"])
            self.assertNotIn("PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED", approved["blockers"])
            self.assertFalse(approved["action_authorized"])
            self.assertFalse(approved["publication_authority"])
            self.assertFalse(approved["rights_clearance"])
            status, reply = studio_http()
            self.assertEqual(status, 200, reply)
            self.assertTrue(reply["data"]["rows"][0]["source_metadata_rights_current"])
            self.assertNotIn("fixture:licensed-metadata", json.dumps(reply))
            registry.record_rights(
                subject=subject, policy_version="fixture-private-v1",
                rights_status="REVOKED", rights_receipt_ref="fixture:revocation",
                supersedes_record_id=current.id,
            )
            revoked = read()
            self.assertFalse(revoked["source_metadata_rights_current"])
            self.assertIn("PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED", revoked["blockers"])
            self.assertNotEqual(approved["snapshot_sha256"], revoked["snapshot_sha256"])
            status, reply = studio_http()
            self.assertEqual(status, 200, reply)
            self.assertFalse(reply["data"]["rows"][0]["source_metadata_rights_current"])
            self.assertFalse(reply["data"]["publication_authority"])
        finally:
            pg.tearDownClass()


if __name__ == "__main__":
    unittest.main()
