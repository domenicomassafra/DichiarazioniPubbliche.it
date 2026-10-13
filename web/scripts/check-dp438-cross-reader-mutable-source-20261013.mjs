/** DP-438: real Python zero-Person projection, cross-reader digest-race regression.
 * Synthetic fixture and independently issued test pins; never publication authority.
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { preflightPublicV3CrossReaderRelease } from "../src/lib/publicV3CrossReaderRelease.ts";
import { buildPublicStatementSearchV3 } from "../src/lib/publicStatementSearchV3.ts";

const repo = fileURLToPath(new URL("../../", import.meta.url));
const generate = String.raw`
import json
from test_dp438_public_person import person, identity, bundle
from test_dp439_person_topic_v3 import make
from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3
source = bundle()
first = person('person:zero-a', slug='zero-a', name='Alex Dimostrativo')
second = person('person:zero-b', slug='zero-b', name='Alex Dimostrativo')
first['disambiguator'] = 'Ente A'
second['disambiguator'] = 'Ente B'
people = build_public_people_v3([first, second], [identity(first), identity(second)], [], [],
    public_bundle=source, current_public_dataset_sha256=source['dataset_sha256'], allow_public_person_v3=True)
join = make(source, people, ())
print(json.dumps({'people': people, 'join': join}, ensure_ascii=False))
`;
const generated = spawnSync("python3", ["-c", generate], {
  cwd: repo, encoding: "utf8", timeout: 15000,
  env: { ...process.env, PYTHONPATH: "poc:tests", PYTHONDONTWRITEBYTECODE: "1" },
});
assert.equal(generated.status, 0, generated.stderr || generated.stdout);
const fixture = JSON.parse(generated.stdout);
assert.equal(fixture.people.people.length, 2);
assert.equal(fixture.join.result_count, 0);
const releasePins = {
  personSha256: fixture.people.dataset_sha256,
  statementSha256: fixture.join.source_dataset_sha256,
  intersectionSha256: fixture.join.dataset_sha256,
};
const index = await buildPublicStatementSearchV3(fixture.join, releasePins);
const pins = { ...releasePins, allowV3Preview: true,
  indexSha256: index.index_sha256, validUntil: "2099-10-12T00:00:00Z" };
const expectedRoutes = fixture.people.people.map(p => p.route).sort();
assert.equal(expectedRoutes.length, 2);

// Every isolated scenario starts from freshly approved bytes and independent pins.
// Mutate the ORIGINAL caller objects only after a real SHA digest has run.
const scenarios = [
  ["person identity and route", value => {
    value.people.people[0].route = "/persone/private-unreviewed-route/";
    value.people.people[0].display_name = "PRIVATE UNREVIEWED IDENTITY";
  }],
  ["join source and membership", value => {
    value.join.coverage_note = "PRIVATE UNREVIEWED COVERAGE";
    value.join.data.push({ statement_id: "private:unreviewed" });
  }],
  ["search index", value => {
    value.index.coverage_note = "PRIVATE UNREVIEWED SEARCH";
    value.index.records.push({ statement_id: "private:unreviewed" });
  }],
  ["caller pins", (_value, issuedPins) => {
    issuedPins.personSha256 = "f".repeat(64);
    issuedPins.indexSha256 = "f".repeat(64);
  }],
];

for (const [label, mutation] of scenarios) {
  const caller = structuredClone({ people: fixture.people, join: fixture.join, index });
  const callerPins = structuredClone(pins);
  const subtle = globalThis.crypto.subtle;
  const originalDigest = subtle.digest;
  let calls = 0;
  try {
    subtle.digest = async function (algorithm, data) {
      const result = await originalDigest.call(this, algorithm, data);
      if (++calls === 1) mutation(caller, callerPins);
      return result;
    };
    const result = await preflightPublicV3CrossReaderRelease(caller, callerPins);
    assert(calls >= 1, `${label}: no async digest was exercised`);
    assert.equal(result.status, "CONSISTENT_PREVIEW_ONLY", label);
    assert.equal(result.publicationAuthorized, false);
    assert.equal(result.personCount, 2);
    assert.equal(result.statementCount, 0);
    assert.deepEqual(result.personRoutes, expectedRoutes, label);
    assert.deepEqual(result.statementRoutes, []);
    assert.equal(result.releasePins.personSha256, pins.personSha256);
    assert.equal(result.releasePins.indexSha256, pins.indexSha256);
    assert.doesNotMatch(JSON.stringify(result), /PRIVATE|UNREVIEWED/i);
  } finally {
    subtle.digest = originalDigest;
  }
}
const baseline = await preflightPublicV3CrossReaderRelease(
  { people: fixture.people, join: fixture.join, index }, pins);
assert.deepEqual(baseline.personRoutes, expectedRoutes);

// An independently valid release expires *during* an asynchronous digest.
// A successful preflight at the earlier clock must never authorize a result
// after validUntil, even when the source bytes remain intact.
{
  const now = Date.now;
  const originalDigest = globalThis.crypto.subtle.digest;
  const start = now();
  const end = start + 5_000;
  let clock = start;
  let digests = 0;
  try {
    Date.now = () => clock;
    globalThis.crypto.subtle.digest = async function (algorithm, bytes) {
      const value = await originalDigest.call(this, algorithm, bytes);
      if (++digests === 1) clock = end + 1_000;
      return value;
    };
    await assert.rejects(preflightPublicV3CrossReaderRelease(
      { people: fixture.people, join: fixture.join, index },
      { ...pins, validUntil: new Date(end).toISOString() }),
    /PUBLIC_V3_RELEASE_EXPIRED/, "late cross-reader SHA accepted an expired release");
    assert(digests >= 1, "cross-reader expiry hook did not exercise SHA");
  } finally {
    Date.now = now;
    globalThis.crypto.subtle.digest = originalDigest;
  }
}
console.log("DP438_CROSS_READER_MUTABLE_SOURCE_PASS real Python zero-Person, source/join/index/pin/expiry races");
