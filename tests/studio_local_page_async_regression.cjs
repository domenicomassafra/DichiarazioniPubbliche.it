/* Exercise delayed Studio fetches and stale-response privacy against a local DOM. */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor(extra = {}) {
    this.handlers = new Map();
    this.children = [];
    this.textContent = '';
    this.value = '';
    this.hidden = false;
    this.focused = false;
    Object.assign(this, extra);
  }
  addEventListener(event, handler) { this.handlers.set(event, handler); }
  fire(event) {
    const handler = this.handlers.get(event);
    assert.ok(handler, 'missing ' + event + ' listener');
    return handler({preventDefault() {}});
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  contains(child) { return this.children.includes(child); }
  focus() { this.focused = true; }
  setAttribute(name, value) { this[name] = value; }
  requestSubmit() { return this.fire('submit'); }
}

const html = fs.readFileSync(0, 'utf8');
const inlineScript = html.match(/<script nonce="[0-9a-f]{32}">([\s\S]*?)<\/script>/);
assert.ok(inlineScript, 'rendered page must contain its nonce-bound script');

const ids = new Map();
for (const id of ['token', 'results', 'status', 'clear', 'member-links',
                  'claim-links', 'capture-links', 'capture-selector-diff-summary', 'collection-capture-links',
                  'collection-capture-summary', 'capture-passage-links',
                  'passage-candidate-links', 'passage-candidate-summary',
                  'collection-decision-summary',
                  'workload-summary', 'workload-links',
                  'candidate-write-summary',
                  'triage-write-summary',
                  'inbox-annotation-summary','inbox-annotation-links',
                  'media-capture-context-summary',
                  'media-binding-summary',
                  'media-locator', 'corpus-list',
                  'corpus-links', 'corpus-summary', 'corpus-inspector',
                  'corpus-references', 'corpus-inspector-title', 'corpus-back',
                  'corpus-source-jump', 'corpus-jump-status',
                  'source-exact-form', 'source-exact-status', 'source-exact-open']) {
  ids.set(id, new Element());
}
const forms = {};
for (const path of [
  '/v1/collections/members', '/v1/collections/member', '/v1/collections/captures',
  '/v1/collections/passage-candidates',
  '/v1/candidate/decision-receipt',
  '/v1/candidate/decision-annotate',
  '/v1/operator/workload',
  '/v1/discovery/triage-annotate',
  '/v1/discovery/inbox','/v1/discovery/triage-history',
  '/v1/media/capture-context',
  '/v1/media/binding',
  '/v1/collections/claim-provenance', '/v1/capture/compare',
  '/v1/capture/passages', '/v1/corpus/search', '/v1/media/segment',
]) {
  const fields = path === '/v1/operator/workload' ? {
    collection_id:'',limit:'2',after:'',
  } : path === '/v1/media/binding' ? {
    binding_id:'',
  } : path === '/v1/candidate/decision-annotate' ? {
    candidate_id:'',run_id:'',input_fingerprint:'',passage_id:'',
    capture_id:'',capture_sha256:'',request_key:'',decision:'HOLD',
    expected_revision:'0',actor_ref:'',target_type:'',target_id:'',
    credential_id:'',authority_receipt_id:'',review_event_json:'',
    confirm_private_decision:'',
  } : path === '/v1/media/capture-context' ? {
    content_id:'',statement_candidate_id:'',passage_id:'',
    capture_id:'',capture_sha256:'',
  } : path === '/v1/discovery/inbox' ? {
    collection_id:'',limit:'2',after_id:'',
  } : path === '/v1/discovery/triage-history' ? {
    collection_id:'',hit_id:'',limit:'2',after_revision:'0',
  } : path === '/v1/discovery/triage-annotate' ? {
    collection_id:'',hit_id:'',request_key:'',decision:'NEEDS_REVIEW',
    expected_revision:'0',actor_ref:'',receipt_id:'',
    confirm_private_annotation:'',
  } : {
    query: 'demo', limit: '2', kind: '', after_id: '', after_claim_id: '',
    earlier_hash: '', later_hash: '', capture_hash: '',
    collection_id: '', source_id: '', person_id: '', topic_id: '',
    event_id: '', from_date: '', to_date: '', status: '', claim_type: '', check_worthy: '',
    candidate_id:'',run_id:'',passage_id:'',capture_id:'',request_key:'',
    hit_id:'',decision:'',expected_revision:'',actor_ref:'',receipt_id:'',
    confirm_private_annotation:'',
  };
  if (!['/v1/corpus/search','/v1/discovery/inbox',
        '/v1/discovery/triage-history','/v1/discovery/triage-annotate',
        '/v1/media/capture-context','/v1/media/binding',
        '/v1/candidate/decision-annotate','/v1/operator/workload'].includes(path))
    fields.content_id = 'content:one';
  const nodes = {};
  for (const name of Object.keys(fields)) {
    nodes[name] = {name, focus() { this.focused = true; },
      get value() { return fields[name]; }, set value(value) { fields[name] = value; }};
  }
  forms[path] = new Element({dataset: {endpoint: path}, fields,
    querySelectorAll: selector => {
      assert.ok(['input,select','input,select,textarea'].includes(selector));
      return Object.values(nodes);
    },
    elements: {namedItem: name => nodes[name] ?? new Element()}});
}
const nav = ['corpus', 'captures'].map(name => new Element({dataset: {panel: name}}));
const panels = nav.map(button => new Element({id: button.dataset.panel}));
const requests = [];
const document = {
  getElementById: id => ids.get(id),
  querySelector: selector => forms[selector.match(/data-endpoint="([^"]+)"/)?.[1]],
  querySelectorAll: selector => {
    if (selector === 'form[data-endpoint]') return Object.values(forms);
    if (selector === '[data-panel]') return nav;
    if (selector === 'main > section[id]') return panels;
    throw new Error('Unexpected selector ' + selector);
  },
  createElement: () => new Element(),
};
class FormData {
  constructor(form) { this.form = form; }
  entries() { return Object.entries(this.form.fields)[Symbol.iterator](); }
}
const fetch = (path, options) => new Promise(resolve => requests.push({path, options, resolve}));
vm.runInNewContext(inlineScript[1], {document, FormData, fetch, AbortController});
const token = ids.get('token');
const results = ids.get('results');
const status = ids.get('status');
const members = ids.get('member-links');
const media = ids.get('media-locator');
const clear = ids.get('clear');
const corpusForm = forms['/v1/corpus/search'];
const corpusLinks = ids.get('corpus-links');
const corpusList = ids.get('corpus-list');
const inspector = ids.get('corpus-inspector');
const inspectorRefs = ids.get('corpus-references');
const back = ids.get('corpus-back');
const sourceJump = ids.get('corpus-source-jump');
const jumpStatus = ids.get('corpus-jump-status');

