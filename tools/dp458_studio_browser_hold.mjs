// DP458 real MiniPC Studio loopback negative acceptance, using native agent-browser.
// Preflight: a persisted HELD candidate with binding_count=0; token never logged.
// This does not authorize playback, seek, source rights or publication.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { readFile } from 'node:fs/promises';

const tokenPath = process.env.DP458_STUDIO_TOKEN_FILE
  || '/home/udodo/.local/share/dichiarazioni-pubbliche/dp458/studio-browser-token';
const token = (await readFile(tokenPath, 'utf8')).trim();
assert.match(token, /^[0-9a-f]{64}$/);
const host = 'http://127.0.0.1:18777';
const fixtureOnly = process.env.DP458_TEST_FIXTURE === '1';
const name = 'dp458-' + randomBytes(8).toString('hex');
const env = {
  ...process.env,
  AGENT_BROWSER_NAMESPACE: name,
  AGENT_BROWSER_SESSION: name,
  AGENT_BROWSER_EXECUTABLE_PATH: '/usr/bin/google-chrome',
  AGENT_BROWSER_AUTOSAVE_INTERVAL_MS: '0',
  AGENT_BROWSER_RESTORE_SAVE: 'never',
};
delete env.AGENT_BROWSER_RESTORE;
delete env.AGENT_BROWSER_PROFILE;
delete env.AGENT_BROWSER_STATE;
delete env.AGENT_BROWSER_SESSION_NAME;
delete env.AGENT_BROWSER_AUTO_CONNECT;

function safeError(value) {
  return String(value).replaceAll(token, '[REDACTED]').slice(0, 1000);
}

async function native(commands) {
  // Batch JSON through stdin: no bearer in shell arguments, shell history or a
  // browser command echo. --omit-command hides command inputs in success rows.
  const child = spawn('agent-browser', ['batch', '--bail', '--json', '--omit-command'], {
    env, stdio: ['pipe', 'pipe', 'pipe'],
  });
  let stdout = '';
  let stderr = '';
  const stop = setTimeout(() => child.kill('SIGTERM'), 30000);
  child.stdout.on('data', chunk => {
    stdout += chunk.toString();
    if (stdout.length > 2_000_000) child.kill('SIGTERM');
  });
  child.stderr.on('data', chunk => {
    stderr += chunk.toString();
    if (stderr.length > 100_000) child.kill('SIGTERM');
  });
  child.stdin.end(JSON.stringify(commands));
  const code = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', resolve);
  }).finally(() => clearTimeout(stop));
  let rows;
  try { rows = JSON.parse(stdout); } catch { throw Error('AGENT_BROWSER_BATCH_INVALID_JSON: ' + safeError(stderr)); }
  if (code !== 0 || !Array.isArray(rows) ||
      rows.length !== commands.length || rows.some(row => !row.success)) {
    throw Error('AGENT_BROWSER_BATCH_FAILED: ' + safeError(JSON.stringify(rows)) + ' ' + safeError(stderr));
  }
  return rows.map(row => row.result);
}

async function closeNative() {
  // Close the isolated namespace even if any assertion fails. No --restore,
  // --state, or --profile is ever used, so private page auth is transient.
  const child = spawn('agent-browser', ['close'], {
    env, stdio: ['ignore', 'ignore', 'pipe'],
  });
  let stderr = '';
  child.stderr.on('data', chunk => { stderr += chunk.toString(); });
  const code = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', resolve);
  });
  if (code !== 0) throw Error('AGENT_BROWSER_CLOSE_FAILED: ' + safeError(stderr));
}

const initialExpr = '(()=>{let a=document.getElementById("media-verified-audio");return {preload:a.preload,autoplay:a.autoplay,hasSource:a.hasAttribute("src"),paused:a.paused}})()';
const stateExpr = '(()=>{let a=document.getElementById("media-verified-audio");let t=document.body.innerText;return {paused:a.paused,hidden:a.hidden,hasSource:a.hasAttribute("src"),currentTime:a.currentTime,autoPlay:a.autoplay,preload:a.preload,secretQuoteVisible:t.includes("A stronger, more independent Europe is now emerging."),binarySourceVisible:t.includes("qaa.mp4?filename="),status:document.getElementById("media-play-status").textContent}})()';
try {
  await native([['open', host + '/'], ['wait', '--fn', 'document.getElementById("media-verified-audio")!==null']]);
  const initial = (await native([['eval', initialExpr]]))[0].result;
  assert.equal(initial.autoplay, false);
  assert.equal(initial.hasSource, false);
  assert.equal(initial.paused, true);
  assert.ok(['none', 'metadata'].includes(initial.preload));

  // Agent-browser's native keyboard, DOM and request-monitoring features.
  await native([
    ['network', 'requests', '--clear'],
    ['click', '[data-panel=captures]'],
    ['fill', '#token', token],
    ['eval', 'document.getElementById("token").value.length'],
  ]).then(results => assert.equal(results[3].result, 64));

  await native([
    ['eval', `(()=>{let f=document.querySelector('form[data-endpoint="/v1/media/binding"]');f.elements.namedItem("binding_id").value="binding:dp458:I-293056:cue12";f.querySelector("button[type=submit]").focus()})()`],
    ['press', 'Enter'],
    ['wait', '--fn', 'document.getElementById("media-binding-summary").textContent.includes("Nessuna attestazione")'],
    ['focus', '#media-play-button'],
    ['press', 'Enter'],
    ['wait', '--fn', 'document.getElementById("media-play-status").textContent.includes("Riproduzione negata")'],
  ]);
  const state = (await native([['eval', stateExpr]]))[0].result;
  assert.equal(state.paused, true);
  assert.equal(state.hidden, true);
  assert.equal(state.hasSource, false);
  assert.equal(state.currentTime, 0);
  assert.equal(state.autoPlay, false);
  assert.equal(state.secretQuoteVisible, false);
  assert.equal(state.binarySourceVisible, false);

  const network = (await native([['network', 'requests', '--filter', '/v1/media/']]))[0].requests;
  assert.ok(Array.isArray(network), 'native request log is available');
  const events = network.filter(item => item.url?.startsWith(host + '/v1/media/'))
    .map(item => ({ path: new URL(item.url).pathname, status: item.status }));
  assert.ok(events.some(item => item.path === '/v1/media/binding' && item.status === 503));
  assert.ok(events.some(item => item.path === '/v1/media/playback' && item.status === 503));

  const cleared = await native([['click', '#clear'], ['eval', 'document.getElementById("token").value.length']]);
  assert.equal(cleared[1].result, 0);
  console.log(JSON.stringify({
    status: fixtureOnly ? 'SYNTHETIC_BROWSER_CAPABILITY_ONLY' : 'REAL_PERSISTED_STUDIO_BROWSER_FAIL_CLOSED',
    origin: '127.0.0.1:18777', real_postgres_source: !fixtureOnly,
    keyboard_activation: true, endpoint_statuses: events,
    initial_no_autoplay: true, initial_preload: initial.preload,
    media_hidden: state.hidden, no_media_src: !state.hasSource,
    currentTime: state.currentTime, no_private_text_leak: !state.secretQuoteVisible,
    no_private_url_leak: !state.binarySourceVisible,
    cleared_token: true, native_seek: 'NOT_AUTHORIZED', publication_authorized: false,
  }));
} finally {
  // Always attempt cleanup even if native.open fails partway through.
  await closeNative();
}
