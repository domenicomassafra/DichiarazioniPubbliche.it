/**
 * Isolated DP-429 public search suggestion check. No build, browser profile,
 * fixture publication, provider request or repository mutation is required.
 *
 * Run from web/ after installing its normal dev dependencies:
 * node scripts/check-dp429-public-query-suggestions-20261013.mjs
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const componentPath = path.join(webRoot, "src/components/ExploreClient.tsx");
const indexPath = path.join(webRoot, "src/lib/searchIndex.ts");
const builderPath = path.join(webRoot, "src/lib/searchRecordBuilders.ts");
const shapePath = path.join(webRoot, "src/lib/searchIndexShape.ts");
const source = await readFile(componentPath, "utf8");
const indexSource = await readFile(indexPath, "utf8");
const builderSource = await readFile(builderPath, "utf8");

// The current v2 index offers result/source publication timestamps, not a
// source-attested original declaration date or an archive addition timestamp.
// Any default labelled "recent declarations" is blocked until DP-409 extends
// its approved index/projection contract.
const recordContract = indexSource.split("export interface PublicSearchRecord {")[1]?.split("\n}")[0];
assert(recordContract, "public search record schema must be present");
assert.match(recordContract, /published_at: string \| null/);
assert.doesNotMatch(recordContract, /statement_date|declaration_date|added_at/);
assert.match(builderSource, /dossier\.finding\.published_at\s*\?\?\s*dossier\.source\.published_at/);

const transpile = (text, filename) => ts.transpileModule(text, {
  fileName: filename,
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX,
  },
}).outputText;
function load(text, filename, dependencies) {
  const out = { exports: {} };
  new Function("require", "module", "exports", transpile(text, filename))(
    (id) => {
      if (!(id in dependencies)) throw new Error("UNEXPECTED_TEST_IMPORT: " + id);
      return dependencies[id];
    }, out, out.exports,
  );
  return out.exports;
}
const shape = load(await readFile(shapePath, "utf8"), shapePath, {
  "./format.ts": { publicIdSlug: (id) => id.replaceAll(":", "-") },
});
const search = load(indexSource, indexPath, {
  "./searchIndexShape.ts": shape,
  "./format.ts": { publicIdSlug: (id) => id.replaceAll(":", "-") },
  "./searchRecordBuilders.ts": {
    compactTerms: (terms) => terms, findingRecord() {}, statementRecords() { return []; },
  },
  "./minisearchAdapter.ts": { publicTextScores: (records, query, fields, normalize) => new Map(
    records.flatMap((row, i) => {
      const terms = [...fields(row).primary, ...fields(row).secondary]
        .flatMap(term => normalize(term).split(" "));
      // Simulate a fuzzy retrieval hit while the typed spelling is wrong.
      return terms.some(term => term.startsWith(query) ||
        (query === "inflazone" && term === "inflazione")) ? [[i, 1]] : [];
    }),
  ) },
});

const sample = (id, title, kind = "finding", overrides = {}) => ({
  id, title, kind, subtitle: "", published_at: "2025-04-10",
  assessment: null, route: "/dichiarazioni/" + id + "/", has_corrections: false,
  has_rights_of_reply: false, wording_type: "PARAPHRASE", source_wording_type: null,
  direct_quote_eligible: false, primary_terms: [title], secondary_terms: [],
  person_id: "person:publica", topic_ids: ["topic:economia"], ...overrides,
});
const records = [
  sample("inflazione", "Inflazione nel bilancio"),
  sample("spesa", "Spesa pubblica"),
  sample("salari", "Salari dei lavoratori"),
  sample("immigrazione", "Immigrazione", "finding", { person_id: "person:diversa" }),
  sample("riservato", "Termine pubblico diverso", "finding", {
    primary_terms: ["Termine pubblico diverso"],
    secondary_terms: ["Notizia pubblicata"],
  }),
];
const index = { records };
const deps = {
  react: {
    useEffect() {},
    useMemo(fn) { return fn(); },
    useRef() { return { current: null }; },
    useState() { throw new Error("configure state before render"); },
  },
  "react/jsx-runtime": {
    jsx: (type, props, key) => ({ type, props: props ?? {}, key }),
    jsxs: (type, props, key) => ({ type, props: props ?? {}, key }),
    Fragment: "fragment",
  },
  "../lib/format": {
    assessmentLabel: (value) => value,
    assessmentTone: () => "neutral",
    formatDate: (value) => value,
  },
  "./design/SegmentedControl": { __esModule: true, default: () => null },
  "../lib/searchIndex": search,
};
const component = load(source, componentPath, deps);
assert.equal(typeof component.getExploreSuggestions, "function", "public-only suggestions function must exist");
assert.equal(typeof component.buildExploreUrlKeepingQuery, "function", "URL must retain exact typed query");
assert.equal(typeof component.getExploreActiveFilters, "function", "active mobile filters need a public-only accessible projection");
assert.equal(typeof component.getExploreFacetCounts, "function", "public facet options must show accurate approved intersection counts");

const publicFacets = { records: [
  sample("person:approved", "Persona verificata", "person", {route:"/persone/person-approved/",person_id:undefined,topic_ids:undefined}),
  sample("topic:approved", "Tema verificato", "topic", {route:"/temi/topic-approved/",person_id:undefined,topic_ids:undefined}),
] };
const activeState = {
  query:"non cambiare",kind:"finding",assessment:"SUPPORTED",sort:"recent",
  personId:"person:approved",topicId:"topic:approved",
};
const active = component.getExploreActiveFilters(publicFacets,activeState);
assert.deepEqual(active.map(item=>item.key),["kind","assessment","sort","personId","topicId"]);
assert(active.some(item=>item.label.includes("Persona verificata")));
assert(active.some(item=>item.label.includes("Tema verificato")));
const forgedState={...activeState,personId:"person:PRIVATE_DO_NOT_LEAK",topicId:"topic:PRIVATE_DO_NOT_LEAK"};
const safeLabels=component.getExploreActiveFilters(publicFacets,forgedState);
assert.doesNotMatch(JSON.stringify(safeLabels),/PRIVATE_DO_NOT_LEAK/,
  "an unrecognized URL facet must never echo a private person or topic ID");
assert.deepEqual(component.getExploreActiveFilters(publicFacets,{
  query:"",kind:"ALL",assessment:"ALL",sort:"relevance",personId:"ALL",topicId:"ALL",
}),[],"no chips for an empty filter state");
const countedIndex={records:[
  ...publicFacets.records,
  sample("topic:second", "Secondo tema", "topic", {route:"/temi/topic-second/",person_id:undefined,topic_ids:undefined}),
  sample("finding:one","Bilancio pubblico","finding",{person_id:"person:approved",topic_ids:["topic:approved"]}),
  sample("finding:two","Bilancio approvato","finding",{person_id:"person:approved",topic_ids:["topic:second"]}),
  sample("statement:one","Bilancio originale","statement",{
    person_id:"person:approved",wording_type:null,topic_ids:undefined,
  }),
  sample("finding:held","Totale altro","finding",{person_id:"person:other",topic_ids:["topic:else"]}),
]};
const counted=component.getExploreFacetCounts(countedIndex,"Bilancio",{assessment:"ALL",sort:"relevance"});
assert.equal(counted.people["person:approved"],3,
  "approved original Statements count towards their published Person facet");
assert.equal(counted.topics["topic:approved"],1);
assert.equal(counted.people["person:other"],undefined,"nonmatching records may not pollute visible option counts");
const intersection=component.getExploreFacetCounts(countedIndex,"Bilancio",{
  assessment:"ALL",sort:"relevance",topicId:"topic:approved",personId:"person:approved",
});
assert.equal(intersection.people["person:approved"],1);
assert.equal(intersection.topics["topic:approved"],1);
assert.equal(intersection.topics["topic:second"],1,
  "topic choices must count alternative approved memberships while ignoring the currently active Topic");

const raw = "  inflazone  ";
assert.equal(
  new URLSearchParams(component.buildExploreUrlKeepingQuery({
    query: raw, assessment: "ALL", kind: "ALL", sort: "relevance",
    personId: "ALL", topicId: "ALL",
  })).get("q"), raw,
  "the shared URL must replay the EXACT typed query including spaces",
);
assert.equal(
  new URLSearchParams(component.buildExploreUrlKeepingQuery({
    query: "  ", assessment: "ALL", kind: "finding", sort: "recent",
    personId: "ALL", topicId: "ALL",
  })).get("q"), "  ",
  "whitespace-only user queries must not be silently rewritten",
);

assert.deepEqual(
  component.getExploreSuggestions(index, raw, {}),
  ["  inflazione  "],
  "offer a real approved-index correction even when fuzzy retrieval found a hit",
);
assert.deepEqual(
  component.getExploreSuggestions(index, raw, { kind: "topic" }),
  [],
  "suggestions must respect the active public kind filter",
);
assert.deepEqual(
  component.getExploreSuggestions(index, "  inflazone  ", { personId: "person:diversa" }),
  [],
  "suggestions must respect approved Person facet membership",
);
assert.deepEqual(component.getExploreSuggestions(index, "", {}), []);
assert.deepEqual(component.getExploreSuggestions(index, "x".repeat(201), {}), []);
assert.deepEqual(component.getExploreSuggestions({ records: [] }, raw, {}), []);
assert.ok(
  component.getExploreSuggestions(index, "immigrazione", {}).length === 0,
  "do not suggest a correction for an exact public term",
);
assert.ok(
  component.getExploreSuggestions({
    records: Array.from({ length: 150 }, (_, i) => sample(String(i), "Parola" + String(i))),
  }, "parolb", {}).length <= 4,
  "suggestions must be bounded even with many public terms",
);

// P2: 24 valid-looking near words of the WRONG public type / person consumed
// the candidate budget before a legitimate later-ordered topic/person hit.
const decoys = ["aaaabbax", ...[..."abcdefghijklmnopqrstuvw"].map((letter) => "aaaabbb" + letter)];
assert.equal(decoys.length, 24);
const falseFindings = decoys.map((title, i) => sample(
  "other:" + i, title, "finding", { person_id: "person:other", assessment: "SUPPORTED" },
));
const validTopic = sample("topic:valid", "aaaabbby", "topic", {
  route: "/temi/valid/", person_id: undefined, topic_ids: undefined,
});
assert.deepEqual(
  component.getExploreSuggestions({ records: [...falseFindings, validTopic] }, "aaaabbbx", { kind: "topic" }),
  ["aaaabbby"],
  "active Topic type must not be starved by 24 other-type candidates",
);
assert.deepEqual(
  component.getExploreSuggestions({ records: falseFindings }, "aaaabbbx", { kind: "topic" }),
  [],
  "other-type terms must never be suggested when there is no Topic",
);
const validPersonFinding = sample("target:valid", "aaaabbby", "finding", {
  person_id: "person:target", assessment: "FACTUALLY_FALSE", topic_ids: ["topic:target"],
});
const mixedPeople = { records: [...falseFindings, validPersonFinding] };
assert.deepEqual(
  component.getExploreSuggestions(mixedPeople, "aaaabbbx", { personId: "person:target" }),
  ["aaaabbby"],
  "active Person facet must not be starved by 24 other-person candidates",
);
assert.deepEqual(
  component.getExploreSuggestions(mixedPeople, "aaaabbbx", { topicId: "topic:target" }),
  ["aaaabbby"],
  "approved Topic membership must not be starved by other public memberships",
);
assert.deepEqual(
  component.getExploreSuggestions(mixedPeople, "aaaabbbx", { assessment: "FACTUALLY_FALSE" }),
  ["aaaabbby"],
  "active assessment must not be starved by 24 differently classified findings",
);
for (const filters of [
  { personId: "person:unapproved" },
  { topicId: "topic:unapproved" },
  { kind: "topic", personId: "person:target" },
]) {
  assert.deepEqual(
    component.getExploreSuggestions(mixedPeople, "aaaabbbx", filters), [],
    "no matching public filter intersection must yield no suggestion",
  );
}

let state = ["", "ALL", "ALL", "relevance", "ALL", "ALL", true, index, "ready", false];
let nextStates = [];
let position = 0;
deps.react.useState = (initial) => {
  const slot = position++;
  if (state[slot] === undefined) state[slot] = initial;
  return [state[slot], (value) => { nextStates.push([slot, value]); }];
};
function render(query) {
  state[0] = query;
  position = 0;
  nextStates = [];
  return component.default({ expectedProjectionSha256: "a".repeat(64) });
}
function walk(node, predicate, found = []) {
  if (Array.isArray(node)) {
    node.forEach((item) => walk(item, predicate, found));
  } else if (node && typeof node === "object") {
    if (predicate(node)) found.push(node);
    walk(node.props?.children, predicate, found);
  }
  return found;
}
const view = render(raw);
const input = walk(view, (node) => node.type === "input" && node.props.id === "client-search")[0];
assert.equal(input?.props.value, raw, "typed input remains unchanged before opt-in");
const suggestionButton = walk(view, (node) =>
  node.type === "button" && String(node.props.children).includes("inflazione") &&
  node.props["data-search-suggestion"] === true
)[0];
assert(suggestionButton, "visible interactive suggestion should be offered on a no-match query");
assert.ok(walk(view, (node) => node.type === "button" && node.props["data-search-suggestion"] === true).length <= 4);
assert.equal(nextStates.length, 0, "rendering a suggestion must never auto-correct the query");
suggestionButton.props.onClick();
assert.deepEqual(nextStates, [[0, "  inflazione  "]], "only explicit suggestion click updates query");
const unchanged = render("Inflazione");
assert.equal(walk(unchanged, (node) => node.props?.["data-search-suggestion"] === true).length, 0);
assert.match(source, /non (?:è|sono) la data della dichiarazione/i,
  "the UI must not mislabel v2 publication as original statement chronology");
// Mobile refinement controls must expose selected public facets outside the
// modal, be keyboard-operable and remove exactly one URL filter at a time.
state=["", "SUPPORTED", "finding", "recent", "person:approved", "topic:approved", true, publicFacets, "ready", false];
const chipView=render("ricerca precisa");
const chips=walk(chipView,node=>node.type==="button" && node.props["data-active-filter"]);
assert.equal(chips.length,5,"each active filter must have a removable chip");
assert(chips.every(item=>item.props.type==="button" && /Rimuovi filtro:/.test(item.props["aria-label"])));
assert(chips.every(item=>item.props.style===undefined),"touch targets must come from responsive CSS, not inline overrides");
const personChip=chips.find(item=>item.props["data-active-filter"]==="personId");
assert(personChip,"approved Person filter chip missing");
assert.match(JSON.stringify(personChip),/Persona verificata/);
nextStates=[];
const savedWindow=globalThis.window;
const navigations=[];
globalThis.window={location:{pathname:"/esplora/"},history:{pushState(_a,_b,url){navigations.push(url);}}};
try{personChip.props.onClick();}finally{globalThis.window=savedWindow;}
assert.deepEqual(nextStates,[[4,"ALL"]],"only the Person facet state may change");
assert.equal(navigations.length,1);
const nextParams=new URL(navigations[0],"https://example.test").searchParams;
assert.equal(nextParams.get("persona"),null);
assert.equal(nextParams.get("tema"),"topic:approved");
assert.equal(nextParams.get("q"),"ricerca precisa");
const unavailable=render("ricerca precisa");
assert.doesNotMatch(JSON.stringify(unavailable),/PRIVATE_DO_NOT_LEAK/);
console.log("DP429_SUGGESTIONS_PASS public-only bounded fuzzy opt-in, filters, exact query URL, source-date honesty");
