/**
 * DP-436 cross-consumer verbatim parity: ONE governed release, four independent
 * surfaces — static search index (TypeScript), API v3 wire record, JSON-LD and
 * N-Triples (Python serializers).
 *
 * The existing gates compare API/JSON-LD/N-Triples with each other (Python) and
 * the index with the Person archive (publicV3CrossReaderRelease.ts). Nothing
 * compared the *cross-language* pair, so a release could ship identical
 * fingerprints with two different quotations. This gate refuses that.
 *
 * Synthetic fixtures only: it grants no right, approves no source and publishes
 * nothing. Run it unchanged against a real authorized release when #468/#98
 * produce one.
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { canonicalJson } from "../src/lib/searchIndex.ts";
import {
  buildPublicStatementSearchV3,
  validatePublicStatementSearchV3,
} from "../src/lib/publicStatementSearchV3.ts";

const root = fileURLToPath(new URL("../../", import.meta.url));
const MISMATCH = "DP436_CROSS_CONSUMER_MISMATCH";
const BASE = "https://dichiarazionipubbliche.it";
const SCHEMA = "https://schema.org/";
const DP = BASE + "/vocab#";

const python = String.raw`
import json, copy
from dataclasses import replace
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256
from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3
from test_dp438_public_person import identity
from test_dp435_public_statement_seam import SHA
from test_dp439_person_topic_v3 import published, make
from dichiarazioni_pubbliche.public_statement_readers_v3 import (
    get_public_statement_v3, list_public_statements_v3)
from dichiarazioni_pubbliche.public_api import PublicApiError
from dichiarazioni_pubbliche.linked_data import (
    projection_statement_v3_jsonld, projection_statement_v3_ntriples)

def surfaces(bundle):
    return {
        "bundle_dataset": bundle["dataset_sha256"],
        "schema": bundle["schema_version"],
        "api": list_public_statements_v3(
            bundle, allow_statement_v3=True,
            current_public_dataset_sha256=bundle["dataset_sha256"]),
        "jsonld": projection_statement_v3_jsonld(bundle, allow_statement_v3=True),
        "nt": projection_statement_v3_ntriples(bundle, allow_statement_v3=True),
    }

def public_people(public_bundle):
    return build_public_people_v3(
        roster, [identity(row) for row in roster], [], [],
        public_bundle=public_bundle,
        current_public_dataset_sha256=public_bundle["dataset_sha256"],
        allow_public_person_v3=True)

def rebuild(source, previous_bundle, previous_decisions, content_ids=None):
    """Re-emit the release and its independent join after a fixture correction."""
    bundle = source.build()
    bundle["topics"] = copy.deepcopy(previous_bundle["topics"])
    bundle["dataset_sha256"] = projection_dataset_sha256(bundle)
    people = public_people(bundle)
    decisions = tuple(
        replace(item, public_dataset_sha256=bundle["dataset_sha256"],
                **({"content_id": content_ids[item.statement_id]}
                   if content_ids and item.statement_id in content_ids else {}))
        for item in previous_decisions)
    return bundle, decisions, make(bundle, people, decisions)

source, bundle, people, roster, decisions = published()
# The synthetic source reuses content:B for two *different* source documents.
# A public content resource has exactly one canonical URL (content_item.url), so
# give the third Statement its own content id: a real release cannot serve two
# source URLs for one content node.
def one_source_per_content(source):
    # Give the third Statement its own content id (see note above).
    third = source.subjects[2]
    third.row["content_id"] = "content:C"
    for gate in third.gates.values():
        gate["content_id"] = "content:C"

one_source_per_content(source)
bundle, decisions, full_join = rebuild(
    source, bundle, decisions, {"statement:3": "content:C"})

# Withdrawal: one Statement's rights are revoked; the release must drop it from
# every surface at once, never only from the reader that happens to re-check.
source.subjects[1].gates["rights"]["status"] = "REVOKED"
withdrawn_bundle, _, withdrawn_join = rebuild(source, bundle, decisions)

# The un-corrected synthetic release keeps two source URLs on one content node.
# N-Triples cannot state which URL a Statement came from, so the gate must
# refuse it instead of silently choosing one.
shared_source, shared_bundle, _, _, shared_decisions = published()
shared_bundle, _, _ = rebuild(shared_source, shared_bundle, shared_decisions)
try:
    get_public_statement_v3(
        withdrawn_bundle, "statement:2", allow_statement_v3=True,
        current_public_dataset_sha256=withdrawn_bundle["dataset_sha256"])
    withdrawn_detail = {"status": "LEAKED"}
except PublicApiError as exc:
    withdrawn_detail = {"status": exc.status, "code": exc.code}

# Byte fidelity: tabs, newlines and edge spaces inside an approved verbatim span
# must never be trimmed by one consumer and preserved by another.
special_source, original_special_bundle, _, _, special_decisions = published()
one_source_per_content(special_source)
owner = special_source.subjects[0]
quote = " «Café»\tora\n "
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
            **({"content_id": "content:C"} if item.statement_id == "statement:3" else {}),
            **({"quote_sha256": SHA(quote), "source_sha256": SHA(owner.source_text)}
               if item.statement_id == "statement:1" else {}))
    for item in special_decisions)
special_join = make(special_bundle, public_people(special_bundle), special_decisions)

print(json.dumps({
    "full": {"join": full_join, **surfaces(bundle)},
    "withdrawn": {"join": withdrawn_join, **surfaces(withdrawn_bundle)},
    "withdrawn_detail": withdrawn_detail,
    "special": {"join": special_join, **surfaces(special_bundle)},
    "shared_content": projection_statement_v3_ntriples(
        shared_bundle, allow_statement_v3=True),
}, ensure_ascii=False))
`;

const build = () => {
  const result = spawnSync("python3", ["-c", python], {
    cwd: root,
    encoding: "utf8",
    timeout: 20000,
    env: { ...process.env, PYTHONPATH: "poc:tests", PYTHONDONTWRITEBYTECODE: "1" },
  });
  assert.equal(result.status, 0, "governed release build failed: " + result.stderr);
  return result.stdout;
};

/** N-Triples literal escaping, re-implemented here on purpose: a shared helper
 * would make the comparison echo the serializer instead of checking it. */
