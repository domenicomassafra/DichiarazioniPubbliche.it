/** DP-438: private opt-in, pinned zero-Statement Person/archived opinion reader.
 *
 * Not an HTTP route, approval issuer, person search, sitemap publisher, or
 * rights check replacement. Every SHA/expiry must be issued out of band by the
 * current authenticated public release owner, never read from these assets.
 */
import { canonicalJson } from "./searchIndex.ts";
import { readApprovedPersonV3, type ApprovedPersonV3, type ApprovedPersonV3Collection,
  type ApprovedPersonV3Role } from "./publicPersonV3.ts";
import { preflightPublicV3CrossReaderRelease } from "./publicV3CrossReaderRelease.ts";
import { validatePublicStatementSearchV3, type PublicStatementSearchV3,
  type V3IndexPins } from "./publicStatementSearchV3.ts";
import { validateOriginalStatement, PUBLIC_STATEMENT_V3_SCHEMA,
  type PublicOriginalStatement } from "./statementV3.ts";

const SHA = /^[a-f0-9]{64}$/;
const ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const ROUTE = /^\/persone\/[a-z0-9]+(?:-[a-z0-9]+)*\/$/;
const obj = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
function fail(code: string): never { throw new Error("DP438_PRIVATE_" + code); }
async function digest(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(canonicalJson(value));
  const sum = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(sum)].map(b => b.toString(16).padStart(2, "0")).join("");
}
function instant(value: unknown): number | null {
  if (typeof value !== "string" || !/(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}
export interface PrivatePublicPersonPins extends V3IndexPins {
  allowPrivatePersonPreview: boolean;
  /** The v3 source publication timestamp is NOT included in source dataset SHA. */
  sourceGeneratedAt: string;
  /** Independent checksum for the exact set of approved Person sitemap paths. */
  personSitemapSha256: string;
  validUntil: string;
}
export interface PrivatePersonSourceCard {
  statementId: string;
  versionId: string;
  statementRoute: string;
  statementDate: string;
  originalText: string;
  language: string;
  quoteSha256: string;
  sourceSha256: string;
  sourceVersion: string;
  sourceUrl: string;
  sourceTitle: string;
  contentId: string;
  locator: PublicOriginalStatement["locator"];
  findingId: string | null;
  roleAtStatement: ApprovedPersonV3Role | null;
}
export interface ApprovedPrivatePersonPreview {
  status: "APPROVED_EMPTY" | "APPROVED_WITH_STATEMENTS";
  publicationAuthorized: false;
  providerCalls: 0;
  searchStatementCount: number;
  sitemapPersonRoutes: string[];
  person: {
    personId: string;
    route: string;
    displayName: string;
    disambiguator: string | null;
    entityVersion: string;
    profileScope: string;
    roles: ApprovedPersonV3Role[];
  };
  emptyState: string | null;
  statements: PrivatePersonSourceCard[];
}
export interface UnavailablePrivatePersonPreview {
  status: "UNAVAILABLE";
  publicationAuthorized: false;
  providerCalls: 0;
  message: "Risorsa non disponibile";
  person: null;
}
export type PrivatePersonPreview = ApprovedPrivatePersonPreview | UnavailablePrivatePersonPreview;
const UNAVAILABLE: UnavailablePrivatePersonPreview = Object.freeze({
  status: "UNAVAILABLE", publicationAuthorized: false, providerCalls: 0,
  message: "Risorsa non disponibile", person: null,
});

function expectedRole(roles: ApprovedPersonV3Role[], onDate: string): ApprovedPersonV3Role | null {
  const matching = roles.filter(r => r.valid_from <= onDate && (r.valid_to === null || r.valid_to >= onDate));
  return matching.length === 1 ? matching[0] : null;
}
function exactMatch(item: ApprovedPersonV3["statements"][number], source: PublicOriginalStatement): boolean {
  return item.statement_id === source.statement_id && item.version_id === source.version_id &&
    item.statement_date === source.statement_date && item.content_id === source.content_id &&
    item.source_title === source.source_title && item.source_url === source.source_url &&
    item.source_version === source.source_version && item.source_kind === source.source_kind &&
    item.source_sha256 === source.source_sha256 && item.original_text === source.original_text &&
    item.quote_sha256 === source.quote_sha256 && item.language === source.language &&
    item.speech_act === source.speech_act && source.endorsed === true &&
    item.finding_id === source.finding_id &&
    canonicalJson(item.locator) === canonicalJson(source.locator);
}
/** Return an approved Person zero-state or source-verified cards, or a constant
 * generic unavailable response shared by unknown/private/withdrawn identities.
 *
 * A caller must rotate ALL current release pins and generated static artifacts
 * atomically after any future rights/identity revocation. Historical matching
 * hashes do not themselves reveal a revocation unknown to the release issuer.
 */
export async function readPinnedPrivatePublicPersonV3(
  input: { people: unknown; join: unknown; index: unknown; source: unknown; sitemapPersonRoutes: unknown },
  pins: PrivatePublicPersonPins,
  identifier: string,
): Promise<PrivatePersonPreview> {
  // The approved collection, v3 source, search index, sitemap and independent
  // pins are one point-in-time release. Never consume caller-owned objects
  // after an awaited digest, even if a nested reader cloned its own input.
  let detached: {input: typeof input; pins: PrivatePublicPersonPins};
  try { detached=structuredClone({input,pins}); }
  catch { fail("SOURCE_STALE"); }
  input=detached.input;
  pins=detached.pins;
  if (pins?.allowPrivatePersonPreview !== true) fail("OPT_IN_REQUIRED");
  if (!obj(pins) || ![pins.personSha256, pins.statementSha256, pins.intersectionSha256,
    pins.indexSha256, pins.personSitemapSha256].every(h => typeof h === "string" && SHA.test(h)) ||
    instant(pins.sourceGeneratedAt) === null) fail("PIN_REQUIRED");
  const expires = instant(pins.validUntil);
  if (expires === null || expires <= Date.now() ||
      (instant(pins.sourceGeneratedAt) as number) > Date.now()) fail("AUTHORITY_EXPIRED");
  if (!obj(input) || !obj(input.source) || !obj(input.people) || !Array.isArray(input.source.statements) ||
    !Array.isArray(input.source.topics) || !Array.isArray(input.source.contents) ||
    !Array.isArray(input.source.dossiers) || input.source.statements.length > 10000 ||
    input.source.schema_version !== PUBLIC_STATEMENT_V3_SCHEMA ||
    input.source.dataset_sha256 !== pins.statementSha256 ||
    input.source.generated_at !== pins.sourceGeneratedAt) fail("SOURCE_STALE");
  if (await digest({dossiers:input.source.dossiers,topics:input.source.topics,
    contents:input.source.contents,statements:input.source.statements}) !== pins.statementSha256) fail("SOURCE_STALE");
  const people = input.people as unknown as ApprovedPersonV3Collection;
  // Validates the ENTIRE approved collection, not only the requested identity.
  await readApprovedPersonV3(people, {allowPersonV3:true,
    expectedCollectionSha256:pins.personSha256,identifier:"preview:unknown"});
  const indexed: PublicStatementSearchV3 = await validatePublicStatementSearchV3(input.index, pins);
  if (indexed.generated_at !== pins.sourceGeneratedAt) fail("SOURCE_STALE");
  // This separately validates the original Python DP439 join against the
  // indexed records and their current Person-backed source versions.
  await preflightPublicV3CrossReaderRelease({
    people:input.people, join:input.join, index:input.index,
  }, {allowV3Preview:true,personSha256:pins.personSha256,
    statementSha256:pins.statementSha256,intersectionSha256:pins.intersectionSha256,
    indexSha256:pins.indexSha256,validUntil:pins.validUntil});
  if (!Array.isArray(input.sitemapPersonRoutes) ||
    input.sitemapPersonRoutes.some(route => typeof route !== "string" || !ROUTE.test(route))) fail("SITEMAP_STALE");
  const paths = [...input.sitemapPersonRoutes] as string[];
  const expected = people.people.map(p => p.route).sort();
  if (paths.length !== new Set(paths).size ||
    canonicalJson(paths) !== canonicalJson(expected) ||
    await digest(paths) !== pins.personSitemapSha256) fail("SITEMAP_STALE");
  const bySource = new Map<string, PublicOriginalStatement>();
  for (const raw of input.source.statements) {
    const current = await validateOriginalStatement(raw);
    if (bySource.has(current.statement_id)) fail("SOURCE_REVISION_CONFLICT");
    bySource.set(current.statement_id, current);
  }
  // Revalidate all Person membership rows, not only records tagged to a Topic
  // in the search index: an approved opinion without Topic is still eligible.
  const archiveById = new Map<string, {person: ApprovedPersonV3; item: ApprovedPersonV3["statements"][number]}>();
  for (const person of people.people) {
    for (const item of person.statements) {
      const original = bySource.get(item.statement_id);
      if (!original || original.person_id !== person.person_id || !exactMatch(item,original) ||
        item.role_at_statement !== null &&
          canonicalJson(item.role_at_statement) !== canonicalJson(expectedRole(person.roles,item.statement_date)) ||
        item.role_at_statement === null && expectedRole(person.roles,item.statement_date) !== null ||
        archiveById.has(item.statement_id)) fail("SOURCE_REVISION_STALE");
      archiveById.set(item.statement_id,{person,item});
    }
  }
  // A current published Statement attributed to an already-published Person
  // cannot silently disappear from that Person archive and be reclassified
  // as "approved zero" by a separately self-consistent projection.
  const visiblePeople = new Set(people.people.map(person => person.person_id));
  for (const statement of bySource.values()) {
    if (visiblePeople.has(statement.person_id) && statement.endorsed &&
      (statement.speech_act === "OPINION" || statement.speech_act === "DIRECT_ASSERTION") &&
      !archiveById.has(statement.statement_id)) fail("SOURCE_REVISION_STALE");
  }
  // Missing indexed identities or phantom/index-only records are refused.
  for (const indexedRecord of indexed.records) {
    const entry = archiveById.get(indexedRecord.statement_id);
    if (!entry || entry.person.person_id !== indexedRecord.person_id ||
      entry.item.version_id !== indexedRecord.version_id ||
      entry.item.source_url !== indexedRecord.source.url ||
      entry.item.source_sha256 !== indexedRecord.source.sha256 ||
      entry.item.quote_sha256 !== indexedRecord.original.quote_sha256 ||
      entry.item.statement_date !== indexedRecord.statement_date ||
      canonicalJson(entry.item.locator) !== canonicalJson(indexedRecord.original.locator)) fail("INDEX_STALE");
  }
  // The final sitemap/source SHA may complete after validUntil. Never return
  // a Person (or a generic unavailable result) from an expired release.
  if (expires <= Date.now()) fail("AUTHORITY_EXPIRED");
  // No request-specific material is projected before all cross-release checks.
  if (typeof identifier !== "string" || !ID.test(identifier)) return UNAVAILABLE;
  const person = people.people.find(p => p.person_id === identifier || p.slug === identifier);
  if (!person) return UNAVAILABLE;
  const cards: PrivatePersonSourceCard[] = person.statements.map(row => ({
    statementId:row.statement_id,versionId:row.version_id,statementRoute:row.statement_route,
    statementDate:row.statement_date,originalText:row.original_text,
    language:row.language,quoteSha256:row.quote_sha256,sourceSha256:row.source_sha256,
    sourceVersion:row.source_version,sourceUrl:row.source_url,sourceTitle:row.source_title,
    contentId:row.content_id,locator:structuredClone(row.locator),findingId:row.finding_id,
    roleAtStatement:row.role_at_statement === null ? null : structuredClone(row.role_at_statement),
  }));
  return {
    status:cards.length?"APPROVED_WITH_STATEMENTS":"APPROVED_EMPTY",
    publicationAuthorized:false,providerCalls:0,
    searchStatementCount:indexed.records.filter(r=>r.person_id===person.person_id).length,
    sitemapPersonRoutes:[...paths],
    person:{personId:person.person_id,route:person.route,displayName:person.display_name,
      disambiguator:person.disambiguator,entityVersion:person.entity_version,
      profileScope:person.profile_scope,roles:structuredClone(person.roles)},
    emptyState:cards.length?null:"Nessuna dichiarazione pubblicata per questa persona",
    statements:cards,
  };
}
