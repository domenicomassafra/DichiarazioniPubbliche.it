import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

const root = path.resolve("dist");
const chromeBin = process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const screenshotRoot = path.join(tmpdir(), "dichiarazioni-pubbliche-browser-qa");

const mime = new Map([
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".woff2", "font/woff2"],
  [".svg", "image/svg+xml"],
]);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function exists(file) {
  try {
    await stat(file);
    return true;
  } catch {
    return false;
  }
}

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...await walk(full));
    else out.push(full);
  }
  return out;
}

function routeFor(file) {
  const rel = path.relative(root, file).replaceAll("\\", "/");
  if (rel === "index.html") return "/";
  return `/${rel.replace(/index\.html$/, "")}`;
}

async function startStaticServer() {
  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url || "/", "http://127.0.0.1");
      let pathname = decodeURIComponent(url.pathname);
      if (pathname.endsWith("/")) pathname += "index.html";
      const resolved = path.resolve(root, `.${pathname}`);
      if (!resolved.startsWith(root + path.sep) && resolved !== root) {
        res.writeHead(403).end();
        return;
      }
      const body = await readFile(resolved);
      const type = mime.get(path.extname(resolved)) || "application/octet-stream";
      res.writeHead(200, { "content-type": type, "cache-control": "no-store" });
      res.end(body);
    } catch {
      res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
      res.end("not found");
    }
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  assert(address && typeof address === "object");
  return { server, origin: `http://127.0.0.1:${address.port}` };
}

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    this.listeners = new Map();
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data));
      if (message.id) {
        const pending = this.pending.get(message.id);
        if (!pending) return;
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(`${pending.method}: ${message.error.message}`));
        else pending.resolve(message.result ?? {});
        return;
      }
      for (const listener of this.listeners.get(message.method) ?? []) listener(message.params ?? {});
    });
  }

  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, method });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  on(method, listener) {
    const listeners = this.listeners.get(method) ?? [];
    listeners.push(listener);
    this.listeners.set(method, listeners);
  }

  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "browser evaluation failed");
    return result.result?.value;
  }
}

async function connectCdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
  return new Cdp(ws);
}

async function launchChrome(origin, { scale = 1, zoomFactor = 1 } = {}) {
  const profile = await mkdtemp(path.join(tmpdir(), "dp-chrome-"));
  if (zoomFactor !== 1) {
    const zoomLevel = Math.log(zoomFactor) / Math.log(1.2);
    const hostname = new URL(origin).hostname;
    const defaultProfile = path.join(profile, "Default");
    await mkdir(defaultProfile, { recursive: true });
    await writeFile(
      path.join(defaultProfile, "Preferences"),
      JSON.stringify({
        partition: {
          per_host_zoom_levels: {
            x: {
              [hostname]: { zoom_level: zoomLevel },
            },
          },
        },
      }),
    );
  }
  const args = [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "--window-size=1280,900",
    ...(scale === 1 ? [] : [`--force-device-scale-factor=${scale}`]),
    `${origin}/esplora/`,
  ];
  const child = spawn(chromeBin, args, { stdio: ["ignore", "ignore", "pipe"] });
  const stderrChunks = [];
  child.stderr?.on("data", (chunk) => {
    const text = String(chunk);
    stderrChunks.push(text);
    if (stderrChunks.length > 20) stderrChunks.shift();
  });

  async function cleanup() {
    if (child.exitCode === null && !child.killed) child.kill("SIGTERM");
    await Promise.race([
      new Promise((resolve) => child.once("exit", resolve)),
      sleep(1500),
    ]);
    if (child.exitCode === null) child.kill("SIGKILL");
    for (let attempt = 0; attempt < 40; attempt += 1) {
      try {
        await rm(profile, { recursive: true, force: true });
        return;
      } catch (error) {
        if (attempt === 39) throw error;
        await sleep(50);
      }
    }
  }

  try {
    const activePort = path.join(profile, "DevToolsActivePort");
    for (let attempt = 0; attempt < 300 && !(await exists(activePort)); attempt += 1) {
      if (child.exitCode !== null) {
        throw new Error(`Chrome exited before DevTools was ready (exit ${child.exitCode})`);
      }
      await sleep(50);
    }
    assert(await exists(activePort), "Chrome did not expose DevToolsActivePort within 15 seconds");
    const [port] = (await readFile(activePort, "utf8")).trim().split("\n");
    let target;
    for (let attempt = 0; attempt < 200; attempt += 1) {
      if (child.exitCode !== null) {
        throw new Error(`Chrome exited before a page target was ready (exit ${child.exitCode})`);
      }
      try {
        const targets = await fetch(`http://127.0.0.1:${port}/json/list`).then((response) => response.json());
        target = targets.find((item) => item.type === "page" && item.url.startsWith(origin)) ?? targets.find((item) => item.type === "page");
        if (target?.webSocketDebuggerUrl) break;
      } catch {
        // Chrome can expose the port just before the target list is ready.
      }
      await sleep(50);
    }
    assert(target?.webSocketDebuggerUrl, "Chrome page target unavailable within 10 seconds");
    const cdp = await connectCdp(target.webSocketDebuggerUrl);
    await Promise.all([
      cdp.send("Page.enable"),
      cdp.send("Runtime.enable"),
      cdp.send("Network.enable"),
      cdp.send("Accessibility.enable"),
    ]);
    return {
      child,
      cdp,
      profile,
      async close() {
        try { await cdp.send("Browser.close"); } catch {}
        await cleanup();
      },
    };
  } catch (error) {
    const stderr = stderrChunks.join("").trim();
    await cleanup();
    const detail = stderr ? `\nChrome stderr:\n${stderr.slice(-4000)}` : "";
    throw new Error(`${error.message}${detail}`, { cause: error });
  }
}