const escapeLiteral = (value) =>
  [...value].map((char) => {
    const simple = { "\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t" }[char];
    if (simple) return simple;
    const point = char.codePointAt(0);
    return point < 32 || point === 127
      ? "\\u" + point.toString(16).toUpperCase().padStart(4, "0")
      : char;
  }).join("");

const unescapeLiteral = (value) => {
  const simple = { "\\\\": "\\", '\\"': '"', "\\n": "\n", "\\r": "\r", "\\t": "\t" };
  return value.replace(/\\(?:u[0-9A-Fa-f]{4}|.)/g, (match) =>
    simple[match] ?? String.fromCodePoint(Number.parseInt(match.slice(2), 16)));
};

const resourceUri = (kind, identifier) => `${BASE}/id/${kind}/${encodeURIComponent(identifier)}`;
const decodeUri = (uri, kind) => {
  const prefix = `${BASE}/id/${kind}/`;
  assert.ok(uri.startsWith(prefix), `${MISMATCH}: unexpected ${kind} resource IRI`);
  return decodeURIComponent(uri.slice(prefix.length));
};

/** One public surface flattened to the fields every consumer must share. */
const expectation = (row) => ({
  statement_id: row.statement_id,
  version_id: row.version_id,
  statement_date: row.statement_date,
  person_id: row.person_id,
  content_id: row.content_id,
  source_title: row.source_title,
  source_url: row.source_url,
  source_version: row.source_version,
  source_kind: row.source_kind,
  original_text: row.original_text,
  language: row.language,
  quote_sha256: row.quote_sha256,
  source_sha256: row.source_sha256,
  locator: row.locator,
  finding_id: row.finding_id,
});

const fromIndex = (index) => index.records.map((record) => expectation({
  statement_id: record.statement_id,
  version_id: record.version_id,
  statement_date: record.statement_date,
  person_id: record.person_id,
  content_id: record.source.content_id,
  source_title: record.source.title,
  source_url: record.source.url,
  source_version: record.source.version_id,
  source_kind: record.source.kind,
  original_text: record.original.text,
  language: record.original.language,
  quote_sha256: record.original.quote_sha256,
  source_sha256: record.source.sha256,
  locator: record.original.locator,
  finding_id: record.finding_id,
}));

