import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  buildSearchIndexMaterial,
  canonicalJson,
  finalizeSearchIndex,
  validateSearchIndex,
} from "../src/lib/searchIndex.ts";


const projectionPath = process.argv[2];
if (!projectionPath) {
  throw new Error("usage: check-dp221-private-body-search.mjs <projection-index.json>");
}

const projection = JSON.parse(await readFile(projectionPath, "utf8"));
const material = buildSearchIndexMaterial(projection);
const index = await finalizeSearchIndex(material);
await validateSearchIndex(structuredClone(index), projection.dataset_sha256);

const encodedProjection = canonicalJson(projection);
const encodedIndex = canonicalJson(index);
const privateBodyMarkers = [
  "PRIVATE_SOURCE_OCCURRENCE_BODY_SENTINEL",
  "PRIVATE_PARAPHRASE_BODY_SENTINEL",
  "PRIVATE_SUMMARY_BODY_SENTINEL",
  "PRIVATE_TRANSLATION_BODY_SENTINEL",
];

for (const marker of privateBodyMarkers) {
  assert.equal(encodedProjection.includes(marker), false, `${marker} escaped projection`);
  assert.equal(encodedIndex.includes(marker), false, `${marker} escaped search index`);
}
assert.equal(
  index.records.some((record) => record.kind === "finding"),
  false,
  "omitted private-body dossiers must not become search records",
);

console.log("DP-221 private-body search boundary: PASS");
