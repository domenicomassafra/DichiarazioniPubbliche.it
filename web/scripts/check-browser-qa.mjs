import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

// Allow a complete browser acceptance pass against a freshly built isolated
// artifact; QA must never depend on a previously populated shared web/dist.
const root = path.resolve(process.env.DP_BROWSER_DIST || "dist");
const chromeBin = process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const screenshotRoot = path.join(tmpdir(), "dichiarazioni-pubbliche-browser-qa");
const dp422CaptureDir = process.env.DP422_CAPTURE_DIR;

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
        // Chrome can close the DevTools transport before answering Browser.close.
        // Always release the child/profile and WebSocket so CI terminates.
        try { await Promise.race([cdp.send("Browser.close"), sleep(750)]); } catch {}
        finally {
          cdp.ws.close();
          await cleanup();
        }
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

async function dp422Screenshot(cdp, family, variant) {
  if (!dp422CaptureDir) return null;
  await mkdir(dp422CaptureDir, { recursive: true });
  const shot = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
  const output = path.join(dp422CaptureDir, `${family}-${variant}.png`);
  await writeFile(output, Buffer.from(shot.data, "base64"));
  return output;
}

const { server, origin } = await startStaticServer();
const externalRequests = [];
const canonicalFiles = (await walk(root)).filter((file) => file.endsWith("index.html"));
const routes = canonicalFiles.map(routeFor).filter((route) => !route.startsWith("/studio/"));
const searchIndex = JSON.parse(await readFile(path.join(root, "search-index.v1.json"), "utf8"));
assert(Array.isArray(searchIndex.records), "search index records must be an array");
const correctedRecords = searchIndex.records.filter((record) =>
  record.kind === "finding" && (record.has_corrections || record.has_rights_of_reply)
);
const browser = await launchChrome(origin);
browser.cdp.on("Network.requestWillBeSent", ({ request }) => {
  if (!request?.url || request.url.startsWith("data:") || request.url.startsWith("blob:")) return;
  if (!request.url.startsWith(origin)) externalRequests.push(request.url);
});

