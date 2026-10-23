/** DP437: the private SSR opinion must survive neither a release epoch change nor expiry. */
import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {createHash} from "node:crypto";
import {mkdir,readFile,rm,symlink,writeFile} from "node:fs/promises";
import {join} from "node:path";
import {fileURLToPath} from "node:url";
import {makeScratchDir} from "./lib/scratch.mjs";
import {canonicalJson} from "../src/lib/searchIndex.ts";
import {buildPublicStatementSearchV3} from "../src/lib/publicStatementSearchV3.ts";
import {readPrivateStatementOpinionV3} from "../src/lib/privateStatementOpinionPreviewV3.ts";

const root=fileURLToPath(new URL("../../",import.meta.url));
const web=fileURLToPath(new URL("../",import.meta.url));
const python=[
  "import json",
  "from test_dp439_person_topic_v3 import published,make",
  "from test_dp438_public_person import identity",
  "from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3",
  "source,bundle,_,roster,decisions=published()",
  "people=build_public_people_v3(roster,[identity(row) for row in roster],[],[],",
  "  public_bundle=bundle,current_public_dataset_sha256=bundle['dataset_sha256'],",
  "  allow_public_person_v3=True)",
  "join=make(bundle,people,decisions)",
  "print(json.dumps(dict(bundle=bundle,people=people,join=join),ensure_ascii=False))",
].join("\n");
const constructed=spawnSync("python3",["-c",python],{cwd:root,encoding:"utf8",
  timeout:15000,env:{...process.env,PYTHONPATH:"poc:tests",PYTHONDONTWRITEBYTECODE:"1"}});
assert.equal(constructed.status,0,constructed.stderr);
const fixture=JSON.parse(constructed.stdout);
const index=await buildPublicStatementSearchV3(fixture.join,{
  personSha256:fixture.people.dataset_sha256,
  statementSha256:fixture.bundle.dataset_sha256,
  intersectionSha256:fixture.join.dataset_sha256,
});
const routes=fixture.people.people.map(p=>p.route).sort();
const sha=value=>createHash("sha256").update(canonicalJson(value)).digest("hex");
const pins={
  allowPrivatePersonPreview:true,allowPrivateStatementOpinion:true,
  releaseId:"dp437-currentness-1",epoch:9,
  personSha256:fixture.people.dataset_sha256,
  statementSha256:fixture.bundle.dataset_sha256,
  intersectionSha256:fixture.join.dataset_sha256,
  indexSha256:index.index_sha256,sourceGeneratedAt:fixture.bundle.generated_at,
  personSitemapSha256:sha(routes),validUntil:"2099-01-01T00:00:00Z",
};
const artifacts={people:fixture.people,join:fixture.join,index,source:fixture.bundle,
  sitemapPersonRoutes:routes};
const approved=fixture.bundle.statements.find(s=>s.speech_act==="OPINION"&&s.endorsed&&s.finding_id===null);
assert.ok(approved,"approved, original Python opinion required");
const look=(release,read)=>readPrivateStatementOpinionV3(artifacts,release,read,
  approved.person_id,approved.statement_id);
const success=await look({...pins},async()=>({...pins}));
assert.equal(success.status,"READY");
assert.equal(success.statement.originalText,approved.original_text);

// An external release manager may reuse a mutable current-pins record. Once
// the call has begun, changing its epoch must revoke the OLD request even if
// the same JS object was supplied as the original expectation.
const shared={...pins};
let reads=0;
await assert.rejects(look(shared,async()=>{
  if (++reads===2) shared.epoch+=1;
  return {...shared};
}),/DP437_PRIVATE_CURRENT_RELEASE_CHANGED/);
assert.equal(reads,2);

// The pin can expire during a slow second independent authority read, with
// exactly the same release ID/hash/epoch. Clock is simulated deterministically.
const actualNow=Date.now;
let now=actualNow();
let expiryReads=0;
try {
  Date.now=()=>now;
  await assert.rejects(look({...pins},async()=>{
    if (++expiryReads===2) now=Date.parse(pins.validUntil)+1;
    return {...pins};
  }),/DP437_PRIVATE_CURRENT_RELEASE_EXPIRED/);
} finally {
  Date.now=actualNow;
}
assert.equal(expiryReads,2);

// The successful original excerpt is still generated into a real isolated
// Astro SSR page; rejected decisions do not create any Astro/public route.
const dir=await makeScratchDir("dp437-opinion-current-");
try {
  await mkdir(join(dir,"src","pages"),{recursive:true});
  await symlink(join(web,"node_modules"),join(dir,"node_modules"));
  await writeFile(join(dir,"package.json"),JSON.stringify({private:true,type:"module"}));
  await writeFile(join(dir,"astro.config.mjs"),
    "import {defineConfig} from 'astro/config';export default defineConfig({output:'static'});");
  const page=["---",`const statement=${JSON.stringify(success.statement)};`,"---",
    '<html><head><meta name="robots" content="noindex,nofollow" /></head>',
    '<body><blockquote data-finding={String(statement.findingId)}>{statement.originalText}</blockquote>',
    '<time datetime={statement.statementDate}>{statement.statementDate}</time>',
    '<a href={statement.sourceUrl}>{statement.sourceTitle}</a></body></html>',
  ].join("\n");
  await writeFile(join(dir,"src","pages","index.astro"),page);
  const build=spawnSync(join(web,"node_modules",".bin","astro"),["build","--root",dir],
    {cwd:dir,encoding:"utf8",timeout:25000});
  assert.equal(build.status,0,build.stderr+"\n"+build.stdout);
  const html=await readFile(join(dir,"dist","index.html"),"utf8");
  assert.ok(html.includes("noindex,nofollow"));
  assert.ok(html.includes(approved.original_text));
  assert.ok(html.includes("data-finding=\"null\""));
  assert.ok(html.includes(approved.source_title));
} finally {
  await rm(dir,{recursive:true,force:true});
}
console.log("DP437 private opinion currentness: epoch/expiry races refused; approved original Astro SSR PASS");
