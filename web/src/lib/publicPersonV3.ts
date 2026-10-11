/** DP-405/438 opt-in public Person v3 archive reader.
 *
 * This is a consumer of a separately authorized, current public collection,
 * NOT permission to publish a private Person or an unreviewed Statement.
 * The collection pin must originate outside the candidate payload.
 */
import { canonicalJson } from "./searchIndex.ts";
import { publicIdSlug } from "./format.ts";

export const PUBLIC_PERSON_V3_SCHEMA = "dichiarazioni-pubbliche-public-v3-person-opt-in";

export interface ApprovedPersonV3Statement {
  statement_id: string; statement_route: string; version_id: string;
  statement_date: string; content_id: string; source_title: string;
  source_url: string; source_version: string; source_kind: "WRITTEN" | "TIMED";
  locator: {start_char: number; end_char: number; segment_id?: string; start_ms?: number; end_ms?: number};
  original_text: string; language: string; quote_sha256: string;
  source_sha256: string; speech_act: "DIRECT_ASSERTION" | "OPINION";
  finding_id: string | null; role_at_statement: ApprovedPersonV3Role | null;
}

export interface ApprovedPersonV3Role {
  role_id: string; label: string; organization: string | null;
  valid_from: string; valid_to: string | null; source_ref: string; source_url: string;
}

export interface ApprovedPersonV3 {
  person_id: string; slug: string; route: string; display_name: string;
  disambiguator: string | null; entity_version: string; profile_scope: string;
  status: "PUBLISHED"; roles: ApprovedPersonV3Role[];
  statements: ApprovedPersonV3Statement[];
}

export interface ApprovedPersonV3Collection {
  schema_version: typeof PUBLIC_PERSON_V3_SCHEMA;
  dataset_sha256: string;
  people: ApprovedPersonV3[];
}

