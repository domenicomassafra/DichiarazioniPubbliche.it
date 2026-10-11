import type { PublicDossier, PublicProjection } from "./types";
import { publicIdSlug } from "./format.ts";

export const SEARCH_INDEX_SCHEMA = "dichiarazioni-pubbliche-search-index-v1" as const;
export const SEARCH_QUERY_MAX_CHARS = 200;

export type SearchRecordKind = "finding" | "content" | "person" | "topic";

export interface PublicSearchRecord {
  id: string;
  kind: SearchRecordKind;
  title: string;
  subtitle: string;
  published_at: string | null;
  assessment: PublicDossier["finding"]["assessment"] | null;
  route: string;
  has_corrections: boolean;
  has_rights_of_reply: boolean;
  wording_type: "PARAPHRASE" | null;
  source_wording_type: "VERBATIM_ORIGINAL" | "REPORTED_QUOTE" | null;
  direct_quote_eligible: false;
  primary_terms: string[];
  secondary_terms: string[];
  /** Public-only facet membership. Never populate from private candidates. */
  person_id?: string;
  topic_ids?: string[];
}

export interface PublicSearchIndex {
  schema_version: typeof SEARCH_INDEX_SCHEMA;
  projection_schema_version: PublicProjection["schema_version"];
  projection_sha256: string;
  generated_at: string;
  index_sha256: string;
  records: PublicSearchRecord[];
}

export interface SearchFilters {
  kind?: SearchRecordKind | "ALL";
  assessment?: PublicDossier["finding"]["assessment"] | "ALL";
  sort?: "relevance" | "recent" | "old";
  personId?: string | "ALL";
  topicId?: string | "ALL";
}

export interface SearchResponse {
  status: "OK" | "QUERY_TOO_LONG";
  records: PublicSearchRecord[];
}

export interface ExploreUrlState {
  query: string;
  kind: SearchRecordKind | "ALL";
  assessment: PublicDossier["finding"]["assessment"] | "ALL";
  sort: "relevance" | "recent" | "old";
  personId?: string | "ALL";
  topicId?: string | "ALL";
}

const ASSESSMENT_FILTERS = new Set([
  "SUPPORTED",
  "FACTUALLY_FALSE",
  "OUTDATED_DATA",
  "INSUFFICIENT_EVIDENCE",
  "UNRESOLVED",
]);
const KIND_FILTERS = new Set(["finding", "content", "person", "topic"]);
const SORT_FILTERS = new Set(["relevance", "recent", "old"]);
// Opaque public IDs may contain spaces (historical IDs and Unicode display
// disambiguators); disallow delimiters/control bytes and bound URL length.
const PUBLIC_FACET_ID = /^[\p{L}\p{N}:._ -]{1,120}$/u;
const ROUTE_BY_KIND: Record<SearchRecordKind, RegExp> = {
  finding: /^\/dichiarazioni\/[a-z0-9]+(?:-[a-z0-9]+)*\/$/,
  person: /^\/persone\/[a-z0-9]+(?:-[a-z0-9]+)*\/$/,
  topic: /^\/temi\/[a-z0-9]+(?:-[a-z0-9]+)*\/$/,
  content: /^\/contenuti\/[a-z0-9]+(?:-[a-z0-9]+)*\/$/,
};

function hasCanonicalSearchRoute(record: PublicSearchRecord): boolean {
  if (!KIND_FILTERS.has(record.kind) || typeof record.route !== "string") return false;
  if (!ROUTE_BY_KIND[record.kind].test(record.route)) return false;
  // Person and Finding routes are derived from approved, stable public IDs.
  // Do not let a self-hashed search asset silently rebind their identities.
  return (record.kind !== "person" && record.kind !== "finding") ||
    record.route === (record.kind === "person"
      ? "/persone/" + publicIdSlug(record.id) + "/"
      : "/dichiarazioni/" + publicIdSlug(record.id) + "/");
}

function publicFacetId(value: string): string | "ALL" {
  return PUBLIC_FACET_ID.test(value) ? value : "ALL";
}

