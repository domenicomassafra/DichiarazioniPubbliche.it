/* Execute the actual private page script with a deterministic DOM and clipboard. */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const checkCaptureDiff = require('./studio_capture_diff_assertions.cjs');

class Element {
  constructor(extra = {}) {
    this.handlers = new Map();
    this.children = [];
    this.textContent = '';
    this.hidden = false;
    this.value = '';
    Object.assign(this, extra);
  }
  addEventListener(type, handler) { this.handlers.set(type, handler); }
  fire(type) {
    const handler = this.handlers.get(type);
    assert.ok(handler, 'missing ' + type);
    return handler({preventDefault() {}});
  }
  requestSubmit() { return this.fire('submit'); }
  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
  contains(child) { return this.children.includes(child); }
  setAttribute(name, value) { this[name] = value; }
  focus() { this.focused = true; }
}

const html = fs.readFileSync(0, 'utf8');
const inline = html.match(/<script nonce="[0-9a-f]{32}">([\s\S]*?)<\/script>/);
assert.ok(inline, 'nonce-bound Studio JavaScript exists');
const ids = new Map([...html.matchAll(/id="([^"]+)"/g)].map(match => [match[1], new Element()]));
const forms = {};
for (const match of html.matchAll(/<form data-endpoint="([^"]+)"[^>]*>([\s\S]*?)<\/form>/g)) {
  const fields = {};
  for (const field of match[2].matchAll(/name="([^"]+)"[^>]*(?:value="([^"]*)")?/g))
    fields[field[1]] = field[2] ?? '';
  const nodes = Object.fromEntries(Object.keys(fields).map(name => [name, {
    name, get value() { return fields[name]; }, set value(value) { fields[name] = value; },
    focus() { this.focused = true; },
  }]));
  forms[match[1]] = new Element({dataset: {endpoint: match[1]}, fields,
    querySelectorAll: () => Object.values(nodes),
    elements: {namedItem: name => nodes[name] ?? new Element()}});
}
const nav = [...html.matchAll(/data-panel="([^"]+)"/g)].map(
  match => new Element({dataset: {panel: match[1]}}));
const panels = nav.map(button => new Element({id: button.dataset.panel}));
const document = {
  getElementById: id => ids.get(id) ?? null,
  querySelector: selector => forms[selector.match(/data-endpoint="([^"]+)"/)?.[1]] ?? null,
  querySelectorAll: selector => selector === 'form[data-endpoint]' ? Object.values(forms)
    : selector === '[data-panel]' ? nav : selector === 'main > section[id]' ? panels : [],
  createElement: () => new Element(),
};
class FormData {
  constructor(form) { this.form = form; }
  entries() { return Object.entries(this.form.fields)[Symbol.iterator](); }
}
const requests = [];
const copiedReferences = [];
const fetch = (path, options) => new Promise(resolve => requests.push({path, options, resolve}));
vm.runInNewContext(inline[1], {document, FormData, fetch, AbortController,
  navigator: {clipboard: {writeText: async value => { copiedReferences.push(value); }}}});
const complete = (index, data) => requests[index].resolve({ok: true, json: async () => ({
  contract_version: 'studio-local-readonly-api-v1', data,
})});
const token = ids.get('token');
token.value = 'a'.repeat(64);
checkCaptureDiff({forms, requests, complete, ids, copiedReferences,
  clear: ids.get('clear'), token, results: ids.get('results')})
  .then(() => process.stdout.write('DP-419 private Capture diff and audit clipboard PASS\n'))
  .catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
