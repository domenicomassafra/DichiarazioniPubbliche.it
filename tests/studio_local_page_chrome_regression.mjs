// Real Chromium keyboard + DOM proof for the nonce-bound private Studio page.
// Usage: PYTHONPATH=poc python3 -c 'from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page; print(render_studio_login_page("a"*32).decode())' | node tests/studio_local_page_chrome_regression.mjs
// The server and token are disposable local fixtures. No PostgreSQL/provider/public requests.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

let page = '';
for await (const chunk of process.stdin) page += chunk;
assert.match(page, /<script nonce="[0-9a-f]{32}">/, 'expected rendered private HTML');
const requests = [];
const safeRow = {
  id: 'passage:keyboard', kind: 'PASSAGE',
  content_id: 'content:keyboard', passage_id: 'passage:keyboard', source_id: 'source:keyboard',
};
const server = createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(page);
    return;
  }
  if (req.method === 'POST' && req.url === '/v1/corpus/search') {
    let body = '';
    for await (const part of req) body += part;
    const payload = JSON.parse(body);
    requests.push({ payload, authorization: req.headers.authorization });
    const data = {
      contract_version: 'studio-operator-search-v1',
      private_only: true, publication_authority: false,
      query_sha256: 'b'.repeat(64), result_count: 1,
      results: [safeRow],
    };
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify({ contract_version: 'studio-local-readonly-api-v1', data }));
    return;
  }
  if (req.method === 'POST' && req.url === '/v1/collections/member') {
    let body = '';
    for await (const part of req) body += part;
    const payload = JSON.parse(body);
    requests.push({ payload, authorization: req.headers.authorization, path: req.url });
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify({ contract_version: 'studio-local-readonly-api-v1', data: {
      collection_id: payload.collection_id, content_id: payload.content_id,
      source_id: 'source:keyboard', source_exists: true, private_only: true,
      publication_authority: false, private_marker: 'SHOULD_NOT_APPEAR', claims: [],
    }}));
    return;
  }
  if (req.method === 'POST' && [
      '/v1/collections/captures', '/v1/capture/passages',
      '/v1/collections/passage-candidates',
    ].includes(req.url)) {
    let body = '';
    for await (const part of req) body += part;
    const payload = JSON.parse(body);
    requests.push({ payload, authorization: req.headers.authorization, path: req.url });
    const common = {private_only: true, publication_authority: false, rights_clearance: false};
    const data = req.url === '/v1/collections/captures' ? {
      ...common, capture_authorized: false,
      contract_version: 'studio-collection-captures-v1',
      collection_id: 'research:garlasco', content_id: 'content:keyboard',
      source_id: 'source:keyboard', source_exists: true,
      collection_state: 'PAUSED', rights_status: 'UNKNOWN', processing_status: 'REVIEW_REQUIRED',
      captures: [{id: 'capture:keyboard', content_sha256: 'a'.repeat(64),
                  observed_at: '2026-10-08T09:00:00Z',
                  status: 'CAPTURED', archive_status: 'NOT_REQUESTED'}],
      has_more: false, next_after_id: null,
    } : req.url === '/v1/capture/passages' ? {
      ...common, selectors: [{id: 'passage:keyboard', selector_type: 'TEXT_POSITION'}],
    } : {
      ...common, review_authority: false,
      contract_version: 'studio-passage-candidates-v1',
      collection_id: 'research:garlasco', content_id: 'content:keyboard',
      passage_id: 'passage:keyboard', source_id: 'source:keyboard',
      rights_status: 'UNKNOWN', selector_type: 'TEXT_POSITION',
      candidates: [{statement_candidate_id: 'statement:keyboard', status: 'HELD',
                    claim_candidates: [{id: 'claimcandidate:keyboard', status: 'CANDIDATE',
                                        promoted_claim_id: null}]}],
      has_more: false, next_after_id: null,
    };
    res.writeHead(200, {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'});
    res.end(JSON.stringify({contract_version: 'studio-local-readonly-api-v1', data}));
    return;
  }
  res.writeHead(404).end();
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = 'http://127.0.0.1:' + server.address().port;
const profile = await mkdtemp(path.join(tmpdir(), 'dp415-studio-chrome-'));
const chrome = process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const child = spawn(chrome, [
  '--headless=new', '--disable-gpu', '--no-first-run',
  '--no-default-browser-check', '--disable-background-networking',
  '--remote-debugging-port=0', '--user-data-dir=' + profile, origin + '/',
], { stdio: 'ignore' });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let ws;
try {
  let port;
  for (let i = 0; i < 140; i += 1) {
    if (child.exitCode !== null) throw new Error('Chromium terminated prematurely');
    try {
      port = (await readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0];
      break;
    } catch { await sleep(75); }
  }
  assert(port, 'Chrome DevTools port unavailable');
  let target;
  for (let i = 0; i < 140; i += 1) {
    try {
      const pages = await fetch('http://127.0.0.1:' + port + '/json/list').then(r => r.json());
      target = pages.find(item => item.type === 'page' && item.url.startsWith(origin));
      if (target?.webSocketDebuggerUrl) break;
    } catch {}
    await sleep(75);
  }
  assert(target?.webSocketDebuggerUrl, 'Chrome test page unavailable');
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });
  let seq = 0;
  const pending = new Map();
  ws.addEventListener('message', ({ data }) => {
    const event = JSON.parse(data);
    if (!event.id) return;
    const record = pending.get(event.id);
    if (!record) return;
    pending.delete(event.id);
    if (event.error) record.reject(new Error(event.error.message));
    else record.resolve(event.result);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async expression => {
    const reply = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.text);
    return reply.result.value;
  };
  const wait = async expression => {
    for (let i = 0; i < 100; i += 1) {
      if (await evaluate(expression)) return;
      await sleep(50);
    }
    throw new Error('Chrome DOM condition never became true: ' + expression
      + ' routes=' + requests.map(row => row.path || '/v1/corpus/search').join(',')
      + ' captureRequest=' + JSON.stringify(requests.at(-1)?.payload)
      + ' collectionStatus=' + await evaluate('document.getElementById("collection-capture-summary").textContent')
      + ' receipt=' + await evaluate('document.getElementById("results").textContent'));
  };
  const space = async () => {
    for (const type of ['rawKeyDown', 'char', 'keyUp']) {
      await send('Input.dispatchKeyEvent', {
        type, key: ' ', code: 'Space', windowsVirtualKeyCode: 32,
        nativeVirtualKeyCode: 49, ...(type === 'char' ? { text: ' ' } : {}),
      });
    }
  };
  await send('Runtime.enable');
  await wait(`document.querySelector('form[data-endpoint="/v1/corpus/search"]') !== null`);
  await evaluate(`document.getElementById('token').value = '${'a'.repeat(64)}';
    const form = document.querySelector('form[data-endpoint="/v1/corpus/search"]');
    for (const [key, value] of Object.entries({
      query: 'fixture keyboard', kind: 'PASSAGE', collection_id: 'research:garlasco',
      source_id: 'source:keyboard', person_id: 'person:keyboard', topic_id: 'topic:keyboard',
      event_id: 'event:keyboard', from_date: '2026-01-01', to_date: '2026-10-01',
      status: 'APPROVED', claim_type: 'FACTUAL', check_worthy: 'false', limit: '5',
    })) form.elements.namedItem(key).value = value;
    form.requestSubmit();`);
  await wait('document.querySelectorAll("#corpus-links button").length === 1');
  assert.equal(requests.length, 1);
  assert.deepEqual(requests[0].payload, {
    query: 'fixture keyboard', kinds: ['PASSAGE'], collection_id: 'research:garlasco',
    source_id: 'source:keyboard', person_id: 'person:keyboard',
    topic_id: 'topic:keyboard', event_id: 'event:keyboard',
    from_at: '2026-01-01T00:00:00Z', to_at: '2026-10-01T23:59:59Z',
    status: 'APPROVED', claim_type: 'FACTUAL', check_worthy: false, limit: 5,
  });
  assert.equal(requests[0].authorization, 'Bearer ' + 'a'.repeat(64));
  await send('Page.bringToFront');
  await evaluate('document.querySelector("#corpus-links button").focus()');
  await space();
  await wait('document.getElementById("corpus-inspector").hidden === false');
  assert.equal(await evaluate('document.activeElement.id'), 'corpus-inspector-title');
  assert.equal(await evaluate('document.getElementById("corpus-references").textContent.includes("source:keyboard")'), true);
  assert.equal(await evaluate('document.getElementById("corpus-source-jump").hidden'), false);
  await evaluate('document.getElementById("corpus-source-jump").click()');
  await wait('document.getElementById("corpus-jump-status").textContent.includes("Collegamento persistito verificato")');
  assert.equal(requests.length, 2);
  assert.deepEqual(requests[1].payload, {
    collection_id: 'research:garlasco', content_id: 'content:keyboard', limit: 1,
  });
  assert.equal(await evaluate('document.getElementById("corpus-jump-status").textContent.includes("SHOULD_NOT_APPEAR")'), false);
  await evaluate('document.getElementById("corpus-back").focus()');
  await space();
  await wait('document.getElementById("corpus-inspector").hidden === true');
  assert.equal(await evaluate('document.activeElement.textContent.includes("passage:keyboard")'), true);
  assert.equal(await evaluate(`document.querySelector('form[data-endpoint="/v1/corpus/search"]').elements.namedItem('query').value`), 'fixture keyboard');
  await evaluate(`document.querySelector('[data-panel="captures"]').click()`);
  assert.equal(await evaluate(`document.querySelector('form[data-endpoint="/v1/corpus/search"]').elements.namedItem('query').value`), '');
  assert.equal(await evaluate('document.querySelector("#corpus-links").children.length'), 0);
  assert.equal(await evaluate('document.querySelector("#corpus-references").children.length'), 0);
  assert.equal(await evaluate('document.getElementById("results").textContent.includes("source:keyboard")'), false);
  await evaluate(`(() => { document.querySelector('[data-panel="collections"]').click();
    const form = document.querySelector('form[data-endpoint="/v1/collections/member"]');
    form.elements.namedItem('collection_id').value = 'research:garlasco';
    form.elements.namedItem('content_id').value = 'content:keyboard';
    form.requestSubmit(); })()`);
  await wait('document.querySelectorAll("#collection-capture-links button").length === 1');
  assert.equal(requests.at(-1).path, '/v1/collections/captures', 'detail must auto-link persisted capture versions');
  assert.equal(requests.at(-1).payload.content_id, 'content:keyboard');
  assert.equal(await evaluate('document.getElementById("collection-capture-summary").textContent.includes("UNKNOWN")'), true);
  await evaluate('document.querySelector("#collection-capture-links button").click()');
  await wait('document.querySelectorAll("#capture-passage-links button").length === 1');
  assert.equal(requests.at(-1).path, '/v1/capture/passages');
  assert.equal(requests.at(-1).payload.capture_hash, 'a'.repeat(64));
  await evaluate('document.querySelector("#capture-passage-links button").focus()');
  await space();
  await wait('document.querySelectorAll("#passage-candidate-links button").length === 1');
  assert.equal(requests.at(-1).path, '/v1/collections/passage-candidates');
  assert.equal(requests.at(-1).payload.passage_id, 'passage:keyboard');
  assert.equal(await evaluate('document.getElementById("passage-candidate-links").textContent.includes("claimcandidate:keyboard")'), true);
  assert.equal(await evaluate('document.getElementById("passage-candidate-links").textContent.includes("SECRET")'), false);
  await evaluate('document.getElementById("clear").click()');
  assert.equal(await evaluate('document.querySelectorAll("#passage-candidate-links button").length'), 0,
               'disconnect must clear private candidate navigation');
  console.log('PASS real Chrome: DP416/419 collection -> source -> capture -> passage -> candidate/claim keyboard navigation + scrub');
} finally {
  try { ws?.close(); } catch {}
  child.kill('SIGTERM');
  await Promise.race([new Promise(resolve => child.once('exit', resolve)), sleep(1600)]);
  if (child.exitCode === null) child.kill('SIGKILL');
  server.close();
  await rm(profile, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
}
