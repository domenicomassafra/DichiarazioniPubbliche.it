/** Genuine Python approved opinion -> pinned private TS -> isolated Astro SSR. */
import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {createHash} from "node:crypto";
import {mkdtemp,mkdir,readFile,rm,symlink,writeFile} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {fileURLToPath} from "node:url";
import {canonicalJson} from "../src/lib/searchIndex.ts";
import {buildPublicStatementSearchV3} from "../src/lib/publicStatementSearchV3.ts";
import {readPrivateStatementOpinionV3} from "../src/lib/privateStatementOpinionPreviewV3.ts";

const root=fileURLToPath(new URL("../../",import.meta.url));
const web=fileURLToPath(new URL("../",import.meta.url));
const py=[
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
const built=spawnSync("python3",["-c",py],{cwd:root,encoding:"utf8",timeout:15000,
  env:{...process.env,PYTHONPATH:"poc:tests",PYTHONDONTWRITEBYTECODE:"1"}});
assert.equal(built.status,0,built.stderr);
const fixture=JSON.parse(built.stdout);
const index=await buildPublicStatementSearchV3(fixture.join,{
  personSha256:fixture.people.dataset_sha256,
  statementSha256:fixture.bundle.dataset_sha256,
  intersectionSha256:fixture.join.dataset_sha256,
});
const sha=v=>createHash("sha256").update(canonicalJson(v)).digest("hex");
const routes=fixture.people.people.map(p=>p.route).sort();
const pins={
  allowPrivatePersonPreview:true,allowPrivateStatementOpinion:true,
  releaseId:"fixture-release-1",epoch:1,personSha256:fixture.people.dataset_sha256,
  statementSha256:fixture.bundle.dataset_sha256,
  intersectionSha256:fixture.join.dataset_sha256,
  indexSha256:index.index_sha256,sourceGeneratedAt:fixture.bundle.generated_at,
  personSitemapSha256:sha(routes),validUntil:"2099-01-01T00:00:00Z",
};
const assets={people:fixture.people,join:fixture.join,index,source:fixture.bundle,
  sitemapPersonRoutes:routes};
const look=(person,statement,read=async()=>({...pins}),data=assets,expected=pins)=>
  readPrivateStatementOpinionV3(data,expected,read,person,statement);
const opinion=fixture.bundle.statements.find(s=>s.speech_act==="OPINION"&&s.endorsed&&s.finding_id===null);
assert.ok(opinion,"real Python approved opinion with nullable Finding");
const id=opinion.statement_id;
const good=await look(opinion.person_id,id);
assert.equal(good.status,"READY");
assert.equal(good.statement.findingId,null);
assert.equal(good.statement.assessment,null);
assert.equal(good.statement.speechAct,"OPINION");
assert.equal(good.statement.originalText,opinion.original_text);
assert.equal(good.statement.quoteSha256,opinion.quote_sha256);
assert.equal(good.statement.sourceSha256,opinion.source_sha256);
assert.equal(good.statement.sourceVersion,opinion.source_version);
assert.deepEqual(good.statement.locator,opinion.locator);
assert.equal(good.publicationAuthorized,false);
const missing=await look(opinion.person_id,"statement:removed");
assert.deepEqual(missing,await look("person:unknown",id));
assert.equal(missing.status,"UNAVAILABLE");
assert.doesNotMatch(JSON.stringify(missing),/person:unknown|removed|PRIVATE/);
await assert.rejects(look(opinion.person_id,id,async()=>({...pins,epoch:2})),/CURRENT_RELEASE_CHANGED/);
await assert.rejects(look(opinion.person_id,id,async()=>{throw Error("SECRET");}),/CURRENT_RELEASE_UNAVAILABLE/);
await assert.rejects(look(opinion.person_id,id,async()=>({...pins}),assets,
  {...pins,allowPrivateStatementOpinion:false}),/PIN_REQUIRED/);
let reads=0;
await assert.rejects(look(opinion.person_id,id,async()=>({...pins,epoch:++reads===1?1:2})),
  /CURRENT_RELEASE_CHANGED/);
assert.equal(reads,2,"revocation between independent CURRENT reads refuses");
const altered=structuredClone(assets);
altered.source.statements.find(s=>s.statement_id===id).original_text+=" tampered";
await assert.rejects(look(opinion.person_id,id,async()=>({...pins}),altered));
const safe=structuredClone(good);
assets.source.statements.find(s=>s.statement_id===id).original_text+=" changed after snapshot";
assert.deepEqual(good,safe,"detached read model cannot be mutated by old source");

const temp=await mkdtemp(join(tmpdir(),"dp437-private-opinion-"));
try {
  await mkdir(join(temp,"src","pages"),{recursive:true});
  await symlink(join(web,"node_modules"),join(temp,"node_modules"));
  await writeFile(join(temp,"package.json"),JSON.stringify({private:true,type:"module"}));
  await writeFile(join(temp,"astro.config.mjs"),
    "import {defineConfig} from 'astro/config';export default defineConfig({output:'static'});");
  const page=[
    "---",
    "const statement = "+JSON.stringify(good.statement)+";",
    "---",
    "<html><head><meta name=\"robots\" content=\"noindex,nofollow\" /></head>",
    "<body><h1>Anteprima privata opinione</h1><article>",
    "<blockquote data-finding={String(statement.findingId)}>{statement.originalText}</blockquote>",
    "<time datetime={statement.statementDate}>{statement.statementDate}</time>",
    "<p>{statement.sourceTitle}</p>",
    "</article></body></html>",
  ].join("\n");
  await writeFile(join(temp,"src","pages","index.astro"),page);
  const build=spawnSync(join(web,"node_modules",".bin","astro"),["build","--root",temp],
    {cwd:temp,encoding:"utf8",timeout:25000});
  assert.equal(build.status,0,build.stderr+"\n"+build.stdout);
  const html=await readFile(join(temp,"dist","index.html"),"utf8");
  assert.ok(html.includes("noindex,nofollow"));
  assert.ok(html.includes(good.statement.originalText));
  assert.ok(!html.includes("changed after snapshot"));
  assert.ok(html.includes("data-finding=\"null\""));
  assert.doesNotMatch(html,/provider secret|person score|FACTUALLY_FALSE/i);
} finally {
  await rm(temp,{recursive:true,force:true});
}
console.log("DP437 approved Python opinion -> pinned Statement -> isolated Astro SSR PASS; withdraw race refused");
