/** DP-409 / DP-439: isolated, opt-in browser search of the approved v3 join.
 *
 * NOT wired to public-v2, not an HTTP endpoint, and not an approval engine.
 * The expected hashes must come from an independently authenticated current
 * release manifest. Hashes copied from the downloaded asset authorize nothing.
 */
import { canonicalJson, normalizeSearchText } from "./searchIndex.ts";
import { publicIdSlug } from "./format.ts";

export const PUBLIC_STATEMENT_SEARCH_V3_SCHEMA = "public-statement-search-v3-opt-in" as const;
export const PUBLIC_STATEMENT_SEARCH_V3_MAX_QUERY = 200;
const PERSON_TOPIC_VERSION = "public-person-topic-v3-opt-in";
const SHA = /^[0-9a-f]{64}$/;
const ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const ROUTE = /^\/(?:persone|temi|dichiarazioni)\/[a-z0-9]+(?:-[a-z0-9]+)*\/$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const SORTS = new Set(["recent", "old", "relevance"]);

export interface V3SearchPins {
  /** The independently authorized current DP-439 read-model digest. */
  intersectionSha256: string;
  /** The independently authorized current source Statement-v3 digest. */
  statementSha256: string;
  /** The independently authorized current approved Person-v3 digest. */
  personSha256: string;
}
export interface V3IndexPins extends V3SearchPins {
  /** Independently issued asset SHA; a rehashed malicious file must be refused. */
  indexSha256: string;
}
export interface V3SourceLocator {
  start_char: number;
  end_char: number;
  segment_id?: string;
  start_ms?: number;
  end_ms?: number;
}
export interface V3StatementRecord {
  statement_id: string;
  version_id: string;
  /** Source-bound calendar day of this Statement, not archive insertion or index generation. */
  statement_date: string;
  person_id: string;
  person_name: string;
  person_route: string;
  statement_route: string;
  topics: Array<{ topic_id: string; topic_route: string }>;
  original: {
    wording_type: "VERBATIM_ORIGINAL";
    text: string;
    language: string;
    quote_sha256: string;
    locator: V3SourceLocator;
  };
  source: {
    content_id: string;
    title: string;
    url: string;
    version_id: string;
    sha256: string;
    kind: "WRITTEN" | "TIMED";
  };
  finding_id: string | null;
}
export interface PublicStatementSearchV3 {
  schema_version: typeof PUBLIC_STATEMENT_SEARCH_V3_SCHEMA;
  intersection_sha256: string;
  source_dataset_sha256: string;
  person_dataset_sha256: string;
  generated_at: string;
  coverage_note: string;
  source_status: "READY" | "EMPTY_PUBLIC_CORPUS" | "EMPTY_PUBLIC_INTERSECTION";
  records: V3StatementRecord[];
  index_sha256: string;
}
export interface V3SearchUrlState {
  query: string;
  personId: string | null;
  topicId: string | null;
  /** recent/old compare statement_date; no archive-addition ordering is authorized. */
  sort: "recent" | "old" | "relevance";
}
export interface V3SearchResult {
  status: "OK" | "QUERY_TOO_LONG" | "NO_MATCH" | "EMPTY_PUBLIC_CORPUS" | "EMPTY_PUBLIC_INTERSECTION";
  records: V3StatementRecord[];
  result_count: number;
  generated_at: string;
  coverage_note: string;
}

const fail = (code: string): never => { throw new Error(code); };
const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const exactKeys = (obj: Record<string, unknown>, keys: string[]) =>
  Object.keys(obj).length === keys.length && keys.every((key) => Object.hasOwn(obj, key));
const text = (value: unknown, limit = 2000) =>
  typeof value === "string" && value.length > 0 && value.length <= limit &&
  value.trim() === value && !/[\u0000-\u001f\u007f]/u.test(value);
// Unlike UI labels, independently reviewed verbatim quotations may
// legitimately contain line breaks, tabs, and leading/trailing spaces.
// Never normalize, trim or substitute them: their SHA binds exact bytes.
const verbatimText = (value: unknown) =>
  typeof value === "string" && value.trim().length > 0 && value.length <= 2000 &&
  !/[\u0000-\u0008\u000b-\u001f\u007f]/u.test(value);
