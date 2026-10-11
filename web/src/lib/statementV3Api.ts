/** DP-436: opt-in reader for the backend's already-governed v3 API detail.
 *
 * No HTTP request, route, publication decision, source-rights approval or
 * v2-to-v3 conversion is performed here. Callers must pin a dataset hash
 * independently from the payload they are reading.
 */
import { PUBLIC_STATEMENT_V3_SCHEMA, type StatementSpeechAct } from "./statementV3.ts";
import { canonicalJson } from "./searchIndex.ts";

export interface PublicStatementV3ApiRecord {
  statement_id: string;
  version_id: string;
  statement_date: string;
  person: { id: string; name: string };
  source: {
    content_id: string;
    title: string;
    url: string;
    version_id: string;
    sha256: string;
    kind: "WRITTEN" | "TIMED";
  };
  original: {
    wording_type: "VERBATIM_ORIGINAL";
    text: string;
    language: string;
    quote_sha256: string;
    locator: {
      start_char: number;
      end_char: number;
      segment_id?: string;
      start_ms?: number;
      end_ms?: number;
    };
  };
  speech_act: StatementSpeechAct;
  endorsed: boolean;
  finding_id: string | null;
  summary: null | { wording_type: "SUMMARY"; text: string; source_quote_sha256: string };
  translation: null | {
    wording_type: "TRANSLATION";
    text: string;
    source_quote_sha256: string;
    source_language: string;
    language: string;
  };
}

export interface PublicStatementV3ApiDetail {
  meta: {
    public_schema_version: typeof PUBLIC_STATEMENT_V3_SCHEMA;
    dataset_sha256: string;
    generated_at: string;
  };
  data: PublicStatementV3ApiRecord;
}

const HASH = /^[a-f0-9]{64}$/;
const ACTS = new Set<string>(["DIRECT_ASSERTION", "OPINION", "REPORTED_QUOTE", "CRITICISM", "IRONY"]);
const hasText = (value: unknown): value is string => typeof value === "string" && !!value.trim();
const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

function exactFields(value: unknown, fields: readonly string[]): asserts value is Record<string, unknown> {
  if (!isRecord(value) || Object.keys(value).length !== fields.length ||
      fields.some((field) => !Object.hasOwn(value, field))) {
    throw new Error("PUBLIC_STATEMENT_API_FIELDS_INVALID");
  }
}

