"""DP419 persisted canonical media vs Capture context through real loopback HTTP."""
import http.client
import json
import threading
import unittest

from dichiarazioni_pubbliche.studio_local_api import (
    _StudioCaptureReader, StudioLocalReaders, StudioLoopbackServer,
)


class ScopedMediaCaptureHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_studio_capture_selectors_pg import StudioCaptureSelectorPostgresTests
        cls.pg = StudioCaptureSelectorPostgresTests
        cls.pg.setUpClass()
        cls.pg._sql("UPDATE content_item SET duration_ms=4000 WHERE id='content:one'")

    @classmethod
    def tearDownClass(cls):
        cls.pg.tearDownClass()

    def setUp(self):
        self.token="b"*64
        self.server=StudioLoopbackServer(
            0, StudioLocalReaders(None, _StudioCaptureReader(self.pg.dsn), None),
            self.token,
        )
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def send(self, payload, *, token=None, origin=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=5)
        headers={"Content-Type":"application/json"}
        if token is not False:
            headers["Authorization"]="Bearer "+(token or self.token)
        if origin is not None:
            headers["Origin"]=origin
        conn.request("POST","/v1/media/capture-context",json.dumps(payload).encode(),headers)
        response=conn.getresponse()
        status=response.status
        extra=dict(response.getheaders())
        body=json.loads(response.read())
        conn.close()
        return status,body,extra

    def args(self):
        return {"content_id":"content:one","statement_candidate_id":"statement:one",
                "passage_id":"passage:media","capture_id":"capture:aaaaaa",
                "capture_sha256":"a"*64}

    def test_canonical_segment_and_separate_capture_without_forged_seek_or_raw_media(self):
        self.assertEqual(self.send(self.args(),token=False)[0],401)
        self.assertEqual(self.send(self.args(),origin="https://elsewhere.invalid")[0],403)
        status,reply,headers=self.send(self.args())
        self.assertEqual(status,200,reply)
        row=reply["data"]
        self.assertEqual(row["canonical_segment"]["start_ms"],1200)
        self.assertEqual(row["canonical_segment"]["end_ms"],3400)
        self.assertEqual(row["capture"]["id"],"capture:aaaaaa")
        self.assertEqual(row["capture_segment_binding"],"UNPROVEN")
        self.assertFalse(row["seek_authorized"])
        self.assertFalse(row["publication_authority"])
        self.assertEqual(headers["Cache-Control"],"no-store, private")
        for secret in ("https://","SECRET","private_text","body_ref","authorization"):
            self.assertNotIn(secret,json.dumps(reply))

    def test_wrong_sha_wrong_content_and_extra_fields_fail_closed(self):
        self.assertEqual(self.send(self.args()|{"capture_sha256":"bad"})[0],422)
        self.assertEqual(self.send(self.args()|{"publish":True})[0],422)
        self.assertNotEqual(self.send(self.args()|{"content_id":"content:missing"})[0],200)


if __name__=="__main__":
    unittest.main()