const fromApi = (list) => list.data.map((row) => expectation({
  statement_id: row.statement_id,
  version_id: row.version_id,
  statement_date: row.statement_date,
  person_id: row.person.id,
  content_id: row.source.content_id,
  source_title: row.source.title,
  source_url: row.source.url,
  source_version: row.source.version_id,
  source_kind: row.source.kind,
  original_text: row.original.text,
  language: row.original.language,
  quote_sha256: row.original.quote_sha256,
  source_sha256: row.source.sha256,
  locator: row.original.locator,
  finding_id: row.finding_id,
}));

const fromJsonLd = (jsonld) => jsonld["@graph"]
  .filter((node) => node["@type"] === "Quotation")
  .map((node) => expectation({
    statement_id: node.identifier,
    version_id: node.version,
    statement_date: node.dateCreated,
    person_id: decodeUri(node["dp:recordedSpeaker"]["@id"], "person"),
    content_id: decodeUri(node.isPartOf["@id"], "content"),
    source_title: node.isPartOf.name,
    source_url: node.isPartOf.url,
    source_version: node["dp:sourceVersion"],
    source_kind: node["dp:sourceKind"],
    original_text: node.text,
    language: node.inLanguage,
    quote_sha256: node["dp:quoteSha256"],
    source_sha256: node["dp:sourceSha256"],
    locator: node["dp:locator"],
    finding_id: node.subjectOf ? decodeUri(node.subjectOf["@id"], "finding") : null,
  }));

const SINGLE_VALUED = new Set(["identifier", "version", "dateCreated", "text",
  "inLanguage", "name", "url", "isPartOf", "subjectOf", "recordedSpeaker",
  "wordingType", "quoteSha256", "sourceSha256", "sourceVersion", "sourceKind",
  "speechAct", "endorsed", "startChar", "endChar", "segmentId", "startMs", "endMs",
  "projectionFingerprint"].flatMap((term) => [SCHEMA + term, DP + term]));

const fromNTriples = (text) => {
  const triples = new Map();
  for (const line of text.split("\n")) {
    if (!line) continue;
    const match = /^<([^>]+)> <([^>]+)> (.+) \.$/.exec(line);
    assert.ok(match, `${MISMATCH}: unparsable N-Triples line`);
    const [, subject, predicate, object] = match;
    if (!triples.has(subject)) triples.set(subject, new Map());
    const predicates = triples.get(subject);
    // A public node must have one value per provenance predicate. Two source
    // URLs on one content node mean the graph cannot say which one a
    // Statement came from, so the release is refused rather than guessed.
    // schema:hasPart is legitimately repeated and is not read here.
    if (SINGLE_VALUED.has(predicate) && predicates.has(predicate) &&
        predicates.get(predicate) !== object) {
      throw new Error(`${MISMATCH}: ambiguous ${predicate} on ${subject}`);
    }
    predicates.set(predicate, object);
  }
  const literal = (map, term) => {
    const raw = map.get(SCHEMA + term) ?? map.get(DP + term);
    assert.ok(raw?.startsWith('"') && raw.endsWith('"'), `${MISMATCH}: missing ${term} literal`);
    return unescapeLiteral(raw.slice(1, -1));
  };
  const iri = (map, term) => {
    const raw = map.get(SCHEMA + term) ?? map.get(DP + term);
    assert.ok(raw?.startsWith("<") && raw.endsWith(">"), `${MISMATCH}: missing ${term} IRI`);
    return raw.slice(1, -1);
  };
  const rows = [];
  for (const [subject, map] of triples) {
    if (map.get("http://www.w3.org/1999/02/22-rdf-syntax-ns#type") !== "<" + SCHEMA + "Quotation>") continue;
    const statementId = literal(map, "identifier");
    assert.equal(subject, resourceUri("statement", statementId), `${MISMATCH}: subject IRI`);
    const contentUri = iri(map, "isPartOf");
    const content = triples.get(contentUri);
    assert.ok(content, `${MISMATCH}: missing content node`);
    const locator = {
      start_char: Number(literal(map, "startChar")),
      end_char: Number(literal(map, "endChar")),
    };
    if (map.has(DP + "segmentId")) {
      locator.segment_id = literal(map, "segmentId");
      locator.start_ms = Number(literal(map, "startMs"));
      locator.end_ms = Number(literal(map, "endMs"));
    }
    const findingIri = map.get(SCHEMA + "subjectOf");
    rows.push(expectation({
      statement_id: statementId,
      version_id: literal(map, "version"),
      statement_date: literal(map, "dateCreated"),
      person_id: decodeUri(iri(map, "recordedSpeaker"), "person"),
      content_id: decodeUri(contentUri, "content"),
      source_title: unescapeLiteral(content.get(SCHEMA + "name").slice(1, -1)),
      source_url: content.get(SCHEMA + "url").slice(1, -1),
      source_version: literal(map, "sourceVersion"),
      source_kind: literal(map, "sourceKind"),
      original_text: literal(map, "text"),
      language: literal(map, "inLanguage"),
      quote_sha256: literal(map, "quoteSha256"),
      source_sha256: literal(map, "sourceSha256"),
      locator,
      finding_id: findingIri ? decodeUri(findingIri.slice(1, -1), "finding") : null,
    }));
  }
  return rows;
};

