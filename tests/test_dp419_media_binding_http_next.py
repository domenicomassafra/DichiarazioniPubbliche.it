"""PG operator-attested Capture/Segment revocation -> signed-free read-only Studio."""
import http.client
import json
import threading
import unittest

from dichiarazioni_pubbliche.studio_local_api import (
    _StudioCaptureReader, StudioLocalReaders, StudioLoopbackServer,
)


class MediaBindingLoopbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_dp419_media_capture_binding_pg_next import DP419MediaCaptureBindingPgNext
        cls.pg=DP419MediaCaptureBindingPgNext
        cls.pg.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.pg.tearDownClass()

    def setUp(self):
        self.fixture=self.pg("test_persisted_binding_exact_source_and_replay_after_restart")
        self.fixture.setUp()
        self.fixture.claim()
        self.token="d"*64
        self.server=StudioLoopbackServer(
            0,StudioLocalReaders(None,_StudioCaptureReader(self.pg.dsn),None),self.token,
        )
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

    def call(self,body,*,token=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=5)
        headers={"Content-Type":"application/json"}
        if token is not False:
            headers["Authorization"]="Bearer "+(token or self.token)
        conn.request("POST","/v1/media/binding",json.dumps(body).encode(),headers)
        r=conn.getresponse();status=r.status;data=json.loads(r.read())
        conn.close()
        return status,data

    def test_live_postgres_attested_binding_read_and_rights_withdrawal(self):
        self.assertEqual(self.call({"binding_id":"media-binding:one"},token=False)[0],401)
        result=self.call({"binding_id":"media-binding:one"})
        self.assertEqual(result[0],200,result)
        row=result[1]["data"]
        self.assertEqual(row["capture_id"],"capture:aaaaaa")
        self.assertEqual(row["canonical_segment_id"],"canonical:one")
        self.assertEqual(row["capture_segment_binding"],"OPERATOR_ATTESTED_METADATA_ONLY")
        self.assertFalse(row["seek_authorized"])
        self.assertFalse(row["rights_clearance"])
        self.assertFalse(row["publication_authority"])
        self.fixture._sql("UPDATE content_capture SET rights_status='REVOKED' "
                          "WHERE id='capture:aaaaaa';")
        try:
            after=self.call({"binding_id":"media-binding:one"})
            self.assertEqual(after[0],200,after)
            self.assertIn("CAPTURE_RIGHTS_REVOKED",after[1]["data"]["hold_reasons"])
            self.assertFalse(after[1]["data"]["seek_authorized"])
        finally:
            self.fixture._sql("UPDATE content_capture SET rights_status='UNKNOWN' "
                              "WHERE id='capture:aaaaaa';")

    def test_cross_scope_and_extra_json_never_expose_source(self):
        self.assertEqual(self.call({"binding_id":"not:existent"})[0],503)
        self.assertEqual(self.call({"binding_id":"media-binding:one","force":True})[0],422)
        self.assertEqual(self.call({"binding_id":"bad' OR true --"})[0],422)


if __name__=="__main__":
    unittest.main()
