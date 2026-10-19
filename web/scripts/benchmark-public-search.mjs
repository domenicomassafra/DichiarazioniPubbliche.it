// Offline reproducible benchmark: identical approved lexical corpus for v2 and v3.
// node --experimental-strip-types --expose-gc scripts/benchmark-public-search.mjs
import { performance } from "node:perf_hooks";
import { gzipSync } from "node:zlib";
import { canonicalJson, searchPublicIndex, SEARCH_INDEX_SCHEMA } from "../src/lib/searchIndex.ts";
import { searchPublicStatementsV3, PUBLIC_STATEMENT_SEARCH_V3_SCHEMA } from "../src/lib/publicStatementSearchV3.ts";

const count = Number(process.env.DP_SEARCH_BENCH_RECORDS ?? "250");
const rounds = Number(process.env.DP_SEARCH_BENCH_ROUNDS ?? "15");
if (!Number.isSafeInteger(count) || count < 1 || count > 2000 ||
    !Number.isSafeInteger(rounds) || rounds < 1 || rounds > 100) {
  throw new Error("BENCHMARK_BOUNDS_INVALID");
}
const hash = async (text) => {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Buffer.from(digest).toString("hex");
};
const v2Records = [];
const v3Records = [];
const quote = (i) => `La spesa nel settore ${i} costa 10 euro secondo il rapporto pubblico`;
for (let i = 0; i < count; i++) {
  const text = quote(i);
  const person = `Persona sintetica ${i % 20}`;
  const source = `Rapporto pubblico numero ${i % 50}`;
  const day = `2026-10-${String(i % 19 + 1).padStart(2, "0")}`;
  v2Records.push({
    id: `finding:${i}`, kind: "finding", title: text, subtitle: person + " · " + source,
    published_at: day + "T00:00:00Z", assessment: "SUPPORTED",
    route: `/dichiarazioni/finding-${i}/`, has_corrections: false,
    has_rights_of_reply: false, wording_type: "PARAPHRASE",
    source_wording_type: "VERBATIM_ORIGINAL", direct_quote_eligible: false,
    primary_terms: [text], secondary_terms: [person, source],
    person_id: `person:${i % 20}`, topic_ids: ["topic:benchmark"],
  });
  v3Records.push({
    statement_id: `statement:${String(i).padStart(4, "0")}`, version_id: "v1",
    statement_date: day, person_id: `person:${i % 20}`, person_name: person,
    person_route: `/persone/person-${i % 20}/`,
    statement_route: `/dichiarazioni/statement-${String(i).padStart(4, "0")}/`,
    topics: [{ topic_id: "topic:benchmark", topic_route: "/temi/benchmark/" }],
    original: {
      wording_type: "VERBATIM_ORIGINAL", text, language: "it",
      quote_sha256: await hash(text), locator: { start_char: 0, end_char: [...text].length },
    },
    source: {
      content_id: `content:${i}`, title: source, url: `https://example.org/${i}`,
      version_id: "v1", sha256: "a".repeat(64), kind: "WRITTEN",
    }, finding_id: null,
  });
}
const v2 = {
  schema_version: SEARCH_INDEX_SCHEMA, projection_schema_version: "dichiarazioni-pubbliche-public-v2",
  projection_sha256: "a".repeat(64), generated_at: "2026-10-19T12:00:00Z",
  index_sha256: "b".repeat(64), records: v2Records,
};
const v3Material = {
  schema_version: PUBLIC_STATEMENT_SEARCH_V3_SCHEMA, intersection_sha256: "c".repeat(64),
  source_dataset_sha256: "d".repeat(64), person_dataset_sha256: "e".repeat(64),
  generated_at: "2026-10-19T12:00:00Z", coverage_note: "Fixture synthetic public data",
  source_status: "READY", records: v3Records,
};
const v3 = { ...v3Material, index_sha256: await hash(canonicalJson(v3Material)) };
const pins = {
  intersectionSha256: v3.intersection_sha256, statementSha256: v3.source_dataset_sha256,
  personSha256: v3.person_dataset_sha256, indexSha256: v3.index_sha256,
};
const queries = ["spesa", "settore 20", "persona sintetica 5", "rapporto pubblico", "costa 10 euro"];
const cases = [
  { name: "v2", asset: v2, query: (q) => searchPublicIndex(v2, q) },
  { name: "v3", asset: v3, query: (q) => searchPublicStatementsV3(v3, pins, q, { sort: "relevance" }) },
];
const results = {};
for (const scenario of cases) {
  for (const q of queries) await scenario.query(q);
  global.gc?.();
  const heapBefore = process.memoryUsage().heapUsed;
  const samples = [];
  const hits = [];
  for (let i = 0; i < rounds; i++) {
    for (const query of queries) {
      const start = performance.now();
      const response = await scenario.query(query);
      samples.push(performance.now() - start);
      hits.push(response.records.length);
    }
  }
  global.gc?.();
  samples.sort((a, b) => a - b);
  const data = canonicalJson(scenario.asset);
  results[scenario.name] = {
    corpus: count, operations: samples.length,
    p50_ms: Number(samples[Math.floor(samples.length / 2)].toFixed(3)),
    p95_ms: Number(samples[Math.ceil(samples.length * 0.95) - 1].toFixed(3)),
    min_ms: Number(samples[0].toFixed(3)),
    max_ms: Number(samples[samples.length - 1].toFixed(3)),
    heap_used_before: heapBefore, heap_used_after_gc: process.memoryUsage().heapUsed,
    asset_bytes: Buffer.byteLength(data), asset_gzip_bytes: gzipSync(data).length,
    query_hits: hits.slice(0, queries.length),
  };
}
console.log(JSON.stringify({ node: process.version, queries, results }, null, 2));