const datasetFingerprintOfNTriples = (text) => {
  const match = /^<[^>]+> <https:\/\/dichiarazionipubbliche\.it\/vocab#projectionFingerprint> "([0-9a-f]{64})" \.$/m.exec(text);
  assert.ok(match, `${MISMATCH}: missing dataset fingerprint triple`);
  return match[1];
};

/** Every surface must describe the same record set with the same bytes. */
const agreement = (surfaces) => {
  const maps = surfaces.map(({ name, rows }) => [name, new Map(rows.map((row) => [row.statement_id, row]))]);
  const ids = [...new Set(surfaces.flatMap(({ rows }) => rows.map((row) => row.statement_id)))].sort();
  for (const [name, map] of maps) {
    if (map.size !== ids.length || ids.some((id) => !map.has(id))) {
      throw new Error(`${MISMATCH}: ${name} record set`);
    }
  }
  const [referenceName, reference] = maps[0];
  for (const [name, map] of maps.slice(1)) {
    for (const id of ids) {
      const left = canonicalJson(reference.get(id));
      const right = canonicalJson(map.get(id));
      if (left !== right) throw new Error(`${MISMATCH}: ${name} disagrees with ${referenceName} on ${id}`);
    }
  }
  return ids;
};

const indexOf = async (state) => {
  const pins = {
    intersectionSha256: state.join.dataset_sha256,
    statementSha256: state.join.source_dataset_sha256,
    personSha256: state.join.person_dataset_sha256,
  };
  const index = await buildPublicStatementSearchV3(state.join, pins);
  assert.deepEqual(
    await validatePublicStatementSearchV3(index, { ...pins, indexSha256: index.index_sha256 }),
    index,
  );
  assert.equal(index.source_status, "READY");
  return { index, pins };
};

const surfacesOf = (state, index) => ({
  index: fromIndex(index),
  api: fromApi(state.api),
  jsonld: fromJsonLd(state.jsonld),
  ntriples: fromNTriples(state.nt),
});

const checkRelease = async (state, name) => {
  const { index, pins } = await indexOf(state);
  const surfaces = surfacesOf(state, index);
  const ids = agreement(Object.entries(surfaces).map(([surface, rows]) => ({ name: surface, rows })));
  // One release, one fingerprint: index, API, JSON-LD, N-Triples and the
  // governed bundle must never disagree about which dataset is being served.
  const fingerprints = {
    index: index.source_dataset_sha256,
    api: state.api.meta.dataset_sha256,
    jsonld: state.jsonld["@graph"][0]["dp:projectionFingerprint"],
    ntriples: datasetFingerprintOfNTriples(state.nt),
    bundle: state.bundle_dataset,
  };
  for (const [surface, value] of Object.entries(fingerprints)) {
    assert.equal(value, state.bundle_dataset, `${name}: ${surface} dataset fingerprint`);
  }
  // Replay of the same inputs must be byte-stable, not merely equal per field.
  const replay = await buildPublicStatementSearchV3(state.join, pins);
  assert.equal(canonicalJson(replay), canonicalJson(index), `${name}: index replay is not byte-stable`);
  return { index, pins, surfaces, ids };
};

// 1. Identical safe replay of the whole release (Python surfaces) is byte-stable.
const first = build();
const second = build();
assert.equal(second, first, "identical safe replay must produce identical API/JSON-LD/N-Triples bytes");
const release = JSON.parse(first);

// 2. Four surfaces of one release agree on identifiers, wording, source,
//    language, locator, finding and dataset fingerprint.
const full = await checkRelease(release.full, "full");
assert.equal(full.ids.length, 3);
assert.deepEqual(full.ids, ["statement:1", "statement:2", "statement:3"]);
for (const row of full.surfaces.index) {
  assert.equal(row.locator.end_char - row.locator.start_char, [...row.original_text].length,
    "indexed locator must span exactly the approved original");
}

