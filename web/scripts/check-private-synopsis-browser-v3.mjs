/** DP-440 private Python synopsis -> anchored, noindex browser/SSR fixture. */
import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {createHash} from "node:crypto";
import {mkdir, readFile, rm, symlink, writeFile} from "node:fs/promises";
import {join} from "node:path";
import {fileURLToPath} from "node:url";
import {makeScratchDir} from "./lib/scratch.mjs";
import {canonicalJson} from "../src/lib/searchIndex.ts";
import {buildPublicStatementSearchV3} from "../src/lib/publicStatementSearchV3.ts";
import {readPrivateSynopsisBrowserV3} from "../src/lib/privateSynopsisBrowserV3.ts";

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
  "b['statements'][0]['source_title']='Documento <script>alert(1)</script>'",
  "b['dataset_sha256']=projection_dataset_sha256(b)",
  "people=build_public_people_v3(roster,[identity(p) for p in roster],[],[],public_bundle=b,current_public_dataset_sha256=b['dataset_sha256'],allow_public_person_v3=True)",
  "decisions=tuple(event(b,i,'topic:economia') for i in (0,1,2))",
  "joined=make(b,people,decisions)",
  "revoked=make(b,people,(*decisions,event(b,0,'topic:economia',revision=2,status='REVOKED')))",
  "now=datetime.now(timezone.utc)",
  "keys=tuple((s['statement_id'],s['version_id']) for s in b['statements'][:2])",
  "att=ApprovedTopicIntersection(person_id='person:A',topic_id='topic:economia',dataset_sha256=b['dataset_sha256'],statement_versions=keys,statement_lineages=tuple((*key,'original-lineage:'+str(i)) for i,key in enumerate(keys)),review_event_id='review:topic:independent',status='APPROVED',currentness_attestation_id='attested:independent',currentness_attested_at=now.isoformat(),currentness_valid_until=(now+timedelta(hours=2)).isoformat())",
  "sentences=tuple(ReviewedSynopsisSentence(text=('Nel corpus raccolto <img src=x onerror=alert(1)> è riportata una posizione.' if i==0 else 'Nel corpus raccolto compare una seconda posizione datata.'),source_statement_versions=(key,),source_quote_sha256=(b['statements'][i]['quote_sha256'],),review_event_id='review:summary:'+str(i),kind=('REVIEWED_DESCRIPTIVE_SUMMARY' if i==0 else 'SOURCE_LIST_ONLY')) for i,key in enumerate(keys))",
  "args=dict(bundle=b,intersection=att,reviewed_sentences=sentences,current_public_dataset_sha256=b['dataset_sha256'],coverage_note='Nel corpus raccolto, copertura incompleta delle fonti.',now=now)",
  "ready=prepare_public_synopsis(**args)",
  "withheld=prepare_public_synopsis(**{**args,'intersection':replace(att,status='REVOKED')})",
  "print(json.dumps(dict(source=b,people=people,join=joined,revoked_join=revoked,synopsis=asdict(ready),withheld=asdict(withheld)),ensure_ascii=False))",
].join("\n");
const result=spawnSync("python3",["-c",python],{
  cwd:root,encoding:"utf8",timeout:20000,
  env:{...process.env,PYTHONPATH:"poc:tests",PYTHONDONTWRITEBYTECODE:"1"},
});
assert.equal(result.status,0,result.stderr);
const fixture=JSON.parse(result.stdout);
const {source,people,join:intersection,revoked_join:revokedJoin,synopsis,withheld}=fixture;
assert.equal(synopsis.status,"READY_READ_MODEL");
assert.equal(withheld.status,"WITHHELD");
const index=await buildPublicStatementSearchV3(intersection,{
  personSha256:people.dataset_sha256,statementSha256:source.dataset_sha256,
  intersectionSha256:intersection.dataset_sha256,
});
const hash=value=>createHash("sha256").update(canonicalJson(value)).digest("hex");
const routes=people.people.map(person=>person.route).sort();
const pins={
  allowPrivateSynopsisCrossPreview:true,allowPrivatePersonPreview:true,
  allowSynopsisV3:true,releaseId:"synthetic-browser-release",epoch:7,
  personSha256:people.dataset_sha256,statementSha256:source.dataset_sha256,
  intersectionSha256:intersection.dataset_sha256,indexSha256:index.index_sha256,
  sourceGeneratedAt:source.generated_at,personSitemapSha256:hash(routes),
  synopsisSha256:hash(synopsis),synopsisFingerprint:synopsis.fingerprint,
  validUntil:new Date(Date.now()+3600_000).toISOString(),
  publicDatasetSha256:source.dataset_sha256,publicGeneratedAt:source.generated_at,
  personId:synopsis.person_id,topicId:synopsis.topic_id,
};
const artifacts={source,people,join:intersection,index,synopsis,sitemapPersonRoutes:routes};
const read=(a=artifacts,p=pins,current=async()=>({...p}))=>
  readPrivateSynopsisBrowserV3(a,p,current);
