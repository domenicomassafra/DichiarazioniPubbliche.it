import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";

const dist = new URL("../dist/", import.meta.url).pathname;

async function walk(dir) {
  const output = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) output.push(...await walk(path));
    else output.push(path);
  }
  return output;
}

function routeFor(path) {
  const rel = relative(dist, path).replaceAll("\\", "/");
  if (rel === "index.html") return "/";
  return `/${rel.replace(/index\.html$/, "")}`;
}

function canonicalOf(html) {
  return html.match(/<link\s+rel="canonical"\s+href="([^"]+)"/i)?.[1] ?? null;
}

const htmlFiles = (await walk(dist)).filter((path) => path.endsWith(".html"));
const pages = new Map();
for (const path of htmlFiles) pages.set(routeFor(path), await readFile(path, "utf8"));
const searchIndex = JSON.parse(await readFile(join(dist, "search-index.v1.json"), "utf8"));
assert(Array.isArray(searchIndex.records), "search index records must be an array");
const demoProjection = JSON.parse(await readFile(new URL("../src/data/demo-projection.json", import.meta.url), "utf8"));
const demoSnapshot = searchIndex.projection_sha256 === demoProjection.dataset_sha256;

const kindToPrefix = new Map([
  ["finding", "/dichiarazioni/"],
  ["person", "/persone/"],
  ["topic", "/temi/"],
  ["content", "/contenuti/"],
]);

function expectedDynamicRoutes(records) {
  const expected = new Map([...kindToPrefix.values()].map((prefix) => [prefix, new Set()]));
  for (const record of records) {
    const prefix = kindToPrefix.get(record?.kind);
    if (!prefix) continue;
    assert.equal(typeof record.route, "string", `${record?.kind ?? "unknown"} search record is missing a route`);
    assert(record.route.startsWith(prefix), `${record.kind} search record route escaped ${prefix}: ${record.route}`);
    expected.get(prefix).add(record.route);
  }
  return expected;
}

// Regression guard: first-class Content can be public with zero Findings/People/Topics.
const contentOnlyRegression = expectedDynamicRoutes([{ kind: "content", route: "/contenuti/content-only/" }]);
assert.deepEqual([...contentOnlyRegression.get("/contenuti/")], ["/contenuti/content-only/"]);
for (const prefix of ["/dichiarazioni/", "/persone/", "/temi/"]) {
  assert.equal(contentOnlyRegression.get(prefix).size, 0, `content-only regression unexpectedly requires ${prefix}`);
}
const expectedByPrefix = expectedDynamicRoutes(searchIndex.records);

function primaryPages(prefix) {
  return [...pages.entries()].filter(([route]) => route.startsWith(prefix));
}

const requiredStatic = ["/", "/esplora/", "/metodo/", "/correzioni/", "/dati/", "/progetto/"];
for (const route of requiredStatic) assert(pages.has(route), `missing canonical route ${route}`);
for (const [prefix, expectedRoutes] of expectedByPrefix) {
  const actualRoutes = new Set([...pages.keys()].filter((route) => route.startsWith(prefix)));
  assert.deepEqual(
    [...actualRoutes].sort(),
    [...expectedRoutes].sort(),
    `${prefix}: canonical routes diverge from the verified public search index`,
  );
}
const traceRoutes = new Set([...pages.keys()].filter((route) => route.startsWith("/tracce/")));
if (demoSnapshot) assert(traceRoutes.size > 0, "demo fixture must exercise at least one reviewed Trace route");

const legacyToCanonical = new Map([
  ["/fact-check/", "/dichiarazioni/"],
  ["/record/person/", "/persone/"],
  ["/record/", "/persone/"],
  ["/contents/", "/contenuti/"],
  ["/compare/", "/tracce/"],
]);
let legacyCount = 0;
let compareAliasCount = 0;
for (const [route, html] of pages) {
  for (const [legacyPrefix, canonicalPrefix] of legacyToCanonical) {
    if (!route.startsWith(legacyPrefix)) continue;
    legacyCount += 1;
    if (legacyPrefix === "/compare/") compareAliasCount += 1;
    const canonical = canonicalOf(html);
    assert(canonical?.startsWith(canonicalPrefix), `${route}: unsafe/missing legacy canonical ${canonical}`);
    assert(pages.has(canonical), `${route}: canonical target is not built: ${canonical}`);
  }
}
assert.equal(compareAliasCount, traceRoutes.size, "Trace compatibility aliases must match canonical Trace routes one-for-one");
if (demoSnapshot) assert(legacyCount > 0, "demo fixture must exercise legacy compatibility aliases");

