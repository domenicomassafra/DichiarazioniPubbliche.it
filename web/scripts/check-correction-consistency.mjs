import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

const dist = path.resolve("dist");

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...await walk(full));
    else out.push(full);
  }
  return out;
}

function routeFor(file) {
  const rel = path.relative(dist, file).replaceAll("\\", "/");
  if (rel === "index.html") return "/";
  return `/${rel.replace(/index\.html$/, "")}`;
}

const htmlFiles = (await walk(dist)).filter((file) => file.endsWith("index.html"));
const pages = new Map();
for (const file of htmlFiles) pages.set(routeFor(file), await readFile(file, "utf8"));

const searchIndex = JSON.parse(await readFile(path.join(dist, "search-index.v1.json"), "utf8"));
const corrected = searchIndex.records.filter((record) =>
  record.kind === "finding" && (record.has_corrections || record.has_rights_of_reply)
);

const correctionRegister = pages.get("/correzioni/");
assert(correctionRegister, "correction register route missing");
if (corrected.length === 0) {
  assert.match(correctionRegister, /Nessuna correzione pubblicata in questo snapshot/i, "empty correction register state missing");
}

const surfacePrefixes = ["/persone/", "/temi/", "/contenuti/", "/tracce/"];
let linkedSurfaceCount = 0;

for (const record of corrected) {
  const statement = pages.get(record.route);
  assert(statement, `${record.id}: canonical Statement route missing`);
  assert.match(statement, /id="storia"/, `${record.id}: Statement history anchor missing`);
  if (record.has_corrections) {
    assert.match(statement, /Correzioni pubblicate/i, `${record.id}: corrected Statement lacks correction history`);
    assert(correctionRegister.includes(`href="${record.route}"`), `${record.id}: correction register does not link current Statement`);
  }
  if (record.has_rights_of_reply) {
    assert.match(statement, /Repliche pubblicate/i, `${record.id}: replied Statement lacks reply history`);
  }

  const historyHref = `${record.route}#storia`;
  const linked = [];
  for (const [route, html] of pages) {
    if (!surfacePrefixes.some((prefix) => route.startsWith(prefix))) continue;
    if (!html.includes(`href="${record.route}"`)) continue;
    linked.push(route);
    assert(html.includes(`href="${historyHref}"`), `${record.id}: ${route} links the Statement but omits its correction/reply history path`);
  }
  assert(linked.some((route) => route.startsWith("/persone/")), `${record.id}: Person surface missing`);
  assert(linked.some((route) => route.startsWith("/contenuti/")), `${record.id}: Content surface missing`);
  linkedSurfaceCount += linked.length;
}

console.log(`correction-consistency checks PASS (${corrected.length} corrected/replied findings, ${linkedSurfaceCount} linked derived surfaces${corrected.length === 0 ? "; approved empty snapshot" : ""})`);
