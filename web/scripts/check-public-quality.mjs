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

const forbiddenPublicMarkers = [
  "provider_receipt",
  "canonical_transcript",
  "raw_transcript",
  "raw_text",
  "database_url",
  "omniroute_api_key",
  "person_truth_score",
];

for (const path of htmlFiles) {
  const html = await readFile(path, "utf8");
  const name = relative(distPath, path);
  assert.match(html, /<html\s[^>]*lang="it"/i, `${name}: missing lang=it`);
  assert.match(html, /<meta\s+name="description"\s+content="[^"]+"/i, `${name}: missing description`);
  assert.match(html, /<meta\s+name="robots"\s+content="noindex,nofollow"/i, `${name}: demo build must be noindex`);
  assert.match(html, /<link\s+rel="canonical"\s+href="[^"]+"/i, `${name}: missing canonical`);
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
  `public-quality checks PASS (${htmlFiles.length} HTML, ${jsFiles.length} JS; largest gzip JS ${maxCompressed} bytes: ${maxAsset})`,
);
