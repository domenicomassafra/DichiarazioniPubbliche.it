"""DP-229: the configured official RSS challenger must call the native adapter."""

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.research_discovery import (
    ConfiguredRegistryDiscoveryAdapter, DiscoveryAdapterRequest, load_discovery_manifest,
)
from dichiarazioni_pubbliche.source_adapters import DiscoveryResult
from dichiarazioni_pubbliche.source_watcher import DiscoveredContent

ROOT = Path(__file__).resolve().parents[1]


class OfficialRssChallengerTests(unittest.TestCase):
    def test_configured_official_rss_invokes_native_discovery(self) -> None:
        manifest = load_discovery_manifest({
            "schema_version": 1,
            "id": "manifest:dp229:rss:regression",
            "collection_id": "collection:dp229:isolated",
            "limits": {
                "max_results": 2,
                "max_results_per_host": 1,
                "cost_cap_usd": "0",
            },
            "seeds": [{"kind": "source_id", "value": "official-camera-temi"}],
            "source_families": ["public_rss"],
            "queries": [{
                "id": "query:dp229:rss:regression",
                "query": "Camera dei deputati",
                "source_families": ["public_rss"],
                "adapter_ids": ["configured_registry"],
                "max_results": 2,
                "seeds": [{"kind": "source_id", "value": "official-camera-temi"}],
            }],
        })
        request = DiscoveryAdapterRequest(
            manifest_id=manifest.id,
            manifest_sha256=manifest.manifest_sha256,
            run_id="run:dp229:rss:regression",
            query=manifest.queries[0],
            date_from=None,
            date_to=None,
            remaining_cost_usd=Decimal("0"),
        )
        discovered = DiscoveryResult((
            DiscoveredContent(
                source_id="official-camera-temi",
                platform="public_rss",
                external_id="camera:example",
                title="Camera dei deputati: aggiornamento",
                canonical_url="https://www.camera.it/leg18/1234",
                published_at="",
            ),
        ))
        adapter = ConfiguredRegistryDiscoveryAdapter(
            ROOT / "config" / "source-registry.v1.json"
        )
        self.assertEqual(adapter.cost_upper_bound_usd(request), Decimal("0"))
        with patch(
            "dichiarazioni_pubbliche.research_discovery.discover_source_result",
            return_value=discovered,
        ) as native_discover:
            result = adapter.discover(request)
        native_discover.assert_called_once()
        self.assertEqual(result.status, "OK")
        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.hits[0].source_family, "public_rss")
        self.assertEqual(result.hits[0].source_id, "official-camera-temi")


if __name__ == "__main__":
    unittest.main()
