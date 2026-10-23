/** DP-409: isolated authentic Astro old/new static build + stale mixed-release proof. */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { makeScratchDir } from "./lib/scratch.mjs";
import {
  buildSearchIndexMaterial,
  canonicalJson,
  finalizeSearchIndex,
  readPinnedPublicSearch,
  searchPublicIndex,
  validateSearchIndex,
} from "../src/lib/searchIndex.ts";

const root = fileURLToPath(new URL("../", import.meta.url));
const scratch = await makeScratchDir("dp409-withdrawal-build-");
const demo = JSON.parse(await readFile(new URL("../src/data/demo-projection.json", import.meta.url), "utf8"));
const sha = value => createHash("sha256").update(value, "utf8").digest("hex");
const retiredText = "TEST ONLY withdrawn snippet amber constellation";

function approvedShape(dossiers, timestamp) {
  const material = { dossiers, topics: [], contents: [] };
  return {
    schema_version: "dichiarazioni-pubbliche-public-v2",
    generated_at: timestamp,
    dataset_sha256: sha(canonicalJson(material)),
    dossier_count: dossiers.length,
    ...material,
    methodology: { aggregate_person_score: false, claim_level_only: true,
      requires_publication_gate: true, requires_approved_evidence: true,
      requires_resolved_transcript: true },
  };
}

// Synthetic fixture with a *genuine* built public-v2 record. External rights
// and approval do not come from this fixture, even when the schema accepts it.
const dossier = structuredClone(demo.dossiers[0]);
dossier.finding_id = "finding:withdrawal-canary";
dossier.claim_id = "claim:withdrawal-canary";
dossier.claim = retiredText;
dossier.speaker.id = "person:withdrawal-canary";
dossier.speaker.name = "Fictional Source Canary";
dossier.source.content_id = "content:withdrawal-canary";
dossier.source.title = "Fictional Withdrawal Publication";
dossier.corrections = [];
dossier.rights_of_reply = [];

const oldSource = approvedShape([dossier], "2026-10-11T09:00:00Z");
const newSource = approvedShape([], "2026-10-12T09:00:00Z");
const oldPath = join(scratch, "old-projection.json");
const newPath = join(scratch, "new-projection.json");
const oldOutput = join(scratch, "old-build");
const newOutput = join(scratch, "new-build");
const { DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: _path,
  DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: _demo, ...cleanEnv } = process.env;

function build(source, output) {
  const result = spawnSync("npm", ["run", "build", "--", "--outDir", output], {
    cwd: root, encoding: "utf8", timeout: 90000, maxBuffer: 2 * 1024 * 1024,
    env: { ...cleanEnv, DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: source },
  });
  assert.equal(result.status, 0,
    `Isolated Astro build failed: ${String(result.stderr).slice(-3500)} ${String(result.stdout).slice(-2500)}`);
}

const until = "2099-01-01T00:00:00Z";
const pin = (asset, epoch, releaseId) => ({
  allowPinnedSearch: true,
  releaseId,
  epoch,
  projectionSha256: asset.projection_sha256,
  indexSha256: asset.index_sha256,
  generatedAt: asset.generated_at,
  validUntil: until,
});
const clock = () => new Date("2026-10-12T12:00:00Z");
const matches = (asset, trustedPins, query = "withdrawn") => readPinnedPublicSearch(
  asset, async () => trustedPins, query, { kind: "finding" }, { now: clock },
);
const fail = async (label, task, regexp) =>
  assert.rejects(task, regexp, `${label}: stale/private public snippet must be refused`);

