import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// An explicit build directory permits real isolated positive/negative route
// regression checks without mutating the shared web/dist during parallel work.
const dist = resolve(process.env.DP_ROUTE_DIST ?? fileURLToPath(new URL("../dist/", import.meta.url)));

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
  const absolute = html.match(/<link\s+rel="canonical"\s+href="([^"]+)"/i)?.[1];
  if (!absolute) return null;
  const url = new URL(absolute);
  assert.equal(url.origin, "https://dichiarazionipubbliche.it");
  assert.equal(absolute, url.origin + url.pathname);
  return url.pathname;
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
// Trace has no standalone search-record kind yet. An empty public index cannot
// authorize a rendered Trace or its compatibility alias, even with a canonical.
if (!demoSnapshot && searchIndex.records.length === 0) {
  assert.equal(traceRoutes.size, 0, "approved-empty route set must not expose Trace pages");
}

const legacyToCanonical = new Map([
  ["/fact-check/", "/dichiarazioni/"],
  ["/record/person/", "/persone/"],
  ["/record/", "/persone/"],
  ["/contents/", "/contenuti/"],
  ["/compare/", "/tracce/"],
]);

// AC-422.1 also forbids introducing a public template without its own page
// job. Canonical/self-linked HTML alone is not evidence that an extra route is
// approved. Account, privacy and correction intake are noindex utility surfaces,
// not additional primary public-record templates.
function assertKnownPublicPageFamilies(routes) {
  const staticPages = new Set([...requiredStatic, "/accedi/", "/account/", "/privacy/", "/segnalazioni/"]);
  const dynamicFamilies = [...kindToPrefix.values(), "/tracce/", ...legacyToCanonical.keys()];
  for (const route of routes) {
    assert(
      staticPages.has(route) || dynamicFamilies.some((prefix) => route.startsWith(prefix)),
      `${route}: unapproved public page family without a distinct page job`,
    );
  }
}
// A future self-canonical page must not silently pass this route inventory.
assert.throws(
  () => assertKnownPublicPageFamilies([...pages.keys(), "/nuovo-hub/"]),
  /unapproved public page family/,
  "a new route family needs an explicit page-owner contract",
);
assertKnownPublicPageFamilies(pages.keys());

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
    // Current compatibility templates share the slug of their v3 target.
    // Existence of an unrelated target cannot authorize a legacy alias.
    assert.equal(
      route.slice(legacyPrefix.length),
      canonical.slice(canonicalPrefix.length),
      `${route}: legacy alias identifier differs from canonical target ${canonical}`,
    );
    if (legacyPrefix === "/compare/" && demoSnapshot) {
      assert.equal(html, pages.get(canonical), `${route}: demo Trace alias rendered differently from ${canonical}`);
    }
    // The nested /record/person/ prefix precedes /record/: count and validate once.
    break;
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
const staticAssets = new Set(["/favicon.svg"]);
for (const asset of staticAssets) {
  assert.match(await readFile(join(dist, asset.slice(1)), "utf8"), /<svg\b/,
    `${asset}: linked favicon must be included in the build`);
}
let internalLinks = 0;
for (const [route, html] of pages) {
  for (const match of html.matchAll(/href="(\/[^"]*)"/g)) {
    const href = match[1];
    if (href.startsWith("/#") || href === "#") continue;
    const target = href.split("#", 1)[0].split("?", 1)[0];
    if (!target || runtimePaths.some((prefix) => target.startsWith(prefix)) || staticAssets.has(target)) continue;
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
    ? "non-demo empty snapshot (approval requires external proof)"
    : `search-driven snapshot (${[...new Set(searchIndex.records.map((record) => record.kind))].sort().join(", ")})`;
const canonicalFamilies = ["/", "/esplora/", "/metodo/", ...kindToPrefix.values(), "/tracce/"];
const presentFamilies = canonicalFamilies.filter((family) =>
  family === "/" || family === "/esplora/" || family === "/metodo/"
    ? pages.has(family)
    : [...pages.keys()].some((route) => route.startsWith(family)),
);
// Even 8/8 in a fixture is only structural proof: AC-422.1 asks for the real
// approved public route set with independent live published-resource readback.
console.log(`route-contract checks PASS (${snapshotShape}; canonical v3 families ${presentFamilies.length}/${canonicalFamilies.length}; AC-422.1 live acceptance NOT_ATTESTED; ${pages.size} HTML routes, ${legacyCount} compatibility aliases, ${internalLinks} internal links, ${timedLocatorPages} timed locator pages, ${writtenLocatorPages} written locator pages)`);
