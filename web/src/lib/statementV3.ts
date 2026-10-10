/** Opt-in public Statement v3 consumer contract (DP-435/436).
 *
 * This does NOT turn on public-v3 routing. The source backend must first
 * independently authorize the exact excerpt, attribution, context and rights.
 * v2 normalized dossiers must never be reinterpreted as verbatim Statements.
 */
export const PUBLIC_STATEMENT_V3_SCHEMA = "dichiarazioni-pubbliche-public-v3-statement-opt-in" as const;

export type StatementSpeechAct =
  | "DIRECT_ASSERTION" | "OPINION" | "REPORTED_QUOTE" | "CRITICISM" | "IRONY";

export interface PublicOriginalStatement {
  statement_id: string;
  version_id: string;
  person_id: string;
  speaker_name: string;
  content_id: string;
  source_title: string;
  source_url: string;
  source_version: string;
  source_sha256: string;
  original_text: string;
  quote_sha256: string;
  language: string;
  statement_date: string;
  source_kind: "WRITTEN" | "TIMED";
  locator: {
    start_char: number;
    end_char: number;
    segment_id?: string;
    start_ms?: number;
    end_ms?: number;
  };
  speech_act: StatementSpeechAct;
  endorsed: boolean;
  review_provenance: {
    rights: string;
    attribution: string;
    context: string;
    wording: string;
    publication: string;
  };
  finding_id: string | null;
  summary: null | {
    wording_type: "SUMMARY";
    text: string;
    review_event_id: string;
    source_quote_sha256: string;
  };
  translation: null | {
    wording_type: "TRANSLATION";
    text: string;
    review_event_id: string;
    source_quote_sha256: string;
    source_language: string;
    language: string;
  };
}

const SHA256 = /^[0-9a-f]{64}$/;
const VALID_ACTS = new Set<StatementSpeechAct>([
  "DIRECT_ASSERTION", "OPINION", "REPORTED_QUOTE", "CRITICISM", "IRONY",
]);

function nonempty(value: unknown): value is string {
  return typeof value === "string" && !!value.trim();
}

async function digest(value: string): Promise<string> {
  const bytes = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** Defense-in-depth for an *already approved* v3 public projection record. */
export async function validateOriginalStatement(value: unknown): Promise<PublicOriginalStatement> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("PUBLIC_STATEMENT_INVALID");
  }
  const statement = value as PublicOriginalStatement;
  const requiredText = [
    statement.statement_id, statement.version_id, statement.person_id,
    statement.speaker_name, statement.content_id, statement.source_title,
    statement.source_url, statement.source_version, statement.language,
    statement.original_text, statement.statement_date,
  ];
  if (
    requiredText.some((item) => !nonempty(item)) ||
    statement.original_text.length > 2000 ||
    !SHA256.test(statement.source_sha256) ||
    !SHA256.test(statement.quote_sha256) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(statement.statement_date) ||
    !["WRITTEN", "TIMED"].includes(statement.source_kind) ||
    !VALID_ACTS.has(statement.speech_act) ||
    typeof statement.endorsed !== "boolean"
  ) {
    throw new Error("PUBLIC_STATEMENT_INCOMPATIBLE");
  }
  try {
    const url = new URL(statement.source_url);
    if (url.protocol !== "https:" || !url.hostname || url.username || url.password) {
      throw new Error("source URL not public HTTPS");
    }
  } catch {
    throw new Error("PUBLIC_STATEMENT_SOURCE_INVALID");
  }
  if (["REPORTED_QUOTE", "CRITICISM", "IRONY"].includes(statement.speech_act) && statement.endorsed) {
    throw new Error("PUBLIC_STATEMENT_UNSUPPORTED_ENDORSEMENT");
  }
  if (
    !statement.locator ||
    !Number.isSafeInteger(statement.locator.start_char) ||
    !Number.isSafeInteger(statement.locator.end_char) ||
    statement.locator.start_char < 0 ||
    statement.locator.end_char - statement.locator.start_char !== [...statement.original_text].length
  ) {
    throw new Error("PUBLIC_STATEMENT_LOCATOR_INVALID");
  }
  if (statement.source_kind === "TIMED" && (
    !nonempty(statement.locator.segment_id) ||
    !Number.isSafeInteger(statement.locator.start_ms) ||
    !Number.isSafeInteger(statement.locator.end_ms) ||
    Number(statement.locator.start_ms) < 0 ||
    Number(statement.locator.end_ms) <= Number(statement.locator.start_ms)
  )) {
    throw new Error("PUBLIC_STATEMENT_TIMED_LOCATOR_INVALID");
  }
  const reviews = statement.review_provenance;
  const ids = reviews && Object.values(reviews);
  if (
    !ids || ids.length !== 5 || !ids.every(nonempty) || new Set(ids).size !== 5
  ) {
    throw new Error("PUBLIC_STATEMENT_REVIEW_MISSING");
  }
  if (statement.finding_id !== null && !nonempty(statement.finding_id)) {
    throw new Error("PUBLIC_STATEMENT_FINDING_INVALID");
  }
  if ((await digest(statement.original_text)) !== statement.quote_sha256) {
    throw new Error("PUBLIC_STATEMENT_QUOTE_TAMPERED");
  }
  for (const kind of ["summary", "translation"] as const) {
    const derived = statement[kind];
    if (derived === null) continue;
    if (
      !derived ||
      derived.wording_type !== kind.toUpperCase() ||
      !nonempty(derived.text) ||
      derived.text === statement.original_text ||
      !nonempty(derived.review_event_id) ||
      derived.source_quote_sha256 !== statement.quote_sha256 ||
      (kind === "translation" && (
        !("source_language" in derived) ||
        derived.source_language !== statement.language ||
        !nonempty(derived.language) ||
        derived.language === statement.language
      ))
    ) {
      throw new Error("PUBLIC_STATEMENT_DERIVATION_INVALID");
    }
  }
  return statement;
}
