/**
 * DP-436 rendered-card parity: the FIFTH public surface.
 *
 * `check-dp436-cross-consumer-verbatim-parity.mjs` compares the four machine
 * surfaces (search index, API v3, JSON-LD, N-Triples). The card a reader
 * actually sees — `VerbatimStatementRecord.astro` — was only ever checked
 * against the API payload it is built from, never against the released index,
 * linked data and N-Triples bytes of the same governed release. A card that
 * escapes, decodes, trims or re-encodes an approved span differently is a
 * verbatim divergence even when every machine surface agrees.
 *
 * This gate renders the real component in an isolated scratch site for ONE
 * governed release, extracts the quotation from the produced HTML, decodes it
 * and requires the exact approved bytes. Synthetic fixtures only: it grants no
 * right, approves no source and activates no route. Run it unchanged against a
 * real authorized release when #468/#98 produce one.
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { canonicalJson } from "../src/lib/searchIndex.ts";
import {
  buildPublicStatementSearchV3,
  validatePublicStatementSearchV3,
} from "../src/lib/publicStatementSearchV3.ts";
import {
  rowsFromApi,
  rowsFromIndex,
  rowsFromJsonLd,
  rowsFromNTriples,
} from "./lib/verbatim-parity.mjs";
import { makeScratchDir } from "./lib/scratch.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const web = fileURLToPath(new URL("../", import.meta.url));
const component = fileURLToPath(new URL("../src/components/VerbatimStatementRecord.astro", import.meta.url));

// HTML-sensitive characters and the whitespace bytes an approved span may
// legitimately carry: a card must show the approved bytes, not a normalized echo.
const TRICKY = `A & B < C > D "E" 'F'\tseconda riga\n  fine  `;

const python = String.raw`
import json, copy
from dataclasses import replace
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256
from dichiarazioni_pubbliche.public_person_v3 import build_public_people_v3
from test_dp438_public_person import identity
from test_dp435_public_statement_seam import SHA
from test_dp439_person_topic_v3 import published, make
from dichiarazioni_pubbliche.public_statement_readers_v3 import (
    get_public_statement_v3, list_public_statements_v3)
from dichiarazioni_pubbliche.public_api import PublicApiError
from dichiarazioni_pubbliche.linked_data import (
    projection_statement_v3_jsonld, projection_statement_v3_ntriples)

def surfaces(bundle):
    return {
        "dataset": bundle["dataset_sha256"],
        "api": list_public_statements_v3(
            bundle, allow_statement_v3=True,
            current_public_dataset_sha256=bundle["dataset_sha256"]),
        "jsonld": projection_statement_v3_jsonld(bundle, allow_statement_v3=True),
        "nt": projection_statement_v3_ntriples(bundle, allow_statement_v3=True),
    }

def public_people(public_bundle):
    return build_public_people_v3(
        roster, [identity(row) for row in roster], [], [],
        public_bundle=public_bundle,
        current_public_dataset_sha256=public_bundle["dataset_sha256"],
        allow_public_person_v3=True)

def rebuild(source, previous_bundle, previous_decisions, content_ids=None):
    bundle = source.build()
    bundle["topics"] = copy.deepcopy(previous_bundle["topics"])
    bundle["dataset_sha256"] = projection_dataset_sha256(bundle)
    people = public_people(bundle)
    decisions = tuple(
        replace(item, public_dataset_sha256=bundle["dataset_sha256"],
                **({"content_id": content_ids[item.statement_id]}
                   if content_ids and item.statement_id in content_ids else {}))
        for item in previous_decisions)
    return bundle, decisions, make(bundle, people, decisions)

def detail(bundle, statement_id):
    return get_public_statement_v3(
        bundle, statement_id, allow_statement_v3=True,
        current_public_dataset_sha256=bundle["dataset_sha256"])

source, bundle, people, roster, decisions = published()
bundle, decisions, full_join = rebuild(source, bundle, decisions)

full = {"join": full_join, **surfaces(bundle)}
full["details"] = {row["statement_id"]: detail(bundle, row["statement_id"])
                   for row in bundle["statements"]}

# The same release with one approved span carrying HTML metacharacters, a tab,
# a line break and edge spaces.
special_source, original_special_bundle, _, _, special_decisions = published()
owner = special_source.subjects[0]
quote = __TRICKY__
owner.source_text = "Contesto: " + quote + "Fine."
offset = owner.source_text.index(quote)
owner.row["original_text"] = quote
owner.row["source_sha256"] = SHA(owner.source_text)
owner.row["locator"] = {"start_char": offset, "end_char": offset + len(quote)}
for gate in owner.gates.values():
    gate["source_sha256"] = SHA(owner.source_text)
    gate["quote_sha256"] = SHA(quote)
    gate["span_start"], gate["span_end"] = offset, offset + len(quote)
special_bundle = special_source.build()
special_bundle["topics"] = copy.deepcopy(original_special_bundle["topics"])
special_bundle["dataset_sha256"] = projection_dataset_sha256(special_bundle)
special_decisions = tuple(
    replace(item, public_dataset_sha256=special_bundle["dataset_sha256"],
            **({"quote_sha256": SHA(quote), "source_sha256": SHA(owner.source_text)}
               if item.statement_id == "statement:1" else {}))
    for item in special_decisions)
special = {"join": make(special_bundle, public_people(special_bundle), special_decisions),
           "quote": quote, "statement_id": "statement:1", **surfaces(special_bundle)}
special["detail"] = detail(special_bundle, "statement:1")

# Withdrawal: revoking the rights of one Statement must remove it from every
# surface, including the card a reader can still request by route.
stale_detail = detail(bundle, "statement:2")
source.subjects[1].gates["rights"]["status"] = "REVOKED"
withdrawn_bundle, _, withdrawn_join = rebuild(source, bundle, decisions)
withdrawn = {"join": withdrawn_join, **surfaces(withdrawn_bundle), "stale_detail": stale_detail}
withdrawn["details"] = {statement_id: detail(withdrawn_bundle, statement_id)
                        for statement_id in ("statement:1", "statement:3")}
try:
    detail(withdrawn_bundle, "statement:2")
    withdrawn["detail_status"] = {"status": "LEAKED"}
except PublicApiError as exc:
    withdrawn["detail_status"] = {"status": exc.status, "code": exc.code}

print(json.dumps({"full": full, "special": special, "withdrawn": withdrawn},
                 ensure_ascii=False))
`.replace("__TRICKY__", JSON.stringify(TRICKY));

const buildRelease = () => {
  const result = spawnSync("python3", ["-c", python], {
    cwd: root,
    encoding: "utf8",
    timeout: 20000,
    env: { ...process.env, PYTHONPATH: "poc:tests", PYTHONDONTWRITEBYTECODE: "1" },
  });
  assert.equal(result.status, 0, "governed release build failed: " + result.stderr);
  return JSON.parse(result.stdout);
};

const pinsOf = (join) => ({
  intersectionSha256: join.dataset_sha256,
  statementSha256: join.source_dataset_sha256,
  personSha256: join.person_dataset_sha256,
});

const indexOf = async (state) => {
  const pins = pinsOf(state.join);
  const index = await buildPublicStatementSearchV3(state.join, pins);
  assert.deepEqual(
    await validatePublicStatementSearchV3(index, { ...pins, indexSha256: index.index_sha256 }),
    index,
  );
  assert.equal(index.source_status, "READY");
  return index;
};

const rowsOf = async (state) => {
  const index = await indexOf(state);
  return {
    index,
    rows: {
      index: rowsFromIndex(index),
      api: rowsFromApi(state.api),
      jsonld: rowsFromJsonLd(state.jsonld),
      ntriples: rowsFromNTriples(state.nt),
    },
  };
};

/** Decode exactly one level of HTML character references: Astro escapes the
 * approved bytes into text nodes, so a reader must get them back untouched. */
