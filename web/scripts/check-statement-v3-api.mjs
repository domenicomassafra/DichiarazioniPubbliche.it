import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { validatePublicStatementV3Detail } from "../src/lib/statementV3Api.ts";
import { canonicalJson } from "../src/lib/searchIndex.ts";
import { makeScratchDir } from "./lib/scratch.mjs";

// Backend-owned synthetic fixture, never a real-source publication or a web route.
const root = fileURLToPath(new URL("../../", import.meta.url));
const source = [
  "import json,sys",
  "sys.path.insert(0,'poc');sys.path.insert(0,'tests')",
  "from test_dp436_public_statement_consumers import with_derived,v2_bundle",
  "from dichiarazioni_pubbliche.public_api import get_public_statement_v3",
  "bundle=with_derived()",
  "print(json.dumps({'detail':get_public_statement_v3(bundle,'statement:1',allow_statement_v3=True),'v2':v2_bundle()},ensure_ascii=False))",
].join(";");
const run = spawnSync("python3", ["-c", source], {
  cwd: root, encoding: "utf8", env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
});
assert.equal(run.status, 0, `synthetic API detail fixture failed: ${run.stderr}`);
const { detail, v2 } = JSON.parse(run.stdout);
// The record pin represents a separately verified approved-bundle entry.
// It must NEVER be recalculated from a candidate API payload in production.
const recordDigest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalJson(detail.data)));
const approvedRecordSha256 = Buffer.from(recordDigest).toString("hex");
const allowed = {
  allowStatementV3: true,
  expectedDatasetSha256: detail.meta.dataset_sha256,
  expectedRecordSha256: approvedRecordSha256,
};
const read = (payload, options = allowed) => validatePublicStatementV3Detail(payload, options);
const corrupt = (change) => {
  const value = structuredClone(detail);
  change(value);
  return value;
};

await assert.rejects(read(detail, { ...allowed, allowStatementV3: false }), /OPT_IN/);
await assert.rejects(read(detail, { allowStatementV3: true }), /FINGERPRINT/);
await assert.rejects(read(detail, { allowStatementV3: true, expectedDatasetSha256: detail.meta.dataset_sha256 }), /FINGERPRINT/);
await assert.rejects(read(detail, { ...allowed, expectedDatasetSha256: "f".repeat(64) }), /FINGERPRINT/);
await assert.rejects(read({ meta: { public_schema_version: v2.schema_version }, data: detail.data }), /FIELDS|FINGERPRINT|SCHEMA/);
assert.deepEqual((await read(detail)).data, detail.data, "a governed v3 API detail must survive unmodified");
// A successfully validated result must not alias caller-owned input. After a
// later rights withdrawal/replacement, the old verified fingerprint must not
// authorize newly swapped private text or source URLs.
const mutableDetail = structuredClone(detail);
const checkedSnapshot = await read(mutableDetail);
const expectedOriginal = checkedSnapshot.data.original.text;
const expectedUrl = checkedSnapshot.data.source.url;
mutableDetail.data.original.text = "PRIVATE NOT APPROVED POST VALIDATION";
mutableDetail.data.source.url = "https://example.test/forged-private-source";
mutableDetail.meta.dataset_sha256 = "f".repeat(64);
assert.equal(checkedSnapshot.data.original.text, expectedOriginal,
  "validated source wording aliases an untrusted mutable caller");
assert.equal(checkedSnapshot.data.source.url, expectedUrl,
  "validated source URL aliases an untrusted mutable caller");
assert.equal(checkedSnapshot.meta.dataset_sha256, detail.meta.dataset_sha256,
  "validated dataset fingerprint aliases an untrusted mutable caller");
// An adversarial caller can also race the last asynchronous digest, after
// validation has computed the approved hash but before its Promise resumes.
const racing = structuredClone(detail);
const subtle = globalThis.crypto.subtle;
const originalDigestFunction = subtle.digest;
let digestCount = 0;
try {
  subtle.digest = async function (algorithm, input) {
    const bytes = await originalDigestFunction.call(this, algorithm, input);
    if (++digestCount === 2) {
      racing.data.original.text = "PRIVATE CONCURRENT UNREVIEWED QUOTE";
      racing.data.source.url = "https://example.test/unapproved-race";
      racing.data.summary.text = "PRIVATE CONCURRENT UNREVIEWED SUMMARY";
    }
    return bytes;
  };
  const racingResult = await read(racing);
  assert.equal(digestCount, 2, "test failed to interleave at the second digest");
  assert.equal(racingResult.data.original.text, detail.data.original.text,
    "caller race substituted the approved quotation after hash validation");
  assert.equal(racingResult.data.source.url, detail.data.source.url,
    "caller race substituted the source locator after hash validation");
  assert.equal(racingResult.data.summary?.text, detail.data.summary?.text,
    "caller race substituted the separately reviewed summary");
} finally {
  subtle.digest = originalDigestFunction;
}
assert.equal(detail.data.original.wording_type, "VERBATIM_ORIGINAL");
assert.equal(detail.data.finding_id, null, "an opinion need not manufacture a factual Finding");
assert.equal(detail.data.translation?.wording_type, "TRANSLATION");
assert.equal(detail.data.summary?.wording_type, "SUMMARY");

