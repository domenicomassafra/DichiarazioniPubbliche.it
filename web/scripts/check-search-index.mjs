import assert from "node:assert/strict";
import {
  SEARCH_QUERY_MAX_CHARS,
  buildExploreSearch,
  buildSearchIndexMaterial,
  canonicalJson,
  finalizeSearchIndex,
  searchPublicIndex,
  parseExploreSearch,
  validateSearchIndex,
} from "../src/lib/searchIndex.ts";

const dossier = (id, claim, speaker, source, publishedAt, assessment = "SUPPORTED", sourceWordingType = "VERBATIM_ORIGINAL") => ({
  finding_id: id,
  claim_id: `claim:${id}`,
  claim,
  claim_type: "NUMERIC_STATISTIC",
  speaker: { id: `person:${speaker.toLowerCase()}`, name: speaker, public_roles: [] },
  source: {
    content_id: `content:${id}`,
    url: `https://example.test/${id}`,
    title: source,
    published_at: publishedAt,
    segments: [],
  },
  finding: { assessment, publication_status: "PUBLISHED", rationale: "Public rationale", published_at: publishedAt },
  evidence: [],
  corrections: id === "finding:corretto" ? [{ id: "correction:1" }] : [],
  rights_of_reply: id === "finding:corretto" ? [{ id: "reply:1" }] : [],
  wording: {
    version: "wording-contract-v1",
    source_occurrence: {
      occurrence_id: `statement:${id}`,
      wording_type: sourceWordingType,
      text_sha256: "b".repeat(64),
      language: "it",
      direct_quote_eligible: sourceWordingType === "VERBATIM_ORIGINAL",
      representation_role: "SOURCE_OCCURRENCE",
    },
    normalized_claim: {
      wording_type: "PARAPHRASE",
      text_sha256: "c".repeat(64),
      source_occurrence_id: `statement:${id}`,
      source_wording_type: sourceWordingType,
      language: "it",
      derivation_method: "CLAIM_NORMALIZATION",
      derivation_version: "test-v1",
      direct_quote_eligible: false,
      representation_role: "DERIVED_REPRESENTATION",
    },
    representations: [],
    public_provenance: { segment_ids: [], text_provenance_ids: [] },
  },
});

const projection = {
  schema_version: "dichiarazioni-pubbliche-public-v2",
  generated_at: "2026-10-05T12:00:00+00:00",
  dataset_sha256: "a".repeat(64),
  methodology: {
    claim_level_only: true,
    aggregate_person_score: false,
    requires_publication_gate: true,
    requires_approved_evidence: true,
    requires_resolved_transcript: true,
  },
  dossier_count: 3,
  omitted_count: 0,
  dossiers: [
    dossier("finding:esatto", "L'inflazione è al 2 per cento", "José Rossi", "ISTAT", "2026-10-05T10:00:00Z"),
    dossier("finding:fonte", "Il dato è stabile", "Anna Bianchi", "Rapporto inflazione annuale", "2026-10-04T10:00:00Z"),
    dossier("finding:corretto", "La spesa è aumentata", "Mario Verdi", "Bilancio", "2026-10-03T10:00:00Z", "OUTDATED_DATA", "REPORTED_QUOTE"),
  ],
  topics: [{
    topic_id: "topic:economia",
    slug: "economia",
    canonical_name: "Economìa",
    scope_text: "Dati economici",
    entity_version: "topic-v1",
    review_event_ids: ["review:topic"],
    memberships: [],
  }],
  contents: [],
};

const material = buildSearchIndexMaterial(projection);
const index = await finalizeSearchIndex(material);
const second = await finalizeSearchIndex(buildSearchIndexMaterial(projection));
assert.equal(canonicalJson(index), canonicalJson(second), "same projection must produce identical bytes");
assert.deepEqual(await validateSearchIndex(structuredClone(index), projection.dataset_sha256), index);

const accent = searchPublicIndex(index, "Jose Rossi");
assert.equal(accent.records[0]?.id, "person:josé rossi", "diacritics must not affect matching");
const phrase = searchPublicIndex(index, "inflazione");
assert.equal(phrase.records[0]?.id, "finding:esatto", "claim match must rank before source metadata match");
const corrected = searchPublicIndex(index, "spesa").records[0];
assert.equal(corrected?.has_corrections, true);
assert.equal(corrected?.has_rights_of_reply, true);
assert.equal(corrected?.wording_type, "PARAPHRASE");
assert.equal(corrected?.source_wording_type, "REPORTED_QUOTE");
assert.equal(corrected?.direct_quote_eligible, false);
assert.equal(index.records.filter((record) => record.kind === "finding").every((record) => record.wording_type === "PARAPHRASE" && record.direct_quote_eligible === false), true);
assert.equal(index.records.filter((record) => record.kind !== "finding").every((record) => record.wording_type === null && record.direct_quote_eligible === false), true);
assert.equal(searchPublicIndex(index, "").records[0]?.id, "finding:esatto", "empty query must use recent order");
assert.equal(searchPublicIndex(index, "x".repeat(SEARCH_QUERY_MAX_CHARS + 1)).status, "QUERY_TOO_LONG");
assert.equal(searchPublicIndex(index, "spesa", { assessment: "SUPPORTED" }).records.length, 0);
assert.equal(searchPublicIndex(index, "economia").records[0]?.kind, "topic");

const urlState = {
  query: " José Rossi ",
  kind: "person",
  assessment: "SUPPORTED",
  sort: "recent",
};
const encodedState = buildExploreSearch(urlState);
assert.deepEqual(parseExploreSearch(`?${encodedState}`), { ...urlState, query: "José Rossi" });
assert.deepEqual(parseExploreSearch("?tipo=private&esito=SECRET&ordine=random"), {
  query: "",
  kind: "ALL",
  assessment: "ALL",
  sort: "relevance",
});

const tampered = structuredClone(index);
tampered.records[0].title = "tampered";
await assert.rejects(() => validateSearchIndex(tampered, projection.dataset_sha256), /TAMPERED/);
await assert.rejects(() => validateSearchIndex(index, "b".repeat(64)), /INCOMPATIBLE/);

const encoded = canonicalJson(index);
for (const forbidden of [
  "raw_text",
  "canonical_text",
  "provider_receipt",
  "credential",
  "person_score",
  "public_attribution_input",
  "retrieval_score",
  "supporting_features",
  "contradicting_features",
  "speaker_label",
  "identifier_value",
]) {
  assert.equal(encoded.includes(forbidden), false, `index leaked forbidden field marker: ${forbidden}`);
}
assert.equal(encoded.includes('"direct_quote_eligible":true'), false, "search index must never create direct-quote authority");

console.log(`search-index checks PASS (${index.records.length} records, ${encoded.length} bytes)`);
