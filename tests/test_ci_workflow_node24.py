"""Protect the read-only contributor CI from removed JavaScript action runtimes."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'ci.yml'


class CiWorkflowNode24Tests(unittest.TestCase):
    def test_every_first_party_action_uses_supported_node24_runtime_major(self):
        source = WORKFLOW.read_text()
        actions = re.findall(r'^\s+- uses: (actions/(checkout|setup-python|setup-node)@v\d+)\s*$',
                             source, re.MULTILINE)
        self.assertEqual(len(actions), 7)
        versions = {
            'checkout': 'actions/checkout@v5',
            'setup-python': 'actions/setup-python@v6',
            'setup-node': 'actions/setup-node@v5',
        }
        for name, kind in actions:
            with self.subTest(name=name):
                self.assertEqual(name, versions[kind])
        self.assertNotIn('ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION', source)
        self.assertNotIn('FORCE_JAVASCRIPT_ACTIONS_TO_NODE24', source)

    def test_runners_matrix_install_and_no_deploy_guards_remain(self):
        source = WORKFLOW.read_text()
        for required in (
            'permissions:\n  contents: read',
            'os: [ubuntu-latest, macos-latest]',
            'python-version: ["3.11", "3.12", "3.13", "3.14"]',
            'node-version: "24"',
            'cache: npm',
            'cache-dependency-path: web/package-lock.json',
            'DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: "1"',
            'Explicit public-projection build fails closed',
            'Assert the tree was not modified by the build',
            'permissions:',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        for forbidden in ('deploy:', 'release:', 'publish:', 'contents: write'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
