"""Private Collection navigation and operator state regression scenario."""

_COLLECTION_VERTICAL_SCENARIO_JS = r"""async function main() {
  assert.ok(forms['/v1/collections/passage-lineage'], 'missing dedicated Collection Passage UI');
  assert.ok(forms['/v1/discovery/capture-queue'], 'missing capture triage form');
  assert.match(html, /id="collection-lineage-summary"[^>]*role="status"|role="status"[^>]*id="collection-lineage-summary"/);

  const collections = forms['/v1/collections/list'];
  collections.fields.limit = '20';
  let pending = collections.fire('submit');
  assert.equal(requests.at(-1).path, '/v1/collections/list');
  reply({contract_version: 'studio-operator-queues-v1', private_only: true,
    publication_authority: false, results: [{id: 'research:pilot', state: 'ACTIVE',
      included_content_count: 1}], next_after_id: null});
  await pending;
  const collectionLink = ids.get('collection-links').children[0];
  assert.ok(collectionLink, 'Collection list must have a keyboard-operable selection');
  assert.match(collectionLink.textContent, /research:pilot/);
  collectionLink.fire('click');
  assert.equal(requests.at(-1).path, '/v1/collections/members');
  assert.equal(JSON.parse(requests.at(-1).options.body).collection_id, 'research:pilot');
  const members = forms['/v1/collections/members'];
  reply({collection_id: 'research:pilot', results: [{content_id: 'content:one',
    rights_status: 'UNKNOWN', processing_status: 'HELD'}]});
  await drain();
  const memberLink = ids.get('member-links').children[0];
  assert.ok(memberLink, 'Collection must open a Content link');
  forms['/v1/collections/captures'].fields.limit = '20';
  memberLink.fire('click');
  assert.equal(requests.at(-1).path, '/v1/collections/member');
  reply({...base, collection_id: 'research:pilot', content_id: 'content:one',
    source_id: 'source:one', source_exists: true, claims: []});
  await drain();
  assert.equal(requests.at(-1).path, '/v1/collections/captures',
    ids.get('collection-capture-summary').textContent + ' / ' + ids.get('status').textContent);
  reply({...base, capture_authorized: false, contract_version: 'studio-collection-captures-v1',
    collection_id: 'research:pilot', content_id: 'content:one', source_id: 'source:one',
    source_exists: true, collection_state: 'ACTIVE', processing_status: 'HELD',
    rights_status: 'UNKNOWN', has_more: false, next_after_id: null, captures: [{id: 'capture:one',
      content_sha256: sha, observed_at: '2026-10-11T18:00:00Z',
      status: 'CAPTURED', archive_status: 'SUCCEEDED'}]});
  await drain();
  const captureButton = ids.get('collection-capture-links').children[0];
  assert.ok(captureButton, 'Content must open a capture');
  forms['/v1/capture/passages'].fields.limit = '20';
  captureButton.fire('click');
  assert.equal(requests.at(-1).path, '/v1/capture/passages');
  assert.equal(JSON.parse(requests.at(-1).options.body).capture_hash, sha);
  assert.equal(JSON.parse(requests.at(-1).options.body).limit, 20);
  reply({...base, contract_version: 'studio-capture-inspection-v1', content_id: 'content:one',
    capture: {id: 'capture:one', content_sha256: sha, observed_at: '2026-10-11T18:00:00Z',
      capture_state: 'CAPTURED', hold_state: 'NONE', archive_state: 'SUCCEEDED',
      body_state: 'STORED_UNVERIFIED', archive_receipt_recorded: true,
      purge_receipt_recorded: false, body_purged_at: null}, selectors: [{
      id: 'passage:one', selector_type: 'TEXT_POSITION', text_sha256: passageHash,
      capture_locator: {content_id: 'content:one', capture_id: 'capture:one',
        capture_sha256: sha, passage_id: 'passage:one'}
    }], has_more: false, next_after_id: null});
  await drain();
  const passageButton = ids.get('capture-passage-links').children[0];
  assert.ok(passageButton, 'Capture must offer a written Passage: ' +
    ids.get('status').textContent + ' ' + ids.get('results').textContent);
  passageButton.fire('click');
  assert.equal(requests.at(-1).path, '/v1/collections/passage-lineage');
  assert.deepEqual(JSON.parse(requests.at(-1).options.body), {
    collection_id: 'research:pilot', content_id: 'content:one',
    capture_id: 'capture:one', passage_id: 'passage:one', limit: 20});
  const lineageData = {...base, contract_version: 'studio-operator-queues-v1',
    review_authority_evaluated: false, collection_id: 'research:pilot',
    collection_state: 'ACTIVE', content_id: 'content:one', source_id: 'source:one',
    source_exists: true, rights_status: 'UNKNOWN', processing_status: 'HELD',
    capture_id: 'capture:one', capture_sha256: sha, capture_state: 'CAPTURED',
    capture_hold_state: 'NONE', passage: {id: 'passage:one', text_sha256: passageHash,
      selector_type: 'TEXT_POSITION', start_char: 2, end_char: 5},
    candidates: [{id: 'statement:one', status: 'CANDIDATE',
      statement_text_hash: 'c'.repeat(64), claim_candidate_count: 1,
      claim_candidates_truncated: false, review_authority_evaluated: false,
      claim_candidates: [{id: 'claim_candidate:one', status: 'PROMOTED',
        recorded_promoted_claim_id: 'claim:one', promotion_receipt_id: 'promotion:one',
        promotion_authority_evaluated: false}]}], next_after_statement_id: null,
    blockers: ['CONTENT_RIGHTS_NOT_APPROVED']};
  reply(lineageData);
  await drain();
  const lineage = ids.get('collection-lineage-links');
  assert.ok(lineage.children.length, 'candidate detail must be visible');
  assert.match(lineage.children.map(x => x.textContent).join(' '), /statement:one/);
  assert.match(lineage.children.map(x => x.textContent).join(' '), /claim_candidate:one/);
  assert.match(lineage.children.map(x => x.textContent).join(' '), /claim:one/);
  assert.match(ids.get('collection-lineage-summary').textContent, /diritti|rights/i);
  assert.doesNotMatch(ids.get('results').textContent, /PRIVATE_SOURCE_BODY/);
  lineage.children[0].fire('click');
  assert.equal(ids.get('collection-lineage-inspector').hidden, false);
  assert.equal(ids.get('collection-candidate-heading').focused, true);
  assert.match(ids.get('collection-candidate-detail').textContent, /promotion:one/);
  // A full one-row page can advertise a follow-up keyset cursor.
  const lineageForm = forms['/v1/collections/passage-lineage'];
  lineageForm.fields.limit = '1';
  pending = lineageForm.fire('submit');
  reply({...lineageData, next_after_statement_id: 'statement:one'});
  await pending;
  assert.ok(lineage.children.some(x => /Pagina successiva/.test(x.textContent)),
    'full page must expose bounded statement cursor, not a full-corpus load');
  const more = lineage.children.find(x => /Pagina successiva/.test(x.textContent));
  more.fire('click');
  assert.equal(JSON.parse(requests.at(-1).options.body).after_statement_id, 'statement:one');
  reply({...base, contract_version: 'studio-operator-queues-v1',
    review_authority_evaluated: false, collection_id: 'research:pilot',
    content_id: 'content:one', capture_id: 'capture:other', passage: {id: 'passage:one'},
    candidates: [{id: 'statement:unrelated', private_text: 'PRIVATE_SOURCE_BODY'}]});
  await drain();
  assert.equal(lineage.children.length, 0, 'cross-Capture page must fail closed');
  assert.doesNotMatch(ids.get('results').textContent, /PRIVATE_SOURCE_BODY/);
  assert.match(ids.get('collection-lineage-summary').textContent, /non verific|non conforme/i);

  const queue = forms['/v1/discovery/capture-queue'];
  queue.fields.collection_id = 'research:pilot';
  queue.fields.limit = '20';
  pending = queue.fire('submit');
  assert.equal(requests.at(-1).path, '/v1/discovery/capture-queue');
  reply({...base, contract_version: 'studio-capture-triage-queue-v1', read_only: true,
    triage_action_authorized: false, collection_id: 'research:pilot',
    collection_status: 'PAUSED', results: [{collection_id: 'research:pilot',
      content_id: 'content:one', capture_id: 'capture:one', state: 'BLOCKED',
      queue_family: 'BLOCKED_CAPTURE', blockers: ['COLLECTION_NOT_ACTIVE']}],
    snapshot_sha256: 'a'.repeat(64),
    next_after_capture_id: null});
  await pending;
  const queueLinks = ids.get('capture-queue-links');
  assert.ok(queueLinks.children.length);
  assert.match(queueLinks.children[0].textContent, /BLOCKED/);
  queue.fields.limit = '1';
  pending = queue.fire('submit');
  reply({...base, contract_version: 'studio-capture-triage-queue-v1', read_only: true,
    triage_action_authorized: false, collection_id: 'research:pilot',
    collection_status: 'PAUSED', results: [{collection_id: 'research:pilot',
      content_id: 'content:one', capture_id: 'capture:one', state: 'BLOCKED',
      queue_family: 'BLOCKED_CAPTURE', blockers: ['COLLECTION_NOT_ACTIVE']}],
    snapshot_sha256: 'a'.repeat(64),
    next_after_capture_id: 'capture:one'});
  await pending;
  const nextCapture = queueLinks.children.find(x => /Pagina successiva/.test(x.textContent));
  assert.ok(nextCapture, 'capture exceptions must paginate by verified Capture ID');
  nextCapture.fire('click');
  assert.equal(JSON.parse(requests.at(-1).options.body).after_capture_id, 'capture:one');
  assert.equal(JSON.parse(requests.at(-1).options.body).expected_snapshot_sha256, 'a'.repeat(64));
  reply({...base, contract_version: 'studio-capture-triage-queue-v1', read_only: true,
    triage_action_authorized: false, collection_id: 'research:pilot',
    snapshot_sha256: 'b'.repeat(64), collection_status: 'PAUSED',
    results: [{collection_id: 'research:pilot', content_id: 'content:one',
      capture_id: 'capture:foreign-snapshot', queue_family: 'BLOCKED_CAPTURE',
      state: 'BLOCKED', blockers: ['STALE_PRIVATE_MARKER']}],
    next_after_capture_id: null});
  await drain();
  assert.equal(queueLinks.children.length, 0, 'changed fingerprint must reject stale queue page');
  assert.doesNotMatch(ids.get('results').textContent, /STALE_PRIVATE_MARKER/);
  pending = queue.fire('submit');
  reply({...base, contract_version: 'studio-capture-triage-queue-v1', read_only: true,
    triage_action_authorized: false, collection_id: 'research:foreign',
    collection_status: 'PAUSED', results: [{collection_id: 'research:foreign',
      content_id: 'content:foreign', capture_id: 'capture:foreign', state: 'BLOCKED',
      queue_family: 'BLOCKED_CAPTURE', blockers: ['FOREIGN_PRIVATE_MARKER']}]});
  await drain();
  assert.equal(queueLinks.children.length, 0, 'cross-Collection capture queue must fail closed');
  assert.doesNotMatch(ids.get('results').textContent, /FOREIGN_PRIVATE_MARKER/);
  const candidates = forms['/v1/discovery/candidate-queue'];
  assert.ok(candidates, 'candidate PG triage queue requires a usable private form');
  candidates.fields.collection_id = 'research:pilot';
  candidates.fields.limit = '1';
  pending = candidates.fire('submit');
  assert.equal(requests.at(-1).path, '/v1/discovery/candidate-queue');
  const candidateRow = {collection_id: 'research:pilot',
    candidate_id: 'statement:one', content_id: 'content:one',
    capture_id: 'capture:one', passage_id: 'passage:one',
    candidate_status: 'HELD', state: 'BLOCKED',
    blockers: ['PASSAGE_CAPTURE_NOT_LATEST', 'PRIVATE_SOURCE_RIGHTS_NOT_ATTESTED'],
    retry_condition: 'AFTER_PRIVATE_PROVENANCE_AND_RIGHTS_REVIEW'};
  reply({contract_version: 'studio-statement-candidate-queue-pg-v1',
    private_only: true, read_only: true, publication_authority: false,
    triage_action_authorized: false, collection_id: 'research:pilot',
    collection_status: 'ACTIVE', snapshot_sha256: 'a'.repeat(64),
    rows: [candidateRow], next_after_candidate_id: 'statement:one'});
  await pending;
  const candidateLinks = ids.get('candidate-queue-links');
  assert.equal(candidateLinks.children.length, 2, 'row plus verified next page control');
  candidateLinks.children[0].fire('click');
  assert.equal(requests.at(-1).path, '/v1/collections/passage-lineage');
  assert.equal(JSON.parse(requests.at(-1).options.body).passage_id, 'passage:one');
  const nextCandidate = candidateLinks.children.find(x => /Pagina successiva/.test(x.textContent));
  nextCandidate.fire('click');
  assert.equal(requests.at(-1).path, '/v1/discovery/candidate-queue');
  assert.equal(JSON.parse(requests.at(-1).options.body).expected_snapshot_sha256, 'a'.repeat(64));
  reply({contract_version: 'studio-statement-candidate-queue-pg-v1',
    private_only: true, read_only: true, publication_authority: false,
    triage_action_authorized: false, collection_id: 'research:pilot',
    collection_status: 'ACTIVE', snapshot_sha256: 'b'.repeat(64),
    rows: [{...candidateRow, candidate_id: 'PRIVATE_STALE_CANDIDATE'}],
    next_after_candidate_id: null});
  await drain();
  assert.equal(candidateLinks.children.length, 0, 'stale Candidate page must fail closed');
  assert.doesNotMatch(ids.get('results').textContent, /PRIVATE_STALE_CANDIDATE/);
  const coverage = forms['/v1/discovery/coverage-queue'];
  assert.ok(coverage, 'persisted Coverage Need needs a Studio form');
  coverage.fields.collection_id = 'research:pilot';
  coverage.fields.limit = '1';
  pending = coverage.fire('submit');
  assert.equal(requests.at(-1).path, '/v1/discovery/coverage-queue');
  const needRow = {collection_id: 'research:pilot', need_id: 'need:one',
    need_type: 'PRIMARY_SOURCE', requirement_kind: 'ROLE_ANY', status: 'OPEN',
    state: 'NEEDS_REVIEW', attempt_count: 0, max_attempts: 2,
    event_id: 'event:need-one', atomic_claim_id: null, claim_candidate_id: null,
    source_intelligence_assessment_id: null,
    blockers: ['NEED_OPEN', 'SOURCE_RIGHTS_NOT_ATTESTED'],
    retry_condition: 'AFTER_SOURCE_RIGHTS_AND_COVERAGE_REVIEW'};
  reply({contract_version: 'studio-coverage-need-queue-pg-v1',
    private_only: true, read_only: true, rights_clearance: false,
    publication_authority: false, triage_action_authorized: false,
    collection_id: 'research:pilot', collection_status: 'ACTIVE',
    snapshot_sha256: 'a'.repeat(64), rows: [needRow],
    next_after_need_id: 'need:one'});
  await pending;
  const coverageLinks = ids.get('coverage-queue-links');
  assert.equal(coverageLinks.children.length, 2, 'Coverage Needs row and next page');
  assert.match(coverageLinks.children[0].textContent, /need:one/);
  const moreCoverage = coverageLinks.children.find(x => /Pagina successiva/.test(x.textContent));
  moreCoverage.fire('click');
  assert.equal(requests.at(-1).path, '/v1/discovery/coverage-queue');
  assert.equal(JSON.parse(requests.at(-1).options.body).expected_snapshot_sha256, 'a'.repeat(64));
  reply({contract_version: 'studio-coverage-need-queue-pg-v1',
    private_only: true, read_only: true, rights_clearance: false,
    publication_authority: false, triage_action_authorized: false,
    collection_id: 'research:pilot', collection_status: 'ACTIVE',
    snapshot_sha256: 'b'.repeat(64),
    rows: [{...needRow, need_id: 'PRIVATE_STALE_NEED'}],
    next_after_need_id: null});
  await drain();
  assert.equal(coverageLinks.children.length, 0, 'stale Coverage Need page must fail closed');
  assert.doesNotMatch(ids.get('results').textContent, /PRIVATE_STALE_NEED/);
  const inboxForm = forms['/v1/discovery/inbox'];
  assert.ok(inboxForm, 'persisted Discovery Inbox needs a private operator form');
  inboxForm.fields.collection_id = 'research:pilot';
  inboxForm.fields.limit = '3';
  pending = inboxForm.fire('submit');
  assert.equal(requests.at(-1).path, '/v1/discovery/inbox');
  const inboxRow = (hit_id, queue, reason_code = null) => ({
    collection_id: 'research:pilot', hit_id, queue, reason_code, content_id: 'content:one',
    provenance_path: {hit_id, collection_id: 'research:pilot', run_id: 'run:one',
      query_id: 'query:one', manifest_id: 'manifest:one'},
    private_only: true, read_only: true, action_authorized: false,
    publication_authority: false, annotation_revision: 0,
    blockers: ['PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED'],
    unblock_conditions: [{blocker: 'PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED',
      unblock_condition: 'VERIFY_CURRENT_PRIVATE_SOURCE_RIGHTS_RECORD'}]
  });
  const hitRows = [inboxRow('hit:new', 'NEW_CONTENT'),
    inboxRow('hit:duplicate', 'DUPLICATE_WITHIN_RUN', 'DUPLICATE'),
    inboxRow('hit:old', 'EXISTING_CONTENT')];
  reply({contract_version: 'studio-discovery-inbox-v2', collection_id: 'research:pilot',
    private_only: true, read_only: true, action_authorized: false,
    publication_authority: false, rows: hitRows, next_after_id: 'hit:old'});
  await pending;
  const inboxLinks = ids.get('inbox-annotation-links');
  assert.match(ids.get('inbox-annotation-summary').textContent,
    /nuove 1 · esistenti 1 · doppioni 1 · da analizzare 3/);
  assert.match(inboxLinks.children[0].textContent, /Nuova fonte/);
  assert.match(inboxLinks.children[1].textContent, /Doppione nella scoperta/);
  assert.match(inboxLinks.children[1].textContent, /VERIFY_CURRENT_PRIVATE_SOURCE_RIGHTS_RECORD/);
  inboxLinks.children[1].fire('click');
  assert.equal(requests.at(-1).path, '/v1/discovery/triage-history');
  assert.equal(JSON.parse(requests.at(-1).options.body).hit_id, 'hit:duplicate');
  reply({private_only: true});
  await drain();
  const nextInbox = inboxLinks.children.find(x => /Pagina successiva/.test(x.textContent));
  assert.ok(nextInbox, 'more Discovery Hits must remain accessible by pagination');
  nextInbox.fire('click');
  assert.equal(requests.at(-1).path, '/v1/discovery/inbox');
  assert.equal(JSON.parse(requests.at(-1).options.body).after_id, 'hit:old');
  reply({contract_version: 'studio-discovery-inbox-v2', collection_id: 'research:pilot',
    private_only: true, read_only: true, action_authorized: false,
    publication_authority: false,
    rows: [{...inboxRow('hit:bad', 'NEW_CONTENT'), provenance_path: {
      ...inboxRow('hit:bad', 'NEW_CONTENT').provenance_path, collection_id: 'other'}}],
    next_after_id: null});
  await drain();
  assert.equal(inboxLinks.children.length, 0, 'foreign provenance must fail closed');
  assert.doesNotMatch(ids.get('inbox-annotation-summary').textContent, /hit:bad/);
  pending = queue.fire('submit');
  token.value = 'b'.repeat(64);
  token.fire('input');
  reply({private_marker: 'OLD_OPERATOR_RESPONSE'});
  await pending;
  assert.equal(queueLinks.children.length, 0, 'token replacement clears prior operator references');
  assert.equal(candidateLinks.children.length, 0, 'token replacement clears Candidate references');
  assert.equal(coverageLinks.children.length, 0, 'token replacement clears Coverage Needs');
  assert.equal(inboxLinks.children.length, 0, 'token replacement clears Discovery Inbox');
  assert.equal(lineage.children.length, 0);
  assert.doesNotMatch(ids.get('results').textContent, /OLD_OPERATOR_RESPONSE/);
  ids.get('clear').fire('click');
  assert.equal(lineage.children.length, 0);
  assert.equal(queueLinks.children.length, 0);
  assert.doesNotMatch(ids.get('results').textContent, /capture:one/);
  process.stdout.write('Collection Capture Passage Candidate and capture triage UI PASS\n');
}
main().catch(e => {console.error(e); process.exitCode = 1;});
"""
