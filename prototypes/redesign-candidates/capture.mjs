#!/usr/bin/env node
/**
 * DP-441: render the existing offline comparison with the Studio's dedicated
 * automation-browser-visible Chrome (CDP 17630); never inspect other tabs.
 * No external assets, source capture, live data or private profile access.
 */
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const output = join(root, 'screenshots');
const base = 'http://127.0.0.1:17630';
const views = ['home', 'explore', 'statement', 'intersection', 'source', 'trace'];
const sizes = [{ width: 1440, height: 900 }, { width: 390, height: 844 }, { width: 320, height: 700 }, { width: 195, height: 422 }]; // CSS reflow equivalent of a 390px viewport at 200% zoom
const variants = ['atlante', 'biblioteca'];
const evidence = {
  observed_at: new Date().toISOString(),
  browser: 'automation-browser-visible (Mac Studio, existing CDP 17630, own tab only)',
  projection: 'OFFLINE FIXTURE ONLY; public-v2 DRAFT, zero approved dossiers on readback',
  fixture: 'build.py SAMPLE, deliberately invented; no third-party assets',
  source_sha256: Object.fromEntries(variants.map(v => [v, createHash('sha256').update(readFileSync(join(root, v + '.html'))).digest('hex')])),
  observations: []
};
const screenshots = new Set([
  'home-1440', 'home-390', 'explore-320', 'statement-1440',
  'statement-390', 'intersection-390', 'source-390', 'trace-390'
]);
mkdirSync(output, { recursive: true });
let target;
let ws;
let commandId = 0;
const pending = new Map();
function send(method, params = {}) {
  return new Promise((accept, reject) => {
    const id = ++commandId;
    const timeout = setTimeout(() => {
      pending.delete(id);
      reject(new Error('CDP timeout: ' + method));
    }, 12000);
    pending.set(id, { accept, reject, timeout });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(fn) {
  const response = await send('Runtime.evaluate', {
    expression: '(' + fn.toString() + ')()',
    returnByValue: true,
    awaitPromise: true
  });
  if (response.exceptionDetails) {
    throw new Error(JSON.stringify(response.exceptionDetails).slice(0, 500));
  }
  return response.result.value;
}
async function loaded(expected) {
  for (let i = 0; i < 60; i++) {
    const state = await evaluate(function () {
      return { href: location.href, ready: document.readyState, panel: !!document.querySelector('[data-panel]:not([hidden])') };
    });
    if (state.href === expected && state.ready === 'complete' && state.panel) return;
    await new Promise(ok => setTimeout(ok, 50));
  }
  throw new Error('Page did not finish rendering: ' + expected);
}
function pageMetrics() {
  const panel = document.querySelector('[data-panel]:not([hidden])');
  const banner = document.querySelector('.flag');
  const links = [...panel.querySelectorAll('a[href]')];
  return {
    view: panel.id,
    h1: panel.querySelector('h1')?.textContent?.trim(),
    banner: banner?.textContent?.trim(),
    css_viewport: window.innerWidth,
    document_width: document.documentElement.scrollWidth,
    horizontal_overflow: document.documentElement.scrollWidth > window.innerWidth,
    original_quote: panel.querySelector('blockquote')?.textContent?.trim() ?? null,
    heading_in_first_viewport: panel.querySelector('h1')?.getBoundingClientRect().top < window.innerHeight,
    link_targets: links.map(a => a.getAttribute('href')),
    empty_state: panel.id === 'home' || panel.id === 'explore'
      ? /vuot|nessuna dichiarazione|nessuna scheda/i.test(panel.textContent) : null,
    noindex: document.querySelector('meta[name=robots]')?.getAttribute('content')
  };
}
try {
  const version = await fetch(base + '/json/version').then(r => r.json());
  evidence.chrome_version = version.Browser;
  const created = await fetch(base + '/json/new?about:blank', { method: 'PUT' });
  if (!created.ok) throw new Error('Cannot open dedicated automation tab: ' + created.status);
  target = await created.json();
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((ok, fail) => {
    ws.addEventListener('open', ok, { once: true });
    ws.addEventListener('error', fail, { once: true });
  });
  ws.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    const task = pending.get(message.id);
    if (!task) return;
    clearTimeout(task.timeout);
    pending.delete(message.id);
    message.error ? task.reject(new Error(JSON.stringify(message.error))) : task.accept(message.result);
  });
  await send('Page.enable');
  await send('Runtime.enable');
  for (const variant of variants) {
    const page = pathToFileURL(resolve(root, variant + '.html')).href;
    for (const size of sizes) {
      await send('Emulation.setDeviceMetricsOverride', { width: size.width, height: size.height, deviceScaleFactor: 1, mobile: false });
      for (const view of views) {
        const href = page + '?view=' + view;
        await send('Page.navigate', { url: href });
        await loaded(href);
        const metrics = await evaluate(pageMetrics);
        const validTargets = metrics.link_targets.every(link => /^\?view=(home|explore|statement|intersection|source|trace)$/.test(link));
        const observation = {
          variant, view, viewport: size.width + 'x' + size.height,
          h1: metrics.h1, document_width: metrics.document_width,
          in_first_viewport: metrics.heading_in_first_viewport,
          demo_label: !!metrics.banner?.includes('NON PUBBLICABILE'),
          noindex: metrics.noindex === 'noindex,nofollow',
          empty_state: metrics.empty_state, local_links_valid: validTargets,
          original_quote: metrics.original_quote
        };
        if (metrics.view !== view || !metrics.h1 || !metrics.banner?.includes('NON PUBBLICABILE') ||
            metrics.noindex !== 'noindex,nofollow' || !validTargets || metrics.horizontal_overflow ||
            (size.width >= 320 && !metrics.heading_in_first_viewport) || metrics.empty_state === false) {
          throw new Error('Unexpected rendering: ' + JSON.stringify(observation));
        }
        if (view === 'statement' && metrics.original_quote !== 'Questo testo è un esempio inventato per valutare la leggibilità.') {
          throw new Error('Fixture mismatch: ' + variant);
        }
        if (screenshots.has(view + '-' + size.width)) {
          const filename = variant + '-' + view + '-' + size.width + '.png';
          const result = await send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false });
          writeFileSync(join(output, filename), Buffer.from(result.data, 'base64'));
          observation.screenshot = 'screenshots/' + filename;
          observation.screenshot_sha256 = createHash('sha256').update(readFileSync(join(output, filename))).digest('hex');
        }
        evidence.observations.push(observation);
        console.log(variant + ' ' + view + ' ' + size.width + ': ' + (observation.screenshot ?? 'metrics OK') + ', scrollWidth=' + metrics.document_width);
      }
    }
  }
  const comparable = evidence.observations.filter(x => x.view === 'statement' && x.viewport.startsWith('1440'));
  if (comparable.length !== 2 || comparable[0].original_quote !== comparable[1].original_quote) {
    throw new Error('Alternatives do not share a record');
  }
  writeFileSync(join(root, 'render-evidence.json'), JSON.stringify(evidence, null, 2) + '\n');
  console.log('PASS: ' + evidence.observations.length + ' browser renders; ' + evidence.observations.filter(x => x.screenshot).length + ' real PNG screenshots');
} finally {
  if (ws) ws.close();
  if (target) {
    const close = await fetch(base + '/json/close/' + target.id).catch(() => null);
    if (!close?.ok) console.error('Could not close the own automation tab: ' + target.id);
  }
}
