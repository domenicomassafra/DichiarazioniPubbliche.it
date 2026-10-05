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

const claimTypeLabels: Record<string, string> = {
  ARITHMETIC: "Calcolo",
  CAUSAL_CLAIM: "Rapporto causale",
  CURRENT_FOREIGN_POLICY: "Politica estera",
  CURRENT_POLICY: "Politica pubblica",
  CURRENT_POLICY_POSITION: "Posizione su una politica",
  DISTRIBUTIONAL_CLAIM: "Distribuzione / impatto",
  ELECTION_PREDICTION: "Previsione elettorale",
  FISCAL_INFERENCE: "Inferenza fiscale",
  GROUP_MOTIVE: "Attribuzione a un gruppo",
  HISTORICAL_ATTRIBUTION: "Attribuzione storica",
  HISTORICAL_CLAIM: "Affermazione storica",
  HISTORICAL_POLITICAL: "Politica storica",
  LEGAL_POLICY_STATUS: "Stato normativo",
  LEGAL_QUOTE: "Citazione normativa",
  MOTIVE_ATTRIBUTION: "Attribuzione di intenzione",
  NUMERIC_STATISTIC: "Dato numerico",
  POLICY_DIFFERENCE: "Confronto tra politiche",
  POLICY_SCOPE: "Ambito di una politica",
  POLITICAL_ATTRIBUTION: "Attribuzione politica",
  PRICE_STATISTIC: "Prezzi",
  QUOTE_ATTRIBUTION: "Attribuzione di citazione",
  RHETORICAL_GENERALIZATION: "Generalizzazione",
  SYSTEMIC_CLAIM: "Affermazione sistemica",
  SYSTEMIC_INFERENCE: "Inferenza sistemica",
  TAX_RATE: "Aliquota / tassazione",
  VALUE_JUDGMENT: "Giudizio di valore"
};

export function claimTypeLabel(value: string): string {
  return claimTypeLabels[value] ?? value.replaceAll("_", " ").toLocaleLowerCase("it-IT");
}
