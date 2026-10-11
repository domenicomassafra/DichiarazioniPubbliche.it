/** DP-440: explicit opt-in browser/SSR reader for precomputed Python v3 synopsis.
 *
 * A Python READY_READ_MODEL receipt is never an approval certificate. The
 * caller must obtain these pins from an independently authenticated current
 * release authority; values copied out of either downloaded payload grant
 * nothing. This module does not fetch, generate, publish or activate routes.
 */
import { canonicalJson } from "./searchIndex.ts";
import { publicIdSlug } from "./format.ts";
import {
  PUBLIC_STATEMENT_V3_SCHEMA,
  validateOriginalStatement,
  type PublicOriginalStatement,
} from "./statementV3.ts";

export const PUBLIC_SYNOPSIS_V3_SCHEMA = "public-synopsis-v3-opt-in" as const;
const SHA = /^[0-9a-f]{64}$/;
const ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,149}$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const TIMEZONE = /(?:Z|[+-]\d{2}:\d{2})$/;

type JsonObject = Record<string, unknown>;
type Locator = PublicOriginalStatement["locator"];
const obj = (value: unknown): value is JsonObject =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const exact = (value: unknown, fields: readonly string[]): value is JsonObject =>
  obj(value) && Object.keys(value).length === fields.length &&
  fields.every((field) => Object.hasOwn(value, field));
const sha = (value: unknown): value is string => typeof value === "string" && SHA.test(value);
const id = (value: unknown): value is string => typeof value === "string" && ID.test(value);
const text = (value: unknown, length: number): value is string =>
  typeof value === "string" && value.length > 0 && value.length <= length &&
  value.trim() === value && !/[\u0000-\u001f\u007f]/u.test(value);
const instant = (value: unknown): number | null => {
  if (typeof value !== "string" || !TIMEZONE.test(value)) return null;
  const milliseconds = Date.parse(value);
  return Number.isFinite(milliseconds) ? milliseconds : null;
};
const day = (value: unknown): value is string =>
  typeof value === "string" && DATE.test(value) &&
  Number.isFinite(Date.parse(value + "T00:00:00Z")) &&
  new Date(value + "T00:00:00Z").toISOString().slice(0, 10) === value;
function fail(code: string): never { throw new Error(code); }

async function hash(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(canonicalJson(value));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
}

export interface PublicSynopsisV3Pins {
  allowSynopsisV3: boolean;
  /** SHA of the entire Python dataclass DTO; independently released. */
  synopsisSha256: string;
  /** Opaque Python fingerprint, pinned separately: its private material is omitted. */
  synopsisFingerprint: string;
  /** Current, independently released public-v3 Statement dataset fingerprint. */
  publicDatasetSha256: string;
  /** Projection timestamp is outside Python's dataset hash: pin it separately. */
  publicGeneratedAt: string;
  personId: string;
  topicId: string;
  /** Finite independent membership/current-rights validity; MUST be refreshed. */
  validUntil: string;
}

export interface PinnedSynopsisCitationV3 {
  statementId: string;
  versionId: string;
  statementRoute: string;
  quoteSha256: string;
  sourceSha256: string;
  sourceUrl: string;
  statementDate: string;
  language: string;
  locator: Locator;
}

export interface PinnedPublicSynopsisV3 {
  status: "PINNED_PREVIEW_ONLY";
  publicationAuthorized: false;
  providerCalls: 0;
  personId: string;
  topicId: string;
  coverageNote: string;
  snapshotAt: string;
  publicDatasetSha256: string;
  sentences: Array<{
    text: string;
    kind: "SOURCE_LIST_ONLY" | "REVIEWED_DESCRIPTIVE_SUMMARY";
    citations: PinnedSynopsisCitationV3[];
  }>;
}

/** Pure async read: works with `crypto.subtle` in SSR and in secure browsers.
 *
 * `now` is the host's trusted clock, injectable for deterministic fixture
 * replay; callers must NEVER derive it or the pins from untrusted URL/input.
 * If the authority has not refreshed release pins after a revoke or correction,
 * no offline consumer can detect that unseen update before pin expiry.
 */