for (const [reason, modify] of [
  ["paraphrase promoted into source wording", (v) => { v.data.original.wording_type = "PARAPHRASE"; }],
  ["modified quote without matching hash", (v) => { v.data.original.text = "La cifra è alterata."; }],
  ["invalid source URL", (v) => { v.data.source.url = "http://example.test"; }],
  ["invented review status in public record", (v) => { v.data.private_review = "approved"; }],
  ["raw operational source exposure", (v) => { v.data.source.raw_transcript = "private"; }],
  ["extra operational metadata", (v) => { v.meta.candidate_count = 999; }],
  ["falsified source version", (v) => { v.data.source.version_id = ""; }],
  ["crossed summary source hash", (v) => { v.data.summary.source_quote_sha256 = "a".repeat(64); }],
  ["translation pretending to be source language", (v) => { v.data.translation.language = v.data.original.language; }],
  ["translation in source text position", (v) => { v.data.original.text = v.data.translation.text; }],
  ["swapped original span", (v) => { v.data.original.locator.end_char += 1; }],
  ["source kind spoofed", (v) => { v.data.source.kind = "TIMED"; }],
  ["source URL silently re-bound under an unchanged dataset fingerprint", (v) => { v.data.source.url = "https://another-source.example/document"; }],
  ["source hash silently re-bound under an unchanged dataset fingerprint", (v) => { v.data.source.sha256 = "d".repeat(64); }],
  ["falsified endorsed reported quote", (v) => { v.data.speech_act = "REPORTED_QUOTE"; v.data.endorsed = true; }],
  ["unexpected API version", (v) => { v.meta.public_schema_version = "dichiarazioni-pubbliche-public-v2"; }],
  ["index-style record as detail", (v) => { v.data = { title: "claim", statement_id: "statement:1" }; }],
  ["schema smuggling at wrapper", (v) => { v.private = "secret"; }],
]) {
  await assert.rejects(read(corrupt(modify)), undefined, reason);
}

console.log("DP-436 frontend opt-in API exact-quote consumer PASS (synthetic backend data only)");

// Render the real Astro component in a disposable, isolated site. A synthetic
// fixture under /tmp is never copied to web/src/pages, dist or the MiniPC.
const temp = await makeScratchDir("dp436-astro-opt-in-");
const web = fileURLToPath(new URL("../", import.meta.url));
const component = fileURLToPath(new URL("../src/components/VerbatimStatementRecord.astro", import.meta.url));
async function fixtureBuild(apiDetail, enabled, output) {
  const fixture = join(temp, "detail.json");
  await writeFile(fixture, JSON.stringify(apiDetail));
  const page = [
    "---",
    `import VerbatimStatementRecord from ${JSON.stringify(component)};`,
    'import detail from "../../detail.json";',
    "---",
    "<html lang=\"it\"><body>",
    `<VerbatimStatementRecord apiDetail={detail} allowStatementV3={${enabled}} expectedDatasetSha256=${JSON.stringify(detail.meta.dataset_sha256)} expectedRecordSha256=${JSON.stringify(approvedRecordSha256)} />`,
    "</body></html>",
  ].join("\n");
  await writeFile(join(temp, "src/pages/index.astro"), page);
  return spawnSync(join(web, "node_modules/.bin/astro"), [
    "build", "--root", temp, "--outDir", join(temp, output),
  ], { cwd: web, encoding: "utf8", timeout: 120_000 });
}

