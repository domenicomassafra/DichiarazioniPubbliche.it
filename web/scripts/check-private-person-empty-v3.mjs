/** DP-438: synthetic Python provenance, private/isolated consumer only. */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { canonicalJson } from "../src/lib/searchIndex.ts";
import { makeScratchDir } from "./lib/scratch.mjs";
import { buildPublicStatementSearchV3 } from "../src/lib/publicStatementSearchV3.ts";
import { readPinnedPrivatePublicPersonV3 } from "../src/lib/privatePublicPersonEmptyV3.ts";

const repo = fileURLToPath(new URL("../../", import.meta.url));
const web = fileURLToPath(new URL("../", import.meta.url));
const py = String.raw`
import json,copy
from test_dp439_person_topic_v3 import published,make
from test_dp438_public_person import person,identity,role,role_review
from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256
source,bundle,_,roster,decisions=published()
zero=person('person:zero',slug='persona-zero',name='Alex Demo')
zero['disambiguator']='Ente zero'
hidden=person('person:held',slug='persona-held',name='Nome riservato')
roster=[*roster,zero,hidden]
roles=[
  {**role('role:prior',from_date='2020-01-01',to_date='2021-12-31'), 'person_id':'person:A'},
  {**role('role:current',from_date='2027-01-01',to_date=None), 'person_id':'person:A'},
  {**role('role:at',from_date='2026-09-01',to_date='2026-12-01'), 'person_id':'person:B'},
]
review=[role_review(row) for row in roles]
identities=[identity(row) for row in roster[:-1]]+[identity(hidden,status='HELD')]
def people_for(value, ids=identities):
  return build_public_people_v3(roster,ids,roles,review,public_bundle=value,
    current_public_dataset_sha256=value['dataset_sha256'],allow_public_person_v3=True)
people=people_for(bundle)
join=make(bundle,people,decisions)
no_topic_join=make(bundle,people,())
revoked_people=people_for(bundle,[*identities[:-2],identity(zero,status='REVOKED'),identities[-1]])
revoked_join=make(bundle,revoked_people,decisions)
source.subjects[1].gates['rights']['status']='REVOKED'
after=source.build()
after['topics']=copy.deepcopy(bundle['topics'])
after['dataset_sha256']=projection_dataset_sha256(after)
after_people=people_for(after)
from dataclasses import replace
after_join=make(after,after_people,tuple(replace(d,public_dataset_sha256=after['dataset_sha256']) for d in decisions))
print(json.dumps(dict(bundle=bundle,people=people,join=join,no_topic_join=no_topic_join,
  revoked_people=revoked_people,revoked_join=revoked_join,
  after_bundle=after,after_people=after_people,after_join=after_join),ensure_ascii=False))
`;
const generated=spawnSync("python3",["-c",py],{cwd:repo,encoding:"utf8",timeout:18000,
  env:{...process.env,PYTHONPATH:"poc:tests",PYTHONDONTWRITEBYTECODE:"1"}});
assert.equal(generated.status,0,generated.stderr);
const fixture=JSON.parse(generated.stdout);
const sha=value=>createHash("sha256").update(canonicalJson(value)).digest("hex");
const makeIndex=join=>buildPublicStatementSearchV3(join,{
  intersectionSha256:join.dataset_sha256,statementSha256:join.source_dataset_sha256,
  personSha256:join.person_dataset_sha256,
});
const index=await makeIndex(fixture.join);
const routes=fixture.people.people.map(p=>p.route).sort();
const pins={
  allowPrivatePersonPreview:true,
  personSha256:fixture.people.dataset_sha256,
  statementSha256:fixture.bundle.dataset_sha256,
  intersectionSha256:fixture.join.dataset_sha256,
  indexSha256:index.index_sha256,
  sourceGeneratedAt:fixture.bundle.generated_at,
  personSitemapSha256:sha(routes),
  validUntil:"2099-10-12T00:00:00Z",
};
const data={people:fixture.people,join:fixture.join,index,source:fixture.bundle,
  sitemapPersonRoutes:routes};
const run=(identifier,assets=data,p=pins)=>readPinnedPrivatePublicPersonV3(assets,p,identifier);

