// DP-410: real Google Chrome keyboard/320px private Studio accessibility proxy.
// No VoiceOver/physical iOS claim; one isolated Chrome profile, loopback fixture.
// Usage: PYTHONPATH=poc python3 -c 'from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page; import sys;sys.stdout.buffer.write(render_studio_login_page("a"*32))' | node tests/studio_local_page_accessibility_next.mjs
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';

let html = '';
for await (const chunk of process.stdin) html += chunk;
assert.match(html, /<script nonce="[a-f0-9]{32}">/);
assert.match(html, /name="robots" content="noindex,nofollow,noarchive,nosnippet"/);
const requests = [];
const mediaRequests = [];
let mediaRevoked = false;
const playableWav = Buffer.alloc(44 + 16000 * 4 * 2);
playableWav.write('RIFF',0); playableWav.writeUInt32LE(playableWav.length-8,4);
playableWav.write('WAVEfmt ',8); playableWav.writeUInt32LE(16,16);
playableWav.writeUInt16LE(1,20); playableWav.writeUInt16LE(1,22);
playableWav.writeUInt32LE(16000,24); playableWav.writeUInt32LE(32000,28);
playableWav.writeUInt16LE(2,32); playableWav.writeUInt16LE(16,34);
playableWav.write('data',36); playableWav.writeUInt32LE(playableWav.length-44,40);
const realMediaPath=process.env.DP419_REAL_MEDIA_PATH;
const playbackBytes=realMediaPath ? await readFile(realMediaPath) : playableWav;
const playbackType=realMediaPath
  ? (process.env.DP419_REAL_MEDIA_TYPE || (realMediaPath.endsWith('.m4a') ? 'audio/mp4' : 'audio/ogg'))
  : 'audio/wav';