try {
  await mkdir(join(temp, "src/pages"), { recursive: true });
  await symlink(join(web, "node_modules"), join(temp, "node_modules"), "dir");
  await writeFile(join(temp, "astro.config.mjs"),
    'import { defineConfig } from "astro/config"; export default defineConfig({ output: "static" });\n');
  const approvedRender = await fixtureBuild(detail, true, "approved");
  assert.equal(approvedRender.status, 0, `v3 Astro rendering failed:\n${approvedRender.stdout}\n${approvedRender.stderr}`);
  const html = await readFile(join(temp, "approved/index.html"), "utf8");
  const quote = detail.data.original.text;
  assert.ok(html.includes(`<p>${quote}</p>`), "SSR did not display the exact approved original quote");
  assert.match(html, /data-contract="public-statement-v3-opt-in"/);
  assert.ok(html.includes(`data-dataset-sha256="${detail.meta.dataset_sha256}"`));
  assert.match(html, /<blockquote\b[^>]*lang="it"[^>]*cite="https:/);
  assert.match(html, /Traduzione \(en\)/);
  assert.match(html, /Riassunto/);
  assert.doesNotMatch(html, /private_review|raw_transcript|candidate_count/);

  const refused = await fixtureBuild(detail, false, "refused");
  assert.notEqual(refused.status, 0, "Astro component unexpectedly rendered an unopted v3 payload");
  const falsified = corrupt((value) => { value.data.original.wording_type = "PARAPHRASE"; });
  const spoofed = await fixtureBuild(falsified, true, "spoofed");
  assert.notEqual(spoofed.status, 0, "Astro component rendered a paraphrase as a source quote");

  // The legacy, directly supplied governed source-record mode must not become
  // a way around the explicit v3 opt-in and independently pinned source record.
  const original = detail.data;
  const directStatement = {
    statement_id: original.statement_id,
    version_id: original.version_id,
    person_id: original.person.id,
    speaker_name: original.person.name,
    content_id: original.source.content_id,
    source_title: original.source.title,
    source_url: original.source.url,
    source_version: original.source.version_id,
    source_sha256: original.source.sha256,
    original_text: original.original.text,
    quote_sha256: original.original.quote_sha256,
    language: original.original.language,
    statement_date: original.statement_date,
    source_kind: original.source.kind,
    locator: original.original.locator,
    speech_act: original.speech_act,
    endorsed: original.endorsed,
    review_provenance: {
      rights: "review:rights:fixture", attribution: "review:attribution:fixture",
      context: "review:context:fixture", wording: "review:wording:fixture",
      publication: "review:publication:fixture",
    },
    finding_id: original.finding_id,
    summary: original.summary === null ? null : {
      ...original.summary, review_event_id: "review:summary:fixture",
    },
    translation: original.translation === null ? null : {
      ...original.translation, review_event_id: "review:translation:fixture",
    },
  };
  const directDigest = await crypto.subtle.digest(
    "SHA-256", new TextEncoder().encode(canonicalJson(directStatement)),
  );
  const directRecordPin = Buffer.from(directDigest).toString("hex");
  async function directBuild(enabled, recordPin, output) {
    await writeFile(join(temp, "direct.json"), JSON.stringify(directStatement));
    const componentPage = [
      "---",
      `import VerbatimStatementRecord from ${JSON.stringify(component)};`,
      'import direct from "../../direct.json";',
      "---",
      "<html lang=\"it\"><body>",
      `<VerbatimStatementRecord statement={direct} allowStatementV3={${enabled}} expectedDatasetSha256=${JSON.stringify(detail.meta.dataset_sha256)} expectedRecordSha256=${JSON.stringify(recordPin)} />`,
      "</body></html>",
    ].join("\n");
    await writeFile(join(temp, "src/pages/index.astro"), componentPage);
    return spawnSync(join(web, "node_modules/.bin/astro"), [
      "build", "--root", temp, "--outDir", join(temp, output),
    ], { cwd: web, encoding: "utf8", timeout: 120_000 });
  }
  const unoptedDirect = await directBuild(false, directRecordPin, "direct-unopted");
  assert.notEqual(unoptedDirect.status, 0, "direct source record bypassed explicit v3 opt-in");
  const unpinnedDirect = await directBuild(true, "f".repeat(64), "direct-unpinned");
  assert.notEqual(unpinnedDirect.status, 0, "direct source record bypassed the external record pin");
  const governedDirect = await directBuild(true, directRecordPin, "direct-governed");
  assert.equal(governedDirect.status, 0, `direct pinned source render failed: ${governedDirect.stderr}`);
  const directHtml = await readFile(join(temp, "direct-governed/index.html"), "utf8");
  assert.match(directHtml, /Parole originali dalla fonte/);
  assert.match(directHtml, /data-dataset-sha256="[a-f0-9]{64}"/);
  console.log("DP-436 isolated Astro original/translation/summary SSR and fail-closed opt-in PASS");
} finally {
  await rm(temp, { recursive: true, force: true });
}