async function waitFor(cdp, expression, message, timeoutMs = 6000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await cdp.evaluate(expression)) return;
    await sleep(50);
  }
  throw new Error(message);
}

async function navigate(cdp, url) {
  await cdp.send("Page.navigate", { url });
  await waitFor(cdp, "document.readyState === 'complete'", `page did not load: ${url}`);
}

async function key(cdp, keyName, { modifiers = 0, code = keyName, keyCode = 0, text = "" } = {}) {
  const base = {
    key: keyName,
    code,
    modifiers,
    windowsVirtualKeyCode: keyCode,
    ...(text ? { text, unmodifiedText: text } : {}),
  };
  await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", ...base });
  await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", ...base });
}

function axValue(node, field) {
  return node[field]?.value ?? "";
}

async function screenshot(cdp, name) {
  await rm(screenshotRoot, { recursive: true, force: true }).catch(() => {});
  const shot = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
  const output = path.join(tmpdir(), `dp-${name}.png`);
  await writeFile(output, Buffer.from(shot.data, "base64"));
  return output;
}

const { server, origin } = await startStaticServer();
const externalRequests = [];
const canonicalFiles = (await walk(root)).filter((file) => file.endsWith("index.html"));
const routes = canonicalFiles.map(routeFor).filter((route) => !route.startsWith("/studio/"));
const browser = await launchChrome(origin);
browser.cdp.on("Network.requestWillBeSent", ({ request }) => {
  if (!request?.url || request.url.startsWith("data:") || request.url.startsWith("blob:")) return;
  if (!request.url.startsWith(origin)) externalRequests.push(request.url);
});

