/* DP-406.7 / DP-408.6 visual-architecture regression over an explicit
 * populated, approved-schema test projection. Never generates data/routes. */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const dist = new URL("../dist/", import.meta.url);
const root = dist.pathname;
const index = JSON.parse(await readFile(join(root, "search-index.v1.json"), "utf8"));
assert(Array.isArray(index.records), "M4_GRAMMAR_PUBLIC_INDEX_REQUIRED");
// Require a populated test case. An empty production projection cannot prove
// visual Topic/Trace acceptance and must never report an empty-success PASS.
const route = (kind) => index.records.find((item) => item.kind === kind)?.route;
const required = ["person"].map((kind) => [kind, route(kind)]);
const trace = "/tracce/relation-demo-public-services-update/";
const readRoute = async (path) =>
  readFile(join(root, path.slice(1), "index.html"), "utf8");
for (const [kind, path] of required) {
  assert(path, `M4_GRAMMAR_${kind.toUpperCase()}_POPULATED_ROUTE_REQUIRED`);
}
const topics = await Promise.all([...new Set(index.records
  .filter((item) => item.kind === "topic")
  .map((item) => item.route))].map(readRoute));
const topic = topics.find((html) => html.includes('class="shell topic-dossier"'));
assert(topic, "M4_GRAMMAR_POPULATED_TOPIC_REQUIRED");
const [person, relation] = await Promise.all([
  readRoute(required[0][1]), readRoute(trace),
]);
const hasClass = (html, name) =>
  [...html.matchAll(/class="([^"]*)"/g)]
    .some(([, names]) => names.split(/\s+/).includes(name));
const position = (html, literal) => html.indexOf(literal);

// Topic is a real scoped dossier with separate reader stream and contextual
// indices, while Person is a chronological archive of one person's statements.
assert(hasClass(topic, "topic-dossier"), "Topic lost dossier main surface");
assert(hasClass(topic, "topic-primary"), "Topic lost statement-stream primary job");
assert(hasClass(topic, "topic-context"), "Topic lost contextual secondary rail");
assert(hasClass(topic, "topic-person-index"), "Topic lost alphabetical Person index");
assert(hasClass(topic, "topic-source-index"), "Topic lost original-source index");
assert(hasClass(person, "person-chronology"), "Person lost chronology primary job");
assert(!hasClass(person, "topic-dossier"), "Person reused Topic's dossier hierarchy");
assert(!hasClass(topic, "person-chronology"), "Topic reused Person's chronology hierarchy");
assert(position(topic, 'class="topic-primary"') < position(topic, 'class="topic-context"'),
  "Topic contextual rail precedes primary statement stream in reading order");

// Trace's chronology must be an ordered collection of selectable events,
// each owning a neighboring detail panel, with full relation provenance behind
// secondary disclosure rather than an unsourced side-by-side comparison.
assert(hasClass(relation, "dp-trace-workspace"), "Trace workspace absent");
assert.match(relation, /<h2[^>]*id="trace-chronology-heading">Cronologia revisionata<\/h2>/,
  "Trace lacks explicit chronology heading");
assert.match(relation, /<ol class="dp-trace-chronology">/,
  "Trace must use an ordered timeline");
assert.equal((relation.match(/data-trace-event(?:\s|>)/g) ?? []).length, 2,
  "Test fixture requires two timeline participants");
assert.equal((relation.match(/data-trace-detail(?:\s|>)/g) ?? []).length, 2,
  "Every timeline participant needs its own detail");
assert(position(relation, 'class="dp-trace-chronology"') < position(relation, 'class="comparison-review'),
  "Relation review/provenance displaced the primary chronology");
assert.match(relation, /senza attribuire intenzioni|senza inferire intenzioni/i,
  "Trace lost the no-intent disclosure");
for (const [kind, html] of [["person", person], ["topic", topic], ["trace", relation]]) {
  assert(!/person_truth_score|reliability_score|leaderboard|kpi-dashboard|scorecard/i.test(html),
    `${kind} surface exposed a person score or dashboard concept`);
}
console.log("M4 page grammar PASS (approved-schema populated fixture; distinct Person/Topic IA, chronological Trace, 2 reviewed-shape participants; test only, no public approval)");
