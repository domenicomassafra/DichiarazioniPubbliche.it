/** Canonical public-only search document construction. */
import type { PublicDossier } from "./types.ts";
import type { PublicSearchRecord } from "./searchIndex.ts";
import { publicIdSlug } from "./format.ts";

export function compactTerms(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const terms: string[] = [];
  for (const raw of values) {
    const value = String(raw ?? "").trim();
    if (!value || seen.has(value)) continue;
    seen.add(value);
    terms.push(value);
  }
  return terms;
}

export function findingRecord(dossier: PublicDossier): PublicSearchRecord {
  const roles = (dossier.speaker.public_roles ?? []).flatMap(role => [
    role.role, role.organization_name ?? null,
  ]);
  return {
    id: dossier.finding_id,
    kind: "finding",
    title: dossier.claim,
    subtitle: [dossier.speaker.name, dossier.source.title].filter(Boolean).join(" · "),
    published_at: dossier.finding.published_at ?? dossier.source.published_at ?? null,
    assessment: dossier.finding.assessment,
    route: `/dichiarazioni/${publicIdSlug(dossier.finding_id)}/`,
    has_corrections: (dossier.corrections ?? []).length > 0,
    has_rights_of_reply: (dossier.rights_of_reply ?? []).length > 0,
    wording_type: "PARAPHRASE",
    source_wording_type: dossier.wording?.source_occurrence.wording_type ?? null,
    direct_quote_eligible: false,
    primary_terms: compactTerms([dossier.claim]),
    secondary_terms: compactTerms([
      dossier.speaker.name, dossier.source.title, dossier.claim_type,
      dossier.finding.assessment, ...roles,
    ]),
    person_id: dossier.speaker.id,
    topic_ids: [],
  };
}
