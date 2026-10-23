/** DP-439 private operator session: actual Python v3 inputs -> TS -> isolated Astro SSR. */
import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {createHash} from "node:crypto";
import {mkdir,readFile,rm,symlink,writeFile} from "node:fs/promises";
import {join} from "node:path";
import {fileURLToPath} from "node:url";
import {makeScratchDir} from "./lib/scratch.mjs";
import {canonicalJson} from "../src/lib/searchIndex.ts";
import {buildPublicStatementSearchV3} from "../src/lib/publicStatementSearchV3.ts";
import {readPrivateV3OperatorSession} from "../src/lib/privateV3OperatorSession.ts";

const root=fileURLToPath(new URL("../../",import.meta.url));
const web=fileURLToPath(new URL("../",import.meta.url));
const python=[
  "import json",
  "from dataclasses import asdict,replace",
  "from datetime import datetime,timezone,timedelta",
  "from test_dp439_person_topic_v3 import fixture,make,event",
  "from test_dp438_public_person import identity",
  "from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3",
  "from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256",
  "from dichiarazioni_pubbliche.public_synopsis_v3 import ApprovedTopicIntersection,ReviewedSynopsisSentence,prepare_public_synopsis",
  "_,b,_,roster=fixture()",
  "b['statements'][1]['source_sha256']='a'*64",
  "b['dataset_sha256']=projection_dataset_sha256(b)",
  "people=build_public_people_v3(roster,[identity(p) for p in roster],[],[],public_bundle=b,current_public_dataset_sha256=b['dataset_sha256'],allow_public_person_v3=True)",
  "decisions=tuple(event(b,i,'topic:economia') for i in (0,1,2))",
  "joined=make(b,people,decisions)",
  "revoked=make(b,people,(*decisions,event(b,0,'topic:economia',revision=2,status='REVOKED')))",
  "now=datetime.now(timezone.utc)",
  "keys=tuple((s['statement_id'],s['version_id']) for s in b['statements'][:2])",
  "att=ApprovedTopicIntersection(person_id='person:A',topic_id='topic:economia',dataset_sha256=b['dataset_sha256'],statement_versions=keys,statement_lineages=tuple((*key,'lineage:'+str(i)) for i,key in enumerate(keys)),review_event_id='review:topic:independent',status='APPROVED',currentness_attestation_id='attested:independent',currentness_attested_at=now.isoformat(),currentness_valid_until=(now+timedelta(hours=2)).isoformat())",
  "sentences=tuple(ReviewedSynopsisSentence(text=('Nel corpus raccolto <img src=x onerror=alert(1)> figura una dichiarazione datata.' if i==0 else 'Nel corpus raccolto figura una seconda dichiarazione datata.'),source_statement_versions=(key,),source_quote_sha256=(b['statements'][i]['quote_sha256'],),review_event_id='review:summary:'+str(i),kind='REVIEWED_DESCRIPTIVE_SUMMARY') for i,key in enumerate(keys))",
  "args=dict(bundle=b,intersection=att,reviewed_sentences=sentences,current_public_dataset_sha256=b['dataset_sha256'],coverage_note='Nel corpus raccolto la copertura è incompleta.',now=now)",
  "ready=prepare_public_synopsis(**args)",
  "print(json.dumps(dict(source=b,people=people,join=joined,revoked=revoked,synopsis=asdict(ready)),ensure_ascii=False))",
].join("\n");
const produced=spawnSync("python3",["-c",python],{
  cwd:root,encoding:"utf8",timeout:20000,
  env:{...process.env,PYTHONPATH:"poc:tests",PYTHONDONTWRITEBYTECODE:"1"},
});
assert.equal(produced.status,0,produced.stderr);
const {source,people,join:intersection,revoked,synopsis}=JSON.parse(produced.stdout);
assert.equal(synopsis.status,"READY_READ_MODEL");
const index=await buildPublicStatementSearchV3(intersection,{
  personSha256:people.dataset_sha256,statementSha256:source.dataset_sha256,
  intersectionSha256:intersection.dataset_sha256,
});
const digest=value=>createHash("sha256").update(canonicalJson(value)).digest("hex");
const routes=people.people.map(person=>person.route).sort();
const pins={
  allowPrivatePersonTopic:true,allowPrivateSynopsisCrossPreview:true,
  allowPrivatePersonPreview:true,allowSynopsisV3:true,
  releaseId:"synthetic-session",epoch:11,personId:"person:A",topicId:"topic:economia",
  indexSha256:index.index_sha256,personSha256:people.dataset_sha256,
  intersectionSha256:intersection.dataset_sha256,statementSha256:source.dataset_sha256,
  topicSha256ById:Object.fromEntries(source.topics.map(topic=>[topic.topic_id,digest(topic)])),
  generatedAt:source.generated_at,sourceGeneratedAt:source.generated_at,
  publicDatasetSha256:source.dataset_sha256,publicGeneratedAt:source.generated_at,
  synopsisSha256:digest(synopsis),synopsisFingerprint:synopsis.fingerprint,
  personSitemapSha256:digest(routes),
  validUntil:new Date(Date.now()+3600_000).toISOString(),
};
const assets={source,people,join:intersection,index,synopsis,sitemapPersonRoutes:routes};
const url="?persona=person%3AA&tema=topic%3Aeconomia&ordine=recent";
const read=(a=assets,p=pins,q=url,current=async()=>({...p}))=>
  readPrivateV3OperatorSession(a,p,q,current,{pageSize:1});