const playbackStart=realMediaPath ? Number(process.env.DP419_REAL_MEDIA_START_MS || 522000) : 1200;
const playbackEnd=realMediaPath ? Number(process.env.DP419_REAL_MEDIA_END_MS || 534000) : 2200;
const server = createServer(async (req,res) => {
  if (req.method === 'GET' && req.url === '/') {
    res.writeHead(200, {'Content-Type':'text/html; charset=utf-8', 'Cache-Control':'no-store'});
    res.end(html); return;
  }
  if (req.method === 'POST' && req.url === '/v1/media/binding') {
    let body = '';
    for await (const chunk of req) body += chunk;
    const data = JSON.parse(body);
    requests.push({endpoint:req.url, data, authorization:req.headers.authorization});
    res.writeHead(200, {'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store'});
    res.end(JSON.stringify({contract_version:'studio-local-readonly-api-v1',data:{
      contract_version:'studio-capture-segment-binding-pg-v1',private_only:true,
      publication_authority:false,rights_clearance:false,seek_authorized:false,
      capture_segment_binding:'OPERATOR_ATTESTED_METADATA_ONLY',
      binding_id:data.binding_id,content_id:'content:mobile',capture_id:'capture:mobile',
      capture_sha256:'b'.repeat(64),canonical_segment_id:'segment:mobile',
      segment_index:0,start_ms:playbackStart,end_ms:playbackEnd,revision:1,
      binding_state:'HELD',hold_reasons:['CAPTURE_RIGHTS_UNKNOWN','RIGHTS_NOT_INDEPENDENTLY_APPROVED'],
      sensitive_url:'https://private.invalid/NEVER_SHOW',private_transcript:'SECRET_NEVER_SHOW',
    }})); return;
  }
  if (req.method === 'POST' && req.url === '/v1/media/playback') {
    let raw='';
    for await (const part of req) raw+=part;
    mediaRequests.push({body:JSON.parse(raw),authorization:req.headers.authorization});
    if (mediaRevoked || req.headers.authorization !== 'Bearer '+'a'.repeat(64)) {
      res.writeHead(422, {'Content-Type':'application/json'});
      res.end('{"error":"STUDIO_LOCAL_REQUEST_OR_DATA_INVALID"}'); return;
    }
    res.writeHead(200, {'Content-Type':playbackType,
      'Content-Length':playbackBytes.length,
      'X-Seek-Start-Ms':String(playbackStart),'X-Seek-End-Ms':String(playbackEnd),
      'Cache-Control':'no-store, private'});
    res.end(playbackBytes); return;
  }
  res.writeHead(404, {'Content-Type':'application/json'}).end('{}');
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin='http://127.0.0.1:'+server.address().port;
const profile=await mkdtemp(path.join(tmpdir(),'dp410-studio-a11y-'));
const chrome=process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const child=spawn(chrome, ['--headless=new','--disable-gpu','--no-first-run',
  '--no-default-browser-check','--disable-background-networking',
  '--remote-debugging-port=0','--user-data-dir='+profile,origin+'/'], {stdio:'ignore'});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let socket;
try {
  let port;
  for(let i=0;i<140;i++) {
    if(child.exitCode!==null) throw Error('Chrome stopped before debugging');
    try {port=(await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break;}
    catch {await sleep(70);}
  }
  assert(port,'one Chrome debug profile must start');
  let target;
  for(let i=0;i<140;i++) {
    try {
      const pages=await fetch(`http://127.0.0.1:${port}/json/list`).then(r=>r.json());
      target=pages.find(x=>x.type==='page' && x.url.startsWith(origin));
      if(target?.webSocketDebuggerUrl) break;
    } catch {}
    await sleep(70);
  }
  assert(target?.webSocketDebuggerUrl);
  socket=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((ok,no)=>{
    socket.addEventListener('open',ok,{once:true});
    socket.addEventListener('error',no,{once:true});
  });
  const pending=new Map();let next=0;
  socket.addEventListener('message',({data})=>{
    const msg=JSON.parse(data);
    if(!msg.id || !pending.has(msg.id)) return;
    const {ok,no}=pending.get(msg.id);pending.delete(msg.id);
    if(msg.error) no(Error(msg.error.message));else ok(msg.result);
  });
  const send=(method,params={})=>new Promise((ok,no)=>{
    const id=++next;pending.set(id,{ok,no});socket.send(JSON.stringify({id,method,params}));
  });
  const evaluate=async expr=>{
    const reply=await send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true});
    if(reply.exceptionDetails) throw Error(reply.exceptionDetails.text);
    return reply.result.value;
  };
  const wait=async expr=>{
    for(let i=0;i<280;i++){if(await evaluate(expr))return;await sleep(55);}
    const status=await evaluate(`({status:document.getElementById('status').textContent,
      binding:document.getElementById('media-binding-summary').textContent,
      focused:document.activeElement?.outerHTML.slice(0,180),
      mediaStatus:document.getElementById('media-play-status').textContent,
      audioTime:document.getElementById('media-verified-audio').currentTime,
      audioSrc:document.getElementById('media-verified-audio').getAttribute('src'),
      audioReady:document.getElementById('media-verified-audio').readyState,
      audioNetwork:document.getElementById('media-verified-audio').networkState,
      audioError:document.getElementById('media-verified-audio').error?.code})`);
    throw Error('Chrome condition did not resolve: '+expr+'; state='+JSON.stringify(status)
      +'; endpoints='+requests.map(x=>x.endpoint).join(',')+'; mediaRequests='+JSON.stringify(mediaRequests));
  };
  const key=async (name,code,virtual)=>{
    for(const type of name==='Enter'?['rawKeyDown','char','keyUp']:['rawKeyDown','keyUp'])
      await send('Input.dispatchKeyEvent',{type,key:name,code,windowsVirtualKeyCode:virtual,
        nativeVirtualKeyCode:virtual,...(type==='char'?{text:'\r',unmodifiedText:'\r'}:{})});
  };
  await send('Runtime.enable');
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride',{width:320,height:720,deviceScaleFactor:1,mobile:true});
  // Changing mobile metrics after navigation alone retains Chrome's previous
  // layout viewport. Reload exactly once under the mobile emulation profile.
  await send('Page.reload',{ignoreCache:true});
  await wait('!!document.querySelector("form[data-endpoint=\\"/v1/candidate/decision-annotate\\"]")');
  const initialAudio=await evaluate(`(() => {
    const audio=document.getElementById('media-verified-audio');
    return {preload:audio.preload,autoplay:audio.autoplay,hasSource:audio.hasAttribute('src'),paused:audio.paused};
  })()`);
  assert.equal(initialAudio.preload,'none','private source media must not preload before explicit activation');
  assert.equal(initialAudio.autoplay,false);
  assert.equal(initialAudio.hasSource,false);
  assert.equal(initialAudio.paused,true);
  await evaluate(`document.querySelector('[data-panel="collections"]').click()`);
  const measurements=await evaluate(`(() => {
    const form=document.querySelector('form[data-endpoint="/v1/candidate/decision-annotate"]');
    const label=form.querySelector('textarea[name="review_event_json"]').closest('label');
    const pane=document.getElementById('collections');
    const rect=label.getBoundingClientRect();
    const parent=pane.getBoundingClientRect();
    return {innerWidth:innerWidth,screenWidth:screen.width,visualWidth:visualViewport.width,
      outerWidth:outerWidth,devicePixelRatio:devicePixelRatio,bodyWidth:document.body.getBoundingClientRect().width,
      documentWidth:document.documentElement.scrollWidth,
      labelWidth:rect.width, labelRight:rect.right, paneRight:parent.right,
      labelMin:getComputedStyle(label).minWidth, labelVisible:rect.width>0,
      overflow:[...document.querySelectorAll('body *')].filter(node=>{
        const r=node.getBoundingClientRect();return r.width>0 && r.right>320+1 && getComputedStyle(node).display!=='none';
      }).slice(0,12).map(node=>({tag:node.tagName,name:node.getAttribute('name'),id:node.id,
        width:Math.round(node.getBoundingClientRect().width),right:Math.round(node.getBoundingClientRect().right)})),
      clipped:[...document.querySelectorAll('body *')].filter(node=>
        node.clientWidth>0 && node.scrollWidth>node.clientWidth+2 && getComputedStyle(node).display!=='none')
        .slice(0,12).map(node=>({tag:node.tagName,id:node.id,
          scroll:node.scrollWidth,client:node.clientWidth,text:node.textContent.slice(0,55)})),
      formDescribedBy:form.getAttribute('aria-describedby'),
      writeStatus:document.getElementById('candidate-write-summary').getAttribute('role')};
  })()`);
  assert.equal(measurements.innerWidth,320,JSON.stringify(measurements));
  assert.equal(measurements.labelVisible,true);
  assert.ok(measurements.documentWidth<=320,
    'RED: signed ReviewEvent JSON textarea creates horizontal overflow at 320px: '+JSON.stringify(measurements));
  assert.ok(measurements.labelRight<=measurements.paneRight+1,
    'RED: signed JSON editor extends beyond the Collections panel: '+JSON.stringify(measurements));
  assert.equal(measurements.formDescribedBy,'candidate-write-summary',
    'signed dynamic form should identify its live privacy/confirmation feedback');
  assert.equal(measurements.writeStatus,'status');
  // Real keyboard: tab from the editor must advance to confirmation without
  // an off-screen trap; the accessible browser focus remains in the form.
  await evaluate(`document.querySelector('form[data-endpoint="/v1/candidate/decision-annotate"] textarea').focus()`);
  await key('Tab','Tab',9);
  const focused=await evaluate(`({tag:document.activeElement.tagName,name:document.activeElement.name,
    rect:document.activeElement.getBoundingClientRect().toJSON()})`);
  assert.equal(focused.name,'confirm_private_decision');
  assert.ok(focused.rect.left>=0 && focused.rect.right<=320,
    'next keyboard field must be visible at 320px '+JSON.stringify(focused));
  await evaluate(`document.querySelector('[data-panel="captures"]').click()`);
  const binding=await evaluate(`(() => {
    const form=document.querySelector('form[data-endpoint="/v1/media/binding"]');
    return {descriptor:form.getAttribute('aria-describedby'),
      role:document.getElementById('media-binding-summary').getAttribute('role'),
      inputLabel:form.elements.namedItem('binding_id').labels?.[0]?.textContent.trim(),
      viewportWidth:document.documentElement.scrollWidth};
  })()`);
  assert.equal(binding.descriptor,'media-binding-summary',
    'media revocation result must be associated with its dynamic form');
  assert.equal(binding.role,'status');
  assert.equal(binding.inputLabel,'Binding ID');
  assert.ok(binding.viewportWidth<=320,'media binding panel must reflow without horizontal scroll');
  await evaluate(`document.getElementById('token').value='${'a'.repeat(64)}';
    const form=document.querySelector('form[data-endpoint="/v1/media/binding"]');
    form.elements.namedItem('binding_id').value='binding:mobile';
    form.querySelector('button[type=submit]').focus();`);
  await key('Enter','Enter',13);
  await wait(`document.getElementById('media-binding-summary').textContent.includes('binding:mobile')`);
  assert.equal(requests.length,1);
  assert.equal(requests[0].endpoint,'/v1/media/binding');
  assert.deepEqual(requests[0].data,{binding_id:'binding:mobile'});
  assert.equal(requests[0].authorization,'Bearer '+'a'.repeat(64));
  const summary=await evaluate(`({text:document.getElementById('media-binding-summary').textContent,
    focused:document.activeElement.textContent,documentWidth:document.documentElement.scrollWidth,
    result:document.getElementById('results').textContent})`);
  assert.match(summary.text,/nessuna riproduzione/i);
  assert.doesNotMatch(JSON.stringify(summary),/SECRET_NEVER_SHOW|private\.invalid/);
  assert.ok(summary.documentWidth<=320,'dynamic media response cannot introduce horizontal overflow');
  assert.equal(summary.focused,'Rileggi stato corrente e revoche');
  // DP419: the real HTMLMediaElement must perform a keyboard-initiated
  // seek on original-timeline seconds, without private-media autoplay.
  await evaluate("document.getElementById('media-play-button').focus()");
  await key('Enter','Enter',13);
  await wait("document.getElementById('media-verified-audio').hasAttribute('src')");
  const pendingSeek = await evaluate(`({
    confirmed: document.getElementById('media-play-status').textContent.includes('Seek reale'),
    hidden: document.getElementById('media-verified-audio').hidden
  })`);
  if (!pendingSeek.confirmed) {
    assert.equal(pendingSeek.hidden,true,
      'audio controls must remain hidden until native seek has been verified');
  }
  await wait("document.getElementById('media-play-status').textContent.includes('Seek reale') || document.getElementById('media-play-status').textContent.includes('nessun seek verificato')");
  assert.equal(mediaRequests.length,1);
  assert.deepEqual(mediaRequests[0].body,{binding_id:'binding:mobile'});
  assert.equal(mediaRequests[0].authorization,'Bearer '+'a'.repeat(64));
  const mediaState=await evaluate(`(() => {
    const audio=document.getElementById('media-verified-audio');
    return {seek:audio.currentTime,hidden:audio.hidden,
      source:audio.hasAttribute('src'),paused:audio.paused};
  })()`);
  const seekConfirmed=await evaluate("document.getElementById('media-play-status').textContent.includes('Seek reale')");
  if (realMediaPath) assert.equal(seekConfirmed,true,'original media bytes must prove native currentTime seek');
  if (seekConfirmed) {
    assert.ok(Math.abs(mediaState.seek-playbackStart/1000)<=0.1,JSON.stringify(mediaState));
    assert.equal(mediaState.hidden,false);
    assert.equal(mediaState.source,true);
    assert.equal(mediaState.paused,true);
  } else {
    assert.equal(mediaState.hidden,true,'failed decoder must clear and hide player');
    assert.equal(mediaState.source,false,'failed decoder must revoke media blob');
  }
  mediaRevoked=true;
  await evaluate("document.getElementById('media-play-button').click()");
  await wait("document.getElementById('media-play-status').textContent.includes('Riproduzione negata')");
  assert.equal(mediaRequests.length,2);
  assert.equal(await evaluate("document.getElementById('media-verified-audio').hasAttribute('src')"),false);
  await evaluate(`document.getElementById('clear').click()`);
  assert.equal(await evaluate(`document.getElementById('media-binding-summary').textContent`),'Nessun binding verificato.');
  assert.equal(await evaluate(`document.querySelector('form[data-endpoint="/v1/media/binding"]').elements.namedItem('binding_id').value`),'');
  assert.equal(await evaluate(`document.getElementById('token').value`),'');
  console.log('DP410 + DP419 Chrome PASS: 320px, keyboard-authenticated binary request, revoked request and scrub; native seek='+(seekConfirmed?'PASS':'UNVERIFIED (headless decoder unavailable)'));
} finally {
  try {socket?.close();} catch {}
  child.kill('SIGTERM');
  await Promise.race([new Promise(ok=>child.once('exit',ok)),sleep(1600)]);
  if(child.exitCode===null) child.kill('SIGKILL');
  server.close();
  await rm(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});
}
