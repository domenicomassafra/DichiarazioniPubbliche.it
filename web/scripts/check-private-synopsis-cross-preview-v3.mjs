/** DP-440: real Python-v3 fixture -> independently pinned cross-reader -> isolated SSR. */
import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {createHash} from "node:crypto";
import {mkdir,readFile,rm,symlink,writeFile} from "node:fs/promises";
import {join} from "node:path";
import {fileURLToPath} from "node:url";
import {makeScratchDir} from "./lib/scratch.mjs";
import {canonicalJson} from "../src/lib/searchIndex.ts";
import {buildPublicStatementSearchV3} from "../src/lib/publicStatementSearchV3.ts";
import {readPrivateSynopsisCrossPreviewV3} from "../src/lib/privateSynopsisCrossPreviewV3.ts";

const root=fileURLToPath(new URL("../../",import.meta.url));
const web=fileURLToPath(new URL("../",import.meta.url));
const pythonCode=[
  "import json",
  "from dataclasses import asdict,replace",
  "from datetime import datetime,timezone,timedelta",
  "from test_dp439_person_topic_v3 import fixture,make,event",
  "from test_dp438_public_person import identity",
  "from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3",
  "from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256",
  "from dichiarazioni_pubbliche.public_synopsis_v3 import ApprovedTopicIntersection,ReviewedSynopsisSentence,prepare_public_synopsis",
  "_,b,_,roster=fixture()",
  "# Two distinct synthetic originals; a mirrored source SHA is ineligible.",
  "b['statements'][1]['source_sha256']='a'*64",
  "b['dataset_sha256']=projection_dataset_sha256(b)",
  "people=build_public_people_v3(roster,[identity(p) for p in roster],[],[],public_bundle=b,current_public_dataset_sha256=b['dataset_sha256'],allow_public_person_v3=True)",
  "decisions=tuple(event(b,i,'topic:economia') for i in (0,1,2))",
  "joined=make(b,people,decisions)",
  "revoked=make(b,people,(*decisions,event(b,0,'topic:economia',revision=2,status='REVOKED')))",
  "now=datetime.now(timezone.utc)",
  "keys=tuple((s['statement_id'],s['version_id']) for s in b['statements'][:2])",
  "att=ApprovedTopicIntersection(person_id='person:A',topic_id='topic:economia',dataset_sha256=b['dataset_sha256'],statement_versions=keys,statement_lineages=tuple((*key,'original-lineage:'+str(i)) for i,key in enumerate(keys)),review_event_id='review:topic:independent',status='APPROVED',currentness_attestation_id='attested:independent',currentness_attested_at=now.isoformat(),currentness_valid_until=(now+timedelta(hours=2)).isoformat())",
  "sentences=tuple(ReviewedSynopsisSentence(text='Nel corpus raccolto appare una posizione datata con copertura delimitata.',source_statement_versions=(key,),source_quote_sha256=(b['statements'][i]['quote_sha256'],),review_event_id='review:summary:'+str(i),kind='REVIEWED_DESCRIPTIVE_SUMMARY') for i,key in enumerate(keys))",
  "args=dict(bundle=b,intersection=att,reviewed_sentences=sentences,current_public_dataset_sha256=b['dataset_sha256'],coverage_note='Nel corpus raccolto, copertura incompleta delle fonti e della cronologia.',now=now)",
  "ready=prepare_public_synopsis(**args)",
  "withheld=prepare_public_synopsis(**{**args,'intersection':replace(att,status='REVOKED')})",
  "print(json.dumps(dict(source=b,people=people,join=joined,revoked_join=revoked,synopsis=asdict(ready),withheld=asdict(withheld)),ensure_ascii=False))",
].join("\n");
const processResult=spawnSync("python3",["-c",pythonCode],{
  cwd:root,encoding:"utf8",timeout:20000,
  env:{...process.env,PYTHONPATH:"poc:tests",PYTHONDONTWRITEBYTECODE:"1"},
});
assert.equal(processResult.status,0,processResult.stderr);
const fixture=JSON.parse(processResult.stdout);
const {source,people,join:intersection,revoked_join:revokedJoin,synopsis,withheld}=fixture;
assert.equal(synopsis.status,"READY_READ_MODEL");
assert.equal(withheld.status,"WITHHELD");
assert.equal(intersection.status,"READY");
const index=await buildPublicStatementSearchV3(intersection,{
  personSha256:people.dataset_sha256,statementSha256:source.dataset_sha256,
  intersectionSha256:intersection.dataset_sha256,
});
const sourceSha=value=>createHash("sha256").update(canonicalJson(value)).digest("hex");
const routes=people.people.map(p=>p.route).sort();
const pins={
  allowPrivateSynopsisCrossPreview:true,allowPrivatePersonPreview:true,
  allowSynopsisV3:true,releaseId:"synthetic-release-1",epoch:42,
  personSha256:people.dataset_sha256,statementSha256:source.dataset_sha256,
  intersectionSha256:intersection.dataset_sha256,indexSha256:index.index_sha256,
  sourceGeneratedAt:source.generated_at,personSitemapSha256:sourceSha(routes),
  validUntil:new Date(Date.now()+3600_000).toISOString(),
  synopsisSha256:sourceSha(synopsis),synopsisFingerprint:synopsis.fingerprint,
  publicDatasetSha256:source.dataset_sha256,publicGeneratedAt:source.generated_at,
  personId:synopsis.person_id,topicId:synopsis.topic_id,
};
const artifacts={people,join:intersection,index,source,synopsis,sitemapPersonRoutes:routes};
const read=(asset=artifacts,expected=pins,current=async()=>({...expected}))=>
  readPrivateSynopsisCrossPreviewV3(asset,expected,current);
