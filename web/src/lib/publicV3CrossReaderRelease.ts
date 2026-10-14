/**
 * DP-422/DP-405/DP-406/DP-409: an opt-in, read-only preparation boundary for
 * ONE consistent public-v3 reader release. It is NOT a publishing authority.
 *
 * Independently supplied release pins validate each artifact, but a valid
 * index and a valid Person archive can still describe different wording for
 * the same Statement. This seam refuses that split-brain release.
 */
import { canonicalJson } from "./searchIndex.ts";
import { readApprovedPersonV3 } from "./publicPersonV3.ts";
import {
  buildPublicStatementSearchV3,
  validatePublicStatementSearchV3,
  type V3StatementRecord,
} from "./publicStatementSearchV3.ts";

const HASH = /^[0-9a-f]{64}$/;
type JsonRecord = Record<string, unknown>;
const obj = (value: unknown): value is JsonRecord =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const fail = (message: string): never => { throw new Error(message); };
const asString = (value: unknown): string =>
  typeof value === "string" ? value : fail("PUBLIC_V3_CROSS_READER_MISMATCH");

export interface PublicV3CrossReaderPins {
  allowV3Preview: boolean;
  /** All values must come from one independent, authenticated release owner. */
  personSha256: string;
  statementSha256: string;
  intersectionSha256: string;
  indexSha256: string;
  validUntil: string;
}

export interface PublicV3CrossReaderPreview {
  status: "CONSISTENT_PREVIEW_ONLY";
  publicationAuthorized: false;
  sourceStatus: "READY" | "EMPTY_PUBLIC_CORPUS" | "EMPTY_PUBLIC_INTERSECTION";
  personCount: number;
  statementCount: number;
  membershipCount: number;
  personRoutes: string[];
  statementRoutes: string[];
  topicRoutes: string[];
  /** A local consistency receipt, not an attested/served-public release. */
  releasePins: {
    personSha256: string;
    intersectionSha256: string;
    indexSha256: string;
  };
}

const correspondence = (item: JsonRecord, record: V3StatementRecord) => {
  const expected = {
    statement_id: record.statement_id,
    statement_route: record.statement_route,
    version_id: record.version_id,
    statement_date: record.statement_date,
    content_id: record.source.content_id,
    source_title: record.source.title,
    source_url: record.source.url,
    source_version: record.source.version_id,
    source_kind: record.source.kind,
    locator: record.original.locator,
    original_text: record.original.text,
    language: record.original.language,
    quote_sha256: record.original.quote_sha256,
    source_sha256: record.source.sha256,
    finding_id: record.finding_id,
  };
  for (const [key, value] of Object.entries(expected)) {
    if (canonicalJson(item[key]) !== canonicalJson(value)) {
      fail("PUBLIC_V3_CROSS_READER_MISMATCH");
    }
  }
};

/**
 * Consumes pinned, already-public data only. Never activates an Astro route,
 * creates source permissions, or selects records from an operational database.
 */
