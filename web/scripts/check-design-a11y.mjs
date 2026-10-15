import assert from "node:assert/strict";
import { readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { build } from "esbuild";

// Node-only contract regression: real assistive-technology acceptance belongs
// to AC-412.5's separate manual matrix. Do not label markup checks as AT proof.
const root = path.resolve(import.meta.dirname, "..");
const compiledPath = path.join(root, "scripts", `.dp412-a11y-${process.pid}.mjs`);
const entry = [
  'export { Button, dispatchButtonClick } from "../src/components/design/Button";',
  'export { TextField } from "../src/components/design/TextField";',
  'export { EmptyState, ErrorState, SkeletonRegion, Skeleton } from "../src/components/design/States";',
  'export { StatusText } from "../src/components/design/StatusText";',
  'export { SegmentedControl } from "../src/components/design/SegmentedControl";',
  'export { Disclosure } from "../src/components/design/Disclosure";',
  'export { Dialog } from "../src/components/design/Dialog";',
].join("\n");

let components;
try {
  const result = await build({
    stdin: { contents: entry, resolveDir: path.join(root, "scripts"), sourcefile: "dp412-entry.tsx", loader: "tsx" },
    bundle: true,
    format: "esm",
    platform: "node",
    packages: "external",
    write: false,
    outfile: compiledPath,
  });
  await writeFile(compiledPath, result.outputFiles[0].contents);
  components = await import(pathToFileURL(compiledPath).href);
} finally {
  await rm(compiledPath, { force: true });
}

const render = (Component, props, ...children) =>
  renderToStaticMarkup(createElement(Component, props, ...children));
let checks = 0;
function check(name, callback) {
  callback();
  checks += 1;
  console.log(`PASS ${name}`);
}

check("Busy buttons stay focusable, and native-disabled controls do not", () => {
  const busy = render(components.Button, { busy: true, type: "submit" }, "Invia");
  assert.match(busy, /aria-busy="true"/);
  assert.match(busy, /aria-disabled="true"/);
  assert.doesNotMatch(busy, /\sdisabled(=|\s|>)/);
  assert.match(busy, />Invia<\/span>/);
  const disabled = render(components.Button, { disabled: true }, "Non disponibile");
  assert.match(disabled, /\sdisabled=""/);
});

check("Busy button activation is suppressed before callbacks and form submission", () => {
  let clicks = 0;
  let prevented = 0;
  let stopped = 0;
  const event = {
    preventDefault: () => { prevented += 1; },
    stopPropagation: () => { stopped += 1; },
  };
  components.dispatchButtonClick(true, event, () => { clicks += 1; });
  assert.deepEqual({ clicks, prevented, stopped }, { clicks: 0, prevented: 1, stopped: 1 });
  components.dispatchButtonClick(false, event, () => { clicks += 1; });
  assert.deepEqual({ clicks, prevented, stopped }, { clicks: 1, prevented: 1, stopped: 1 });
});

check("Search field error and hint both have existing described-by targets", () => {
  const html = render(components.TextField, {
    label: "Cerca nel record", name: "q", value: "", onChange: () => {},
    hint: "Inserisci parole di ricerca", error: "Inserisci almeno due caratteri",
  });
  assert.match(html, /<label[^>]+for="([^"]+)"/);
  assert.match(html, /aria-invalid="true"/);
  const described = html.match(/aria-describedby="([^"]+)"/)?.[1]?.split(" ") ?? [];
  assert.equal(described.length, 2, "hint and error need distinct description IDs");
  for (const id of described) {
    assert(html.includes(`id="${id}"`), `unresolved aria-describedby target ${id}`);
  }
  assert.match(html, /role="alert"/);
});

check("EmptyState keeps the required base class with caller CSS", () => {
  const html = render(components.EmptyState, { title: "Nessun risultato", body: "Riprova", className: "fixture-extra" });
  assert.match(html, /class="dp-state fixture-extra"/);
  assert.match(html, /data-state="empty"/);
});

