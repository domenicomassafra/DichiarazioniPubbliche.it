"""DP-419: private media timeline and capture-retention evidence from real PG.

The base fixture initializes disposable PostgreSQL from the canonical schema;
this module adds read-only time/capture crosschecks without a production DB.
"""

import json
import unittest

from tests.test_studio_capture_selectors_pg import StudioCaptureSelectorPostgresTests
from dichiarazioni_pubbliche.studio_local_api import _StudioCaptureReader
from dichiarazioni_pubbliche.studio_media_selector import (
    inspect_candidate_media_capture_context,
)


class DP419MediaTimelinePostgresTests(StudioCaptureSelectorPostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sql("UPDATE content_item SET duration_ms=4000 WHERE id='content:one'")

    def context(self, **changes):
        params = dict(
            content_id='content:one',
            statement_candidate_id='statement:one',
            passage_id='passage:media',
            capture_id='capture:aaaaaa',
            capture_sha256='a' * 64,
        )
        params.update(changes)
        return inspect_candidate_media_capture_context(_StudioCaptureReader(self.dsn), **params)

    def test_real_persisted_media_interval_capture_retention_without_version_claim(self):
        result = self.context()
        self.assertEqual(result['canonical_segment']['start_ms'], 1200)
        self.assertEqual(result['canonical_segment']['end_ms'], 3400)
        self.assertEqual(result['duration_ms'], 4000)
        self.assertEqual(result['capture']['id'], 'capture:aaaaaa')
        self.assertEqual(result['capture']['content_sha256'], 'a' * 64)
        self.assertEqual(result['capture']['retention_class'], 'POLICY_PENDING')
        self.assertEqual(result['capture']['body_state'], 'STORED_UNVERIFIED')
        self.assertEqual(result['capture_segment_binding'], 'UNPROVEN')
        self.assertFalse(result['seek_authorized'])
        self.assertFalse(result['rights_clearance'])
        self.assertFalse(result['publication_authority'])
        self.assertIn('STUDIO_MEDIA_CAPTURE_SEGMENT_BINDING_UNPROVEN', result['hold_reasons'])
        for forbidden in ('SECRET', 'https://', 'body_ref', 'canonical_text',
                          'private_text', 'normalized_statement', 'bearer_token'):
            self.assertNotIn(forbidden, json.dumps(result))

    def test_cross_content_and_wrong_hash_or_selector_fail_closed(self):
        for changes in (
            {'capture_id': 'capture:bbbbbb', 'capture_sha256': 'b' * 64},
            {'capture_id': 'capture:aaaaaa', 'capture_sha256': 'b' * 64},
            {'passage_id': 'passage:01'},
            {'statement_candidate_id': 'statement:missing'},
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(
                RuntimeError, '^STUDIO_MEDIA_CAPTURE_CONTEXT_NOT_FOUND$',
            ):
                self.context(**changes)

    def test_second_version_on_same_content_is_not_segment_version_proof(self):
        try:
            self._sql("UPDATE content_capture SET retention_class='DURABLE_PRIVATE' "
                      "WHERE id='capture:cccccc'")
            second = self.context(capture_id='capture:cccccc', capture_sha256='c' * 64)
            self.assertEqual(second['capture']['id'], 'capture:cccccc')
            self.assertEqual(second['capture']['retention_class'], 'DURABLE_PRIVATE')
            self.assertEqual(second['capture_segment_binding'], 'UNPROVEN')
            self.assertFalse(second['seek_authorized'])
        finally:
            self._sql("UPDATE content_capture SET retention_class='POLICY_PENDING' "
                      "WHERE id='capture:cccccc'")

    def test_apparent_cleared_rights_and_private_retention_never_grant_seek(self):
        try:
            self._sql("UPDATE content_capture SET rights_status='CLEARED', "
                      "retention_class='DURABLE_PRIVATE' WHERE id='capture:aaaaaa'")
            result = self.context()
            self.assertEqual(result['capture']['rights_status'], 'CLEARED')
            self.assertEqual(result['capture_segment_binding'], 'UNPROVEN')
            self.assertIn('STUDIO_MEDIA_INDEPENDENT_RIGHTS_CHECK_REQUIRED', result['hold_reasons'])
            self.assertFalse(result['seek_authorized'])
        finally:
            self._sql("UPDATE content_capture SET rights_status='UNKNOWN', "
                      "retention_class='POLICY_PENDING' WHERE id='capture:aaaaaa'")

    def test_unknown_duration_or_uncertain_transcript_remains_held(self):
        try:
            self._sql("UPDATE content_item SET duration_ms=NULL WHERE id='content:one'")
            self._sql("UPDATE canonical_transcript_segment SET "
                      "transcript_status='TRANSCRIPT_UNCERTAIN', publication_blocked=true "
                      "WHERE id='canonical:one'")
            result = self.context()
            self.assertIsNone(result['duration_ms'])
            self.assertIn('STUDIO_MEDIA_DURATION_UNKNOWN', result['hold_reasons'])
            self.assertIn('STUDIO_MEDIA_TRANSCRIPT_UNRESOLVED', result['hold_reasons'])
            self.assertFalse(result['seek_authorized'])
        finally:
            self._sql("UPDATE content_item SET duration_ms=4000 WHERE id='content:one'")
            self._sql("UPDATE canonical_transcript_segment SET "
                      "transcript_status='RESOLVED', publication_blocked=false "
                      "WHERE id='canonical:one'")

    def test_duration_mismatch_is_rejected_before_operator_seek(self):
        try:
            self._sql("UPDATE content_item SET duration_ms=2000 WHERE id='content:one'")
            with self.assertRaisesRegex(ValueError, '^STUDIO_MEDIA_DURATION_RANGE_INVALID$'):
                self.context()
        finally:
            self._sql("UPDATE content_item SET duration_ms=4000 WHERE id='content:one'")

    def test_purged_capture_is_visible_as_metadata_but_held(self):
        try:
            self._sql("""
                UPDATE content_capture SET status='PURGED_BODY', body_ref=NULL,
                    body_purged_at='2026-10-10T12:00:00Z',
                    purge_reason='SECRET private legal note',
                    purge_receipt='{"token":"SECRET"}'::jsonb
                WHERE id='capture:aaaaaa';
            """)
            result = self.context()
            self.assertEqual(result['capture']['body_state'], 'PURGED')
            self.assertIn('STUDIO_MEDIA_CAPTURE_PURGED', result['hold_reasons'])
            self.assertNotIn('SECRET', json.dumps(result))
        finally:
            self._sql("""
                UPDATE content_capture SET status='CAPTURED',
                    body_ref='/private/SECRET-body', body_purged_at=NULL,
                    purge_reason=NULL, purge_receipt='{}'::jsonb
                WHERE id='capture:aaaaaa';
            """)

    def test_false_purge_timestamp_cannot_become_trusted_capture_provenance(self):
        try:
            self._sql("UPDATE content_capture SET body_purged_at='2026-10-10T12:00:00Z' "
                      "WHERE id='capture:aaaaaa'")
            with self.assertRaisesRegex(ValueError, '^STUDIO_MEDIA_CAPTURE_PURGE_INVALID$'):
                self.context()
        finally:
            self._sql("UPDATE content_capture SET body_purged_at=NULL "
                      "WHERE id='capture:aaaaaa'")


if __name__ == '__main__':
    unittest.main()
