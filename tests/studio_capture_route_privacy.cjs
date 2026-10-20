/* Execute the actual nonce-bound Studio script against private Capture replies. */
'use strict';
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const html = fs.readFileSync(0, 'utf8');
const script = html.match(/<script nonce="[0-9a-f]{32}">([\s\S]*?)<\/script>/);
assert.ok(script);
class Element {
  constructor(extra = {}) {
    this.children = []; this.handlers = new Map(); this.textContent = '';
    this.hidden = false; this.value = ''; Object.assign(this, extra);
  }
  addEventListener(kind, callback) { this.handlers.set(kind, callback); }
  fire(kind) { assert.ok(this.handlers.has(kind)); return this.handlers.get(kind)({preventDefault() {}}); }
  requestSubmit() { return this.fire('submit'); }
  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
  contains(element) { return this.children.includes(element); }
  focus() { this.focused = true; }
  setAttribute(key, value) { this[key] = value; }
}
const ids = new Map([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], new Element()]));
const forms = {};
for (const match of html.matchAll(/<form data-endpoint="([^"]+)"[^>]*>([\s\S]*?)<\/form>/g)) {
  const fields = {};
  for (const field of match[2].matchAll(/name="([^"]+)"[^>]*(?:value="([^"]*)")?/g))
    fields[field[1]] = field[2] ?? '';
  const nodes = Object.fromEntries(Object.keys(fields).map(name => [name, {
    get value() { return fields[name]; }, set value(value) { fields[name] = value; },
    focus() { this.focused = true; },
  }]));
  forms[match[1]] = new Element({dataset:{endpoint:match[1]},fields,
    elements:{namedItem:name=>nodes[name] ?? new Element()},
    querySelectorAll:()=>Object.values(nodes)});
}
const nav = [...html.matchAll(/data-panel="([^"]+)"/g)].map(m => new Element({dataset:{panel:m[1]}}));
const panels = nav.map(item => new Element({id:item.dataset.panel}));
const document = {
  querySelector: selector => forms[selector.match(/data-endpoint="([^"]+)"/)?.[1]] ?? null,
  getElementById: id => ids.get(id) ?? null,
  querySelectorAll: selector => selector === 'form[data-endpoint]' ? Object.values(forms)
    : selector === '[data-panel]' ? nav : selector === 'main > section[id]' ? panels : [],
  createElement: () => new Element(),
};
class FormData {
  constructor(form) { this.fields = form.fields; }
  entries() { return Object.entries(this.fields)[Symbol.iterator](); }
}
const requests = [];
const fetch = (path, options) => new Promise(resolve => requests.push({path,options,resolve}));
vm.runInNewContext(script[1], {document, fetch, FormData, AbortController});
const captureForm = forms['/v1/collections/captures'];
assert.ok(captureForm);
ids.get('token').value = 'a'.repeat(64);
captureForm.fields.limit = '20';
captureForm.fields.collection_id = 'collection:one';
captureForm.fields.content_id = 'content:one';
const base = {
  contract_version:'studio-collection-captures-v1',private_only:true,
  publication_authority:false,rights_clearance:false,capture_authorized:false,
  collection_id:'collection:one',content_id:'content:one',
  source_id:'source:one',source_exists:true,collection_state:'ACTIVE',
  rights_status:'UNKNOWN',processing_status:'HELD',captures:[{
    id:'capture:one',content_sha256:'a'.repeat(64),observed_at:'2026-10-20T12:00:00Z',
    status:'CAPTURED',archive_status:'SUCCEEDED',
  }],has_more:false,next_after_id:null,
};
const markers = ['PRIVATE_BODY_REF_W11','PRIVATE_AUTH_HEADER_W11','PRIVATE_PURGE_RECEIPT_W11','UNTRUSTED_RIGHTS_STATUS'];
function visible() {
  return [ids.get('results').textContent, ids.get('status').textContent,
    ids.get('collection-capture-summary').textContent,
    ...ids.get('collection-capture-links').children.map(item => item.textContent)].join(' ');
}
async function check(reply, {ok=true,links=0,expected=null}={}) {
  const pending = captureForm.fire('submit');
  const request = requests.at(-1);
  assert.equal(request.path,'/v1/collections/captures');
  assert.equal(JSON.parse(request.options.body).collection_id,'collection:one');
  request.resolve({ok,json: async()=>reply});
  await pending;
  const out = visible();
  markers.forEach(marker=>assert.ok(!out.includes(marker), 'leaked ' + marker + ' in ' + out));
  assert.equal(ids.get('collection-capture-links').children.length,links,out);
  if (expected) assert.match(out,expected);
}
async function checkAdjacentCaptureNavigation(endpoint, data) {
  const form = forms[endpoint];
  assert.ok(form, endpoint);
  const pending = form.fire('submit');
  const request = requests.at(-1);
  assert.equal(request.path, endpoint);
  request.resolve({ok:true,json:async()=>({contract_version:'studio-local-readonly-api-v1',
    data:{...data,body_ref:markers[0],headers:{Authorization:markers[1]},
      purge_receipt:markers[2]}})});
  await pending;
  const result = ids.get('results').textContent;
  markers.forEach(marker=>assert.ok(!result.includes(marker), endpoint + ' leaked ' + marker));
}
async function main() {
  const receipt = data => ({contract_version:'studio-local-readonly-api-v1',data});
  await check(receipt(base),{links:1,expected:/Cattura capture:one/});
  const poison = {...base,body_ref:markers[0],
    headers:{Authorization:markers[1]},purge_receipt:markers[2]};
  await check({...receipt(poison),message:markers[1]});
  await check(receipt({...base, rights_status:markers[3]}));
  await check(receipt({...base,captures:[{...base.captures[0],observed_at:markers[0]}]}));
  await check(receipt({...base,captures:[{...base.captures[0],status:markers[2]}]}));
  await check(receipt({...base,captures:[{...base.captures[0],headers:{Authorization:markers[1]}}]}));
  await check(receipt({...base,collection_id:'collection:other',purge_receipt:markers[2]}));
  await check(receipt({...base,rights_clearance:true,headers:{Authorization:markers[1]}}));
  await check(receipt({...base,captures:null,body_ref:markers[0]}));
  await check({contract_version:'error',message:markers[0],errors:[markers[1]]},
    {ok:false,expected:/non verificabili|nessun riferimento/i});
  await checkAdjacentCaptureNavigation('/v1/collections/members',
    {collection_id:'collection:one',results:[],next_after_id:null});
  await checkAdjacentCaptureNavigation('/v1/collections/member',
    {collection_id:'collection:one',content_id:'content:one',source_exists:false,claims:[]});
  console.log('DP419 private Capture route allowlist and error privacy PASS');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