const HASH = /^[0-9a-f]{64}$/;
const ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const hasText = (value: unknown): value is string => typeof value === "string" && !!value.trim();
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
function exact(value: unknown, keys: string[]): asserts value is Record<string, unknown> {
  if (!object(value) || Object.keys(value).length !== keys.length || keys.some((key) => !Object.hasOwn(value, key))) {
    throw new Error("PUBLIC_PERSON_V3_FIELDS_INVALID");
  }
}
function date(value: unknown): value is string {
  if (!hasText(value) || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const time = new Date(value);
  return Number.isFinite(time.getTime()) && time.toISOString().slice(0, 10) === value;
}
function safeUrl(value: unknown): boolean {
  try {
    if (!hasText(value)) return false;
    const url = new URL(value);
    return url.protocol === "https:" && !!url.hostname && !url.username && !url.password;
  } catch { return false; }
}
async function sha(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
}
function role(value: unknown): asserts value is ApprovedPersonV3Role {
  exact(value, ["role_id", "label", "organization", "valid_from", "valid_to", "source_ref", "source_url"]);
  if (!ID.test(String(value.role_id)) || !ID.test(String(value.source_ref)) ||
      !hasText(value.label) || (value.organization !== null && !hasText(value.organization)) ||
      !date(value.valid_from) || (value.valid_to !== null && (!date(value.valid_to) || value.valid_to < value.valid_from)) ||
      !safeUrl(value.source_url)) throw new Error("PUBLIC_PERSON_V3_ROLE_INVALID");
}
async function statement(value: unknown): Promise<void> {
  exact(value, ["statement_id", "statement_route", "version_id", "statement_date", "content_id",
    "source_title", "source_url", "source_version", "source_kind", "locator", "original_text",
    "language", "quote_sha256", "source_sha256", "speech_act", "finding_id", "role_at_statement"]);
  if (!ID.test(String(value.statement_id)) || !ID.test(String(value.version_id)) ||
      !ID.test(String(value.content_id)) || !ID.test(String(value.source_version)) ||
      value.statement_route !== `/dichiarazioni/${publicIdSlug(String(value.statement_id))}/` ||
      !date(value.statement_date) || !hasText(value.source_title) || !safeUrl(value.source_url) ||
      !hasText(value.original_text) || value.original_text.length > 2000 || !hasText(value.language) ||
      !HASH.test(String(value.source_sha256)) || !HASH.test(String(value.quote_sha256)) ||
      !["DIRECT_ASSERTION", "OPINION"].includes(String(value.speech_act)) ||
      (value.finding_id !== null && !ID.test(String(value.finding_id)))) {
    throw new Error("PUBLIC_PERSON_V3_STATEMENT_INVALID");
  }
  exact(value.locator, value.source_kind === "TIMED"
    ? ["start_char", "end_char", "segment_id", "start_ms", "end_ms"]
    : ["start_char", "end_char"]);
  const loc = value.locator;
  if (!Number.isSafeInteger(loc.start_char) || !Number.isSafeInteger(loc.end_char) ||
      (loc.start_char as number) < 0 ||
      (loc.end_char as number) - (loc.start_char as number) !== [...(value.original_text as string)].length ||
      (value.source_kind !== "TIMED" && value.source_kind !== "WRITTEN") ||
      (value.source_kind === "TIMED" && (!ID.test(String(loc.segment_id)) ||
        !Number.isSafeInteger(loc.start_ms) || !Number.isSafeInteger(loc.end_ms) ||
        (loc.start_ms as number) < 0 || (loc.end_ms as number) <= (loc.start_ms as number)))) {
    throw new Error("PUBLIC_PERSON_V3_LOCATOR_INVALID");
  }
  if (await sha(value.original_text as string) !== value.quote_sha256) {
    throw new Error("PUBLIC_PERSON_V3_QUOTE_TAMPERED");
  }
  if (value.role_at_statement !== null) {
    role(value.role_at_statement);
    if (value.role_at_statement.valid_from > value.statement_date ||
        (value.role_at_statement.valid_to !== null && value.role_at_statement.valid_to < value.statement_date)) {
      throw new Error("PUBLIC_PERSON_V3_ROLE_DATE_MISMATCH");
    }
  }
}

export async function readApprovedPersonV3(
  value: unknown,
  options: {allowPersonV3?: boolean; expectedCollectionSha256?: string; identifier: string},
): Promise<ApprovedPersonV3 | null> {
  if (options.allowPersonV3 !== true) throw new Error("PUBLIC_PERSON_V3_OPT_IN_REQUIRED");
  if (!HASH.test(options.expectedCollectionSha256 ?? "")) throw new Error("PUBLIC_PERSON_V3_PIN_REQUIRED");
  exact(value, ["schema_version", "dataset_sha256", "people"]);
  if (value.schema_version !== PUBLIC_PERSON_V3_SCHEMA || !Array.isArray(value.people) ||
      !HASH.test(String(value.dataset_sha256)) || value.people.length > 10000) {
    throw new Error("PUBLIC_PERSON_V3_SCHEMA_INVALID");
  }
  // Backend computes this digest on canonical sorted-key JSON of the complete
  // public collection. Hashing the *whole* list binds zero-record withdrawals.
  if (value.dataset_sha256 !== options.expectedCollectionSha256 ||
      await sha(canonicalJson(value.people)) !== value.dataset_sha256) {
    throw new Error("PUBLIC_PERSON_V3_COLLECTION_STALE_OR_TAMPERED");
  }
  const seen = new Set<string>();
  for (const person of value.people) {
    exact(person, ["person_id", "slug", "route", "display_name", "disambiguator",
      "entity_version", "profile_scope", "status", "roles", "statements"]);
    const id = String(person.person_id);
    const slug = String(person.slug);
    if (!ID.test(id) || !SLUG.test(slug) ||
        person.route !== `/persone/${person.slug}/` || !hasText(person.display_name) ||
        !ID.test(String(person.entity_version)) || !hasText(person.profile_scope) ||
        (person.disambiguator !== null && !hasText(person.disambiguator)) ||
        person.status !== "PUBLISHED" || !Array.isArray(person.roles) || !Array.isArray(person.statements) ||
        seen.has(id) || seen.has(slug)) {
      throw new Error("PUBLIC_PERSON_V3_IDENTITY_INVALID");
    }
    seen.add(id);
    seen.add(slug);
    person.roles.forEach(role);
    const statementIds = new Set<string>();
    for (const item of person.statements) {
      await statement(item);
      if (statementIds.has(item.statement_id)) throw new Error("PUBLIC_PERSON_V3_DUPLICATE_STATEMENT");
      statementIds.add(item.statement_id);
    }
  }
  if (!hasText(options.identifier)) throw new Error("PUBLIC_PERSON_V3_IDENTITY_REQUIRED");
  return value.people.find((person: ApprovedPersonV3) =>
    person.person_id === options.identifier || person.slug === options.identifier) ?? null;
}
