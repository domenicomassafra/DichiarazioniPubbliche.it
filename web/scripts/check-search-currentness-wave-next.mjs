/** DP-409: pinned wire-byte identity, not just duplicate-tolerant parsed JSON. */
import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {readFile} from "node:fs/promises";
import {
  buildSearchIndexMaterial,
  canonicalJson,
  finalizeSearchIndex,
  readPinnedPublicSearch,
} from "../src/lib/searchIndex.ts";

const demo=JSON.parse(await readFile(new URL("../src/data/demo-projection.json",import.meta.url),"utf8"));
const hash=value=>createHash("sha256").update(canonicalJson(value),"utf8").digest("hex");
const withdrawn="Withdrawn demo-only original title MUST NOT remain in published wire bytes";
const allowed="Current demo-only approved finding still searchable";
const oldFinding=structuredClone(demo.dossiers[0]);
oldFinding.finding_id="finding:withdrawn-demo-409";
oldFinding.claim_id="claim:withdrawn-demo-409";
oldFinding.claim=withdrawn;
oldFinding.speaker.id="person:withdrawn-demo-409";
oldFinding.speaker.name="Withdrawn fictional person";
oldFinding.source.content_id="content:withdrawn-demo-409";
const currentFinding=structuredClone(demo.dossiers[0]);
currentFinding.finding_id="finding:approved-demo-409";
currentFinding.claim_id="claim:approved-demo-409";
currentFinding.claim=allowed;
currentFinding.speaker.id="person:approved-demo-409";
currentFinding.speaker.name="Approved fictional person";
currentFinding.source.content_id="content:approved-demo-409";

function projection(dossiers){
  const parts={dossiers,topics:[],contents:[]};
  return {
    schema_version:"dichiarazioni-pubbliche-public-v2",
    generated_at:"2026-10-12T09:00:00Z",
    dataset_sha256:hash(parts),
    dossier_count:dossiers.length,omitted_count:0,
    ...parts,
    methodology:{claim_level_only:true,aggregate_person_score:false},
  };
}
const old=await finalizeSearchIndex(buildSearchIndexMaterial(projection([oldFinding,currentFinding])));
const current=await finalizeSearchIndex(buildSearchIndexMaterial(projection([currentFinding])));
assert.notEqual(old.index_sha256,current.index_sha256);
assert.notEqual(old.projection_sha256,current.projection_sha256);
assert(old.records.some(record=>record.title===withdrawn));
assert(!current.records.some(record=>record.title===withdrawn));
const release={
  allowPinnedSearch:true,releaseId:"synthetic-current-409",epoch:41,
  projectionSha256:current.projection_sha256,
  indexSha256:current.index_sha256,
  generatedAt:current.generated_at,validUntil:"2026-10-14T00:00:00Z",
};
const options={now:()=>new Date("2026-10-12T12:00:00Z")};
let reads=0;
const read=(wire,q="")=>readPinnedPublicSearch(wire,async()=>{
  reads++;
  return {...release};
},q,{kind:"finding"},options);
const accepted=await read(canonicalJson(current)+"\n",allowed);
assert.equal(accepted.status,"OK");
assert.deepEqual(accepted.records.map(r=>r.id),["finding:approved-demo-409"]);
assert.equal(reads,2,"both independent issuer checks are still mandatory");

// Regression: JSON.parse takes the LAST duplicate field. Canonical hashing of
// that parsed object erases the FIRST field, which can contain a revoked result
// in the exact same bytes served to the public under an unchanged release ID,
// epoch, source SHA, index SHA and generated-at.
const goodWire=canonicalJson(current);
const withdrawnRecords=canonicalJson(old.records.filter(record=>record.title===withdrawn));
const ambiguousWire=goodWire.replace(
  '"records":', '"records":'+withdrawnRecords+',"records":',
);
assert.notEqual(ambiguousWire,goodWire);
assert(ambiguousWire.includes(withdrawn));
assert.deepEqual(JSON.parse(ambiguousWire),current,
  "effective parsed object is identical; ordinary parsed-object SHA does not see retired text");
await assert.rejects(read(ambiguousWire,allowed),/SEARCH_PINNED_INDEX_NONCANONICAL/,
  "duplicated top-level records must not ship retired bytes under current release pin");

// The same ambiguity in a nested result may expose withdrawn quotation text
// without changing any parsed result or independently pinned release digest.
const duplicateTitleWire=goodWire.replace('"title":'+JSON.stringify(allowed),
  '"title":'+JSON.stringify(withdrawn)+',"title":'+JSON.stringify(allowed));
assert(duplicateTitleWire.includes(withdrawn));
assert.deepEqual(JSON.parse(duplicateTitleWire),current);
await assert.rejects(read(duplicateTitleWire,allowed),/SEARCH_PINNED_INDEX_NONCANONICAL/,
  "duplicate nested result key must also refuse under the SAME current release");
assert.equal((await read(goodWire,allowed)).records[0].title,allowed);
console.log("DP409 current same-epoch canonical wire-byte guard PASS: authentic synthetic indexed assets accepted; duplicate records/title containing withdrawn text refused");