try {
  await writeFile(oldPath, canonicalJson(oldSource) + "\n");
  await writeFile(newPath, canonicalJson(newSource) + "\n");
  build(oldPath, oldOutput);
  build(newPath, newOutput);
  const oldBytes = await readFile(join(oldOutput, "search-index.v1.json"), "utf8");
  const newBytes = await readFile(join(newOutput, "search-index.v1.json"), "utf8");
  const old = JSON.parse(oldBytes), current = JSON.parse(newBytes);
  assert.notEqual(old.projection_sha256, current.projection_sha256);
  assert.notEqual(old.index_sha256, current.index_sha256);
  assert(old.records.some(row => row.title === retiredText && row.kind === "finding"));
  assert.equal(current.records.length, 0, "withdrawal build still contains a public record");
  assert(!newBytes.includes(retiredText));
  assert((await readFile(join(oldOutput, "esplora/index.html"), "utf8")).includes("esplora"));
  assert((await readFile(join(newOutput, "esplora/index.html"), "utf8")).includes("esplora"));

  // Current v2 search remains compatible, but a self-hashed asset can falsely
  // claim a newer projection fingerprint while carrying retired old snippets.
  const forged = await finalizeSearchIndex({
    ...buildSearchIndexMaterial(oldSource),
    projection_sha256: current.projection_sha256,
    generated_at: current.generated_at,
  });
  assert.equal((await validateSearchIndex(forged, current.projection_sha256)).records
    .some(row => row.title === retiredText), true,
  "RED defect was not reproducible: legacy validator unexpectedly binds independent release");
  assert.equal(searchPublicIndex(old, "withdrawn").records[0]?.title, retiredText);
  assert.equal(searchPublicIndex(current, "withdrawn").records.length, 0);

  const currentPins = pin(current, 2, "release:after-withdrawal");
  const oldPins = pin(old, 1, "release:before-withdrawal");
  await fail("stale real Astro asset", () => matches(oldBytes, currentPins),
    /SEARCH_INDEX_INCOMPATIBLE|SEARCH_PINNED_INDEX_MISMATCH/);
  await fail("rehashed spoof of current projection", () => matches(canonicalJson(forged), currentPins),
    /SEARCH_PINNED_INDEX_MISMATCH/);
  const safe = await matches(newBytes, currentPins);
  assert.equal(safe.status, "OK");
  assert.deepEqual(safe.records, []);
  const historical = await matches(oldBytes, oldPins, "withdrawn");
  assert.equal(historical.records[0]?.title, retiredText,
    "old same-snapshot preview remains deterministic; old pins are not current authority");

  await fail("old asset under current release epoch", () =>
    readPinnedPublicSearch(oldBytes, async () => currentPins, "", {}, { now: clock }),
    /SEARCH_INDEX_INCOMPATIBLE|SEARCH_PINNED_INDEX_MISMATCH/);

  let reads = 0;
  await fail("withdrawal during pending read", () => readPinnedPublicSearch(
    oldBytes, async () => (++reads === 1 ? oldPins : currentPins), "withdrawn",
    {}, { now: clock },
  ), /SEARCH_PINNED_RELEASE_CHANGED/);
  assert.equal(reads, 2, "reader must inspect latest release after computation");

  let sameDigestReads = 0;
  await fail("changed epoch with identical hashes", () => readPinnedPublicSearch(
    newBytes, async () => (++sameDigestReads === 1 ? currentPins : { ...currentPins, epoch: 3 }),
    "withdrawn", {}, { now: clock },
  ), /SEARCH_PINNED_RELEASE_CHANGED/);
  assert.equal(sameDigestReads, 2);
  await fail("missing external authority", () => matches(newBytes, { ...currentPins, allowPinnedSearch: false }),
    /SEARCH_PINNED_RELEASE_INVALID/);
  await fail("expired externally supplied release", () => matches(newBytes, {
    ...currentPins, validUntil: "2026-10-12T11:00:00Z",
  }), /SEARCH_PINNED_RELEASE_EXPIRED/);
  await fail("unavailable current authority", () => readPinnedPublicSearch(
    newBytes, async () => { throw Error("AUTHORITY_OFFLINE"); }, "",
    {}, { now: clock },
  ), /SEARCH_PINNED_RELEASE_UNAVAILABLE/);
  const poisoned = structuredClone(current);
  poisoned.records = structuredClone(old.records);
  const { index_sha256: _discardedSelfHash, ...mixedMaterial } = poisoned;
  const mismatched = await finalizeSearchIndex(mixedMaterial);
  assert.equal((await validateSearchIndex(mismatched, current.projection_sha256))
    .records.find(item => item.kind === "finding")?.title,
    retiredText, "rehashed old record must demonstrate same-projection legacy split-brain");
  await fail("mixed typed record old/new artifact", () => matches(canonicalJson(mismatched), currentPins),
    /SEARCH_PINNED_INDEX_MISMATCH/);
  console.log("DP409 GREEN: 2 authentic isolated Astro builds, 1 retired finding -> 0, " +
    "forged/rehashed/mixed releases refused; external pin double read and stale epoch denied. " +
    `old=${old.index_sha256}, new=${current.index_sha256}`);
} finally {
  await rm(scratch, { recursive: true, force: true });
}
