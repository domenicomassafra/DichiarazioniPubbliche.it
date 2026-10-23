/** Local DP-439 contract, genuine Python fixture; never an approval or public route. */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { canonicalJson } from "../src/lib/searchIndex.ts";
import { makeScratchDir } from "./lib/scratch.mjs";
import { buildPublicStatementSearchV3 } from "../src/lib/publicStatementSearchV3.ts";
import {
  parsePrivatePersonTopicUrl, serializePrivatePersonTopicUrl, readPrivatePersonTopicV3,
} from "../src/lib/privatePersonTopicV3.ts";

const root = fileURLToPath(new URL("../../", import.meta.url));
const web = fileURLToPath(new URL("../", import.meta.url));
const python = String.raw`
import json,copy
from dataclasses import replace
from test_dp439_person_topic_v3 import published,make,event,fixture
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256
from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3
from test_dp438_public_person import identity
source,bundle,people,roster,decisions=published()
initial=make(bundle,people,decisions)
revoked=make(bundle,people,(*decisions,event(bundle,0,'topic:economia',revision=2,status='REVOKED')))
none=make(bundle,people,())
source.subjects[1].gates['rights']['status']='REVOKED'
withdrawn_bundle=source.build()
withdrawn_bundle['topics']=copy.deepcopy(bundle['topics'])
withdrawn_bundle['dataset_sha256']=projection_dataset_sha256(withdrawn_bundle)
withdrawn_people=build_public_people_v3(roster,[identity(row) for row in roster],[],[],public_bundle=withdrawn_bundle,current_public_dataset_sha256=withdrawn_bundle['dataset_sha256'],allow_public_person_v3=True)
withdrawn=make(withdrawn_bundle,withdrawn_people,tuple(replace(row,public_dataset_sha256=withdrawn_bundle['dataset_sha256']) for row in decisions))
print(json.dumps({'join':initial,'bundle':bundle,'people':people,'revoked':revoked,'none':none,'withdrawn':withdrawn,'withdrawn_bundle':withdrawn_bundle,'withdrawn_people':withdrawn_people},ensure_ascii=False))
`;
const producer = spawnSync("python3", ["-c", python], { cwd: root, encoding: "utf8", timeout: 15000,
  env: { ...process.env, PYTHONPATH: "poc:tests", PYTHONDONTWRITEBYTECODE: "1" } });
assert.equal(producer.status, 0, `Python DP-439 fixture generation: ${producer.stderr}`);
const fixture = JSON.parse(producer.stdout);
const digest = (value) => createHash("sha256").update(canonicalJson(value)).digest("hex");
const sourcePins = (join, people, bundle, index) => ({
  allowPrivatePersonTopic: true,
  indexSha256: index.index_sha256,
  intersectionSha256: join.dataset_sha256,
  personSha256: people.dataset_sha256,
  statementSha256: bundle.dataset_sha256,
  generatedAt: bundle.generated_at,
  topicSha256ById: Object.fromEntries(bundle.topics.map(topic=>[topic.topic_id,digest(topic)])),
  validUntil: "2026-10-12T13:00:00Z",
});
const indexOf = async (join) => buildPublicStatementSearchV3(join, {
  intersectionSha256: join.dataset_sha256,
  statementSha256: join.source_dataset_sha256,
  personSha256: join.person_dataset_sha256,
});
const index = await indexOf(fixture.join);
const pins = sourcePins(fixture.join, fixture.people, fixture.bundle, index);
const input = { index, people: fixture.people, source: fixture.bundle };
const at = new Date("2026-10-11T14:00:01Z");
const state = {query:"",personId:"person:A",topicId:"topic:economia",sort:"recent",page:1};
const read = (value=input,pin=pins,url=serializePrivatePersonTopicUrl(state)) =>
  readPrivatePersonTopicV3(value,pin,url,{ now:at,pageSize:1 });

