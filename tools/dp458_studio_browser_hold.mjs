// DP458 real MiniPC Chrome + authenticated Studio loopback negative acceptance.
// Run ONLY against the private 127.0.0.1:18777 Studio listener with a current
// persisted HELD candidate; first verify binding_count=0 in PostgreSQL.
// Does not simulate binding approval or prove native seek; never logs the bearer.
// Requires Chrome and Node >=22, single disposable headless browser cleaned on exit.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {readFile, mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';

const tokenPath=process.env.DP458_STUDIO_TOKEN_FILE || '/home/udodo/.local/share/dichiarazioni-pubbliche/dp458/studio-browser-token';
const token=(await readFile(tokenPath,'utf8')).trim();
assert.match(token,/^[0-9a-f]{64}$/);
const host='http://127.0.0.1:18777';
const profile=await mkdtemp(path.join(tmpdir(),'dp458-real-studio-browser-'));
const child=spawn('/usr/bin/google-chrome', [
  '--headless=new', '--disable-gpu', '--no-first-run',
  '--no-default-browser-check','--disable-background-networking',
  '--remote-debugging-port=0','--user-data-dir='+profile,host+'/'], {stdio:'ignore'});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let socket;
const events=[];
try {
  let port;
  for(let k=0;k<200;k++){
    if(child.exitCode!==null)throw Error('REAL_STUDIO_CHROME_EXITED');
    try{port=(await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break;}
    catch{await sleep(70);}
  }
  assert.ok(port,'REAL_STUDIO_CHROME_DEVTOOLS_UNAVAILABLE');
  let target;
  for(let k=0;k<150;k++){
    try {
      const pages=await fetch('http://127.0.0.1:'+port+'/json/list').then(x=>x.json());
      target=pages.find(x=>x.type==='page'&&x.url.startsWith(host));
      if(target?.webSocketDebuggerUrl)break;
    }catch{}
    await sleep(70);
  }
  assert.ok(target?.webSocketDebuggerUrl,'REAL_STUDIO_PAGE_NOT_FOUND');
  socket=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{
    socket.addEventListener('open',resolve,{once:true});
    socket.addEventListener('error',reject,{once:true});
  });
  let id=0;const pending=new Map();
  socket.addEventListener('message',({data})=>{
    const payload=JSON.parse(data);
    if(payload.method==='Network.responseReceived'){
      const url=payload.params.response?.url||'';
      if(url.startsWith(host+'/v1/media/'))
        events.push({path:new URL(url).pathname,status:payload.params.response.status});
    }
    if(!payload.id||!pending.has(payload.id))return;
    const state=pending.get(payload.id);pending.delete(payload.id);
    if(payload.error)state.reject(Error(payload.error.message));
    else state.resolve(payload.result);
  });
  const send=(method,params={})=>new Promise((resolve,reject)=>{
    const key=++id;pending.set(key,{resolve,reject});
    socket.send(JSON.stringify({id:key,method,params}));
  });
  const evalJs=async expression=>{
    const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    if(r.exceptionDetails)throw Error('REAL_STUDIO_JS_EVALUATION_FAILURE');
    return r.result.value;
  };
  const wait=async(expression)=>{
    for(let k=0;k<150;k++){
      if(await evalJs(expression))return;
      await sleep(80);
    }
    throw Error('REAL_STUDIO_BROWSER_EXPECTATION_UNMET');
  };
  const enter=async()=>{
    for(const type of ['rawKeyDown','char','keyUp'])
      await send('Input.dispatchKeyEvent',{type,key:'Enter',code:'Enter',
        windowsVirtualKeyCode:13,nativeVirtualKeyCode:13,
        ...(type==='char'?{text:'\r',unmodifiedText:'\r'}:{})});
  };
  await send('Runtime.enable');
  await send('Network.enable');
  await send('Page.enable');
  await wait('document.getElementById("media-verified-audio")!==null');
  const initial=await evalJs('(()=>{let a=document.getElementById("media-verified-audio");return {preload:a.preload,autoplay:a.autoplay,hasSource:a.hasAttribute("src"),paused:a.paused}})()');
  assert.equal(initial.autoplay,false); assert.equal(initial.hasSource,false); assert.equal(initial.paused,true); assert.ok(['none','metadata'].includes(initial.preload));
  await evalJs('document.querySelector("[data-panel=captures]").click()');
  await evalJs('document.getElementById("token").focus()');
  await send('Input.insertText',{text:token});
  assert.equal(await evalJs('document.getElementById("token").value.length'),64);
  await evalJs('(()=>{let f=document.querySelector("form[data-endpoint=\'/v1/media/binding\']");f.elements.namedItem("binding_id").value="binding:dp458:I-293056:cue12";f.querySelector("button[type=submit]").focus()})()');
  await enter();
  await wait('document.getElementById("media-binding-summary").textContent.includes("Nessuna attestazione")');
  await evalJs('document.getElementById("media-play-button").focus()');
  await enter();
  await wait('document.getElementById("media-play-status").textContent.includes("Riproduzione negata")');
  const state=await evalJs('(()=>{let a=document.getElementById("media-verified-audio");let t=document.body.innerText;return {paused:a.paused,hidden:a.hidden,hasSource:a.hasAttribute("src"),currentTime:a.currentTime,autoPlay:a.autoplay,preload:a.preload,secretQuoteVisible:t.includes("A stronger, more independent Europe is now emerging."),binarySourceVisible:t.includes("qaa.mp4?filename="),status:document.getElementById("media-play-status").textContent}})()');
  assert.equal(state.paused,true);
  assert.equal(state.hidden,true);
  assert.equal(state.hasSource,false);
  assert.equal(state.currentTime,0);
  assert.equal(state.autoPlay,false);
  assert.equal(state.secretQuoteVisible,false);
  assert.equal(state.binarySourceVisible,false);
  assert.ok(events.some(x=>x.path==='/v1/media/binding'&&x.status===503));
  assert.ok(events.some(x=>x.path==='/v1/media/playback'&&x.status===503));
  await evalJs('document.getElementById("clear").click()');
  assert.equal(await evalJs('document.getElementById("token").value.length'),0);
  console.log(JSON.stringify({
    status:'REAL_PERSISTED_STUDIO_BROWSER_FAIL_CLOSED',
    origin:'127.0.0.1:18777',real_postgres_source:true,
    keyboard_activation:true,endpoint_statuses:events,
    initial_no_autoplay:true,initial_preload:initial.preload,media_hidden:state.hidden,no_media_src:!state.hasSource,
    currentTime:state.currentTime,no_private_text_leak:!state.secretQuoteVisible,
    no_private_url_leak:!state.binarySourceVisible,
    cleared_token:true,native_seek:'NOT_AUTHORIZED',publication_authorized:false
  }));
}finally {
  try{socket?.close();}catch{}
  child.kill('SIGTERM');
  await rm(profile,{recursive:true,force:true}).catch(()=>{});
}