const id = (value: unknown) => typeof value === "string" && ID.test(value);
const sha = (value: unknown) => typeof value === "string" && SHA.test(value);
const integer = (value: unknown) => Number.isSafeInteger(value) && (value as number) >= 0;
const isoDate = (value: unknown) => typeof value === "string" &&
  DATE.test(value) && !Number.isNaN(Date.parse(value + "T00:00:00Z")) &&
  new Date(value + "T00:00:00Z").toISOString().slice(0, 10) === value;
const instant = (value: unknown) => typeof value === "string" &&
  /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const canonicalRoute = (route: unknown, prefix: "persone" | "temi" | "dichiarazioni") =>
  typeof route === "string" && ROUTE.test(route) && route.startsWith("/" + prefix + "/");

async function hash(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

function safeSourceUrl(value: unknown): boolean {
  if (typeof value !== "string" || value.length > 2048 ||
      /[\u0000-\u001f\u007f\\]/.test(value)) return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !!url.hostname && !url.username &&
      !url.password && !url.hash && !value.includes("@");
  } catch {
    return false;
  }
}

function validLocator(value: unknown, kind: unknown): value is V3SourceLocator {
  if (!isObject(value) || !integer(value.start_char) || !integer(value.end_char) ||
      (value.end_char as number) <= (value.start_char as number)) return false;
  if (kind === "WRITTEN") return exactKeys(value, ["start_char", "end_char"]);
  return kind === "TIMED" &&
    exactKeys(value, ["start_char", "end_char", "segment_id", "start_ms", "end_ms"]) &&
    id(value.segment_id) && integer(value.start_ms) && integer(value.end_ms) &&
    (value.end_ms as number) > (value.start_ms as number);
}

async function validateRecord(value: unknown): Promise<void> {
  if (!isObject(value)) fail("PUBLIC_V3_INDEX_RECORD_INVALID");
  const record = value as Record<string, unknown>;
  if (!exactKeys(record, [
    "statement_id", "version_id", "statement_date", "person_id", "person_name",
    "person_route", "statement_route", "topics", "original", "source", "finding_id",
  ])) fail("PUBLIC_V3_INDEX_RECORD_INVALID");
  if (!id(record.statement_id) || !id(record.version_id) || !id(record.person_id) ||
      !text(record.person_name, 300) || !isoDate(record.statement_date) ||
      !canonicalRoute(record.person_route, "persone") ||
      record.statement_route !== "/dichiarazioni/" + publicIdSlug(record.statement_id as string) + "/" ||
      !canonicalRoute(record.statement_route, "dichiarazioni") ||
      !Array.isArray(record.topics) || record.topics.length < 1 ||
      !isObject(record.original) || !isObject(record.source) ||
      !(record.finding_id === null || id(record.finding_id))) fail("PUBLIC_V3_INDEX_RECORD_INVALID");
  const topics = record.topics as unknown[];
  const seen = new Set<string>();
  for (const value of topics) {
    if (!isObject(value)) fail("PUBLIC_V3_INDEX_TOPIC_INVALID");
    const topic = value as Record<string, unknown>;
    if (!exactKeys(topic, ["topic_id", "topic_route"]) ||
        !id(topic.topic_id) || !canonicalRoute(topic.topic_route, "temi") ||
        seen.has(topic.topic_id as string)) fail("PUBLIC_V3_INDEX_TOPIC_INVALID");
    seen.add(topic.topic_id as string);
  }
  if (topics.some((entry, i) => i > 0 &&
      (topics[i - 1] as { topic_id: string }).topic_id >= (entry as { topic_id: string }).topic_id)) {
    fail("PUBLIC_V3_INDEX_TOPIC_ORDER_INVALID");
  }
  const source = record.source as Record<string, unknown>;
  const original = record.original as Record<string, unknown>;
  if (!exactKeys(source, ["content_id", "title", "url", "version_id", "sha256", "kind"]) ||
      !id(source.content_id) || !id(source.version_id) || !text(source.title, 500) ||
      !safeSourceUrl(source.url) || !sha(source.sha256) ||
      !["WRITTEN", "TIMED"].includes(source.kind as string) ||
      !exactKeys(original, ["wording_type", "text", "language", "quote_sha256", "locator"]) ||
      original.wording_type !== "VERBATIM_ORIGINAL" || !verbatimText(original.text) ||
      !text(original.language, 40) || !sha(original.quote_sha256) ||
      !validLocator(original.locator, source.kind)) fail("PUBLIC_V3_INDEX_PROVENANCE_INVALID");
  if ((original.locator as V3SourceLocator).end_char -
      (original.locator as V3SourceLocator).start_char !== [...(original.text as string)].length) {
    fail("PUBLIC_V3_INDEX_LOCATOR_LENGTH_MISMATCH");
  }
  if (await hash(original.text as string) !== original.quote_sha256) {
    fail("PUBLIC_V3_INDEX_QUOTE_SHA_MISMATCH");
  }
}

