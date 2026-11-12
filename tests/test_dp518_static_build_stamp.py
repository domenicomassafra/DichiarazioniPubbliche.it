"""DP-518: a release cannot pair a new source commit with an older static payload."""

import json
import unittest

from tests.test_dp481_minipc_release import MiniPCImmutableReleaseTests
from tools.dp481_minipc_release import stage
from tools.dp481_static_contract import BUILD_STAMP_FILE


class StaticBuildStampTests(unittest.TestCase):
    setUp = MiniPCImmutableReleaseTests.setUp
    make = MiniPCImmutableReleaseTests.make

    def stage(self, git_sha):
        return stage(self.root, self.source, self.static, self.projection,
                     git_sha=git_sha, rights_epoch_ref="PRIVATE_DRAFT_NO_GO")

    def test_payload_built_from_another_commit_or_projection_is_refused(self):
        self.make(withdrawn=False)
        faithful = (self.static / BUILD_STAMP_FILE).read_bytes()
        with self.assertRaisesRegex(ValueError, "STATIC_BUILD_MISMATCH"):
            self.stage("2" * 40)
        other = json.loads(faithful)
        other["projection_sha256"] = "0" * 64
        (self.static / BUILD_STAMP_FILE).write_text(json.dumps(other))
        with self.assertRaisesRegex(ValueError, "STATIC_BUILD_MISMATCH"):
            self.stage("1" * 40)
        (self.static / BUILD_STAMP_FILE).unlink()
        with self.assertRaisesRegex(ValueError, "STATIC_BUILD_STAMP_MISSING"):
            self.stage("1" * 40)
        (self.static / BUILD_STAMP_FILE).write_bytes(faithful)
        self.assertTrue(self.stage("1" * 40)["release_id"])


if __name__ == "__main__":
    unittest.main()
