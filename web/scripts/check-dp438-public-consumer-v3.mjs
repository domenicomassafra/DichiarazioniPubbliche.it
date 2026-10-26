/** DP-438: public integration using the same pinned synthetic fixture. */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFile, writeFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { makeScratchDir } from "./lib/scratch.mjs";
import { data, pins, routes, web, sha } from "./check-private-person-empty-v3.mjs";

// Public static integration: the same independently pinned release drives
// Person pages, the search index, the sitemap and the API-facing JSON artifact.
const integration=await makeScratchDir("dp438-published-v3-");
try {
  const v2={
    schema_version:"dichiarazioni-pubbliche-public-v2",
    generated_at:"2026-10-11T00:00:00+00:00",
    dataset_sha256:sha({contents:[],dossiers:[],topics:[]}),
    dossier_count:0,omitted_count:0,dossiers:[],topics:[],contents:[],
    methodology:{aggregate_person_score:false},
  };
  const projectionPath=join(integration,"projection.json");
  const assetsPath=join(integration,"person-assets.json");
  const pinsPath=join(integration,"current-pins.json");
  await writeFile(projectionPath,JSON.stringify(v2));
  await writeFile(assetsPath,JSON.stringify(data));
  await writeFile(pinsPath,JSON.stringify({...pins,publicationAuthorized:true}));
  const full=spawnSync(join(web,"node_modules/.bin/astro"),["build","--outDir",join(integration,"dist")],{
    cwd:web,encoding:"utf8",timeout:180000,
    env:{...process.env,DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH:projectionPath,
      DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3:"1",
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_ASSETS_PATH:assetsPath,
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_PINS_PATH:pinsPath,
      DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION:"0"},
  });
  assert.equal(full.status,0,`DP438 public static build: ${full.stdout}\n${full.stderr}`);
  const built=name=>readFile(join(integration,"dist",name),"utf8");
  const zeroPage=await built("persone/persona-zero/index.html");
  assert.match(zeroPage,/Nessuna dichiarazione pubblicata per questa persona/);
  assert.match(zeroPage,/Alex Demo/);
  const opinionPage=await built("persone/persona-a/index.html");
  assert.match(opinionPage,/\/dichiarazioni\/statement-2\//);
  assert.match(opinionPage,/non ha un Finding fattuale pubblicato/);
  const statementPage=await built("dichiarazioni/statement-2/index.html");
  assert.match(statementPage,/non ha un Finding fattuale pubblicato/);
  assert.match(statementPage,/2026-10-02/);
  assert.match(statementPage,/https:\/\/example/);
  await assert.rejects(built("persone/persona-held/index.html"),/ENOENT/);
  const sitemap=await built("sitemap.xml");
  for(const route of routes) assert(sitemap.includes(route),`missing route ${route}`);
  assert(sitemap.includes("/dichiarazioni/statement-2/"));
  assert.doesNotMatch(sitemap,/persona-held/);
  const search=JSON.parse(await built("search-index.v1.json"));
  assert(search.records.some(row=>row.kind==="statement" && row.route==="/dichiarazioni/statement-2/"),"approved original Statement must be discoverable through public search");
  assert(search.records.some(row=>row.kind==="person" && row.route==="/persone/persona-zero/"));
  assert(search.records.some(row=>row.kind==="person" && row.route==="/persone/persona-a/"));
  assert.doesNotMatch(JSON.stringify(search),/Private Candidate|persona-held|person:held/);
  const api=JSON.parse(await built("public-people.v3.json"));
  assert.equal(api.dataset_sha256,pins.personSha256);
  assert(api.people.some(person=>person.slug==="persona-zero" && person.statements.length===0));
  assert.doesNotMatch(JSON.stringify(api),/Private Candidate|persona-held|person:held/);
  // End-to-end bridge: Python must read the exact JSON emitted by Astro, not
  // an independently reconstructed Python fixture that happens to be valid.
  const bridge=spawnSync("python3",["-c",`import json, os
import tempfile
from pathlib import Path
from tests.test_dp438_public_person import bundle
from dichiarazioni_pubbliche.public_api import dispatch
from dichiarazioni_pubbliche.public_person_v3_api import load_current_public_people_v3
people, sha = load_current_public_people_v3()
with tempfile.TemporaryDirectory() as scratch:
    projection = Path(scratch) / "v2.json"
    projection.write_text(json.dumps(bundle(v2=True)))
    response = dispatch("GET", "/api/v1/people", projection_path=projection)
assert response.status == 200, response.status
assert json.loads(response.body)["meta"]["person_dataset_sha256"] == sha
assert len(people) >= 2
print("Astro generated JSON -> Python API current pin PASS")`],{
    cwd:join(web,".."),encoding:"utf8",timeout:30000,
    env:{...process.env,PYTHONPATH:join(web,"..","poc"),DP438_PROJECTION:projectionPath,
      DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3:"1",
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_API_PATH:join(integration,"dist","public-people.v3.json"),
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_PINS_PATH:pinsPath},
  });
  assert.equal(bridge.status,0,`${bridge.stdout}\n${bridge.stderr}`);
  // A v3 release must never publish an unrelated v2 dossier, its Person
  // membership or old source pages via the same sitemap/search/home build.
  const mixed=spawnSync(join(web,"node_modules/.bin/astro"),["build","--outDir",join(integration,"mixed")],{
    cwd:web,encoding:"utf8",timeout:180000,
    env:{...process.env,DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH:join(web,"src","data","demo-projection.json"),
      DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3:"1",
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_ASSETS_PATH:assetsPath,
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_PINS_PATH:pinsPath,
      DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION:"1"},
  });
  assert.notEqual(mixed.status,0,"nonempty v2 dossier projection was published with independent v3 release");
  assert.match(mixed.stdout+"\n"+mixed.stderr,/DP438_LEGACY_PROJECTION_NOT_EMPTY/);

  // Withdraw the pin and ensure a new candidate build is refused.
  await writeFile(pinsPath,JSON.stringify({...pins,publicationAuthorized:false}));
  const denied=spawnSync(join(web,"node_modules/.bin/astro"),["build","--outDir",join(integration,"held")],{
    cwd:web,encoding:"utf8",timeout:180000,
    env:{...process.env,DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH:projectionPath,
      DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3:"1",
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_ASSETS_PATH:assetsPath,
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_PINS_PATH:pinsPath,
      DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION:"0"},
  });
  assert.notEqual(denied.status,0,"withdrawn identity release incorrectly produced public pages");
}finally{await rm(integration,{recursive:true,force:true});}
console.log("DP-438 public Person/Statement static pages, search, sitemap, API JSON, release withdrawal PASS");