check("Finding states are written, and decorative marks stay out of the accessibility tree", () => {
  for (const state of ["supported", "contradicted", "imprecise", "unresolved"]) {
    const html = render(components.StatusText, { state });
    assert(html.includes(`data-state="${state}"`));
    assert.match(html, /class="dp-status__mark" aria-hidden="true"/);
    assert.match(html, /class="dp-status__label">[^<]+<\/span>/);
  }
  assert.equal(render(components.StatusText, { state: "supported", label: "" }), "");
  assert.equal(render(components.StatusText, { state: "supported", count: 99 }), "");
});

check("Native radio/disclosure semantics and text-first system states are present", () => {
  const segment = render(components.SegmentedControl, {
    label: "Tipo", name: "tipo", value: "all", onChange: () => {},
    options: [{ value: "all", label: "Tutte" }, { value: "docs", label: "Documenti", disabled: true }],
  });
  assert.match(segment, /role="radiogroup"/);
  assert.match(segment, /<legend[^>]*>Tipo<\/legend>/);
  assert.match(segment, /type="radio"[^>]+checked=""/);
  assert.match(segment, /type="radio"[^>]+disabled=""/);
  assert.match(render(components.Disclosure, { summary: "Dettagli" }, "Contenuto"), /<details[^>]*><summary[^>]*>/);
  assert.match(render(components.ErrorState, { title: "Errore", body: "Riprova" }), /role="alert"/);
  assert.match(render(components.ErrorState, { title: "Non disponibile", body: "Riprova", variant: "blocked" }), /role="status"/);
  assert.match(render(components.Skeleton, {}), /aria-hidden="true"/);
  assert.match(render(components.SkeletonRegion, { label: "Caricamento" }, createElement(components.Skeleton)), /aria-busy="true"/);
});

check("The dialog is named by its visible title rather than being an unnamed native modal", () => {
  const html = render(components.Dialog, {
    open: false, onClose: () => {}, title: "Dialogo di prova",
  }, "Contenuto di prova");
  const reference = html.match(/<dialog[^>]*aria-labelledby="([^"]+)"/)?.[1];
  assert(reference, "dialog must explicitly point to its visible heading");
  assert(html.includes(`<h2 id="${reference}" class="dp-overlay__title">Dialogo di prova</h2>`),
    "accessible dialog name must be its visible title");
});

const css = await readFile(path.join(root, "src/styles/tokens.css"), "utf8");
const primitives = await readFile(path.join(root, "src/styles/primitives.css"), "utf8");
const literals = new Map([...css.matchAll(/(--[a-z0-9-]+):\s*(#[0-9a-f]{6})\s*;/gi)]
  .map((match) => [match[1], match[2]]));
const channel = (value) => {
  const value01 = parseInt(value, 16) / 255;
  return value01 <= 0.04045 ? value01 / 12.92 : ((value01 + 0.055) / 1.055) ** 2.4;
};
const luminance = (hex) => {
  const rgb = [hex.slice(1, 3), hex.slice(3, 5), hex.slice(5, 7)];
  return rgb.reduce((sum, color, i) => sum + channel(color) * [0.2126, 0.7152, 0.0722][i], 0);
};
const contrast = (a, b) => {
  const first = luminance(literals.get(a));
  const second = luminance(literals.get(b));
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
};

check("Status/text tokens meet AA and controls meet non-text contrast against paper", () => {
  for (const role of ["--ink-500", "--ink-700", "--ink-900", "--cobalt-700",
    "--support-700", "--contradict-700", "--imprecise-700", "--unresolved-700"]) {
    assert(contrast(role, "--paper-0") >= 4.5, `${role}: insufficient text contrast`);
  }
  assert(contrast("--rule-control", "--paper-0") >= 3, "control boundary lacks non-text contrast");
  assert(contrast("--focus-ring-color", "--paper-0") >= 3, "focus indicator lacks contrast");
});

check("Reduced-motion variants keep static loading/selection states", () => {
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(primitives, /@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.dp-button__spinner\s*\{\s*animation:\s*none/);
  assert.match(primitives, /@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.dp-skeleton::after\s*\{\s*animation:\s*none/);
  assert.match(primitives, /\.dp-segmented__option\[data-checked='true'\]::after/);
});

console.log(JSON.stringify({ result: "PASS", checks, scope: "Node SSR/contract/contrast", manual_screen_reader: "PENDING", exact_browser_zoom: "covered by separate browser QA" }));
