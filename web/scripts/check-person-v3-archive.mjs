import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { readApprovedPersonV3 } from "../src/lib/publicPersonV3.ts";

// Import real backend's opt-in v3 Person projection fixture; never a real
// approved source. This test's pin is recorded BEFORE adversarial mutation.
const root = fileURLToPath(new URL("../../", import.meta.url));
const backend = [
  "import json,sys",
  "sys.path.insert(0,'poc');sys.path.insert(0,'tests')",
  "from test_dp438_public_person import project,statement",
  "print(json.dumps({'published':project(statements=[statement()]),'empty':project()},ensure_ascii=False))",
].join(";");
const run = spawnSync("python3", ["-c", backend], {cwd: root, encoding: "utf8"});
assert.equal(run.status, 0, `synthetic approved Person projection unavailable: ${run.stderr}`);
const {published, empty} = JSON.parse(run.stdout);
const opts = {allowPersonV3: true, identifier: "persona-uno", expectedCollectionSha256: published.dataset_sha256};
const read = (data, options = opts) => readApprovedPersonV3(data, options);
const mutate = (fn) => { const copy = structuredClone(published); fn(copy); return copy; };

const person = await read(published);
assert.equal(person.statements.length, 1);
assert.equal(person.statements[0].statement_route, "/dichiarazioni/statement-one/");
assert.equal(person.statements[0].finding_id, null);
assert.equal((await read(empty, {...opts, expectedCollectionSha256: empty.dataset_sha256})).statements.length, 0);
assert.equal(await read(published, {...opts, identifier: "person:missing"}), null);
await assert.rejects(read(published, {...opts, allowPersonV3: false}), /OPT_IN/);
await assert.rejects(read(published, {...opts, expectedCollectionSha256: empty.dataset_sha256}), /STALE/);
await assert.rejects(read(published, {allowPersonV3:true,identifier:"persona-uno"}), /PIN/);
for (const [label, corrupt] of [
  ["independent record SHA change", (v) => {v.people[0].statements[0].source_sha256 = "f".repeat(64);}],
  ["quote re-bound with matching quote digest absent", (v) => {v.people[0].statements[0].original_text = "Testo diverso";}],
  ["private review fields", (v) => {v.people[0].statements[0].review_provenance = {rights:"private"};}],
  ["internal person candidate", (v) => {v.people[0].status = "HELD";}],
  ["cross-origin statement route", (v) => {v.people[0].statements[0].statement_route = "//bad.example/";}],
  ["invented finding assessment", (v) => {v.people[0].statements[0].assessment = "SUPPORTED";}],
  ["withdrawn row replay", (v) => {v.people = [];}],
]) await assert.rejects(read(mutate(corrupt)), undefined, label);

// Recompute a self-asserted bundle SHA; the independently supplied approved
// pin still refuses the unapproved new collection.
const lifted = mutate((v) => {v.people[0].statements[0].source_version = "source:forged";});
const { canonicalJson } = await import("../src/lib/searchIndex.ts");
const digest = async (value) => Buffer.from(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value))).toString("hex");
lifted.dataset_sha256 = await digest(canonicalJson(lifted.people));
await assert.rejects(read(lifted), /STALE/);
console.log("DP-405 opt-in v3 Person backend→TypeScript archive, negative authorization and withdrawal PASS");

const web = fileURLToPath(new URL("../", import.meta.url));
const component = fileURLToPath(new URL("../src/components/PublicPersonArchiveV3.astro", import.meta.url));
// Astro moves prerendered assets from web/.astro into this output via rename.
// Keep both on the same filesystem: /tmp may be a separate tmpfs on MiniPC.
// The scratch directory is deleted by the finally block below.
const temp = await mkdtemp(join(web, ".dp405-person-v3-"));
async function render(collection, identifier, pin, enabled, output) {
  await writeFile(join(temp, "public-person.json"), JSON.stringify(collection));
  const page = [
    "---",
    `import Person from ${JSON.stringify(component)};`,
    'import collection from "../../public-person.json";',
    "---",
    `<Person collection={collection} identifier=${JSON.stringify(identifier)} expectedCollectionSha256=${JSON.stringify(pin)} allowPersonV3={${enabled}} />`,
  ].join("\n");
  await writeFile(join(temp, "src/pages/index.astro"), page);
  return spawnSync(join(web, "node_modules/.bin/astro"), ["build", "--root", temp, "--outDir", join(temp, output)], {
    cwd: web, encoding: "utf8", timeout: 120000, env: {...process.env, DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION:"1"},
  });
}
try {
  await mkdir(join(temp, "src/pages"), {recursive:true});
  await symlink(join(web, "node_modules"), join(temp, "node_modules"), "dir");
  await writeFile(join(temp, "astro.config.mjs"), 'import {defineConfig} from "astro/config";export default defineConfig({output:"static"})');
  const success = await render(published, "persona-uno", published.dataset_sha256, true, "published");
  assert.equal(success.status, 0, `SSR failed: ${success.stdout}\n${success.stderr}`);
  const html = await readFile(join(temp, "published/index.html"), "utf8");
  assert.match(html, /Una frase dimostrativa\./);
  assert.match(html, /href="\/dichiarazioni\/statement-one\/"/);
  assert.match(html, /data-person-v3-source/);
  assert.match(html, /non ha un Finding fattuale pubblicato/);
  assert.doesNotMatch(html, /review_provenance|privacy_policy_ref|source_body|person_score/);
  const emptyRender = await render(empty, "persona-uno", empty.dataset_sha256, true, "empty");
  assert.equal(emptyRender.status, 0, `zero history SSR failed: ${emptyRender.stderr}`);
  const emptyHtml = await readFile(join(temp, "empty/index.html"), "utf8");
  assert.match(emptyHtml, /Nessuna dichiarazione pubblicata per questa persona/);
  assert.doesNotMatch(emptyHtml, /Una frase dimostrativa\./);
  const unopted = await render(published, "persona-uno", published.dataset_sha256, false, "not-authorized");
  assert.notEqual(unopted.status, 0, "Unopted archive must not render");
  const revoked = await render(published, "persona-uno", empty.dataset_sha256, true, "withdrawn");
  assert.notEqual(revoked.status, 0, "Withdrawn collection must not render");
  console.log("DP-405 Astro Person v3 populated+zero-history SSR and stale/unopted rejection PASS");
} finally { await rm(temp, {recursive:true, force:true}); }
