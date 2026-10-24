import { relationSlug } from "./format";
import type { PublicDossier, PublicProjection } from "./types";

export interface PublicTrace {
  id: string;
  slug: string;
  relationType: string;
  relationVersion: string;
  reviewEventId: string;
  rationaleCodes: string[];
  participants: PublicDossier[];
}

export function collectPublicTraces(projection: PublicProjection): PublicTrace[] {
  const byClaim = new Map(projection.dossiers.map((dossier) => [dossier.claim_id, dossier]));
  const traces = new Map<string, PublicTrace>();
  const conflictingIds = new Set<string>();

  for (const dossier of projection.dossiers) {
    for (const relation of dossier.relations ?? []) {
      if (relation.status !== "APPROVED" || !relation.review_event_id) continue;
      const related = byClaim.get(relation.related_claim_id);
      if (!related || conflictingIds.has(relation.id)) continue;

      const previous = traces.get(relation.id);
      // A shared ID cannot combine different approved review receipts, policy
      // versions, relation types or rationale. Drop the entire disputed Trace
      // rather than assigning later participants the first edge's authority.
      if (previous && (previous.relationType !== relation.relation_type ||
          previous.relationVersion !== relation.relation_version ||
          previous.reviewEventId !== relation.review_event_id ||
          JSON.stringify([...previous.rationaleCodes].sort()) !==
            JSON.stringify([...(relation.rationale_codes ?? [])].sort()))) {
        traces.delete(relation.id);
        conflictingIds.add(relation.id);
        continue;
      }

      const current = previous ?? {
        id: relation.id,
        slug: relationSlug(relation.id),
        relationType: relation.relation_type,
        relationVersion: relation.relation_version,
        reviewEventId: relation.review_event_id,
        rationaleCodes: relation.rationale_codes ?? [],
        participants: []
      };

      for (const participant of [dossier, related]) {
        if (!current.participants.some((item) => item.finding_id === participant.finding_id)) {
          current.participants.push(participant);
        }
      }
      traces.set(relation.id, current);
    }
  }

  return [...traces.values()]
    .filter((trace) => trace.participants.length >= 2)
    .map((trace) => ({
      ...trace,
      participants: [...trace.participants].sort((a, b) => {
        const left = Date.parse(a.source.published_at ?? a.finding.published_at ?? "1970-01-01");
        const right = Date.parse(b.source.published_at ?? b.finding.published_at ?? "1970-01-01");
        return left - right || a.finding_id.localeCompare(b.finding_id);
      })
    }));
}
