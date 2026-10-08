"""DP-209/210/214/215: bounded real-input batch with private fail-closed preflight."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.capture_authorization import PrivateCaptureAuthorizationBlocked  # noqa: E402
from dichiarazioni_pubbliche.private_capture_batch import (  # noqa: E402
    BATCH_VERSION, CaptureBatch, CaptureBatchItem,
    load_private_capture_batch, preflight_capture_batch, require_persisted_discovery,
)
from test_capture_authorization import content_state, record, CONTENT_ID, URL, SOURCE_FAMILY  # noqa: E402


def make_batch(*, item_count=1):
    return CaptureBatch(
        collection_id="research:approved",
        items=tuple(
            CaptureBatchItem(
                content_id=CONTENT_ID if i == 0 else f"content:approved-{i}",
                canonical_url=URL if i == 0 else f"https://example.test/article-{i}",
                source_family=SOURCE_FAMILY,
                rights_record_id="private-rights:reviewed",
            )
            for i in range(item_count)
        ),
    )


def research_context(item=None, **changes):
    item = item or make_batch().items[0]
    state = {
        "collection_id": "research:approved",
        "collection_status": "ACTIVE",
        "membership_status": "INCLUDED",
        "capture_authorized": True,
        "content_id": item.content_id,
        "canonical_url": item.canonical_url,
        "accepted_discovery_hits": 1,
        "accepted_discovery_groups": [{"source_family": item.source_family, "hit_count": 1}],
    }
    state.update(changes)
    return state


class FakeBatchCaptureStore:
    def __init__(self, **context_overrides):
        self.context_overrides = context_overrides
        self.calls = 0

    def read_research_capture_context(self, collection_id, content_id):
        self.calls += 1
        item = next(
            i for i in make_batch(item_count=3).items if i.content_id == content_id
        )
        return research_context(item, **self.context_overrides)

    def read_operator_capture_content_state(self, content_id):
        item = next(i for i in make_batch(item_count=3).items if i.content_id == content_id)
        return content_state(id=content_id, canonical_url=item.canonical_url)


class FakeBatchRightsStore:
    def read_current(self, subject):
        return record(content_id=subject.content_id, locator_value=subject.locator_value)


class PrivateCaptureBatchTests(unittest.TestCase):
    def test_structurally_valid_manifest_is_private_input_not_fake_fixture_authority(self):
        batch = make_batch()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            path.write_text(json.dumps({
                "version": BATCH_VERSION,
                "collection_id": batch.collection_id,
                "items": [vars(item) for item in batch.items],
            }), encoding="utf-8")
            first = load_private_capture_batch(path)
            self.assertEqual(first.items, batch.items)
            self.assertEqual(first.collection_id, batch.collection_id)
            self.assertEqual(len(first.manifest_sha256), 64)
            self.assertEqual(first.manifest_sha256, load_private_capture_batch(path).manifest_sha256)
            path.write_text(json.dumps({
                "version": BATCH_VERSION,
                "collection_id": "research:changed",
                "items": [vars(item) for item in batch.items],
            }), encoding="utf-8")
            self.assertNotEqual(first.manifest_sha256, load_private_capture_batch(path).manifest_sha256)

    def test_manifest_fails_closed_on_duplicate_excess_noncanonical_and_extra_fields(self):
        item = vars(make_batch().items[0])
        cases = (
            {"version": BATCH_VERSION, "collection_id": "research:approved", "items": []},
            {"version": BATCH_VERSION, "collection_id": "research:approved", "items": [item] * 26},
            {"version": BATCH_VERSION, "collection_id": "research:approved", "items": [item] * 2},
            {"version": BATCH_VERSION, "collection_id": "research:approved", "items": [{**item, "canonical_url": "http://example.test/unsafe"}]},
            {"version": BATCH_VERSION, "collection_id": "research:approved", "items": [{**item, "unknown_permission": True}]},
            {"version": "stale", "collection_id": "research:approved", "items": [item]},
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            for payload in cases:
                with self.subTest(payload=payload):
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_private_capture_batch(path)

    def test_persisted_discovery_requires_active_included_reviewed_hit(self):
        item = make_batch().items[0]
        require_persisted_discovery(
            research_context(item), collection_id="research:approved", item=item
        )
        cases = (
            None,
            research_context(item, collection_id="research:other"),
            research_context(item, collection_status="PAUSED"),
            research_context(item, membership_status="REMOVED"),
            research_context(item, capture_authorized=False),
            research_context(item, capture_authorized=None),
            research_context(item, accepted_discovery_hits=0),
            research_context(item, accepted_discovery_groups=[]),
            research_context(item, accepted_discovery_groups=[{"source_family": "WRONG_FAMILY", "hit_count": 1}]),
            research_context(item, accepted_discovery_groups=None),
            research_context(item, accepted_discovery_groups=[{"source_family": item.source_family, "hit_count": True}]),
            research_context(item, accepted_discovery_groups=[{"source_family": item.source_family, "hit_count": 1},
                                                               {"source_family": item.source_family, "hit_count": 1}]),
            research_context(item, content_id="content:other"),
            research_context(item, canonical_url="https://example.test/other"),
        )
        for context in cases:
            with self.subTest(context=context):
                with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                    require_persisted_discovery(
                        context, collection_id="research:approved", item=item
                    )

    def test_preflight_revalidates_every_item_without_capture(self):
        store = FakeBatchCaptureStore()
        guards = preflight_capture_batch(
            make_batch(item_count=3), capture_store=store, rights_store=FakeBatchRightsStore()
        )
        self.assertEqual(store.calls, 3)
        self.assertEqual(len(guards), 3)
        for guard in guards:
            guard()
        self.assertEqual(store.calls, 6)

    def test_preflight_refuses_entire_batch_when_second_item_lacks_discovery(self):
        store = FakeBatchCaptureStore()
        original = store.read_research_capture_context

        def missing_second(collection_id, content_id):
            result = original(collection_id, content_id)
            if content_id == "content:approved-1":
                result["accepted_discovery_hits"] = 0
                result["accepted_discovery_groups"] = []
            return result

        store.read_research_capture_context = missing_second
        with self.assertRaisesRegex(
            PrivateCaptureAuthorizationBlocked, "DISCOVERY_PROVENANCE_MISSING"
        ):
            preflight_capture_batch(
                make_batch(item_count=3), capture_store=store, rights_store=FakeBatchRightsStore()
            )
        self.assertEqual(store.calls, 2)


if __name__ == "__main__":
    unittest.main()
