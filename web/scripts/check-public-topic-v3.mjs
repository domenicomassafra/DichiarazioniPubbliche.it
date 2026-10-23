/** DP-406 isolated Astro SSR; no route, demo projection or private data in production. */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { canonicalJson } from "../src/lib/searchIndex.ts";
import { makeScratchDir } from "./lib/scratch.mjs";

const repo = fileURLToPath(new URL("../../", import.meta.url));
const web = fileURLToPath(new URL("../", import.meta.url));
const component = fileURLToPath(new URL("../src/components/PublicTopicV3.astro", import.meta.url));

// Exactly the independent DP-439 synthetic public fixture. No claim to a real
// rights-approved Topic, source or independently approved review authority.
const python = `import json,sys
sys.path.insert(0,'poc'); sys.path.insert(0,'tests')
from test_dp439_person_topic_v3 import published,make,event
_,bundle,people,_,decisions=published()
print(json.dumps({'populated':make(bundle,people,decisions), 'empty':make(bundle,people,()), 'one':make(bundle,people,(decisions[0],)), 'revoked':make(bundle,people,(*decisions,event(bundle,0,'topic:economia',revision=2,status='REVOKED'))), 'topics':bundle['topics'], 'source_sha':bundle['dataset_sha256'], 'people_sha':people['dataset_sha256']}, ensure_ascii=False))`;
const producer = spawnSync("python3", ["-c", python], { cwd: repo, encoding: "utf8" });
assert.equal(producer.status, 0, `DP439 fixture failed: ${producer.stderr}`);
const { populated, empty, one, revoked, topics, source_sha, people_sha } = JSON.parse(producer.stdout);
const [economia, economica] = topics;
const hash = (input) => createHash("sha256").update(canonicalJson(input)).digest("hex");
assert.equal(populated.result_count, 4);
assert.equal(one.result_count, 1);
assert.equal(empty.result_count, 0);
assert.equal(revoked.result_count, 3);
assert.equal(economia.canonical_name, economica.canonical_name, "fixture must exercise homonym Topic identity");

const temp = await makeScratchDir("dp406-topic-v3-");
const pin = {
  expectedCollectionSha256: populated.dataset_sha256,
  expectedSourceDatasetSha256: source_sha,
  expectedPeopleDatasetSha256: people_sha,
  expectedTopicSha256: hash(economia),
  topicId: economia.topic_id,
  // Synthetic positive pin expires after this test starts; never a production approval.
  validUntil: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
  allowTopicV3: true,
};

async function render(name, model, topic = economia, options = {}) {
  const props = { ...pin, ...options };
  await writeFile(join(temp, "public-topic.json"), JSON.stringify({ collection: model, topic }));
  const imports = [
    "---",
    `import Topic from ${JSON.stringify(component)};`,
    'import data from "../../public-topic.json";',
    "---",
  ];
  const attrs = Object.entries(props).map(([key, value]) => `${key}={${JSON.stringify(value)}}`).join(" ");
  await writeFile(join(temp, "src/pages/index.astro"), [...imports,
    `<Topic collection={data.collection} topic={data.topic} ${attrs} />`,
  ].join("\n"));
  return spawnSync(join(web, "node_modules/.bin/astro"),
    ["build", "--root", temp, "--outDir", join(temp, name)],
    { cwd: web, encoding: "utf8", timeout: 120000, env: {
      ...process.env, DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: "1",
    } });
}
async function succeeds(name, model, topic = economia, options = {}) {
  const result = await render(name, model, topic, options);
  assert.equal(result.status, 0, `Astro SSR ${name} failed:\n${result.stdout}\n${result.stderr}`);
  return readFile(join(temp, name, "index.html"), "utf8");
}
async function rejects(name, model, topic = economia, options = {}) {
  const result = await render(name, model, topic, options);
  assert.notEqual(result.status, 0, `Unsafe ${name} unexpectedly built and exposed a Topic`);
}
try {
  await mkdir(join(temp, "src/pages"), { recursive: true });
  await symlink(join(web, "node_modules"), join(temp, "node_modules"), "dir");
  await writeFile(join(temp, "astro.config.mjs"),
    'import {defineConfig} from "astro/config";export default defineConfig({output:"static"})');

  const populatedHtml = await succeeds("published", populated);
  assert.match(populatedHtml, /data-public-topic-v3/);
  assert.match(populatedHtml, /Raccolta sintetica delimitata/);
  assert.match(populatedHtml, /costa 10 euro, non 20\./);
  assert.match(populatedHtml, /href="\/persone\/persona-a\/"/);
  assert.match(populatedHtml, /href="\/persone\/persona-b\/"/);
  assert.match(populatedHtml, /href="\/dichiarazioni\/statement-3\/"/);
  assert.match(populatedHtml, /href="https:\/\/example\.test\/source-3"/);
  assert.match(populatedHtml, /data-topic-v3-count/);
  assert.match(populatedHtml, /aria-live="polite"/);
  assert.match(populatedHtml, /type="date"/);
  assert.match(populatedHtml, /class="claim-list/);
  assert.match(populatedHtml, /non ha un verdetto fattuale/);
  assert.doesNotMatch(populatedHtml, /leaderboard|person_score|reliability_score|evidence_body|raw_transcript|review:membership/);
  assert.ok(populatedHtml.indexOf("2026-10-03") < populatedHtml.indexOf("2026-10-01"), "chronology must be newest first");

  const noMatchHtml = await succeeds("approved-empty", empty, economia,
    {expectedCollectionSha256:empty.dataset_sha256});
  assert.match(noMatchHtml, /Nessuna opinione pubblicata disponibile per questo Tema/);
  assert.match(noMatchHtml, /href="\/esplora\/"/);
  assert.match(noMatchHtml, /href="\/metodo\/"/);
  assert.doesNotMatch(noMatchHtml, /costa 10 euro/);
  const otherHtml = await succeeds("distinct-same-label", one, economica, {
    topicId: economica.topic_id, expectedTopicSha256: hash(economica),
    expectedCollectionSha256: one.dataset_sha256,
  });
  assert.match(otherHtml, /Nessuna opinione pubblicata disponibile per questo Tema/);
  assert.doesNotMatch(otherHtml, /href="\/persone\/persona-a\/"/);

  await rejects("opt-in-off", populated, economia, {allowTopicV3:false});
  await rejects("stale-release", revoked, economia); // held/withdrawn new release, OLD pin
  await rejects("expired-authority", populated, economia, {
    validUntil: new Date(Date.now() - 60_000).toISOString(),
  });
  await rejects("unknown-topic", populated, economia, {topicId:"topic:missing"});
  await rejects("wrong-topic-digest", populated, economia, {expectedTopicSha256:hash(economica)});
  const forged = structuredClone(populated);
  forged.data[0].statement.original.text = "TESTO PRIVATO NON AUTORIZZATO";
  await rejects("body-tamper", forged, economia);
  const foreign = structuredClone(populated);
  foreign.data[0].person_route = "//evil.invalid/";
  await rejects("foreign-person-link", foreign, economia);
  console.log("DP-406 actual Astro SSR opt-in Topic dossier: populated, empty, homonym, date/source/Person links, stale/withdrawn, forgery and unavailable fail-closed PASS");
} finally {
  await rm(temp, { recursive: true, force: true });
}
