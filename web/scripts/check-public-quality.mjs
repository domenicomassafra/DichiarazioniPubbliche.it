import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";

const root = new URL("../dist/", import.meta.url);
const jsBudgetBytes = 120 * 1024;

async function files(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...await files(path));
    else out.push(path);
  }
  return out;
}

const distPath = root.pathname;
const all = await files(distPath);
const htmlFiles = all.filter((path) => path.endsWith(".html"));
const jsFiles = all.filter((path) => path.endsWith(".js"));
assert(htmlFiles.length > 0, "static build must contain HTML pages");
const sitemapPath = join(distPath, "sitemap.xml");
const robotsPath = join(distPath, "robots.txt");
assert(all.includes(sitemapPath), "static build must contain sitemap.xml");
assert(all.includes(robotsPath), "static build must contain robots.txt");

const forbiddenPublicMarkers = [
  "provider_receipt",
  "canonical_transcript",
  "raw_transcript",
  "raw_text",
  "database_url",
  "omniroute_api_key",
  "person_truth_score",
];

const canonicalRoutes = new Set();
const privateAccountRoutes = new Set(["/accedi/", "/account/"]);
const publicCanonicalRoutes = new Set();
for (const path of htmlFiles) {
  const html = await readFile(path, "utf8");
  const name = relative(distPath, path);
  assert.match(html, /<html\s[^>]*lang="it"/i, `${name}: missing lang=it`);
  assert.match(html, /<meta\s+name="description"\s+content="[^"]+"/i, `${name}: missing description`);
  const robots = html.match(/<meta\s+name="robots"\s+content="([^"]+)"/i)?.[1];
  assert(["noindex,nofollow", "index,follow"].includes(robots), `${name}: invalid robots policy ${robots}`);
  const canonical = html.match(/<link\s+rel="canonical"\s+href="([^"]+)"/i)?.[1];
  assert(canonical, `${name}: missing canonical`);
  canonicalRoutes.add(canonical);
  if (privateAccountRoutes.has(canonical)) {
    assert.equal(robots, "noindex,nofollow", `${name}: account sign-in/profile routes must stay noindex`);
  } else {
    publicCanonicalRoutes.add(canonical);
  }
  assert.match(html, /<main\s+id="main"/i, `${name}: missing main landmark`);
  const mainCount = (html.match(/<main\b/gi) ?? []).length;
  assert.equal(mainCount, 1, `${name}: expected exactly one main landmark, found ${mainCount}`);
  assert.match(html, /href="#main"/i, `${name}: missing skip link`);
  const h1Count = (html.match(/<h1\b/gi) ?? []).length;
  assert.equal(h1Count, 1, `${name}: expected exactly one h1, found ${h1Count}`);
  const lowered = html.toLowerCase();
  for (const marker of forbiddenPublicMarkers) {
    assert.equal(lowered.includes(marker), false, `${name}: leaked forbidden marker ${marker}`);
  }
  if (name.startsWith("dichiarazioni/")) {
    const match = html.match(/<script\s+type="application\/ld\+json">([\s\S]*?)<\/script>/i);
    assert(match, `${name}: Statement JSON-LD missing`);
    const structured = JSON.parse(match[1]);
    assert.equal(structured.url, canonical, `${name}: JSON-LD URL diverges from canonical`);
    assert.equal(typeof structured.identifier, "string", `${name}: JSON-LD finding identifier missing`);
    assert.equal(typeof structured.name, "string", `${name}: JSON-LD statement wording missing`);
  }
}
const publicPolicies = await Promise.all([...publicCanonicalRoutes].map(async (route) => {
  const filename = route === "/" ? "index.html" : `${route.slice(1)}index.html`;
  const html = await readFile(join(distPath, filename), "utf8");
  return html.match(/<meta\s+name="robots"\s+content="([^"]+)"/i)?.[1];
}));
assert.equal(new Set(publicPolicies).size, 1, "public reader pages must share one build robots policy");
const buildRobotsPolicy = publicPolicies[0];
const sitemap = await readFile(sitemapPath, "utf8");
const robotsText = await readFile(robotsPath, "utf8");
const sitemapRoutes = [...sitemap.matchAll(/<loc>https:\/\/dichiarazionipubbliche\.it([^<]*)<\/loc>/g)].map((match) => match[1]);
for (const route of sitemapRoutes) {
  assert(!route.startsWith("/studio/"), `sitemap leaked private Studio route ${route}`);
  assert(!privateAccountRoutes.has(route), `sitemap leaked account route ${route}`);
  for (const legacy of ["/fact-check/", "/record/", "/contents/", "/compare/"]) {
    assert(!route.startsWith(legacy), `sitemap leaked legacy alias ${route}`);
  }
}
if (buildRobotsPolicy === "noindex,nofollow") {
  assert.equal(sitemapRoutes.length, 0, "demo/noindex build must not publish sitemap URLs");
  assert.match(robotsText, /^User-agent: \*\nDisallow: \/\n$/);
} else {
  assert.match(robotsText, /^User-agent: \*\nAllow: \/\nSitemap: https:\/\/dichiarazionipubbliche\.it\/sitemap\.xml\n$/);
  assert.deepEqual(
    [...new Set(sitemapRoutes)].sort(),
    [...publicCanonicalRoutes].sort(),
    "production sitemap must equal the unique canonical public route set",
  );
}

let maxCompressed = 0;
let maxAsset = "";
for (const path of jsFiles) {
  const compressed = gzipSync(await readFile(path), { mtime: 0 }).byteLength;
  if (compressed > maxCompressed) {
    maxCompressed = compressed;
    maxAsset = relative(distPath, path);
  }
  assert(
    compressed <= jsBudgetBytes,
    `${relative(distPath, path)} exceeds ${jsBudgetBytes} byte compressed JS budget: ${compressed}`,
  );
}

const clientJs = (await Promise.all(jsFiles.map((path) => readFile(path, "utf8")))).join("\n").toLowerCase();
for (const marker of ["postgresql://", "omniroute", "openai.com/v1", "anthropic.com/v1", "database_url"]) {
  assert.equal(clientJs.includes(marker), false, `client JS contains forbidden runtime marker ${marker}`);
}

console.log(
  `public-quality checks PASS (${htmlFiles.length} HTML, ${jsFiles.length} JS; ${sitemapRoutes.length} sitemap URLs; public=${buildRobotsPolicy}; account=noindex; largest gzip JS ${maxCompressed} bytes: ${maxAsset})`,
);
