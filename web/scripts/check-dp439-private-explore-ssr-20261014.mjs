/** DP439: real Python -> pinned TS preview -> isolated Astro document SSR.
 * Synthetic approvals only. Never creates a public route or publishes data.
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { makeScratchDir } from "./lib/scratch.mjs";
import { buildPublicStatementSearchV3 } from "../src/lib/publicStatementSearchV3.ts";
import { readPinnedPersonTopicExploreV3 } from "../src/lib/publicPersonTopicExploreV3.ts";

const repo = fileURLToPath(new URL("../../", import.meta.url));
const web = fileURLToPath(new URL("../", import.meta.url));
const component = fileURLToPath(new URL("../src/components/PrivatePersonTopicExploreV3.astro", import.meta.url));
const reader = fileURLToPath(new URL("../src/lib/publicPersonTopicExploreV3.ts", import.meta.url));
const python = String.raw`
import json,copy
from dataclasses import replace
from test_dp439_person_topic_v3 import published,make,event
from test_dp438_public_person import bundle as empty_bundle
from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256
source, public, people, roster, decisions = published()
joined = make(public, people, decisions)
injected = make(public, people, decisions, coverage_note='<img src=x onerror=alert(1)>')
empty = make(public, people, ())
revoked = make(public, people, (*decisions, event(public,0,'topic:economia',revision=2,status='REVOKED')))
source.subjects[1].gates['rights']['status']='REVOKED'
withdrawn_source=source.build()
withdrawn_source['topics']=copy.deepcopy(public['topics'])
withdrawn_source['dataset_sha256']=projection_dataset_sha256(withdrawn_source)
withdrawn_people=build_public_people_v3(roster,[],[],[],public_bundle=withdrawn_source,current_public_dataset_sha256=withdrawn_source['dataset_sha256'],allow_public_person_v3=True)
withdrawn=make(withdrawn_source,withdrawn_people,tuple(replace(row,public_dataset_sha256=withdrawn_source['dataset_sha256']) for row in decisions))
empty_source=empty_bundle()
empty_people=build_public_people_v3([],[],[],[],public_bundle=empty_source,current_public_dataset_sha256=empty_source['dataset_sha256'],allow_public_person_v3=True)
no_corpus=make(empty_source,empty_people,())
print(json.dumps({'people':people,'joined':joined,'injected':injected,'empty':empty,'revoked':revoked,'withdrawn':withdrawn,'withdrawn_people':withdrawn_people,'no_corpus':no_corpus,'empty_people':empty_people},ensure_ascii=False))
`;
const generated = spawnSync("python3", ["-c", python], {
  cwd: repo, encoding: "utf8", timeout: 15000,
  env: {...process.env, PYTHONPATH:"poc:tests", PYTHONDONTWRITEBYTECODE:"1"},
});
assert.equal(generated.status, 0, generated.stderr || generated.stdout);
const fixture = JSON.parse(generated.stdout);
const indexFor = joinData => buildPublicStatementSearchV3(joinData, {
  intersectionSha256:joinData.dataset_sha256,
  statementSha256:joinData.source_dataset_sha256,
  personSha256:joinData.person_dataset_sha256,
});
const index = await indexFor(fixture.joined);
const injectedIndex = await indexFor(fixture.injected);
const revokedIndex = await indexFor(fixture.revoked);
const emptyIndex = await indexFor(fixture.empty);
const noCorpusIndex = await indexFor(fixture.no_corpus);
const issued = (joinData, searchIndex) => ({
  allowV3Preview:true, intersectionSha256:joinData.dataset_sha256,
  statementSha256:joinData.source_dataset_sha256,
  personSha256:joinData.person_dataset_sha256,
  indexSha256:searchIndex.index_sha256, validUntil:"2099-10-11T00:00:00Z",
});
const pins = issued(fixture.joined, index);
const base = {people:fixture.people,join:fixture.joined,index};
const selected = "?persona=person%3AA&tema=topic%3Aeconomia";
const first = await readPinnedPersonTopicExploreV3(base,pins,selected,{pageSize:1});
assert.equal(first.status,"PREVIEW_READY");
assert.equal(first.records[0].statementId,"statement:2");
assert.equal(first.records[0].findingId,null);
assert.equal(first.records[0].originalWordingType,"VERBATIM_ORIGINAL");
assert.equal(first.records[0].quoteSha256,createHash("sha256").update(first.records[0].originalText).digest("hex"),
  "independently pinned exact original bytes/sha256 mismatch");
const second = await readPinnedPersonTopicExploreV3(base,pins,first.nextUrl,{pageSize:1});
assert.equal(second.records[0].statementId,"statement:1");
const unknown = await readPinnedPersonTopicExploreV3(base,pins,"?persona=person%3Aprivate-secret",{pageSize:1});
assert.equal(unknown.status,"NO_MATCH");
assert.doesNotMatch(JSON.stringify(unknown),/private-secret/);
const zero = await readPinnedPersonTopicExploreV3({people:fixture.people,join:fixture.empty,index:emptyIndex},
  issued(fixture.empty,emptyIndex),"",{pageSize:1});
assert.equal(zero.status,"EMPTY_PUBLIC_INTERSECTION");
const noCorpus = await readPinnedPersonTopicExploreV3({people:fixture.empty_people,join:fixture.no_corpus,index:noCorpusIndex},
  issued(fixture.no_corpus,noCorpusIndex),"",{pageSize:1});
assert.equal(noCorpus.status,"EMPTY_PUBLIC_CORPUS");
assert.deepEqual(noCorpus.personOptions,[]);
assert.deepEqual(noCorpus.topicOptions,[]);
await assert.rejects(readPinnedPersonTopicExploreV3(base,pins,"?pagina=501",{pageSize:1}),/URL_INVALID/);
await assert.rejects(readPinnedPersonTopicExploreV3(base,pins,selected,{pageSize:26}),/PAGE_SIZE_INVALID/);
const withdrawn = await readPinnedPersonTopicExploreV3({people:fixture.people,join:fixture.revoked,index:revokedIndex},
  issued(fixture.revoked,revokedIndex),selected,{pageSize:1});
assert.equal(withdrawn.totalResults,1);
await assert.rejects(readPinnedPersonTopicExploreV3({people:fixture.people,join:fixture.revoked,index:revokedIndex},
  pins,selected,{pageSize:1}),/PUBLIC_.*(?:STALE|TAMPER|MISMATCH)/);

const scratch = await makeScratchDir("dp439-private-explore-ssr-");
const astro = join(web,"node_modules/.bin/astro");
const configs = [
  {name:"first",input:base,pins,search:selected},
  {name:"second",input:base,pins,search:first.nextUrl},
  {name:"unknown",input:base,pins,search:"?persona=person%3Aprivate-secret"},
  {name:"zero",input:{people:fixture.people,join:fixture.empty,index:emptyIndex},pins:issued(fixture.empty,emptyIndex),search:""},
  {name:"no-corpus",input:{people:fixture.empty_people,join:fixture.no_corpus,index:noCorpusIndex},pins:issued(fixture.no_corpus,noCorpusIndex),search:""},
  {name:"revoked",input:{people:fixture.people,join:fixture.revoked,index:revokedIndex},pins:issued(fixture.revoked,revokedIndex),search:selected},
  {name:"xss",input:{people:fixture.people,join:fixture.injected,index:injectedIndex},
    pins:issued(fixture.injected,injectedIndex),search:selected},
];
async function materializePages(pages) {
  await mkdir(join(scratch,"src/pages"),{recursive:true});
  for (const config of pages) {
    const name=config.name;
    await writeFile(join(scratch,`${name}.json`),JSON.stringify(config.input));
    const page=[
      "---",
      `import Explore from ${JSON.stringify(component)};`,
      `import input from ${JSON.stringify(join(scratch,`${name}.json`))};`,
      `const pins=${JSON.stringify(config.pins)};`,
      ...(config.hostile ? [
        `import {readPinnedPersonTopicExploreV3} from ${JSON.stringify(reader)};`,
        `const preview=await readPinnedPersonTopicExploreV3(input,pins,${JSON.stringify(config.search)},{pageSize:1});`,
      ] : []),
      ...(config.hostile ? [config.hostile] : []),
      ...(config.mutateInput ? [config.mutateInput] : []),
      "---",
      `<Explore input={input} pins={pins} search=${JSON.stringify(config.search)} pageSize={1} allowPrivatePreview={true}${config.hostile ? " preview={preview}" : ""} />`,
    ].join("\n");
    await writeFile(join(scratch,`src/pages/${name}.astro`),page);
  }
}
function build(out) {
  return spawnSync(astro,["build","--root",scratch,"--outDir",join(scratch,out)],{
    cwd:web,encoding:"utf8",timeout:120000,
    env:{...process.env,ASTRO_TELEMETRY_DISABLED:"1"},
  });
}
try {
  await symlink(join(web,"node_modules"),join(scratch,"node_modules"),"dir");
  await writeFile(join(scratch,"astro.config.mjs"),
    'import {defineConfig} from "astro/config";export default defineConfig({output:"static"})');
  await materializePages(configs);
  const built=build("positive");
  assert.equal(built.status,0,`Astro positive: ${built.stdout}\n${built.stderr}`);
  const html=async name=>readFile(join(scratch,"positive",`${name}/index.html`),"utf8");
  const positive=await html("first");
  assert.match(positive,/<meta\s+name="robots"\s+content="noindex,nofollow,noarchive,nosnippet"/);
  assert.match(positive,/<head>[^]*?<meta\s+name="robots"/);
  assert.match(positive,/data-dp439-private-explore/);
  assert.match(positive,/data-source-original/);
  assert(positive.includes(first.records[0].originalText),"published quotation must preserve exact original wording");
  assert.match(positive,/data-statement-date="2026-10-02"/);
  assert.match(positive,/data-statement-id="statement:2"/);
  assert.match(positive,/\/dichiarazioni\/statement-2\//);
  assert.match(positive,/data-source-version/);
  assert.match(positive,/data-quote-sha256/);
  assert.match(positive,/data-source-locator/);
  assert.match(positive,/Sintesi non disponibile/);
  assert.match(positive,/Data della dichiarazione/);
  assert.match(positive,/Copertura/);
  assert.match(positive,/data-pager-next/);
  assert.match(positive,/person%3AA/);
  assert.match(positive,/topic%3Aeconomia/);
  assert.match(positive,/Ente A/);
  assert.match(positive,/temi\/economia/);
  assert.doesNotMatch(positive,/review_provenance|review:membership|private-secret|raw_transcript/);
  assert.doesNotMatch(positive,/<script\s+src=|<link\s+[^>]*https?:\/\//i);
  for (const tag of positive.match(/<a\b[^>]*>/g)??[]) {
    assert.match(tag,/\brel="[^"]*nofollow/,`preview link is not nofollow: ${tag}`);
  }
  const next=await html("second");
  assert.match(next,/data-pager-previous/);
  assert.match(next,/data-statement-id="statement:1"/);
  assert.doesNotMatch(next,/data-statement-id="statement:2"/);
  const empty=await html("zero");
  assert.match(empty,/data-empty-public-intersection/);
  assert.doesNotMatch(empty,/data-source-original/);
  const noCorpusHtml=await html("no-corpus");
  assert.match(noCorpusHtml,/data-empty-public-corpus/);
  assert.doesNotMatch(noCorpusHtml,/data-source-original|data-statement-id=/);
  const missing=await html("unknown");
  assert.match(missing,/data-no-match/);
  assert.doesNotMatch(missing,/private-secret|data-source-original/);
  const revoked=await html("revoked");
  assert.equal((revoked.match(/data-statement-id=/g)??[]).length,1);
  const xss=await html("xss");
  assert.match(xss,/&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(xss,/<img\s+src=x|<script>\s*alert\(1\)/);
  // The component is deliberately opt-in, independent of the page's pinned read.
  await rm(join(scratch,"src/pages"),{recursive:true});
  await materializePages([{name:"closed",input:base,pins,search:selected}]);
  const closedPath=join(scratch,"src/pages/closed.astro");
  const closed=(await readFile(closedPath,"utf8")).replace("allowPrivatePreview={true}","allowPrivatePreview={false}");
  await writeFile(closedPath,closed);
  const denied=build("denied");
  assert.notEqual(denied.status,0,"missing opt-in unexpectedly emitted static preview");
  // The SSR boundary must reject *every* legacy caller-supplied preview,
  // including mutations after an apparently successful SHA validation.
  for (const candidate of [
    {name:"hostile-quote",hostile:'preview.records[0].originalText="FORGED ORIGINAL UNDER OLD SHA";preview.records[0].sourceLocator.end_char=preview.records[0].sourceLocator.start_char+[...preview.records[0].originalText].length;'},
    {name:"hostile-roster",hostile:'preview.personOptions.push({id:"person:private-sentinel",route:"/persone/privato/",label:"PRIVATE SENTINEL"});'},
    {name:"hostile-combined",hostile:'preview.records[0].originalText="FORGED ORIGINAL UNDER OLD SHA";preview.records[0].sourceLocator.end_char=preview.records[0].sourceLocator.start_char+[...preview.records[0].originalText].length;preview.personOptions.push({id:"person:private-sentinel",route:"/persone/privato/",label:"PRIVATE SENTINEL"});'},
    {name:"hostile-current",hostile:'preview.currentUrl="?persona=person%3Aprivate-secret";preview.currentPerson=null;'},
    {name:"hostile-next",hostile:'preview.nextUrl="?persona=person%3Aprivate-secret&pagina=2";'},
    {name:"hostile-topic",hostile:'preview.currentUrl="?tema=topic%3Aprivate-secret";preview.currentPerson=null;preview.currentTopic=null;'},
    {name:"hostile-cross-scope",hostile:'preview.nextUrl="?persona=person%3AB&tema=topic%3Aeconomia&pagina=2";'},
    {name:"hostile-query-scope",hostile:'preview.nextUrl="?persona=person%3AA&tema=topic%3Aeconomia&q=private-search&pagina=2";'},
  ]) {
    await rm(join(scratch,"src/pages"),{recursive:true});
    await materializePages([{...candidate,input:base,pins,search:selected}]);
    const attack=build(candidate.name);
    assert.notEqual(attack.status,0,`forged mutable preview ${candidate.name} was rendered`);
    assert.match(`${attack.stdout}\n${attack.stderr}`,/DP439_PRIVATE_EXPLORE_MUTABLE_PREVIEW_FORBIDDEN/,
      `failure reason for ${candidate.name} was not the intended fail-closed legacy-preview boundary`);
  }
  // A fresh read INSIDE the component must reject any originally approved
  // release whose source/index/person bytes changed after pins were issued.
  // An expired issuer pin must likewise fail before a document is emitted.
  for (const candidate of [
    {name:"stale-original",mutateInput:'input.join.data[0].statement.original.text="FORGED AFTER PIN";'},
    {name:"stale-index",mutateInput:'input.index.records[0].original.text="FORGED INDEX TEXT";'},
    {name:"private-roster",mutateInput:'input.people.people.push({...input.people.people[0],person_id:"person:private-sentinel",slug:"privato",route:"/persone/privato/",display_name:"PRIVATE SENTINEL"});'},
    {name:"expired-issuer",pins:{...pins,validUntil:"2000-01-01T00:00:00Z"}},
  ]) {
    await rm(join(scratch,"src/pages"),{recursive:true});
    await materializePages([{input:base,pins,search:selected,...candidate}]);
    const attack=build(candidate.name);
    assert.notEqual(attack.status,0,`stale/unauthorized release ${candidate.name} incorrectly emitted HTML`);
    assert.match(`${attack.stdout}\n${attack.stderr}`,/PUBLIC_(?:V3|PERSON_V3)_.*(?:STALE|TAMPER|MISMATCH|EXPIRED|INVALID)/,
      `failure reason for ${candidate.name} was not invalidated release pins or original source`);
  }
} finally { await rm(scratch,{recursive:true,force:true}); }
console.log("DP439_PRIVATE_EXPLORE_SSR_PASS Python pinned Person×Topic -> Astro opt-in noindex, original/citation, facets, paging, XSS, zero/unknown/revoked");