const empty=await run("person:zero");
assert.equal(empty.status,"APPROVED_EMPTY");
assert.equal(empty.person.route,"/persone/persona-zero/");
assert.equal(empty.person.displayName,"Alex Demo");
assert.equal(empty.person.disambiguator,"Ente zero");
assert.deepEqual(empty.statements,[]);
assert.equal(empty.publicationAuthorized,false);
assert.deepEqual(empty.sitemapPersonRoutes,routes);
assert.equal(empty.searchStatementCount,0);
assert.equal(empty.emptyState,"Nessuna dichiarazione pubblicata per questa persona");
const unknown=await run("person:unknown");
const privateOnly=await run("person:held");
const privateSlug=await run("persona-held");
assert.deepEqual(unknown,privateOnly);
assert.deepEqual(unknown,privateSlug);
assert.equal(unknown.status,"UNAVAILABLE");
assert.doesNotMatch(JSON.stringify(unknown),/person:held|Nome riservato|persona-held|person:unknown/);

const first=await run("person:A");
const second=await run("person:B");
assert.equal(first.status,"APPROVED_WITH_STATEMENTS");
assert.equal(second.status,"APPROVED_WITH_STATEMENTS");
assert.equal(first.person.displayName,second.person.displayName);
assert.notEqual(first.person.disambiguator,second.person.disambiguator);
assert.notEqual(first.person.route,second.person.route);
assert.deepEqual(first.statements.map(s=>s.statementId),["statement:2","statement:1"]);
assert.equal(first.statements[0].findingId,null);
assert.ok(first.statements[0].originalText);
assert.ok(first.statements[0].sourceUrl.startsWith("https://"));
assert.equal(first.statements[0].statementDate,"2026-10-02");
assert.equal(first.statements[0].statementRoute,"/dichiarazioni/statement-2/");
assert.equal(first.statements[0].quoteSha256,fixture.bundle.statements[1].quote_sha256);
assert.deepEqual(first.statements[0].locator,fixture.bundle.statements[1].locator);
assert.equal(first.statements[0].roleAtStatement,null,"future/current role cannot leak into past statement");
assert.equal(first.person.roles.length,2,"date-delimited role history can remain source-linked");
assert.equal(first.searchStatementCount,2);
assert.equal(second.searchStatementCount,1);
const copied=await run("person:A");
assert.deepEqual(first,copied);
const originalRole=data.people.people[0].roles[0].label;
data.people.people[0].roles[0].label="late changed private role";
assert.equal(first.person.roles.some(r=>r.label==="late changed private role"),false);
data.people.people[0].roles[0].label=originalRole;
const originalLocator=data.source.statements[0].locator.start_char;
data.source.statements[0].locator.start_char+=10;
assert.equal(first.statements[1].locator.start_char,originalLocator);
data.source.statements[0].locator.start_char=originalLocator;
const safeData=data;

// Regression: the private wrapper must NOT re-read mutable caller-owned
// Person fields after the sitemap digest has already authenticated the
// approved route set. The late digest hook runs before the final card is made.
const callerRace=structuredClone(safeData);
const raceDigestInput=canonicalJson(routes);
const subtle=globalThis.crypto.subtle;
const originalDigest=subtle.digest;
let injected=false;
try {
  subtle.digest=async function(algorithm,bytes){
    const hash=await originalDigest.call(this,algorithm,bytes);
    if(!injected && new TextDecoder().decode(bytes)===raceDigestInput){
      injected=true;
      const target=callerRace.people.people.find(p=>p.person_id==="person:zero");
      target.display_name="PRIVATE UNREVIEWED NAME";
      target.route="/persone/private-unreviewed-route/";
      target.disambiguator="PRIVATE UNREVIEWED ALIAS";
    }
    return hash;
  };
  const approvedRace=await run("person:zero",callerRace);
  assert(injected,"private Person post-sitemap digest race not exercised");
  assert.equal(approvedRace.status,"APPROVED_EMPTY");
  assert.equal(approvedRace.person.displayName,"Alex Demo",
    "late caller-owned name was presented as approved under earlier Person SHA");
  assert.equal(approvedRace.person.route,"/persone/persona-zero/");
  assert.doesNotMatch(JSON.stringify(approvedRace),/PRIVATE UNREVIEWED/);
}finally{subtle.digest=originalDigest;}

