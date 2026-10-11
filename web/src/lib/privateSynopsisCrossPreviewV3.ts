/**
 * DP-440 private synopsis/Person×Topic/Statement/source preview.
 *
 * All input artifacts are already-public v3 projections, and every pin must
 * come from the same independent CURRENT release issuer. This composition
 * neither grants rights nor evaluates the truth/endorsement of an opinion.
 * It creates no route, signed authority, new public output or provider call.
 */
import {canonicalJson} from "./searchIndex.ts";
import {
  readPinnedPublicSynopsisV3,
  type PublicSynopsisV3Pins,
  type PinnedPublicSynopsisV3,
} from "./publicSynopsisV3.ts";
import {
  readPinnedPrivatePublicPersonV3,
  type PrivatePublicPersonPins,
  type ApprovedPrivatePersonPreview,
} from "./privatePublicPersonEmptyV3.ts";
import {type PublicStatementSearchV3} from "./publicStatementSearchV3.ts";
import {type PublicOriginalStatement} from "./statementV3.ts";

const ID=/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const HASH=/^[0-9a-f]{64}$/;
const obj=(value:unknown):value is Record<string,unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
function fault(code:string):never {throw new Error("DP440_PRIVATE_"+code);}

/** Obtained from independent authority, never constructed from preview assets. */
export interface PrivateSynopsisCrossPreviewPins
  extends PrivatePublicPersonPins,PublicSynopsisV3Pins {
  allowPrivateSynopsisCrossPreview: true;
  releaseId: string;
  epoch: number;
}
export interface PrivateSynopsisSourceCitation {
  statementId:string;
  versionId:string;
  statementRoute:string;
  originalText:string;
  speakerName:string;
  statementDate:string;
  language:string;
  quoteSha256:string;
  sourceSha256:string;
  contentId:string;
  sourceTitle:string;
  sourceUrl:string;
  sourceVersion:string;
  sourceKind:PublicOriginalStatement["source_kind"];
  speechAct:"OPINION";
  endorsed:true;
  findingId:string|null;
  locator:PublicOriginalStatement["locator"];
}
export interface PrivateSynopsisCrossPreview {
  status:"PRIVATE_PINNED_SYNOPSIS_PREVIEW";
  publicationAuthorized:false;
  providerCalls:0;
  person:{personId:string;route:string;displayName:string};
  topic:{topicId:string;route:string};
  coverageNote:string;
  snapshotAt:string;
  sourceGeneratedAt:string;
  sentences:Array<{
    text:string;
    kind:"SOURCE_LIST_ONLY"|"REVIEWED_DESCRIPTIVE_SUMMARY";
    citations:PrivateSynopsisSourceCitation[];
  }>;
}
type PreviewAssets={
  people:unknown;join:unknown;index:unknown;source:unknown;
  synopsis:unknown;sitemapPersonRoutes:unknown;
};

function validatePins(value:PrivateSynopsisCrossPreviewPins):void {
  if (!obj(value) || value.allowPrivateSynopsisCrossPreview !== true ||
      value.allowPrivatePersonPreview !== true || value.allowSynopsisV3 !== true) {
    fault("OPT_IN_REQUIRED");
  }
  if (typeof value.releaseId !== "string" || !ID.test(value.releaseId) ||
      !Number.isSafeInteger(value.epoch) || value.epoch < 0 ||
      !ID.test(value.personId) || !ID.test(value.topicId) ||
      ![value.personSha256,value.statementSha256,value.intersectionSha256,
        value.indexSha256,value.personSitemapSha256,value.synopsisSha256,
        value.synopsisFingerprint,value.publicDatasetSha256].every(
        v=>typeof v==="string" && HASH.test(v)) ||
      value.publicDatasetSha256 !== value.statementSha256 ||
      value.publicGeneratedAt !== value.sourceGeneratedAt) {
    fault("PIN_REQUIRED");
  }
}

function matchCitation(
  cited:PinnedPublicSynopsisV3["sentences"][number]["citations"][number],
  card:ApprovedPrivatePersonPreview["statements"][number],
  index:PublicStatementSearchV3["records"][number],
  source:PublicOriginalStatement,
  pins:PrivateSynopsisCrossPreviewPins,
):boolean {
  return source.person_id === pins.personId &&
    source.statement_id === cited.statementId && source.statement_id === card.statementId &&
    source.statement_id === index.statement_id &&
    source.version_id === cited.versionId && source.version_id === card.versionId &&
    source.version_id === index.version_id &&
    source.statement_date === cited.statementDate &&
    source.statement_date === card.statementDate &&
    source.statement_date === index.statement_date &&
    source.original_text === card.originalText &&
    source.original_text === index.original.text &&
    source.quote_sha256 === cited.quoteSha256 &&
    source.quote_sha256 === card.quoteSha256 &&
    source.quote_sha256 === index.original.quote_sha256 &&
    source.source_sha256 === cited.sourceSha256 &&
    source.source_sha256 === card.sourceSha256 &&
    source.source_sha256 === index.source.sha256 &&
    source.source_url === cited.sourceUrl &&
    source.source_url === card.sourceUrl &&
    source.source_url === index.source.url &&
    source.source_version === card.sourceVersion &&
    source.source_version === index.source.version_id &&
    source.source_title === card.sourceTitle &&
    source.source_title === index.source.title &&
    source.content_id === card.contentId &&
    source.content_id === index.source.content_id &&
    source.source_kind === index.source.kind &&
    source.language === cited.language && source.language === card.language &&
    source.language === index.original.language &&
    canonicalJson(source.locator) === canonicalJson(cited.locator) &&
    canonicalJson(source.locator) === canonicalJson(card.locator) &&
    canonicalJson(source.locator) === canonicalJson(index.original.locator) &&
    cited.statementRoute === card.statementRoute &&
    cited.statementRoute === index.statement_route &&
    index.person_id === pins.personId &&
    index.topics.some(topic=>topic.topic_id === pins.topicId) &&
    source.speech_act === "OPINION" && source.endorsed === true;
}

