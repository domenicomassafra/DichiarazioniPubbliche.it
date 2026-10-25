"""DOM harness for the private Studio Collection navigation scenario."""

from tests.studio_collection_vertical_scenario_js import _COLLECTION_VERTICAL_SCENARIO_JS

_COLLECTION_VERTICAL_JS = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const html = fs.readFileSync(0, 'utf8');
const script = html.match(/<script nonce="[0-9a-f]{32}">([\s\S]*?)<\/script>/);
assert.ok(script);
class Element {
  constructor(extra = {}) { this.children = []; this.handlers = new Map();
    this.hidden = false; this.textContent = ''; this.value = ''; Object.assign(this, extra); }
  addEventListener(type, fn) { this.handlers.set(type, fn); }
  fire(type) { assert.ok(this.handlers.has(type), 'missing ' + type);
    return this.handlers.get(type)({preventDefault() {}}); }
  requestSubmit() { return this.fire('submit'); }
  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
  contains(child) { return this.children.includes(child); }
  focus() { this.focused = true; }
  setAttribute(name, value) { this[name] = value; }
}
const ids = new Map([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], new Element()]));
const forms = {};
for (const m of html.matchAll(/<form data-endpoint="([^"]+)"[^>]*>([\s\S]*?)<\/form>/g)) {
  const fields = {};
  for (const field of m[2].matchAll(/name="([^"]+)"[^>]*(?:value="([^"]*)")?/g)) {
    fields[field[1]] = field[2] ?? '';
  }
  const elements = Object.fromEntries(Object.keys(fields).map(name => [name, {
    name, get value() { return fields[name]; }, set value(value) { fields[name] = value; },
    focus() { this.focused = true; },
  }]));
  forms[m[1]] = new Element({dataset: {endpoint: m[1]}, fields,
    elements: {namedItem: name => elements[name] ?? new Element()},
    querySelectorAll: () => Object.values(elements)});
}
const nav = [...html.matchAll(/data-panel="([^"]+)"/g)].map(m => new Element({dataset: {panel: m[1]}}));
const panels = nav.map(button => new Element({id: button.dataset.panel}));
const document = {getElementById: id => ids.get(id) ?? null,
  querySelector: selector => forms[selector.match(/data-endpoint="([^"]+)"/)?.[1]] ?? null,
  querySelectorAll: selector => selector === 'form[data-endpoint]' ? Object.values(forms)
    : selector === '[data-panel]' ? nav : selector === 'main > section[id]' ? panels : [],
  createElement: () => new Element()};
class FormData { constructor(form) { this.form = form; }
  entries() { return Object.entries(this.form.fields)[Symbol.iterator](); } }
const requests = [];
const fetch = (path, options) => new Promise(resolve => requests.push({path, options, resolve}));
vm.runInNewContext(script[1], {document, fetch, FormData, AbortController});
const token = ids.get('token');
token.value = 'a'.repeat(64);
const sha = 'a'.repeat(64), passageHash = 'b'.repeat(64);
function reply(data, {ok = true} = {}) {
  const request = requests[requests.length - 1];
  request.resolve({ok, json: async () => ({contract_version: 'studio-local-readonly-api-v1', data})});
}
const base = {private_only: true, publication_authority: false, rights_clearance: false};
async function drain() { await new Promise(resolve => setImmediate(resolve)); }
""" + _COLLECTION_VERTICAL_SCENARIO_JS
