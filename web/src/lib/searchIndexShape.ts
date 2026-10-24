import type { PublicSearchIndex, PublicSearchRecord } from "./searchIndex.ts";

const INDEX_FIELDS = new Set([
  "schema_version", "projection_schema_version", "projection_sha256",
  "generated_at", "index_sha256", "records",
]);
const RECORD_FIELDS = new Set([
  "id", "kind", "title", "subtitle", "published_at", "assessment", "route",
  "has_corrections", "has_rights_of_reply", "wording_type",
  "source_wording_type", "direct_quote_eligible", "primary_terms",
  "secondary_terms", "person_id", "topic_ids",
]);
const KINDS = new Set(["finding", "content", "person", "topic"]);
const ASSESSMENTS = new Set([
  "SUPPORTED", "FACTUALLY_FALSE", "OUTDATED_DATA",
  "INSUFFICIENT_EVIDENCE", "UNRESOLVED",
]);

function isDisplaySafeRecord(value: unknown): value is PublicSearchRecord {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      Object.keys(value).some((field) => !RECORD_FIELDS.has(field))) return false;
  const record = value as Partial<PublicSearchRecord>;
  return KINDS.has(String(record.kind)) &&
    typeof record.id === "string" && record.id.trim().length > 0 &&
    typeof record.title === "string" && record.title.trim().length > 0 &&
    typeof record.subtitle === "string" &&
    typeof record.route === "string" &&
    (record.published_at === null ||
      (typeof record.published_at === "string" &&
       Number.isFinite(Date.parse(record.published_at)))) &&
    typeof record.has_corrections === "boolean" &&
    typeof record.has_rights_of_reply === "boolean" &&
    record.direct_quote_eligible === false &&
    (record.kind === "finding"
      ? record.wording_type === "PARAPHRASE"
      : record.wording_type === null) &&
    (record.assessment === null
      ? record.kind !== "finding"
      : record.kind === "finding" && ASSESSMENTS.has(record.assessment)) &&
    (record.source_wording_type === null ||
      record.source_wording_type === "VERBATIM_ORIGINAL" ||
      record.source_wording_type === "REPORTED_QUOTE") &&
    (record.kind === "finding" || record.source_wording_type === null) &&
    Array.isArray(record.primary_terms) &&
    record.primary_terms.every((term) => typeof term === "string") &&
    Array.isArray(record.secondary_terms) &&
    record.secondary_terms.every((term) => typeof term === "string");
}

/** A self-hash proves equality of bytes, not that display data are well typed
 * or that a public index contains only deliberately projected fields.
 */
export function assertSearchIndexShape(index: PublicSearchIndex): void {
  if (!Object.keys(index).every((field) => INDEX_FIELDS.has(field)) ||
      typeof index.generated_at !== "string" ||
      !Number.isFinite(Date.parse(index.generated_at))) {
    throw new Error("SEARCH_INDEX_INCOMPATIBLE");
  }
  if (!index.records.every(isDisplaySafeRecord)) {
    throw new Error("SEARCH_INDEX_RECORD_INVALID");
  }
}