interface V3JoinRow {
  statement_id: string;
  version_id: string;
  statement_date: string;
  person_id: string;
  person_route: string;
  topic_id: string;
  topic_route: string;
  statement_route: string;
  statement: Record<string, unknown>;
}

async function recordFromJoin(value: unknown): Promise<V3StatementRecord> {
  if (!isObject(value)) fail("PUBLIC_V3_JOIN_ROW_INVALID");
  const row = value as Record<string, unknown>;
  if (!exactKeys(row, [
    "statement_id", "version_id", "statement_route", "statement_date",
    "person_id", "person_route", "topic_id", "topic_route", "statement",
  ]) || !isObject(row.statement)) fail("PUBLIC_V3_JOIN_ROW_INVALID");
  const item = row as unknown as V3JoinRow;
  const statement = item.statement;
  if (!isObject(statement.person) || !isObject(statement.source) ||
      !isObject(statement.original)) fail("PUBLIC_V3_JOIN_ROW_INVALID");
  const speaker = statement.person as Record<string, unknown>;
  const original = statement.original as Record<string, unknown>;
  const source = statement.source as Record<string, unknown>;
  if (statement.statement_id !== item.statement_id ||
      statement.version_id !== item.version_id ||
      statement.statement_date !== item.statement_date ||
      speaker.id !== item.person_id ||
      statement.endorsed !== true || statement.speech_act !== "OPINION" ||
      statement.summary !== null && statement.summary !== undefined && !isObject(statement.summary) ||
      !id(item.topic_id) || !canonicalRoute(item.topic_route, "temi") ||
      original.wording_type !== "VERBATIM_ORIGINAL") fail("PUBLIC_V3_JOIN_ROW_INVALID");
  const record: V3StatementRecord = {
    statement_id: item.statement_id,
    version_id: item.version_id,
    statement_date: item.statement_date,
    person_id: item.person_id,
    person_name: speaker.name as string,
    person_route: item.person_route,
    statement_route: item.statement_route,
    topics: [{ topic_id: item.topic_id, topic_route: item.topic_route }],
    original: {
      wording_type: "VERBATIM_ORIGINAL",
      text: original.text as string,
      language: original.language as string,
      quote_sha256: original.quote_sha256 as string,
      locator: structuredClone(original.locator) as V3SourceLocator,
    },
    source: {
      content_id: source.content_id as string,
      title: source.title as string,
      url: source.url as string,
      version_id: source.version_id as string,
      sha256: source.sha256 as string,
      kind: source.kind as "WRITTEN" | "TIMED",
    },
    finding_id: statement.finding_id as string | null,
  };
  await validateRecord(record);
  return record;
}

function material(index: Omit<PublicStatementSearchV3, "index_sha256">) {
  return {
    schema_version: index.schema_version, intersection_sha256: index.intersection_sha256,
    source_dataset_sha256: index.source_dataset_sha256,
    person_dataset_sha256: index.person_dataset_sha256,
    generated_at: index.generated_at, coverage_note: index.coverage_note,
    source_status: index.source_status, records: index.records,
  };
}

