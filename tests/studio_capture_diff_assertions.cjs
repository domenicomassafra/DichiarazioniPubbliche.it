/* DP-419: exercise bounded versioned Capture audit locators in real Studio JS. */
'use strict';

const assert = require('node:assert/strict');

module.exports = async function checkCaptureDiff({forms, requests, complete, ids,
    copiedReferences, clear, token, results, deferClipboard}) {
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
  const scope = {
    contract_version: 'studio-capture-inspection-v1', private_only: true,
    rights_clearance: false, publication_authority: false, content_id: 'content:one',
    earlier, later,
  };
  const counts = {UNCHANGED: 0, CHANGED: 1, ADDED: 1, REMOVED: 1};
  const completed = {
    complete: true, status: 'COMPLETE', max_per_version: 20, counts, changes: diffRows,
  };
  complete(first, {...scope, selector_comparison: completed});
  await compareRequest;
  async function inspect(data) {
    // Session logout clears the private form; re-enter the exact audited scope.
    compareForm.fields.content_id = scope.content_id;
    compareForm.fields.earlier_hash = earlier.content_sha256;
    compareForm.fields.later_hash = later.content_sha256;
    const request = compareForm.fire('submit');
    const index = requests.length - 1;
    assert.equal(requests[index].path, '/v1/capture/compare');
    complete(index, data);
    await request;
  }
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
  const releaseClipboard = deferClipboard();
  const pendingCopy = details.children[0].children[0].fire('click');
  clear.fire('click');
  releaseClipboard();
  await pendingCopy;
  assert.match(ids.get('capture-copy-status').textContent, /privati/,
    'late clipboard success must not restore private result after logout');
  assert.equal(details.children.length, 0, 'logout removes captured selectors');
  token.value = 'a'.repeat(64);
  await inspect({...scope, selector_comparison: {...completed,
    counts: {UNCHANGED: 0, CHANGED: 1, ADDED: 0, REMOVED: 0},
    changes: [{...diffRows[0], later_locator: {...diffRows[0].later_locator,
      private_body: 'NEVER_COPY_PRIVATE_BODY'}}]}});
  assert.equal(details.children.length, 0, 'malformed audit locator fails closed');
  assert.match(diff.textContent, /non verificabili/);
  assert.doesNotMatch(results.textContent, /NEVER_COPY_PRIVATE_BODY/);
  await inspect({...scope, selector_comparison: {...completed,
    counts: {UNCHANGED: 0, CHANGED: 2, ADDED: 0, REMOVED: 0},
    changes: [diffRows[0], diffRows[0]]}});
  assert.equal(details.children.length, 0, 'duplicate selector anchor must fail closed');
  assert.match(diff.textContent, /non verificabili/);
  await inspect({...scope, selector_comparison: {...completed,
    counts: {UNCHANGED: 0, CHANGED: 21, ADDED: 0, REMOVED: 0},
    changes: Array.from({length: 21}, (_, index) => ({...diffRows[0],
      start_char: index * 10, end_char: index * 10 + 5}))}});
  assert.equal(details.children.length, 0, 'a single Capture cannot exceed twenty selectors');
  assert.match(diff.textContent, /non verificabili/);
  await inspect({...scope, content_id: 'content:foreign',
    selector_comparison: {...completed, changes: undefined}});
  assert.match(diff.textContent, /non verificabili/,
    'legacy count payload without matching Content must not render');
  await inspect({...scope, later: {...later, content_sha256: 'e'.repeat(64)},
    selector_comparison: {...completed, changes: undefined}});
  assert.match(diff.textContent, /non verificabili/,
    'legacy count payload without matching Capture SHA must not render');
  await inspect({...scope, selector_comparison: {...completed, changes: undefined}});
  assert.match(diff.textContent, /Solo conteggi/,
    'older count-only response may render only with fully validated Capture scope');
  assert.equal(details.children.length, 0, 'legacy counters never imply copyable locators');
  assert.equal(ids.get('capture-links').children.length, 0,
    'legacy counters never imply a version navigation link');
  await inspect({...scope, selector_comparison: {
    status: 'TRUNCATED', complete: false, max_per_version: 20, changes: [],
  }});
  assert.match(diff.textContent, /Confronto non completo/);
  await inspect({...scope, content_id: 'content:foreign', selector_comparison: {
    status: 'TRUNCATED', complete: false, max_per_version: 20, changes: [],
  }});
  assert.match(diff.textContent, /non verificabili/,
    'truncated comparisons must not hide a mismatched scope');
  const staleDiff = compareForm.fire('submit');
  clear.fire('click');
  complete(requests.length - 1, {...scope, selector_comparison: {
    ...completed, counts: {UNCHANGED: 999, CHANGED: 999, ADDED: 999, REMOVED: 999},
  }});
  await staleDiff;
  assert.equal(details.children.length, 0, 'disconnect must scrub private passage anchors');
  assert.doesNotMatch(diff.textContent, /999/);
  assert.match(diff.textContent, /Nessun confronto/);
  token.value = 'a'.repeat(64);
  // Even an accidentally extended private response must never render raw
  // excerpts, media locations, archive receipts or headers in the inspector.
  const passageForm = forms['/v1/capture/passages'];
  passageForm.fields.content_id = 'content:one';
  passageForm.fields.capture_hash = earlier.content_sha256;
  passageForm.fields.limit = '20';
  const passageRequest = passageForm.fire('submit');
  const passageIndex = requests.length - 1;
  assert.equal(requests[passageIndex].path, '/v1/capture/passages');
  complete(passageIndex, {contract_version: 'studio-capture-inspection-v1',
    private_only: true, content_id: 'content:one', capture: earlier,
    selectors: [], body_ref: 'PRIVATE_BODY_REF_NEVER_SHOW',
    archived_url: 'https://media.invalid/PRIVATE_NEVER_SHOW',
    transcript_text: 'PRIVATE_TRANSCRIPT_NEVER_SHOW',
    headers: {Authorization: 'PRIVATE_HEADER_NEVER_SHOW'},
    purge_receipt: 'PRIVATE_PURGE_NEVER_SHOW',
    rights_state: 'REVOKED', body_state: 'PURGED'});
  await passageRequest;
  assert.doesNotMatch(results.textContent,
    /PRIVATE_BODY_REF_NEVER_SHOW|PRIVATE_NEVER_SHOW|PRIVATE_TRANSCRIPT_NEVER_SHOW|PRIVATE_HEADER_NEVER_SHOW|PRIVATE_PURGE_NEVER_SHOW/,
    'capture inspector must never render unreviewed response JSON');
  assert.match(results.textContent, /Solo metadati verificati nei pannelli dedicati/);
  const mediaForm = forms['/v1/media/segment'];
  mediaForm.fields.content_id = 'content:one';
  mediaForm.fields.statement_candidate_id = 'statement:one';
  mediaForm.fields.passage_id = 'passage:one';
  const mediaRequest = mediaForm.fire('submit');
  const mediaIndex = requests.length - 1;
  complete(mediaIndex, {contract_version: 'studio-media-selector-inspection-v1',
    private_only: true, publication_authority: false, rights_clearance: false,
    content_id: 'content:one', statement_candidate_id: 'statement:one',
    passage_id: 'passage:one', canonical_segment: {
      id: 'PRIVATE_URL_IN_SEGMENT_ID', start_ms: 'PRIVATE_RAW_TIME',
      end_ms: 5000, transcript_status: 'RESOLVED', publication_blocked: true}});
  await mediaRequest;
  assert.doesNotMatch(ids.get('media-locator').textContent,
    /PRIVATE_URL_IN_SEGMENT_ID|PRIVATE_RAW_TIME/,
    'invalid media selector fields must not be rendered as a verified locator');

  // An actual collection may have exactly one persisted Capture and no Passage.
  // Inspecting it must still expose a bounded, useful provenance/HOLD summary.
  const captureCollection = forms['/v1/collections/captures'];
  captureCollection.fields.collection_id = 'research:senato';
  captureCollection.fields.content_id = 'content:senato';
  captureCollection.fields.limit = '20';
  const collectionRequest = captureCollection.fire('submit');
  const collectionIndex = requests.length - 1;
  const single = {id: 'capture:senato', content_sha256: '1'.repeat(64),
    observed_at: '2026-10-24T23:53:44+02:00', status: 'CAPTURED',
    archive_status: 'NOT_REQUESTED'};
  complete(collectionIndex, {contract_version: 'studio-collection-captures-v1',
    private_only: true, publication_authority: false, rights_clearance: false,
    capture_authorized: false, collection_id: 'research:senato',
    content_id: 'content:senato', source_id: 'source:senato', source_exists: true,
    collection_state: 'ACTIVE', rights_status: 'CLEARED',
    processing_status: 'READY', captures: [single], has_more: false,
    next_after_id: null});
  await collectionRequest;
  const captureLinks = ids.get('collection-capture-links');
  assert.equal(captureLinks.children.length, 1);
  const selected = captureLinks.children[0].fire('click');
  const selectedIndex = requests.length - 1;
  assert.equal(requests[selectedIndex].path, '/v1/capture/passages');
  const inspection = {contract_version: 'studio-capture-inspection-v1',
    private_only: true, publication_authority: false, rights_clearance: false,
    content_id: 'content:senato', capture: {
      id: single.id, observed_at: single.observed_at,
      content_sha256: single.content_sha256, capture_state: 'CAPTURED',
      hold_state: 'NONE', archive_state: 'NOT_REQUESTED',
      body_state: 'STORED_UNVERIFIED', archive_receipt_recorded: false,
      purge_receipt_recorded: false, body_purged_at: null},
    selectors: [], has_more: false, next_after_id: null,
    body_ref: 'PRIVATE_BODY_NEVER_RENDER', headers: {Authorization: 'SECRET_NEVER_RENDER'}};
  complete(selectedIndex, inspection);
  await selected;
  await new Promise(resolve => setImmediate(resolve));
  const summary = ids.get('passage-candidate-summary');
  assert.match(summary.textContent, /capture:senato/);
  assert.match(summary.textContent, /1{64}/, 'exact immutable Capture hash');
  assert.match(summary.textContent, /nessun Passage/i);
  assert.match(summary.textContent, /nessun permesso di riprodurre/i);
  assert.doesNotMatch(summary.textContent, /PRIVATE_BODY|SECRET_NEVER_RENDER/);
  assert.equal(ids.get('capture-passage-links').children.length, 0);
  const purgeRequest = passageForm.fire('submit');
  const purgeIndex = requests.length - 1;
  complete(purgeIndex, {...inspection, capture: {...inspection.capture,
    capture_state: 'PURGED_BODY', body_state: 'PURGED',
    purge_receipt_recorded: true, body_purged_at: '2026-10-25T08:00:00Z'}});
  await purgeRequest;
  assert.match(summary.textContent, /PURGED_BODY/);
  assert.match(summary.textContent, /purge 2026-10-25T08:00:00Z/);
  const badPurgeRequest = passageForm.fire('submit');
  complete(requests.length - 1, {...inspection, capture: {...inspection.capture,
    capture_state: 'PURGED_BODY', body_state: 'PURGED', purge_receipt_recorded: false}});
  await badPurgeRequest;
  assert.match(summary.textContent, /non verificabile/,
    'a false purge receipt cannot present verified purge metadata');
  clear.fire('click');
  assert.doesNotMatch(summary.textContent, /capture:senato|1{64}/,
    'logout must scrub even the single-Capture metadata summary');
};