async function runBrowserChecks() {
try {
  const { cdp } = browser;
  // An approved empty projection has no React search controls to hydrate.
  // Verify the actual static launch experience in one Chrome process instead.
  if (searchIndex.records.length === 0) {
    const checked = [];
    const screenshots = {};
    await cdp.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
    for (const width of [1280, 390, 320]) {
      await cdp.send("Emulation.setDeviceMetricsOverride", { width, height: 840, deviceScaleFactor: 1, mobile: width < 500 });
      for (const route of ["/", "/esplora/", "/metodo/", "/correzioni/", "/dati/", "/progetto/"]) {
        await navigate(cdp, `${origin}${route}`);
        const state = await cdp.evaluate(`({
          viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth,
          heading: document.querySelector('main h1')?.textContent ?? '',
          headings: document.querySelectorAll('main h1').length,
          mainCount: document.querySelectorAll('main').length,
          demo: /garlasco|ambiente dimostrativo|finding-demo/i.test(document.body.innerText),
          reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
          canonical: document.querySelector('link[rel="canonical"]')?.getAttribute('href'),
          navigation: [...document.querySelectorAll('header a')].filter(a => a.getAttribute('href')?.startsWith('/')).map(a => a.getAttribute('href'))
        })`);
        assert.equal(state.viewport, width, `${route}: viewport mismatch`);
        assert(state.scrollWidth <= width + 1, `${route} ${width}px: horizontal overflow ${state.scrollWidth}`);
        assert.equal(state.mainCount, 1, `${route}: expected one main landmark`);
        assert.equal(state.headings, 1, `${route}: expected one primary heading`);
        assert(state.heading.trim().length > 0, `${route}: page h1 missing`);
        assert.equal(state.reducedMotion, true, `${route}: reduced-motion preference was lost`);
        assert.equal(state.canonical, route, `${route}: canonical URL mismatch`);
        assert.equal(state.demo, false, `${route}: demo or forbidden topic visible`);
        if (route === "/esplora/") {
          assert.equal(await cdp.evaluate("!!document.querySelector('.launch-empty-state')"), true, "approved empty state missing");
          assert.equal(await cdp.evaluate("!!document.querySelector('.claim-row')"), false, "phantom public row on empty state");
        }
        if (route === "/") {
          assert.equal(await cdp.evaluate("!!document.querySelector('.home-launch-status')"), true, "launch readiness status missing");
          assert.equal(await cdp.evaluate("!!document.querySelector('.home-recent .claim-row')"), false, "phantom recent finding");
        }
        if (width === 1280 && route === "/") screenshots.homeDesktop = await screenshot(cdp, "launch-home-desktop");
        if (width === 390 && route === "/esplora/") screenshots.exploreMobile = await screenshot(cdp, "launch-explore-mobile");
        checked.push(`${route}@${width}`);
      }
    }
    await cdp.send("Emulation.setDeviceMetricsOverride", { width: 390, height: 840, deviceScaleFactor: 1, mobile: true });
    await navigate(cdp, `${origin}/esplora/`);
    const axNodes = (await cdp.send("Accessibility.getFullAXTree")).nodes;
    assert(axNodes.some((node) => axValue(node, "role") === "heading" && axValue(node, "name") === "Non ci sono ancora record pubblicati."), "empty state is not exposed as an accessibility heading");
    assert(axNodes.some((node) => axValue(node, "role") === "navigation" && axValue(node, "name") === "Informazioni sul progetto"), "empty-state links lack a named navigation landmark");
    await cdp.evaluate("document.querySelector('.launch-empty-links a[href=\"/metodo/\"]').focus()");
    assert.equal(await cdp.evaluate("document.activeElement?.getAttribute('href')"), "/metodo/", "empty-state link is not keyboard focusable");
    await key(cdp, "Tab", { code: "Tab", keyCode: 9 });
    assert.equal(await cdp.evaluate("document.activeElement?.getAttribute('href')"), "/progetto/", "empty-state link order is not keyboard accessible");
    await key(cdp, "Tab", { code: "Tab", keyCode: 9, modifiers: 8 });
    assert.equal(await cdp.evaluate("document.activeElement?.getAttribute('href')"), "/metodo/", "reverse keyboard tab order failed in empty state");
    await key(cdp, "Enter", { code: "Enter", keyCode: 13, text: "\r" });
    await waitFor(cdp, "location.pathname === '/metodo/'", "empty-state keyboard navigation failed");

    await navigate(cdp, `${origin}/esplora/`);
    await cdp.send("Emulation.setEmulatedVisionDeficiency", { type: "achromatopsia" });
    screenshots.exploreGrayscale = await screenshot(cdp, "launch-explore-grayscale");
    await cdp.send("Emulation.setEmulatedVisionDeficiency", { type: "none" });
    await cdp.send("Emulation.clearDeviceMetricsOverride");

    // The second Chrome session applies actual 200% browser zoom via profile
    // settings; viewport emulation or pinch scaling would not prove reflow.
    const zoomBrowser = await launchChrome(origin, { zoomFactor: 2 });
    zoomBrowser.cdp.on("Network.requestWillBeSent", ({ request }) => {
      if (!request?.url || request.url.startsWith("data:") || request.url.startsWith("blob:")) return;
      if (!request.url.startsWith(origin)) externalRequests.push(request.url);
    });
    const zoomed = [];
    try {
      for (const route of ["/", "/esplora/", "/metodo/", "/correzioni/", "/dati/", "/progetto/"]) {
        await navigate(zoomBrowser.cdp, `${origin}${route}`);
        const metrics = await zoomBrowser.cdp.evaluate(`({
          viewport: innerWidth,
          outerWidth,
          devicePixelRatio,
          visualScale: visualViewport.scale,
          scrollWidth: document.documentElement.scrollWidth,
          headings: document.querySelectorAll('main h1').length
        })`);
        assert.equal(metrics.outerWidth, 1280, `${route}: unexpected physical browser width at 200% zoom`);
        assert.equal(metrics.viewport, 640, `${route}: browser zoom did not halve CSS viewport`);
        assert.equal(metrics.devicePixelRatio, 2, `${route}: browser zoom did not double devicePixelRatio`);
        assert.equal(metrics.visualScale, 1, `${route}: browser zoom was replaced by pinch scaling`);
        assert(metrics.scrollWidth <= metrics.viewport + 1, `${route}: overflow at real 200% browser zoom`);
        assert.equal(metrics.headings, 1, `${route}: primary heading missing at 200% zoom`);
        await dp422Screenshot(zoomBrowser.cdp, `launch-${route === "/" ? "home" : route.split("/")[1]}`, "zoom200");
        zoomed.push(route);
      }
    } finally {
      await zoomBrowser.close();
    }
    assert.deepEqual(externalRequests, [], "empty public launch requested an external provider");
    console.log(JSON.stringify({ status: "PASS", state: "empty-public-projection", pages: checked.length, actual_zoom_200_pages: zoomed.length, keyboard_navigation: "PASS", grayscale: "CHECKED", reduced_motion: "PASS", screenshots, external_requests: externalRequests.length }, null, 2));
    return;
  }
  await navigate(cdp, `${origin}/esplora/`);
  await waitFor(cdp, "document.querySelector('.results-count')?.textContent?.includes('risultat')", "Explore did not hydrate");
  const correctionHistoryHref = await cdp.evaluate("document.querySelector('.claim-row-meta a')?.getAttribute('href') ?? ''");
  if (correctedRecords.length > 0) {
    assert.match(correctionHistoryHref, /^\/dichiarazioni\/[^#]+\/#storia$/, "Explore correction indicator must link to version history");
  } else {
    assert.equal(correctionHistoryHref, "", "empty approved snapshot rendered a correction-history result link");
  }

  const ax = (await cdp.send("Accessibility.getFullAXTree")).nodes;
  assert(ax.some((node) => ["searchbox", "textbox"].includes(axValue(node, "role")) && axValue(node, "name") === "Cerca nel record pubblico"), "search control missing from accessibility tree");
  assert(ax.some((node) => axValue(node, "role") === "radiogroup" && axValue(node, "name") === "Tipo di record"), "record-type radiogroup missing from accessibility tree");
  assert(ax.some((node) => axValue(node, "role") === "button" && axValue(node, "name").startsWith("Filtri")), "filter button missing from accessibility tree");

  const allRecords = searchIndex.records.length;
  assert.equal(await cdp.evaluate("document.querySelectorAll('.explore-row').length"), allRecords,
    "default Explore list differs from the approved search index");
  assert.equal(await cdp.evaluate("document.querySelector('.results-count[aria-live=polite]')?.textContent.trim()"),
    `${allRecords} risultati`, "initial announced result count does not match the visible list");
  const assertRadioAx = async (name, checked) => {
    const nodes = (await cdp.send("Accessibility.getFullAXTree")).nodes;
    const radio = nodes.find((node) => axValue(node, "role") === "radio" && axValue(node, "name") === name);
    assert(radio, `${name}: selected state absent from accessibility tree`);
    const checkedValue = radio.properties?.find((property) => property.name === "checked")?.value?.value;
    assert.equal(String(checkedValue), String(checked), `${name}: assistive-tech checked state differs from DOM selection`);
  };
  await assertRadioAx("Tutto", "true");

  await cdp.evaluate("document.querySelector('input[type=radio][value=ALL]').focus()");
  await key(cdp, "ArrowRight", { code: "ArrowRight", keyCode: 39 });
  await waitFor(cdp, "document.querySelector('input[type=radio][value=finding]').checked", "arrow-key radio transition failed");
  assert.equal(await cdp.evaluate("document.activeElement?.value"), "finding", "selected radio did not retain keyboard focus");
  assert.match(await cdp.evaluate("location.search"), /tipo=finding/, "keyboard filter transition did not serialize URL state");
  const findingCount = searchIndex.records.filter((record) => record.kind === "finding").length;
  await waitFor(cdp, `document.querySelector('.results-count')?.textContent?.includes('${findingCount} risultat')`, "filtered finding count not updated for screen readers");
  assert.equal(await cdp.evaluate("document.querySelectorAll('.explore-row').length"), findingCount,
    "filtered findings did not match visible result list");
  await assertRadioAx("Dichiarazioni", "true");
  await assertRadioAx("Tutto", "false");

  await key(cdp, "ArrowRight", { code: "ArrowRight", keyCode: 39 });
  await waitFor(cdp, "document.querySelector('input[type=radio][value=person]').checked", "keyboard next-kind transition failed");
  const personCount = searchIndex.records.filter((record) => record.kind === "person").length;
  assert.equal(await cdp.evaluate("document.querySelectorAll('.explore-row').length"), personCount,
    "People radio filter does not match approved public Person records");
  assert.equal(await cdp.evaluate("document.querySelector('.results-count[aria-live=polite]')?.textContent.trim()"),
    `${personCount} ${personCount === 1 ? "risultato" : "risultati"}`,
    "filtered Person result count not announced semantically");
  assert.match(await cdp.evaluate("location.search"), /tipo=person/, "Person filter did not serialize shareable URL");
  await assertRadioAx("Persone", "true");
  const personLinks = await cdp.evaluate("[...document.querySelectorAll('.explore-row .claim-row-claim')].map(link => link.getAttribute('href'))");
  assert(personLinks.every((route) => route.startsWith("/persone/") && routes.includes(route)),
    "Person results link outside built canonical destinations");

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

  const personRoute = routes.find((route) => route.startsWith("/persone/"));
  const topicRoute = routes.find((route) => route.startsWith("/temi/"));
  let personShot = null;
  let topicShot = null;
  if (personRoute) {
    await navigate(cdp, `${origin}${personRoute}`);
    personShot = await screenshot(cdp, "person-desktop");
  }
  if (topicRoute) {
    await navigate(cdp, `${origin}${topicRoute}`);
    topicShot = await screenshot(cdp, "topic-desktop");
  }

  // DP-422.8: exercise every canonical v4 page family in one real Chrome
  // session, both desktop and phone. A fixture route is not runtime approval;
  // the matrix is reported explicitly and missing families are never forged.
  const dp422Families = new Map([
    ["home", "/"], ["explore", "/esplora/"],
    ["statement", scanRoutes.find((route) => route.startsWith("/dichiarazioni/"))],
    ["person", scanRoutes.find((route) => route.startsWith("/persone/"))],
    ["topic", scanRoutes.find((route) => route.startsWith("/temi/"))],
    ["content", scanRoutes.find((route) => route.startsWith("/contenuti/"))],
    ["trace", scanRoutes.find((route) => route.startsWith("/tracce/"))],
    ["method", "/metodo/"], ["utility", "/correzioni/"],
  ]);
  const dp422Matrix = [];
  for (const [variant, width, height, mobile] of [
    ["desktop", 1440, 900, false],
    ["phone", 375, 812, true],
  ]) {
    await cdp.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
    for (const [family, route] of dp422Families) {
      if (!route) continue;
      await navigate(cdp, `${origin}${route}`);
      if (family === "explore") await waitFor(cdp, "Boolean(document.querySelector('.results-count'))", "Explore hydration missing in v4 QA");
      const state = await cdp.evaluate(`(() => ({
        viewport: innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        h1: [...document.querySelectorAll('h1')].map(node => node.textContent.trim()),
        main: Boolean(document.querySelector('main')),
        horizontalScroll: document.documentElement.scrollWidth > innerWidth + 1,
      }))()`);
      assert.equal(state.viewport, width, `${family} ${variant}: wrong CSS viewport ${JSON.stringify(state)}`);
      assert(!state.horizontalScroll, `${family} ${variant}: horizontal page overflow ${JSON.stringify(state)}`);
      assert.equal(state.h1.length, 1, `${family} ${variant}: must have exactly one primary heading`);
      assert(state.h1[0].length > 0 && state.main, `${family} ${variant}: primary heading or main missing`);
      if (family === "home" || family === "method" || family === "utility") {
        const geometry = await cdp.evaluate(`(() => {
          const box = (selector) => {
            const element = document.querySelector(selector);
            if (!element) return null;
            const rect = element.getBoundingClientRect();
            return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
          };
          return {
            intro: box('${family === "home" ? ".hero-copy-v4" : ".dp-utility-document__header"}'),
            partner: box('${family === "home" ? ".hero-search-v4" : ".dp-utility-document__rail"}'),
            body: box('${family === "home" ? ".home-recent" : ".dp-utility-document__body"}'),
          };
        })()`);
        assert(geometry.intro && geometry.partner && geometry.body, `${family} ${variant}: split template element missing`);
        if (variant === "desktop") {
          assert(geometry.partner.left >= geometry.intro.right - 1, `${family}: primary search/context rail must occupy right desktop column: ${JSON.stringify(geometry)}`);
          assert(geometry.partner.top < geometry.intro.bottom, `${family}: right column must be alongside introduction, not stacked below: ${JSON.stringify(geometry)}`);
        } else {
          assert(geometry.partner.top >= geometry.intro.bottom - 1, `${family}: phone reading order must put context after introduction: ${JSON.stringify(geometry)}`);
          assert(geometry.body.top >= geometry.partner.bottom - 1, `${family}: phone context must not appear below document/results: ${JSON.stringify(geometry)}`);
        }
      }
      const shot = await dp422Screenshot(cdp, family, variant);
      dp422Matrix.push({ family, route, variant, viewport: width, screenshot: shot });
    }
  }
  await cdp.send("Emulation.setDeviceMetricsOverride", { width: 320, height: 720, deviceScaleFactor: 1, mobile: true });
  for (const [family, route] of dp422Families) {
    if (!route || !["home", "method", "utility"].includes(family)) continue;
    await navigate(cdp, `${origin}${route}`);
    const bounds = await cdp.evaluate("({ viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth })");
    assert.equal(bounds.viewport, 320, `${family}: 320px phone width not observed`);
    assert(bounds.scrollWidth <= bounds.viewport + 1, `${family}: 320px phone horizontal overflow ${JSON.stringify(bounds)}`);
  }
  if (dp422Families.has("person") && personRoute) {
    await navigate(cdp, `${origin}${personRoute}`);
    await cdp.send("Emulation.setEmulatedVisionDeficiency", { type: "achromatopsia" });
    await dp422Screenshot(cdp, "person", "phone-grayscale");
    await cdp.send("Emulation.setEmulatedVisionDeficiency", { type: "none" });
    const mobilePersonAx = (await cdp.send("Accessibility.getFullAXTree")).nodes;
    const personHeading = await cdp.evaluate("document.querySelector('h1')?.textContent.trim()");
    assert(mobilePersonAx.some((node) => axValue(node, "role") === "heading" && axValue(node, "name") === personHeading), "Person primary heading absent from mobile AX tree");
    const filterButton = await cdp.evaluate("document.querySelector('[data-record-filter-toggle]')?.getBoundingClientRect().toJSON() ?? null");
    assert(filterButton && filterButton.height >= 44, `Person phone filter tap target too small: ${JSON.stringify(filterButton)}`);
    await cdp.evaluate("document.querySelector('[data-record-filter-toggle]').focus()");
    await key(cdp, "Enter", { code: "Enter", keyCode: 13, text: "\r" });
    assert.equal(await cdp.evaluate("document.querySelector('[data-record-filter-toggle]').getAttribute('aria-expanded')"), "true", "Person filters did not open from keyboard");
    await cdp.evaluate("document.querySelector('[data-record-filter-close]').click()");
    assert.equal(await cdp.evaluate("document.activeElement?.hasAttribute('data-record-filter-toggle')"), true, "Person filter close failed to restore keyboard focus");
  }
  await cdp.send("Emulation.clearDeviceMetricsOverride");

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
    for (const [family, route] of dp422Families) {
      if (!route) continue;
      await navigate(zoomBrowser.cdp, `${origin}${route}`);
      const width = await zoomBrowser.cdp.evaluate("({ viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth })");
      assert.equal(width.viewport, 640, `${family}: browser must stay at exact 200% zoom`);
      assert(width.scrollWidth <= width.viewport + 1, `${family}: horizontal overflow at exact 200% zoom: ${JSON.stringify(width)}`);
      await dp422Screenshot(zoomBrowser.cdp, family, "zoom200");
    }
  } finally {
    await zoomBrowser.close();
  }

  assert.deepEqual(externalRequests, [], `browser made external/provider requests: ${externalRequests.join(", ")}`);
  console.log(JSON.stringify({
    status: "PASS",
    search_records: searchIndex.records.length,
    routes_scanned: scanRoutes.length,
    external_requests: externalRequests.length,
    reduced_motion: motion,
    reflow_200_equivalent: reflow,
    browser_zoom_200_exact: zoom200,
    phone,
    dp422_visual_matrix: dp422Matrix,
    screenshots: { mobileShot, personShot, topicShot },
  }, null, 2));
} finally {
  await browser.close();
  // A renderer may outlive Chrome's DevTools browser target briefly; its
  // keep-alive connection must not leave the test server hanging in CI.
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
}
}

await runBrowserChecks();