// The independently issued expiry may pass before the first digest yet
// expire after all nested readers, at the LAST sitemap SHA. Refuse success.
{
  const now=Date.now;
  const begin=now();
  const expiration=begin+5_000;
  let clock=begin;
  let hookSeen=false;
  try{
    Date.now=()=>clock;
    subtle.digest=async function(algorithm,bytes){
      const hash=await originalDigest.call(this,algorithm,bytes);
      if(!hookSeen && new TextDecoder().decode(bytes)===raceDigestInput){
        hookSeen=true;
        clock=expiration+1_000;
      }
      return hash;
    };
    await assert.rejects(run("person:zero",safeData,{
      ...pins,validUntil:new Date(expiration).toISOString(),
    }),/AUTHORITY_EXPIRED/,"private zero-Person returned after release expiry");
    assert(hookSeen,"private late sitemap expiry was not exercised");
  }finally{Date.now=now;subtle.digest=originalDigest;}
}

await assert.rejects(run("person:A",safeData,{...pins,allowPrivatePersonPreview:false}),/OPT_IN/);
await assert.rejects(run("person:A",safeData,{...pins,personSha256:"0".repeat(64)}),/STALE|PIN/);
await assert.rejects(run("person:A",safeData,{...pins,validUntil:"2000-01-01T00:00:00Z"}),/EXPIRED/);
const mutate=(fn)=>{const copy=structuredClone(safeData);fn(copy);return copy;};
for(const [label,fn] of [
  ["sitemap unknown route",d=>d.sitemapPersonRoutes.push("/persone/persona-held/")],
  ["sitemap omitted approved zero",d=>d.sitemapPersonRoutes=d.sitemapPersonRoutes.filter(r=>r!=="/persone/persona-zero/")],
  ["sitemap duplicate",d=>d.sitemapPersonRoutes.push(d.sitemapPersonRoutes[0])],
  ["split-brain Person source locator",d=>d.people.people.find(p=>p.person_id==="person:A").statements[0].locator.start_char++],
  ["private name into index",d=>d.index.records[0].person_name="Nome riservato"],
  ["source Statement wording changed",d=>d.source.statements[0].original_text="FORGED PRIVATE TEXT"],
  ["source Statement version changed",d=>d.source.statements[0].version_id="version:changed"],
  ["rights review revoked",d=>d.source.statements[0].review_provenance.rights=""],
  ["source timestamp modified outside hash",d=>d.source.generated_at="2026-10-01T00:00:00Z"],
  ["index stale topic membership",d=>d.index.records[0].topics=[]],
]) await assert.rejects(run("person:A",mutate(fn)),undefined,label);
// No Topic join is a valid public state. A separately rehashed malicious
// Person archive omitting an otherwise current published opinion must NOT
// be presented as a zero-record Person, even when all local hashes agree.
const missing=structuredClone(fixture.people);
missing.people.find(p=>p.person_id==="person:A").statements=[];
missing.dataset_sha256=sha(missing.people);
const noTopic=structuredClone(fixture.no_topic_join);
noTopic.person_dataset_sha256=missing.dataset_sha256;
const {dataset_sha256:_unbound,provider_calls:_calls,...noTopicBody}=noTopic;
noTopic.dataset_sha256=sha(noTopicBody);
const noTopicIndex=await makeIndex(noTopic);
const noTopicPins={...pins,personSha256:missing.dataset_sha256,
  intersectionSha256:noTopic.dataset_sha256,indexSha256:noTopicIndex.index_sha256};
await assert.rejects(run("person:A",{people:missing,join:noTopic,index:noTopicIndex,
  source:fixture.bundle,sitemapPersonRoutes:routes},noTopicPins),/SOURCE_REVISION_STALE/);
const removedIndex=await makeIndex(fixture.revoked_join);
const removedRoutes=fixture.revoked_people.people.map(p=>p.route).sort();
const revokedAssets={people:fixture.revoked_people,join:fixture.revoked_join,index:removedIndex,
  source:fixture.bundle,sitemapPersonRoutes:removedRoutes};
const revokedPins={...pins,personSha256:fixture.revoked_people.dataset_sha256,
  intersectionSha256:fixture.revoked_join.dataset_sha256,indexSha256:removedIndex.index_sha256,
  personSitemapSha256:sha(removedRoutes)};
assert.deepEqual(await run("person:zero",revokedAssets,revokedPins),await run("person:unknown",revokedAssets,revokedPins));
await assert.rejects(run("person:zero",revokedAssets,pins),/STALE/);
const afterIndex=await makeIndex(fixture.after_join);
const afterRoutes=fixture.after_people.people.map(p=>p.route).sort();
const afterAssets={people:fixture.after_people,join:fixture.after_join,index:afterIndex,
  source:fixture.after_bundle,sitemapPersonRoutes:afterRoutes};
