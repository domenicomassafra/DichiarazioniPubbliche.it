const assert = require("node:assert/strict");
const { mkdtemp, rm, writeFile } = require("node:fs/promises");
const { tmpdir } = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { build } = require("esbuild");

// Deterministic React effect + RAF fixture for the *real* Dialog module.
// It proves focus scheduling, not screen-reader speech or browser focus.
const hooks = `
const effects = [];
export function useRef(value) { return { current: value }; }
export function useId() { return "dialog-test-heading"; }
export function useEffect(fn) { effects.push(fn); }
export const harness = {
  reset() { effects.length = 0; },
  commit() { for (const fn of effects) fn(); },
};
`;
const jsx = `
export const jsx = (type, props) => ({ type, props });
export const jsxs = jsx;
export const Fragment = Symbol("Fragment");
`;

async function run() {
  const dir = await mkdtemp(path.join(tmpdir(), "dp412-dialog-focus-"));
  try {
    const source = path.resolve(__dirname, "../src/components/design/Dialog.tsx");
    const result = await build({
      stdin: {
        contents: `export { Dialog } from ${JSON.stringify(source)}; export { harness } from "react";`,
        resolveDir: path.dirname(source),
        sourcefile: "dialog-initial-focus-test.tsx",
        loader: "tsx",
      },
      bundle: true,
      platform: "node",
      format: "esm",
      jsx: "automatic",
      write: false,
      plugins: [{ name: "react-effects-fixture", setup(plugin) {
        plugin.onResolve({ filter: /^react$/ }, () => ({ path: "react", namespace: "fixture" }));
        plugin.onResolve({ filter: /^react\/jsx-runtime$/ }, () => ({ path: "jsx", namespace: "fixture" }));
        plugin.onLoad({ filter: /.*/, namespace: "fixture" }, (args) => ({
          contents: args.path === "react" ? hooks : jsx,
          loader: "js",
        }));
      } }],
    });
    const bundle = path.join(dir, "dialog-test.mjs");
    await writeFile(bundle, result.outputFiles[0].contents);
    const { Dialog, harness } = await import(pathToFileURL(bundle).href);

    for (const initialFocus of ["close", "body"]) {
      harness.reset();
      const focused = [];
      const pending = new Map();
      let frame = 0;
      let showModalCalls = 0;
      const close = { focus() { focused.push("close"); } };
      const dialog = {
        open: false,
        showModal() { showModalCalls++; this.open = true; },
        querySelector(selector) { return selector === "[data-overlay-close]" ? close : null; },
        focus() { focused.push("body"); },
        addEventListener() {},
      };
      globalThis.document = { body: {}, activeElement: { id: "invoker" } };
      globalThis.requestAnimationFrame = (fn) => { pending.set(++frame, fn); return frame; };
      globalThis.cancelAnimationFrame = (id) => pending.delete(id);

      const view = Dialog({ open: true, onClose() {}, title: "Prova", initialFocus });
      view.props.ref.current = dialog;
      harness.commit();
      for (const callback of pending.values()) callback();

      assert.equal(showModalCalls, 1, "one native modal open");
      assert.deepEqual(focused, [initialFocus], `initialFocus=${initialFocus} must focus exactly once`);
    }
    console.log("DP-412 Dialog initial focus scheduling PASS: close, body (2/2)");
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
