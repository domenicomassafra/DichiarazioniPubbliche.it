import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { canonicalJson } from "../src/lib/searchIndex.ts";
import { buildPublicStatementSearchV3 } from "../src/lib/publicStatementSearchV3.ts";
import { preflightPublicV3CrossReaderRelease } from "../src/lib/publicV3CrossReaderRelease.ts";

const root = fileURLToPath(new URL("../../", import.meta.url));
const python = String.raw`
import json, copy
from dataclasses import replace
from test_dp439_person_topic_v3 import published, make
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256
from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3
from test_dp438_public_person import identity
source, bundle, people, roster, decisions = published()
full = make(bundle, people, decisions)
unmatched = make(bundle, people, ())
source.subjects[1].gates["rights"]["status"] = "REVOKED"
withdrawn_bundle = source.build()
withdrawn_bundle["topics"] = copy.deepcopy(bundle["topics"])
withdrawn_bundle["dataset_sha256"] = projection_dataset_sha256(withdrawn_bundle)
new_people = build_public_people_v3(
    roster, [identity(row) for row in roster], [], [],
    public_bundle=withdrawn_bundle,
    current_public_dataset_sha256=withdrawn_bundle["dataset_sha256"],
    allow_public_person_v3=True)
withdrawn_join = make(withdrawn_bundle, new_people,
    tuple(replace(item, public_dataset_sha256=withdrawn_bundle["dataset_sha256"])
      for item in decisions))
for owner in source.subjects:
    owner.gates["publication"]["status"] = "REVOKED"
empty_bundle = source.build()
empty_bundle["topics"] = copy.deepcopy(bundle["topics"])
empty_bundle["dataset_sha256"] = projection_dataset_sha256(empty_bundle)
empty_people = build_public_people_v3(
    roster, [identity(row) for row in roster], [], [],
    public_bundle=empty_bundle,
    current_public_dataset_sha256=empty_bundle["dataset_sha256"],
    allow_public_person_v3=True)
empty_join = make(empty_bundle, empty_people, ())
print(json.dumps({"people": people, "full": full, "unmatched": unmatched,
    "withdrawn_people": new_people, "withdrawn": withdrawn_join,
    "empty_people": empty_people, "empty_join": empty_join}, ensure_ascii=False))
`;
const result = spawnSync("python3", ["-c", python], {
  cwd: root, encoding: "utf8", timeout: 12000,
  env: { ...process.env, PYTHONPATH: "poc:tests", PYTHONDONTWRITEBYTECODE: "1" },
});
assert.equal(result.status, 0, result.stderr);
const { people, full, unmatched, withdrawn_people, withdrawn, empty_people, empty_join } =
  JSON.parse(result.stdout);
const digest = (value) => createHash("sha256").update(canonicalJson(value)).digest("hex");
const pinsOf = (join, index) => ({
  allowV3Preview: true,
  personSha256: join.person_dataset_sha256,
  statementSha256: join.source_dataset_sha256,
  intersectionSha256: join.dataset_sha256,
  indexSha256: index.index_sha256,
  validUntil: "2099-10-11T00:00:00Z",
});
const indexOf = (join) => buildPublicStatementSearchV3(join, {
  personSha256: join.person_dataset_sha256,
  statementSha256: join.source_dataset_sha256,
  intersectionSha256: join.dataset_sha256,
});
const index = await indexOf(full);
const pins = pinsOf(full, index);
const review = await preflightPublicV3CrossReaderRelease({people, join: full, index}, pins);
assert.equal(review.status, "CONSISTENT_PREVIEW_ONLY");
assert.equal(review.publicationAuthorized, false);
assert.equal(review.personCount, 2);
assert.equal(review.statementCount, 3);
assert.equal(review.membershipCount, 4);
assert.deepEqual(review.statementRoutes,
  ["/dichiarazioni/statement-1/", "/dichiarazioni/statement-2/", "/dichiarazioni/statement-3/"]);
assert.deepEqual(review.personRoutes,
  ["/persone/persona-a/", "/persone/persona-b/"]);
assert.equal(JSON.stringify(review).includes("costa 10 euro"), false, "no source body in release receipt");
assert.deepEqual(await preflightPublicV3CrossReaderRelease({people, join: full, index}, pins), review);

