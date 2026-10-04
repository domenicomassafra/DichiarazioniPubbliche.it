/**
 * Dichiarazioni Pubbliche — Design System v1 · shared primitive contracts
 *
 * Types and small helpers shared by the components in this directory.
 * No component in `components/design/**` may introduce a literal color,
 * radius, duration or font: they all resolve through here or through
 * `lib/tokens.ts`.
 */

import type { Density, FindingState } from "../../lib/tokens";

/**
 * The four finding states, re-exported so a consumer imports the component
 * vocabulary and the state vocabulary from one place.
 *
 * PRODUCT INVARIANT: a finding state is a written finding about a claim and
 * its evidence. It is never a score, a rank, a vote, or an opinion about a
 * person, party or entity.
 */
export type { Density, FindingState };

/** Join class names, dropping falsy entries. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/** A density is a data attribute, never a prop that changes the markup. */
export const densityAttr = (density: Density): Record<string, string> => ({
  "data-density": density
});