// 3. Byte fidelity on a real verbatim span containing tabs, newlines and edge
//    spaces: no consumer may trim or normalize what another preserves.
const special = await checkRelease(release.special, "special");
const specialQuote = " «Café»\tora\n ";
for (const [surface, rows] of Object.entries(special.surfaces)) {
  assert.equal(rows.find((row) => row.statement_id === "statement:1").original_text, specialQuote,
    `${surface} must preserve the approved bytes exactly`);
}
assert.ok(release.special.nt.includes('"' + escapeLiteral(specialQuote) + '"'),
  "N-Triples literal escaping must round-trip the exact approved bytes");

// 4. Withdrawal removes the affected Statement from every surface at once,
//    while the remaining records keep agreeing.
const withdrawn = await checkRelease(release.withdrawn, "withdrawn");
assert.equal(withdrawn.ids.length, 2);
assert.equal(withdrawn.ids.includes("statement:2"), false);
const withdrawnRecord = full.surfaces.index.find((row) => row.statement_id === "statement:2");
const remainingQuotes = new Set(withdrawn.surfaces.index.map((row) => row.original_text));
for (const [surface, text] of Object.entries({
  index: canonicalJson(withdrawn.index),
  api: JSON.stringify(release.withdrawn.api),
  jsonld: JSON.stringify(release.withdrawn.jsonld),
  ntriples: release.withdrawn.nt,
})) {
  for (const marker of ["statement:2", "statement-version:2", "/dichiarazioni/statement-2/",
    "statement%3A2", "source-version:2"]) {
    assert.equal(text.includes(marker), false, `${surface} still serves the withdrawn record (${marker})`);
  }
  if (!remainingQuotes.has(withdrawnRecord.original_text)) {
    assert.equal(text.includes(withdrawnRecord.original_text.trim()), false,
      `${surface} still serves the withdrawn quote`);
  }
}
assert.deepEqual(release.withdrawn_detail, { status: 404, code: "RESOURCE_NOT_FOUND" },
  "a withdrawn Statement must not be readable through the pinned detail reader");
// A previously published release must not survive withdrawal under new pins.
await assert.rejects(
  () => validatePublicStatementSearchV3(full.index, {
    ...withdrawn.pins, indexSha256: full.index.index_sha256,
  }),
  /PUBLIC_V3_INDEX_STALE_OR_INCOMPATIBLE/,
  "the old approved index must fail closed after withdrawal",
);

// 5. A release whose linked data cannot state one source per content node is
//    refused: N-Triples must not silently pick one of two source URLs.
assert.throws(() => fromNTriples(release.shared_content), new RegExp(MISMATCH),
  "an ambiguous content node must be refused, not silently resolved");

// 6. The comparator must not be vacuous: spoofing any one surface is refused.
const spoof = (surface, mutate) => {
  const rows = structuredClone(full.surfaces[surface]);
  mutate(rows[0]);
  return Object.entries(full.surfaces)
    .map(([name, value]) => ({ name, rows: name === surface ? rows : value }));
};
for (const surface of ["index", "api", "jsonld", "ntriples"]) {
  assert.throws(
    () => agreement(spoof(surface, (row) => { row.original_text = "parafrasi non approvata"; })),
    new RegExp(MISMATCH),
    `a changed quotation on ${surface} must be refused`,
  );
  assert.throws(
    () => agreement(spoof(surface, (row) => { row.source_version = "source-version:9"; })),
    new RegExp(MISMATCH),
    `a changed source version on ${surface} must be refused`,
  );
}

// 7. No operational or private field may ride along on any surface.
const serialized = [JSON.stringify(full.surfaces.api), JSON.stringify(release.full.jsonld), release.full.nt];
for (const token of ["raw_transcript", "review_provenance", "provider_receipt", "person_score", "private_candidate"]) {
  assert.equal(serialized.some((text) => text.includes(token)), false, `private field leaked: ${token}`);
}

console.log(
  "DP-436 cross-consumer verbatim parity PASS " +
  `(4 surfaces × 3 statements, byte-stable replay, withdrawal 3→2, ` +
  `fingerprint ${full.index.source_dataset_sha256.slice(0, 12)})`,
);