/**
 * Only a private isolated consumer can call this function. The release issuer
 * MUST check correction/withdrawal and rotate all pins atomically at serving
 * time. Double-reading current pins detects changes during this local read,
 * but it cannot substitute for a transactional public serving/cache gate.
 */
export async function readPrivateSynopsisCrossPreviewV3(
  artifacts:PreviewAssets,
  expected:PrivateSynopsisCrossPreviewPins,
  readCurrentPins:()=>Promise<PrivateSynopsisCrossPreviewPins>,
):Promise<PrivateSynopsisCrossPreview> {
  validatePins(expected);
  if (typeof readCurrentPins !== "function") fault("CURRENT_RELEASE_UNAVAILABLE");
  const reference=canonicalJson(expected);
  async function checkCurrent():Promise<void> {
    let current:PrivateSynopsisCrossPreviewPins;
    try { current=await readCurrentPins(); }
    catch { fault("CURRENT_RELEASE_UNAVAILABLE"); }
    if (!obj(current) || canonicalJson(current) !== reference) fault("CURRENT_RELEASE_CHANGED");
    validatePins(current);
    const expires=Date.parse(expected.validUntil);
    if (typeof expected.validUntil !== "string" ||
        !/(?:Z|[+-]\d{2}:\d{2})$/.test(expected.validUntil) ||
        !Number.isFinite(expires) || expires <= Date.now()) fault("AUTHORITY_EXPIRED");
  }
  await checkCurrent();
  // Snapshot once: asynchronous validation cannot race a mutation of the
  // caller's input objects and silently mix two source generations.
  let snapshot:PreviewAssets;
  try { snapshot=structuredClone(artifacts); }
  catch { fault("ASSETS_INVALID"); }
  if (!obj(snapshot) || !obj(snapshot.source) || !obj(snapshot.index) ||
      !Array.isArray(snapshot.source.statements) ||
      !Array.isArray(snapshot.index.records)) fault("ASSETS_INVALID");
  const synopsis=await readPinnedPublicSynopsisV3(
    snapshot.synopsis,snapshot.source,expected);
  const person=await readPinnedPrivatePublicPersonV3({
    people:snapshot.people,join:snapshot.join,index:snapshot.index,
    source:snapshot.source,sitemapPersonRoutes:snapshot.sitemapPersonRoutes,
  },expected,expected.personId);
  if (person.status !== "APPROVED_WITH_STATEMENTS" ||
      person.person.personId !== expected.personId) fault("PERSON_NOT_APPROVED");

  const rows=snapshot.source.statements as PublicOriginalStatement[];
  const indexed=(snapshot.index as unknown as PublicStatementSearchV3).records;
  const citedSentences:PrivateSynopsisCrossPreview["sentences"]=[];
  const topicRoutes=new Set<string>();
  for (const sentence of synopsis.sentences) {
    const citations:PrivateSynopsisSourceCitation[]=[];
    for (const citation of sentence.citations) {
      const cards=person.statements.filter(s=>s.statementId===citation.statementId);
      const originals=rows.filter(s=>s.statement_id===citation.statementId);
      const entries=indexed.filter(s=>s.statement_id===citation.statementId);
      if (cards.length!==1 || originals.length!==1 || entries.length!==1 ||
          !matchCitation(citation,cards[0],entries[0],originals[0],expected)) {
        fault("MEMBERSHIP_STALE");
      }
      const topic=entries[0].topics.find(t=>t.topic_id===expected.topicId);
      if (!topic) fault("MEMBERSHIP_STALE");
      topicRoutes.add(topic.topic_route);
      const source=originals[0];
      citations.push({
        statementId:source.statement_id,
        versionId:source.version_id,
        statementRoute:citation.statementRoute,
        originalText:source.original_text,
        speakerName:source.speaker_name,
        statementDate:source.statement_date,
        language:source.language,
        quoteSha256:source.quote_sha256,
        sourceSha256:source.source_sha256,
        contentId:source.content_id,
        sourceTitle:source.source_title,
        sourceUrl:source.source_url,
        sourceVersion:source.source_version,
        sourceKind:source.source_kind,
        speechAct:"OPINION",
        endorsed:true,
        findingId:source.finding_id,
        locator:structuredClone(source.locator),
      });
    }
    citedSentences.push({text:sentence.text,kind:sentence.kind,citations});
  }
  if (topicRoutes.size!==1) fault("TOPIC_ROUTE_STALE");
  const topicRoute=[...topicRoutes][0];
  const result:PrivateSynopsisCrossPreview={
    status:"PRIVATE_PINNED_SYNOPSIS_PREVIEW",
    publicationAuthorized:false,providerCalls:0,
    person:{personId:person.person.personId,route:person.person.route,
      displayName:person.person.displayName},
    topic:{topicId:expected.topicId,route:topicRoute},
    coverageNote:synopsis.coverageNote,
    snapshotAt:synopsis.snapshotAt,
    sourceGeneratedAt:expected.sourceGeneratedAt,
    sentences:citedSentences,
  };
  // Refuse stale/revoked pins discovered after async source and join checks.
  await checkCurrent();
  return result;
}
