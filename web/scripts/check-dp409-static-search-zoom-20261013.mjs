/**
 * DP-409.8 supplemental browser probe, deliberately independent of the 640px
 * check-browser-qa.mjs path. No source, dist, provider, or DB writes.
 *
 * Run from web/: node scripts/check-dp409-static-search-zoom-20261013.mjs
 * Serves the already-built synthetic/static dist on loopback, uses ONE Chrome
 * profile at actual per-host 200% zoom, and resizes its window to obtain
 * 320/390 CSS-pixel layouts. On main the known DP-429 focus defect is an
 * observed, explicitly NOT-PASS status (not a default CI failure). Enforce
 * clear-focus acceptance with DP409_REQUIRE_CLEAR_FOCUS=1 against an isolated
 * candidate artifact. A physical screen-reader judgment is not made.
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

const dist = path.resolve(process.env.DP_BROWSER_DIST || "dist");
const chromeBin = process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.seq = 0;
    this.pending = new Map();
    this.listeners = new Map();
    ws.addEventListener("message", (event) => {
      const msg = JSON.parse(String(event.data));
      if (msg.id) {
        const pending = this.pending.get(msg.id);
        if (!pending) return;
        this.pending.delete(msg.id);
        if (msg.error) pending.reject(new Error(`${pending.method}: ${msg.error.message}`));
        else pending.resolve(msg.result ?? {});
      } else {
        for (const fn of this.listeners.get(msg.method) ?? []) fn(msg.params ?? {});
      }
    });
  }

  send(method, params = {}) {
    const id = ++this.seq;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, method });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  on(name, fn) {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), fn]);
  }

  async eval(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression, returnByValue: true, awaitPromise: true,
    });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || expression);
    return result.result?.value;
  }
}

async function until(fn, message) {
  for (let i = 0; i < 160; i += 1) {
    if (await fn()) return;
    await sleep(50);
  }
  throw new Error(message);
}

async function key(cdp, name, code, keyCode, text = "") {
  for (const type of ["keyDown", "keyUp"]) {
    await cdp.send("Input.dispatchKeyEvent", {
      type, key: name, code, windowsVirtualKeyCode: keyCode,
      ...(text ? { text, unmodifiedText: text } : {}),
    });
  }
}

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url || "/", "http://127.0.0.1");
    const pathname = decodeURIComponent(url.pathname);
    const file = path.resolve(dist, `.${pathname.endsWith("/") ? `${pathname}index.html` : pathname}`);
    if (!file.startsWith(`${dist}${path.sep}`)) {
      response.writeHead(403).end();
      return;
    }
    const mime = {
      ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
      ".html": "text/html; charset=utf-8", ".woff2": "font/woff2", ".svg": "image/svg+xml",
    };
    const body = await readFile(file);
    response.writeHead(200, { "content-type": mime[path.extname(file)] || "application/octet-stream", "cache-control": "no-store" });
    response.end(body);
  } catch {
    response.writeHead(404).end("not found");
  }
});

let child;
let ws;
let profile;
try {
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const origin = `http://127.0.0.1:${server.address().port}`;
  const index = JSON.parse(await readFile(path.join(dist, "search-index.v1.json"), "utf8"));
  assert(index.records?.length > 0, "NO_GO: fixture must contain synthetic public search records");
  profile = await mkdtemp(path.join(tmpdir(), "dp409-zoom-"));
  await mkdir(path.join(profile, "Default"));
  await writeFile(path.join(profile, "Default", "Preferences"), JSON.stringify({
    partition: { per_host_zoom_levels: { x: { "127.0.0.1": { zoom_level: Math.log(2) / Math.log(1.2) } } } },
  }));
  child = spawn(chromeBin, [
    "--headless=new", "--disable-gpu", "--disable-background-networking", "--no-first-run",
    "--no-default-browser-check", "--remote-debugging-port=0", `--user-data-dir=${profile}`,
    "--window-size=640,840", `${origin}/esplora/`,
  ], { stdio: "ignore" });
  const portFile = path.join(profile, "DevToolsActivePort");
  await until(async () => stat(portFile).then(() => true, () => false), "Chrome CDP port not available");
  const [port] = (await readFile(portFile, "utf8")).trim().split("\n");
  let target;
  await until(async () => {
    try {
      const pages = await fetch(`http://127.0.0.1:${port}/json/list`).then((res) => res.json());
      target = pages.find((item) => item.type === "page" && item.url.startsWith(origin));
    } catch {}
    return !!target?.webSocketDebuggerUrl;
  }, "Chrome Explore target not available");
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
  const cdp = new Cdp(ws);
  await Promise.all([cdp.send("Page.enable"), cdp.send("Runtime.enable"), cdp.send("Network.enable")]);
  const external = [];
  cdp.on("Network.requestWillBeSent", ({ request }) => {
    if (request?.url && !request.url.startsWith(origin) && !/^(data|blob):/.test(request.url)) external.push(request.url);
  });
  await cdp.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
  const { windowId } = await cdp.send("Browser.getWindowForTarget", { targetId: target.id });
  const results = [];
  for (const cssWidth of [320, 390]) {
    await cdp.send("Browser.setWindowBounds", { windowId, bounds: { width: cssWidth * 2, height: 840 } });
    await cdp.send("Page.navigate", { url: `${origin}/esplora/` });
    await until(() => cdp.eval("document.querySelector('.results-count')?.textContent?.includes('risultat')"), `Explore not hydrated at ${cssWidth}px`);
    const initial = await cdp.eval(`(() => ({
      cssWidth: innerWidth, physicalWidth: outerWidth, dpr: devicePixelRatio,
      pinchScale: visualViewport.scale, scrollWidth: document.documentElement.scrollWidth,
      searchWidth: document.querySelector('#client-search')?.getBoundingClientRect().width,
      filterHeight: document.querySelector('.filter-row .filter-button')?.getBoundingClientRect().height,
      reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
    }))()`);
    assert.equal(initial.cssWidth, cssWidth, `${cssWidth}: not exact browser zoom/reflow ${JSON.stringify(initial)}`);
    assert.equal(initial.physicalWidth, cssWidth * 2);
    assert.equal(initial.dpr, 2);
    assert.equal(initial.pinchScale, 1);
    assert(initial.scrollWidth <= cssWidth + 1, `${cssWidth}: horizontal overflow ${JSON.stringify(initial)}`);
    assert(initial.searchWidth > 0 && initial.filterHeight >= 44 && initial.reduced);

    await cdp.eval("document.querySelector('#client-search').focus()");
    await cdp.send("Input.insertText", { text: "servizi" });
    await until(() => cdp.eval("Boolean(document.querySelector('button[aria-label=\"Pulisci ricerca\"]'))"), "Clear search did not appear");
    await cdp.eval("document.querySelector('button[aria-label=\"Pulisci ricerca\"]').focus()");
    await key(cdp, "Enter", "Enter", 13, "\r");
    await until(() => cdp.eval("document.querySelector('#client-search')?.value === ''"), "Clear did not empty query");
    const clearFocus = await cdp.eval("({ activeTag: document.activeElement?.tagName, activeId: document.activeElement?.id, bodyFocused: document.activeElement === document.body, clearGone: !document.querySelector('button[aria-label=\"Pulisci ricerca\"]') })");

    await cdp.eval("document.querySelector('.filter-row .filter-button').focus()");
    await key(cdp, "Enter", "Enter", 13, "\r");
    await until(() => cdp.eval("document.querySelector('dialog')?.open === true"), "Filter sheet did not open from keyboard");
    const openState = await cdp.eval("({ expanded: document.querySelector('.filter-row .filter-button').getAttribute('aria-expanded'), focusedInside: document.querySelector('dialog').contains(document.activeElement), motion: getComputedStyle(document.querySelector('dialog')).animationDuration })");
    assert.equal(openState.expanded, "true");
    assert.equal(openState.focusedInside, true);
    assert(parseFloat(openState.motion) <= .001, `${cssWidth}: reduced motion not respected`);
    // Synthetic selection tests public URL/React restoration, not native
    // OS-specific keyboard behavior of the platform <select> popup.
    await cdp.eval("(() => { const select = document.querySelector('#explore-filter-dialog select'); select.value = 'person'; select.dispatchEvent(new Event('change', { bubbles: true })); })()");
    await until(() => cdp.eval("new URLSearchParams(location.search).get('tipo') === 'person'"), "Selected filter not reflected in shareable URL");
    await cdp.eval("document.querySelector('#explore-filter-dialog button[aria-label=\"Chiudi filtri\"]').focus()");
    await key(cdp, "Escape", "Escape", 27);
    await until(() => cdp.eval("document.querySelector('dialog')?.open === false"), "Escape did not close sheet");
    await until(() => cdp.eval("document.querySelector('.filter-row .filter-button').getAttribute('aria-expanded') === 'false'"), "Escape did not restore collapsed ARIA state");
    const closed = await cdp.eval("({ focusedOnButton: document.activeElement === document.querySelector('.filter-row .filter-button'), expanded: document.querySelector('.filter-row .filter-button').getAttribute('aria-expanded') })");
    assert.equal(closed.focusedOnButton, true);
    assert.equal(closed.expanded, "false");
    await key(cdp, "Enter", "Enter", 13, "\r");
    await until(() => cdp.eval("document.querySelector('dialog')?.open === true"), "Selected filter dialog did not reopen");
    const selectedAfterReopen = await cdp.eval("document.querySelector('#explore-filter-dialog select')?.value");
    assert.equal(selectedAfterReopen, "person", `${cssWidth}: selected filter state not preserved`);
    await key(cdp, "Escape", "Escape", 27);
    await until(() => cdp.eval("document.querySelector('dialog')?.open === false"), "Reopened dialog Escape failed");
    results.push({ cssWidth, initial, clearFocus, openState, closed, selectedAfterReopen });
  }
  assert.deepEqual(external, [], `External/provider traffic: ${external.join(", ")}`);
  const clearFocusPass = results.every((value) => value.clearFocus.activeId === "client-search");
  console.log(JSON.stringify({
    status: clearFocusPass ? "BROWSER_PROBE_PASS_MANUAL_AT_PENDING" : "BROWSER_PROBE_CLEAR_FOCUS_GAP",
    static_fixture_records: index.records.length,
    zoom200: results,
    clear_focus_pass: clearFocusPass,
    external_requests: external.length,
    screen_reader_manual: "PENDING",
  }, null, 2));
  if (process.env.DP409_REQUIRE_CLEAR_FOCUS === "1") {
    assert(clearFocusPass, "DP409: keyboard clear loses focus from search input");
  }
} finally {
  try { ws?.close(); } catch {}
  if (child && child.exitCode === null) child.kill("SIGTERM");
  if (profile) await rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
  await new Promise((resolve) => server.close(resolve));
}