const emptyIndex = await indexOf(unmatched);
const empty = await preflightPublicV3CrossReaderRelease(
  {people, join: unmatched, index: emptyIndex}, pinsOf(unmatched, emptyIndex));
assert.equal(empty.statementCount, 0);
assert.equal(empty.membershipCount, 0);
assert.equal(empty.sourceStatus, "EMPTY_PUBLIC_INTERSECTION");
const zeroIndex = await indexOf(empty_join);
const zero = await preflightPublicV3CrossReaderRelease(
  {people: empty_people, join: empty_join, index: zeroIndex}, pinsOf(empty_join, zeroIndex));
assert.equal(zero.sourceStatus, "EMPTY_PUBLIC_CORPUS");
assert.equal(zero.statementCount, 0);
assert.equal(zero.topicRoutes.length, 0);

const nextIndex = await indexOf(withdrawn);
const next = await preflightPublicV3CrossReaderRelease(
  {people: withdrawn_people, join: withdrawn, index: nextIndex}, pinsOf(withdrawn, nextIndex));
assert.equal(next.statementCount, 2);
assert.equal(next.statementRoutes.includes("/dichiarazioni/statement-2/"), false);
await assert.rejects(
  () => preflightPublicV3CrossReaderRelease({people, join: full, index}, pinsOf(withdrawn, nextIndex)),
  /PUBLIC_(?:PERSON_V3_|V3_)/,
  "old release refused after a version/rights withdrawal");

// Three separately self-consistent, independently pinned assets can still
// disagree semantically. A single-release preflight must compare them.
const alteredPeople = structuredClone(people);
const person = alteredPeople.people.find((row) => row.person_id === "person:A");
const item = person.statements.find((row) => row.statement_id === "statement:1");
const original = item.original_text;
item.original_text = "X".repeat([...original].length);
item.quote_sha256 = createHash("sha256").update(item.original_text).digest("hex");
alteredPeople.dataset_sha256 = digest(alteredPeople.people);
const splitJoin = structuredClone(full);
splitJoin.person_dataset_sha256 = alteredPeople.dataset_sha256;
const {dataset_sha256: _ignore, provider_calls: _p, ...joinBody} = splitJoin;
splitJoin.dataset_sha256 = digest(joinBody);
const splitIndex = await indexOf(splitJoin);
await assert.rejects(
  () => preflightPublicV3CrossReaderRelease(
    {people: alteredPeople, join: splitJoin, index: splitIndex}, pinsOf(splitJoin, splitIndex)),
  /PUBLIC_V3_CROSS_READER_MISMATCH/,
  "all three hashes locally match, yet the Person shows different source words");

const missingPeople = structuredClone(people);
missingPeople.people.find((row) => row.person_id === "person:A").statements =
  missingPeople.people.find((row) => row.person_id === "person:A").statements
    .filter((row) => row.statement_id !== "statement:1");
missingPeople.dataset_sha256 = digest(missingPeople.people);
const splitMissingJoin = structuredClone(full);
splitMissingJoin.person_dataset_sha256 = missingPeople.dataset_sha256;
const {dataset_sha256: _d, provider_calls: _c, ...missingBody} = splitMissingJoin;
splitMissingJoin.dataset_sha256 = digest(missingBody);
const missingIndex = await indexOf(splitMissingJoin);
await assert.rejects(
  () => preflightPublicV3CrossReaderRelease(
    {people: missingPeople, join: splitMissingJoin, index: missingIndex},
    pinsOf(splitMissingJoin, missingIndex)),
  /PUBLIC_V3_CROSS_READER_MISMATCH/,
  "index may not expose a Statement omitted from the authoritative Person archive");

await assert.rejects(
  () => preflightPublicV3CrossReaderRelease({people, join: full, index}, {...pins, allowV3Preview: false}),
  /PUBLIC_V3_RELEASE_OPT_IN_REQUIRED/);
await assert.rejects(
  () => preflightPublicV3CrossReaderRelease({people, join: full, index},
    {...pins, validUntil: "2020-01-01T00:00:00Z"}),
  /PUBLIC_V3_RELEASE_EXPIRED/);
console.log("public v3 cross-reader release PASS (3 matching sources, 4 memberships, 2 post-withdrawal; split-brain/removed-source/expiry refused)");
