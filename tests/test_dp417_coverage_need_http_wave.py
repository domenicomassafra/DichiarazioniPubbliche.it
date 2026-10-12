"""Authenticated loopback HTTP→PostgreSQL Coverage Need queue acceptance."""
from __future__ import annotations

import json

from tests.test_studio_auth_vertical_next import StudioAuthVerticalNextTests


class CoverageNeedQueueHttpWaveTests(StudioAuthVerticalNextTests):
    def test_private_coverage_need_auth_source_scrub_and_stale_snapshot(self):
        path = "/v1/discovery/coverage-queue"
        body = {"collection_id": "collection:one", "limit": 1}
        self.pg.store.run("""
            INSERT INTO coverage_need(id,collection_id,need_type,requirement_kind,
                requirement_fingerprint,question,status,attempt_count,max_attempts)
            VALUES ('need:http:a','collection:one','ORIGINAL_MEDIA','ROLE_ANY',
                    repeat('d',64),'PRIVATE_UNREVIEWED_QUESTION','OPEN',0,2),
                   ('need:http:b','collection:one','EARLIER_VERSION','ROLE_ANY',
                    repeat('e',64),'PRIVATE_SOURCE_TEXT','SEARCHING',1,2);
        """)
        try:
            self.assertEqual(self.request(path, body, auth=False)[0], 401)
            self.assertEqual(self.request(path, body, origin="https://evil.invalid")[0], 403)
            code, receipt, headers = self.request(path, body)
            self.assertEqual(code, 200, receipt)
            page = receipt["data"]
            self.assertEqual(page["rows"][0]["need_id"], "need:http:a")
            self.assertEqual(page["next_after_need_id"], "need:http:a")
            self.assertEqual(headers["Cache-Control"], "no-store, private")
            self.assertFalse(page["publication_authority"])
            self.assertFalse(page["rights_clearance"])
            self.assertNotIn("PRIVATE_UNREVIEWED_QUESTION", json.dumps(receipt))
            self.assertNotIn("PRIVATE_SOURCE_TEXT", json.dumps(receipt))
            next_body = body | {"after_need_id": page["next_after_need_id"],
                                "expected_snapshot_sha256": page["snapshot_sha256"]}
            self.assertEqual(self.request(path, next_body)[0], 200)
            self.assertEqual(self.request(path, body | {"publish": True})[0], 422)
            self.assertEqual(self.request(path, body | {"after_need_id": "need:http:a"})[0], 422)
            self.pg.store.run("""
                UPDATE coverage_need SET status='BLOCKED',blocker_code='RIGHTS_HOLD',
                  resolved_at=now() WHERE id='need:http:b';
            """)
            self.assertEqual(self.request(path, next_body)[0], 422)
            new_code, new_receipt, _ = self.request(path, {"collection_id":"collection:one"})
            self.assertEqual(new_code, 200)
            self.assertIn("SOURCE_RIGHTS_HOLD", new_receipt["data"]["rows"][1]["blockers"])
        finally:
            self.pg.store.run("DELETE FROM coverage_need WHERE id LIKE 'need:http:%'")
