/** Only the values React reads live here; all other design tokens are native CSS
 * custom properties in ../styles/tokens.css. */

export type Density = "public" | "studio";
export type FindingState = "supported" | "contradicted" | "imprecise" | "unresolved";

// A finding describes evidence for a claim, never a person or a ranking.
export const finding = {
  supported: { text: "var(--support-700)" },
  contradicted: { text: "var(--contradict-700)" },
  imprecise: { text: "var(--imprecise-700)" },
  unresolved: { text: "var(--unresolved-700)" }
} as const satisfies Record<FindingState, { readonly text: string }>;

export const findingLabel = {
  supported: "Sostenuta",
  contradicted: "Contradetta",
  imprecise: "Imprecisa",
  unresolved: "Non risolta"
} as const satisfies Record<FindingState, string>;
