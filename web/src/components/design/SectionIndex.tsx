/**
 * Dichiarazioni Pubbliche — Design System v1 · SectionIndex / Rail
 *
 * The margin index of a long document. It is the `SectionIndex` and
 * `fact-rail` from the UX-v2 component grammar, rebuilt as one component.
 *
 * DESIGN INTENT
 * Navigation only. It never carries content that is not otherwise on the
 * page, and it is removed entirely on a short page rather than padded out.
 *
 * The numbers appear only when the sequence itself carries information the
 * reader needs — a step order, a claim count, an ordered method. `numbered`
 * is a deliberate per-instance decision, not a default, because a number that
 * means nothing is the cheapest-looking decoration in the system.
 *
 * A11Y
 * - A nav landmark, named by `label`, so a screen-reader user can jump to it.
 * - The active entry is `aria-current`, not a color change.
 * - Every entry is a real anchor: middle-click, open-in-new-tab, and copy
 *   link address all work, which a click-handler implementation would break.
 * - `aria-current` is the only position cue that is announced; the cobalt
 *   rail is its visual counterpart, so neither carries the state alone.
 */

import type { ReactNode } from "react";
import { cx } from "./shared";

export interface RailEntry {
  /** The fragment target, e.g. "rationale". */
  id: string;
  /** The visible link text. */
  label: string;
  /**
   * Optional ordinal. Shown only when `numbered` is true. A string so it can
   * be "3" or "3/7" — a position, never a score.
   */
  ordinal?: string;
}

export interface SectionIndexProps {
  /** Names the nav landmark. Required: an unnamed nav is a trap. */
  label: string;
  entries: RailEntry[];
  /** The id of the section the reader is currently in. */
  activeId?: string;
  /** Show ordinals. Only when the sequence carries real information. */
  numbered?: boolean;
  /** Extra content below the index, e.g. the "Limits" block. */
  children?: ReactNode;
  className?: string;
}

export function SectionIndex({
  label,
  entries,
  activeId,
  numbered = false,
  children,
  className
}: SectionIndexProps) {
  // An index with one entry is not an index.
  if (entries.length < 2) return null;

  return (
    <nav aria-label={label} className={cx("dp-rail", className)}>
      <h2 className="dp-rail__heading">{label}</h2>
      <ol className="dp-rail__list">
        {entries.map((entry) => {
          const isActive = entry.id === activeId;
          return (
            <li key={entry.id}>
              <a
                href={`#${entry.id}`}
                aria-current={isActive ? "true" : undefined}
                className="dp-rail__link"
              >
                {numbered && entry.ordinal !== undefined ? (
                  <span className="dp-rail__numbered">
                    <span className="dp-rail__number" aria-hidden="true">
                      {entry.ordinal}
                    </span>
                    <span>{entry.label}</span>
                  </span>
                ) : (
                  entry.label
                )}
              </a>
            </li>
          );
        })}
      </ol>
      {children}
    </nav>
  );
}

export default SectionIndex;