/** Build only from an externally pinned DP-439 source release, never from v2. */
export async function buildPublicStatementSearchV3(
  input: unknown, pins: V3SearchPins,
): Promise<PublicStatementSearchV3> {
  if (!validPins(pins) || !isObject(input) || input.schema_version !== PERSON_TOPIC_VERSION ||
      input.dataset_sha256 !== pins.intersectionSha256 ||
      input.source_dataset_sha256 !== pins.statementSha256 ||
      input.person_dataset_sha256 !== pins.personSha256 ||
      !instant(input.generated_at) || !text(input.coverage_note, 400) ||
      input.provider_calls !== 0 || !Array.isArray(input.data) ||
      !Number.isSafeInteger(input.result_count) || input.result_count !== input.data.length ||
      !["READY", "EMPTY_PUBLIC_CORPUS", "EMPTY_PUBLIC_INTERSECTION"].includes(input.status as string) ||
      ((input.data.length > 0) !== (input.status === "READY"))) {
    fail("PUBLIC_V3_JOIN_NOT_CURRENT");
  }
  const snapshot = structuredClone(input);
  const { schema_version, source_dataset_sha256, person_dataset_sha256,
    generated_at, coverage_note, status, result_count, data } = snapshot as Record<string, unknown>;
  const originalMaterial = { schema_version, source_dataset_sha256, person_dataset_sha256,
    generated_at, coverage_note, status, result_count, data };
  if (await hash(canonicalJson(originalMaterial)) !== pins.intersectionSha256) {
    fail("PUBLIC_V3_JOIN_TAMPERED");
  }
  const grouped = new Map<string, V3StatementRecord>();
  for (const row of data as unknown[]) {
    const record = await recordFromJoin(row);
    // A public Statement has one current version per canonical shareable
    // route. A corrected version replaces the prior snapshot, never becomes
    // another searchable hit under the same URI.
    const key = record.statement_id;
    const prior = grouped.get(key);
    if (prior) {
      const { topics: _old, ...base } = prior;
      const { topics: _new, ...next } = record;
      if (canonicalJson(base) !== canonicalJson(next) ||
          prior.topics.some((topic) => topic.topic_id === record.topics[0].topic_id)) {
        fail("PUBLIC_V3_JOIN_CONFLICT");
      }
      prior.topics.push(record.topics[0]);
    } else {
      grouped.set(key, record);
    }
  }
  const records = Array.from(grouped.values());
  for (const record of records) {
    record.topics.sort((a, b) => a.topic_id < b.topic_id ? -1 : a.topic_id > b.topic_id ? 1 : 0);
  }
  records.sort((a, b) =>
    a.statement_id < b.statement_id ? -1 : a.statement_id > b.statement_id ? 1 :
    a.version_id < b.version_id ? -1 : a.version_id > b.version_id ? 1 : 0);
  const prepared: Omit<PublicStatementSearchV3, "index_sha256"> = {
    schema_version: PUBLIC_STATEMENT_SEARCH_V3_SCHEMA,
    intersection_sha256: pins.intersectionSha256,
    source_dataset_sha256: pins.statementSha256,
    person_dataset_sha256: pins.personSha256,
    generated_at: generated_at as string,
    coverage_note: coverage_note as string,
    source_status: status as PublicStatementSearchV3["source_status"],
    records,
  };
  return { ...prepared, index_sha256: await hash(canonicalJson(material(prepared))) };
}

function validPins(pins: unknown): pins is V3SearchPins {
  return isObject(pins) &&
    sha(pins.intersectionSha256) && sha(pins.statementSha256) && sha(pins.personSha256);
}

/** Verify asset bytes AND all externally expected current release fingerprints. */
export async function validatePublicStatementSearchV3(
  value: unknown, pins: V3IndexPins,
): Promise<PublicStatementSearchV3> {
  if (!validPins(pins) || !sha(pins.indexSha256) || !isObject(value) ||
      !exactKeys(value, [
        "schema_version", "intersection_sha256", "source_dataset_sha256",
        "person_dataset_sha256", "generated_at", "coverage_note", "source_status",
        "records", "index_sha256",
      ]) ||
      value.schema_version !== PUBLIC_STATEMENT_SEARCH_V3_SCHEMA ||
      value.intersection_sha256 !== pins.intersectionSha256 ||
      value.source_dataset_sha256 !== pins.statementSha256 ||
      value.person_dataset_sha256 !== pins.personSha256 ||
      value.index_sha256 !== pins.indexSha256 || !Array.isArray(value.records) ||
      !instant(value.generated_at) || !text(value.coverage_note, 400) ||
      !["READY", "EMPTY_PUBLIC_CORPUS", "EMPTY_PUBLIC_INTERSECTION"].includes(value.source_status as string) ||
      ((value.records.length > 0) !== (value.source_status === "READY"))) {
    fail("PUBLIC_V3_INDEX_STALE_OR_INCOMPATIBLE");
  }
  const index = structuredClone(value) as unknown as PublicStatementSearchV3;
  if (await hash(canonicalJson(material(index))) !== index.index_sha256) {
    fail("PUBLIC_V3_INDEX_TAMPERED");
  }
  const seen = new Set<string>();
  let previousKey = "";
  for (const record of index.records) {
    await validateRecord(record);
    const key = record.statement_id;
    if (seen.has(key) || (previousKey && key <= previousKey)) {
      fail("PUBLIC_V3_INDEX_DUPLICATE_OR_UNORDERED");
    }
    previousKey = key;
    seen.add(key);
  }
  return index;
}

