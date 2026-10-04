import type { AssessmentCode, PublicDossier } from "./types";

export const assessmentLabels: Record<string, string> = {
  SUPPORTED: "Supportata",
  FACTUALLY_FALSE: "Conclusione fattualmente falsa",
  OUTDATED_DATA: "Dato superato",
  INSUFFICIENT_EVIDENCE: "Prove insufficienti",
  UNRESOLVED: "Non risolta"
};

export function assessmentLabel(code: AssessmentCode): string {
  return assessmentLabels[code] ?? "Valutazione non disponibile";
}

export function assessmentTone(code: AssessmentCode): string {
  if (code === "SUPPORTED") return "support";
  if (code === "FACTUALLY_FALSE") return "contradict";
  if (code === "OUTDATED_DATA") return "outdated";
  if (code === "INSUFFICIENT_EVIDENCE") return "insufficient";
  return "unresolved";
}

export function formatDate(value?: string | null): string {
  if (!value) return "Data non disponibile";
  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  }).format(new Date(value));
}

export function dossierSlug(dossier: PublicDossier): string {
  return dossier.finding_id
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function speakerSlug(dossier: PublicDossier): string {
  return publicIdSlug(dossier.speaker.id);
}

export function publicIdSlug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function contentSlug(dossier: PublicDossier): string {
  return publicIdSlug(dossier.source.content_id);
}

export function relationSlug(relationId: string): string {
  return publicIdSlug(relationId);
}