const afterPins={...pins,personSha256:fixture.after_people.dataset_sha256,
  statementSha256:fixture.after_bundle.dataset_sha256,
  intersectionSha256:fixture.after_join.dataset_sha256,indexSha256:afterIndex.index_sha256,
  sourceGeneratedAt:fixture.after_bundle.generated_at,personSitemapSha256:sha(afterRoutes)};
assert.equal((await run("person:A",afterAssets,afterPins)).statements.length,1);
await assert.rejects(run("person:A",afterAssets,pins),/STALE/);

// Real isolated static Astro rendering, no public route created in repo.
const scratch=await makeScratchDir("dp438-zero-ssr-");
const modulePath=fileURLToPath(new URL("../src/lib/privatePublicPersonEmptyV3.ts",import.meta.url));
async function render(name,assets,issue,identifier){
  await writeFile(join(scratch,"artifacts.json"),JSON.stringify(assets));
  const page=["---",`import {readPinnedPrivatePublicPersonV3} from ${JSON.stringify(modulePath)};`,
    'import artifacts from "../../artifacts.json";',
    `const pins=${JSON.stringify(issue)};`,
    `const model=await readPinnedPrivatePublicPersonV3(artifacts,pins,${JSON.stringify(identifier)});`,
    "---",'<main data-private-person-v3>',
    '{model.person ? <><h1>{model.person.displayName}</h1><span data-disambiguator>{model.person.disambiguator}</span><a href={model.person.route}>Profilo</a><p>{model.emptyState}</p>{model.statements.map(s=><a href={s.statementRoute} data-date={s.statementDate} data-source={s.sourceUrl}>{s.originalText}</a>)}</> : <p>Risorsa non disponibile</p>}',
    "</main>"].join("\n");
  await writeFile(join(scratch,"src/pages/index.astro"),page);
  return spawnSync(join(web,"node_modules/.bin/astro"),
    ["build","--root",scratch,"--outDir",join(scratch,name)],{cwd:web,encoding:"utf8",timeout:120000});
}
try{
  await mkdir(join(scratch,"src/pages"),{recursive:true});
  await symlink(join(web,"node_modules"),join(scratch,"node_modules"),"dir");
  await writeFile(join(scratch,"astro.config.mjs"),'import {defineConfig} from "astro/config";export default defineConfig({output:"static"})');
  const approved={people:fixture.people,join:fixture.join,index,source:fixture.bundle,sitemapPersonRoutes:routes};
  const zeroSsr=await render("zero",approved,pins,"person:zero");
  assert.equal(zeroSsr.status,0,zeroSsr.stderr);
  const zeroHtml=await readFile(join(scratch,"zero/index.html"),"utf8");
  assert.match(zeroHtml,/Nessuna dichiarazione pubblicata per questa persona/);
  assert.match(zeroHtml,/\/persone\/persona-zero\//);
  assert.doesNotMatch(zeroHtml,/FORGED|Nome riservato|person:held|score|verdict|raw_transcript/);
  const opinionSsr=await render("opinion",approved,pins,"person:A");
  assert.equal(opinionSsr.status,0,opinionSsr.stderr);
  const opinionHtml=await readFile(join(scratch,"opinion/index.html"),"utf8");
  assert.match(opinionHtml,/\/dichiarazioni\/statement-2\//);
  assert.match(opinionHtml,/data-date="2026-10-02"/);
  assert.doesNotMatch(opinionHtml,/score|verdict|raw_transcript/);
  const privateSsr=await render("private",approved,pins,"person:held");
  assert.equal(privateSsr.status,0,privateSsr.stderr);
  const missingSsr=await render("missing",approved,pins,"person:missing");
  assert.equal(missingSsr.status,0,missingSsr.stderr);
  assert.equal(await readFile(join(scratch,"private/index.html"),"utf8"),
               await readFile(join(scratch,"missing/index.html"),"utf8"));
  assert.notEqual((await render("revoked-stale",revokedAssets,pins,"person:zero")).status,0);
  assert.notEqual((await render("expired",approved,{...pins,validUntil:"2000-01-01T00:00:00Z"},"person:zero")).status,0);
}finally{await rm(scratch,{recursive:true,force:true});}
console.log("DP-438 Python approved zero/opinion/held→TypeScript pinned Person/source/index/sitemap, isolated Astro SSR positive/negative PASS");
