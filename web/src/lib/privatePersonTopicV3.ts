/** DP-439 isolated private/SSR reader, gated by independent CURRENT release pins.
 * No route, dynamic provider, private manifest access, topic inference or publish grant.
 * Pins may NEVER be copied from the candidate assets themselves.
 */
import { canonicalJson } from "./searchIndex.ts";
import { publicIdSlug } from "./format.ts";
import {
  validatePublicStatementSearchV3, searchPublicStatementsV3,
  parsePublicStatementSearchV3Url, serializePublicStatementSearchV3Url,
  type PublicStatementSearchV3, type V3IndexPins, type V3StatementRecord,
  type V3SearchUrlState,
} from "./publicStatementSearchV3.ts";
import { readApprovedPersonV3, type ApprovedPersonV3Collection } from "./publicPersonV3.ts";
import { validateOriginalStatement, PUBLIC_STATEMENT_V3_SCHEMA, type PublicOriginalStatement } from "./statementV3.ts";

const HASH = /^[0-9a-f]{64}$/;
const ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const TIMEZONE = /(?:Z|[+-]\d{2}:\d{2})$/;
const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
function fail(reason: string): never { throw new Error("DP439_PRIVATE_" + reason); }
const instant = (value: unknown): number | null => {
  if (typeof value !== "string" || !TIMEZONE.test(value)) return null;
  const n = Date.parse(value);
  return Number.isFinite(n) ? n : null;
};
const validDate = (value: unknown): value is string =>
  typeof value === "string" && DAY.test(value) && !Number.isNaN(Date.parse(value + "T00:00:00Z")) &&
  new Date(value + "T00:00:00Z").toISOString().slice(0, 10) === value;
async function digest(value: unknown): Promise<string> {
  const data = new TextEncoder().encode(canonicalJson(value));
  const hashed = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(hashed)].map(n => n.toString(16).padStart(2, "0")).join("");
}

export interface PrivatePersonTopicPins extends V3IndexPins {
  allowPrivatePersonTopic: boolean;
  /** Source release timestamp is outside the Python collection digest. */
  generatedAt: string;
  /** Independently approved current public Topic identity-version hashes. */
  topicSha256ById: Record<string, string>;
  validUntil: string;
}

export interface PrivatePersonTopicUrl extends V3SearchUrlState {
  page: number;
  fromDate?: string;
  toDate?: string;
  sourceId?: string;
}

export interface PrivatePersonTopicRow {
  statementId: string;
  versionId: string;
  statementRoute: string;
  statementDate: string;
  personId: string;
  personName: string;
  personRoute: string;
  topicIds: string[];
  topicRoute: string | null;
  originalText: string;
  language: string;
  quoteSha256: string;
  sourceSha256: string;
  sourceVersion: string;
  sourceUrl: string;
  sourceTitle: string;
  sourceContentId: string;
  locator: V3StatementRecord["original"]["locator"];
  findingId: string | null;
}

export interface PrivatePersonTopicRead {
  status: "READY" | "NO_MATCH" | "EMPTY_PUBLIC_CORPUS" | "EMPTY_PUBLIC_INTERSECTION";
  publicationAuthorized: false;
  providerCalls: 0;
  totalResults: number;
  page: number;
  pageCount: number;
  previousUrl: string | null;
  nextUrl: string | null;
  generatedAt: string;
  coverageNote: string;
  records: PrivatePersonTopicRow[];
}

/** Parse a shareable relative query only; may be re-evaluated on popstate/reload. */
export function parsePrivatePersonTopicUrl(query: string): PrivatePersonTopicUrl {
  if (typeof query !== "string" || query.length > 1500 || query.startsWith("//")) fail("URL_INVALID");
  const params = new URLSearchParams(query.startsWith("?") ? query.slice(1) : query);
  const allowed = new Set(["q", "persona", "tema", "ordine", "pagina", "dal", "al", "fonte"]);
  for (const key of params.keys()) {
    if (!allowed.has(key) || params.getAll(key).length !== 1) fail("URL_INVALID");
  }
  const rawPage = params.get("pagina") ?? "1";
  if (!/^[1-9][0-9]{0,5}$/.test(rawPage)) fail("URL_INVALID");
  const page = Number(rawPage);
  const first = new URLSearchParams(params);
  for (const key of ["pagina", "dal", "al", "fonte"]) first.delete(key);
  let parsed: V3SearchUrlState;
  try { parsed = parsePublicStatementSearchV3Url(first.toString()); }
  catch { return fail("URL_INVALID"); }
  const fromDate = params.get("dal");
  const toDate = params.get("al");
  const sourceId = params.get("fonte");
  if ((fromDate !== null && !validDate(fromDate)) ||
      (toDate !== null && !validDate(toDate)) ||
      (fromDate !== null && toDate !== null && fromDate > toDate) ||
      (sourceId !== null && !ID.test(sourceId))) fail("URL_INVALID");
  return {
    ...parsed, page,
    ...(fromDate !== null ? {fromDate} : {}),
    ...(toDate !== null ? {toDate} : {}),
    ...(sourceId !== null ? {sourceId} : {}),
  };
}

