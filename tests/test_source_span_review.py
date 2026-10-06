from __future__ import annotations

import hashlib
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.context_integrity import assess_context_integrity  # noqa: E402
from dichiarazioni_pubbliche.source_span_review import (  # noqa: E402
    SourceSpanReviewStore,
    context_review_freshness,
    transcript_review_freshness,
)
from dichiarazioni_pubbliche.transcript_contract import (  # noqa: E402
    VerbatimEvidenceMethod,
    reconcile_candidates,
)


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class SourceSpanReviewPostgresTests(unittest.TestCase):
    tmp: tempfile.TemporaryDirectory
    data_dir: Path
    database_url: str
    server_started = False

    @classmethod
    def _command(cls, args, *, input_text=None, check=True):
        proc = subprocess.run(
            args,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        if check and proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout).strip())
        return proc

    @classmethod
    def _psql(cls, sql: str, *, check=True):
        proc = cls._command(
            [
                shutil.which("psql") or "psql",
                "-X",
                "-qAt",
                "-v",
                "ON_ERROR_STOP=1",
                "--dbname",
                cls.database_url,
            ],
            input_text=sql,
            check=check,
        )
        return proc.stdout.strip(), proc

    @classmethod
    def _apply(cls, path: Path) -> None:
        cls._command(
            [
                shutil.which("psql") or "psql",
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "--dbname",
                cls.database_url,
                "-f",
                str(path),
            ]
        )

    @classmethod
    def setUpClass(cls):
        required = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "psql")}
        missing = [name for name, path in required.items() if path is None]
        if missing:
            raise unittest.SkipTest("ephemeral PostgreSQL requires: " + ", ".join(missing))
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp217-dp220-source-span-review-")
        root = Path(cls.tmp.name)
        cls.data_dir = root / "data"
        port = _free_tcp_port()
        try:
            cls._command(
                [
                    required["initdb"] or "initdb",
                    "-D",
                    str(cls.data_dir),
                    "--username=postgres",
                    "--auth=trust",
                    "--encoding=UTF8",
                    "--no-locale",
                ]
            )
            cls._command(
                [
                    required["pg_ctl"] or "pg_ctl",
                    "-D",
                    str(cls.data_dir),
                    "-l",
                    str(root / "postgres.log"),
                    "-o",
                    f"-F -p {port} -h 127.0.0.1 -k {root}",
                    "-w",
                    "start",
                ]
            )
            cls.server_started = True
            admin = f"postgresql://postgres@127.0.0.1:{port}/postgres"
            cls.database_url = admin
            cls._psql("CREATE DATABASE source_span_review;")
            cls.database_url = f"postgresql://postgres@127.0.0.1:{port}/source_span_review"
            cls._apply(ROOT / "db" / "schema.v1.sql")
            migration = ROOT / "db" / "migrations" / "20261006-add-source-span-review-ledgers.sql"
            cls._apply(migration)
            cls._apply(migration)

            raw_text = "No, non aumenteremo le tasse."
            raw_hash = hashlib.sha256(raw_text.encode()).hexdigest()
            cls._psql(
                f"""
                INSERT INTO content_item(id, canonical_url)
                VALUES ('content:review', 'https://example.test/review');
                INSERT INTO transcript_variant(
                    id,content_id,provider_id,source_kind,raw_text_sha256,raw_text
                ) VALUES (
                    'variant:asr','content:review','fixture-asr','ASR','{raw_hash}',
                    '{raw_text}'
                );
                INSERT INTO transcript_segment(
                    id,variant_id,segment_index,start_ms,end_ms,text
                ) VALUES (
                    'segment:asr','variant:asr',0,1000,4000,'{raw_text}'
                );
                """
            )
            cls.store = SourceSpanReviewStore(cls.database_url)
            cls.raw_text = raw_text
            cls.raw_hash = raw_hash
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "server_started", False):
            subprocess.run(
                [
                    shutil.which("pg_ctl") or "pg_ctl",
                    "-D",
                    str(cls.data_dir),
                    "-m",
                    "fast",
                    "-w",
                    "stop",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            cls.server_started = False
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_human_audio_review_is_persisted_and_derived_without_mutating_source(self):
        review = self.store.record_transcript_review(
            content_id="content:review",
            source_variant_id="variant:asr",
            source_segment_id="segment:asr",
            start_ms=1000,
            end_ms=4000,
            reviewed_text="No, non aumenteremo le tasse.",
            decision="APPROVED",
            reviewer_ref="reviewer:fixture",
            reason_codes=("LISTENED_TO_AUDIO",),
        )
        candidate = review.as_transcript_candidate()
        reconciled = reconcile_candidates((candidate,))
        self.assertTrue(reconciled.verbatim_eligible)
        self.assertEqual(
            reconciled.verbatim_evidence_method,
            VerbatimEvidenceMethod.HUMAN_AUDIO_VERIFIED,
        )
        source, _ = self._psql(
            "SELECT source_kind || '|' || raw_text_sha256 FROM transcript_variant WHERE id='variant:asr';"
        )
        self.assertEqual(source, f"ASR|{self.raw_hash}")
        count, _ = self._psql(
            "SELECT count(*) FROM transcript_verbatim_review_event WHERE id='"
            + review.id
            + "';"
        )
        self.assertEqual(count, "1")

    def test_transcript_review_stales_on_version_segment_or_range_change(self):
        review = self.store.record_transcript_review(
            content_id="content:review",
            source_variant_id="variant:asr",
            source_segment_id="segment:asr",
            start_ms=1000,
            end_ms=4000,
            reviewed_text=self.raw_text,
            decision="APPROVED",
            reviewer_ref="reviewer:freshness",
        )
        segment_sha = hashlib.sha256(self.raw_text.encode()).hexdigest()
        self.assertTrue(
            transcript_review_freshness(
                review,
                source_variant_sha256=self.raw_hash,
                source_segment_sha256=segment_sha,
                start_ms=1000,
                end_ms=4000,
            ).current
        )
        stale = transcript_review_freshness(
            review,
            source_variant_sha256="f" * 64,
            source_segment_sha256=segment_sha,
            start_ms=1000,
            end_ms=3999,
        )
        self.assertFalse(stale.current)
        self.assertIn("TRANSCRIPT_SOURCE_VERSION_CHANGED", stale.blockers)
        self.assertIn("TRANSCRIPT_REVIEW_RANGE_CHANGED", stale.blockers)

    def test_reviewed_text_preserves_exact_whitespace_in_derived_representation(self):
        reviewed_text = "  No, non aumenteremo le tasse.  "
        review = self.store.record_transcript_review(
            content_id="content:review",
            source_variant_id="variant:asr",
            source_segment_id="segment:asr",
            start_ms=1000,
            end_ms=4000,
            reviewed_text=reviewed_text,
            decision="APPROVED",
            reviewer_ref="reviewer:whitespace",
        )
        self.assertEqual(review.reviewed_text, reviewed_text)
        self.assertEqual(review.as_transcript_candidate().text, reviewed_text)
        self.assertEqual(
            review.reviewed_text_sha256,
            hashlib.sha256(reviewed_text.encode()).hexdigest(),
        )

    def test_context_review_persists_hashes_only_and_stales_on_binding_change(self):
        source = "Aumenterete le tasse? No."
        quote = "No."
        start = source.index(quote)
        assessment = assess_context_integrity(
            source_text=source,
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            quote_start=start,
            quote_end=start + len(quote),
        )
        review = self.store.record_context_review(
            record_id="statement:context-review",
            assessment=assessment,
            decision="APPROVED",
            reviewer_ref="reviewer:context",
            reason_codes=("QUESTION_CONTEXT_RETAINED",),
        )
        self.assertTrue(context_review_freshness(review, assessment).current)
        changed = dict(assessment.to_metadata())
        changed["context_sha256"] = "0" * 64
        stale = context_review_freshness(review, changed)
        self.assertFalse(stale.current)
        self.assertIn("CONTEXT_WINDOW_CHANGED", stale.blockers)
        encoded, _ = self._psql(
            "SELECT row_to_json(r)::text FROM context_integrity_review_event r WHERE id='"
            + review.id
            + "';"
        )
        self.assertNotIn(source, encoded)
        self.assertNotIn("Aumenterete", encoded)

    def test_both_review_ledgers_are_append_only(self):
        transcript_review = self.store.record_transcript_review(
            content_id="content:review",
            source_variant_id="variant:asr",
            source_segment_id="segment:asr",
            start_ms=1000,
            end_ms=4000,
            reviewed_text=self.raw_text,
            decision="APPROVED",
            reviewer_ref="reviewer:append-only",
        )
        _, transcript_update = self._psql(
            "UPDATE transcript_verbatim_review_event SET decision='REJECTED' WHERE id='"
            + transcript_review.id
            + "';",
            check=False,
        )
        self.assertNotEqual(transcript_update.returncode, 0)
        self.assertIn("append-only", transcript_update.stderr)

        source = "Se il dato cambia, rivaluteremo."
        assessment = assess_context_integrity(
            source_text=source,
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            quote_start=0,
            quote_end=len(source),
        )
        context_review = self.store.record_context_review(
            record_id="statement:append-only",
            assessment=assessment,
            decision="APPROVED",
            reviewer_ref="reviewer:append-only",
        )
        _, context_delete = self._psql(
            "DELETE FROM context_integrity_review_event WHERE id='" + context_review.id + "';",
            check=False,
        )
        self.assertNotEqual(context_delete.returncode, 0)
        self.assertIn("append-only", context_delete.stderr)


if __name__ == "__main__":
    unittest.main()
