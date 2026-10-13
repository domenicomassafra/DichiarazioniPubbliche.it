/** DP-439 opt-in, offline Explore v3: pinned Person × Topic originals only.
 *
 * No public route or live release registration. Current pins must be issued
 * independently; a self-hashed fixture is not permission to publish a quote.
 */
import { preflightPublicV3CrossReaderRelease,
  type PublicV3CrossReaderPins } from "./publicV3CrossReaderRelease.ts";
import { parsePublicStatementSearchV3Url, serializePublicStatementSearchV3Url,
  searchPublicStatementsV3, type V3SearchUrlState, type V3StatementRecord,
} from "./publicStatementSearchV3.ts";

const fail = (code: string): never => { throw new Error(code); };
const DEFAULT_PAGE_SIZE = 20;
const MAX_PAGE_SIZE = 25;
const MAX_PAGE = 500;

export interface PublicV3ExploreRow {
  statementId: string;
  versionId: string;
  statementDate: string;
  statementRoute: string;
  personId: string;
  personRoute: string;
  originalWordingType: "VERBATIM_ORIGINAL";
  originalText: string;
  originalLanguage: string;
  quoteSha256: string;
  sourceSha256: string;
  sourceUrl: string;
  sourceTitle: string;
  sourceVersion: string;
  sourceLocator: V3StatementRecord["original"]["locator"];
  findingId: string | null;
  topicRoutes: string[];
}

interface Option { id: string; route: string; label: string }
export interface PublicV3ExplorePreview {
  status: "PREVIEW_READY" | "EMPTY_PUBLIC_CORPUS" | "EMPTY_PUBLIC_INTERSECTION" | "NO_MATCH" | "QUERY_TOO_LONG";
  publicationAuthorized: false;
  providerCalls: 0;
  coverageNote: string;
  generatedAt: string;
  /** Statement occurrence date, never mistaken for archive-added date. */
  dateKind: "SOURCE_ATTESTED_STATEMENT_DATE";
  totalResults: number;
  page: number;
  pageSize: number;
  records: PublicV3ExploreRow[];
  personOptions: Option[];
  topicOptions: Option[];
  currentPerson: Option | null;
  currentTopic: Option | null;
  currentUrl: string;
  nextUrl: string | null;
  previousUrl: string | null;
}

function parsePage(search: string): {url: V3SearchUrlState; page: number} {
  if (typeof search !== "string" || search.length > 1300) fail("PUBLIC_V3_EXPLORE_URL_INVALID");
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const values = params.getAll("pagina");
  if (values.length > 1 || (values.length === 1 &&
      (!/^[1-9]\d{0,2}$/.test(values[0]) || Number(values[0]) > MAX_PAGE))) {
    fail("PUBLIC_V3_EXPLORE_URL_INVALID");
  }
  params.delete("pagina");
  return {url: parsePublicStatementSearchV3Url(params.toString()),
    page: values.length === 1 ? Number(values[0]) : 1};
}

function pageUrl(state: V3SearchUrlState, page: number): string {
  const params = new URLSearchParams(serializePublicStatementSearchV3Url(state));
  if (page > 1) params.set("pagina", String(page));
  const value = params.toString();
  return value ? `?${value}` : "";
}

function rowOf(record: V3StatementRecord): PublicV3ExploreRow {
  return {
    statementId:record.statement_id,versionId:record.version_id,
    statementDate:record.statement_date,statementRoute:record.statement_route,
    personId:record.person_id,personRoute:record.person_route,
    originalWordingType:record.original.wording_type,originalText:record.original.text,
    originalLanguage:record.original.language,quoteSha256:record.original.quote_sha256,
    sourceSha256:record.source.sha256,sourceUrl:record.source.url,
    sourceTitle:record.source.title,sourceVersion:record.source.version_id,
    sourceLocator:structuredClone(record.original.locator),findingId:record.finding_id,
    topicRoutes:record.topics.map(topic=>topic.topic_route),
  };
}

/** Construct a *preview* from one already-pinned complete v3 release.
 * Retrieval, source metadata, reviewed membership and a current issuer are
 * independent preconditions; no caller can mint them through this function.
 */