const positive=await read();
assert.equal(positive.status,"PRIVATE_PINNED_SYNOPSIS_PREVIEW");
assert.equal(positive.publicationAuthorized,false);
assert.equal(positive.providerCalls,0);
assert.equal(positive.sentences.length,2);
assert.equal(positive.person.personId,"person:A");
assert.equal(positive.person.route,"/persone/persona-a/");
assert.equal(positive.topic.topicId,"topic:economia");
assert.equal(positive.topic.route,"/temi/economia/");
for(let i=0;i<2;i++){
  const citation=positive.sentences[i].citations[0];
  const original=source.statements[i];
  assert.equal(citation.statementId,original.statement_id);
  assert.equal(citation.versionId,original.version_id);
  assert.equal(citation.originalText,original.original_text);
  assert.equal(citation.quoteSha256,original.quote_sha256);
  assert.equal(citation.sourceSha256,original.source_sha256);
  assert.equal(citation.sourceVersion,original.source_version);
  assert.equal(citation.statementDate,original.statement_date);
  assert.deepEqual(citation.locator,original.locator);
  assert.equal(citation.speechAct,"OPINION");
  assert.equal(citation.endorsed,true);
  assert.equal(citation.findingId,null);
  assert.equal(citation.statementRoute,`/dichiarazioni/statement-${i+1}/`);
  assert.notEqual(positive.sentences[i].text,citation.originalText);
}
assert.ok(!JSON.stringify(positive).includes("review_provenance"));
assert.ok(!JSON.stringify(positive).includes("review:summary"));
assert.deepEqual(positive,await read());

async function reject(label,patchAssets,patchPins,expression=/DP440_PRIVATE_|PUBLIC_/){
  const next=structuredClone(artifacts);
  const expected=structuredClone(pins);
  patchAssets?.(next);
  patchPins?.(expected);
  await assert.rejects(read(next,expected),expression,label);
}
await reject("opt-in absent",null,p=>{p.allowPrivateSynopsisCrossPreview=false;},/OPT_IN/);
await reject("scope Person mismatch",null,p=>{p.personId="person:B";},/SCOPE/);
await assert.rejects(read(artifacts,{...pins,epoch:43},async()=>({...pins})),
  /CURRENT_RELEASE_CHANGED/,"independent current issuer disagrees with expected epoch");
await reject("citation quote changed",a=>{a.source.statements[0].original_text+=" una modifica";},null,/SOURCE|STALE/);
await reject("source locator drift",a=>{a.source.statements[0].locator.start_char++;},null,/SOURCE|STALE/);
await reject("rights revoked",a=>{a.source.statements[0].review_provenance.rights="";},null,/SOURCE|STALE/);
await reject("source snapshot timestamp changed",a=>{a.source.generated_at="2026-10-01T00:00:00Z";},null,/SOURCE|STALE/);
await reject("future synopsis",a=>{a.synopsis.snapshot_at="2099-10-01T00:00:00Z";},null,/PIN|STALE/);
await reject("private leaked field even if rehashed",a=>{a.synopsis.private_review="SECRET";},
  p=>{p.synopsisSha256=sourceSha({...synopsis,private_review:"SECRET"});},/SCHEMA/);
await assert.rejects(read({...artifacts,synopsis:withheld}),/WITHHELD/);
await assert.rejects(read(artifacts,{...pins,validUntil:"2000-01-01T00:00:00Z"}),/EXPIRED/);

// One reviewer can revoke a Topic membership while all source bytes and the
// synopsis DTO stay unchanged. A freshly pinned join/index must still reject it.
const revokedIndex=await buildPublicStatementSearchV3(revokedJoin,{
  personSha256:people.dataset_sha256,statementSha256:source.dataset_sha256,
  intersectionSha256:revokedJoin.dataset_sha256,
});
await assert.rejects(read({...artifacts,join:revokedJoin,index:revokedIndex},{
  ...pins,intersectionSha256:revokedJoin.dataset_sha256,indexSha256:revokedIndex.index_sha256,
}),/MEMBERSHIP_STALE/);

