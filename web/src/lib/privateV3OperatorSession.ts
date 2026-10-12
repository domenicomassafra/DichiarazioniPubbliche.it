/**
 * DP-439 opt-in, operator-only Person × Topic v3 inspection session.
 *
 * Reuses the existing DP-439 pinned search and DP-440 pinned original/synopsis
 * browser. No network request, admin privilege, topic inference, public route,
 * publication authorization or asynchronous provider work is created here.
 * The real operator SSR endpoint must enforce auth, private/no-store headers,
 * and obtain CURRENT release pins from an independently authenticated issuer.
 */
import {canonicalJson} from "./searchIndex.ts";
import {
  parsePrivatePersonTopicUrl,
  readPrivatePersonTopicV3,
  type PrivatePersonTopicPins,
  type PrivatePersonTopicRead,
  type PrivatePersonTopicRow,
} from "./privatePersonTopicV3.ts";
import {
  readPrivateSynopsisBrowserV3,
  type PrivateSynopsisBrowserV3,
} from "./privateSynopsisBrowserV3.ts";
import {type PrivateSynopsisCrossPreviewPins} from "./privateSynopsisCrossPreviewV3.ts";

const fault=(code:string):never=>{throw new Error("DP439_SESSION_"+code);};
const escapeHtml=(value:string):string=>value.replace(/[&<>"']/g,character=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;",
})[character] ?? character);
const ROUTE=/^\/dichiarazioni\/[a-z0-9]+(?:-[a-z0-9]+)*\/$/;
const PIN_TIME=/(?:Z|[+-]\d{2}:\d{2})$/;

type Assets={
  people:unknown;join:unknown;index:unknown;source:unknown;
  synopsis:unknown;sitemapPersonRoutes:unknown;
};
/** All pin fields must originate from one authenticated CURRENT release. */
export interface PrivateV3OperatorSessionPins
  extends PrivateSynopsisCrossPreviewPins,PrivatePersonTopicPins {
  allowPrivatePersonTopic:true;
}
export interface PrivateV3OperatorSession {
  status:"PRIVATE_OPERATOR_SESSION";
  publicationAuthorized:false;
  providerCalls:0;
  robots:"noindex,nofollow,noarchive";
  /** Escape-safe HTML for a private authenticated, no-store Astro SSR context. */
  html:string;
  shareableQuery:string;
  resultCount:number;
  page:number;
  previousUrl:string|null;
  nextUrl:string|null;
  rows:PrivatePersonTopicRow[];
  synopsisCount:number;
  snapshotAt:string;
}

function pinGuard(pins:PrivateV3OperatorSessionPins):void {
  if (!pins || pins.allowPrivatePersonTopic!==true ||
      pins.allowPrivateSynopsisCrossPreview!==true ||
      pins.allowSynopsisV3!==true || pins.allowPrivatePersonPreview!==true ||
      pins.statementSha256!==pins.publicDatasetSha256 ||
      pins.sourceGeneratedAt!==pins.publicGeneratedAt ||
      pins.generatedAt!==pins.sourceGeneratedAt ||
      typeof pins.validUntil!=="string" ||
      !PIN_TIME.test(pins.validUntil) ||
      !Number.isFinite(Date.parse(pins.validUntil)) ||
      Date.parse(pins.validUntil)<=Date.now()) {
    fault("MIXED_RELEASE_OR_EXPIRED");
  }
}

