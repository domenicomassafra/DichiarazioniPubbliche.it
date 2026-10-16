/**
 * DP-440 isolated private synopsis browser. No public route, publication grant,
 * network fetch or generation. All content comes from the pinned cross-reader.
 *
 * An operator SSR caller must set X-Robots-Tag: noindex, nofollow and
 * Cache-Control: private, no-store in addition to rendering the robots meta.
 * The independent release issuer must rotate epochs on source/Topic withdrawal.
 */
import {canonicalJson} from "./searchIndex.ts";
import {
  readPrivateSynopsisCrossPreviewV3,
  type PrivateSynopsisCrossPreviewPins,
  type PrivateSynopsisCrossPreview,
} from "./privateSynopsisCrossPreviewV3.ts";

const ROUTES={
  statement:/^\/dichiarazioni\/[a-z0-9-]+\/$/,
  person:/^\/persone\/[a-z0-9-]+\/$/,
  topic:/^\/temi\/[a-z0-9-]+\/$/,
};
const escapes:Record<string,string>={
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;",
};
const html=(value:string):string=>value.replace(/[&<>"']/g,character=>escapes[character]);
const fault=(code:string):never=>{throw new Error("DP440_BROWSER_"+code);};

type PreviewAssets={
  people:unknown;join:unknown;index:unknown;source:unknown;
  synopsis:unknown;sitemapPersonRoutes:unknown;
};
export interface PrivateSynopsisBrowserV3 {
  status:"PRIVATE_BROWSER_PREVIEW_ONLY";
  publicationAuthorized:false;
  providerCalls:0;
  robots:"noindex,nofollow,noarchive";
  /** Sanitized HTML fragment; render only inside private/no-store SSR. */
  html:string;
  sentenceCount:number;
  citationCount:number;
  snapshotAt:string;
}

function render(view:PrivateSynopsisCrossPreview):Pick<
  PrivateSynopsisBrowserV3,"html"|"sentenceCount"|"citationCount"|"snapshotAt"
> {
  if (view.status!=="PRIVATE_PINNED_SYNOPSIS_PREVIEW" ||
      view.publicationAuthorized!==false || view.providerCalls!==0 ||
      view.sentences.length<1 || view.sentences.length>8 ||
      !ROUTES.person.test(view.person.route) || !ROUTES.topic.test(view.topic.route)) {
    fault("CROSS_PREVIEW_INVALID");
  }
  const fragments:string[]=[];
  let citationCount=0;
  fragments.push(
    '<main data-private-synopsis-browser aria-label="Anteprima privata Persona e Tema">',
    '<p data-private-only>Anteprima privata non pubblicabile · nessuna revisione automatica</p>',
    '<header><h1>'+html(view.person.displayName)+' — '+html(view.topic.topicId)+'</h1>',
    '<p><a href="'+html(view.person.route)+'">Scheda Persona</a> · ',
    '<a href="'+html(view.topic.route)+'">Scheda Tema</a></p>',
    '<p data-coverage>'+html(view.coverageNote)+'</p>',
    '<p data-snapshot>Snapshot: <time datetime="'+html(view.snapshotAt)+'">'+
      html(view.snapshotAt)+'</time></p></header>',
    '<nav aria-label="Indice delle sintesi"><ol>',
    ...view.sentences.map((_,i)=>
      '<li><a href="#dp440-synopsis-'+(i+1)+'">Sintesi '+(i+1)+'</a></li>'),
    '</ol></nav>',
  );
  for (const [i,sentence] of view.sentences.entries()) {
    if (sentence.citations.length<1 || sentence.citations.length>12 ||
        citationCount+sentence.citations.length>24) fault("CITATION_LIMIT");
    const current=i+1;
    const prev=i>0
      ? '<a href="#dp440-synopsis-'+i+'">Precedente</a>'
      : '<span aria-disabled="true">Precedente</span>';
    const next=i+1<view.sentences.length
      ? '<a href="#dp440-synopsis-'+(current+1)+'">Successiva</a>'
      : '<span aria-disabled="true">Successiva</span>';
    fragments.push(
      '<article id="dp440-synopsis-'+current+'" tabindex="-1" data-synopsis-entry>',
      '<h2>Sintesi '+current+' di '+view.sentences.length+'</h2>',
      '<p data-synopsis-text>'+html(sentence.text)+'</p>',
      '<nav aria-label="Navigazione della sintesi '+current+'">'+prev+' · '+next+'</nav>',
      '<p><a href="#dp440-source-'+current+'-1">Vai alla prima fonte originale</a></p>',
      '<section data-original-sources aria-label="Fonti originali citate">',
      '<h3>Frasi originali e documenti di origine</h3>',
    );
    for (const [j,citation] of sentence.citations.entries()) {
      let sourceUrl:URL|null=null;
      try { sourceUrl=new URL(citation.sourceUrl); }
      catch { fault("CITATION_SOURCE_URL_INVALID"); }
      if (!ROUTES.statement.test(citation.statementRoute) ||
          !sourceUrl || sourceUrl.protocol!=="https:" || !sourceUrl.hostname ||
          sourceUrl.username || sourceUrl.password ||
          citation.originalText.length>2000 || citation.originalText.length===0 ||
          citation.speakerName.length>300 || citation.sourceTitle.length>300) {
        fault("CITATION_ROUTE_OR_BODY_INVALID");
      }
      citationCount++;
      const anchor='dp440-source-'+current+'-'+(j+1);
      fragments.push(
        '<figure data-source-citation>',
        '<blockquote id="'+anchor+'" tabindex="-1" data-original-quote lang="'+
          html(citation.language)+'">'+html(citation.originalText)+'</blockquote>',
        '<figcaption>Originale '+(j+1)+' · '+html(citation.speakerName)+' · ',
        '<time datetime="'+html(citation.statementDate)+'">'+html(citation.statementDate)+'</time>',
        ' · '+html(citation.sourceTitle)+' · ',
        '<a href="'+html(citation.statementRoute)+'" rel="nofollow" data-quote-sha="'+
          html(citation.quoteSha256)+'" data-source-sha="'+html(citation.sourceSha256)+
          '">Apri dichiarazione originale</a>',
        ' · <a href="'+html(citation.sourceUrl)+'" rel="noreferrer noopener nofollow"',
        ' data-source-version="'+html(citation.sourceVersion)+'">Apri documento sorgente</a>',
        ' · <a href="#dp440-synopsis-'+current+'">Torna alla sintesi</a>',
        '</figcaption></figure>',
      );
    }
    fragments.push('</section></article>');
  }
  fragments.push('</main>');
  return {
    html:fragments.join(""),
    sentenceCount:view.sentences.length,
    citationCount,
    snapshotAt:view.snapshotAt,
  };
}

/**
 * Reuse the independent CURRENT release double-read and full source/Topic
 * citation binding. A third CURRENT epoch read protects the final SSR assembly
 * if a revoke arrives after the cross-reader's last await.
 */
export async function readPrivateSynopsisBrowserV3(
  artifacts:PreviewAssets,
  expected:PrivateSynopsisCrossPreviewPins,
  readCurrentPins:()=>Promise<PrivateSynopsisCrossPreviewPins>,
):Promise<PrivateSynopsisBrowserV3> {
  const cross=await readPrivateSynopsisCrossPreviewV3(artifacts,expected,readCurrentPins);
  const rendered=render(cross);
  let current:PrivateSynopsisCrossPreviewPins|undefined;
  try { current=await readCurrentPins(); }
  catch { fault("CURRENT_UNAVAILABLE"); }
  if (!current || canonicalJson(current)!==canonicalJson(expected) ||
      !Number.isFinite(Date.parse(expected.validUntil)) ||
      Date.parse(expected.validUntil)<=Date.now()) {
    fault("CURRENT_CHANGED");
  }
  return {
    status:"PRIVATE_BROWSER_PREVIEW_ONLY",
    publicationAuthorized:false,
    providerCalls:0,
    robots:"noindex,nofollow,noarchive",
    ...rendered,
  };
}