let readCount=0;
await assert.rejects(read(artifacts,pins,async()=>{
  readCount++;
  return {...pins,epoch:readCount===1?42:43};
}),/CURRENT_RELEASE_CHANGED/);
assert.equal(readCount,2,"second independent current-pin read gates SSR response");
await assert.rejects(read(artifacts,pins,async()=>{throw Error("PRIVATE AUTH ERROR");}),
  /CURRENT_RELEASE_UNAVAILABLE/);
const detached=structuredClone(positive);
const approvedAssets=structuredClone(artifacts);
artifacts.source.statements[0].original_text+=" mutated after read";
assert.deepEqual(positive,detached,"read output detaches from source mutation");

const temporary=await makeScratchDir("dp440-private-cross-preview-");
try {
  await mkdir(join(temporary,"src/pages"),{recursive:true});
  await symlink(join(web,"node_modules"),join(temporary,"node_modules"));
  await writeFile(join(temporary,"package.json"),JSON.stringify({private:true,type:"module"}));
  await writeFile(join(temporary,"astro.config.mjs"),
    "import {defineConfig} from 'astro/config';export default defineConfig({output:'static'});");
  const modulePath=fileURLToPath(new URL("../src/lib/privateSynopsisCrossPreviewV3.ts",import.meta.url));
  const page=[
    "---",
    `import {readPrivateSynopsisCrossPreviewV3} from ${JSON.stringify(modulePath)};`,
    'import assets from "../../assets.json";',
    'import expected from "../../pins.json";',
    'import current from "../../current.json";',
    "let reads=0;",
    "const {epochDrift=false,...currentPins}=current;",
    "const view=await readPrivateSynopsisCrossPreviewV3(assets,expected,async()=>",
    "  ({...currentPins,epoch:currentPins.epoch + (epochDrift && ++reads===2 ? 1 : 0)}));",
    "---",
    '<html><head><meta name="robots" content="noindex,nofollow" /></head><body>',
    '<main data-private-synopsis-preview>',
    '<h1>{view.person.displayName} — {view.topic.topicId}</h1>',
    '<p data-coverage>{view.coverageNote}</p>',
    '{view.sentences.map(sentence => <article><p data-synopsis>{sentence.text}</p>',
    '{sentence.citations.map(c => <figure><blockquote data-original>{c.originalText}</blockquote>',
    '<figcaption><time datetime={c.statementDate}>{c.statementDate}</time>',
    '<a href={c.statementRoute} data-quote-sha={c.quoteSha256} data-source-version={c.sourceVersion} data-start={c.locator.start_char}>Fonte originale</a>',
    '</figcaption></figure>)}</article>)}',
    '</main></body></html>',
  ].join("\n");
  await writeFile(join(temporary,"src/pages/index.astro"),page);
  async function buildSsr(assets,expected,current,outDir){
    await writeFile(join(temporary,"assets.json"),JSON.stringify(assets));
    await writeFile(join(temporary,"pins.json"),JSON.stringify(expected));
    await writeFile(join(temporary,"current.json"),JSON.stringify(current));
    return spawnSync(join(web,"node_modules/.bin/astro"),
      ["build","--root",temporary,"--outDir",join(temporary,outDir)],{
        cwd:temporary,encoding:"utf8",timeout:35000,
      });
  }
  const rendered=await buildSsr(approvedAssets,pins,pins,"approved");
  assert.equal(rendered.status,0,rendered.stdout+"\n"+rendered.stderr);
  const html=await readFile(join(temporary,"approved/index.html"),"utf8");
  assert.match(html,/data-private-synopsis-preview/);
  assert.match(html,/noindex,nofollow/);
  assert.match(html,/data-synopsis/);
  assert.match(html,/data-original/);
  assert.match(html,/href="\/dichiarazioni\/statement-1\/"/);
  assert.ok(html.includes(source.statements[0].original_text.replace(" mutated after read","")));
  assert.doesNotMatch(html,/PRIVATE AUTH ERROR|review_provenance|private_review|SECRET|raw_transcript/);
  const revokedAssets={...approvedAssets,join:revokedJoin,index:revokedIndex};
  const revokedPins={...pins,intersectionSha256:revokedJoin.dataset_sha256,
    indexSha256:revokedIndex.index_sha256};
  const revokedSsr=await buildSsr(revokedAssets,revokedPins,revokedPins,"revoked");
  assert.notEqual(revokedSsr.status,0,"revoked Topic membership must abort even fresh SSR build");
  assert.match(revokedSsr.stdout+revokedSsr.stderr,/MEMBERSHIP_STALE/);
  const epochSsr=await buildSsr(approvedAssets,pins,{...pins,epochDrift:true},"epoch-race");
  assert.notEqual(epochSsr.status,0,"epoch drift during SSR must abort");
  assert.match(epochSsr.stdout+epochSsr.stderr,/CURRENT_RELEASE_CHANGED/);
} finally {
  await rm(temporary,{recursive:true,force:true});
}
console.log("DP440 Python v3 -> independent synopsis/Person/Topic/source pins -> private Astro SSR PASS; revoke/epoch/rights negatives PASS");
