"""DP-704: rollback rehearsal must read back the restored origin over HTTP."""

import unittest
from unittest.mock import patch

from tests.test_dp481_minipc_release import MiniPCImmutableReleaseTests
from tools import dp481_minipc_release as release_tool


class RehearsalRollbackReadbackTests(unittest.TestCase):
    setUp = MiniPCImmutableReleaseTests.setUp
    make = MiniPCImmutableReleaseTests.make

    def test_restored_release_is_served_and_verified_before_safe_return(self):
        self.make(withdrawn=True)
        origin_readbacks = []
        original_verify = release_tool.verify

        def record_readback(*args, **kwargs):
            proof = original_verify(*args, **kwargs)
            if kwargs.get("origin"):
                origin_readbacks.append(proof["release_id"])
            return proof

        with patch.object(release_tool, "verify", side_effect=record_readback):
            result = release_tool.rehearse(
                self.source, self.static, self.projection,
                git_sha="1" * 40, rights_epoch_ref="PRIVATE_DRAFT_NO_GO",
            )
        self.assertEqual(result["restored_release_id"], result["initial_release_id"])
        self.assertTrue(result["restored_origin_verified"])
        self.assertEqual(origin_readbacks, [
            result["initial_release_id"], result["safe_release_id"],
            result["initial_release_id"], result["safe_release_id"],
        ])


if __name__ == "__main__":
    unittest.main()
