/** Synthetic DP-408 Trace acceptance: one public relation ID must retain one
 * reviewed meaning, not merge unrelated statements under a first review. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const relationsPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src/lib/relations.ts");
const source = ts.transpileModule(readFileSync(relationsPath, "utf8"), {
  fileName: relationsPath,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const module = { exports: {} };
new Function("require", "module", "exports", source)(
  (id) => {
    if (id !== "./format") throw new Error("Unexpected dependency: " + id);
    return { relationSlug: (id) => id.replaceAll(":", "-") };
  }, module, module.exports,
);
const { collectPublicTraces } = module.exports;
const relation = (id, related_claim_id, overrides = {}) => ({
  id, related_claim_id, relation_type: "UPDATE", relation_version: "relation-v1",
  review_event_id: "review:approved-one", rationale_codes: ["REVIEWED_TIMELINE"],
  status: "APPROVED", role: "LEFT", related_claim: "Synthetic statement",
  ...overrides,
});
const statement = (name, relations = []) => ({
  claim_id: "claim:" + name, finding_id: "finding:" + name,
  source: { published_at: "2026-10-01T10:00:00Z" },
  finding: { published_at: "2026-10-10T10:00:00Z" },
  relations,
});
const a = statement("A", [relation("relation:one", "claim:B")]);
const b = statement("B", [relation("relation:one", "claim:A")]);
const good = collectPublicTraces({ dossiers: [a, b] });
assert.equal(good.length, 1, "approved reciprocal edges must still form one trace");
assert.deepEqual(good[0].participants.map((row) => row.finding_id), ["finding:A", "finding:B"]);

// Independent pair reuses the same ID with a different review receipt.
const c = statement("C", [relation("relation:one", "claim:D", {
  review_event_id: "review:approved-two",
})]);
const d = statement("D");
const e = statement("E", [relation("relation:separate", "claim:F")]);
const f = statement("F");
const collided = collectPublicTraces({ dossiers: [a, b, c, d, e, f] });
assert.deepEqual(collided.map((trace) => trace.id), ["relation:separate"],
  "collision must fail closed; independent reviewed traces survive");
assert.deepEqual(collided[0].participants.map((row) => row.finding_id), ["finding:E", "finding:F"]);
// The source of conflict may be any approved provenance field, not merely
// the review receipt. The collector must not keep the first visible edge.
for (const override of [
  { relation_type: "CLARIFICATION" },
  { relation_version: "relation-v2" },
  { rationale_codes: ["DIFFERENT_REVIEWED_SCOPE"] },
]) {
  const conflicting = statement("C", [relation("relation:one", "claim:D", override)]);
  const rows = collectPublicTraces({ dossiers: [a, b, conflicting, d, e, f] });
  assert.deepEqual(rows.map((trace) => trace.id), ["relation:separate"],
    "public Trace must be held when approved relation metadata conflict: " + JSON.stringify(override));
}
// Rationale sets can be serialized in a different order without creating
// different reviewed meaning. This must not suppress a valid reviewed pair.
const orderedCodes = ["REVIEWED_TIMELINE", "SCOPE_APPROVED"];
const first = statement("A", [relation("relation:one", "claim:B", {
  rationale_codes: orderedCodes,
})]);
const second = statement("B", [relation("relation:one", "claim:A", {
  rationale_codes: [...orderedCodes].reverse(),
})]);
assert.equal(collectPublicTraces({ dossiers: [first, second] }).length, 1,
  "approved rationale code ordering must not prevent a valid reciprocal Trace");
// An earlier or later matching edge must not resurrect a rejected relation ID.
const later = statement("G", [relation("relation:one", "claim:A")]);
assert.deepEqual(collectPublicTraces({ dossiers: [a, b, c, d, later, e, f] })
  .map((trace) => trace.id), ["relation:separate"],
  "later matching edges cannot resurrect an ID with a conflicting receipt");
console.log("DP-408 Trace review consistency PASS (synthetic approved edges; conflicts fail closed)");
