"""Protect the read-only contributor CI from removed JavaScript action runtimes."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'ci.yml'


class CiWorkflowNode24Tests(unittest.TestCase):
    def test_hosted_macos_uses_latest_supported_python_only(self):
        source = WORKFLOW.read_text()
        matrix = source.split('      matrix:\n', 1)[1].split('\n    steps:', 1)[0]
        self.assertIn('os: [ubuntu-latest, macos-latest]', matrix)
        self.assertIn('python-version: ["3.11", "3.12", "3.13", "3.14"]', matrix)
        for version in ('3.11', '3.12', '3.13'):
            with self.subTest(version=version):
                self.assertIn(
                    f'          - os: macos-latest\n            python-version: "{version}"',
                    matrix,
                )
        self.assertEqual(matrix.count('          - os: macos-latest'), 3)
        self.assertNotIn('python-version: "3.14"', matrix)

    def test_branch_push_keeps_repository_gate_without_duplicate_matrix(self):
        source = WORKFLOW.read_text()
        self.assertIn('on:\n  push:\n  pull_request:', source)
        self.assertNotIn('branches: [main]', source)
        self.assertEqual(source.count("if: github.event_name == 'pull_request' || github.ref == 'refs/heads/main'"), 3)
        repo_job = source.split('  repository-contract:', 1)[1].split('\n  clean-clone:', 1)[0]
        self.assertNotIn('    if:', repo_job)
        self.assertIn('os: [ubuntu-latest, macos-latest]', source)

    def test_static_acceptance_runs_once_off_the_scarce_backend_pool(self):
        source = WORKFLOW.read_text()
        backend = source.split('  backend-minimal:', 1)[1].split('  openapi-contract:', 1)[0]
        repository = source.split('  repository-contract:', 1)[1].split('  clean-clone:', 1)[0]
        # Static tree checks have no OS/Python input. Keep the full contributor
        # gate required, but do not spend eight runner allocations repeating it.
        self.assertIn('python3 tools/check_contributor_acceptance.py', repository)
        self.assertNotIn('python3 tools/check_contributor_acceptance.py', backend)
        self.assertIn('PYTHONPATH=poc python -m unittest discover -s tests -v', backend)
        self.assertIn('python -m build --outdir dist-ci', backend)
        self.assertNotIn('continue-on-error:', backend)
        self.assertNotIn('max-parallel:', backend)

    def test_ubuntu_decoder_install_rewrites_the_effective_apt_mirror(self):
        source = WORKFLOW.read_text()
        steps = source.split('      - name: Install original-media test decoder\n')[1:]
        self.assertEqual(len(steps), 2)
        for index, step in enumerate(steps):
            with self.subTest(decoder_step=index):
                body = step.split('\n      - name: ', 1)[0]
                self.assertIn(
                    's@mirror+file:/etc/apt/apt-mirrors.txt@http://archive.ubuntu.com/ubuntu@g',
                    body,
                )
                self.assertIn(
                    's@http://azure.archive.ubuntu.com/ubuntu@http://archive.ubuntu.com/ubuntu@g',
                    body,
                )

    def test_every_first_party_action_uses_supported_node24_runtime_major(self):
        source = WORKFLOW.read_text()
        actions = re.findall(r'^\s+- uses: (actions/(checkout|setup-python|setup-node)@v\d+)\s*$',
                             source, re.MULTILINE)
        # New CI jobs may add actions; every actions/* invocation must be checked.
        self.assertGreater(len(actions), 0)
        self.assertEqual(len(actions), len(re.findall(r'^\s+- uses: actions/', source, re.MULTILINE)))
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
