import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import demoProjection from "../data/demo-projection.json";
import { assertUniquePublicRoutes } from "./format.ts";
import type { PublicProjection } from "./types";

const EXPECTED_SCHEMA = "dichiarazioni-pubbliche-public-v2";
const DEMO_FINDING_IDS = new Set(demoProjection.dossiers.map((dossier) => dossier.finding_id));
const DEMO_TOPIC_IDS = new Set((demoProjection.topics ?? []).map((topic) => topic.topic_id));
const DEMO_CONTENT_IDS = new Set(demoProjection.dossiers.map((dossier) => dossier.source.content_id));

function containsKnownDemoRecords(projection: PublicProjection): boolean {
  // The fixture may be copied or renamed, or partially edited before being used as
  // an alleged public projection. A filename check cannot protect the public build.
  return projection.dataset_sha256 === demoProjection.dataset_sha256 ||
    projection.dossiers.some((dossier) => DEMO_FINDING_IDS.has(dossier.finding_id)) ||
    (projection.topics ?? []).some((topic) => DEMO_TOPIC_IDS.has(topic.topic_id)) ||
    (projection.contents ?? []).some((content) => DEMO_CONTENT_IDS.has(content.content_id));
}

function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const entries = Object.entries(value as Record<string, unknown>)
    .sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0))
    .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`);
  return `{${entries.join(",")}}`;
}

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
  if (candidate.dossier_count !== candidate.dossiers.length) {
    throw new Error("Public projection dossier_count does not match published dossiers.");
  }
  if (typeof candidate.generated_at !== "string" || !Number.isFinite(Date.parse(candidate.generated_at))) {
    throw new Error("Public projection must have a valid generated_at timestamp.");
  }
  if (!/^[0-9a-f]{64}$/.test(String(candidate.dataset_sha256 ?? ""))) {
    throw new Error("Public projection must have a valid dataset_sha256 fingerprint.");
  }
  if (candidate.methodology?.aggregate_person_score !== false) {
    throw new Error("Public projection must explicitly disable aggregate person scores.");
  }

  assertUniquePublicRoutes(candidate as PublicProjection);

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

  if (candidate.contents !== undefined) {
    if (!Array.isArray(candidate.contents)) {
      throw new Error("Public projection contents must be an array when present.");
    }
    const findingToContent = new Map<string, string>();
    for (const dossier of candidate.dossiers) {
      if (!dossier || typeof dossier !== "object") continue;
      const findingId = String((dossier as { finding_id?: unknown }).finding_id ?? "").trim();
      const contentId = String((dossier as { source?: { content_id?: unknown } }).source?.content_id ?? "").trim();
      if (findingId && contentId) findingToContent.set(findingId, contentId);
    }
    const contentIds = new Set<string>();
    const contentSlugs = new Set<string>();
    for (const content of candidate.contents) {
      if (!content || typeof content !== "object") {
        throw new Error("Public projection contains an invalid Content resource.");
      }
      const contentId = String(content.content_id ?? "").trim();
      const slug = String(content.slug ?? "").trim();
      const title = String(content.title ?? "").trim();
      if (
        !contentId || !slug || !title ||
        content.publication_version !== "public-content-v1" ||
        !Array.isArray(content.review_event_ids) || !content.review_event_ids.length ||
        !Array.isArray(content.finding_ids)
      ) {
        throw new Error("Public Content identity/review provenance is incomplete.");
      }
      if (contentIds.has(contentId) || contentSlugs.has(slug)) {
        throw new Error("Public projection contains duplicate Content identity.");
      }
      contentIds.add(contentId);
      contentSlugs.add(slug);
      for (const findingId of content.finding_ids) {
        if (findingToContent.get(String(findingId)) !== contentId) {
          throw new Error("Public Content references a non-projectable finding.");
        }
      }
    }
  }

  // A legacy v2 bundle may omit additive Topic/Content collections, but its
  // fingerprint still covers every collection actually present. Do not render
  // tampered legacy dossiers simply because `contents` is absent.
  const material: Record<string, unknown> = { dossiers: candidate.dossiers };
  if (candidate.topics !== undefined) material.topics = candidate.topics;
  if (candidate.contents !== undefined) material.contents = candidate.contents;
  const fingerprint = createHash("sha256")
    .update(canonicalJson(material), "utf8")
    .digest("hex");
  if (candidate.dataset_sha256 !== fingerprint) {
    throw new Error("Public projection fingerprint does not match dossiers/topics/contents.");
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
  if (containsKnownDemoRecords(parsed) && process.env.DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION !== "1") {
    throw new Error("Demo projection records cannot be used in a public build. Explicit local demo mode is required.");
  }
  return parsed;
}

export const projectionSchemaVersion = EXPECTED_SCHEMA;