export function serializePrivatePersonTopicUrl(state: PrivatePersonTopicUrl): string {
  if (!Number.isSafeInteger(state.page) || state.page < 1 || state.page > 999999 ||
      (state.fromDate !== undefined && !validDate(state.fromDate)) ||
      (state.toDate !== undefined && !validDate(state.toDate)) ||
      (state.fromDate !== undefined && state.toDate !== undefined && state.fromDate > state.toDate) ||
      (state.sourceId !== undefined && !ID.test(state.sourceId))) fail("URL_INVALID");
  let base: string;
  try { base = serializePublicStatementSearchV3Url(state); }
  catch { return fail("URL_INVALID"); }
  const out = new URLSearchParams(base);
  if (state.page > 1) out.set("pagina", String(state.page));
  if (state.fromDate !== undefined) out.set("dal", state.fromDate);
  if (state.toDate !== undefined) out.set("al", state.toDate);
  if (state.sourceId !== undefined) out.set("fonte", state.sourceId);
  return out.toString();
}

function readTime(pins: PrivatePersonTopicPins, now: Date): void {
  if (pins?.allowPrivatePersonTopic !== true) fail("OPT_IN_REQUIRED");
  if (!object(pins) || !HASH.test(pins.indexSha256) || !HASH.test(pins.intersectionSha256) ||
      !HASH.test(pins.statementSha256) || !HASH.test(pins.personSha256) ||
      instant(pins.generatedAt) === null || !object(pins.topicSha256ById)) fail("PIN_REQUIRED");
  if (!Number.isFinite(now.getTime()) || instant(pins.validUntil) === null ||
      now.getTime() >= (instant(pins.validUntil) as number) ||
      (instant(pins.generatedAt) as number) > now.getTime()) fail("AUTHORITY_EXPIRED");
}

/** Validates the WHOLE current release before any filtered/paginated output.
 * For correction/revoke convergence, upstream must atomically rotate the
 * externally authenticated pins and served static artifacts; this reader
 * cannot detect a future private revocation that its pins haven't observed.
 */
