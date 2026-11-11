/** DP-436 surface readers: flatten one governed public-v3 release to the
 * fields every consumer must agree on, and refuse any disagreement.
 *
 * Deliberately independent of the serializers: the N-Triples reader carries its
 * own literal escaping and IRI decoding so the comparison checks the serializer
 * instead of echoing it. Read-only fixtures and release data; this grants no
 * publication right and activates no route.
 */
import assert from "node:assert/strict";
import { canonicalJson } from "../../src/lib/searchIndex.ts";

export const MISMATCH = "DP436_CROSS_CONSUMER_MISMATCH";
const BASE = "https://dichiarazionipubbliche.it";
const SCHEMA = "https://schema.org/";
const DP = BASE + "/vocab#";

/** N-Triples literal escaping, re-implemented here on purpose: a shared helper
 * would make the comparison echo the serializer instead of checking it. */
export const escapeLiteral = (value) =>
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

export const rowsFromIndex = (index) => index.records.map((record) => expectation({
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

export const rowsFromApi = (list) => list.data.map((row) => expectation({
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

export const rowsFromJsonLd = (jsonld) => jsonld["@graph"]
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

export const rowsFromNTriples = (text) => {
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

export const datasetFingerprintOfNTriples = (text) => {
  const match = /^<[^>]+> <https:\/\/dichiarazionipubbliche\.it\/vocab#projectionFingerprint> "([0-9a-f]{64})" \.$/m.exec(text);
  assert.ok(match, `${MISMATCH}: missing dataset fingerprint triple`);
  return match[1];
};

/** Every surface must describe the same record set with the same bytes. */
export const requireAgreement = (surfaces) => {
  const maps = surfaces.map(({ name, rows }) => {
    const map = new Map(rows.map((row) => [row.statement_id, row]));
    if (map.size !== rows.length) throw new Error(`${MISMATCH}: ${name} duplicate Statement ID`);
    return [name, map];
  });
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
