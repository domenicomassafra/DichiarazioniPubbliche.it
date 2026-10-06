import assert from "node:assert/strict";
import {
  buildSearchIndexMaterial,
  canonicalJson,
  finalizeSearchIndex,
} from "../src/lib/searchIndex.ts";

const privateSentinels = [
  "PRIVATE-HIGH-RISK-SCORE-71",
  "PRIVATE-HIGH-RISK-NOTES",
  "PRIVATE-REVIEWER-ACTOR-REF",
  "PRIVATE-CREDENTIAL-FINGERPRINT",
  "PRIVATE-HIGH-RISK-REASON",
  "HOLD_HIGH_RISK_HUMAN_REVIEW_REQUIRED",
];

const projection = {
  schema_version: "dichiarazioni-pubbliche-public-v2",
  generated_at: "2026-10-06T00:00:00Z",
  dataset_sha256: "a".repeat(64),
  methodology: {
    claim_level_only: true,
    aggregate_person_score: false,
    requires_publication_gate: true,
    requires_approved_evidence: true,
    requires_resolved_transcript: true,
  },
  dossier_count: 1,
  omitted_count: 0,
  dossiers: [{
    finding_id: "finding:high-risk-search-proof",
    claim_id: "claim:high-risk-search-proof",
    claim: "Proposizione pubblica sintetica.",
    claim_type: "LEGAL_POLICY_STATUS",
    speaker: { id: "person:proof", name: "Persona prova", public_roles: [] },
    source: {
      content_id: "content:proof",
      url: "https://example.test/proof",
      title: "Fonte prova",
      published_at: "2026-10-05T10:00:00Z",
      segments: [],
    },
    finding: {
      assessment: "SUPPORTED",
      publication_status: "PUBLISH",
      rationale: "Razionale pubblico.",
      published_at: "2026-10-05T11:00:00Z",
    },
    evidence: [],
    corrections: [{
      id: "correction:private-proof",
      changed_fields: {
        high_risk_score: privateSentinels[0],
        high_risk_notes: privateSentinels[1],
        reviewer_actor_ref: privateSentinels[2],
        credential_fingerprint: privateSentinels[3],
        high_risk_private_reason: privateSentinels[4],
        status_reason: privateSentinels[5],
      },
    }],
    rights_of_reply: [],
  }],
  topics: [],
  contents: [],
};

const index = await finalizeSearchIndex(buildSearchIndexMaterial(projection));
const encoded = canonicalJson(index);
for (const sentinel of privateSentinels) {
  assert.equal(encoded.includes(sentinel), false, `search index leaked ${sentinel}`);
}
for (const key of [
  "high_risk_score",
  "high_risk_notes",
  "reviewer_actor_ref",
  "credential_fingerprint",
  "high_risk_private_reason",
]) {
  assert.equal(encoded.includes(key), false, `search index leaked internal key ${key}`);
}

console.log(`high-risk public search serializer PASS (${index.records.length} records)`);