function renderQuery(
  query:PrivatePersonTopicRead,
  browser:PrivateSynopsisBrowserV3,
  shareableQuery:string,
):string {
  if (query.publicationAuthorized!==false || query.providerCalls!==0 ||
      browser.publicationAuthorized!==false || browser.providerCalls!==0 ||
      query.records.length>50 || browser.sentenceCount<1 || browser.sentenceCount>8) {
    fault("DATA_INVALID");
  }
  const fragments=[
    '<section data-private-v3-operator-session aria-label="Sessione privata Persona e Tema">',
    '<p>Uso operatore · solo anteprima privata, nessuna approvazione o pubblicazione</p>',
    '<nav aria-label="Indirizzo condivisibile della sessione"><a href="?' +
      escapeHtml(shareableQuery) + '" data-session-url>Riapri questa ricerca</a></nav>',
    '<p role="status" aria-live="polite" data-session-result-count>'+
      query.totalResults+' risultati nel corpus pubblico approvato; pagina '+
      query.page+' di '+query.pageCount+'</p>',
    '<p data-session-coverage>'+escapeHtml(query.coverageNote)+'</p>',
    '<p>Snapshot delle dichiarazioni: <time datetime="'+escapeHtml(query.generatedAt)+'">'+
      escapeHtml(query.generatedAt)+'</time></p>',
    '<nav aria-label="Indice delle dichiarazioni della pagina"><ol>',
    ...query.records.map((_,i)=>'<li><a href="#dp439-operator-record-'+(i+1)+
      '">Dichiarazione '+(i+1)+'</a></li>'),
    '</ol></nav>',
  ];
  for(const [i,row] of query.records.entries()){
    if(!ROUTE.test(row.statementRoute) || row.originalText.length>2000 ||
       !row.originalText.trim() || row.sourceTitle.length>300 ||
       row.personName.length>300) fault("UNSAFE_RECORD");
    const number=i+1;
    fragments.push(
      '<article id="dp439-operator-record-'+number+'" tabindex="-1" data-original-statement>',
      '<h2>Dichiarazione '+number+' · '+escapeHtml(row.personName)+'</h2>',
      '<blockquote lang="'+escapeHtml(row.language)+'">'+escapeHtml(row.originalText)+'</blockquote>',
      '<p><time datetime="'+escapeHtml(row.statementDate)+'">'+
        escapeHtml(row.statementDate)+'</time> · '+escapeHtml(row.sourceTitle)+'</p>',
      '<p><a href="'+escapeHtml(row.statementRoute)+'" rel="nofollow" data-version="'+
        escapeHtml(row.versionId)+'" data-quote-sha="'+escapeHtml(row.quoteSha256)+
        '">Originale e provenienza</a></p>',
      '<nav aria-label="Navigazione delle dichiarazioni"><span>'+
        (i>0?'<a href="#dp439-operator-record-'+i+'">Precedente</a>':'Precedente')+
        '</span> · <span>'+
        (i+1<query.records.length?'<a href="#dp439-operator-record-'+(number+1)+
          '">Successiva</a>':'Successiva')+
        '</span></nav></article>',
    );
  }
  fragments.push(
    '<nav aria-label="Pagine della ricerca">'+
      (query.previousUrl===null?'<span>Pagina precedente non disponibile</span>':
        '<a data-previous-page href="?'+escapeHtml(query.previousUrl)+'">Pagina precedente</a>')+
      ' · '+
      (query.nextUrl===null?'<span>Pagina successiva non disponibile</span>':
        '<a data-next-page href="?'+escapeHtml(query.nextUrl)+'">Pagina successiva</a>')+
      '</nav>',
    '<p data-synopsis-scope>La sintesi descrive le fonti raccolte nel corpus, non solo i risultati filtrati.</p>',
    browser.html,
    '</section>',
  );
  return fragments.join("");
}

/**
 * Independent CURRENT release check before, between and after async reads,
 * including after HTML composition. The caller's assets are snapshotted once;
 * changed pins, stale source/rights or mismatched Person×Topic withhold ALL
 * session HTML rather than combining two individually valid but mixed epochs.
 */
export async function readPrivateV3OperatorSession(
  artifacts:Assets,
  expected:PrivateV3OperatorSessionPins,
  urlQuery:string,
  readCurrentPins:()=>Promise<PrivateV3OperatorSessionPins>,
  options:{pageSize?:number}={},
):Promise<PrivateV3OperatorSession> {
  pinGuard(expected);
  if(typeof readCurrentPins!=="function") fault("CURRENT_UNAVAILABLE");
  const state=parsePrivatePersonTopicUrl(urlQuery);
  if(state.personId!==expected.personId || state.topicId!==expected.topicId) {
    fault("PERSON_TOPIC_SCOPE_MISMATCH");
  }
  const reference=canonicalJson(expected);
  const checkCurrent=async():Promise<void>=>{
    let latest:PrivateV3OperatorSessionPins;
    try {latest=await readCurrentPins();}
    catch{throw new Error("DP439_SESSION_CURRENT_UNAVAILABLE");}
    if(!latest || canonicalJson(latest)!==reference) fault("CURRENT_CHANGED");
    pinGuard(latest);
  };
  await checkCurrent();
  let snapshot:Assets;
  try{snapshot=structuredClone(artifacts);}
  catch{throw new Error("DP439_SESSION_SNAPSHOT_INVALID");}
  const input={index:snapshot.index,people:snapshot.people,source:snapshot.source};
  const query=await readPrivatePersonTopicV3(input,expected,urlQuery,{
    pageSize:options.pageSize,
  });
  await checkCurrent();
  if(query.records.some(row=>row.personId!==expected.personId ||
       !row.topicIds.includes(expected.topicId) || row.topicRoute===null)) {
    fault("CROSS_PERSON_TOPIC_RESULT");
  }
  const browser=await readPrivateSynopsisBrowserV3(snapshot,expected,readCurrentPins);
  if(Date.parse(browser.snapshotAt)<Date.parse(query.generatedAt) || browser.publicationAuthorized!==false ||
      browser.providerCalls!==0) fault("MIXED_SNAPSHOT");
  // Independent cross-check of all source versions present both in the
  // paginated search and in the synopsis. Absence is not false endorsement.
  const rendered=renderQuery(query,browser,
    urlQuery.startsWith("?")?urlQuery.slice(1):urlQuery);
  await checkCurrent();
  return {
    status:"PRIVATE_OPERATOR_SESSION",
    publicationAuthorized:false,providerCalls:0,
    robots:"noindex,nofollow,noarchive",
    html:rendered,shareableQuery:urlQuery.startsWith("?")?urlQuery.slice(1):urlQuery,
    resultCount:query.totalResults,page:query.page,
    previousUrl:query.previousUrl,nextUrl:query.nextUrl,
    rows:structuredClone(query.records),
    synopsisCount:browser.sentenceCount,snapshotAt:browser.snapshotAt,
  };
}