const decodeEntities = (value) => {
  const named = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: "\u00a0" };
  return value.replace(/&(?:#(\d+)|#[xX]([0-9a-fA-F]+)|([a-zA-Z]+));/g, (match, dec, hex, name) => {
    if (dec) return String.fromCodePoint(Number(dec));
    if (hex) return String.fromCodePoint(Number.parseInt(hex, 16));
    return Object.hasOwn(named, name) ? named[name] : match;
  });
};

/** The card surface: the approved quotation as the produced HTML carries it. */
const quotationOf = (html) => {
  const block = /<blockquote\b[^>]*>([\s\S]*?)<\/blockquote>/.exec(html);
  assert.ok(block, "rendered card has no verbatim blockquote");
  const paragraph = /<p>([\s\S]*?)<\/p>/.exec(block[1]);
  assert.ok(paragraph, "rendered card blockquote has no quotation paragraph");
  return { raw: paragraph[1], text: decodeEntities(paragraph[1]) };
};

const renderCards = async (state, statements, label) => {
  const temp = await makeScratchDir(`dp436-card-${label}-`);
  try {
    await mkdir(join(temp, "src/pages"), { recursive: true });
    await symlink(join(web, "node_modules"), join(temp, "node_modules"), "dir");
    await writeFile(join(temp, "astro.config.mjs"),
      'import { defineConfig } from "astro/config"; export default defineConfig({ output: "static" });\n');
    for (const statementId of statements) {
      const detail = state.details[statementId];
      // The record pin stands in for a separately verified approved-bundle
      // entry; production must never recompute it from the served payload.
      const digest = await crypto.subtle.digest(
        "SHA-256", new TextEncoder().encode(canonicalJson(detail.data)),
      );
      const recordPin = Buffer.from(digest).toString("hex");
      const slug = statementId.replace(/[^a-z0-9]+/gi, "-");
      await writeFile(join(temp, `${slug}.json`), JSON.stringify(detail));
      await writeFile(join(temp, "src/pages", `${slug}.astro`), [
        "---",
        `import VerbatimStatementRecord from ${JSON.stringify(component)};`,
        `import detail from "../../${slug}.json";`,
        "---",
        '<html lang="it"><body>',
        `<VerbatimStatementRecord apiDetail={detail} allowStatementV3={true} ` +
          `expectedDatasetSha256=${JSON.stringify(state.dataset)} ` +
          `expectedRecordSha256=${JSON.stringify(recordPin)} />`,
        "</body></html>",
      ].join("\n"));
    }
    const result = spawnSync(join(web, "node_modules/.bin/astro"), [
      "build", "--root", temp, "--outDir", join(temp, "out"),
    ], { cwd: web, encoding: "utf8", timeout: 120_000 });
    return { temp, result, html: async (statementId) =>
      readFile(join(temp, "out", statementId.replace(/[^a-z0-9]+/gi, "-"), "index.html"), "utf8") };
  } catch (error) {
    await rm(temp, { recursive: true, force: true });
    throw error;
  }
};

