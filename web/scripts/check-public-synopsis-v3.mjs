import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { readPinnedPublicSynopsisV3 } from "../src/lib/publicSynopsisV3.ts";
import { makeScratchDir } from "./lib/scratch.mjs";
import { canonicalJson } from "../src/lib/searchIndex.ts";

// Read the ACTUAL Python DP-440 synthetic fixture and its withheld decisions.
// No real source rights, editorial attestation or deployed public release.
const root = fileURLToPath(new URL("../../", import.meta.url));
const script = [
  "import json,sys,dataclasses",
  "sys.path.insert(0,'poc');sys.path.insert(0,'tests')",
  "from test_dp440_public_synopsis import bundle,prepare,intersection,sentence",
  "from dataclasses import replace",
  "b=bundle()",
  "print(json.dumps({'bundle':b,'ready':dataclasses.asdict(prepare(b)),'revoked':dataclasses.asdict(prepare(b,proof=intersection(b,status='REVOKED'))),'wrong_quote':dataclasses.asdict(prepare(b,sentences=(sentence(b,source_quote_sha256=('f'*64)),)))},ensure_ascii=False))",
].join(";");
const python = spawnSync("python3", ["-c", script], { cwd: root, encoding: "utf8", timeout: 15000 });
assert.equal(python.status, 0, `DP-440 Python source fixture failed: ${python.stderr}`);
const fixture = JSON.parse(python.stdout);
const { bundle, ready, revoked, wrong_quote } = fixture;
assert.equal(ready.status, "READY_READ_MODEL");
assert.equal(revoked.status, "WITHHELD");
assert.equal(wrong_quote.status, "WITHHELD");

const sha = (value) => createHash("sha256").update(value).digest("hex");
const at = new Date("2026-10-11T16:00:01Z"); // historical synthetic fixture clock
const pin = {
  allowSynopsisV3: true,
  synopsisSha256: sha(canonicalJson(ready)),
  synopsisFingerprint: ready.fingerprint,
  publicDatasetSha256: bundle.dataset_sha256,
  publicGeneratedAt: bundle.generated_at,
  personId: ready.person_id,
  topicId: ready.topic_id,
  validUntil: "2026-10-12T13:00:00Z", // synthetic attestation expiry
};
const read = (synopsis = ready, publicBundle = bundle, pins = pin) =>
  readPinnedPublicSynopsisV3(synopsis, publicBundle, pins, at);
const copy = structuredClone;
const failed = async (label, changeSynopsis, changeBundle, changePin, pattern) => {
  const s = copy(ready);
  const b = copy(bundle);
  const p = copy(pin);
  changeSynopsis?.(s);
  changeBundle?.(b);
  changePin?.(p);
  await assert.rejects(read(s, b, p), pattern, label);
};

const validated = await read();
assert.equal(validated.status, "PINNED_PREVIEW_ONLY");
assert.equal(validated.publicationAuthorized, false);
assert.equal(validated.providerCalls, 0);
assert.equal(validated.sentences.length, 2);
assert.equal(validated.coverageNote, ready.coverage_note);
assert.equal(validated.snapshotAt, ready.snapshot_at);
for (let i = 0; i < 2; i++) {
  const expected = ready.sentences[i].citations[0];
  const citation = validated.sentences[i].citations[0];
  assert.equal(citation.statementId, expected.statement_id);
  assert.equal(citation.versionId, expected.version_id);
  assert.equal(citation.quoteSha256, expected.quote_sha256);
  assert.equal(citation.sourceSha256, expected.source_sha256);
  assert.equal(citation.statementDate, expected.statement_date);
  assert.deepEqual(citation.locator, expected.locator);
  assert.equal(citation.statementRoute, `/dichiarazioni/statement-${i + 1}/`);
  assert.equal(citation.sourceUrl, expected.source_url);
  assert.ok(citation.language);
  assert.ok(!("original_text" in citation));
}
assert.ok(!JSON.stringify(validated).includes("review_provenance"));
assert.ok(!JSON.stringify(validated).includes("original_text"));
assert.ok(!JSON.stringify(validated).includes("review:topic:1"));
assert.deepEqual(validated, await read(), "pure SSR/browser read is deterministic");

await failed("missing opt-in", null, null, p => { p.allowSynopsisV3 = false; }, /OPT_IN/);
await failed("untrusted synopsis pin", null, null, p => { delete p.synopsisSha256; }, /PIN/);
await failed("self-hashed forged fingerprint", s => { s.fingerprint = "f".repeat(64); }, null,
  p => { p.synopsisSha256 = sha(canonicalJson({ ...ready, fingerprint: "f".repeat(64) })); }, /PIN/);
