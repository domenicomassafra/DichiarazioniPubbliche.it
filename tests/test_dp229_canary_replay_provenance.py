"""DP-229 live canary: durable attempt time must distinguish discovery from replay."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.source_adapters import DiscoveryResult
from tools.dp229_official_rss_canary import binary, run_case


def _has_local_postgres() -> bool:
    try:
        for name in ("initdb", "pg_ctl", "psql"):
            binary(name)
        return True
    except RuntimeError:
        return False


@unittest.skipUnless(_has_local_postgres(), "Local PostgreSQL tools required")
class RealCanaryReplayProvenanceTests(unittest.TestCase):
    def test_repeat_invocation_is_readback_not_fresh_research(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dp229-canary-") as folder:
            state = Path(folder) / "private"
            with patch(
                "dichiarazioni_pubbliche.research_discovery.discover_source_result",
                return_value=DiscoveryResult(()),
            ) as live_fetch:
                first = run_case(state)
                second = run_case(state)

        live_fetch.assert_called_once()
        self.assertTrue(first["new_healthy_attempt_this_invocation"])
        self.assertFalse(second["new_healthy_attempt_this_invocation"])
        self.assertEqual(first["attempt_started_at_utc"], second["attempt_started_at_utc"])
        self.assertTrue(first["attempt_started_at_utc"])
        self.assertTrue(first["readback_replay_equal"])
        self.assertTrue(second["readback_replay_equal"])


if __name__ == "__main__":
    unittest.main()