const release = buildRelease();

// 1. The full governed release: every card shows the bytes the four machine
//    surfaces serve, and no card trims or normalizes an approved span.
const full = await rowsOf(release.full);
const cards = await renderCards(release.full, Object.keys(release.full.details), "full");
try {
  assert.equal(cards.result.status, 0,
    `card rendering failed:\n${cards.result.stdout}\n${cards.result.stderr}`);
  for (const [surface, rows] of Object.entries(full.rows)) {
    for (const row of rows) {
      const html = await cards.html(row.statement_id);
      const card = quotationOf(html);
      assert.equal(card.text, row.original_text,
        `rendered card disagrees with ${surface} on ${row.statement_id}`);
      assert.ok(html.includes(`data-dataset-sha256="${release.full.dataset}"`),
        "card must carry the governed release fingerprint");
    }
  }
} finally {
  await rm(cards.temp, { recursive: true, force: true });
}

// 2. HTML metacharacters, a tab, a line break and edge spaces survive the card
//    exactly: escaping is transport, never an excuse to change the words.
const special = await rowsOf(release.special);
const specialRow = special.rows.api.find((row) => row.statement_id === release.special.statement_id);
assert.equal(specialRow.original_text, TRICKY, "fixture must keep the approved bytes");
const specialCards = await renderCards(
  { ...release.special, details: { [release.special.statement_id]: release.special.detail } },
  [release.special.statement_id], "special");
try {
  assert.equal(specialCards.result.status, 0,
    `special card rendering failed:\n${specialCards.result.stdout}\n${specialCards.result.stderr}`);
  const html = await specialCards.html(release.special.statement_id);
  const card = quotationOf(html);
  assert.equal(card.text, TRICKY, "card changed the approved bytes");
  assert.ok(!/&(?![a-zA-Z]+;|#\d+;)/.test(card.raw),
    "raw card markup must escape the source ampersand");
  assert.ok(!card.raw.includes("<"), "raw card markup must escape source angle brackets");
  for (const [surface, rows] of Object.entries(special.rows)) {
    assert.equal(rows.find((row) => row.statement_id === release.special.statement_id).original_text,
      card.text, `card disagrees with ${surface} on the approved bytes`);
  }
} finally {
  await rm(specialCards.temp, { recursive: true, force: true });
}

// 3. Withdrawal: the withdrawn Statement is gone from the four machine surfaces
//    and cannot be rendered as a card under the current release pins, while the
//    cards of the remaining records keep agreeing with every surface.
const withdrawn = await rowsOf(release.withdrawn);
assert.equal(withdrawn.rows.api.some((row) => row.statement_id === "statement:2"), false);
assert.deepEqual(release.withdrawn.detail_status, { status: 404, code: "RESOURCE_NOT_FOUND" },
  "a withdrawn Statement must not be readable through the pinned detail reader");
const staleCards = await renderCards(
  { ...release.withdrawn, details: { "statement:2": release.withdrawn.stale_detail } },
  ["statement:2"], "withdrawn");
try {
  assert.notEqual(staleCards.result.status, 0,
    "the withdrawn Statement still renders as a current card under the new release pins");
  const output = staleCards.result.stdout + staleCards.result.stderr;
  assert.match(output, /FINGERPRINT|PUBLIC_STATEMENT/,
    "the withdrawn card must fail closed on the governed release pins");
} finally {
  await rm(staleCards.temp, { recursive: true, force: true });
}
const surviving = await renderCards(release.withdrawn,
  Object.keys(release.withdrawn.details), "surviving");
try {
  assert.equal(surviving.result.status, 0, `surviving card rendering failed:\n${surviving.result.stderr}`);
  for (const [surface, rows] of Object.entries(withdrawn.rows)) {
    for (const row of rows) {
      const card = quotationOf(await surviving.html(row.statement_id));
      assert.equal(card.text, row.original_text,
        `after withdrawal the card disagrees with ${surface} on ${row.statement_id}`);
    }
  }
} finally {
  await rm(surviving.temp, { recursive: true, force: true });
}

console.log(
  "DP-436 rendered-card parity PASS " +
  `(card = 5th surface, ${Object.keys(release.full.details).length} statements, ` +
  `exact bytes including metacharacters/whitespace, withdrawal refuses the stale card, ` +
  `fingerprint ${full.index.source_dataset_sha256.slice(0, 12)})`,
);
