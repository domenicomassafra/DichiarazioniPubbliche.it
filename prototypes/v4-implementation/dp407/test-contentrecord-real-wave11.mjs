// DP-407 mounted Content route, isolated public-fixture + real Chrome accessibility test.
// Run from the repo root: node prototypes/v4-implementation/dp407/test-contentrecord-real-wave11.mjs
// This is NOT a live projection, deployment, or manual screen-reader acceptance.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { createServer } from "node:http";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const webRoot = path.join(root, "web");
const fixture = path.join(webRoot, "src/data/dp407-content-projection.json");
const fixtureData = JSON.parse(await readFile(fixture, "utf8"));
const contentId = "content:demo:maintenance";
const relevant = fixtureData.dossiers.filter((dossier) => dossier.source.content_id === contentId);
assert.equal(relevant.length, 12, "bounded public-schema fixture must contain 12 same-Content moments");
const target = relevant.find((item) => item.finding_id.endsWith("moment-06"));
assert(target, "sixth fixture moment missing");

const built = spawnSync("npm", ["run", "build"], {
  cwd: webRoot, encoding: "utf8", maxBuffer: 8 * 1024 * 1024,
  env: {
    ...process.env,
    DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: "1",
    DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: fixture,
  },
});
if (built.status !== 0) {
  throw new Error(`DP-407 isolated static build failed:\n${(built.stderr || built.stdout).slice(-5000)}`);
}
const dist = path.join(webRoot, "dist");
const canonicalPath = "/contenuti/content-demo-maintenance/";
await stat(path.join(dist, canonicalPath, "index.html"));
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".woff2": "font/woff2" };
const visited = [];
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://127.0.0.1");
    visited.push(url.pathname);
    const requestedPath = url.pathname.endsWith("/") ? `${url.pathname}index.html` : url.pathname;
    const resolved = path.resolve(dist, `.${requestedPath}`);
    if (!resolved.startsWith(`${dist}${path.sep}`)) {
      response.writeHead(403).end();
      return;
    }
    const body = await readFile(resolved);
    response.writeHead(200, { "Content-Type": `${mime[path.extname(resolved)] || "application/octet-stream"}; charset=utf-8` });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const profile = await mkdtemp(path.join(tmpdir(), "dp407-real-wave11-"));
const chrome = process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const startingMoment = "finding:demo:maintenance-moment-02";
const initialUrl = `${origin}${canonicalPath}?momento=${encodeURIComponent(startingMoment)}&keep=fixture#position`;
const child = spawn(chrome, ["--headless=new", "--disable-gpu", "--disable-background-networking",
  "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=0",
  `--user-data-dir=${profile}`, initialUrl], { stdio: "ignore" });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let ws;
