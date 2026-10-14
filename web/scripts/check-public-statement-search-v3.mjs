import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";
import { performance } from "node:perf_hooks";
import { canonicalJson } from "../src/lib/searchIndex.ts";
import {
  buildPublicStatementSearchV3,
  validatePublicStatementSearchV3,
  searchPublicStatementsV3,
  serializePublicStatementSearchV3Url,
  parsePublicStatementSearchV3Url,
} from "../src/lib/publicStatementSearchV3.ts";

const root = fileURLToPath(new URL("../../", import.meta.url));
const python = String.raw`
import json
import copy
from dataclasses import replace
from dichiarazioni_pubbliche.public_projection import build_public_projection
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256
from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3
from test_dp438_public_person import identity
from test_dp435_public_statement_seam import SHA
from test_dp439_person_topic_v3 import published, make
source, bundle, people, roster, decisions = published()
full = make(bundle, people, decisions)
unmatched = make(bundle, people, ())
source.subjects[1].gates["rights"]["status"] = "REVOKED"
withdrawn_bundle = source.build()
withdrawn_bundle["topics"] = copy.deepcopy(bundle["topics"])
withdrawn_bundle["dataset_sha256"] = projection_dataset_sha256(withdrawn_bundle)
def public_people(public_bundle):
    return build_public_people_v3(
        roster, [identity(row) for row in roster], [], [],
        public_bundle=public_bundle,
        current_public_dataset_sha256=public_bundle["dataset_sha256"],
        allow_public_person_v3=True,
    )
after = make(withdrawn_bundle, public_people(withdrawn_bundle),
    tuple(replace(item, public_dataset_sha256=withdrawn_bundle["dataset_sha256"])
        for item in decisions))
for owner in source.subjects:
    owner.gates["publication"]["status"] = "REVOKED"
empty_bundle = source.build()
empty_bundle["topics"] = copy.deepcopy(bundle["topics"])
empty_bundle["dataset_sha256"] = projection_dataset_sha256(empty_bundle)
empty = make(empty_bundle, public_people(empty_bundle), ())
special_source, original_special_bundle, _, _, special_decisions = published()
owner = special_source.subjects[0]
quote = ' «Café»\tora\n '
owner.source_text = "Contesto: " + quote + "Fine."
offset = owner.source_text.index(quote)
owner.row["original_text"] = quote
owner.row["source_sha256"] = SHA(owner.source_text)
owner.row["locator"] = {"start_char": offset, "end_char": offset + len(quote)}
for gate in owner.gates.values():
    gate["source_sha256"] = SHA(owner.source_text)
    gate["quote_sha256"] = SHA(quote)
    gate["span_start"], gate["span_end"] = offset, offset + len(quote)
special_bundle = special_source.build()
special_bundle["topics"] = copy.deepcopy(original_special_bundle["topics"])
special_bundle["dataset_sha256"] = projection_dataset_sha256(special_bundle)
special_decisions = tuple(
    replace(item, public_dataset_sha256=special_bundle["dataset_sha256"],
        **({"quote_sha256": SHA(quote), "source_sha256": SHA(owner.source_text)}
           if item.statement_id == "statement:1" else {}))
    for item in special_decisions)
special = make(special_bundle, public_people(special_bundle), special_decisions)
print(json.dumps({"full": full, "withdrawn": after, "unmatched": unmatched, "empty": empty,
    "special": special}, ensure_ascii=False))
`;
const observed = spawnSync("python3", ["-c", python], {
  cwd: root, encoding: "utf8",
  env: { ...process.env, PYTHONPATH: "poc:tests", PYTHONDONTWRITEBYTECODE: "1" },
  timeout: 12000,
});
assert.equal(observed.status, 0, observed.stderr);
const { full: actualDp439Join, withdrawn, unmatched, empty, special } = JSON.parse(observed.stdout);
assert.equal(actualDp439Join.result_count, 4);
assert.equal(actualDp439Join.schema_version, "public-person-topic-v3-opt-in");

const pins = {
  intersectionSha256: actualDp439Join.dataset_sha256,
  statementSha256: actualDp439Join.source_dataset_sha256,
  personSha256: actualDp439Join.person_dataset_sha256,
};
const index = await buildPublicStatementSearchV3(actualDp439Join, pins);
const trusted = { ...pins, indexSha256: index.index_sha256 };
assert.deepEqual(await validatePublicStatementSearchV3(index, trusted), index);