const validFilter = (value: string | null) => value === null || ID.test(value);

export function serializePublicStatementSearchV3Url(state: V3SearchUrlState): string {
  if (!validFilter(state.personId) || !validFilter(state.topicId) ||
      !SORTS.has(state.sort) || typeof state.query !== "string" ||
      [...state.query.trim()].length > PUBLIC_STATEMENT_SEARCH_V3_MAX_QUERY ||
      /[\u0000-\u001f\u007f]/u.test(state.query)) fail("PUBLIC_V3_SEARCH_URL_INVALID");
  const params = new URLSearchParams();
  if (state.query.trim()) params.set("q", state.query.trim());
  if (state.personId) params.set("persona", state.personId);
  if (state.topicId) params.set("tema", state.topicId);
  if (state.sort !== "recent") params.set("ordine", state.sort);
  return params.toString();
}

export function parsePublicStatementSearchV3Url(search: string): V3SearchUrlState {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  if ([...params.keys()].some((key) => !["q", "persona", "tema", "ordine"].includes(key)) ||
      [...params.keys()].some((key) => params.getAll(key).length !== 1)) {
    fail("PUBLIC_V3_SEARCH_URL_INVALID");
  }
  const state: V3SearchUrlState = {
    query: params.get("q") ?? "",
    personId: params.get("persona"),
    topicId: params.get("tema"),
    sort: (params.get("ordine") ?? "recent") as V3SearchUrlState["sort"],
  };
  serializePublicStatementSearchV3Url(state); // same bounds and ID grammar
  return state;
}

function relevance(record: V3StatementRecord, term: string): number {
  if (!term) return 0;
  const original = normalizeSearchText(record.original.text);
  const secondary = [
    normalizeSearchText(record.person_name),
    normalizeSearchText(record.source.title),
  ];
  if (original === term) return 400;
  if (original.includes(term)) return 300;
  if (secondary.some((value) => value === term)) return 200;
  if (secondary.some((value) => value.includes(term))) return 100;
  return -1;
}

/** Browser search validates the pinned static artifact before every result. */
export async function searchPublicStatementsV3(
  index: unknown, pins: V3IndexPins, rawQuery: string, filters: Partial<V3SearchUrlState> = {},
): Promise<V3SearchResult> {
  const verified = await validatePublicStatementSearchV3(index, pins);
  if (typeof rawQuery !== "string" || [...rawQuery.trim()].length > PUBLIC_STATEMENT_SEARCH_V3_MAX_QUERY ||
      /[\u0000-\u001f\u007f]/u.test(rawQuery)) {
    return { status: "QUERY_TOO_LONG", records: [], result_count: 0,
      generated_at: verified.generated_at, coverage_note: verified.coverage_note };
  }
  const sort = filters.sort ?? "recent";
  const person = filters.personId ?? null;
  const topic = filters.topicId ?? null;
  if (!SORTS.has(sort) || !validFilter(person) || !validFilter(topic)) {
    fail("PUBLIC_V3_SEARCH_FILTER_INVALID");
  }
  const needle = normalizeSearchText(rawQuery.trim());
  const records = verified.records
    .map((record) => ({ record, score: relevance(record, needle) }))
    .filter(({ record, score }) =>
      (!needle || score >= 0) &&
      (person === null || record.person_id === person) &&
      (topic === null || record.topics.some((member) => member.topic_id === topic)));
  records.sort((a, b) => {
    if (needle && sort === "relevance" && a.score !== b.score) return b.score - a.score;
    const date = a.record.statement_date.localeCompare(b.record.statement_date);
    if (date) return sort === "old" ? date : -date;
    return a.record.statement_id < b.record.statement_id ? -1 :
      a.record.statement_id > b.record.statement_id ? 1 :
      a.record.version_id < b.record.version_id ? -1 :
      a.record.version_id > b.record.version_id ? 1 : 0;
  });
  const out = records.map(({ record }) => record);
  const status: V3SearchResult["status"] = out.length ? "OK" :
    verified.source_status === "EMPTY_PUBLIC_CORPUS" ? "EMPTY_PUBLIC_CORPUS" :
    verified.source_status === "EMPTY_PUBLIC_INTERSECTION" ? "EMPTY_PUBLIC_INTERSECTION" : "NO_MATCH";
  return {
    status, records: out, result_count: out.length,
    generated_at: verified.generated_at, coverage_note: verified.coverage_note,
  };
}