const first=await read();
assert.equal(first.status,"READY");
assert.equal(first.publicationAuthorized,false);
assert.equal(first.totalResults,2);
assert.equal(first.records.length,1);
assert.equal(first.records[0].statementId,"statement:2");
assert.equal(first.records[0].findingId,null);
assert.equal(first.records[0].personRoute,"/persone/persona-a/");
assert.equal(first.records[0].topicRoute,"/temi/economia/");
assert.equal(first.records[0].statementRoute,"/dichiarazioni/statement-2/");
assert.equal(first.records[0].quoteSha256,fixture.bundle.statements[1].quote_sha256);
assert.equal(first.records[0].sourceSha256,fixture.bundle.statements[1].source_sha256);
assert.deepEqual(first.records[0].locator,fixture.bundle.statements[1].locator);
assert.equal(first.records[0].statementDate,"2026-10-02");
assert.equal(first.coverageNote,fixture.join.coverage_note);
assert.equal(first.generatedAt,fixture.join.generated_at);
assert.equal(first.nextUrl.includes("pagina=2"),true);
const second=await read(input,pins,first.nextUrl);
assert.equal(second.records[0].statementId,"statement:1");
assert.equal(second.previousUrl,serializePrivatePersonTopicUrl(state));
assert.equal((await read(input,pins,second.previousUrl)).records[0].statementId,"statement:2");
const old=await read(input,pins,serializePrivatePersonTopicUrl({...state,sort:"old"}));
assert.equal(old.records[0].statementId,"statement:1");
const dated=await read(input,pins,serializePrivatePersonTopicUrl({...state,fromDate:"2026-10-02",toDate:"2026-10-02"}));
assert.deepEqual(dated.records.map(row=>row.statementId),["statement:2"]);
const sourced=await read(input,pins,serializePrivatePersonTopicUrl({...state,sourceId:first.records[0].sourceContentId}));
assert.deepEqual(sourced.records.map(row=>row.statementId),["statement:2"]);
const sameLabel=await read(input,pins,serializePrivatePersonTopicUrl({...state,topicId:"topic:economica"}));
assert.equal(sameLabel.totalResults,1);
assert.equal(sameLabel.records[0].statementId,"statement:2");
const unknown=await read(input,pins,serializePrivatePersonTopicUrl({...state,personId:"person:private"}));
const absent=await read(input,pins,serializePrivatePersonTopicUrl({...state,personId:"person:missing"}));
assert.deepEqual(unknown.records,absent.records);
assert.equal(unknown.status,"NO_MATCH");
assert.doesNotMatch(JSON.stringify(unknown),/person:private|person:missing/);
assert.equal((await read(input,pins,serializePrivatePersonTopicUrl({...state,topicId:null}))).totalResults,2);
const encoded=serializePrivatePersonTopicUrl({...state,query:"café & fonte",page:2});
assert.deepEqual(parsePrivatePersonTopicUrl("?"+encoded),{...state,query:"café & fonte",page:2});
for(const bad of ["?persona=person:A&persona=person:B","?tema=%00","?pagina=0","?pagina=-1","?pagina=01","?pagina=999999999999999","?ordine=trust","?private=1"]){
  assert.throws(()=>parsePrivatePersonTopicUrl(bad),/URL_INVALID/);
}
for(const bad of ["?dal=2026-13-01","?dal=2026-10-03&al=2026-10-01","?fonte=%2Fsecret","?pagina=2&pagina=1"]){
  assert.throws(()=>parsePrivatePersonTopicUrl(bad),/URL_INVALID/);
}
const failed=async(name,data=input,pin=pins,url=serializePrivatePersonTopicUrl(state),reason)=>{
  await assert.rejects(()=>read(data,pin,url),reason, name);
};
await failed("must opt in",input,{...pins,allowPrivatePersonTopic:false},undefined,/OPT_IN/);
await failed("needs independent index pin",input,{...pins,indexSha256:"0".repeat(64)},undefined,/STALE/);
await failed("expired authority",input,{...pins,validUntil:"2026-10-11T14:00:00Z"},undefined,/EXPIRED/);
await failed("revoked release",input,{...pins,statementSha256:fixture.withdrawn_bundle.dataset_sha256},undefined,/STALE/);
const mut=(fn)=>{const x=structuredClone(input);fn(x);return x;};
await failed("source date mutation",mut(x=>{x.source.statements[0].statement_date="2025-01-01";}),pins,undefined,/STALE|SOURCE/);
await failed("source hash mutation",mut(x=>{x.source.statements[0].source_sha256="f".repeat(64);}),pins,undefined,/STALE|SOURCE/);
await failed("source version mutation",mut(x=>{x.source.statements[0].version_id="version:old";}),pins,undefined,/STALE|SOURCE/);
await failed("locator mutation",mut(x=>{x.source.statements[0].locator.start_char+=2;}),pins,undefined,/STALE|SOURCE/);
await failed("rights withdrawal",mut(x=>{x.source.statements[0].review_provenance.rights="";}),pins,undefined,/STALE|SOURCE/);
await failed("no rehashed index forgery",mut(x=>{x.index.records[0].topics[0].topic_id="topic:private";}),pins,undefined,/TAMPER|STALE/);
await failed("person alias source revision",mut(x=>{x.people.people[0].statements[0].source_version="source:forged";}),pins,undefined,/PERSON|STALE/);
await failed("independent Topic version changed",mut(x=>{x.source.topics[0].entity_version="topic-version:forged";}),pins,undefined,/STALE|SOURCE|TOPIC/);
await failed("source timestamp outside collection digest",mut(x=>{x.source.generated_at="2026-10-10T00:00:00Z";}),pins,undefined,/STALE|SOURCE/);
const rebuiltRevoked=await indexOf(fixture.revoked);
const revokedPins=sourcePins(fixture.revoked,fixture.people,fixture.bundle,rebuiltRevoked);
const revokedInput={index:rebuiltRevoked,people:fixture.people,source:fixture.bundle};
assert.equal((await read(revokedInput,revokedPins)).totalResults,1);
await failed("old pinned index after membership revocation",revokedInput,pins,undefined,/STALE/);
const rebuiltWithdrawn=await indexOf(fixture.withdrawn);
const withdrawnPins=sourcePins(fixture.withdrawn,fixture.withdrawn_people,fixture.withdrawn_bundle,rebuiltWithdrawn);
const withdrawnInput={index:rebuiltWithdrawn,people:fixture.withdrawn_people,source:fixture.withdrawn_bundle};
assert.equal((await read(withdrawnInput,withdrawnPins)).totalResults,1);
await failed("old pinned index after rights withdrawal",withdrawnInput,pins,undefined,/STALE/);
const noJoin=await indexOf(fixture.none);
const noPins=sourcePins(fixture.none,fixture.people,fixture.bundle,noJoin);
assert.equal((await read({index:noJoin,people:fixture.people,source:fixture.bundle},noPins)).status,"EMPTY_PUBLIC_INTERSECTION");
const frozen=await read();
const late=structuredClone(input);
late.index.records[0].original.locator.start_char=987;
assert.notEqual(frozen.records[0].locator.start_char,987);

