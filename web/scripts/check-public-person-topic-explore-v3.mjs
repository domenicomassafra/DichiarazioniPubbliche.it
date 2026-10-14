/** Genuine DP439 Python materializer -> pinned opt-in public Explore model.
 * Local fixture only; no public route, provider, rights grant or deployment.
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { buildPublicStatementSearchV3 } from "../src/lib/publicStatementSearchV3.ts";

const root = fileURLToPath(new URL("../../", import.meta.url));
const python = String.raw`
import json,copy
from dataclasses import replace
from test_dp439_person_topic_v3 import published,make,event
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
print(json.dumps({'people':people,'join':initial,'revoked':revoked,'none':none,'withdrawn':withdrawn,'withdrawn_people':withdrawn_people},ensure_ascii=False))
`;
const producer = spawnSync("python3", ["-c", python], {cwd:root, encoding:"utf8", timeout:15000,
  env:{...process.env,PYTHONPATH:"poc:tests",PYTHONDONTWRITEBYTECODE:"1"}});
assert.equal(producer.status,0,producer.stderr);
const fixture = JSON.parse(producer.stdout);
const indexOf = async join => buildPublicStatementSearchV3(join,{
  intersectionSha256:join.dataset_sha256,statementSha256:join.source_dataset_sha256,
  personSha256:join.person_dataset_sha256,
});
const index=await indexOf(fixture.join);
const pinsOf = (join, idx) => ({allowV3Preview:true,intersectionSha256:join.dataset_sha256,
  statementSha256:join.source_dataset_sha256,personSha256:join.person_dataset_sha256,
  indexSha256:idx.index_sha256,validUntil:"2099-10-11T00:00:00Z"});
const pins=pinsOf(fixture.join,index);
const input={people:fixture.people,join:fixture.join,index};
const {readPinnedPersonTopicExploreV3} = await import("../src/lib/publicPersonTopicExploreV3.ts");
const read=(assets=input,issued=pins,url="",pageSize=2)=>
  readPinnedPersonTopicExploreV3(assets,issued,url,{pageSize});

const first=await read(input,pins,"?persona=person%3AA&tema=topic%3Aeconomia",1);
assert.equal(first.status,"PREVIEW_READY");
assert.equal(first.publicationAuthorized,false);
assert.equal(first.providerCalls,0);
assert.equal(first.totalResults,2);
assert.equal(first.records.length,1);
assert.equal(first.records[0].statementId,"statement:2");
assert.equal(first.records[0].statementDate,"2026-10-02");
assert.equal(first.records[0].originalText,index.records.find(row=>row.statement_id==="statement:2").original.text);
assert.equal(first.records[0].originalWordingType,"VERBATIM_ORIGINAL");
assert.equal(first.records[0].findingId,null);
assert.equal(first.records[0].statementRoute,"/dichiarazioni/statement-2/");
assert.equal(first.records[0].sourceUrl.startsWith("https://"),true);
assert.equal(first.personOptions.length,2);
assert.equal(first.topicOptions.some(t=>t.id==="topic:economia"),true);
assert.equal(new Set(first.personOptions.map(p=>p.label)).size,first.personOptions.length,
  "two independently approved homonymous People must have distinguishable accessible labels");
assert.equal(new Set(first.topicOptions.map(t=>t.label)).size,first.topicOptions.length,
  "similar Topic labels without approved title must remain distinguishable by public route");
assert.equal(first.currentPerson?.id,"person:A");
assert.equal(first.currentTopic?.id,"topic:economia");
assert.equal(first.nextUrl.includes("pagina=2"),true);
const second=await read(input,pins,first.nextUrl,1);
assert.equal(second.records[0].statementId,"statement:1");
assert.equal(second.previousUrl.includes("pagina=1"),false);

const original=structuredClone(first.records);
fixture.join.data[0].original_text="PRIVATE UNREVIEWED TEXT AFTER RETURN";
assert.deepEqual(first.records,original);
assert.doesNotMatch(JSON.stringify(first),/PRIVATE UNREVIEWED/);
await assert.rejects(read(input,pins,"?persona=person%3AA&tema=topic%3Aeconomia"),/PUBLIC_V3_.*(?:TAMPER|STALE|MISMATCH|INVALID)/,
  "modified input must never match pinned source");

const pristineJoin=JSON.parse(producer.stdout).join;
const cleanInput={people:fixture.people,join:pristineJoin,index};
const unknown=await read(cleanInput,pins,"?persona=person%3Aprivate-unreviewed");
assert.equal(unknown.status,"NO_MATCH");
assert.equal(unknown.records.length,0);
assert.doesNotMatch(JSON.stringify(unknown),/person:private-unreviewed/);
await assert.rejects(read(cleanInput,pins,"?pagina=0"),/PUBLIC_V3_EXPLORE_URL_INVALID/);
await assert.rejects(read(cleanInput,pins,"?pagina=2&pagina=1"),/PUBLIC_V3_EXPLORE_URL_INVALID/);
await assert.rejects(read(cleanInput,pins,"?not-allowed=private"),/PUBLIC_V3_SEARCH_URL_INVALID/);
await assert.rejects(read(cleanInput,{...pins,allowV3Preview:false}),/PUBLIC_V3_RELEASE_OPT_IN_REQUIRED/);

const noneIndex=await indexOf(fixture.none);
const noMatch=await read({people:fixture.people,join:fixture.none,index:noneIndex},pinsOf(fixture.none,noneIndex));
assert.equal(noMatch.status,"EMPTY_PUBLIC_INTERSECTION");
assert.equal(noMatch.records.length,0);
const revokedIndex=await indexOf(fixture.revoked);
const afterRevoke=await read({people:fixture.people,join:fixture.revoked,index:revokedIndex},pinsOf(fixture.revoked,revokedIndex));
assert.equal(afterRevoke.totalResults,2);
await assert.rejects(read({people:fixture.people,join:fixture.revoked,index:revokedIndex},pins),/PUBLIC_.*(?:TAMPER|STALE|MISMATCH)/);

// Original signed assets stay approved, but expiry must be checked AGAIN
// after the last asynchronous digest and not only on entry.
{
  const initialNow=Date.now;const originalDigest=globalThis.crypto.subtle.digest;
  const start=initialNow();const expiry=start+5000;let clock=start;let count=0;
  try{
    Date.now=()=>clock;
    globalThis.crypto.subtle.digest=async function(algorithm,bytes){
      const result=await originalDigest.call(this,algorithm,bytes);
      if(++count===1) clock=expiry+1000;
      return result;
    };
    await assert.rejects(read(cleanInput,{...pins,validUntil:new Date(expiry).toISOString()}),
      /PUBLIC_V3_RELEASE_EXPIRED|PUBLIC_V3_EXPLORE_EXPIRED/);
    assert(count>=1);
  }finally{Date.now=initialNow;globalThis.crypto.subtle.digest=originalDigest;}
}
console.log("DP439_PUBLIC_EXPLORE_V3_PASS real Python pinned join, exact originals, URL paging, revoke, expiry, private filters");
