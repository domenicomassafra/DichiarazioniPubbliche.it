"""DP-416: operator changes cannot leave Collection locators in editable forms."""
import shutil
import subprocess
import unittest

from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page
from tests.test_studio_local_page_async import _COLLECTION_VERTICAL_JS


class CollectionFormScrubTests(unittest.TestCase):
    def test_persisted_capture_without_passage_stays_navigable_and_held(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")
        anchor = "  const queue = forms['/v1/discovery/capture-queue'];"
        self.assertIn(anchor, _COLLECTION_VERTICAL_JS)
        scenario = """  // The real DP330 Senato state: one immutable Capture, no written Passage.
  const navigation = forms['/v1/collections/navigate'];
  navigation.fields.collection_id = 'research:senato-akn-dp326';
  navigation.fields.limit = '10';
  pending = navigation.fire('submit');
  assert.equal(requests.at(-1).path, '/v1/collections/navigate');
  reply({contract_version:'studio-collection-navigation-v1', private_only:true,
    read_only:true, publication_authority:false, rights_clearance:false,
    review_authority:false, collection_id:'research:senato-akn-dp326',
    collection_state:'ACTIVE', members:[{
      content_id:'content:senato', source_id:'source:senato', source_exists:true,
      rights_status:'CLEARED', processing_status:'DISCOVERED', capture_count:1,
      blockers:['REVIEW_AUTHORITY_NOT_EVALUATED','CONTENT_RIGHTS_NOT_APPROVED',
        'CONTENT_NOT_READY','CAPTURE_NOT_READY_FOR_REVIEW'],
      source_preview_authorized:false, review_authority:false,
      latest_capture:{id:'capture:senato', content_sha256:sha,
        status:'CAPTURED', hold_status:'NONE', rights_status:'CLEARED',
        archive_status:'NOT_REQUESTED', passage_count:0,
        passages_truncated:false, passages:[]}
    }], has_more:false, next_after_content_id:null});
  await pending;
  const navLinks = ids.get('collection-navigation-links').children;
  const exactCapture = navLinks.find(button => /Capture capture:senato/.test(button.textContent));
  assert.ok(exactCapture, 'persisted Capture must have its own focusable link even without Passage');
  assert.match(exactCapture.textContent, /0 Passage/);
  assert.match(exactCapture.textContent, /non disponibili|assenti|HOLD/i);
  assert.equal(navLinks.some(button => /→ Passage .*Statement Candidate/.test(button.textContent)), false,
    'no invented candidate links when Passage does not exist');
  exactCapture.fire('click');
  assert.equal(requests.at(-1).path, '/v1/collections/captures');
  assert.equal(JSON.parse(requests.at(-1).options.body).collection_id, 'research:senato-akn-dp326');
  assert.equal(JSON.parse(requests.at(-1).options.body).content_id, 'content:senato');
  reply({...base, capture_authorized:false, contract_version:'studio-collection-captures-v1',
    collection_id:'research:senato-akn-dp326', content_id:'content:senato',
    source_id:'source:senato', source_exists:true, collection_state:'ACTIVE',
    rights_status:'CLEARED', processing_status:'DISCOVERED',
    has_more:false, next_after_id:null, captures:[{
      id:'capture:senato', content_sha256:sha,
      observed_at:'2026-10-24T21:53:44Z', status:'CAPTURED', archive_status:'NOT_REQUESTED'
    }]});
  await drain();
  assert.ok(ids.get('collection-capture-links').children.some(
    link => /capture:senato/.test(link.textContent)),
  'Capture link opens the real existing version panel');
""" + anchor
        script = _COLLECTION_VERTICAL_JS.replace(anchor, scenario, 1)
        result = subprocess.run(
            [node, "-e", script],
            input=render_studio_login_page("a" * 32).decode(),
            capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
