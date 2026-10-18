import assert from "node:assert/strict";
import { describeReviewedRelation } from "../src/lib/relation-description.ts";

function describe(relationType, rationaleCodes, ...participantPersonIds) {
  return describeReviewedRelation({ relationType, rationaleCodes, participantPersonIds });
}

assert.equal(
  describe("SAME_PROPOSITION", ["CROSS_PERSON_AGREEMENT_REVIEWED"], "person:a", "person:b").label,
  "Accordo tra persone"
);
assert.equal(
  describe("SAME_PROPOSITION", ["CROSS_PERSON_DIVERGENCE_REVIEWED"], "person:a", "person:b").label,
  "Divergenza tra persone"
);
assert.equal(
  describe("POSITION_CHANGE_CANDIDATE", ["NON_OVERLAPPING_TIME"], "person:a", "person:a").label,
  "Cambiamento di posizione revisionato"
);
assert.equal(
  describe("CONTRADICTION_CANDIDATE", ["OVERLAPPING_TEMPORAL_SCOPE"], "person:a", "person:a").label,
  "Contraddizione revisionata"
);
for (const value of [
  describe("SAME_PROPOSITION", [], "person:a", "person:b"),
  describe("SAME_PROPOSITION", ["CROSS_PERSON_AGREEMENT_REVIEWED", "CROSS_PERSON_DIVERGENCE_REVIEWED"], "person:a", "person:b"),
  describe("SAME_PROPOSITION", ["CROSS_PERSON_AGREEMENT_REVIEWED"], "person:a", "person:a"),
  describe("SAME_PROPOSITION", ["CROSS_PERSON_AGREEMENT_REVIEWED"], "UNKNOWN", "person:b"),
  describe("SAME_PROPOSITION", ["CROSS_PERSON_DIVERGENCE_REVIEWED"], "person:a", "person:unresolved"),
  describe("SAME_PROPOSITION", ["CROSS_PERSON_AGREEMENT_REVIEWED"], "person:a", "person: a"),
  describe("POSITION_CHANGE_CANDIDATE", [], "person:a", "person:b"),
  describe("CONTRADICTION_CANDIDATE", [], "person:a", "person:b"),
  describe("CONTRADICTION_CANDIDATE", [], "person:a"),
  describe("UPDATE", ["CROSS_PERSON_DIVERGENCE_REVIEWED"], "person:a", "person:b")
]) {
  assert.equal(/Accordo|Divergenza|Cambiamento|Contraddizione/.test(value.label), false);
}
assert.equal(
  describe("SAME_PROPOSITION", [], "person:a", "person:b").label,
  "Stessa proposizione"
);
console.log("DP-318 reviewed relation descriptions PASS (agreement/divergence/change/contradiction + fail-closed cases)");