await failed("wrong topic", null, null, p => { p.topicId = "topic:foreign"; }, /SCOPE/);
await failed("wrong Person", null, null, p => { p.personId = "person:foreign"; }, /SCOPE/);
await failed("expired attestation", null, null, p => { p.validUntil = "2026-10-11T16:00:00Z"; }, /EXPIRED/);
await failed("missing version", null, b => { b.statements[0].version_id = "statement-version:withdrawn"; }, null, /STALE|SOURCE|CITATION/);
await failed("rights review revoked", null, b => { b.statements[0].review_provenance.rights = ""; }, null, /STALE|SOURCE|RIGHTS/);
await failed("changed source date", null, b => { b.statements[0].statement_date = "2026-10-01"; }, null, /STALE|SOURCE|CITATION/);
await failed("changed un-hashed source timestamp", null, b => { b.generated_at = "2026-10-01T12:00:00Z"; }, null, /STALE|SOURCE/);
await failed("changed locator", null, b => { b.statements[0].locator.start_char += 1; }, null, /STALE|SOURCE|CITATION/);
await failed("changed public quote", null, b => { b.statements[0].original_text += " modifica"; }, null, /STALE|SOURCE|CITATION/);
await failed("changed source hash", null, b => { b.statements[0].source_sha256 = "0".repeat(64); }, null, /STALE|SOURCE|CITATION/);
await failed("wrong source route URL", s => { s.sentences[0].citations[0].source_url = "https://evil.invalid/"; }, null, null, /PIN/);
await failed("unsafe source URL", null, b => { b.statements[0].source_url = "javascript:alert(1)"; }, null, /STALE|SOURCE/);
await failed("materialized private body", s => { s.private_body = "secret"; }, null,
  p => { p.synopsisSha256 = sha(canonicalJson({ ...ready, private_body: "secret" })); }, /SCHEMA/);
await assert.rejects(read(revoked), /WITHHELD/);
await assert.rejects(read(wrong_quote), /WITHHELD/);
await assert.rejects(read(ready, { ...bundle, schema_version: "dichiarazioni-pubbliche-public-v2" }), /SOURCE/);

// A withdrawn source with a NEW self-consistent dataset SHA still cannot be
// displayed with the old independently issued pin from the current release.
const withdrawn = copy(bundle);
withdrawn.statements = withdrawn.statements.slice(1);
const payload = { dossiers: withdrawn.dossiers, topics: withdrawn.topics,
  contents: withdrawn.contents, statements: withdrawn.statements };
withdrawn.dataset_sha256 = sha(canonicalJson(payload));
await assert.rejects(read(ready, withdrawn), /STALE|SOURCE/);

// Never retain an alias of mutable input locators across SSR/browser reads.
const snapshot = await read();
const original = copy(snapshot.sentences[0].citations[0].locator);
const untouched = copy(ready);
bundle.statements[0].locator.start_char += 10;
ready.sentences[0].citations[0].locator.start_char += 10;
assert.deepEqual(snapshot.sentences[0].citations[0].locator, original);

// Also prove an actual isolated Astro SSR build consumes the checked DTO.
// It never creates or enables a production project route.
const web = fileURLToPath(new URL("../", import.meta.url));
const consumer = fileURLToPath(new URL("../src/lib/publicSynopsisV3.ts", import.meta.url));
const scratch = await makeScratchDir("dp440-synopsis-ssr-");
async function buildSsr(previewPins, output) {
  const page = [
    "---",
    `import { readPinnedPublicSynopsisV3 } from ${JSON.stringify(consumer)};`,
    'import synopsis from "../../synopsis.json";',
    'import source from "../../source.json";',
    `const pins = ${JSON.stringify(previewPins)};`,
    `const view = await readPinnedPublicSynopsisV3(synopsis, source, pins, new Date("2026-10-11T16:00:01Z"));`,
    "---",
    '<section data-public-synopsis-preview aria-label="Sintesi citata">',
    '  <p data-coverage>{view.coverageNote}</p>',
    '  {view.sentences.map(sentence => <article><p>{sentence.text}</p>{sentence.citations.map(citation => (',
    '    <a href={citation.statementRoute} data-version={citation.versionId} data-quote-sha={citation.quoteSha256} data-source-sha={citation.sourceSha256} data-date={citation.statementDate} data-start={citation.locator.start_char}>{citation.statementDate}</a>',
    '  ))}</article>)}',
    '</section>',
  ].join("\n");
  await writeFile(join(scratch, "src/pages/index.astro"), page);
  return spawnSync(join(web, "node_modules/.bin/astro"),
    ["build", "--root", scratch, "--outDir", join(scratch, output)],
    { cwd: web, encoding: "utf8", timeout: 120000 });
}
try {
  await mkdir(join(scratch, "src/pages"), { recursive: true });
  await symlink(join(web, "node_modules"), join(scratch, "node_modules"), "dir");
  await writeFile(join(scratch, "astro.config.mjs"),
    'import {defineConfig} from "astro/config";export default defineConfig({output:"static"})');
  await writeFile(join(scratch, "synopsis.json"), JSON.stringify(untouched));
  const unchangedSource = JSON.parse(python.stdout).bundle;
  await writeFile(join(scratch, "source.json"), JSON.stringify(unchangedSource));
  const positive = await buildSsr(pin, "positive");
  assert.equal(positive.status, 0, `DP-440 isolated SSR failed: ${positive.stdout}\n${positive.stderr}`);
  const html = await readFile(join(scratch, "positive/index.html"), "utf8");
  assert.match(html, /data-public-synopsis-preview/);
  assert.match(html, /copertura non esaustiva/);
  assert.match(html, /href="\/dichiarazioni\/statement-1\/"/);
  assert.match(html, /data-version="statement-version:1"/);
  assert.match(html, /data-source-sha="[0-9a-f]{64}"/);
  assert.match(html, /data-date="2026-10-09"/);
  assert.doesNotMatch(html, /original_text|review_provenance|private_body|review:summary|person_truth_score/);
  const expired = await buildSsr({ ...pin, validUntil: "2026-10-11T16:00:00Z" }, "expired");
  assert.notEqual(expired.status, 0, "Expired synopsis must not reach test SSR HTML");
  console.log("DP-440 Python fixture → pinned TypeScript + isolated Astro SSR, citation/source/rights/expiry/withdrawal negatives PASS");
} finally {
  await rm(scratch, { recursive: true, force: true });
}
