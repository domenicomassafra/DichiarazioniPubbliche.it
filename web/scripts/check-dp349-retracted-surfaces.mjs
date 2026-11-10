/** DP-349: withdrawn assessment must not masquerade as a current verdict.
 * Uses existing demo-only dossiers in a disposable build, never public data.
 * Run from web/ with Node strip-types under the Mac resource guard.
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { publicIdSlug } from "../src/lib/format.ts";
import {
  buildSearchIndexMaterial,
  canonicalJson,
  finalizeSearchIndex,
  searchPublicIndex,
  validateSearchIndex,
} from "../src/lib/searchIndex.ts";

const root = fileURLToPath(new URL("../", import.meta.url));
const demo = JSON.parse(await readFile(new URL("../src/data/demo-projection.json", import.meta.url), "utf8"));
const [retracted, disputed, corrected] = demo.dossiers;
assert(retracted && disputed && corrected, "the three existing local demo dossiers are required");
retracted.finding.publication_status = "RETRACTED";
disputed.finding.publication_status = "DISPUTED";
corrected.finding.publication_status = "CORRECTED";

// The projection hash covers optional collections only when present.
const material = { dossiers: demo.dossiers };
if (demo.topics !== undefined) material.topics = demo.topics;
if (demo.contents !== undefined) material.contents = demo.contents;
demo.dataset_sha256 = createHash("sha256").update(canonicalJson(material)).digest("hex");
const searchMaterial = buildSearchIndexMaterial(demo);
const index = await finalizeSearchIndex(searchMaterial);
assert.deepEqual(await validateSearchIndex(index, demo.dataset_sha256), index);

const finding = (id) => index.records.find((record) => record.kind === "finding" && record.id === id);
const retiredIndex = finding(retracted.finding_id);
const disputedIndex = finding(disputed.finding_id);
const correctedIndex = finding(corrected.finding_id);
assert(retiredIndex && disputedIndex && correctedIndex, "all public demo Finding routes must stay indexed");
assert.equal(retiredIndex.assessment, null, "RETRACTED must not expose the historical assessment");
assert.equal(retiredIndex.publication_status, "RETRACTED", "withdrawal must be explicitly declared in the index schema");
assert.match(retiredIndex.subtitle, /^Valutazione ritirata · /, "Explore must show explicit withdrawal");
assert(!retiredIndex.secondary_terms.includes(retracted.finding.assessment),
  "historical assessment must not become a searchable term");
for (const [record, dossier] of [[disputedIndex, disputed], [correctedIndex, corrected]]) {
  assert.equal(record.publication_status, dossier.finding.publication_status);
  assert.equal(record.assessment, dossier.finding.assessment,
    dossier.finding.publication_status + " must retain its current assessment");
}
const activeAssessment = searchPublicIndex(index, "", {
  kind: "finding", assessment: retracted.finding.assessment,
});
assert(!activeAssessment.records.some((record) => record.id === retracted.finding_id),
  "RETRACTED must not appear under its old verdict filter");

// A null finding without the visible withdrawal marker remains invalid:
// accepting null is not permission to erase any ordinary Finding verdict.
const altered = structuredClone(searchMaterial);
const invalid = altered.records.find((record) => record.id === retracted.finding_id);
invalid.subtitle = "Senza stato di ritiro";
const resealed = await finalizeSearchIndex(altered);
await assert.rejects(validateSearchIndex(resealed, demo.dataset_sha256),
  /SEARCH_INDEX_RECORD_INVALID/, "other null-assessment findings must still fail the index gate");

// A forged withdrawal label on an ordinary PUBLISH record must not validate,
// even when both the search material and its self-hash have been recomputed.
const forged = structuredClone(searchMaterial);
const active = forged.records.find((record) => record.id === disputed.finding_id);
active.assessment = null;
active.subtitle = `Valutazione ritirata · ${active.subtitle}`;
await assert.rejects(validateSearchIndex(await finalizeSearchIndex(forged), demo.dataset_sha256),
  /SEARCH_INDEX_RECORD_INVALID/, "an active Finding cannot acquire a withdrawn state from subtitle text");
const reissued = structuredClone(searchMaterial);
const reissuedRow = reissued.records.find((record) => record.id === disputed.finding_id);
reissuedRow.assessment = null;
reissuedRow.publication_status = "RETRACTED";
reissuedRow.subtitle = `Valutazione ritirata · ${reissuedRow.subtitle}`;
const reissuedIndex = await finalizeSearchIndex(reissued);
assert.notEqual(reissuedIndex.index_sha256, index.index_sha256,
  "a forged complete status change must fail the independently embedded page digest");

const { DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: _path,
  DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: _demo, ...cleanEnv } = process.env;
const scratch = await mkdtemp(join(root, ".dp349-retracted-"));
try {
  const fixturePath = join(scratch, "demo-only-retracted.json");
  const dist = join(scratch, "dist");
  await writeFile(fixturePath, canonicalJson(demo) + "\n");
  const build = spawnSync("npm", ["run", "build", "--", "--outDir", dist], {
    cwd: root, encoding: "utf8", timeout: 90000,
    env: {
      ...cleanEnv,
      DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: "1",
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: fixturePath,
    },
  });
  assert.equal(build.status, 0,
    `isolated build failed: ${String(build.stderr).slice(-2500)} ${String(build.stdout).slice(-1200)}`);

  const readRoute = async (route) =>
    readFile(join(dist, route, "index.html"), "utf8");
  const claimRow = (html, dossier) => {
    const route = finding(dossier.finding_id).route;
    const row = [...html.matchAll(/<article\b[^>]*class="claim-row"[^>]*>([\s\S]*?)<\/article>/g)]
      .map((match) => match[1]).find((markup) => markup.includes(`href="${route}"`));
    assert(row, `ClaimRow not rendered for: ${route}`);
    return row;
  };

  const home = await readRoute("");
  assert.match(home, /Dalle parole alle prove\./);
  const featuredSection = home.match(/<section\b[^>]*class="[^"]*dp-home-feature[^\"]*"[^>]*>([\s\S]*?)<\/section>/)?.[1];
  assert(featuredSection, "Home must feature an active Finding if available");
  assert(!featuredSection.includes(finding(retracted.finding_id).route), "Home must not feature a withdrawn Finding");
  const newestActive = [...demo.dossiers]
    .filter((dossier) => dossier.finding.publication_status !== "RETRACTED")
    .sort((a, b) => Date.parse(b.finding.published_at) - Date.parse(a.finding.published_at))[0];
  assert(featuredSection.includes(finding(newestActive.finding_id).route),
    "Home should feature the newest active Finding");
  const person = await readRoute("persone/" + retracted.speaker.id.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
  const topic = demo.topics.find((item) =>
    item.memberships.some((membership) => membership.finding_ids.includes(retracted.finding_id)));
  assert(topic, "withdrawn demo Finding needs a Topic caller");
  for (const [surface, html] of [
    ["Home", home], ["Person", person], ["Topic", await readRoute("temi/" + topic.slug)],
  ]) {
    const row = claimRow(html, retracted);
    assert.match(row, /Valutazione ritirata/, `${surface}: withdrawal status must be visible`);
    assert.doesNotMatch(row, /assessment-support|assessment-contradict|Supportata|Conclusione fattualmente falsa/,
      `${surface}: historical assessment must not be presented as current`);
  }
  for (const dossier of [disputed, corrected]) {
    const row = claimRow(home, dossier);
    assert.match(row, /class="assessment assessment-/,
      dossier.finding.publication_status + " retains the assessment badge");
  }

  const detail = await readRoute(`dichiarazioni/${publicIdSlug(retracted.finding_id)}`);
  assert.match(detail, /Valutazione ritirata/, "canonical detail must announce withdrawal");
  assert(!detail.includes(retracted.finding.rationale), "canonical detail must hide historical rationale");
  const source = await readRoute(`contenuti/${publicIdSlug(retracted.source.content_id)}`);
  assert.match(source, /Valutazione ritirata/, "Content source moments must announce withdrawal");
  for (const relation of retracted.relations ?? []) {
    const tracePath = join(dist, "tracce", publicIdSlug(relation.id), "index.html");
    const trace = await readFile(tracePath, "utf8").catch((error) => {
      if (error.code === "ENOENT") return null;
      throw error;
    });
    if (trace !== null) {
      assert.match(trace, /Valutazione ritirata/, "Trace must not show withdrawn verdict as current");
    }
  }

  const builtIndex = JSON.parse(await readFile(join(dist, "search-index.v1.json"), "utf8"));
  assert.deepEqual(await validateSearchIndex(builtIndex, demo.dataset_sha256), builtIndex);
  const exploreHtml = await readRoute("esplora");
  assert(exploreHtml.includes(builtIndex.index_sha256),
    "Explore HTML must bind the exact search-index SHA independently of fetched asset bytes");
  assert(!exploreHtml.includes(reissuedIndex.index_sha256),
    "a reissued bogus index cannot match the page's authenticated build digest");
  assert.equal(builtIndex.records.find((record) => record.id === retracted.finding_id).assessment, null);
  console.log("DP349 RETRACTED Home/Person/Topic + Explore search index PASS; DISPUTED/CORRECTED unchanged");
} finally {
  await rm(scratch, { recursive: true, force: true });
}