try {
  let port;
  for (let i = 0; i < 240; i++) {
    if (child.exitCode !== null) throw new Error(`Chrome stopped unexpectedly (${child.exitCode})`);
    try {
      port = (await readFile(path.join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0];
      break;
    } catch { await sleep(50); }
  }
  assert(port, "Chrome remote debugging unavailable");
  let page;
  for (let i = 0; i < 240; i++) {
    try {
      const candidates = await fetch(`http://127.0.0.1:${port}/json/list`).then((res) => res.json());
      page = candidates.find((item) => item.type === "page" && item.url.startsWith(origin));
      if (page?.webSocketDebuggerUrl) break;
    } catch { /* DevTools discovery still starting */ }
    await sleep(50);
  }
  assert(page?.webSocketDebuggerUrl, "Chrome Content route target unavailable");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
  const pending = new Map();
  let currentId = 0;
  ws.addEventListener("message", ({ data }) => {
    const response = JSON.parse(data);
    if (!response.id) return;
    const job = pending.get(response.id);
    if (!job) return;
    pending.delete(response.id);
    if (response.error) job.reject(new Error(response.error.message));
    else job.resolve(response.result);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++currentId;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression) => {
    const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  };
  const waitFor = async (expression, description) => {
    for (let i = 0; i < 120; i++) {
      if (await evaluate(expression)) return;
      await sleep(50);
    }
    throw new Error(`Content route did not reach ${description}`);
  };
  await Promise.all([send("Runtime.enable"), send("DOM.enable"), send("Accessibility.enable"), send("Page.enable")]);
  await send("Page.bringToFront");
  await waitFor("document.querySelectorAll('.content-tape [data-content-select]').length === 12", "12 timed moment markers");
  await waitFor(`document.querySelector('[data-content-detail="${startingMoment}"]')?.hidden === false`, "deep-linked second moment");

  const markerSelector = `.content-tape [data-content-select="${target.finding_id}"]`;
  const dom = await send("DOM.getDocument");
  const node = await send("DOM.querySelector", { nodeId: dom.root.nodeId, selector: markerSelector });
  assert(node.nodeId, "real mounted marker not present");
  const ax = await send("Accessibility.getPartialAXTree", { nodeId: node.nodeId, fetchRelatives: false });
  const markerAx = ax.nodes.find((item) => item.role?.value === "button");
  assert(markerAx, "timed marker is not an accessible button");
  const accessibleName = String(markerAx.name?.value ?? "");
  assert(accessibleName.includes(target.claim),
    `Timed marker accessible name does not identify its published claim: ${JSON.stringify(accessibleName)}`);

  await evaluate(`document.querySelector(${JSON.stringify(markerSelector)}).focus()`);
  assert(await evaluate(`document.activeElement?.matches(${JSON.stringify(markerSelector)})`), "marker focus was not set");
  for (const type of ["keyDown", "keyUp"]) {
    await send("Input.dispatchKeyEvent", { type, key: " ", code: "Space", windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 49, text: " " });
  }
  await waitFor(`document.querySelector('[data-content-detail="${target.finding_id}"]')?.hidden === false`, "keyboard-selected detail");
  const actual = await evaluate(`JSON.stringify({
    selected: document.querySelector('.content-moment__detail:not([hidden])')?.dataset.contentDetail,
    currentTape: document.querySelector('.content-tape [aria-current="true"]')?.dataset.contentSelect,
    expandedList: document.querySelector('.content-moment__button[aria-expanded="true"]')?.dataset.contentSelect,
    focused: document.activeElement?.getAttribute('data-content-select'),
    momento: new URL(location.href).searchParams.get('momento'),
    keep: new URL(location.href).searchParams.get('keep'),
    hash: location.hash,
    detailControls: document.querySelector(${JSON.stringify(markerSelector)}).getAttribute('aria-controls')
  })`);
  const state = JSON.parse(actual);
  assert.equal(state.selected, target.finding_id);
  assert.equal(state.currentTape, target.finding_id);
  assert.equal(state.expandedList, target.finding_id);
  assert.equal(state.focused, target.finding_id);
  assert.equal(state.momento, target.finding_id);
  assert.equal(state.keep, "fixture");
  assert.equal(state.hash, "#position");
  assert(await evaluate(`!!document.getElementById(${JSON.stringify(state.detailControls)})`));
  assert(visited.every((uri) => uri === "/favicon.ico" || uri.startsWith("/_astro/") || uri === canonicalPath),
    `unexpected local resource fetch: ${visited.join(", ")}`);
  const loadedResources = JSON.parse(await evaluate("JSON.stringify(performance.getEntriesByType('resource').map(entry => entry.name))"));
  assert(loadedResources.every((url) => url.startsWith(`${origin}/`)), "browser loaded an external resource");
  const publicHtml = await readFile(path.join(dist, canonicalPath, "index.html"), "utf8");
  for (const privateField of ["transcript_candidates", "provider_receipt", "raw_text", "canonical_text", "evidence_body", "person_score"]) {
    assert(!publicHtml.includes(privateField), `private/non-projection field in public output: ${privateField}`);
  }
  console.log("PASS real ContentRecord.astro: 12 public-fixture moments, Chrome AX name, deep link, Space key, focus, detail, URL; public-only HTML and local browser resources");
} finally {
  try { ws?.close(); } catch { /* connection already closed */ }
  child.kill("SIGTERM");
  await Promise.race([new Promise((resolve) => child.once("exit", resolve)), sleep(1600)]);
  if (child.exitCode === null) child.kill("SIGKILL");
  await new Promise((resolve) => server.close(resolve));
  await rm(profile, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
}