export function parseExploreSearch(search: string): ExploreUrlState {
  const params = new URLSearchParams(search);
  const rawAssessment = params.get("esito") ?? "";
  const rawKind = params.get("tipo") ?? "";
  const rawSort = params.get("ordine") ?? "";
  return {
    query: params.get("q") ?? "",
    assessment: ASSESSMENT_FILTERS.has(rawAssessment)
      ? rawAssessment as ExploreUrlState["assessment"]
      : "ALL",
    kind: KIND_FILTERS.has(rawKind) ? rawKind as ExploreUrlState["kind"] : "ALL",
    sort: SORT_FILTERS.has(rawSort) ? rawSort as ExploreUrlState["sort"] : "relevance",
    personId: publicFacetId(params.get("persona") ?? ""),
    topicId: publicFacetId(params.get("tema") ?? ""),
  };
}

export function buildExploreSearch(state: ExploreUrlState): string {
  const params = new URLSearchParams();
  const query = state.query.trim();
  if (query) params.set("q", query);
  if (state.assessment !== "ALL") params.set("esito", state.assessment);
  if (state.kind !== "ALL") params.set("tipo", state.kind);
  if (state.sort !== "relevance") params.set("ordine", state.sort);
  if (state.personId && state.personId !== "ALL" && publicFacetId(state.personId) !== "ALL") {
    params.set("persona", state.personId);
  }
  if (state.topicId && state.topicId !== "ALL" && publicFacetId(state.topicId) !== "ALL") {
    params.set("tema", state.topicId);
  }
  return params.toString();
}

export function normalizeSearchText(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/\p{M}+/gu, "")
    .toLocaleLowerCase("it")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function compactTerms(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const terms: string[] = [];
  for (const raw of values) {
    const value = String(raw ?? "").trim();
    if (!value || seen.has(value)) continue;
    seen.add(value);
    terms.push(value);
  }
  return terms;
}

function findingRecord(dossier: PublicDossier): PublicSearchRecord {
  const roles = (dossier.speaker.public_roles ?? []).flatMap((role) => [
    role.role,
    role.organization_name ?? null,
  ]);
  return {
    id: dossier.finding_id,
    kind: "finding",
    title: dossier.claim,
    subtitle: [dossier.speaker.name, dossier.source.title].filter(Boolean).join(" · "),
    published_at: dossier.finding.published_at ?? dossier.source.published_at ?? null,
    assessment: dossier.finding.assessment,
    route: `/dichiarazioni/${publicIdSlug(dossier.finding_id)}/`,
    has_corrections: (dossier.corrections ?? []).length > 0,
    has_rights_of_reply: (dossier.rights_of_reply ?? []).length > 0,
    wording_type: "PARAPHRASE",
    source_wording_type: dossier.wording?.source_occurrence.wording_type ?? null,
    direct_quote_eligible: false,
    primary_terms: compactTerms([dossier.claim]),
    secondary_terms: compactTerms([
      dossier.speaker.name,
      dossier.source.title,
      dossier.claim_type,
      dossier.finding.assessment,
      ...roles,
    ]),
    person_id: dossier.speaker.id,
    topic_ids: [],
  };
}

