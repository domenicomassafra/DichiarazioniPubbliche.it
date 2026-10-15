import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';

// Deterministic hook/animation-frame contract test. No browser, UI input or AT
// speech is asserted here: those remain part of DP-412.5's real-world matrix.
const stub = `
const refs = [], effects = [];
let cursor = 0;
export const hooks = { begin() { cursor = 0; }, reset() { refs.length = 0; effects.length = 0; cursor = 0; } };
export function useRef(initialValue) { const i = cursor++; return refs[i] ||= { current: initialValue }; }
export function useEffect(fn, deps) {
  const i = cursor++;
  const prev = effects[i];
  if (prev && deps.length === prev.deps.length && deps.every((v,j) => Object.is(v, prev.deps[j]))) return;
  prev?.cleanup?.();
  const cleanup = fn();
  effects[i] = { deps, cleanup };
}
`;
const dir = await mkdtemp(path.join(tmpdir(), 'dp412-focus-'));
try {
  const file = path.join(dir, 'test-bundle.mjs');
  const bundled = await build({
    stdin: {
      contents: `export { useRestoreFocus } from ${JSON.stringify(path.resolve(import.meta.dirname, '../src/components/design/useFocusTrap.ts'))}; export { hooks } from 'react';`,
      resolveDir: process.cwd(), loader: 'tsx', sourcefile: 'check-focus-entry.tsx'
    },
    bundle: true, format: 'esm', platform: 'node', write: false,
    plugins: [{ name: 'hook-harness', setup(p) {
      p.onResolve({ filter: /^react$/ }, () => ({ path: 'react', namespace: 'mock-react' }));
      p.onLoad({ filter: /.*/, namespace: 'mock-react' }, () => ({ contents: stub, loader: 'js' }));
    }}],
  });
  await writeFile(file, bundled.outputFiles[0].contents);
  const { useRestoreFocus, hooks } = await import(pathToFileURL(file).href);
  let frames, next, focused;
  const makeElement = (id) => ({ id, focus() { focused.push(id); }, connected: true });
  const body = makeElement('body');
  let activeElement;
  globalThis.document = {
    body,
    get activeElement() { return activeElement; },
    contains(el) { return el.connected; },
    querySelector(selector) { assert.equal(selector, '[data-dialog-return-focus]'); return fallback; }
  };
  let fallback;
  globalThis.requestAnimationFrame = (cb) => { const id = ++next; frames.set(id, cb); return id; };
  globalThis.cancelAnimationFrame = (id) => { frames.delete(id); };
  function flush() { for (const [id, cb] of [...frames]) { frames.delete(id); cb(); } }
  function setup() { hooks.reset(); frames = new Map(); next = 0; focused = []; fallback = makeElement('fallback'); }
  function render(active) { hooks.begin(); useRestoreFocus(active); }

  setup();
  const trigger1 = makeElement('trigger1');
  activeElement = trigger1;
  render(true); render(false); flush();
  assert.deepEqual(focused, ['trigger1'], 'ordinary close restores original invoker');

  setup();
  const trigger2 = makeElement('trigger2');
  activeElement = trigger2;
  render(true); render(false);
  assert.equal(frames.size, 1);
  activeElement = body; // Modal/native focus may be absent during fast reopen.
  render(true); // Effect cleanup cancels the first restoration.
  assert.equal(frames.size, 0);
  render(false); flush();
  assert.deepEqual(focused, ['trigger2'], 'close/reopen within one frame must not lose original invoker');

  setup();
  const removed = makeElement('removed');
  activeElement = removed;
  render(true); render(false); removed.connected = false; flush();
  assert.deepEqual(focused, ['fallback'], 'removed trigger uses safe return-focus fallback');

  setup();
  const a = makeElement('a'), b = makeElement('b');
  activeElement = a; render(true); render(false); flush();
  activeElement = b; render(true); render(false); flush();
  assert.deepEqual(focused, ['a', 'b'], 'completed restoration permits next invoker');
  console.log('DP-412 focused hook regression PASS: ordinary, rapid toggle, removed invoker, second invoker (4/4)');
} finally {
  await rm(dir, { recursive: true, force: true });
}