assert.equal(index.records.length, 3, "each unique original Statement is indexed once, not once per Topic");
assert.deepEqual(index.records.map((row) => row.statement_id), ["statement:1", "statement:2", "statement:3"]);
assert.equal(index.records.find((row) => row.statement_id === "statement:2").topics.length, 2);
assert.equal(index.records.every((row) => row.original.wording_type === "VERBATIM_ORIGINAL"), true);
assert.equal(index.records.every((row) => row.finding_id === null), true);
assert.equal(index.records.every((row) => row.statement_route === "/dichiarazioni/" + row.statement_id.replace(":", "-") + "/"), true);
assert.equal(index.records.every((row) => row.source.url.startsWith("https:") && row.source.sha256.length === 64), true);
assert.equal(index.records.every((row) => row.original.quote_sha256.length === 64 && row.original.locator.start_char >= 0), true);
assert.equal(index.records.every((row) => !Object.hasOwn(row, "archive_added_at") &&
  !Object.hasOwn(row, "declared_at")), true,
  "the approved v3 search schema exposes only statement_date; archive-added time has no authority");
const before = canonicalJson(index);
assert.equal(canonicalJson(await buildPublicStatementSearchV3(actualDp439Join, pins)), before);
assert.deepEqual(await validatePublicStatementSearchV3(structuredClone(index), trusted), index);
actualDp439Join.data[0].statement.original.text = "Private late mutation";
assert.equal(canonicalJson(index), before, "indexed original must not alias mutable source object");
const fixture = JSON.parse(observed.stdout).full;

const result = (query, filters = {}, asset = index, expected = trusted) =>
  searchPublicStatementsV3(asset, expected, query, filters);
assert.deepEqual((await result("")).records.map((row) => row.statement_id),
  ["statement:3", "statement:2", "statement:1"],
  "default recent orders the Statement day, not archive ingestion or index creation");
assert.deepEqual((await result("costa 10 euro")).records.map((row) => row.statement_id),
  ["statement:3", "statement:2", "statement:1"], "exact original words are searchable");
assert.equal((await result("Documento Dimostrativo")).records.length, 3, "approved source title is a secondary term");
assert.equal((await result("persona sintetica person:B")).records[0].person_id, "person:B");
assert.equal((await result("economia")).status, "NO_MATCH",
  "Topic label/semantic similarity is never invented from Topic ID or URL");
assert.equal((await result("opinione privata mai approvata")).result_count, 0);
assert.equal((await result("x".repeat(201))).status, "QUERY_TOO_LONG");
assert.equal((await result("")).result_count, 3);
assert.deepEqual((await result("", { personId: "person:A", topicId: "topic:economia" }))
  .records.map((row) => row.statement_id), ["statement:2", "statement:1"]);
assert.deepEqual((await result("", { personId: "person:B", topicId: "topic:economica" })).records, []);
assert.deepEqual((await result("", { topicId: "topic:economica" })).records.map((row) => row.statement_id), ["statement:2"]);
assert.deepEqual((await result("", { personId: "person:private" })).records, []);
assert.deepEqual((await result("", { personId: "person:private" })).records,
  (await result("", { personId: "person:unknown" })).records);
assert.deepEqual((await result("", { sort: "old" })).records.map((row) => row.statement_id),
  ["statement:1", "statement:2", "statement:3"]);
assert.equal((await result("costa", { sort: "relevance" })).result_count, 3);

const state = { query: "frase café", personId: "person:A", topicId: "topic:economia", sort: "old" };
const encoded = serializePublicStatementSearchV3Url(state);
assert.deepEqual(parsePublicStatementSearchV3Url("?" + encoded), state);
assert.deepEqual(parsePublicStatementSearchV3Url(serializePublicStatementSearchV3Url({
  query: "", personId: null, topicId: null, sort: "recent",
})), { query: "", personId: null, topicId: null, sort: "recent" });
for (const unsafeUrl of [
  "?persona=person%3Aprivate%2F..", "?tema=%00", "?persona=person%3AA&persona=person%3AB",
  "?ordine=ranking", "?q=" + "x".repeat(201), "?topic=unreviewed",
]) assert.throws(() => parsePublicStatementSearchV3Url(unsafeUrl), /PUBLIC_V3_SEARCH_URL_INVALID/);

const newPins = (join) => ({
  intersectionSha256: join.dataset_sha256,
  statementSha256: join.source_dataset_sha256,
  personSha256: join.person_dataset_sha256,
});
const after = await buildPublicStatementSearchV3(withdrawn, newPins(withdrawn));
const trustedAfter = { ...newPins(withdrawn), indexSha256: after.index_sha256 };
assert.equal(after.records.length, 2);
assert.equal(after.records.some((row) => row.statement_id === "statement:2"), false);
assert.equal((await result("", {}, after, trustedAfter)).result_count, 2);
const specialIndex = await buildPublicStatementSearchV3(special, newPins(special));
const specialOriginal = specialIndex.records.find((row) => row.statement_id === "statement:1").original.text;
assert.equal(specialOriginal, ' «Café»\tora\n ', "source-authenticated tab/newline/edge spaces are preserved byte for byte");
assert.deepEqual((await result("Cafe", {}, specialIndex,
  { ...newPins(special), indexSha256: specialIndex.index_sha256 })).records.map((row) => row.statement_id),
  ["statement:1"], "diacritic-insensitive retrieval still returns the unmodified original");
