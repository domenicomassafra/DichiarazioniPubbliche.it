// Isolated legacy React-component browser test; NOT a public route acceptance.
// Run: node prototypes/v4-implementation/dp407/test-content-audit-keyboard-wave11.mjs
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { createServer } from "node:http";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const requireWeb = createRequire(path.join(root, "web/package.json"));
const { build } = requireWeb("esbuild");
const result = await build({
  stdin: {
    contents: `import React from "react";
import { createRoot } from "react-dom/client";
import ContentAuditClient from "./components/ContentAuditClient";
import { demoContentAudit } from "./data/content-audit";
createRoot(document.getElementById("app")).render(<ContentAuditClient audit={demoContentAudit} />);`,
    loader: "tsx", resolveDir: path.join(root, "web/src"),
  },
  bundle: true, format: "iife", platform: "browser", write: false, logLevel: "silent",
});
const bundle = result.outputFiles[0].text;
const requests = [];
const server = createServer((req, res) => {
  requests.push(req.url);
  if (req.url?.startsWith("/bundle.js")) {
    res.writeHead(200, { "Content-Type": "text/javascript" }).end(bundle);
  } else {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" })
      .end('<!doctype html><html lang="it"><head><title>Legacy Content test</title></head><body><main id="app"></main><script src="/bundle.js"></script></body></html>');
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const profile = await mkdtemp(path.join(tmpdir(), "dp407-wave11-"));
const chrome = process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const child = spawn(chrome, ["--headless=new", "--disable-gpu", "--no-first-run",
  "--no-default-browser-check", "--disable-background-networking", "--remote-debugging-port=0",
  `--user-data-dir=${profile}`, `${origin}/?momento=moment-2&keep=safe#content`],
  { stdio: "ignore" });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let ws;
try {
  const portFile = path.join(profile, "DevToolsActivePort");
  let port;
  for (let i = 0; i < 200; i += 1) {
    if (child.exitCode !== null) throw new Error(`Chrome exited: ${child.exitCode}`);
    try { port = (await readFile(portFile, "utf8")).trim().split("\n")[0]; break; }
    catch { await sleep(50); }
  }
  assert(port, "Chrome debugging port not ready");
  let target;
  for (let i = 0; i < 200; i += 1) {
    try {
      const pages = await fetch(`http://127.0.0.1:${port}/json/list`).then((r) => r.json());
      target = pages.find((p) => p.type === "page" && p.url.startsWith(origin));
      if (target?.webSocketDebuggerUrl) break;
    } catch { /* debugging service not ready yet */ }
    await sleep(50);
  }
  assert(target?.webSocketDebuggerUrl, "Chrome page unavailable");
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
  let lastId = 0;
  const pending = new Map();
  ws.addEventListener("message", ({ data }) => {
    const event = JSON.parse(data);
    if (!event.id) return;
    const job = pending.get(event.id);
    if (!job) return;
    pending.delete(event.id);
    if (event.error) job.reject(new Error(event.error.message));
    else job.resolve(event.result);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++lastId;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const evalJs = async (expression) => {
    const reply = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.text);
    return reply.result.value;
  };
  const wait = async (expression) => {
    for (let i = 0; i < 100; i += 1) {
      if (await evalJs(expression)) return;
      await sleep(50);
    }
    throw new Error(`DOM never reached expected condition: ${expression}`);
  };
  await send("Runtime.enable");
  await wait("document.querySelectorAll('.tape-mark').length === 5");
  // Loading a shareable URL must show that same public-demo moment in both
  // controls and detail. No transcript/body/private data is requested.
  assert.equal(await evalJs("document.querySelector('.tape-mark[aria-pressed=true]')?.textContent.trim()"), "08:46");
  assert.equal(await evalJs("document.querySelector('.audit-detail h2')?.textContent"),
    "Il programma di borse di studio ha raggiunto tutti i posti previsti.");

  // Focus a native button and activate it with a real Chromium Space key.
  await send("Page.bringToFront");
  await evalJs("document.querySelectorAll('.tape-mark')[2].focus()");
  assert.equal(await evalJs("document.activeElement === document.querySelectorAll('.tape-mark')[2]"), true);
  for (const type of ["keyDown", "keyUp"]) {
    await send("Input.dispatchKeyEvent", { type, key: " ", code: "Space", windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 49, text: " " });
  }
  await wait("document.querySelectorAll('.tape-mark')[2].getAttribute('aria-pressed') === 'true'");
  assert.equal(await evalJs("new URL(location.href).searchParams.get('momento')"), "moment-3");
  assert.equal(await evalJs("new URL(location.href).searchParams.get('keep')"), "safe");
  assert.equal(await evalJs("location.hash"), "#content");
  assert.equal(await evalJs("document.activeElement === document.querySelectorAll('.tape-mark')[2]"), true);
  assert.equal(await evalJs("document.querySelector('.audit-detail h2')?.textContent"),
    "La rete locale copre già quasi tutto il fabbisogno energetico.");
  // Browser favicon lookups are harmless local requests, not provider traffic.
  assert.deepEqual(requests.filter((uri) => uri !== "/favicon.ico").sort(),
    ["/?momento=moment-2&keep=safe", "/bundle.js"].sort());
  console.log("PASS real Chromium DOM: deep link + Space selection + URL + focus + detail; local fixture/assets only");
} finally {
  try { ws?.close(); } catch { /* already closed */ }
  child.kill("SIGTERM");
  await Promise.race([new Promise((resolve) => child.once("exit", resolve)), sleep(1600)]);
  if (child.exitCode === null) child.kill("SIGKILL");
  server.close();
  await rm(profile, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
}
