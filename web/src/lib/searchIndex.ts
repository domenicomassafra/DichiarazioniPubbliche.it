import type { PublicDossier, PublicProjection } from "./types";

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
  };
}

export function buildExploreSearch(state: ExploreUrlState): string {
  const params = new URLSearchParams();
  const query = state.query.trim();
  if (query) params.set("q", query);
  if (state.assessment !== "ALL") params.set("esito", state.assessment);
  if (state.kind !== "ALL") params.set("tipo", state.kind);
  if (state.sort !== "relevance") params.set("ordine", state.sort);
  return params.toString();
}

function publicIdSlug(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/\p{M}+/gu, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
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
  };
}

export function buildSearchIndexMaterial(projection: PublicProjection): Omit<PublicSearchIndex, "index_sha256"> {
  const records: PublicSearchRecord[] = projection.dossiers.map(findingRecord);

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
  for (const record of index.records) {
    const identity = `${record.kind}:${record.id}`;
    if (
      identities.has(identity) ||
      !record.id ||
      !record.title ||
      !record.route.startsWith("/") ||
      record.direct_quote_eligible !== false ||
      (record.kind === "finding" && record.wording_type !== "PARAPHRASE") ||
      (record.kind !== "finding" && record.wording_type !== null) ||
      !Array.isArray(record.primary_terms) ||
      !Array.isArray(record.secondary_terms)
    ) {
      throw new Error("SEARCH_INDEX_RECORD_INVALID");
    }
    identities.add(identity);
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
  const sort = filters.sort ?? (needle ? "relevance" : "recent");

  const rows = index.records
    .map((record) => ({ record, score: relevance(record, needle) }))
    .filter(({ record, score }) =>
      (!needle || score >= 0) &&
      (kind === "ALL" || record.kind === kind) &&
      (assessment === "ALL" || record.assessment === assessment)
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