export async function readPinnedPublicSynopsisV3(
  synopsis: unknown,
  publicBundle: unknown,
  pins: PublicSynopsisV3Pins,
  now: Date = new Date(),
): Promise<PinnedPublicSynopsisV3> {
  if (pins?.allowSynopsisV3 !== true) fail("PUBLIC_SYNOPSIS_V3_OPT_IN_REQUIRED");
  if (!obj(pins) || !sha(pins.synopsisSha256) || !sha(pins.synopsisFingerprint) ||
      !sha(pins.publicDatasetSha256) || instant(pins.publicGeneratedAt) === null ||
      !id(pins.personId) || !id(pins.topicId)) {
    fail("PUBLIC_SYNOPSIS_V3_PIN_REQUIRED");
  }
  const observedAt = now instanceof Date ? now.getTime() : NaN;
  const expires = instant(pins.validUntil);
  if (!Number.isFinite(observedAt) || expires === null || expires <= observedAt) {
    fail("PUBLIC_SYNOPSIS_V3_AUTHORITY_EXPIRED");
  }
  if (!obj(synopsis) || synopsis.status !== "READY_READ_MODEL") {
    fail("PUBLIC_SYNOPSIS_V3_WITHHELD");
  }
  if (!exact(synopsis, ["status", "reason_code", "schema_version", "person_id", "topic_id",
    "dataset_sha256", "fingerprint", "coverage_note", "snapshot_at", "sentences", "provider_calls"]) ||
    synopsis.schema_version !== PUBLIC_SYNOPSIS_V3_SCHEMA ||
    synopsis.reason_code !== "SYNOPSIS_OFFLINE_REVIEWED_CITATIONS_READY" ||
    synopsis.provider_calls !== 0 || !sha(synopsis.fingerprint) ||
    !text(synopsis.coverage_note, 450) ||
    !/(corpus|raccolt|copertur)/i.test(synopsis.coverage_note) ||
    !Array.isArray(synopsis.sentences) ||
    synopsis.sentences.length < 1 || synopsis.sentences.length > 8) {
    fail("PUBLIC_SYNOPSIS_V3_SCHEMA_INVALID");
  }
  if (synopsis.person_id !== pins.personId || synopsis.topic_id !== pins.topicId) {
    fail("PUBLIC_SYNOPSIS_V3_SCOPE_MISMATCH");
  }
  if (synopsis.dataset_sha256 !== pins.publicDatasetSha256 ||
      synopsis.fingerprint !== pins.synopsisFingerprint ||
      await hash(synopsis) !== pins.synopsisSha256) {
    fail("PUBLIC_SYNOPSIS_V3_PIN_MISMATCH");
  }
  if (!obj(publicBundle) || publicBundle.schema_version !== PUBLIC_STATEMENT_V3_SCHEMA ||
      publicBundle.dataset_sha256 !== pins.publicDatasetSha256 ||
      publicBundle.generated_at !== pins.publicGeneratedAt ||
      !Array.isArray(publicBundle.dossiers) ||
      !Array.isArray(publicBundle.topics) ||
      !Array.isArray(publicBundle.contents) ||
      !Array.isArray(publicBundle.statements) ||
      publicBundle.statements.length > 10000) {
    fail("PUBLIC_SYNOPSIS_V3_SOURCE_INVALID");
  }
  // Mirrors public_schema.projection_dataset_sha256, which includes the
  // entire v3 collection (not merely selected citations). Withdrawal, rights
  // changes, wording, source version or membership changes invalidate the pin.
  const sourceMaterial = {
    dossiers: publicBundle.dossiers, topics: publicBundle.topics,
    contents: publicBundle.contents, statements: publicBundle.statements,
  };
  if (await hash(sourceMaterial) !== pins.publicDatasetSha256) {
    fail("PUBLIC_SYNOPSIS_V3_SOURCE_STALE");
  }
  const generatedAt = instant(publicBundle.generated_at);
  const snapshotAt = instant(synopsis.snapshot_at);
  if (generatedAt === null || snapshotAt === null || generatedAt > snapshotAt ||
      snapshotAt > observedAt || snapshotAt >= expires) {
    fail("PUBLIC_SYNOPSIS_V3_SOURCE_STALE");
  }
  const byKey = new Map<string, PublicOriginalStatement>();
  for (const raw of publicBundle.statements) {
    const statement = await validateOriginalStatement(raw);
    const key = JSON.stringify([statement.statement_id, statement.version_id]);
    if (byKey.has(key)) fail("PUBLIC_SYNOPSIS_V3_SOURCE_DUPLICATE");
    byKey.set(key, statement);
  }

  const rendered: PinnedPublicSynopsisV3["sentences"] = [];
  const independentContent = new Set<string>();
  const independentUrl = new Set<string>();
  const independentSource = new Set<string>();
  for (const raw of synopsis.sentences) {
    if (!exact(raw, ["text", "kind", "citations"]) || !text(raw.text, 500) ||
        !["SOURCE_LIST_ONLY", "REVIEWED_DESCRIPTIVE_SUMMARY"].includes(String(raw.kind)) ||
        !Array.isArray(raw.citations) || raw.citations.length < 1 || raw.citations.length > 12) {
      fail("PUBLIC_SYNOPSIS_V3_SCHEMA_INVALID");
    }
    const citations: PinnedSynopsisCitationV3[] = [];
    const seen = new Set<string>();
    for (const cited of raw.citations) {
      if (!exact(cited, ["statement_id", "version_id", "quote_sha256", "source_sha256",
        "source_url", "locator", "statement_date", "language"]) ||
        !id(cited.statement_id) || !id(cited.version_id) ||
        !sha(cited.quote_sha256) || !sha(cited.source_sha256) ||
        !day(cited.statement_date) || !text(cited.language, 30) ||
        !obj(cited.locator)) {
        fail("PUBLIC_SYNOPSIS_V3_CITATION_INVALID");
      }
      const key = JSON.stringify([cited.statement_id, cited.version_id]);
      const statement = byKey.get(key);
      if (seen.has(key) || !statement || statement.person_id !== pins.personId ||
          statement.quote_sha256 !== cited.quote_sha256 ||
          statement.source_sha256 !== cited.source_sha256 ||
          statement.source_url !== cited.source_url ||
          statement.statement_date !== cited.statement_date ||
          statement.language !== cited.language ||
          canonicalJson(statement.locator) !== canonicalJson(cited.locator) ||
          cited.statement_date > new Date(Math.min(generatedAt, snapshotAt)).toISOString().slice(0, 10)) {
        fail("PUBLIC_SYNOPSIS_V3_CITATION_STALE");
      }
      if (raw.kind === "REVIEWED_DESCRIPTIVE_SUMMARY" &&
          (!statement.endorsed || !["DIRECT_ASSERTION", "OPINION"].includes(statement.speech_act))) {
        fail("PUBLIC_SYNOPSIS_V3_REPORTED_SPEECH");
      }
      if (raw.text.includes(statement.original_text)) {
        fail("PUBLIC_SYNOPSIS_V3_VERBATIM_AS_SUMMARY");
      }
      const slug = publicIdSlug(statement.statement_id);
      if (!slug) fail("PUBLIC_SYNOPSIS_V3_CITATION_INVALID");
      independentContent.add(statement.content_id);
      independentUrl.add(statement.source_url);
      independentSource.add(statement.source_sha256);
      seen.add(key);
      citations.push({
        statementId: statement.statement_id,
        versionId: statement.version_id,
        statementRoute: `/dichiarazioni/${slug}/`,
        quoteSha256: statement.quote_sha256,
        sourceSha256: statement.source_sha256,
        sourceUrl: statement.source_url,
        statementDate: statement.statement_date,
        language: statement.language,
        locator: { ...statement.locator },
      });
    }
    rendered.push({
      text: raw.text as string,
      kind: raw.kind as "SOURCE_LIST_ONLY" | "REVIEWED_DESCRIPTIVE_SUMMARY",
      citations,
    });
  }
  if (Math.min(independentContent.size, independentUrl.size, independentSource.size) < 2) {
    fail("PUBLIC_SYNOPSIS_V3_SOURCES_INSUFFICIENT");
  }
  return {
    status: "PINNED_PREVIEW_ONLY",
    publicationAuthorized: false,
    providerCalls: 0,
    personId: pins.personId,
    topicId: pins.topicId,
    coverageNote: synopsis.coverage_note as string,
    snapshotAt: synopsis.snapshot_at as string,
    publicDatasetSha256: pins.publicDatasetSha256,
    sentences: rendered,
  };
}
