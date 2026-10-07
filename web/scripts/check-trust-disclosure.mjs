import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const dist = path.resolve("dist");
const statements = path.join(dist, "dichiarazioni");
const searchIndex = JSON.parse(fs.readFileSync(path.join(dist, "search-index.v1.json"), "utf8"));
assert.ok(Array.isArray(searchIndex.records), "search index records must be an array");
const findingRecords = searchIndex.records.filter((record) => record.kind === "finding");
const statementFiles = fs.existsSync(statements)
  ? fs.readdirSync(statements)
    .map((slug) => path.join(statements, slug, "index.html"))
    .filter((file) => fs.existsSync(file))
  : [];
assert.equal(statementFiles.length, findingRecords.length, "rendered Statement count must match the public search index");

for (const file of statementFiles) {
  const html = fs.readFileSync(file, "utf8");
  assert.equal(/<h1[^>]*>\s*[“\"]/.test(html), false, `${file}: normalized claim rendered as direct quote`);
  assert.match(html, /Formulazione normalizzata/i, `${file}: wording label missing`);
  assert.match(html, /non è una citazione verbatim/i, `${file}: explicit non-verbatim disclosure missing`);
  assert.match(html, /PARAPHRASE/i, `${file}: public wording label missing`);
  assert.equal(/AI verified|confidence score|ratingValue/i.test(html), false, `${file}: prohibited trust badge/score language`);
}

const method = fs.readFileSync(path.join(dist, "metodo", "index.html"), "utf8");
for (const phrase of [
  "Originale, parafrasi, traduzione e discorso riportato",
  "Attribuzione senza biometria",
  "non prova che sia vera",
  "non una percentuale",
]) {
  assert.ok(method.includes(phrase), `method disclosure missing: ${phrase}`);
}
assert.equal(/AI verified|ratingValue/i.test(method), false, "method contains prohibited trust shortcut");

console.log(`trust-disclosure checks PASS (${statementFiles.length} statement pages + method${statementFiles.length === 0 ? "; approved empty snapshot" : ""})`);