export async function readPrivatePersonTopicV3(
  artifacts: { index: unknown; people: unknown; source: unknown },
  pins: PrivatePersonTopicPins,
  url: string,
  options: { now?: Date; pageSize?: number } = {},
): Promise<PrivatePersonTopicRead> {
  const now = options.now ?? new Date();
  readTime(pins, now);
  const state = parsePrivatePersonTopicUrl(url);
  const pageSize = options.pageSize ?? 20;
  if (!Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 50) fail("PAGINATION_INVALID");
  if (!object(artifacts) || !object(artifacts.source) || !object(artifacts.people)) fail("SOURCE_INVALID");
  const source = artifacts.source;
  if (source.schema_version !== PUBLIC_STATEMENT_V3_SCHEMA ||
      source.dataset_sha256 !== pins.statementSha256 || source.generated_at !== pins.generatedAt ||
      !Array.isArray(source.dossiers) || !Array.isArray(source.topics) ||
      !Array.isArray(source.contents) || !Array.isArray(source.statements)) fail("SOURCE_STALE");
  const material = {dossiers: source.dossiers, topics: source.topics, contents: source.contents, statements: source.statements};
  if (await digest(material) !== pins.statementSha256) fail("SOURCE_STALE");
  const index: PublicStatementSearchV3 = await validatePublicStatementSearchV3(artifacts.index,pins);
  if (index.generated_at !== pins.generatedAt || instant(index.generated_at) === null) fail("SOURCE_STALE");
  const people = artifacts.people as unknown as ApprovedPersonV3Collection;
  const sentinel = Array.isArray(people.people) && people.people.length ? people.people[0]?.person_id : "preview:empty";
  await readApprovedPersonV3(people, {allowPersonV3:true,expectedCollectionSha256:pins.personSha256,identifier:sentinel});
  const personById = new Map(people.people.map(person=>[person.person_id,person]));
  const topicById = new Map<string, Record<string,unknown>>();
  for (const row of source.topics) {
    if (!object(row) || typeof row.topic_id !== "string" || !ID.test(row.topic_id) ||
        !object(pins.topicSha256ById) || !HASH.test(pins.topicSha256ById[row.topic_id]) ||
        topicById.has(row.topic_id) || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(String(row.slug)) ||
        !ID.test(String(row.entity_version)) ||
        !Array.isArray(row.review_event_ids) || row.review_event_ids.length === 0 ||
        row.review_event_ids.some(v => typeof v !== "string" || !ID.test(v)) ||
        !Array.isArray(row.memberships)) fail("TOPIC_UNAPPROVED");
    if (await digest(row) !== pins.topicSha256ById[row.topic_id]) fail("TOPIC_STALE");
    topicById.set(row.topic_id,row);
  }
  if (Object.keys(pins.topicSha256ById).length !== topicById.size) fail("TOPIC_STALE");
  const sourceById = new Map<string, PublicOriginalStatement>();
  for (const value of source.statements) {
    const statement = await validateOriginalStatement(value);
    if (sourceById.has(statement.statement_id)) fail("SOURCE_DUPLICATE");
    sourceById.set(statement.statement_id,statement);
  }
  for (const record of index.records) {
    const statement=sourceById.get(record.statement_id);
    const person=personById.get(record.person_id);
    if (!statement || !person || person.route !== record.person_route ||
        statement.version_id !== record.version_id || statement.person_id !== record.person_id ||
        statement.statement_date !== record.statement_date || statement.content_id !== record.source.content_id ||
        statement.source_title !== record.source.title || statement.source_url !== record.source.url ||
        statement.source_version !== record.source.version_id || statement.source_kind !== record.source.kind ||
        statement.source_sha256 !== record.source.sha256 || statement.quote_sha256 !== record.original.quote_sha256 ||
        statement.original_text !== record.original.text || statement.language !== record.original.language ||
        canonicalJson(statement.locator) !== canonicalJson(record.original.locator) ||
        statement.speech_act !== "OPINION" || statement.endorsed !== true ||
        statement.finding_id !== record.finding_id ||
        !person.statements.some(member => member.statement_id === record.statement_id &&
          member.version_id === record.version_id && member.statement_route === record.statement_route &&
          member.statement_date === record.statement_date && member.content_id === record.source.content_id &&
          member.source_version === record.source.version_id && member.source_sha256 === record.source.sha256 &&
          member.quote_sha256 === record.original.quote_sha256 && member.source_url === record.source.url &&
          canonicalJson(member.locator) === canonicalJson(record.original.locator))) fail("SOURCE_REVISION_STALE");
    if (record.statement_route !== `/dichiarazioni/${publicIdSlug(record.statement_id)}/`) fail("SOURCE_REVISION_STALE");
    for (const membership of record.topics) {
      const topic=topicById.get(membership.topic_id);
      if (!topic || membership.topic_route !== `/temi/${topic.slug}/`) fail("TOPIC_STALE");
    }
  }
  const found = await searchPublicStatementsV3(index,pins,state.query,state);
  if (found.status === "QUERY_TOO_LONG") fail("URL_INVALID");
  const filtered=found.records.filter(row =>
    (state.fromDate===undefined || row.statement_date>=state.fromDate) &&
    (state.toDate===undefined || row.statement_date<=state.toDate) &&
    (state.sourceId===undefined || row.source.content_id===state.sourceId));
  const pageCount=Math.max(1,Math.ceil(filtered.length/pageSize));
  const current = Math.min(state.page,pageCount);
  // Requests for a past/removed member never return an old page or suggest its
  // existence. Index is always revalidated before deriving safe visible counts.
  const paged=filtered.slice((current-1)*pageSize,current*pageSize);
  const rows: PrivatePersonTopicRow[]=paged.map(row => ({
    statementId:row.statement_id,versionId:row.version_id,statementRoute:row.statement_route,
    statementDate:row.statement_date,personId:row.person_id,personName:row.person_name,
    personRoute:row.person_route,topicIds:row.topics.map(topic=>topic.topic_id),
    topicRoute:state.topicId===null ? null : row.topics.find(topic=>topic.topic_id===state.topicId)?.topic_route??null,
    originalText:row.original.text,language:row.original.language,quoteSha256:row.original.quote_sha256,
    sourceSha256:row.source.sha256,sourceVersion:row.source.version_id,sourceUrl:row.source.url,
    sourceTitle:row.source.title,sourceContentId:row.source.content_id,
    locator:structuredClone(row.original.locator),findingId:row.finding_id,
  }));
  const status: PrivatePersonTopicRead["status"]=rows.length ? "READY" :
    index.source_status==="EMPTY_PUBLIC_CORPUS" ? "EMPTY_PUBLIC_CORPUS" :
    index.source_status==="EMPTY_PUBLIC_INTERSECTION" ? "EMPTY_PUBLIC_INTERSECTION" : "NO_MATCH";
  return {
    status,publicationAuthorized:false,providerCalls:0,totalResults:filtered.length,page:current,pageCount,
    previousUrl:current>1?serializePrivatePersonTopicUrl({...state,page:current-1}):null,
    nextUrl:current<pageCount?serializePrivatePersonTopicUrl({...state,page:current+1}):null,
    generatedAt:index.generated_at,coverageNote:index.coverage_note,records:rows,
  };
}