const first=await read();
assert.equal(first.status,"PRIVATE_OPERATOR_SESSION");
assert.equal(first.publicationAuthorized,false);
assert.equal(first.providerCalls,0);
assert.equal(first.resultCount,2);
assert.equal(first.rows.length,1);
assert.equal(first.rows[0].statementId,"statement:2");
assert.equal(first.synopsisCount,2);
assert.equal(first.robots,"noindex,nofollow,noarchive");
assert.match(first.html,/data-private-v3-operator-session/);
assert.match(first.html,/data-session-result-count[^>]*>2 risultati/);
assert.match(first.html,/&lt;img src=x onerror=alert\(1\)&gt;/);
assert.doesNotMatch(first.html,/<img\s|<script\s|review_provenance|review:summary/);
assert.match(first.html,/data-original-quote/);
assert.match(first.html,/data-original-statement/);
assert.match(first.html,/href="\/dichiarazioni\/statement-2\/"/);
assert.match(first.html,/href="\?persona=person%3AA&amp;tema=topic%3Aeconomia[^"]*pagina=2/);
assert.match(first.html,/id="dp439-operator-record-1" tabindex="-1"/);
assert.match(first.html,/href="#dp439-operator-record-1"/);
const ids=[...first.html.matchAll(/\sid="([^"]+)"/g)].map(x=>x[1]);
const hrefs=[...first.html.matchAll(/href="#([^"]+)"/g)].map(x=>x[1]);
assert.equal(new Set(ids).size,ids.length,"unique focus IDs including reused synopsis browser");
assert.ok(hrefs.every(target=>ids.includes(target)),"every navigation fragment has a target");
const next=await read(assets,pins,"?"+first.nextUrl);
assert.equal(next.rows[0].statementId,"statement:1");
assert.equal(next.previousUrl.startsWith("persona="),true);
assert.equal(next.resultCount,2);
assert.equal((await read(assets,pins,"?"+next.previousUrl)).rows[0].statementId,"statement:2");
assert.deepEqual(await read(),first,"query URL reload is deterministic for pinned release");

