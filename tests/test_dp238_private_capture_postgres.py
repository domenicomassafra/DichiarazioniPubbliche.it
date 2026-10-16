"""DP238 isolated PostgreSQL consumer: real canonical private OCR persistence.

This creates its own short-lived local PostgreSQL cluster and source-use fixture.
No production DB, rights registry, network capture or public route is involved.
"""

from __future__ import annotations

from contextlib import nullcontext
import os
import shutil
import socket
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.capture_pipeline import (
    CaptureBodyStore,
    CapturePipelineStore,
    capture_content,
)
from dichiarazioni_pubbliche.document_scanned_ocr import ScannedPDFOCRParser
from dichiarazioni_pubbliche.ingestion_relevance import (
    append_ingestion_relevance_authority,
    replay_current_ingestion_relevance,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard
from dichiarazioni_pubbliche.rights_registry import (
    PRIVATE_RIGHTS_RECORD_VERSION,
    PrivateRightsRecord,
    RightsSubject,
    rights_subject_fingerprint,
)
from tests.test_dp238_document_extraction import fetched, sha
from tests.test_dp238_scanned_ocr import PDF, _success


ROOT = Path(__file__).resolve().parents[1]
CONTENT_ID = "content:dp238:owner-license-fixture"
URL = "https://source.example/document"


class PrivateCapturePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binaries = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        if any(path is None for path in binaries.values()):
            raise unittest.SkipTest("isolated PostgreSQL binaries unavailable")
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp238-pg-private-")
        cls.root = Path(cls.tmp.name)
        cls.pg_data = cls.root / "pg-data"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.started = False
        try:
            cls._run(
                [
                    binaries["initdb"],
                    "-D",
                    str(cls.pg_data),
                    "--username=postgres",
                    "--auth=trust",
                    "--no-locale",
                    "--encoding=UTF8",
                ]
            )
            cls._run(
                [
                    binaries["pg_ctl"],
                    "-D",
                    str(cls.pg_data),
                    "-l",
                    str(cls.root / "postgres.log"),
                    "-o",
                    f"-F -p {cls.port} -h 127.0.0.1 -k {cls.root}",
                    "-w",
                    "start",
                ]
            )
            cls.started = True
            cls.dsn = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
            cls._run(
                [
                    "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    cls.dsn,
                    "-f",
                    str(ROOT / "db/schema.v1.sql"),
                ]
            )
            cls._run(
                [
                    "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--dbname",
                    cls.dsn,
                    "-f",
                    str(
                        ROOT
                        / "db/migrations/20261007-add-privacy-ingestion-relevance-authority.sql"
                    ),
                ]
            )
            cls.store = CapturePipelineStore(cls.dsn)
            cls.store.run(
                "INSERT INTO content_item (id,canonical_url) VALUES (:'id',:'url')",
                id=CONTENT_ID,
                url=URL,
            )
            # A synthetic relevance authority in this disposable database,
            # distinguishable from any accepted real source/reviewer grant.
            append_ingestion_relevance_authority(
                cls.store.run,
                content_ref=CONTENT_ID,
                canonical_url=URL,
                relevance_reason="OFFICIAL_RECORD",
                reviewer_ref="fixture:synthetic",
                audit_ref="fixture:dp238:disposable",
                reviewed_at="2026-10-16T12:00:00+02:00",
            )
            replay = replay_current_ingestion_relevance(
                cls.store.run,
                content_ref=CONTENT_ID,
                canonical_url=URL,
            )
            if not replay.allowed:
                raise AssertionError(
                    "isolated fixture authority invalid: " + str(replay.blocker)
                )
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def _run(cls, argv):
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=35)
        if proc.returncode:
            raise RuntimeError(f"isolated PG startup/DDL failed: {proc.stderr[-500:]}")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "started", False):
            cls._run(["pg_ctl", "-D", str(cls.pg_data), "-m", "fast", "-w", "stop"])
            cls.started = False
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    @staticmethod
    def _fixture_guard():
        subject = RightsSubject(
            source_family="OWNER_REPOSITORY_TEST",
            locator_kind="URL",
            locator_value=URL,
            content_id=CONTENT_ID,
        )
        record = PrivateRightsRecord(
            id="private-rights:dp238:isolated",
            subject_fingerprint=rights_subject_fingerprint(subject),
            source_family=subject.source_family,
            locator_kind=subject.locator_kind,
            locator_value=URL,
            content_id=CONTENT_ID,
            evidence_id=None,
            transcript_segment_id=None,
            canonical_segment_id=None,
            passage_id=None,
            rights_status="CLEARED",
            rights_receipt_ref="fixture:owner-repository-license",
            permitted_uses=("FETCH", "STORE_BODY", "PARSE_OCR"),
            attribution_requirements=(),
            reviewed_at="2026-10-15T12:00:00+00:00",
            expires_at="2027-10-17T12:00:00+00:00",
            reviewer_ref="fixture:synthetic",
            policy_version="private-use-policy-v1",
            record_visibility="PRIVATE",
            supersedes_id=None,
            version_state="CURRENT",
            record_version=PRIVATE_RIGHTS_RECORD_VERSION,
        )
        return SourceFamilyUseGuard(
            read_current=lambda _: record,
            subject=subject,
            rights_record_id=record.id,
            policy_version=record.policy_version,
            clock=lambda: datetime(2026, 10, 16, 12, tzinfo=timezone.utc),
        )

    def test_private_sql_write_read_replay_and_held_source(self):
        candidate = os.environ.get("DP238_NATIVE_OCR_PDF")
        body = Path(candidate).read_bytes() if candidate else PDF
        self.assertTrue(body.startswith(b"%PDF-"))
        body_store = CaptureBodyStore(self.root / "private-bodies")
        parser = ScannedPDFOCRParser()
        # Patch only this parser instance during the SQL phase. Patching the
        # global subprocess.run would also mock psql and invalidate this test.
        if candidate:
            precomputed = None
        else:
            with patch(
                "dichiarazioni_pubbliche.document_scanned_ocr.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, stdout=_success()),
            ):
                precomputed = parser.parse(fetched(body, media="application/pdf"))
            self.assertEqual(precomputed.status, "SUCCEEDED")

        def run_capture(timestamp):
            with (
                patch.object(parser, "parse", return_value=precomputed)
                if not candidate
                else nullcontext()
            ):
                return capture_content(
                    content_id=CONTENT_ID,
                    url=URL,
                    store=self.store,
                    body_store=body_store,
                    parser=parser,
                    rights_status="CLEARED",
                    source_use_guard=self._fixture_guard(),
                    rights_guard=lambda: None,
                    observed_at=timestamp,
                    fetcher=lambda url, **kw: fetched(body, media="application/pdf"),
                    language="en",
                )

        first = run_capture("2026-10-16T12:00:00+00:00")
        assert first.parse_status == "SUCCEEDED"
        second = run_capture("2026-10-16T12:01:00+00:00")
        self.assertEqual(first.passage_ids, second.passage_ids)
        self.assertEqual(second.capture_state, "EXISTING")
        self.assertEqual(set(second.passage_states), {"EXISTING"})
        readback = self.store.list_passages(first.selected_capture_id)
        self.assertEqual(len(readback), 2)
        for n, item in enumerate(readback, 1):
            meta = item["metadata"]
            self.assertEqual(meta["page_number"], n)
            self.assertEqual(meta["source_sha256"], sha(body))
            self.assertTrue(meta["ocr_word_boxes"])
            self.assertFalse(meta["verbatim_reviewed"])
            self.assertEqual(
                meta["ocr_critical_span_state"], "HELD_INDEPENDENT_REVIEW_REQUIRED"
            )
        self.store.run(
            "UPDATE content_capture SET hold_status='RIGHTS_HOLD' WHERE id=:'id'",
            id=first.selected_capture_id,
        )
        from dichiarazioni_pubbliche.capture_pipeline import CapturePipelineError

        with self.assertRaisesRegex(CapturePipelineError, "DOCUMENT_CAPTURE_HELD"):
            run_capture("2026-10-16T12:02:00+00:00")
        self.assertEqual(len(self.store.list_passages(first.selected_capture_id)), 2)
        # No Statement or Claim Candidate generated, and nothing public written.
        self.assertEqual(
            self.store.run("SELECT count(*) FROM statement_candidate"), "0"
        )
        self.assertEqual(self.store.run("SELECT count(*) FROM claim_candidate"), "0")


if __name__ == "__main__":
    unittest.main()