const personPages = primaryPages("/persone/");
const topicPages = primaryPages("/temi/");
if (demoSnapshot) assert(personPages.length > 0 && topicPages.length > 0, "demo fixture requires Person/Topic routes for IA acceptance");
for (const [route, html] of personPages) {
  assert.match(html, /class="[^"]*person-chronology/, `${route}: Person chronology missing`);
  assert.match(html, /non esiste un punteggio della persona/i, `${route}: Person no-score boundary missing`);
  assert.equal(/class="[^"]*topic-context/.test(html), false, `${route}: Person route leaked Topic context IA`);
}
let populatedTopicPages = 0;
for (const [route, html] of topicPages) {
  const hasDossier = /class="[^"]*topic-dossier/.test(html);
  const hasEmpty = /class="[^"]*topic-empty/.test(html);
  assert(hasDossier || hasEmpty, `${route}: Topic route has neither dossier nor deliberate empty state`);
  if (hasDossier) {
    populatedTopicPages += 1;
    assert.match(html, /class="[^"]*topic-context/, `${route}: populated Topic contextual index missing`);
  }
  assert.equal(/class="[^"]*person-chronology/.test(html), false, `${route}: Topic route leaked Person chronology IA`);
}
if (demoSnapshot) assert(populatedTopicPages > 0, "demo Topic fixture must exercise at least one populated contextual dossier");

const contentPages = primaryPages("/contenuti/");
if (demoSnapshot) assert(contentPages.length > 0, "demo Content routes required for locator acceptance");
let timedLocatorPages = 0;
let writtenLocatorPages = 0;
for (const [route, html] of contentPages) {
  if (/con locator temporale/i.test(html)) {
    timedLocatorPages += 1;
    assert.match(html, /Locator pubblico/i, `${route}: timed locator lacks public-locator disclosure`);
  }
  if (/con locator testuale/i.test(html) || /Passaggio testuale/i.test(html)) {
    writtenLocatorPages += 1;
    assert.match(html, /(?:Passaggio \d+–\d+|Passaggio testuale verificato)/i, `${route}: written locator lacks textual selector`);
    assert.match(html, /Passaggio selezionato/i, `${route}: written locator is mislabeled as a timed moment`);
    assert.equal(/Passaggio selezionato[^<]*(?:\d{1,2}:\d{2})/i.test(html), false, `${route}: written locator fabricated a timestamp`);
  }
}
if (demoSnapshot) assert(timedLocatorPages > 0, "demo Content fixture must exercise at least one timed locator");
if (process.env.DP_EXPECT_WRITTEN_LOCATOR === "1") {
  assert(writtenLocatorPages > 0, "Content fixture must exercise at least one written locator");
}

const statementPages = primaryPages("/dichiarazioni/");
for (const [route, html] of statementPages) {
  assert.match(html, /id="storia"/, `${route}: Statement history/version section missing`);
  assert.match(html, /Apri la fonte originale/i, `${route}: Statement source link missing`);
  assert.match(html, /Versione (?:pubblicata|corretta)/i, `${route}: Statement version state missing`);
}
const tracePages = primaryPages("/tracce/");
for (const [route, html] of tracePages) {
  assert.match(html, /Cronologia revisionata/i, `${route}: Trace chronology missing`);
  assert.match(html, /Apri la fonte originale/i, `${route}: Trace source link missing`);
  assert.match(html, /senza (?:attribuire|inferire) intenzioni/i, `${route}: Trace no-intent boundary missing`);
}

const runtimePaths = ["/_astro/", "/api/", "/llms.txt", "/openapi", "/search-index.v1.json"];
let internalLinks = 0;
for (const [route, html] of pages) {
  for (const match of html.matchAll(/href="(\/[^"]*)"/g)) {
    const href = match[1];
    if (href.startsWith("/#") || href === "#") continue;
    const target = href.split("#", 1)[0].split("?", 1)[0];
    if (!target || runtimePaths.some((prefix) => target.startsWith(prefix))) continue;
    internalLinks += 1;
    const normalized = target.endsWith("/") || target.includes(".") ? target : `${target}/`;
    assert(pages.has(normalized), `${route}: broken internal link ${href}`);
  }
}

assert.equal([...pages.keys()].some((route) => route.startsWith("/studio/")), false, "private Studio route leaked into public build");

for (const [route, html] of pages) {
  if ([...legacyToCanonical.keys()].some((prefix) => route.startsWith(prefix))) continue;
  const canonical = canonicalOf(html);
  assert(canonical, `${route}: missing canonical`);
  assert.equal(canonical, route, `${route}: primary route canonical is ${canonical}`);
}

const snapshotShape = demoSnapshot
  ? "populated demo fixture"
  : searchIndex.records.length === 0
    ? "approved empty snapshot"
    : `search-driven snapshot (${[...new Set(searchIndex.records.map((record) => record.kind))].sort().join(", ")})`;
console.log(`route-contract checks PASS (${snapshotShape}; ${pages.size} HTML routes, ${legacyCount} compatibility aliases, ${internalLinks} internal links, ${timedLocatorPages} timed locator pages, ${writtenLocatorPages} written locator pages)`);