// Isolated Astro static SSR integration: no project route or publish approval.
const scratch=await makeScratchDir("dp439-private-ssr-");
const modulePath=fileURLToPath(new URL("../src/lib/privatePersonTopicV3.ts",import.meta.url));
async function build(release,token,out){
  const page=["---",`import {readPrivatePersonTopicV3} from ${JSON.stringify(modulePath)};`,
    'import data from "../../source.json";',`const pins=${JSON.stringify(token)};`,
    `const view=await readPrivatePersonTopicV3(data,pins,${JSON.stringify(serializePrivatePersonTopicUrl(state))},{now:new Date("2026-10-11T14:00:01Z"),pageSize:1});`,
    "---",'<main data-private-person-topic><p data-coverage>{view.coverageNote}</p>',
    '{view.records.map(row=><article><a href={row.statementRoute} data-source={row.sourceUrl} data-date={row.statementDate} data-version={row.versionId} data-start={row.locator.start_char}>{row.originalText}</a></article>)}',
    '</main>'].join("\n");
  await writeFile(join(scratch,"source.json"),JSON.stringify(release));
  await writeFile(join(scratch,"src/pages/index.astro"),page);
  return spawnSync(join(web,"node_modules/.bin/astro"),["build","--root",scratch,"--outDir",join(scratch,out)],{cwd:web,encoding:"utf8",timeout:120000});
}
try{
  await mkdir(join(scratch,"src/pages"),{recursive:true});
  await symlink(join(web,"node_modules"),join(scratch,"node_modules"),"dir");
  await writeFile(join(scratch,"astro.config.mjs"),'import {defineConfig} from "astro/config";export default defineConfig({output:"static"})');
  const approved={index,people:fixture.people,source:fixture.bundle};
  const positive=await build(approved,pins,"approved");
  assert.equal(positive.status,0,`SSR positive: ${positive.stdout}\n${positive.stderr}`);
  const html=await readFile(join(scratch,"approved/index.html"),"utf8");
  assert.match(html,/data-private-person-topic/);
  assert.match(html,/\/dichiarazioni\/statement-2\//);
  assert.match(html,/data-version="statement-version:2"/);
  assert.doesNotMatch(html,/review_provenance|review:membership|person:private|raw_transcript/);
  assert.notEqual((await build(approved,{...pins,validUntil:"2026-10-11T14:00:00Z"},"expired")).status,0);
  assert.notEqual((await build(withdrawnInput,pins,"withdrawn")).status,0);
} finally { await rm(scratch,{recursive:true,force:true}); }
console.log("DP-439 genuine Python→TS pinned index/Person/Topic/source intersection, query history, rights/revocation and isolated Astro SSR PASS");