await assert.rejects(() => validatePublicStatementSearchV3(index, trustedAfter),
  /PUBLIC_V3_INDEX_STALE_OR_INCOMPATIBLE/, "old approved release must not survive withdrawal");
await assert.rejects(() => buildPublicStatementSearchV3(fixture, newPins(withdrawn)),
  /PUBLIC_V3_JOIN_NOT_CURRENT/, "old source join cannot be rebuilt under new published fingerprint");

const emptyIndex = await buildPublicStatementSearchV3(empty, newPins(empty));
assert.equal(emptyIndex.records.length, 0);
assert.equal((await result("", {}, emptyIndex,
  { ...newPins(empty), indexSha256: emptyIndex.index_sha256 })).status, "EMPTY_PUBLIC_CORPUS");
const noIntersection = await buildPublicStatementSearchV3(unmatched, newPins(unmatched));
assert.equal((await result("", {}, noIntersection,
  { ...newPins(unmatched), indexSha256: noIntersection.index_sha256 })).status, "EMPTY_PUBLIC_INTERSECTION");
assert.equal((await result("not-found")).status, "NO_MATCH");

const tamperedQuote = structuredClone(index);
tamperedQuote.records[0].original.text = "Private!";
await assert.rejects(() => result("", {}, tamperedQuote), /PUBLIC_V3_INDEX_TAMPERED/);
const tamperedTopic = structuredClone(index);
tamperedTopic.records[1].topics[0].topic_id = "topic:private";
await assert.rejects(() => result("", {}, tamperedTopic), /PUBLIC_V3_INDEX_TAMPERED/);
const tamperedRoute = structuredClone(index);
tamperedRoute.records[0].statement_route = "//outside.test/secret";
await assert.rejects(() => result("", {}, tamperedRoute), /PUBLIC_V3_INDEX_TAMPERED/);

async function rehash(value) {
  const { index_sha256: _claimed, ...material } = value;
  const bytes = new TextEncoder().encode(canonicalJson(material));
  const sha = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(sha), (n) => n.toString(16).padStart(2, "0")).join("");
}
// An independent issuer digest is necessary, but cannot silently authorize a
// new date field absent from the current source/schema decision. A future
// archival-addition field needs a separately reviewed upstream contract.
for (const [field, value] of [
  ["archive_added_at", "2026-10-14T12:00:00Z"],
  ["declared_at", "2026-10-14T12:00:00Z"],
]) {
  const dateExpansion = structuredClone(index);
  dateExpansion.records[0][field] = value;
  dateExpansion.index_sha256 = await rehash(dateExpansion);
  const dateExpansionPins = { ...trusted, indexSha256: dateExpansion.index_sha256 };
  await assert.rejects(() => result("", {}, dateExpansion,
    dateExpansionPins),
  /PUBLIC_V3_INDEX_RECORD_INVALID/,
  "unauthorized date field must be rejected even when the entire artifact is repinned: " + field);
}
for (const forged of [tamperedQuote, tamperedTopic, tamperedRoute]) {
  forged.index_sha256 = await rehash(forged);
  await assert.rejects(() => result("", {}, forged), /PUBLIC_V3_INDEX_STALE_OR_INCOMPATIBLE/,
    "attacker rehashing an asset is not independently published approval");
}
const internalForgery = structuredClone(fixture);
internalForgery.data[0].statement.original.text = "Private forged words";
await assert.rejects(() => buildPublicStatementSearchV3(internalForgery, newPins(fixture)),
  /PUBLIC_V3_JOIN_TAMPERED/);
await assert.rejects(() => buildPublicStatementSearchV3({ schema_version: "dichiarazioni-pubbliche-public-v2" }, pins),
  /PUBLIC_V3_JOIN_NOT_CURRENT/);
assert.equal(before.includes("review_provenance"), false);
for (const token of ["provider_receipt", "raw_transcript", "person_score", "review:membership", "private_candidate", "assessment"]) {
  assert.equal(before.includes(token), false, "private/derived leaked in static asset: " + token);
}

const start = performance.now();
for (let i = 0; i < 10; i++) await result("costa", { personId: "person:A", topicId: "topic:economia" });
const elapsed = (performance.now() - start) / 10;
assert.ok(elapsed < 100, "bounded local search must be comfortably under 100 ms");
const bytes = Buffer.byteLength(before, "utf8");
const gzipBytes = gzipSync(before).length;
assert.ok(gzipBytes < 1024 * 1024, "static asset budget 1 MiB compressed");
console.log(`public statement search v3 PASS (DP439 original 4 memberships → 3 unique records; revoked → 2; ${bytes} bytes, ${gzipBytes} gzip bytes, ${elapsed.toFixed(1)} ms/query)`);