function complete(index, data) {
  const request = requests[index], media = request.path === '/v1/media/segment';
  if (media) data = {contract_version:'studio-media-selector-inspection-v1',
    private_only:true,publication_authority:false,rights_clearance:false,
    attribution_authority:false,...JSON.parse(request.options.body),...data};
  request.resolve({ok:true,json:async()=>({
    ...(media?{contract_version:'studio-local-readonly-api-v1'}:{}),data})});
}
function corpusReply(index, rows, overrides = {}) {
  const data = {
    contract_version: 'studio-operator-search-v1',
    private_only: true, publication_authority: false,
    query_sha256: 'a'.repeat(64), result_count: rows.length, results: rows,
    ...overrides,
  };
  requests[index].resolve({ok: true, json: async () => ({
    contract_version: 'studio-local-readonly-api-v1', data,
  })});
}
const safeResult = {
  id: 'passage:one', kind: 'PASSAGE', content_id: 'content:one',
  passage_id: 'passage:one', source_id: 'source:original',
};

async function main() {
  token.value = 'a'.repeat(64);
  corpusForm.fields.query = 'termine privato';
  corpusForm.fields.kind = 'PASSAGE';
  corpusForm.fields.collection_id = 'research:garlasco';
  corpusForm.fields.source_id = 'source:original';
  corpusForm.fields.person_id = 'person:one';
  corpusForm.fields.topic_id = 'topic:one';
  corpusForm.fields.event_id = 'event:one';
  corpusForm.fields.from_date = '2026-01-01';
  corpusForm.fields.to_date = '2026-10-01';
  corpusForm.fields.status = 'APPROVED';
  corpusForm.fields.claim_type = 'FACTUAL';
  corpusForm.fields.check_worthy = 'true';
  corpusForm.fields.limit = '5';
  const searchRequest = corpusForm.fire('submit');
  assert.equal(requests[0].path, '/v1/corpus/search');
  assert.deepEqual(JSON.parse(requests[0].options.body), {
    query: 'termine privato', kinds: ['PASSAGE'], collection_id: 'research:garlasco',
    source_id: 'source:original', person_id: 'person:one', topic_id: 'topic:one',
    event_id: 'event:one', from_at: '2026-01-01T00:00:00Z',
    to_at: '2026-10-01T23:59:59Z', status: 'APPROVED', claim_type: 'FACTUAL',
    check_worthy: true, limit: 5,
  }, 'filters must reach the real local API in its declared schema');
  corpusReply(0, [safeResult]);
  await searchRequest;
  assert.equal(corpusLinks.children.length, 1);
  corpusLinks.children[0].fire('click');
  assert.equal(inspector.hidden, false);
  assert.equal(corpusList.hidden, true);
  assert.equal(ids.get('corpus-inspector-title').focused, true, 'inspector should receive keyboard focus');
  assert.match(inspectorRefs.children.map(item => item.textContent).join(' '), /source:original/);
  assert.equal(sourceJump.hidden, false, 'source jump requires valid collection/content/source IDs');
  const jumpRequest = sourceJump.fire('click');
  assert.equal(requests[1].path, '/v1/collections/member');
  assert.deepEqual(JSON.parse(requests[1].options.body), {
    collection_id: 'research:garlasco', content_id: 'content:one', limit: 1,
  });
  requests[1].resolve({ok: true, json: async () => ({
    contract_version: 'studio-local-readonly-api-v1',
    data: {
      collection_id: 'research:garlasco', content_id: 'content:one',
      source_id: 'source:original', source_exists: true,
      private_only: true, publication_authority: false,
      private_text: 'MUST_NOT_RENDER',
    },
  })});
  await jumpRequest;
  assert.match(jumpStatus.textContent, /source:original/);
  assert.doesNotMatch(jumpStatus.textContent, /MUST_NOT_RENDER/);
  assert.doesNotMatch(results.textContent, /termine privato/);
  back.fire('click');
  assert.equal(corpusList.hidden, false);
  assert.equal(inspector.hidden, true);
  assert.equal(corpusForm.fields.query, 'termine privato', 'query retained');
  assert.equal(corpusForm.fields.kind, 'PASSAGE', 'kind retained');
  assert.equal(corpusForm.fields.collection_id, 'research:garlasco', 'collection retained');
  assert.equal(corpusForm.fields.source_id, 'source:original', 'source retained');
  assert.equal(corpusLinks.children[0].focused, true, 'focus restored');

  const malformedSearch = corpusForm.fire('submit');
  corpusReply(2, [{...safeResult, private_body: 'DO_NOT_ECHO_PRIVATE'}]);
  await malformedSearch;
  assert.equal(corpusLinks.children.length, 0, 'unknown fields held');
  assert.doesNotMatch(results.textContent, /DO_NOT_ECHO_PRIVATE/);

  const lateSearch = corpusForm.fire('submit');
  corpusLinks.replaceChildren();
  clear.fire('click');
  corpusReply(3, [safeResult]);
  await lateSearch;
  assert.equal(corpusLinks.children.length, 0, 'late search held');
  assert.equal(corpusForm.fields.query, '', 'query scrubbed');
  assert.equal(corpusForm.fields.source_id, '', 'filter scrubbed');

  token.value = 'a'.repeat(64);
  const membersRequest = forms['/v1/collections/members'].fire('submit');
  complete(4, {collection_id: 'collection:private', results: [{
    content_id: 'content:secret', rights_status: 'UNKNOWN', processing_status: 'HELD',
  }]});
  await membersRequest;
  assert.equal(members.children.length, 1, 'private link rendered');

  const mediaRequest = forms['/v1/media/segment'].fire('submit');
  complete(5, {canonical_segment: {
    id: 'segment:secret', start_ms: 1000, end_ms: 2000,
    transcript_status: 'RESOLVED', publication_blocked: true,
  }});
  await mediaRequest;
  assert.match(media.textContent, /segment:secret/, 'valid media locator');

  const pending = forms['/v1/corpus/search'].fire('submit');
  clear.fire('click');
  assert.equal(token.value, '');
  assert.equal(members.children.length, 0, 'links cleared');
  assert.doesNotMatch(media.textContent, /segment:secret/, 'locator cleared');
  complete(6, {private_marker: 'STALE_PRIVATE_AFTER_CLEAR'});
  await pending;
  assert.doesNotMatch(results.textContent, /STALE_PRIVATE_AFTER_CLEAR/,
                      'stale output blocked');
  assert.match(status.textContent, /disconnesso/i);

  token.value = 'b'.repeat(64);
  corpusForm.fields.query = 'workspace-only';
  corpusForm.fields.collection_id = 'research:garlasco';
  const oldRequest = forms['/v1/corpus/search'].fire('submit');
  nav[1].fire('click');
  assert.equal(corpusForm.fields.query, '', 'workspace switch must scrub private terms');
  assert.equal(corpusForm.fields.collection_id, '', 'workspace switch must scrub collection');
  const latestRequest = forms['/v1/media/segment'].fire('submit');
  complete(8, {canonical_segment: {
    id: 'segment:latest', start_ms: 2500, end_ms: 4500,
    transcript_status: 'RESOLVED', publication_blocked: false,
  }});
  await latestRequest;
  complete(7, {private_marker: 'STALE_PRIOR_WORKSPACE'});
  await oldRequest;
  assert.match(results.textContent, /Solo coordinate e hash verificati/);
  assert.doesNotMatch(results.textContent, /STALE_PRIOR_WORKSPACE/,
                      'older reply held');
  assert.match(media.textContent, /segment:latest/);
  const decisionForm = forms['/v1/candidate/decision-receipt'];
  for (const [field,value] of Object.entries({
    candidate_id:'candidate:one',run_id:'run:one',capture_id:'capture:one',
    passage_id:'passage:one',request_key:'request:one',
  })) decisionForm.fields[field]=value;
  const reviewRequest=decisionForm.fire('submit');
  const reviewIndex=requests.length-1;
  assert.equal(requests[reviewIndex].path,'/v1/candidate/decision-receipt');
  const privateReceipt={
    contract_version:'studio-candidate-decision-receipt-v1',
    private_only:true,historical_only:true,review_authority:false,
    promotion_authority:false,publication_authority:false,rights_clearance:false,
    decision:'HOLD',revision:1,receipt_sha256:'f'.repeat(64),
    status:'HISTORICAL_SOURCE_WITHDRAWN',
    candidate_id:'candidate:one',run_id:'run:one',capture_id:'capture:one',
    passage_id:'passage:one',request_key:'request:one',
    secret:'DO_NOT_RENDER',
  };
  requests[reviewIndex].resolve({ok:true,json:async()=>({
    contract_version:'studio-local-readonly-api-v1',data:privateReceipt,
  })});
  await reviewRequest;
  assert.match(ids.get('collection-decision-summary').textContent,/HISTORICAL_SOURCE_WITHDRAWN/);
  assert.doesNotMatch(ids.get('collection-decision-summary').textContent,/DO_NOT_RENDER/);
  const lateReview=decisionForm.fire('submit');
  const lateIndex=requests.length-1;
  clear.fire('click');
  requests[lateIndex].resolve({ok:true,json:async()=>({
    contract_version:'studio-local-readonly-api-v1',data:privateReceipt,
  })});
  await lateReview;
  assert.equal(ids.get('collection-decision-summary').textContent,'Nessuna ricevuta letta.');
  assert.equal(decisionForm.fields.candidate_id,'');
  token.value = 'c'.repeat(64);
  const triageForm = forms['/v1/discovery/triage-annotate'];
  for (const [name, value] of Object.entries({
    collection_id:'collection:one',hit_id:'hit:one',request_key:'request:triage:one',
    decision:'NEEDS_REVIEW',expected_revision:'0',actor_ref:'operator:one',
    receipt_id:'triage-receipt-'+'d'.repeat(64),confirm_private_annotation:'true',
  })) triageForm.fields[name]=value;
  const write = triageForm.fire('submit');
  const writeIndex = requests.length-1;
  assert.equal(requests[writeIndex].path,'/v1/discovery/triage-annotate');
  assert.deepEqual(JSON.parse(requests[writeIndex].options.body), {
    collection_id:'collection:one',hit_id:'hit:one',request_key:'request:triage:one',
    decision:'NEEDS_REVIEW',expected_revision:0,actor_ref:'operator:one',
    receipt_id:'triage-receipt-'+'d'.repeat(64),confirm_private_annotation:true,
  });
  const signed = {
    contract_version:'studio-private-triage-annotation-v1',private_only:true,
    mutation_kind:'ANNOTATION_ONLY',result_code:'CREATED',
    collection_id:'collection:one',hit_id:'hit:one',decision:'NEEDS_REVIEW',
    revision:1,payload_sha256:'a'.repeat(64),actor_attested:true,
    capture_authorized:false,triage_action_authorized:false,
    promotion_authority:false,publication_authority:false,
    secret:'NEVER_ECHO_RECEIPT',
  };
  requests[writeIndex].resolve({ok:true,json:async()=>({
    contract_version:'studio-private-annotation-api-v1',data:signed,
  })});
  await write;
  assert.match(ids.get('triage-write-summary').textContent,/CREATED/);
  assert.doesNotMatch(ids.get('triage-write-summary').textContent,/NEVER_ECHO_RECEIPT/);
  const lateTriage = triageForm.fire('submit');
  const lateTriageIndex = requests.length-1;
  clear.fire('click');
  requests[lateTriageIndex].resolve({ok:true,json:async()=>({
    contract_version:'studio-private-annotation-api-v1',data:signed,
  })});
  await lateTriage;
  assert.doesNotMatch(ids.get('triage-write-summary').textContent,/CREATED/);
  assert.equal(triageForm.fields.receipt_id,'');
  token.value = 'a'.repeat(64);
  const inboxForm = forms['/v1/discovery/inbox'];
  inboxForm.fields.collection_id = 'collection:one';
  const inboxRequest=inboxForm.fire('submit');
  const inboxIndex=requests.length-1;
  assert.equal(requests[inboxIndex].path,'/v1/discovery/inbox');
  requests[inboxIndex].resolve({ok:true,json:async()=>({
    contract_version:'studio-local-readonly-api-v1',data:{
      contract_version:'studio-discovery-inbox-v2',
      collection_id:'collection:one',private_only:true,read_only:true,
      action_authorized:false,publication_authority:false,next_after_id:null,
      rows:[{collection_id:'collection:one',hit_id:'hit:one',
        queue:'NEW_CONTENT',content_id:'content:one',reason_code:null,
        provenance_path:{hit_id:'hit:one',collection_id:'collection:one',
          run_id:'run:one',query_id:'query:one',manifest_id:'manifest:one'},
        annotation_revision:1,private_only:true,read_only:true,
        action_authorized:false,publication_authority:false,
        blockers:['DISCOVERY_TRIAGE_REVIEW_AUTHORITY_UNAVAILABLE'],
        unblock_conditions:[{blocker:'DISCOVERY_TRIAGE_REVIEW_AUTHORITY_UNAVAILABLE',
          unblock_condition:'VERIFY_REVIEWER_AUTHORITY_AND_CURRENT_POLICY'}],
        private_text:'SECRET_NEVER_TO_RENDER'}],
    },
  })});
  await inboxRequest;
  const inboxLinks=ids.get('inbox-annotation-links');
  assert.equal(inboxLinks.children.length,1);
  assert.doesNotMatch(inboxLinks.children[0].textContent,/SECRET_NEVER_TO_RENDER/);
  inboxLinks.children[0].fire('click');
  const historyForm=forms['/v1/discovery/triage-history'];
  assert.equal(historyForm.fields.hit_id,'hit:one');
  assert.equal(triageForm.fields.hit_id,'hit:one');
  assert.equal(triageForm.fields.expected_revision,'1');
  assert.equal(triageForm.fields.receipt_id,'');
  assert.equal(requests.at(-1).path,'/v1/discovery/triage-history');
  const historyIndex=requests.length-1;
  requests[historyIndex].resolve({ok:true,json:async()=>({
    contract_version:'studio-local-readonly-api-v1',
    data:{results:[{revision:1,decision:'NEEDS_REVIEW'}]},
  })});
  await Promise.resolve();
  clear.fire('click');
  assert.equal(inboxLinks.children.length,0);
  assert.equal(triageForm.fields.hit_id,'');
  token.value='a'.repeat(64);
  const mediaContextForm = forms['/v1/media/capture-context'];
  Object.assign(mediaContextForm.fields,{
    content_id:'content:one',statement_candidate_id:'statement:one',
    passage_id:'passage:media',capture_id:'capture:one',
    capture_sha256:'a'.repeat(64),
  });
  const mediaContextRequest = mediaContextForm.fire('submit');
  const mediaIndex = requests.length-1;
  assert.equal(requests[mediaIndex].path,'/v1/media/capture-context');
  requests[mediaIndex].resolve({ok:true,json:async()=>({
    contract_version:'studio-local-readonly-api-v1',data:{
      contract_version:'studio-media-capture-context-v1',
      private_only:true,publication_authority:false,rights_clearance:false,
      seek_authorized:false,capture_segment_binding:'UNPROVEN',
      content_id:'content:one',statement_candidate_id:'statement:one',
      passage_id:'passage:media',
      canonical_segment:{id:'canonical:one',start_ms:1200,end_ms:3400},
      capture:{id:'capture:one',content_sha256:'a'.repeat(64),
        body_state:'STORED_UNVERIFIED',retention_class:'POLICY_PENDING',
        status:'CAPTURED'},
      hold_reasons:['STUDIO_MEDIA_CAPTURE_SEGMENT_BINDING_UNPROVEN'],
      private_media_url:'NEVER_RENDER_SOURCE',
    },
  })});
  await mediaContextRequest;
  assert.match(ids.get('media-capture-context-summary').textContent,/UNPROVEN|non attestata/);
  assert.doesNotMatch(ids.get('media-capture-context-summary').textContent,/NEVER_RENDER_SOURCE/);
  clear.fire('click');
  assert.equal(ids.get('media-capture-context-summary').textContent,
    'Nessun contesto cattura verificato.');
  token.value='a'.repeat(64);
  const candidateWriteForm=forms['/v1/candidate/decision-annotate'];
  Object.assign(candidateWriteForm.fields,{
    candidate_id:'candidate:one',run_id:'run:one',input_fingerprint:'f'.repeat(64),
    passage_id:'passage:one',capture_id:'capture:one',capture_sha256:'a'.repeat(64),
    request_key:'req:signed',decision:'HOLD',expected_revision:'0',
    actor_ref:'reviewer:alice',credential_id:'alice',authority_receipt_id:'receipt:one',
    review_event_json:JSON.stringify({signed:'secret-to-omit'}),
    confirm_private_decision:'true',
  });
  const signedWrite=candidateWriteForm.fire('submit');
  const candidateIndex=requests.length-1;
  assert.equal(requests[candidateIndex].path,'/v1/candidate/decision-annotate');
  const sent=JSON.parse(requests[candidateIndex].options.body);
  assert.equal(sent.expected_revision,0);
  assert.equal(sent.confirm_private_decision,true);
  assert.deepEqual(sent.review_event,{signed:'secret-to-omit'});
  assert.equal(sent.review_event_json,undefined);
  requests[candidateIndex].resolve({ok:true,json:async()=>({
    contract_version:'studio-private-candidate-decision-api-v1',data:{
      contract_version:'studio-private-candidate-decision-write-v1',
      private_only:true,mutation_kind:'REVIEW_INTENT_ONLY',result_code:'CREATED',
      candidate_id:'candidate:one',run_id:'run:one',passage_id:'passage:one',
      capture_id:'capture:one',decision:'HOLD',revision:1,receipt_sha256:'b'.repeat(64),
      promoted:false,promotion_authority:false,publication_authority:false,
      source_rights_approved:false,
      private_review_event:'NEVER_EXPOSE_SIGNED_EVENT',
    },
  })});
  await signedWrite;
  assert.match(ids.get('candidate-write-summary').textContent,/CREATED/);
  assert.doesNotMatch(ids.get('candidate-write-summary').textContent,/NEVER_EXPOSE_SIGNED_EVENT/);
  assert.equal(decisionForm.fields.candidate_id,'candidate:one');
  assert.equal(decisionForm.fields.request_key,'req:signed');
  const lateWrite=candidateWriteForm.fire('submit');
  const lateCandidateIndex=requests.length-1;
  clear.fire('click');
  requests[lateCandidateIndex].resolve({ok:true,json:async()=>({
    contract_version:'studio-private-candidate-decision-api-v1',
    data:{private_review_event:'NEVER_EXPOSE_SIGNED_EVENT'},
  })});
  await lateWrite;
  assert.equal(candidateWriteForm.fields.review_event_json,'');
  assert.equal(candidateWriteForm.fields.authority_receipt_id,'');
  assert.equal(decisionForm.fields.candidate_id,'');
  assert.equal(ids.get('candidate-write-summary').textContent,'Nessuna intenzione candidata inviata.');
  token.value='a'.repeat(64);
  const bindingForm=forms['/v1/media/binding'];
  bindingForm.fields.binding_id='media-binding:one';
  const bindingRead=bindingForm.fire('submit');
  const bindingIndex=requests.length-1;
  assert.equal(requests[bindingIndex].path,'/v1/media/binding');
  requests[bindingIndex].resolve({ok:true,json:async()=>({
    contract_version:'studio-local-readonly-api-v1',data:{
      contract_version:'studio-capture-segment-binding-pg-v1',
      private_only:true,publication_authority:false,rights_clearance:false,
      seek_authorized:false,capture_segment_binding:'OPERATOR_ATTESTED_METADATA_ONLY',
      binding_id:'media-binding:one',content_id:'content:one',
      capture_id:'capture:one',capture_sha256:'a'.repeat(64),
      canonical_segment_id:'canonical:one',start_ms:1200,end_ms:3400,
      revision:2,binding_state:'REVOKED',
      hold_reasons:['RIGHTS_NOT_INDEPENDENTLY_APPROVED','BINDING_REVOKED'],
      private_url:'NEVER_DISCLOSE_MEDIA',
    },
  })});
  await bindingRead;
  assert.match(ids.get('media-binding-summary').textContent,/BINDING_REVOKED/);
  assert.doesNotMatch(ids.get('media-binding-summary').textContent,/NEVER_DISCLOSE_MEDIA/);
  clear.fire('click');
  assert.equal(bindingForm.fields.binding_id,'');
  assert.equal(ids.get('media-binding-summary').textContent,'Nessun binding verificato.');
  token.value='a'.repeat(64);
  const workloadForm=forms['/v1/operator/workload'];
  Object.assign(workloadForm.fields,{collection_id:'collection:one',limit:'2',after:''});
  const workloadPending=workloadForm.fire('submit');
  const workloadIndex=requests.length-1;
  assert.equal(requests[workloadIndex].path,'/v1/operator/workload');
  assert.deepEqual(JSON.parse(requests[workloadIndex].options.body),{
    collection_id:'collection:one',limit:2,
  });
  requests[workloadIndex].resolve({ok:true,json:async()=>({
    contract_version:'studio-local-readonly-api-v1',data:{
      version:'studio-operator-workload-pg-v1',collection_id:'collection:one',
      collection_state:'ACTIVE',total_members:1,blocked_members:0,
      review_only_members:1,capture_count:1,passage_count:1,
      statement_candidate_count:1,claim_candidate_count:1,
      dispatch_authorized:false,publication_authority:false,
      image_approval_authority:false,text_review_authority:false,
      source_rights_attested:false,next_cursor:null,blocked_queue:[],
      rows:[{content_id:'content:one',capture_id:'capture:one',
        state:'REVIEW_ONLY',reason:'PRIVATE_TRIAGE_REQUIRED',
        capture_count:1,passage_count:1,statement_candidates:1,
        claim_candidates:1,private_text:'DO_NOT_RENDER'}],
      private_source:'NEVER_RENDER_WIP',
    },
  })});
  await workloadPending;
  assert.match(ids.get('workload-summary').textContent,/1 Content inclusi/);
  assert.doesNotMatch(ids.get('workload-summary').textContent,/DO_NOT_RENDER|NEVER_RENDER_WIP/);
  assert.equal(ids.get('workload-links').children.length,1);
  ids.get('workload-links').children[0].fire('click');
  assert.equal(forms['/v1/collections/captures'].fields.content_id,'content:one');
  assert.equal(forms['/v1/collections/captures'].fields.collection_id,'collection:one');
  clear.fire('click');
  assert.equal(workloadForm.fields.collection_id,'');
  assert.equal(ids.get('workload-links').children.length,0);
  process.stdout.write('Studio Corpus filters, keyboard inspector, return, private scrub and stale-response regression PASS\n');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