export function buildSearchIndexMaterial(projection: PublicProjection): Omit<PublicSearchIndex, "index_sha256"> {
  const records: PublicSearchRecord[] = projection.dossiers.map(findingRecord);

  // A reviewed public Topic membership may name findings, but private/held
  // members must never create searchable records, facets or membership hints.
  const publishedFindings = new Map(
    records.filter((record) => record.kind === "finding").map((record) => [record.id, record]),
  );
  for (const topic of projection.topics ?? []) {
    for (const membership of topic.memberships) {
      for (const findingId of membership.finding_ids) {
        const record = publishedFindings.get(findingId);
        if (record && !record.topic_ids?.includes(topic.topic_id)) {
          record.topic_ids?.push(topic.topic_id);
        }
      }
    }
  }
  for (const record of publishedFindings.values()) {
    record.topic_ids?.sort();
  }

  const people = new Map<string, PublicSearchRecord>();
  for (const dossier of projection.dossiers) {
    if (people.has(dossier.speaker.id)) continue;
    const roles = (dossier.speaker.public_roles ?? []).flatMap((role) => [
      role.role,
      role.organization_name ?? null,
    ]);
    people.set(dossier.speaker.id, {
      id: dossier.speaker.id,
      kind: "person",
      title: dossier.speaker.name,
      subtitle: compactTerms(roles).join(" · "),
      published_at: null,
      assessment: null,
      route: `/persone/${publicIdSlug(dossier.speaker.id)}/`,
      has_corrections: false,
      has_rights_of_reply: false,
      wording_type: null,
      source_wording_type: null,
      direct_quote_eligible: false,
      primary_terms: compactTerms([dossier.speaker.name]),
      secondary_terms: compactTerms(roles),
    });
  }
  records.push(...people.values());

  for (const topic of projection.topics ?? []) {
    records.push({
      id: topic.topic_id,
      kind: "topic",
      title: topic.canonical_name,
      subtitle: topic.scope_text ?? "Tema pubblico revisionato",
      published_at: null,
      assessment: null,
      route: `/temi/${topic.slug}/`,
      has_corrections: false,
      has_rights_of_reply: false,
      wording_type: null,
      source_wording_type: null,
      direct_quote_eligible: false,
      primary_terms: compactTerms([topic.canonical_name]),
      secondary_terms: compactTerms([topic.scope_text]),
    });
  }

  if (projection.contents !== undefined) {
    for (const content of projection.contents) {
      records.push({
        id: content.content_id,
        kind: "content",
        title: content.title,
        subtitle: content.content_kind.toLocaleLowerCase("it"),
        published_at: content.published_at ?? null,
        assessment: null,
        route: `/contenuti/${content.slug}/`,
        has_corrections: false,
        has_rights_of_reply: false,
        wording_type: null,
        source_wording_type: null,
        direct_quote_eligible: false,
        primary_terms: compactTerms([content.title]),
        secondary_terms: compactTerms([content.content_kind]),
      });
    }
  } else {
    const contents = new Map<string, PublicSearchRecord>();
    for (const dossier of projection.dossiers) {
      if (contents.has(dossier.source.content_id)) continue;
      contents.set(dossier.source.content_id, {
        id: dossier.source.content_id,
        kind: "content",
        title: dossier.source.title,
        subtitle: "Fonte pubblica",
        published_at: dossier.source.published_at ?? null,
        assessment: null,
        route: `/contenuti/${publicIdSlug(dossier.source.content_id)}/`,
        has_corrections: false,
        has_rights_of_reply: false,
        wording_type: null,
        source_wording_type: null,
        direct_quote_eligible: false,
        primary_terms: compactTerms([dossier.source.title]),
        secondary_terms: [],
      });
    }
    records.push(...contents.values());
  }

  records.sort((left, right) =>
    left.kind.localeCompare(right.kind) || left.id.localeCompare(right.id)
  );
  return {
    schema_version: SEARCH_INDEX_SCHEMA,
    projection_schema_version: projection.schema_version,
    projection_sha256: projection.dataset_sha256,
    generated_at: projection.generated_at,
    records,
  };
}

