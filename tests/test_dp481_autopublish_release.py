"""The immutable host release binds decision-49 config to its code digest."""

import hashlib
import unittest

from tests.test_dp481_minipc_release import MiniPCImmutableReleaseTests, ROOT


class AutopublishStageTests(unittest.TestCase):
    def test_consent_is_hashed_but_cannot_make_draft_authorized(self):
        fixture = MiniPCImmutableReleaseTests(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        policy = ROOT / "config/autopublish.v1.json"
        (fixture.source / "config").mkdir()
        target = fixture.source / "config/autopublish.v1.json"
        target.write_bytes(policy.read_bytes())
        first = fixture.make(withdrawn=True)
        self.assertEqual(first["assets"]["code/config/autopublish.v1.json"],
                         hashlib.sha256(policy.read_bytes()).hexdigest())
        self.assertFalse(first["publication_authorized"])
        target.unlink()
        target.symlink_to(policy)
        with self.assertRaisesRegex(ValueError, "AUTOPUBLISH_CONFIG_INVALID"):
            fixture.make(withdrawn=True)
