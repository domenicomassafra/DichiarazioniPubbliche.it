import fs from "node:fs/promises";
import path from "node:path";
import demoProjection from "../data/demo-projection.json";
import type { PublicProjection } from "./types";

const EXPECTED_SCHEMA = "dichiarazioni-pubbliche-public-v2";

function assertProjection(value: unknown): asserts value is PublicProjection {
  if (!value || typeof value !== "object") {
    throw new Error("Public projection must be a JSON object.");
  }

  const candidate = value as Partial<PublicProjection>;
  if (candidate.schema_version !== EXPECTED_SCHEMA) {
    throw new Error(
      `Unsupported public projection schema: ${String(candidate.schema_version)}`
    );
  }
  if (!Array.isArray(candidate.dossiers)) {
    throw new Error("Public projection dossiers must be an array.");
  }
  if (candidate.methodology?.aggregate_person_score !== false) {
    throw new Error("Public projection must explicitly disable aggregate person scores.");
  }

  if (candidate.topics !== undefined) {
    if (!Array.isArray(candidate.topics)) {
      throw new Error("Public projection topics must be an array when present.");
    }
    const findingToClaim = new Map<string, string>();
    for (const dossier of candidate.dossiers) {
      if (!dossier || typeof dossier !== "object") continue;
      const findingId = String((dossier as { finding_id?: unknown }).finding_id ?? "").trim();
      const claimId = String((dossier as { claim_id?: unknown }).claim_id ?? "").trim();
      if (findingId && claimId) findingToClaim.set(findingId, claimId);
    }
    const topicIds = new Set<string>();
    const topicSlugs = new Set<string>();
    for (const topic of candidate.topics) {
      if (!topic || typeof topic !== "object") {
        throw new Error("Public projection contains an invalid Topic resource.");
      }
      const topicId = String(topic.topic_id ?? "").trim();
      const slug = String(topic.slug ?? "").trim();
      const name = String(topic.canonical_name ?? "").trim();
      if (!topicId || !slug || !name || !Array.isArray(topic.review_event_ids) || !topic.review_event_ids.length) {
        throw new Error("Public Topic identity/review provenance is incomplete.");
      }
      if (topicIds.has(topicId) || topicSlugs.has(slug)) {
        throw new Error("Public projection contains duplicate Topic identity.");
      }
      topicIds.add(topicId);
      topicSlugs.add(slug);
      if (!Array.isArray(topic.memberships)) {
        throw new Error("Public Topic memberships must be an array.");
      }
      for (const membership of topic.memberships) {
        if (!membership || typeof membership !== "object") {
          throw new Error("Public Topic contains an invalid membership.");
        }
        const claimId = String(membership.claim_id ?? "").trim();
        if (
          !String(membership.membership_id ?? "").trim() ||
          !claimId ||
          !Array.isArray(membership.review_event_ids) ||
          !membership.review_event_ids.length ||
          !Array.isArray(membership.finding_ids) ||
          !membership.finding_ids.length
        ) {
          throw new Error("Public Topic membership/review provenance is incomplete.");
        }
        for (const findingId of membership.finding_ids) {
          if (findingToClaim.get(String(findingId)) !== claimId) {
            throw new Error("Public Topic membership references a non-projectable finding.");
          }
        }
      }
    }
  }
}

export async function loadPublicProjection(): Promise<PublicProjection> {
  const configuredPath = process.env.DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH;
  if (!configuredPath) {
    if (process.env.DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION === "1") {
      assertProjection(demoProjection);
      return demoProjection as PublicProjection;
    }
    throw new Error(
      "DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH is required. " +
      "Set DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 only for explicit local demo builds."
    );
  }

  const resolved = path.resolve(configuredPath);
  const raw = await fs.readFile(resolved, "utf8");
  const parsed: unknown = JSON.parse(raw);
  assertProjection(parsed);
  return parsed;
}

export const projectionSchemaVersion = EXPECTED_SCHEMA;