export async function preflightPublicV3CrossReaderRelease(
  input: {people: unknown; join: unknown; index: unknown},
  pins: PublicV3CrossReaderPins,
): Promise<PublicV3CrossReaderPreview> {
  // The three caller-owned collections AND independent pins must be detached
  // together before the first asynchronous SHA. A validated Person reader
  // cannot protect a second consumer that later reads the original array.
  let detached!: {input: typeof input; pins: PublicV3CrossReaderPins};
  try { detached = structuredClone({input, pins}); }
  catch { fail("PUBLIC_V3_RELEASE_INPUT_INVALID"); }
  const safeInput = detached.input;
  const safePins = detached.pins;
  if (safePins?.allowV3Preview !== true) fail("PUBLIC_V3_RELEASE_OPT_IN_REQUIRED");
  if (![safePins.personSha256, safePins.statementSha256, safePins.intersectionSha256, safePins.indexSha256]
    .every((value) => typeof value === "string" && HASH.test(value))) {
    fail("PUBLIC_V3_RELEASE_PINS_REQUIRED");
  }
  const expires = Date.parse(safePins.validUntil);
  if (typeof safePins.validUntil !== "string" ||
    !/(?:Z|[+-]\d{2}:\d{2})$/.test(safePins.validUntil) ||
    !Number.isFinite(expires) || expires <= Date.now()) {
    fail("PUBLIC_V3_RELEASE_EXPIRED");
  }
  if (!obj(safeInput) || !obj(safeInput.people) || !Array.isArray(safeInput.people.people)) {
    fail("PUBLIC_V3_RELEASE_PEOPLE_INVALID");
  }
  const people = safeInput.people as { people: unknown[] };
  const { join, index } = safeInput;
  // readApprovedPersonV3 always validates the entire collection, not just the
  // requested Person. An absent sentinel also validates a zero-person release.
  const identifier = obj(people.people[0])
    ? asString(people.people[0].person_id) : "preview:empty";
  await readApprovedPersonV3(people, {
    allowPersonV3: true,
    expectedCollectionSha256: safePins.personSha256,
    identifier,
  });
  const releasePins = {
    intersectionSha256: safePins.intersectionSha256,
    statementSha256: safePins.statementSha256,
    personSha256: safePins.personSha256,
  };
  const verifiedIndex = await validatePublicStatementSearchV3(index, {
    ...releasePins, indexSha256: safePins.indexSha256,
  });
  const reconstructed = await buildPublicStatementSearchV3(join, releasePins);
  if (canonicalJson(reconstructed) !== canonicalJson(verifiedIndex)) {
    fail("PUBLIC_V3_CROSS_READER_MISMATCH");
  }
  const generated = Date.parse(verifiedIndex.generated_at);
  if (!Number.isFinite(generated) || generated > Date.now() || generated >= expires) {
    fail("PUBLIC_V3_RELEASE_EXPIRED");
  }

  const byStatement = new Map<string, {owner: string; data: JsonRecord}>();
  const personRoutes = new Set<string>();
  const byPerson = new Map<string, JsonRecord>();
  for (const value of people.people) {
    if (!obj(value) || !Array.isArray(value.statements)) {
      throw new Error("PUBLIC_V3_CROSS_READER_MISMATCH");
    }
    const id = asString(value.person_id);
    personRoutes.add(asString(value.route));
    byPerson.set(id, value);
    for (const row of value.statements) {
      if (!obj(row)) fail("PUBLIC_V3_CROSS_READER_MISMATCH");
      const statementId = asString(row.statement_id);
      if (byStatement.has(statementId)) fail("PUBLIC_V3_CROSS_READER_MISMATCH");
      byStatement.set(statementId, {owner: id, data: row});
    }
  }

  const topicRoutes = new Set<string>();
  let membershipCount = 0;
  for (const record of verifiedIndex.records) {
    const match = byStatement.get(record.statement_id);
    const person = byPerson.get(record.person_id);
    // The independently approved Person display label and the source's
    // statement-level speaker caption need not be identical. Stable Person
    // identity + canonical route, never name matching, establish the join.
    if (!match || !person || match.owner !== record.person_id ||
      person.route !== record.person_route) {
      throw new Error("PUBLIC_V3_CROSS_READER_MISMATCH");
    }
    correspondence(match.data, record);
    for (const topic of record.topics) topicRoutes.add(topic.topic_route);
    membershipCount += record.topics.length;
  }
  if (verifiedIndex.source_status === "EMPTY_PUBLIC_CORPUS" && byStatement.size > 0) {
    fail("PUBLIC_V3_CROSS_READER_MISMATCH");
  }
  // Validity was checked before several awaited cryptographic operations.
  // Refuse a coherent but already-expired preview at the final boundary.
  if (expires <= Date.now()) fail("PUBLIC_V3_RELEASE_EXPIRED");
  return {
    status: "CONSISTENT_PREVIEW_ONLY",
    publicationAuthorized: false,
    sourceStatus: verifiedIndex.source_status,
    personCount: people.people.length,
    statementCount: verifiedIndex.records.length,
    membershipCount,
    personRoutes: [...personRoutes].sort(),
    statementRoutes: verifiedIndex.records.map((item) => item.statement_route).sort(),
    topicRoutes: [...topicRoutes].sort(),
    releasePins: {
      personSha256: safePins.personSha256,
      intersectionSha256: safePins.intersectionSha256,
      indexSha256: safePins.indexSha256,
    },
  };
}
