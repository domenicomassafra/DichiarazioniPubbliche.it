import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { gzipSync } from "node:zlib";
import { mkdtemp, readFile, readdir, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

const root = path.resolve("dist");
const chromeBin = process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const configuredOrigin = process.env.DP_PERF_ORIGIN?.trim() || null;
const lcpBudgetMs = 2000;
const clsBudget = 0.10;
const interactionBudgetMs = 200;
const jsBudgetBytes = 120 * 1024;

const mime = new Map([
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".woff2", "font/woff2"],
  [".svg", "image/svg+xml"],
]);

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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

async function representativeRoutes() {
  const built = new Set((await walk(root)).filter((file) => file.endsWith("index.html")).map(routeFor));
  const selected = ["/", "/esplora/", "/metodo/", "/correzioni/", "/dati/", "/progetto/"].filter((route) => built.has(route));
  for (const prefix of ["/dichiarazioni/", "/persone/", "/temi/", "/contenuti/", "/tracce/"]) {
    const candidate = [...built].sort().find((route) => route.startsWith(prefix));
    if (candidate) selected.push(candidate);
  }
  assert(selected.includes("/") && selected.includes("/esplora/") && selected.includes("/metodo/"), "performance build is missing required public routes");
  return selected;
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
      res.writeHead(200, {
        "content-type": mime.get(path.extname(resolved)) || "application/octet-stream",
        "cache-control": "no-store",
      });
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

async function launchChrome(origin) {
  const profile = await mkdtemp(path.join(tmpdir(), "dp-perf-chrome-"));
  const child = spawn(chromeBin, [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "--window-size=375,812",
    `${origin}/`,
  ], { stdio: ["ignore", "ignore", "pipe"] });
  const stderr = [];
  child.stderr?.on("data", (chunk) => stderr.push(String(chunk)));

  async function cleanup() {
    if (child.exitCode === null && !child.killed) child.kill("SIGTERM");
    for (let attempt = 0; attempt < 30 && child.exitCode === null; attempt += 1) await sleep(50);
    if (child.exitCode === null) {
      child.kill("SIGKILL");
      for (let attempt = 0; attempt < 20 && child.exitCode === null; attempt += 1) await sleep(50);
    }
    let cleanupError;
    for (let attempt = 0; attempt < 20; attempt += 1) {
      try {
        await rm(profile, { recursive: true, force: true });
        cleanupError = undefined;
        break;
      } catch (error) {
        cleanupError = error;
        if (!["ENOTEMPTY", "EBUSY", "EPERM"].includes(error?.code)) throw error;
        await sleep(50);
      }
    }
    if (cleanupError) throw cleanupError;
  }

  try {
    const activePort = path.join(profile, "DevToolsActivePort");
    for (let attempt = 0; attempt < 300 && !(await exists(activePort)); attempt += 1) {
      if (child.exitCode !== null) throw new Error(`Chrome exited before DevTools was ready (exit ${child.exitCode})`);
      await sleep(50);
    }
    assert(await exists(activePort), "Chrome did not expose DevToolsActivePort within 15 seconds");
    const [port] = (await readFile(activePort, "utf8")).trim().split("\n");
    let target;
    for (let attempt = 0; attempt < 200; attempt += 1) {
      const targets = await fetch(`http://127.0.0.1:${port}/json/list`).then((response) => response.json()).catch(() => []);
      target = targets.find((item) => item.type === "page" && item.url.startsWith(origin)) ?? targets.find((item) => item.type === "page");
      if (target?.webSocketDebuggerUrl) break;
      await sleep(50);
    }
    assert(target?.webSocketDebuggerUrl, "Chrome page target unavailable within 10 seconds");
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.addEventListener("open", resolve, { once: true });
      ws.addEventListener("error", reject, { once: true });
    });
    const cdp = new Cdp(ws);
    await Promise.all([
      cdp.send("Page.enable"),
      cdp.send("Runtime.enable"),
      cdp.send("Network.enable"),
      cdp.send("Performance.enable"),
    ]);
    return {
      cdp,
      async close() {
        try { await cdp.send("Browser.close"); } catch {}
        await cleanup();
      },
    };
  } catch (error) {
    await cleanup();
    throw new Error(`${error.message}\n${stderr.join("").slice(-4000)}`, { cause: error });
  }
}