function validDate(value: unknown): value is string {
  if (!hasText(value) || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

async function digest(value: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function validatePublicStatementV3Detail(
  value: unknown,
  options: { allowStatementV3?: boolean; expectedDatasetSha256?: string; expectedRecordSha256?: string },
): Promise<PublicStatementV3ApiDetail> {
  if (options.allowStatementV3 !== true) throw new Error("PUBLIC_STATEMENT_API_OPT_IN_REQUIRED");
  if (!HASH.test(options.expectedDatasetSha256 ?? "")) {
    throw new Error("PUBLIC_STATEMENT_API_FINGERPRINT_REQUIRED");
  }
  if (!HASH.test(options.expectedRecordSha256 ?? "")) {
    throw new Error("PUBLIC_STATEMENT_API_RECORD_FINGERPRINT_REQUIRED");
  }
  exactFields(value, ["meta", "data"]);
  const meta = value.meta;
  exactFields(meta, ["public_schema_version", "dataset_sha256", "generated_at"]);
  if (meta.public_schema_version !== PUBLIC_STATEMENT_V3_SCHEMA) {
    throw new Error("PUBLIC_STATEMENT_API_SCHEMA_INCOMPATIBLE");
  }
  if (meta.dataset_sha256 !== options.expectedDatasetSha256 ||
      !hasText(meta.generated_at) || !Number.isFinite(Date.parse(meta.generated_at))) {
    throw new Error("PUBLIC_STATEMENT_API_FINGERPRINT_MISMATCH");
  }

  const record = value.data;
  exactFields(record, [
    "statement_id", "version_id", "statement_date", "person", "source", "original",
    "speech_act", "endorsed", "finding_id", "summary", "translation",
  ]);
  exactFields(record.person, ["id", "name"]);
  exactFields(record.source, ["content_id", "title", "url", "version_id", "sha256", "kind"]);
  exactFields(record.original, ["wording_type", "text", "language", "quote_sha256", "locator"]);

  const source = record.source;
  const original = record.original;
  const textFields = [
    record.statement_id, record.version_id, record.person.id, record.person.name,
    source.content_id, source.title, source.url, source.version_id, original.text,
    original.language,
  ];
  if (textFields.some((item) => !hasText(item)) || String(original.text).length > 2000 ||
      !validDate(record.statement_date) || !HASH.test(String(source.sha256)) ||
      !HASH.test(String(original.quote_sha256)) || original.wording_type !== "VERBATIM_ORIGINAL" ||
      !["WRITTEN", "TIMED"].includes(String(source.kind)) ||
      !ACTS.has(String(record.speech_act)) || typeof record.endorsed !== "boolean" ||
      (record.finding_id !== null && !hasText(record.finding_id))) {
    throw new Error("PUBLIC_STATEMENT_API_RECORD_INCOMPATIBLE");
  }
  try {
    const url = new URL(source.url as string);
    if (url.protocol !== "https:" || !url.hostname || url.username || url.password) throw new Error();
  } catch {
    throw new Error("PUBLIC_STATEMENT_API_SOURCE_INVALID");
  }
  if (["REPORTED_QUOTE", "CRITICISM", "IRONY"].includes(record.speech_act as string) && record.endorsed) {
    throw new Error("PUBLIC_STATEMENT_API_ENDORSEMENT_INVALID");
  }

  const locator = original.locator;
  exactFields(locator, source.kind === "TIMED"
    ? ["start_char", "end_char", "segment_id", "start_ms", "end_ms"]
    : ["start_char", "end_char"]);
  if (!Number.isSafeInteger(locator.start_char) || !Number.isSafeInteger(locator.end_char) ||
      (locator.start_char as number) < 0 ||
      (locator.end_char as number) - (locator.start_char as number) !== [...(original.text as string)].length ||
      (source.kind === "TIMED" && (
        !hasText(locator.segment_id) || !Number.isSafeInteger(locator.start_ms) ||
        !Number.isSafeInteger(locator.end_ms) || (locator.start_ms as number) < 0 ||
        (locator.end_ms as number) <= (locator.start_ms as number)
      ))) {
    throw new Error("PUBLIC_STATEMENT_API_LOCATOR_INVALID");
  }
  if (await digest(original.text as string) !== original.quote_sha256) {
    throw new Error("PUBLIC_STATEMENT_API_QUOTE_TAMPERED");
  }
  for (const kind of ["summary", "translation"] as const) {
    const derived = record[kind];
    if (derived === null) continue;
    exactFields(derived, kind === "summary"
      ? ["wording_type", "text", "source_quote_sha256"]
      : ["wording_type", "text", "source_quote_sha256", "source_language", "language"]);
    if (derived.wording_type !== kind.toUpperCase() ||
        !hasText(derived.text) || derived.text.length > 2000 ||
        derived.text === original.text || derived.source_quote_sha256 !== original.quote_sha256 ||
        (kind === "translation" && (
          derived.source_language !== original.language ||
          !hasText(derived.language) || derived.language === original.language
        ))) {
      throw new Error("PUBLIC_STATEMENT_API_DERIVATION_INVALID");
    }
  }
  // A dataset digest carried by the API detail is only a *claim*: it cannot
  // prove that this particular record belongs to the approved snapshot.
  // Require a separately pinned digest from a trusted, verified bundle read.
  // Never accept a digest derived from this untrusted API response itself.
  if (await digest(canonicalJson(record)) !== options.expectedRecordSha256) {
    throw new Error("PUBLIC_STATEMENT_API_RECORD_FINGERPRINT_MISMATCH");
  }
  return value as unknown as PublicStatementV3ApiDetail;
}
