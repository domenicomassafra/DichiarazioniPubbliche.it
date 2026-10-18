"""DP-416: operator changes cannot leave Collection locators in editable forms."""
import shutil
import subprocess
import unittest

from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page
from tests.test_studio_local_page_async import _COLLECTION_VERTICAL_JS


class CollectionFormScrubTests(unittest.TestCase):
    def test_token_and_workspace_change_scrub_form_locators(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")

        before = "  pending = queue.fire('submit');\n  token.value = 'b'.repeat(64);"
        injected = """  const navigationForm = forms['/v1/collections/navigate'];
  const privateCapture = forms['/v1/collections/captures'];
  navigationForm.fields.collection_id = 'research:private';
  navigationForm.fields.after_content_id = 'content:private';
  privateCapture.fields.collection_id = 'research:private';
  privateCapture.fields.content_id = 'content:private';
  pending = queue.fire('submit');
  token.value = 'b'.repeat(64);"""
        after = "  assert.equal(queueLinks.children.length, 0, 'token replacement clears prior operator references');"
        checks = """  assert.equal(navigationForm.fields.collection_id, '', 'token must scrub Collection');
  assert.equal(navigationForm.fields.after_content_id, '', 'token must scrub cursor');
  assert.equal(privateCapture.fields.collection_id, '', 'token must scrub Capture parent');
  assert.equal(privateCapture.fields.content_id, '', 'token must scrub Content locator');
  navigationForm.fields.collection_id = 'research:another';
  privateCapture.fields.content_id = 'content:another';
  nav[0].fire('click');
  assert.equal(navigationForm.fields.collection_id, '', 'workspace must scrub Collection');
  assert.equal(privateCapture.fields.content_id, '', 'workspace must scrub Content');
""" + after
        self.assertIn(before, _COLLECTION_VERTICAL_JS)
        self.assertIn(after, _COLLECTION_VERTICAL_JS)
        script = _COLLECTION_VERTICAL_JS.replace(before, injected, 1).replace(after, checks, 1)
        result = subprocess.run(
            [node, "-e", script],
            input=render_studio_login_page("a" * 32).decode(),
            capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
