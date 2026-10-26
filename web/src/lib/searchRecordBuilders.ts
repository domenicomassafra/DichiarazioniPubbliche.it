/** Canonical public-only search document construction. */
import type { PublicDossier } from "./types.ts";
import type { ApprovedPersonV3 } from "./publicPersonV3.ts";
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

/** Index original public statements without inventing a factual Finding. */
export function statementRecords(people: ApprovedPersonV3[]): PublicSearchRecord[] {
  const records: PublicSearchRecord[] = [];
  for (const person of people) {
    for (const statement of person.statements) {
      records.push({
        id: statement.statement_id,
        kind: "statement",
        title: `Dichiarazione di ${person.display_name}`,
        subtitle: `${statement.source_title} · ${statement.statement_date}`,
        published_at: null, // Statement date is not a publication timestamp.
        assessment: null,
        route: statement.statement_route,
        person_id: person.slug,
        has_corrections: false,
        has_rights_of_reply: false,
        wording_type: null,
        source_wording_type: null,
        direct_quote_eligible: false,
        primary_terms: compactTerms([statement.original_text, person.display_name]),
        secondary_terms: compactTerms([
          statement.source_title, statement.statement_date,
          statement.role_at_statement?.label,
        ]),
      });
    }
  }
  return records;
}
