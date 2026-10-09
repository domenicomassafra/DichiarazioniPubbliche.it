/* Exercise the actual Studio inline script against a deterministic local DOM.
 * Delayed fetches deliberately ignore abort signals to prove that stale
 * responses cannot repopulate private UI even when cancellation loses a race.
 */
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
    Object.assign(this, extra);
  }
  addEventListener(event, handler) { this.handlers.set(event, handler); }
  fire(event) {
    const handler = this.handlers.get(event);
    assert.ok(handler, 'missing ' + event + ' listener');
    return handler({preventDefault() {}});
  }
  append(child) { this.children.push(child); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this[name] = value; }
  requestSubmit() { return this.fire('submit'); }
}

const html = fs.readFileSync(0, 'utf8');
const inlineScript = html.match(/<script nonce="[0-9a-f]{32}">([\s\S]*?)<\/script>/);
assert.ok(inlineScript, 'rendered page must contain its nonce-bound script');

const ids = new Map();
for (const id of ['token', 'results', 'status', 'clear', 'member-links',
                  'claim-links', 'capture-links', 'media-locator']) {
  ids.set(id, new Element());
}
const forms = {};
for (const path of [
  '/v1/collections/members', '/v1/collections/member',
  '/v1/collections/claim-provenance', '/v1/capture/compare',
  '/v1/capture/passages', '/v1/corpus/search', '/v1/media/segment',
]) {
  forms[path] = new Element({dataset: {endpoint: path}, fields: {
    content_id: 'content:one', query: 'demo', limit: '2',
  }, elements: {namedItem: () => new Element()}});
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
const fetch = (path) => new Promise(resolve => requests.push({path, resolve}));
vm.runInNewContext(inlineScript[1], {document, FormData, fetch, AbortController});
const token = ids.get('token');
const results = ids.get('results');
const status = ids.get('status');
const members = ids.get('member-links');
const media = ids.get('media-locator');
const clear = ids.get('clear');

function complete(index, data) {
  requests[index].resolve({ok: true, json: async () => ({data})});
}

async function main() {
  token.value = 'a'.repeat(64);
  const membersRequest = forms['/v1/collections/members'].fire('submit');
  complete(0, {collection_id: 'collection:private', results: [{
    content_id: 'content:secret', rights_status: 'UNKNOWN', processing_status: 'HELD',
  }]});
  await membersRequest;
  assert.equal(members.children.length, 1, 'fixture must render a private link');

  const mediaRequest = forms['/v1/media/segment'].fire('submit');
  complete(1, {canonical_segment: {
    id: 'segment:secret', start_ms: 1000, end_ms: 2000,
    transcript_status: 'RESOLVED', publication_blocked: true,
  }});
  await mediaRequest;
  assert.match(media.textContent, /segment:secret/, 'fixture must render private location');

  const pending = forms['/v1/corpus/search'].fire('submit');
  clear.fire('click');
  assert.equal(token.value, '');
  assert.equal(members.children.length, 0, 'clear must hide previously fetched private links');
  assert.doesNotMatch(media.textContent, /segment:secret/, 'clear must hide prior media locator');
  complete(2, {private_marker: 'STALE_PRIVATE_AFTER_CLEAR'});
  await pending;
  assert.doesNotMatch(results.textContent, /STALE_PRIVATE_AFTER_CLEAR/,
                      'late response must not restore private output after disconnect');
  assert.match(status.textContent, /disconnesso/i);

  token.value = 'b'.repeat(64);
  const oldRequest = forms['/v1/corpus/search'].fire('submit');
  nav[1].fire('click');
  const latestRequest = forms['/v1/media/segment'].fire('submit');
  complete(4, {canonical_segment: {
    id: 'segment:latest', start_ms: 2500, end_ms: 4500,
    transcript_status: 'RESOLVED', publication_blocked: false,
  }});
  await latestRequest;
  complete(3, {private_marker: 'STALE_PRIOR_WORKSPACE'});
  await oldRequest;
  assert.match(results.textContent, /segment:latest/,
               'newer workspace result should remain visible');
  assert.doesNotMatch(results.textContent, /STALE_PRIOR_WORKSPACE/,
                      'older workspace response must not overwrite newer result');
  assert.match(media.textContent, /segment:latest/);
  process.stdout.write('Studio stale-response and private clear regression PASS\n');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