export function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const entries = Object.entries(value as Record<string, unknown>)
    .sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0))
    .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`);
  return `{${entries.join(",")}}`;
}

async function sha256Hex(value: string): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export async function finalizeSearchIndex(
  material: Omit<PublicSearchIndex, "index_sha256">,
): Promise<PublicSearchIndex> {
  return {
    ...material,
    index_sha256: await sha256Hex(canonicalJson(material)),
  };
}

export async function validateSearchIndex(
  value: unknown,
  expectedProjectionSha256: string,
): Promise<PublicSearchIndex> {
  if (!value || typeof value !== "object") throw new Error("SEARCH_INDEX_INVALID");
  const index = value as PublicSearchIndex;
  if (
    index.schema_version !== SEARCH_INDEX_SCHEMA ||
    index.projection_schema_version !== "dichiarazioni-pubbliche-public-v2" ||
    index.projection_sha256 !== expectedProjectionSha256 ||
    !/^[0-9a-f]{64}$/.test(String(index.index_sha256 ?? "")) ||
    !Array.isArray(index.records)
  ) {
    throw new Error("SEARCH_INDEX_INCOMPATIBLE");
  }
  const { index_sha256: claimed, ...material } = index;
  const actual = await sha256Hex(canonicalJson(material));
  if (claimed !== actual) throw new Error("SEARCH_INDEX_TAMPERED");
  const identities = new Set<string>();
  const routes = new Set<string>();
  const publicPersonIds = new Set(index.records.filter((record) => record.kind === "person").map((record) => record.id));
  const publicTopicIds = new Set(index.records.filter((record) => record.kind === "topic").map((record) => record.id));
  for (const record of index.records) {
    const identity = `${record.kind}:${record.id}`;
    if (
      identities.has(identity) ||
      routes.has(record.route) ||
      !record.id ||
      !record.title ||
      !hasCanonicalSearchRoute(record) ||
      record.direct_quote_eligible !== false ||
      (record.kind === "finding" && record.wording_type !== "PARAPHRASE") ||
      (record.kind !== "finding" && record.wording_type !== null) ||
      !Array.isArray(record.primary_terms) ||
      !Array.isArray(record.secondary_terms)
      || (record.kind === "finding" && (
        (record.person_id !== undefined && (
          typeof record.person_id !== "string" ||
          !PUBLIC_FACET_ID.test(record.person_id) ||
          !publicPersonIds.has(record.person_id)
        )) ||
        (record.topic_ids !== undefined && (!Array.isArray(record.topic_ids) ||
          record.topic_ids.some((id) => typeof id !== "string" || !PUBLIC_FACET_ID.test(id) || !publicTopicIds.has(id)) ||
          new Set(record.topic_ids).size !== record.topic_ids.length))
      ))
      || (record.kind !== "finding" && (record.person_id !== undefined || record.topic_ids !== undefined))
    ) {
      throw new Error("SEARCH_INDEX_RECORD_INVALID");
    }
    identities.add(identity);
    routes.add(record.route);
  }
  return index;
}

function timestamp(record: PublicSearchRecord): number {
  const parsed = record.published_at ? Date.parse(record.published_at) : 0;
  return Number.isFinite(parsed) ? parsed : 0;
}

function relevance(record: PublicSearchRecord, needle: string): number {
  if (!needle) return 0;
  const primary = record.primary_terms.map(normalizeSearchText);
  const secondary = record.secondary_terms.map(normalizeSearchText);
  if (primary.some((term) => term === needle)) return 400;
  if (primary.some((term) => term.includes(needle))) return 300;
  if (secondary.some((term) => term === needle)) return 200;
  if (secondary.some((term) => term.includes(needle))) return 100;
  return -1;
}

export function searchPublicIndex(
  index: PublicSearchIndex,
  rawQuery: string,
  filters: SearchFilters = {},
): SearchResponse {
  const query = String(rawQuery ?? "").trim();
  if ([...query].length > SEARCH_QUERY_MAX_CHARS) {
    return { status: "QUERY_TOO_LONG", records: [] };
  }
  const needle = normalizeSearchText(query);
  const kind = filters.kind ?? "ALL";
  const assessment = filters.assessment ?? "ALL";
  const personId = filters.personId ?? "ALL";
  const topicId = filters.topicId ?? "ALL";
  const sort = filters.sort ?? (needle ? "relevance" : "recent");

  const rows = index.records
    .map((record) => ({ record, score: relevance(record, needle) }))
    .filter(({ record, score }) =>
      (!needle || score >= 0) &&
      (kind === "ALL" || record.kind === kind) &&
      (assessment === "ALL" || record.assessment === assessment) &&
      (personId === "ALL" || (record.kind === "finding" && record.person_id === personId)) &&
      (topicId === "ALL" || (record.kind === "finding" && record.topic_ids?.includes(topicId)))
    );

  rows.sort((left, right) => {
    if (sort === "relevance" && needle && left.score !== right.score) {
      return right.score - left.score;
    }
    const dateDelta = timestamp(left.record) - timestamp(right.record);
    if (dateDelta !== 0) return sort === "old" ? dateDelta : -dateDelta;
    return left.record.kind.localeCompare(right.record.kind) ||
      left.record.id.localeCompare(right.record.id);
  });
  return { status: "OK", records: rows.map(({ record }) => record) };
}
