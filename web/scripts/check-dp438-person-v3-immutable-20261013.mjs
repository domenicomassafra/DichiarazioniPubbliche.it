/** DP-438 isolated public Person consumer: caller-owned alias/race isolation.
 * Synthetic-only approvals. No public route, publication or provider access.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readApprovedPersonV3, PUBLIC_PERSON_V3_SCHEMA } from "../src/lib/publicPersonV3.ts";
import { canonicalJson } from "../src/lib/searchIndex.ts";

const sha = (value) => createHash("sha256").update(value).digest("hex");
const quote = "Una dichiarazione soltanto sintetica.";
const original = {
  statement_id: "statement:demo",
  statement_route: "/dichiarazioni/statement-demo/",
  version_id: "statement-version:1",
  statement_date: "2026-10-10",
  content_id: "content:synthetic",
  source_title: "Fonte pubblica sintetica",
  source_url: "https://example.test/synthetic",
  source_version: "source-version:1",
  source_kind: "WRITTEN",
  locator: { start_char: 0, end_char: [...quote].length },
  original_text: quote,
  language: "it",
  quote_sha256: sha(quote),
  source_sha256: sha("FONTE-SINTETICA"),
  speech_act: "OPINION",
  finding_id: null,
  role_at_statement: null,
};
const role = {
  role_id: "role:synthetic",
  label: "Incarico verificato sintetico",
  organization: "Istituzione di prova",
  valid_from: "2020-01-01",
  valid_to: "2022-01-01",
  source_ref: "source:synthetic",
  source_url: "https://example.test/role",
};
const people = [
  {
    person_id: "person:approved",
    slug: "persona-approvata",
    route: "/persone/persona-approvata/",
    display_name: "Alex Dimostrativo",
    disambiguator: "Autore con dichiarazione",
    entity_version: "person-version:1",
    profile_scope: "PUBLIC",
    status: "PUBLISHED",
    roles: [role],
    statements: [original],
  },
  {
    person_id: "person:zero",
    slug: "persona-zero",
    route: "/persone/persona-zero/",
    display_name: "Alex Dimostrativo", // deliberately homonymous
    disambiguator: "Persona autonoma senza dichiarazioni",
    entity_version: "person-version:2",
    profile_scope: "PUBLIC",
    status: "PUBLISHED",
    roles: [],
    statements: [],
  },
];
const collection = (items = people) => ({
  schema_version: PUBLIC_PERSON_V3_SCHEMA,
  dataset_sha256: sha(canonicalJson(items)),
  people: items,
});
const options = (bundle, identifier) => ({
  allowPersonV3: true,
  expectedCollectionSha256: bundle.dataset_sha256,
  identifier,
});

// The Person consumer previously returned the caller's mutable dictionary.
// Later changes to a withheld name, role or statement became visible under
// the earlier approved release digest, including in the zero-record state.
for (const identifier of ["persona-approvata", "persona-zero"]) {
  const bundle = collection(structuredClone(people));
  const approved = structuredClone(bundle.people.find((p) => p.slug === identifier));
  const result = await readApprovedPersonV3(bundle, options(bundle, identifier));
  assert.deepEqual(result, approved);
  const callerOwned = bundle.people.find((p) => p.slug === identifier);
  callerOwned.display_name = "PRIVATE UNAPPROVED IDENTITY";
  callerOwned.disambiguator = "PRIVATE UNREVIEWED ALIAS";
  callerOwned.roles.push({ label: "PRIVATE UNREVIEWED ROLE" });
  if (callerOwned.statements.length) {
    callerOwned.statements[0].original_text = "PRIVATE RAW TRANSCRIPT";
    callerOwned.statements[0].source_url = "https://example.test/private";
    callerOwned.statements[0].locator.start_char = 99;
  }
  assert.deepEqual(result, approved, "approved Person aliases mutable private caller record");
  assert.doesNotMatch(JSON.stringify(result), /PRIVATE|UNREVIEWED|RAW TRANSCRIPT/);
  assert.equal(bundle.dataset_sha256, options(bundle, identifier).expectedCollectionSha256);
}

// Also race while a digest is awaited: validate the original signed/public
// collection and quoted bytes, then change caller data before continuation.
const concurrent = collection(structuredClone(people));
const expected = structuredClone(concurrent.people[0]);
const subtle = globalThis.crypto.subtle;
const originalDigest = subtle.digest;
let digestCalls = 0;
try {
  subtle.digest = async function (algorithm, data) {
    const hash = await originalDigest.call(this, algorithm, data);
    digestCalls += 1;
    if (digestCalls === 2) {
      concurrent.people[0].display_name = "PRIVATE CONCURRENT IDENTITY";
      concurrent.people[0].statements[0].original_text = "PRIVATE CONCURRENT QUOTE";
      concurrent.people[0].statements[0].source_url = "https://example.test/private-concurrent";
      concurrent.people[0].statements[0].locator.start_char = 42;
    }
    return hash;
  };
  const result = await readApprovedPersonV3(concurrent, options(concurrent, "person:approved"));
  assert.equal(digestCalls, 2, "real asynchronous collection and quotation digests were not exercised");
  assert.deepEqual(result, expected, "late SHA interleave returned unapproved Person original or alias");
} finally {
  subtle.digest = originalDigest;
}

// Same-name People remain separate public IDs and absent private members
// remain indistinguishable from unknown IDs; no derived status/score.
const pristine = collection(structuredClone(people));
const first = await readApprovedPersonV3(pristine, options(pristine, "person:approved"));
const zero = await readApprovedPersonV3(pristine, options(pristine, "person:zero"));
assert.equal(first.display_name, zero.display_name);
assert.notEqual(first.person_id, zero.person_id);
assert.equal(zero.statements.length, 0);
assert.equal(first.statements[0].finding_id, null);
assert.equal(await readApprovedPersonV3(pristine, options(pristine, "person:private")), null);
assert.equal(await readApprovedPersonV3(pristine, options(pristine, "person:unknown")), null);
assert.deepEqual(pristine.people, people);

console.log("DP438_PERSON_IMMUTABLE_PASS source-pinned zero, homonyms, post-validation and digest-race");
