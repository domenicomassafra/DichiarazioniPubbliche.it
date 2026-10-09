import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'poc'))

from dichiarazioni_pubbliche.studio_media_selector import inspect_candidate_media_selector  # noqa: E402


def media_row(**changes):
    return {
        'statement_candidate_id': 'statement:one',
        'candidate_content_id': 'content:one', 'candidate_status': 'CANDIDATE',
        'passage_id': 'passage:media', 'passage_content_id': 'content:one',
        'passage_capture_id': None, 'selector_type': 'MEDIA_SEGMENT_REF',
        'text_sha256': 'f' * 64, 'passage_segment_id': 'canonical:one',
        'segment_id': 'canonical:one', 'segment_content_id': 'content:one',
        'segment_index': 2, 'start_ms': 1200, 'end_ms': 3400,
        'transcript_status': 'RESOLVED', 'publication_blocked': False,
        'private_text': 'SECRET TRANSCRIPT',
        'metadata': {'bearer_token': 'VERY PRIVATE'}, **changes,
    }


class Store:
    _default = object()

    def __init__(self, row=_default, error=None):
        self.row = media_row() if row is self._default else row
        self.error = error
        self.calls = []

    def read_candidate_media_selector(self, *, content_id, statement_candidate_id, passage_id):
        self.calls.append((content_id, statement_candidate_id, passage_id))
        if self.error:
            raise self.error
        return self.row


class StudioMediaSelectorTests(unittest.TestCase):
    def request(self, store):
        return inspect_candidate_media_selector(
            store, content_id='content:one', statement_candidate_id='statement:one',
            passage_id='passage:media',
        )

    def test_exact_persisted_candidate_to_canonical_media_time_range_is_private(self):
        store = Store()
        result = self.request(store)
        self.assertEqual(store.calls, [('content:one', 'statement:one', 'passage:media')])
        self.assertEqual(result['canonical_segment']['start_ms'], 1200)
        self.assertEqual(result['canonical_segment']['end_ms'], 3400)
        self.assertEqual(result['canonical_segment']['id'], 'canonical:one')
        self.assertEqual(result['statement_candidate_id'], 'statement:one')
        self.assertFalse(result['publication_authority'])
        self.assertFalse(result['rights_clearance'])
        self.assertFalse(result['attribution_authority'])
        for forbidden in ('SECRET', 'VERY PRIVATE', 'private_text', 'metadata'):
            self.assertNotIn(forbidden, json.dumps(result))

    def test_cross_source_missing_bad_selector_and_invalid_time_fail_closed(self):
        tampered = (
            {'candidate_content_id': 'content:other'},
            {'passage_content_id': 'content:other'},
            {'segment_content_id': 'content:other'},
            {'statement_candidate_id': 'statement:foreign'},
            {'passage_id': 'passage:foreign'},
            {'passage_segment_id': 'canonical:other'},
            {'passage_capture_id': 'capture:other'},
            {'selector_type': 'TEXT_POSITION'},
            {'start_ms': -1}, {'end_ms': 1200},
            {'start_ms': True}, {'end_ms': '3500'},
            {'segment_index': True},
            {'publication_blocked': 'false'},
            {'transcript_status': 'FALSIFIED'},
            {'candidate_status': 'UNKNOWN'},
            {'text_sha256': 'bad'},
        )
        for changes in tampered:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.request(Store(media_row(**changes)))
        for record in ({}, [], None):
            with self.subTest(record=record), self.assertRaises(RuntimeError):
                self.request(Store(record))
        for bad_input in ('bad\n', 1, None):
            with self.subTest(bad_input=bad_input), self.assertRaises(ValueError):
                inspect_candidate_media_selector(
                    Store(), content_id='content:one', statement_candidate_id=bad_input,
                    passage_id='passage:media',
                )

    def test_unresolved_segment_exposes_actual_state_not_review_or_publication_authority(self):
        result = self.request(Store(media_row(
            candidate_status='HELD', transcript_status='TRANSCRIPT_UNCERTAIN',
            publication_blocked=True,
        )))
        self.assertEqual(result['candidate_status'], 'HELD')
        self.assertEqual(result['canonical_segment']['transcript_status'], 'TRANSCRIPT_UNCERTAIN')
        self.assertTrue(result['canonical_segment']['publication_blocked'])
        self.assertFalse(result['publication_authority'])
        self.assertFalse(result['rights_clearance'])
        self.assertFalse(result['attribution_authority'])
        with self.assertRaisesRegex(RuntimeError, '^STUDIO_MEDIA_STORE_UNAVAILABLE$') as ctx:
            self.request(Store(error=OSError('SECRET DATABASE PASSWORD')))
        self.assertNotIn('SECRET', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
