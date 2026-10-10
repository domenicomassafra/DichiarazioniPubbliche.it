import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { validateOriginalStatement } from "../src/lib/statementV3.ts";

const sha = (value) => createHash("sha256").update(value).digest("hex");
// Deliberately synthetic text. No right to publish any real source is implied.
const original = "Questo è soltanto un esempio sintetico.";
const quoteHash = sha(original);
const base = {
  statement_id: "statement:synthetic",
  version_id: "statement-version:1",
  person_id: "person:synthetic",
  speaker_name: "Persona di prova",
  content_id: "content:synthetic",
  source_title: "Fonte sintetica di prova",
  source_url: "https://example.test/synthetic",
  source_version: "source-version:1",
  source_sha256: sha("prima " + original + " dopo"),
  original_text: original,
  quote_sha256: quoteHash,
  language: "it",
  statement_date: "2026-10-10",
  source_kind: "WRITTEN",
  locator: { start_char: 6, end_char: 6 + [...original].length },
  speech_act: "OPINION",
  endorsed: true,
  review_provenance: {
    rights: "review:rights",
    attribution: "review:attribution",
    context: "review:context",
    wording: "review:wording",
    publication: "review:publication",
  },
  finding_id: null,
  summary: {
    wording_type: "SUMMARY",
    text: "Il testo costituisce un esempio.",
    review_event_id: "review:summary",
    source_quote_sha256: quoteHash,
  },
  translation: {
    wording_type: "TRANSLATION",
    text: "This is only a synthetic example.",
    review_event_id: "review:translation",
    source_quote_sha256: quoteHash,
    source_language: "it",
    language: "en",
  },
};

assert.deepEqual(await validateOriginalStatement(base), base);
assert.deepEqual(await validateOriginalStatement({ ...base, summary: null, translation: null }), {
  ...base, summary: null, translation: null,
}, "derivations are optional and may never substitute the original");

for (const [description, changes] of [
  ["paraphrase replacing original", { original_text: "Parafrasi modificata" }],
  ["wrong source hash", { source_sha256: "" }],
  ["cropped locator", { locator: { start_char: 6, end_char: 7 } }],
  ["insecure original link", { source_url: "http://example.test/synthetic" }],
  ["questionable reported endorsement", { speech_act: "REPORTED_QUOTE", endorsed: true }],
  ["unauthorized finding placeholder", { finding_id: "" }],
  ["missing reviewer", { review_provenance: { ...base.review_provenance, rights: "" } }],
  ["duplicated reviewer", { review_provenance: { ...base.review_provenance, rights: "review:publication" } }],
  ["unrecognized review kind", { review_provenance: { a: "1", b: "2", c: "3", d: "4", e: "5" } }],
  ["nonexistent calendar date", { statement_date: "2026-99-99" }],
  ["translation passed off as original", { translation: { ...base.translation, language: "it" } }],
  ["derived text with unrelated source", { summary: { ...base.summary, source_quote_sha256: "a".repeat(64) } }],
]) {
  await assert.rejects(() => validateOriginalStatement({ ...base, ...changes }), undefined, description);
}

console.log("public-statement-v3 consumer checks PASS (synthetic only, no release routing)");