const view=await read();
assert.equal(view.status,"PRIVATE_BROWSER_PREVIEW_ONLY");
assert.equal(view.publicationAuthorized,false);
assert.equal(view.providerCalls,0);
assert.equal(view.robots,"noindex,nofollow,noarchive");
assert.match(view.html,/data-private-synopsis-browser/);
assert.match(view.html,/data-synopsis-text/);
assert.equal((view.html.match(/data-synopsis-text/g)||[]).length,1,
  "only reviewed descriptive summaries are labelled as synopsis text");
assert.match(view.html,/<h2>Sintesi 1 di 2<\/h2>/);
assert.match(view.html,/<h2>Elenco fonti 2 di 2<\/h2>/);
assert.match(view.html,/<p data-source-list-text>/);
assert.match(view.html,/<a href="#dp440-synopsis-2">Elenco fonti 2<\/a>/);
assert.match(view.html,/data-original-quote/);
assert.equal((view.html.match(/data-original-sources/g)||[]).length,2,
  "each synopsis must have a distinct labelled original-source section");
assert.match(view.html,/<section data-original-sources aria-label="Fonti originali citate">/);
assert.match(view.html,/rel="noreferrer noopener nofollow" data-source-version=/);
assert.match(view.html,/Apri documento sorgente<\/a>/);
assert.match(view.html,/Versione documento: <code data-source-version-text>source-version:[^<]+<\/code>/,
  "source version must be legible, not only stored in a data attribute");
assert.match(view.html,/Documento &lt;script&gt;alert\(1\)&lt;\/script&gt;/);
assert.doesNotMatch(view.html,/<script\b|<svg\b/i,
  "source-title markup must remain inert text");
assert.match(view.html,/&lt;img src=x onerror=alert\(1\)&gt;/);
assert.doesNotMatch(view.html,/<img\s|<script\s/i);
assert.match(view.html,/href="\/dichiarazioni\/statement-1\/"/);
assert.match(view.html,/href="#dp440-synopsis-2"/);
assert.match(view.html,/href="#dp440-synopsis-1"/);
assert.match(view.html,/href="#dp440-source-1-1"/);
assert.match(view.html,/id="dp440-source-1-1" tabindex="-1"/);
assert.match(view.html,/id="dp440-synopsis-2" tabindex="-1"/);
const targetIds=[...view.html.matchAll(/\sid="([^"]+)"/g)].map(match=>match[1]);
const anchors=[...view.html.matchAll(/href="#([^"]+)"/g)].map(match=>match[1]);
assert.equal(new Set(targetIds).size,targetIds.length,"focus targets are unique");
for (const target of anchors) {
  assert.ok(targetIds.includes(target),`missing previous/next/focus target: ${target}`);
  assert.match(view.html,new RegExp(`id="${target}" tabindex="-1"`),
    `fragment destination must accept keyboard focus: ${target}`);
}
assert.equal((view.html.match(/data-original-quote/g)||[]).length,2);
assert.doesNotMatch(view.html,/review_provenance|review:summary|raw_transcript/);
assert.deepEqual(view,await read());

const bad=structuredClone(artifacts);
bad.source.statements[0].original_text+=" changed";
await assert.rejects(read(bad),/PUBLIC_|DP440_PRIVATE_/);
await assert.rejects(read({...artifacts,synopsis:withheld}),/WITHHELD/);
await assert.rejects(read(artifacts,{...pins,validUntil:"2000-01-01T00:00:00Z"}),/EXPIRED/);
await assert.rejects(read(artifacts,pins,async()=>({...pins,epoch:8})),/CURRENT_RELEASE_CHANGED|CURRENT_CHANGED/);
const revokedIndex=await buildPublicStatementSearchV3(revokedJoin,{
  personSha256:people.dataset_sha256,statementSha256:source.dataset_sha256,
  intersectionSha256:revokedJoin.dataset_sha256,
});
await assert.rejects(read({...artifacts,join:revokedJoin,index:revokedIndex},{
  ...pins,intersectionSha256:revokedJoin.dataset_sha256,indexSha256:revokedIndex.index_sha256,
}),/MEMBERSHIP_STALE/);
let reads=0;
await assert.rejects(read(artifacts,pins,async()=>{
  reads++;
  return {...pins,epoch:reads===3?8:7};
}),/CURRENT_CHANGED/);
assert.equal(reads,3,"one additional epoch pin read follows composed HTML rendering");
const mutableExpected=structuredClone(pins);
let mutableReads=0;
await assert.rejects(read(artifacts,mutableExpected,async()=>{
  mutableReads++;
  if(mutableReads===3) mutableExpected.epoch++;
  return {...mutableExpected};
}),/CURRENT_CHANGED/,
  "a caller mutating the original expected pins during the final await cannot bless stale HTML");