try {
  const { cdp } = browser;
  await navigate(cdp, `${origin}/esplora/`);
  await waitFor(cdp, "document.querySelector('.results-count')?.textContent?.includes('risultat')", "Explore did not hydrate");
  const correctionHistoryHref = await cdp.evaluate("document.querySelector('.claim-row-meta a')?.getAttribute('href') ?? ''");
  assert.match(correctionHistoryHref, /^\/dichiarazioni\/[^#]+\/#storia$/, "Explore correction indicator must link to version history");

  const ax = (await cdp.send("Accessibility.getFullAXTree")).nodes;
  assert(ax.some((node) => ["searchbox", "textbox"].includes(axValue(node, "role")) && axValue(node, "name") === "Cerca nel record pubblico"), "search control missing from accessibility tree");
  assert(ax.some((node) => axValue(node, "role") === "radiogroup" && axValue(node, "name") === "Tipo di record"), "record-type radiogroup missing from accessibility tree");
  assert(ax.some((node) => axValue(node, "role") === "button" && axValue(node, "name").startsWith("Filtri")), "filter button missing from accessibility tree");

  await cdp.evaluate("document.querySelector('input[type=radio][value=ALL]').focus()");
  await key(cdp, "ArrowRight", { code: "ArrowRight", keyCode: 39 });
  await waitFor(cdp, "document.querySelector('input[type=radio][value=finding]').checked", "arrow-key radio transition failed");
  assert.equal(await cdp.evaluate("document.activeElement?.value"), "finding", "selected radio did not retain keyboard focus");
  assert.match(await cdp.evaluate("location.search"), /tipo=finding/, "keyboard filter transition did not serialize URL state");

  await cdp.evaluate("document.querySelector('.filter-button').focus()");
  await key(cdp, "Enter", { code: "Enter", keyCode: 13, text: "\r" });
  await waitFor(cdp, "document.querySelector('dialog')?.open === true", "filter dialog did not open from keyboard");
  assert.equal(await cdp.evaluate("document.querySelector('dialog').contains(document.activeElement)"), true, "dialog did not receive focus");
  await key(cdp, "Escape", { code: "Escape", keyCode: 27 });
  await waitFor(cdp, "document.querySelector('dialog')?.open === false", "Escape did not close filter dialog");
  assert.equal(await cdp.evaluate("document.activeElement?.classList.contains('filter-button')"), true, "dialog close did not restore focus");

  await navigate(cdp, `${origin}/esplora/?q=nessunrisultatoimpossibile`);
  await waitFor(cdp, "Boolean(document.querySelector('[data-state=empty]'))", "no-match state missing");
  const emptyCopy = await cdp.evaluate("document.querySelector('[data-state=empty]')?.textContent");
  assert.match(emptyCopy, /Nessun record pubblico corrisponde/);
  assert.match(emptyCopy, /Azzera ricerca e filtri/);

  const overlong = "x".repeat(201);
  await navigate(cdp, `${origin}/esplora/?q=${overlong}`);
  await waitFor(cdp, "Boolean(document.querySelector('[role=alert]'))", "overlong query alert missing");
  assert.match(await cdp.evaluate("document.querySelector('[role=alert]')?.textContent"), /Ricerca troppo lunga/);
  const alertAx = (await cdp.send("Accessibility.getFullAXTree")).nodes;
  assert(alertAx.some((node) => axValue(node, "role") === "alert"), "overlong validation is absent from accessibility tree");

  await navigate(cdp, `${origin}/esplora/`);
  await waitFor(cdp, "document.querySelector('.results-count')?.textContent?.includes('risultat')", "Explore did not restore empty-query results");
  assert.match(await cdp.evaluate("document.querySelector('.results-count')?.textContent"), /^\d+ risultat/);

  await cdp.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
  assert.equal(await cdp.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches"), true, "reduced-motion emulation not observed");
  await cdp.evaluate("document.querySelector('.filter-button').click()");
  await waitFor(cdp, "document.querySelector('dialog')?.open === true", "dialog did not open under reduced motion");
  const motion = await cdp.evaluate(`(() => {
    const style = getComputedStyle(document.querySelector('dialog'));
    return { animationName: style.animationName, animationDuration: style.animationDuration, transitionDuration: style.transitionDuration };
  })()`);
  assert(motion.animationName === "none" || parseFloat(motion.animationDuration) <= 0.001, `reduced-motion animation still active: ${JSON.stringify(motion)}`);
  await key(cdp, "Escape", { code: "Escape", keyCode: 27 });

  await cdp.send("Emulation.setDeviceMetricsOverride", { width: 640, height: 450, deviceScaleFactor: 1, mobile: false });
  await navigate(cdp, `${origin}/esplora/`);
  await waitFor(cdp, "document.querySelector('.results-count')?.textContent?.includes('risultat')", "Explore did not hydrate at 200%-equivalent reflow viewport");
  const reflow = await cdp.evaluate(`({
    viewport: innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    filterHeight: document.querySelector('.filter-button').getBoundingClientRect().height,
    searchWidth: document.querySelector('#client-search').getBoundingClientRect().width
  })`);
  assert.equal(reflow.viewport, 640);
  assert(reflow.scrollWidth <= reflow.viewport + 1, `200%-equivalent reflow has horizontal page overflow: ${JSON.stringify(reflow)}`);
  assert(reflow.filterHeight >= 44, `filter target below 44px: ${reflow.filterHeight}`);
  assert(reflow.searchWidth > 0, "search input disappeared in reflow viewport");

  await cdp.send("Emulation.setDeviceMetricsOverride", { width: 375, height: 812, deviceScaleFactor: 1, mobile: true });
  await navigate(cdp, `${origin}/esplora/`);
  await waitFor(cdp, "document.querySelector('.results-count')?.textContent?.includes('risultat')", "Explore did not hydrate on phone viewport");
  const phone = await cdp.evaluate(`({
    viewport: innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    filterHeight: document.querySelector('.filter-button').getBoundingClientRect().height
  })`);
  assert(phone.scrollWidth <= phone.viewport + 1, `phone viewport has horizontal page overflow: ${JSON.stringify(phone)}`);
  assert(phone.filterHeight >= 44, `phone filter target below 44px: ${phone.filterHeight}`);
  const mobileShot = await screenshot(cdp, "explore-mobile");

  await cdp.send("Emulation.clearDeviceMetricsOverride");
  const legacyPrefixes = ["/fact-check/", "/record/", "/contents/", "/compare/"];
  const scanRoutes = routes.filter((route) => !legacyPrefixes.some((prefix) => route.startsWith(prefix)));
  const forbiddenAx = ["provider_receipt", "raw_transcript", "canonical_transcript", "person_truth_score", "omniroute_api_key"];
  for (const route of scanRoutes) {
    await navigate(cdp, `${origin}${route}`);
    const pageAx = (await cdp.send("Accessibility.getFullAXTree")).nodes;
    const encoded = pageAx.map((node) => `${axValue(node, "role")} ${axValue(node, "name")} ${axValue(node, "description")}`).join("\n").toLowerCase();
    for (const marker of forbiddenAx) assert.equal(encoded.includes(marker), false, `${route}: forbidden accessibility-tree marker ${marker}`);
  }

  await navigate(cdp, `${origin}/persone/person-demo-maintenance/`);
  const personShot = await screenshot(cdp, "person-desktop");
  await navigate(cdp, `${origin}/temi/servizi-pubblici/`);
  const topicShot = await screenshot(cdp, "topic-desktop");

  const zoomBrowser = await launchChrome(origin, { zoomFactor: 2 });
  let zoom200;
  try {
    await navigate(zoomBrowser.cdp, `${origin}/esplora/`);
    await waitFor(
      zoomBrowser.cdp,
      "document.querySelector('.results-count')?.textContent?.includes('risultat')",
      "Explore did not hydrate at exact 200% browser zoom",
    );
    zoom200 = await zoomBrowser.cdp.evaluate(`({
      innerWidth,
      outerWidth,
      devicePixelRatio,
      visualScale: visualViewport.scale,
      scrollWidth: document.documentElement.scrollWidth,
      filterHeight: document.querySelector('.filter-button').getBoundingClientRect().height,
      searchWidth: document.querySelector('#client-search').getBoundingClientRect().width
    })`);
    assert.equal(zoom200.outerWidth, 1280, `unexpected outer width at 200% browser zoom: ${JSON.stringify(zoom200)}`);
    assert.equal(zoom200.innerWidth, 640, `200% browser zoom did not halve CSS viewport: ${JSON.stringify(zoom200)}`);
    assert.equal(zoom200.devicePixelRatio, 2, `200% browser zoom did not double devicePixelRatio: ${JSON.stringify(zoom200)}`);
    assert.equal(zoom200.visualScale, 1, `200% browser zoom was replaced by pinch/page scaling: ${JSON.stringify(zoom200)}`);
    assert(zoom200.scrollWidth <= zoom200.innerWidth + 1, `exact 200% browser zoom has horizontal page overflow: ${JSON.stringify(zoom200)}`);
    assert(zoom200.filterHeight >= 44, `200% browser zoom filter target below 44px: ${zoom200.filterHeight}`);
    assert(zoom200.searchWidth > 0, "search input disappeared at exact 200% browser zoom");
  } finally {
    await zoomBrowser.close();
  }

  assert.deepEqual(externalRequests, [], `browser made external/provider requests: ${externalRequests.join(", ")}`);
  console.log(JSON.stringify({
    status: "PASS",
    routes_scanned: scanRoutes.length,
    external_requests: externalRequests.length,
    reduced_motion: motion,
    reflow_200_equivalent: reflow,
    browser_zoom_200_exact: zoom200,
    phone,
    screenshots: { mobileShot, personShot, topicShot },
  }, null, 2));
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