// RED: a valid operator session used to copy raw caller-supplied source IDs
// and no-hit query markers into a shareable href, even after zero records.
// Exact public source/topic membership, NOT input grammar, must authorize
// what may reappear in share URLs or query history suggestions.
const approvedSource=first.rows[0].sourceContentId;
const approvedFilter=await read(assets,pins,url+"&fonte="+encodeURIComponent(approvedSource));
assert.equal(approvedFilter.resultCount,1);
assert.equal(new URLSearchParams(approvedFilter.shareableQuery).get("fonte"),approvedSource);
assert.match(approvedFilter.html,/data-session-url/);
const publicQuery=first.rows[0].sourceTitle;
const publicSearch=await read(assets,pins,url+"&q="+encodeURIComponent(publicQuery));
assert.ok(publicSearch.resultCount>0,"an approved public title must stay searchable");
assert.equal(new URLSearchParams(publicSearch.shareableQuery).get("q"),publicQuery);
for(const hostile of [
  {key:"fonte",marker:"content:private-secret",value:"content%3Aprivate-secret"},
  {key:"q",marker:"person:private-secret",value:"person%3Aprivate-secret"},
  {key:"q",marker:"%00",value:"%2500"},
]) {
  const result=await read(assets,pins,url+"&"+hostile.key+"="+hostile.value);
  assert.equal(result.status,"PRIVATE_OPERATOR_SESSION");
  assert.equal(result.resultCount,0);
  assert.equal(new URLSearchParams(result.shareableQuery).get(hostile.key),null,
    `unapproved ${hostile.key} must not be reissued as a shareable filter`);
  assert.doesNotMatch(decodeURIComponent(JSON.stringify(result)),
    new RegExp(hostile.marker.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")),
    `unapproved ${hostile.key} must not appear in HTML, share link or page links`);
  assert.equal(new URLSearchParams(result.shareableQuery).get("persona"),pins.personId);
  assert.equal(new URLSearchParams(result.shareableQuery).get("tema"),pins.topicId);
  assert.match(result.html,/data-session-url/);
}
const combined=await read(assets,pins,
  url+"&fonte=content%3Aprivate-secret&q=person%3Aprivate-secret&pagina=2");
assert.equal(combined.resultCount,0);
assert.equal(combined.page,1,"share the effective page after a no-match request");
assert.equal(new URLSearchParams(combined.shareableQuery).get("pagina"),null);
assert.doesNotMatch(decodeURIComponent(JSON.stringify(combined)),/private-secret/);

const reject=(name,a=assets,p=pins,q=url,current=async()=>({...p}),pattern=/DP439_SESSION_|DP440_|PUBLIC_|DP439_PRIVATE_/)=>
  assert.rejects(read(a,p,q,current),pattern,name);
await reject("wrong Person cannot leak unrelated synopsis",assets,pins,"?persona=person%3AB&tema=topic%3Aeconomia");
await reject("wrong Topic cannot leak pinned synopsis",assets,pins,"?persona=person%3AA&tema=topic%3Aeconomica");
await reject("empty filter cannot escape single Person/Topic",assets,pins,"?ordine=recent");
await reject("source generation mixed across aliases",assets,{...pins,generatedAt:"2026-10-10T00:00:00Z"});
await reject("source SHA mixed across aliases",assets,{...pins,publicDatasetSha256:"f".repeat(64)});
await reject("invalid same-release source",{
  ...assets,source:{...assets.source,statements:assets.source.statements.map((row,i)=>
    i===0?{...row,review_provenance:{...row.review_provenance,rights:""}}:row)},
});
await reject("expired issuer",assets,{...pins,validUntil:"2000-01-01T00:00:00Z"});
await reject("unknown provider/source flag",assets,{...pins,allowPrivatePersonTopic:false});
await reject("epoch changed before read",assets,pins,url,async()=>({...pins,epoch:12}));
const revokedIndex=await buildPublicStatementSearchV3(revoked,{
  personSha256:people.dataset_sha256,statementSha256:source.dataset_sha256,
  intersectionSha256:revoked.dataset_sha256,
});
await reject("fresh revoked Topic membership does not allow old synopsis",{
  ...assets,join:revoked,index:revokedIndex,
},{...pins,intersectionSha256:revoked.dataset_sha256,indexSha256:revokedIndex.index_sha256});
let reads=0;
await reject("epoch races during nested readers",assets,pins,url,async()=>{
  reads++;
  return {...pins,epoch:reads===4?12:11};
},/CURRENT_(?:RELEASE_)?CHANGED/);
assert.ok(reads>=4);
let postReads=0;
await reject("epoch changes after render",assets,pins,url,async()=>{
  postReads++;
  return {...pins,epoch:postReads===6?12:11};
},/CURRENT_CHANGED/);
assert.equal(postReads,6);
const preserved=structuredClone(first);
source.statements[0].original_text+=" late mutation";
assert.deepEqual(first,preserved,"session DTO and HTML detached from mutable assets");

const scratch=await makeScratchDir("dp439-operator-session-");
try{
  await mkdir(join(scratch,"src/pages"),{recursive:true});
  await symlink(join(web,"node_modules"),join(scratch,"node_modules"));
  await writeFile(join(scratch,"package.json"),JSON.stringify({private:true,type:"module"}));
  await writeFile(join(scratch,"astro.config.mjs"),
    "import {defineConfig} from 'astro/config';export default defineConfig({output:'static'});");
  const modulePath=fileURLToPath(new URL("../src/lib/privateV3OperatorSession.ts",import.meta.url));
  const page=(sessionUrl=url)=>[
    "---",
    `import {readPrivateV3OperatorSession} from ${JSON.stringify(modulePath)};`,
    'import assets from "../../assets.json";',
    'import expected from "../../pins.json";',
    'import current from "../../current.json";',
    'let reads=0;',
    'const {driftAt=0,...nowPins}=current;',
    `const view=await readPrivateV3OperatorSession(assets,expected,${JSON.stringify(sessionUrl)},`,
    ' async()=>({...nowPins,epoch:nowPins.epoch+(driftAt&&++reads===driftAt?1:0)}),{pageSize:1});',
    "---",
    '<html lang="it"><head><meta name="robots" content={view.robots} /></head>',
    '<body><Fragment set:html={view.html}/></body></html>',
  ].join("\n");
  async function build(a,p,current,out,sessionUrl=url){
    await writeFile(join(scratch,"assets.json"),JSON.stringify(a));
    await writeFile(join(scratch,"pins.json"),JSON.stringify(p));
    await writeFile(join(scratch,"current.json"),JSON.stringify(current));
    await writeFile(join(scratch,"src/pages/index.astro"),page(sessionUrl));
    return spawnSync(join(web,"node_modules/.bin/astro"),[
      "build","--root",scratch,"--outDir",join(scratch,out),
    ],{cwd:scratch,encoding:"utf8",timeout:45000});
  }
  const approved=structuredClone(assets);
  approved.source.statements[0].original_text=
    approved.source.statements[0].original_text.replace(" late mutation","");
  const positive=await build(approved,pins,pins,"ok");
  assert.equal(positive.status,0,positive.stdout+"\n"+positive.stderr);
  const html=await readFile(join(scratch,"ok/index.html"),"utf8");
  assert.match(html,/noindex,nofollow,noarchive/);
  assert.match(html,/data-private-v3-operator-session/);
  assert.match(html,/data-original-quote/);
  assert.match(html,/id="dp439-operator-record-1" tabindex="-1"/);
  assert.doesNotMatch(html,/<img\s|review_provenance/);
  const scrubbed=await build(approved,pins,pins,"scrubbed",
    url+"&fonte=content%3Aprivate-secret&q=person%3Aprivate-secret");
  assert.equal(scrubbed.status,0,scrubbed.stdout+"\n"+scrubbed.stderr);
  const scrubbedHtml=await readFile(join(scratch,"scrubbed/index.html"),"utf8");
  assert.match(scrubbedHtml,/data-session-url/);
  assert.match(scrubbedHtml,/0 risultati nel corpus pubblico approvato/);
  assert.doesNotMatch(scrubbedHtml,/private-secret|content%3Aprivate|person%3Aprivate/);
  const late=await build(approved,pins,{...pins,driftAt:6},"late");
  assert.notEqual(late.status,0,"revoke between render and reply must abort SSR");
  assert.match(late.stdout+late.stderr,/CURRENT_CHANGED/);
  const withdrawn=await build({...approved,join:revoked,index:revokedIndex},{
    ...pins,intersectionSha256:revoked.dataset_sha256,indexSha256:revokedIndex.index_sha256,
  },{...pins,intersectionSha256:revoked.dataset_sha256,indexSha256:revokedIndex.index_sha256},"revoked");
  assert.notEqual(withdrawn.status,0,"re-pinned revoked Topic aborts before HTML");
}finally{await rm(scratch,{recursive:true,force:true});}
console.log("DP439 private V3 session Python→TS→Astro SSR PASS; scoped URL/back-forward/anchor focus/late-epoch/revocation negatives PASS");
