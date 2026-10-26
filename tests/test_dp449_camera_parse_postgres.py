"""Real PostgreSQL issue/readback and immutable-history acceptance for DP-319B."""
from __future__ import annotations

import sys
import os
from unittest.mock import patch
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.camera_parse_authority import CameraParseAuthority, SOURCES  # noqa: E402
from dichiarazioni_pubbliche.reviewer_identity_authority import (  # noqa: E402
    LocalFileReviewerIdentityAuthority, provision_reviewer_credential,
)
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    RightsSubject,
)
from tests import test_rights_registry_postgres as rights_fixture  # noqa: E402


class CameraParsePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pg = rights_fixture.PrivateRightsRegistryPostgresTests
        # PostgreSQL/Homebrew on macOS fails startup in the host locale unless LC_ALL is set.
        with patch.dict(os.environ, {"LC_ALL": "C"}):
            cls.pg.setUpClass()
        cls.url = cls.pg.fresh_database_url
        cls.store = cls.pg.store
        cls.pg._apply_file(
            cls.url,
            ROOT / "db/migrations/20261026-add-camera-private-parse-attestation.sql",
        )
        # The additive migration must be safely repeatable.
        cls.pg._apply_file(
            cls.url,
            ROOT / "db/migrations/20261026-add-camera-private-parse-attestation.sql",
        )
        for content_id, (source_url, digest) in SOURCES.items():
            cls.store.run(
                """INSERT INTO content_item(id,canonical_url)
                   VALUES (:'content_id',:'url');""",
                content_id=content_id, url=source_url,
            )
            cls.store.run(
                """INSERT INTO content_capture (
                   id,content_id,observed_at,final_url,content_sha256,body_ref,
                   retrieval_method,retrieval_version,status
                   ) VALUES (
                   :'capture_id',:'content_id','2026-10-25T00:00:00Z',:'url',
                   :'capture_sha256','private:test-capture',
                   'OFFICIAL_TEXT','dp449-synthetic-fixture','CAPTURED');""",
                capture_id=f"capture:dp449:{content_id.split(':')[-1]}",
                content_id=content_id, url=source_url,
                capture_sha256=digest,
            )
            cls.store.record_rights(
                subject=RightsSubject(
                    source_family="camera_official_stenographic",
                    locator_kind="URL", locator_value=source_url, content_id=content_id,
                ),
                policy_version="dp426-camera-article5-private-text-20261025-v1",
                rights_status="CLEARED",
                rights_receipt_ref="law:633-1941:art5:official-state-acts:text-only",
                permitted_uses=("FETCH", "PARSE_TEXT", "STORE_BODY"),
                reviewed_at="2026-10-25T00:00:00+00:00",
                expires_at="2026-11-24T00:00:00+00:00",
                reviewer_ref="machine:dp426-primary-legal-source-review",
            )

    @classmethod
    def tearDownClass(cls):
        cls.pg.tearDownClass()

    def test_postgres_hmac_authentication_revocation_and_append_only(self):
        now = datetime(2026, 10, 26, 18, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "local-credential-authority"
            provision_reviewer_credential(
                root, credential_id="dp449-camera-agent",
                actor_ref="agent:private-rights-reviewer:camera", key_version="v1",
            )
            authority = LocalFileReviewerIdentityAuthority(root)
            service = CameraParseAuthority(self.store, authority)
            ids = []
            for content_id, (url, digest) in SOURCES.items():
                denied = service.inspect(
                    content_id=content_id, capture_sha256=digest, use="PARSE_TEXT", now=now,
                )
                self.assertFalse(denied["permitted"])
                approved = service.issue(
                    content_id=content_id, capture_sha256=digest,
                    credential_id="dp449-camera-agent", issued_at=now.isoformat(),
                )
                self.assertTrue(approved["permitted"], approved)
                ids.append(approved["receipt_id"])
                self.assertFalse(service.inspect(
                    content_id=content_id, capture_sha256=digest, use="EXCERPT_PUBLIC", now=now,
                )["permitted"])
                self.assertFalse(service.inspect(
                    content_id=content_id, capture_sha256="f" * 64, use="PARSE_TEXT", now=now,
                )["permitted"])
                self.assertFalse(service.inspect(
                    content_id=content_id, capture_sha256=digest, use="PARSE_TEXT",
                    now=datetime(2026, 11, 25, tzinfo=timezone.utc),
                )["permitted"])
            self.assertEqual(
                self.store.run(
                    """SELECT count(*) FROM private_camera_parse_attestation
                       WHERE receipt_id IN (:'one',:'two');""",
                    one=ids[0], two=ids[1],
                ), "2",
            )
            self.assertIn("PRIVATE_RIGHTS_AGENT", self.store.run(
                """SELECT payload->>'issuer_role' FROM private_camera_parse_attestation
                   WHERE receipt_id=:'id';""", id=ids[0],
            ))
            for operation in ("UPDATE", "DELETE", "TRUNCATE"):
                sql = {
                    "UPDATE": "UPDATE private_camera_parse_attestation SET content_id=content_id;",
                    "DELETE": "DELETE FROM private_camera_parse_attestation;",
                    "TRUNCATE": "TRUNCATE private_camera_parse_attestation;",
                }[operation]
                with self.subTest(operation=operation):
                    with self.assertRaises(RuntimeError):
                        self.store.run(sql)
            authority.revoke("dp449-camera-agent")
            for content_id, (_, digest) in SOURCES.items():
                self.assertFalse(service.inspect(
                    content_id=content_id, capture_sha256=digest, use="PARSE_TEXT", now=now,
                )["permitted"])
            self.assertEqual(
                self.store.run("SELECT count(*) FROM private_camera_parse_attestation;"), "2",
            )


if __name__ == "__main__":
    unittest.main()
