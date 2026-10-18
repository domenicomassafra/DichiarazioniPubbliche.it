/* DP-419: exercise bounded versioned Capture audit locators in real Studio JS. */
'use strict';

const assert = require('node:assert/strict');

module.exports = async function checkCaptureDiff({forms, requests, complete, ids,
    copiedReferences, clear, token, results}) {
  const compareForm = forms['/v1/capture/compare'];
  compareForm.fields.content_id = 'content:one';
  compareForm.fields.earlier_hash = 'a'.repeat(64);
  compareForm.fields.later_hash = 'c'.repeat(64);
  const first = requests.length;
  const compareRequest = compareForm.fire('submit');
  assert.equal(requests[first].path, '/v1/capture/compare');
  const earlier = {id: 'capture:earlier', content_sha256: 'a'.repeat(64)};
  const later = {id: 'capture:later', content_sha256: 'c'.repeat(64)};
  const locator = (capture, id) => ({content_id: 'content:one', capture_id: capture.id,
    capture_sha256: capture.content_sha256, passage_id: id});
  const diffRows = [
    {change: 'CHANGED', earlier_passage_id: 'passage:old', later_passage_id: 'passage:new',
      earlier_text_sha256: 'd'.repeat(64), later_text_sha256: 'e'.repeat(64),
      earlier_locator: locator(earlier, 'passage:old'), later_locator: locator(later, 'passage:new')},
    {change: 'REMOVED', earlier_passage_id: 'passage:removed', later_passage_id: null,
      earlier_text_sha256: 'f'.repeat(64), later_text_sha256: null,
      earlier_locator: locator(earlier, 'passage:removed'), later_locator: null},
    {change: 'ADDED', earlier_passage_id: null, later_passage_id: 'passage:added',
      earlier_text_sha256: null, later_text_sha256: 'b'.repeat(64),
      earlier_locator: null, later_locator: locator(later, 'passage:added')},
  ].map((row, index) => ({selector_type: 'TEXT_POSITION', start_char: index * 10,
    end_char: index * 10 + 5, page_start: null, page_end: null, ...row}));
  complete(first, {
    contract_version: 'studio-capture-inspection-v1', private_only: true,
    rights_clearance: false, publication_authority: false, content_id: 'content:one',
    earlier, later, selector_comparison: {complete: true, status: 'COMPLETE',
      max_per_version: 20, counts: {UNCHANGED: 0, CHANGED: 1, ADDED: 1, REMOVED: 1},
      changes: diffRows},
  });
  await compareRequest;
  const diff = ids.get('capture-selector-diff-summary');
  const details = ids.get('capture-selector-diff-details');
  assert.match(diff.textContent, /1 modificati/);
  assert.match(diff.textContent, /1 aggiunti/);
  assert.match(diff.textContent, /1 rimossi/);
  assert.equal(details.children.length, 3, 'show exact changed, removed and added anchors');
  assert.match(details.children[0].textContent, /caratteri 0–5/);
  assert.match(details.children[0].textContent, /passage:old/);
  assert.deepEqual(JSON.parse(details.children[0].children[1].textContent),
    locator(earlier, 'passage:old'), 'keyboard-selectable code is the clipboard fallback');
  await details.children[0].children[0].fire('click');
  assert.deepEqual(JSON.parse(copiedReferences.at(-1)), locator(earlier, 'passage:old'));
  assert.doesNotMatch(copiedReferences.at(-1), /url|cookie|body|transcript|secret/i);
  const corrupt = compareForm.fire('submit');
  complete(first + 1, {
    contract_version: 'studio-capture-inspection-v1', private_only: true,
    rights_clearance: false, publication_authority: false, content_id: 'content:one',
    earlier, later, selector_comparison: {complete: true, status: 'COMPLETE',
      max_per_version: 20, counts: {UNCHANGED: 0, CHANGED: 1, ADDED: 0, REMOVED: 0},
      changes: [{...diffRows[0], later_locator: {...diffRows[0].later_locator,
        private_body: 'NEVER_COPY_PRIVATE_BODY'}}]},
  });
  await corrupt;
  assert.equal(details.children.length, 0, 'malformed audit locator fails closed');
  assert.match(diff.textContent, /non verificabili/);
  assert.doesNotMatch(results.textContent, /NEVER_COPY_PRIVATE_BODY/);
  const moreRequest = compareForm.fire('submit');
  complete(first + 2, {selector_comparison: {complete: false, status: 'TRUNCATED'}});
  await moreRequest;
  assert.match(diff.textContent, /Confronto non completo/);
  const staleDiff = compareForm.fire('submit');
  clear.fire('click');
  complete(first + 3, {selector_comparison: {complete: true, status: 'COMPLETE', counts: {
    UNCHANGED: 999, CHANGED: 999, ADDED: 999, REMOVED: 999,
  }}});
  await staleDiff;
  assert.equal(details.children.length, 0, 'disconnect must scrub private passage anchors');
  assert.doesNotMatch(diff.textContent, /999/);
  assert.match(diff.textContent, /Nessun confronto/);
  token.value = 'a'.repeat(64);
};
