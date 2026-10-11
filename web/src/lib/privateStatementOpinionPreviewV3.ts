/** DP437 experimental Statement-centric *private* reader.
 *
 * It consumes the real pinned Person/Statement/index/Topic cross-reader
 * contracts. The caller must independently read CURRENT release pins twice.
 * This is not a new route or an authority signer: without a real approved
 * current release no quote is eligible, even for a syntactically valid input.
 */
import { canonicalJson } from "./searchIndex.ts";
import { readPinnedPrivatePublicPersonV3, type PrivatePublicPersonPins,
  type PrivatePersonSourceCard } from "./privatePublicPersonEmptyV3.ts";
import { validateOriginalStatement, type PublicOriginalStatement } from "./statementV3.ts";

const ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const UNAVAILABLE = Object.freeze({
  status: "UNAVAILABLE" as const, publicationAuthorized: false as const,
  providerCalls: 0 as const, message: "Risorsa non disponibile" as const,
  statement: null,
});
export interface PrivateStatementOpinionPins extends PrivatePublicPersonPins {
  allowPrivateStatementOpinion: true;
  releaseId: string;
  epoch: number;
}
export interface PrivateStatementOpinionCard {
  statementId: string;
  statementRoute: string;
  versionId: string;
  statementDate: string;
  speechAct: "OPINION";
  findingId: null;
  assessment: null;
  originalText: string;
  language: string;
  quoteSha256: string;
  sourceSha256: string;
  sourceUrl: string;
  sourceTitle: string;
  sourceVersion: string;
  contentId: string;
  personId: string;
  personRoute: string;
  personDisplayName: string;
  locator: PublicOriginalStatement["locator"];
  reviewedSummary: PublicOriginalStatement["summary"];
  reviewedTranslation: PublicOriginalStatement["translation"];
}
export type PrivateStatementOpinionResult =
  | typeof UNAVAILABLE
  | {status:"READY"; publicationAuthorized:false;providerCalls:0;
     statement:PrivateStatementOpinionCard};

function fault(reason: string): never { throw new Error("DP437_PRIVATE_" + reason); }
function pinsMatch(a: PrivateStatementOpinionPins, b: PrivateStatementOpinionPins): boolean {
  return canonicalJson(a) === canonicalJson(b);
}
function matchesArchive(row: PrivatePersonSourceCard, source: PublicOriginalStatement): boolean {
  return row.statementId === source.statement_id &&
    row.versionId === source.version_id &&
    row.statementDate === source.statement_date &&
    row.quoteSha256 === source.quote_sha256 &&
    row.sourceSha256 === source.source_sha256 &&
    row.sourceVersion === source.source_version &&
    row.contentId === source.content_id &&
    row.sourceUrl === source.source_url &&
    row.sourceTitle === source.source_title &&
    row.originalText === source.original_text &&
    row.findingId === source.finding_id &&
    canonicalJson(row.locator) === canonicalJson(source.locator);
}

/**
 * Returns a single approved, original and source-linked OPINION with *no*
 * fabricated Finding or verdict. Unknown/HELD/non-endorsed/reporting quotes
 * and removed statements all share exactly one response.
 */
export async function readPrivateStatementOpinionV3(
  artifacts: {people:unknown; join:unknown; index:unknown; source:unknown;
    sitemapPersonRoutes:unknown},
  expected: PrivateStatementOpinionPins,
  readCurrentPins: () => Promise<PrivateStatementOpinionPins>,
  personId: string, statementId: string,
): Promise<PrivateStatementOpinionResult> {
  if (expected?.allowPrivateStatementOpinion !== true ||
      typeof readCurrentPins !== "function" ||
      typeof expected.releaseId !== "string" || !ID.test(expected.releaseId) ||
      !Number.isSafeInteger(expected.epoch) || expected.epoch < 0) fault("PIN_REQUIRED");
  async function current(): Promise<PrivateStatementOpinionPins> {
    let value: PrivateStatementOpinionPins;
    try { value = await readCurrentPins(); }
    catch { return fault("CURRENT_RELEASE_UNAVAILABLE"); }
    if (!value || !pinsMatch(value, expected)) fault("CURRENT_RELEASE_CHANGED");
    return value;
  }
  await current();
  const person = await readPinnedPrivatePublicPersonV3(
    artifacts, {...expected,allowPrivatePersonPreview:true}, personId);
  let result: PrivateStatementOpinionResult = UNAVAILABLE;
  if (typeof statementId === "string" && ID.test(statementId) &&
      person.status === "APPROVED_WITH_STATEMENTS") {
    const cards = person.statements.filter(row => row.statementId === statementId);
    if (cards.length > 1) fault("DUPLICATE_MEMBERSHIP");
    const card = cards[0];
    const source = artifacts.source as {statements?:unknown};
    if (card && Array.isArray(source.statements)) {
      const entries = source.statements.filter((row:unknown) =>
        !!row && typeof row === "object" && "statement_id" in row &&
        row.statement_id === statementId);
      if (entries.length !== 1) fault("SOURCE_REVISION_STALE");
      const original = await validateOriginalStatement(entries[0]);
      if (!matchesArchive(card,original)) fault("SOURCE_REVISION_STALE");
      if (original.person_id !== person.person.personId) fault("IDENTITY_STALE");
      if (original.speech_act === "OPINION" && original.endorsed === true &&
          original.finding_id === null) {
        result = {status:"READY",publicationAuthorized:false,providerCalls:0,
          statement:{
            statementId:card.statementId,versionId:card.versionId,
            statementDate:card.statementDate,statementRoute:card.statementRoute,
            speechAct:"OPINION",findingId:null,assessment:null,
            originalText:card.originalText,language:card.language,
            quoteSha256:card.quoteSha256,sourceSha256:card.sourceSha256,
            sourceUrl:card.sourceUrl,sourceTitle:card.sourceTitle,
            sourceVersion:card.sourceVersion,contentId:card.contentId,
            personId:person.person.personId,personRoute:person.person.route,
            personDisplayName:person.person.displayName,
            locator:structuredClone(card.locator),
            reviewedSummary:original.summary === null ? null : structuredClone(original.summary),
            reviewedTranslation:original.translation === null ? null : structuredClone(original.translation),
          }};
      }
    }
  }
  // Refresh CURRENT independently even on withheld results: a withdrawal
  // that races archive/index inspection cannot leak a stale snippet.
  await current();
  return result;
}