export async function readPinnedPersonTopicExploreV3(
  input: {people: unknown; join: unknown; index: unknown},
  pins: PublicV3CrossReaderPins,
  search: string,
  options: {pageSize?: number} = {},
): Promise<PublicV3ExplorePreview> {
  let detached!: {input: typeof input; pins: typeof pins; search: string; options: typeof options};
  try { detached=structuredClone({input,pins,search,options}); }
  catch { fail("PUBLIC_V3_EXPLORE_INPUT_INVALID"); }
  const pageSize = detached.options?.pageSize ?? DEFAULT_PAGE_SIZE;
  if (!Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > MAX_PAGE_SIZE) {
    fail("PUBLIC_V3_EXPLORE_PAGE_SIZE_INVALID");
  }
  const {url,page} = parsePage(detached.search);
  const preflight = await preflightPublicV3CrossReaderRelease(detached.input,detached.pins);
  if (preflight.publicationAuthorized !== false) fail("PUBLIC_V3_EXPLORE_AUTHORITY_INVALID");

  // These options are derived *only* from the separately pinned PUBLISHED
  // Person collection and approved Topic memberships after cross-validation.
  const people = detached.input.people as {people: Array<{
    person_id:string;display_name:string;disambiguator:string|null;route:string;
  }>};
  const personOptions: Option[] = people.people.map(person=>({
    id:person.person_id,route:person.route,
    // Identical public names do not identify one specific Person. Use only
    // source-approved disambiguator and the validated public canonical route;
    // no private identity roster, inferred occupation or person ranking.
    label:`${person.display_name}${person.disambiguator ? ` · ${person.disambiguator}` : ""} (${person.route})`,
  })).sort((a,b)=>a.id.localeCompare(b.id));
  const index = detached.input.index as {records: V3StatementRecord[]};
  const topicById = new Map<string, Option>();
  for(const record of index.records){
    for(const topic of record.topics){
      // The v3 search record does not contain a reviewed Topic display name.
      // Show the already-published canonical route instead of inventing one.
      topicById.set(topic.topic_id,{id:topic.topic_id,route:topic.topic_route,
        label:`Tema pubblico · ${topic.topic_route}`});
    }
  }
  const topicOptions = [...topicById.values()].sort((a,b)=>a.id.localeCompare(b.id));
  const currentPerson = personOptions.find(person=>person.id===url.personId)??null;
  const currentTopic = topicOptions.find(topic=>topic.id===url.topicId)??null;
  const unknownFacet = (url.personId!==null&&!currentPerson)||(url.topicId!==null&&!currentTopic);
  // Unknown/withdrawn/private URL values cannot be echoed in the resulting
  // share link, UI labels or results, even when the user knows their ID.
  const safeState: V3SearchUrlState = {
    ...url,personId:currentPerson?.id??null,topicId:currentTopic?.id??null,
  };
  const response = await searchPublicStatementsV3(detached.input.index,{
    personSha256:detached.pins.personSha256,
    statementSha256:detached.pins.statementSha256,
    intersectionSha256:detached.pins.intersectionSha256,
    indexSha256:detached.pins.indexSha256,
  },url.query,{sort:url.sort,personId:url.personId,topicId:url.topicId});

  if (!Number.isFinite(Date.parse(detached.pins.validUntil)) ||
      Date.now()>=Date.parse(detached.pins.validUntil)) fail("PUBLIC_V3_EXPLORE_EXPIRED");
  const filtered = unknownFacet ? [] : response.records;
  const totalResults = filtered.length;
  const start = (page-1)*pageSize;
  const status: PublicV3ExplorePreview["status"] = unknownFacet ? "NO_MATCH" :
    response.status==="OK" ? (start>=totalResults ? "NO_MATCH" : "PREVIEW_READY") : response.status;
  const records = status==="PREVIEW_READY" ? filtered.slice(start,start+pageSize).map(rowOf) : [];
  const nextUrl = (status==="PREVIEW_READY"&&start+pageSize<totalResults)
    ? pageUrl(safeState,page+1):null;
  const previousUrl = page>1?pageUrl(safeState,page-1):null;
  return {status,publicationAuthorized:false,providerCalls:0,
    coverageNote:response.coverage_note,generatedAt:response.generated_at,
    dateKind:"SOURCE_ATTESTED_STATEMENT_DATE",totalResults,
    page,pageSize,records,personOptions,topicOptions,currentPerson,currentTopic,
    currentUrl:pageUrl(safeState,page),nextUrl,previousUrl};
}