async function waitFor(cdp, expression, message, timeoutMs = 8000) {
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

const localHost = configuredOrigin ? null : await startStaticServer();
const origin = configuredOrigin ? new URL(configuredOrigin).origin : localHost.origin;
const routes = await representativeRoutes();
const browser = await launchChrome(origin);
const externalRequests = [];
const requestedJs = new Set();

browser.cdp.on("Network.requestWillBeSent", ({ request }) => {
  const url = request?.url || "";
  if (!url || url.startsWith("data:") || url.startsWith("blob:")) return;
  if (!url.startsWith(origin)) externalRequests.push(url);
  if (url.startsWith(origin) && new URL(url).pathname.endsWith(".js")) requestedJs.add(new URL(url).pathname);
});

try {
  const { cdp } = browser;
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 375,
    height: 812,
    deviceScaleFactor: 2,
    mobile: true,
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
    source: `
      (() => {
        window.__dpPerf = { lcp: 0, cls: 0 };
        try {
          new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) window.__dpPerf.lcp = Math.max(window.__dpPerf.lcp, entry.startTime || 0);
          }).observe({ type: 'largest-contentful-paint', buffered: true });
        } catch {}
        try {
          new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) if (!entry.hadRecentInput) window.__dpPerf.cls += entry.value || 0;
          }).observe({ type: 'layout-shift', buffered: true });
        } catch {}
      })();
    `,
  });

  const results = [];
  for (const route of routes) {
    requestedJs.clear();
    await cdp.send("Network.clearBrowserCache");
    const preflight = await fetch(`${origin}${route}`, { redirect: "manual" });
    assert(preflight.ok, `${route}: representative performance route returned HTTP ${preflight.status}`);
    await navigate(cdp, `${origin}${route}`);
    if (route === "/esplora/") {
      await waitFor(cdp, "document.querySelector('.results-count')?.textContent?.includes('risultat')", "Explore did not hydrate in performance run");
    }
    await sleep(350);
    const paint = await cdp.evaluate(`({
      lcp: window.__dpPerf?.lcp ?? 0,
      cls: window.__dpPerf?.cls ?? 0,
      readyState: document.readyState,
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      autoplayMediaCount: document.querySelectorAll('video[autoplay],audio[autoplay]').length,
      mediaOverflowCount: [...document.querySelectorAll('img,video,audio,iframe')].filter((node) => {
        const rect = node.getBoundingClientRect();
        return rect.width > window.innerWidth + 1 || rect.right > window.innerWidth + 1;
      }).length
    })`);
    assert(paint.lcp > 0, `${route}: LCP was not observed`);
    assert(paint.lcp <= lcpBudgetMs, `${route}: LCP ${paint.lcp.toFixed(1)}ms exceeds ${lcpBudgetMs}ms`);
    assert(paint.cls <= clsBudget, `${route}: CLS ${paint.cls} exceeds ${clsBudget}`);
    assert(!paint.horizontalOverflow, `${route}: horizontal layout overflow under representative mobile profile`);
    assert.equal(paint.autoplayMediaCount, 0, `${route}: autoplay media is present on a public route`);
    assert.equal(paint.mediaOverflowCount, 0, `${route}: media overflows representative mobile viewport`);

    let interactionProxyMs = null;
    if (route === "/esplora/") {
      interactionProxyMs = await cdp.evaluate(`(async () => {
        const button = document.querySelector('.filter-button');
        if (!button) return null;
        const started = performance.now();
        button.click();
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        return performance.now() - started;
      })()`);
      assert(interactionProxyMs !== null, "Explore interaction proxy control missing");
      assert(interactionProxyMs <= interactionBudgetMs, `Explore interaction proxy ${interactionProxyMs.toFixed(1)}ms exceeds ${interactionBudgetMs}ms`);
    }

    let jsGzipBytes = 0;
    for (const pathname of requestedJs) {
      let body;
      if (configuredOrigin) {
        const response = await fetch(`${origin}${pathname}`);
        assert(response.ok, `${route}: live JS asset failed ${response.status}: ${pathname}`);
        body = Buffer.from(await response.arrayBuffer());
      } else {
        const asset = path.resolve(root, `.${pathname}`);
        assert(asset.startsWith(root + path.sep), `${route}: JS asset escaped dist root: ${pathname}`);
        body = await readFile(asset);
      }
      jsGzipBytes += gzipSync(body, { mtime: 0 }).byteLength;
    }
    assert(jsGzipBytes <= jsBudgetBytes, `${route}: initial JS ${jsGzipBytes} bytes gzip exceeds ${jsBudgetBytes}`);

    results.push({
      route,
      lcp_ms: Number(paint.lcp.toFixed(1)),
      cls: Number(paint.cls.toFixed(4)),
      interaction_proxy_ms: interactionProxyMs === null ? null : Number(interactionProxyMs.toFixed(1)),
      initial_js_gzip_bytes: jsGzipBytes,
      js_requests: requestedJs.size,
      horizontal_overflow: paint.horizontalOverflow,
      autoplay_media_count: paint.autoplayMediaCount,
      media_overflow_count: paint.mediaOverflowCount,
    });
  }

  assert.deepEqual(externalRequests, [], `performance browser made external/provider requests: ${externalRequests.join(", ")}`);
  console.log(JSON.stringify({
    status: "PASS",
    profile: {
      viewport_css_px: "375x812",
      device_scale_factor: 2,
      cpu_throttle_rate: 4,
      cache: "disabled + cleared before each navigation",
      transport: configuredOrigin
        ? `existing static host ${origin}; no synthetic network throttle`
        : "loopback static server; no synthetic network throttle",
      interaction_metric: "two-animation-frame main-thread interaction proxy; not field INP",
    },
    budgets: {
      lcp_ms: lcpBudgetMs,
      cls: clsBudget,
      interaction_proxy_ms: interactionBudgetMs,
      initial_js_gzip_bytes: jsBudgetBytes,
    },
    external_requests: externalRequests.length,
    routes: results,
  }, null, 2));
} finally {
  await browser.close();
  if (localHost) await new Promise((resolve) => localHost.server.close(resolve));
}