assert.equal(mutableReads,3);
const snapshot=structuredClone(view);
source.statements[0].original_text+=" late mutation";
assert.deepEqual(view,snapshot,"rendered HTML is detached from mutable fixtures");

const scratch=await makeScratchDir("dp440-private-browser-");
try {
  await mkdir(join(scratch,"src/pages"),{recursive:true});
  await symlink(join(web,"node_modules"),join(scratch,"node_modules"));
  await writeFile(join(scratch,"package.json"),JSON.stringify({private:true,type:"module"}));
  await writeFile(join(scratch,"astro.config.mjs"),
    "import {defineConfig} from 'astro/config';export default defineConfig({output:'static'});");
  const modulePath=fileURLToPath(new URL("../src/lib/privateSynopsisBrowserV3.ts",import.meta.url));
  const page=[
    "---",
    `import {readPrivateSynopsisBrowserV3} from ${JSON.stringify(modulePath)};`,
    'import assets from "../../assets.json";',
    'import expected from "../../pins.json";',
    'import current from "../../current.json";',
    "let reads=0;",
    "const {epochDrift=false,...currentPins}=current;",
    "const view=await readPrivateSynopsisBrowserV3(assets,expected,async()=>",
    " ({...currentPins,epoch:currentPins.epoch+(epochDrift&&++reads===3?1:0)}));",
    "---",
    '<html lang="it"><head><meta charset="utf-8" />',
    '<meta name="robots" content={view.robots} /></head><body>',
    '<Fragment set:html={view.html}/>',
    '</body></html>',
  ].join("\n");
  await writeFile(join(scratch,"src/pages/index.astro"),page);
  async function build(a,p,c,folder){
    await writeFile(join(scratch,"assets.json"),JSON.stringify(a));
    await writeFile(join(scratch,"pins.json"),JSON.stringify(p));
    await writeFile(join(scratch,"current.json"),JSON.stringify(c));
    return spawnSync(join(web,"node_modules/.bin/astro"),[
      "build","--root",scratch,"--outDir",join(scratch,folder),
    ],{cwd:scratch,encoding:"utf8",timeout:90000});
  }
  const approved=structuredClone(artifacts);
  approved.source.statements[0].original_text=source.statements[0].original_text.replace(" late mutation","");
  const ok=await build(approved,pins,pins,"approved");
  assert.equal(ok.status,0,
    (ok.error?.message??"")+"\n"+ok.stdout+"\n"+ok.stderr);
  const html=await readFile(join(scratch,"approved/index.html"),"utf8");
  assert.match(html,/<meta name="robots" content="noindex,nofollow,noarchive"/);
  assert.match(html,/data-original-quote/);
  assert.match(html,/data-original-sources/);
  assert.match(html,/Apri documento sorgente<\/a>/);
  assert.match(html,/Versione documento: <code data-source-version-text>source-version:[^<]+<\/code>/);
  assert.match(html,/Documento &lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.doesNotMatch(html,/<script\b|<svg\b/i);
  assert.match(html,/<h2>Elenco fonti 2 di 2<\/h2>/);
  assert.match(html,/&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html,/href="#dp440-synopsis-2"/);
  assert.doesNotMatch(html,/<img\s|PRIVATE AUTH ERROR|review_provenance/);
  const revoked=await build({...approved,join:revokedJoin,index:revokedIndex},{
    ...pins,intersectionSha256:revokedJoin.dataset_sha256,indexSha256:revokedIndex.index_sha256,
  },{...pins,intersectionSha256:revokedJoin.dataset_sha256,indexSha256:revokedIndex.index_sha256},"revoked");
  assert.notEqual(revoked.status,0,"withdrawn Topic membership aborts isolated SSR");
  assert.match(revoked.stdout+revoked.stderr,/MEMBERSHIP_STALE/);
  const drift=await build(approved,pins,{...pins,epochDrift:true},"epoch-race");
  assert.notEqual(drift.status,0,"late epoch change aborts SSR after HTML assembly");
  assert.match(drift.stdout+drift.stderr,/CURRENT_CHANGED/);
} finally {
  await rm(scratch,{recursive:true,force:true});
}
console.log("DP440 Python synopsis -> keyboard anchors and escaped private noindex Astro SSR PASS; rights/revocation/third-epoch negative PASS");
