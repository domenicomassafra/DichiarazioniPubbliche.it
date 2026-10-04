/**
 * Dichiarazioni Pubbliche — Design System v1 · StatusText
 *
 * The text-first finding state. This is the single most safety-critical
 * primitive in the system, and the constraints below are product invariants
 * expressed as types and runtime guards rather than as documentation.
 *
 * PRODUCT INVARIANTS ENFORCED HERE
 * 1. TEXT FIRST. A finding state is a word. The mark reinforces the word; it
 *    never carries it. If `label` is empty, this component renders nothing at
 *    all, because a state with no word is not a state.
 * 2. NO IDENTITY COLOR. `state` is a relation between a claim and its
 *    evidence. It is never applied to a person, party or entity. The type
 *    admits only the four finding states; there is no `personState`.
 * 3. NO AGGREGATE. `value` and `count` exist for "3 fonti" — a count of
 *    things, which is a fact — not for a verdict total. See the guard below.
 * 4. NO RANKING. There is deliberately no `score`, `rating`, or `rank` prop.
 * 5. GRAYSCALE LEGIBLE. `unresolved` is drawn with a hollow mark while the
 *    other three are filled, so the filled/hollow distinction survives a
 *    grayscale printout with no hue at all.
 * 6. NO BIOMETRICS. Nothing here accepts an image, a name, or an identity
 *    claim; speaker provenance is textual and lives in the source row.
 *
 * A11Y
 * The mark is `aria-hidden`: the accessible name is the word alone. That is
 * what stops a screen reader announcing "black square, Sostenuta".
 */

import { finding, findingLabel } from "../../lib/tokens";
import type { FindingState } from "../../lib/tokens";
import { cx } from "./shared";

export interface StatusTextProps {
  /**
   * The written finding state. `UNSUPPORTED` and friends from the public
   * projection map to these four; the mapping belongs to the caller's
   * projection layer, not here.
   */
  state: FindingState;
  /**
   * The word. Optional so a caller can fall back to the system's own Italian
   * label, but an explicitly empty string renders nothing (invariant 1).
   */
  label?: string;
  /** A count of concrete things, e.g. "3 fonti". Never a verdict total. */
  count?: number;
  /** What `count` counts, e.g. "fonti". Rendered after the number. */
  countNoun?: string;
  /** Suppress the mark when the surrounding context already carries one. */
  hideMark?: boolean;
  /** Use the quieter, regular-weight treatment for dense Studio rows. */
  quiet?: boolean;
  className?: string;
}

/**
 * Guards the aggregate-verdict rule. A count above this threshold is not a
 * "count of sources" in any honest public context; it is a score wearing a
 * noun. Refusing to render it is cheaper than explaining the difference.
 */
const MAX_HONEST_COUNT = 50;

export function StatusText({
  state,
  label,
  count,
  countNoun,
  hideMark = false,
  quiet = false,
  className
}: StatusTextProps) {
  const text = label === undefined ? findingLabel[state] : label;

  // Invariant 1: no word, no state.
  if (text === "") return null;

  // Invariant 3: refuse a number that is functioning as a score.
  if (count !== undefined && count > MAX_HONEST_COUNT) return null;

  const scale = finding[state];

  return (
    <span
      data-state={state}
      data-quiet={quiet ? "true" : undefined}
      // Exposed so a consumer can read the verified color without a hardcode.
      data-state-color={scale.text}
      className={cx("dp-status", quiet && "dp-status--quiet", className)}
    >
      {!hideMark && <span className="dp-status__mark" aria-hidden="true" />}
      <span className="dp-status__label">{text}</span>
      {count !== undefined && countNoun ? (
        <>
          {" "}
          <span className="dp-status__count">
            {count} {countNoun}
          </span>
        </>
      ) : null}
    </span>
  );
}

export default StatusText;
